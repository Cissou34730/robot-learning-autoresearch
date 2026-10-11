"""Shared scenario mechanics for training and evaluation.

This module owns every behavior shared by training and evaluation: the MuJoCo
model, target sampling, success and hold semantics, observations and reward.
Training-only target construction lives in
`robot_learning/training/environment.py` so it can change without
altering how a saved policy is measured.

The benchmark constants are defaults, not a contract: research may train on a
different distribution, tolerance or horizon. The human-defined task is
enforced only by the protected benchmark in `benchmark/`.
"""

from typing import Any, ClassVar

import gymnasium as gym
import mujoco
import numpy as np

from contracts.robots.two_joint_arm import (
    FOREARM_LENGTH,
    TWO_JOINT_ARM_XML_PATH,
    UPPER_ARM_LENGTH,
)
from contracts.task_spec import (
    FRAME_SKIP,
    HOLD_SECONDS,
    MAX_EPISODE_STEPS,
    SUCCESS_THRESHOLD,
    TARGET_RADIUS_RANGE,
)
from robot_learning.scenario.observations import OBSERVATION_SIZE
from robot_learning.scenario.policy_io import (
    CONTROL_PROFILE_MARKER,
    DIRECT_CONTROL_PROFILE,
    KNOWN_CONTROL_PROFILES,
    RESIDUAL_TORQUE_PROFILE,
    make_policy_io,
)
from robot_learning.training.reward import (
    DEFAULT_REWARD_PROFILE,
    TARGETED_REGULATION_PROFILE,
    reach_reward,
)


JOINT_ATTRACTION_GAIN = 0.65
JOINT_ERROR_SCALE = 0.70
JOINT_VELOCITY_DAMPING_GAIN = 0.18
JOINT_VELOCITY_SCALE = 2.0
ENDPOINT_ERROR_GAIN = 0.80
ENDPOINT_ERROR_SCALE = 0.025
ENDPOINT_VELOCITY_DAMPING_GAIN = 0.28
ENDPOINT_VELOCITY_SCALE = 0.50
ENDPOINT_BOUNDARY_OUTER_DISTANCE = 0.05
JOINT_LIMIT_RADIANS = np.deg2rad(170.0)
JOINT_LIMIT_MARGIN = np.deg2rad(20.0)
JOINT_LIMIT_REPULSION_GAIN = 0.25
SINGULAR_ELBOW_THRESHOLD = 0.12
SINGULAR_ELBOW_ESCAPE_GAIN = 0.08
RESIDUAL_ACTION_SCALE = 0.35


