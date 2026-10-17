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

from contracts.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH
from contracts.task_spec import (
    FRAME_SKIP,
    HOLD_SECONDS,
    MAX_EPISODE_STEPS,
    SUCCESS_THRESHOLD,
    TARGET_RADIUS_RANGE,
)
from robot_learning.scenario.observations import OBSERVATION_SIZE
from robot_learning.scenario.policy_io import make_policy_io
from robot_learning.training.reward import reach_reward


ELBOW_SINGULAR_TOLERANCE_RAD = 1e-8
ELBOW_BRANCH_LABELS = ("open", "folded", "singular")


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
    ) -> None:
        super().__init__()
        self.max_episode_steps = max_episode_steps
        self.frame_skip = frame_skip
        self.target_radius_range = target_radius_range
        self.policy_io = policy_runtime.io if policy_runtime else make_policy_io()

        self.model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
        self.data = mujoco.MjData(self.model)
        self._velocity_data = mujoco.MjData(self.model)
        self._end_effector_site_id = int(
            mujoco.mj_name2id(
                self.model, mujoco.mjtObj.mjOBJ_SITE, "end_effector"
            )
        )
        if self._end_effector_site_id < 0:
            raise RuntimeError(
                "The scenario model has no required end_effector site for "
                "endpoint-velocity instrumentation"
            )

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

    def _end_effector_position(self, data=None) -> np.ndarray:
        source_data = self.data if data is None else data
        return source_data.site("end_effector").xpos.copy()

    def _end_effector_velocity(self) -> np.ndarray:
        """Return boundary velocity without changing task-owned derived fields."""
        # mj_step leaves the task's existing derived fields untouched for the
        # distance and observation reads below. Refresh an isolated data copy
        # from the post-integration joint state so the velocity uses current
        # position-dependent kinematics without changing those reads.
        self._velocity_data.qpos[:] = self.data.qpos
        self._velocity_data.qvel[:] = self.data.qvel
        mujoco.mj_forward(self.model, self._velocity_data)
        object_velocity = np.empty(6, dtype=np.float64)
        mujoco.mj_objectVelocity(
            self.model,
            self._velocity_data,
            mujoco.mjtObj.mjOBJ_SITE,
            self._end_effector_site_id,
            object_velocity,
            0,
        )
        velocity = np.asarray(object_velocity[3:6], dtype=np.float64).copy()
        if velocity.shape != (3,) or not np.all(np.isfinite(velocity)):
            raise RuntimeError(
                "MuJoCo did not provide a finite world-frame velocity for "
                "the end_effector site"
            )
        return velocity

    def _elbow_configuration(self) -> tuple[float, str]:
        elbow_qpos = float(self.data.qpos[1])
        if not np.isfinite(elbow_qpos):
            raise RuntimeError(
                "MuJoCo did not provide a finite elbow configuration for "
                "branch attribution"
            )
        if abs(elbow_qpos) <= ELBOW_SINGULAR_TOLERANCE_RAD:
            branch = "singular"
        elif elbow_qpos > 0.0:
            branch = "open"
        else:
            branch = "folded"
        return elbow_qpos, branch

    def _distance_to_target(self) -> float:
        return float(
            np.linalg.norm(self._end_effector_position() - self.data.mocap_pos[0])
        )

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
        elbow_qpos, elbow_branch = self._elbow_configuration()
        return self._observation(), {
            "elbow_qpos_rad": elbow_qpos,
            "elbow_branch": elbow_branch,
        }

    def step(
        self, action: np.ndarray
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        action = np.clip(
            np.asarray(self.policy_io.action(action), dtype=np.float64),
            self.action_space.low,
            self.action_space.high,
        )
        applied_action = action.copy()
        action_saturated = np.logical_or(
            applied_action == self.action_space.low,
            applied_action == self.action_space.high,
        )
        self.data.ctrl[:] = action
        for _ in range(self.frame_skip):
            mujoco.mj_step(self.model, self.data)

        # _end_effector_velocity refreshes the isolated data copy from the
        # post-integration joint state. Read the new position from that same
        # copy so instrumentation is boundary-aligned without changing the
        # task-owned derived fields used below.
        endpoint_velocity = self._end_effector_velocity()
        end_effector_position = self._end_effector_position(self._velocity_data)
        if (
            end_effector_position.shape != (3,)
            or not np.all(np.isfinite(end_effector_position))
        ):
            raise RuntimeError(
                "MuJoCo did not provide a finite world-frame position for "
                "the end_effector site"
            )
        endpoint_distance = float(
            np.linalg.norm(end_effector_position - self.data.mocap_pos[0])
        )
        if not np.isfinite(endpoint_distance):
            raise RuntimeError(
                "MuJoCo did not provide a finite endpoint distance for "
                "the end_effector site"
            )
        endpoint_speed = float(np.linalg.norm(endpoint_velocity))
        elbow_qpos, elbow_branch = self._elbow_configuration()
        distance = self._distance_to_target()

        previous_held_steps = self._held_steps
        if distance <= self.success_threshold:
            self._held_steps += 1
            self._outside_after_hold = False
        else:
            if previous_held_steps > 0:
                self._outside_after_hold = True
            self._held_steps = 0

        reward = reach_reward(
            self._previous_distance,
            distance,
            self.success_threshold,
            action,
            held_steps=self._held_steps,
            previous_held_steps=previous_held_steps,
            hold_steps_required=self.hold_steps_required,
            penalize_outside=self._outside_after_hold,
            endpoint_speed=endpoint_speed,
            endpoint_distance=endpoint_distance,
        )
        self._previous_distance = distance

        self._step_count += 1
        terminated = self._held_steps >= self.hold_steps_required
        truncated = self._step_count >= self.max_episode_steps
        info = {
            "distance": distance,
            "is_success": terminated,
            "held_steps": self._held_steps,
            # Researcher-owned instrumentation. These values are not policy
            # inputs and do not participate in termination or reward.
            "applied_action": applied_action,
            "action_saturated": action_saturated,
            "end_effector_position_m": end_effector_position,
            "endpoint_velocity_mps": endpoint_velocity,
            "endpoint_speed_mps": endpoint_speed,
            "elbow_qpos_rad": elbow_qpos,
            "elbow_branch": elbow_branch,
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