def _validate_control_profile(control_profile: str) -> None:
    if (
        not isinstance(control_profile, str)
        or control_profile not in KNOWN_CONTROL_PROFILES
    ):
        raise ValueError(f"unknown control profile: {control_profile}")


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _planar_ik_branches(target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    target_x, target_y = float(target[0]), float(target[1])
    target_angle = float(np.arctan2(target_y, target_x))
    radius_squared = target_x**2 + target_y**2
    cosine_elbow = (
        radius_squared
        - UPPER_ARM_LENGTH**2
        - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_magnitude = float(np.arccos(np.clip(cosine_elbow, -1.0, 1.0)))

    branches = []
    for elbow in (elbow_magnitude, -elbow_magnitude):
        shoulder = target_angle - np.arctan2(
            FOREARM_LENGTH * np.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
        )
        branches.append(np.array([shoulder, elbow], dtype=np.float64))
    return branches[0], branches[1]


def _forward_kinematics(q: np.ndarray) -> np.ndarray:
    q1, q2 = float(q[0]), float(q[1])
    return np.array(
        [
            UPPER_ARM_LENGTH * np.cos(q1)
            + FOREARM_LENGTH * np.cos(q1 + q2),
            UPPER_ARM_LENGTH * np.sin(q1)
            + FOREARM_LENGTH * np.sin(q1 + q2),
        ],
        dtype=np.float64,
    )


def _planar_jacobian(q: np.ndarray) -> np.ndarray:
    q1, q2 = float(q[0]), float(q[1])
    distal_angle = q1 + q2
    return np.array(
        [
            [
                -UPPER_ARM_LENGTH * np.sin(q1)
                - FOREARM_LENGTH * np.sin(distal_angle),
                -FOREARM_LENGTH * np.sin(distal_angle),
            ],
            [
                UPPER_ARM_LENGTH * np.cos(q1)
                + FOREARM_LENGTH * np.cos(distal_angle),
                FOREARM_LENGTH * np.cos(distal_angle),
            ],
        ],
        dtype=np.float64,
    )


def _select_ik_branch(q: np.ndarray, target: np.ndarray) -> np.ndarray:
    branches = _planar_ik_branches(target)
    errors = [
        np.array(
            [
                _wrap_to_pi(float(branch[0] - q[0])),
                _wrap_to_pi(float(branch[1] - q[1])),
            ],
            dtype=np.float64,
        )
        for branch in branches
    ]
    selected_index = int(np.argmin([np.linalg.norm(error) for error in errors]))
    return branches[selected_index]


def _joint_limit_repulsion(q: np.ndarray) -> np.ndarray:
    repulsion = np.zeros(2, dtype=np.float64)
    for index, joint in enumerate(q):
        lower_distance = float(joint + JOINT_LIMIT_RADIANS)
        upper_distance = float(JOINT_LIMIT_RADIANS - joint)
        if lower_distance < JOINT_LIMIT_MARGIN:
            repulsion[index] += JOINT_LIMIT_REPULSION_GAIN * np.clip(
                1.0 - lower_distance / JOINT_LIMIT_MARGIN,
                0.0,
                1.0,
            )
        if upper_distance < JOINT_LIMIT_MARGIN:
            repulsion[index] -= JOINT_LIMIT_REPULSION_GAIN * np.clip(
                1.0 - upper_distance / JOINT_LIMIT_MARGIN,
                0.0,
                1.0,
            )
    return repulsion


def _residual_control_action(
    learned_action: np.ndarray,
    q: np.ndarray,
    qvel: np.ndarray,
    target: np.ndarray,
    success_threshold: float,
) -> np.ndarray:
    selected_branch = _select_ik_branch(q, target)
    joint_error = np.array(
        [
            _wrap_to_pi(float(selected_branch[0] - q[0])),
            _wrap_to_pi(float(selected_branch[1] - q[1])),
        ],
        dtype=np.float64,
    )
    joint_attraction = JOINT_ATTRACTION_GAIN * np.tanh(
        joint_error / JOINT_ERROR_SCALE
    )
    joint_damping = JOINT_VELOCITY_DAMPING_GAIN * np.tanh(
        qvel / JOINT_VELOCITY_SCALE
    )
    nominal_torque = np.clip(
        joint_attraction - joint_damping,
        -1.0,
        1.0,
    )

    current_endpoint = _forward_kinematics(q)
    endpoint_error = np.asarray(target[:2], dtype=np.float64) - current_endpoint
    jacobian = _planar_jacobian(q)
    endpoint_term = ENDPOINT_ERROR_GAIN * np.tanh(
        (jacobian.T @ endpoint_error) / ENDPOINT_ERROR_SCALE
    )

    endpoint_velocity = jacobian @ qvel
    distance = float(np.linalg.norm(endpoint_error))
    boundary_weight = np.clip(
        (ENDPOINT_BOUNDARY_OUTER_DISTANCE - distance)
        / (ENDPOINT_BOUNDARY_OUTER_DISTANCE - success_threshold),
        0.0,
        1.0,
    )
    endpoint_velocity_term = -(
        ENDPOINT_VELOCITY_DAMPING_GAIN
        * boundary_weight
        * np.tanh((jacobian.T @ endpoint_velocity) / ENDPOINT_VELOCITY_SCALE)
    )

    limit_term = _joint_limit_repulsion(q)
    singular_escape = np.zeros(2, dtype=np.float64)
    if abs(float(q[1])) < SINGULAR_ELBOW_THRESHOLD:
        target_angle = float(np.arctan2(target[1], target[0]))
        escape_direction = 1.0 if target_angle >= 0.0 else -1.0
        singular_escape[1] = SINGULAR_ELBOW_ESCAPE_GAIN * escape_direction

    return np.clip(
        nominal_torque
        + endpoint_term
        + endpoint_velocity_term
        + limit_term
        + singular_escape
        + RESIDUAL_ACTION_SCALE * learned_action,
        -1.0,
        1.0,
    )


class TwoJointArmReachEnv(gym.Env[np.ndarray, np.ndarray]):
    metadata: ClassVar[dict[str, Any]] = {"render_modes": []}

    def __init__(
        self,
        *,
        target_radius_range: tuple[float, float] = TARGET_RADIUS_RANGE,
        success_threshold: float = SUCCESS_THRESHOLD,
        hold_seconds: float = HOLD_SECONDS,
        frame_skip: int = FRAME_SKIP,
        max_episode_steps: int = MAX_EPISODE_STEPS,
        policy_runtime=None,
        reward_profile: str = DEFAULT_REWARD_PROFILE,
        control_profile: str = DIRECT_CONTROL_PROFILE,
    ) -> None:
        super().__init__()
        _validate_control_profile(control_profile)
        self.max_episode_steps = max_episode_steps
        self.frame_skip = frame_skip
        self.target_radius_range = target_radius_range
        if policy_runtime is not None:
            self.policy_io = policy_runtime.io
            self.control_profile = getattr(
                self.policy_io,
                CONTROL_PROFILE_MARKER,
                DIRECT_CONTROL_PROFILE,
            )
        else:
            self.policy_io = make_policy_io(control_profile=control_profile)
            self.control_profile = control_profile
        _validate_control_profile(self.control_profile)
        self.reward_profile = reward_profile

        self.model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
        self.data = mujoco.MjData(self.model)

        self.success_threshold = success_threshold
        control_dt = self.model.opt.timestep * self.frame_skip
        self.hold_steps_required = round(hold_seconds / control_dt)

        n_joints = 2
        self.observation_space = gym.spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(OBSERVATION_SIZE,),
            dtype=np.float32,
        )
        self.action_space = gym.spaces.Box(
            low=-1.0, high=1.0, shape=(n_joints,), dtype=np.float32
        )

        self._step_count = 0
        self._previous_distance = 0.0
        self._held_steps = 0
        self._outside_after_hold = False

    def _end_effector_position(self) -> np.ndarray:
        return self.data.site("end_effector").xpos.copy()

    def _distance_to_target(self) -> float:
        return float(
            np.linalg.norm(self._end_effector_position() - self.data.mocap_pos[0])
        )

    def _endpoint_linear_velocity(self) -> float:
        jacobian_position = np.zeros((3, self.model.nv), dtype=np.float64)
        jacobian_rotation = np.zeros((3, self.model.nv), dtype=np.float64)
        site_id = mujoco.mj_name2id(
            self.model, mujoco.mjtObj.mjOBJ_SITE, "end_effector"
        )
        mujoco.mj_jacSite(
            self.model,
            self.data,
            jacobian_position,
            jacobian_rotation,
            site_id,
        )
        return float(np.linalg.norm(jacobian_position @ self.data.qvel))

    def _sample_target_position(self) -> None:
        angle = float(self.np_random.uniform(-np.pi, np.pi))
        radius = float(
            self.np_random.uniform(
                self.target_radius_range[0], self.target_radius_range[1]
            )
        )
        # The arm is planar but its plane sits above the world origin. Keep the
        # target in that same plane so the 3-D distance can genuinely reach zero.
        target_z = float(self._end_effector_position()[2])
        self.data.mocap_pos[0] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            target_z,
        ]

    def _observation(self) -> np.ndarray:
        return self.policy_io.observe(self.data)

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[np.ndarray, dict[str, Any]]:
        del options
        super().reset(seed=seed)
        if self.policy_io.reset is not None:
            self.policy_io.reset()
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[:] = 0.0
        self.data.qvel[:] = 0.0
        mujoco.mj_forward(self.model, self.data)
        self._sample_target_position()
        mujoco.mj_forward(self.model, self.data)

        self._step_count = 0
        self._previous_distance = self._distance_to_target()
        self._held_steps = 0
        self._outside_after_hold = False
        return self._observation(), {}

    def step(
        self, action: np.ndarray
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        action = np.clip(
            np.asarray(self.policy_io.action(action), dtype=np.float64),
            self.action_space.low,
            self.action_space.high,
        )
        if self.control_profile == RESIDUAL_TORQUE_PROFILE:
            action = _residual_control_action(
                action,
                np.asarray(self.data.qpos[:2], dtype=np.float64),
                np.asarray(self.data.qvel[:2], dtype=np.float64),
                np.asarray(self.data.mocap_pos[0], dtype=np.float64),
                self.success_threshold,
            )
        self.data.ctrl[:] = action
        for _ in range(self.frame_skip):
            mujoco.mj_step(self.model, self.data)

        distance = self._distance_to_target()

        previous_held_steps = self._held_steps
        if distance <= self.success_threshold:
            self._held_steps += 1
            self._outside_after_hold = False
        else:
            if previous_held_steps > 0:
                self._outside_after_hold = True
            self._held_steps = 0

        reward_kwargs = {}
        if self.reward_profile == TARGETED_REGULATION_PROFILE:
            reward_kwargs = {
                "reward_profile": self.reward_profile,
                "joint_velocity": self.data.qvel[:2].copy(),
                "endpoint_velocity": self._endpoint_linear_velocity(),
            }
        reward = reach_reward(
            self._previous_distance,
            distance,
            self.success_threshold,
            action,
            held_steps=self._held_steps,
            previous_held_steps=previous_held_steps,
            hold_steps_required=self.hold_steps_required,
            penalize_outside=self._outside_after_hold,
            **reward_kwargs,
        )
        self._previous_distance = distance

        self._step_count += 1
        terminated = self._held_steps >= self.hold_steps_required
        truncated = self._step_count >= self.max_episode_steps
        info = {
            "distance": distance,
            "is_success": terminated,
            "held_steps": self._held_steps,
            # Arbitrary scenario-owned attribution; the RL algorithm still only
            # ever sees `reward.total`.
            "reward_components": reward.components,
        }
        return self._observation(), float(reward.total), terminated, truncated, info


def make_evaluation_env(*, policy_runtime=None) -> gym.Env:
    """Build the fixed-distribution environment used by research evaluation."""
    env = TwoJointArmReachEnv(
        target_radius_range=TARGET_RADIUS_RANGE, policy_runtime=policy_runtime
    )
    if policy_runtime is not None:
        env.observation_space = policy_runtime.observation_space
    return env
