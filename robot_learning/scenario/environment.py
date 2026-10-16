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
from robot_learning.scenario.branch_aware_control import BranchAwareController
from robot_learning.scenario.observations import OBSERVATION_SIZE
from robot_learning.scenario.policy_io import (
    is_branch_aware_policy_io,
    make_policy_io,
)
from robot_learning.training.reward import reach_reward


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
        self.branch_aware_active = is_branch_aware_policy_io(self.policy_io)

        self.model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
        self.data = mujoco.MjData(self.model)
        self.success_threshold = success_threshold
        self._branch_controller = (
            BranchAwareController(
                self.model, success_threshold=self.success_threshold
            )
            if self.branch_aware_active
            else None
        )
        # Keep diagnostic kinematics separate from the live data.  MuJoCo's
        # integration step leaves derived site positions at the pre-integration
        # state; forwarding this copy lets research traces describe the actual
        # post-block qpos without changing the established task state path.
        self._diagnostic_data = mujoco.MjData(self.model)

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
        self._diagnostic_held_steps = 0
        self._max_contact_count = 0
        self._contact_geom_pairs: set[tuple[str, str]] = set()

    def _end_effector_position(self) -> np.ndarray:
        return self.data.site("end_effector").xpos.copy()

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

    def _joint_limit_distances(self) -> dict[str, float]:
        distances: dict[str, float] = {}
        for joint_id in range(self.model.njnt):
            if not self.model.jnt_limited[joint_id]:
                continue
            qpos_address = int(self.model.jnt_qposadr[joint_id])
            position = float(self.data.qpos[qpos_address])
            lower, upper = (
                float(limit) for limit in self.model.jnt_range[joint_id]
            )
            if position < lower:
                distance = position - lower
            elif position > upper:
                distance = upper - position
            else:
                distance = min(position - lower, upper - position)
            distances[str(self.model.joint(joint_id).name)] = float(distance)
        return distances

    def _capture_contacts(self) -> None:
        self._max_contact_count = max(
            self._max_contact_count, int(self.data.ncon)
        )
        for contact_index in range(int(self.data.ncon)):
            contact = self.data.contact[contact_index]
            geom_names = (
                str(self.model.geom(int(contact.geom1)).name),
                str(self.model.geom(int(contact.geom2)).name),
            )
            self._contact_geom_pairs.add(geom_names)

    def _diagnostic_distance(self) -> float:
        self._diagnostic_data.qpos[:] = self.data.qpos
        self._diagnostic_data.qvel[:] = self.data.qvel
        self._diagnostic_data.mocap_pos[:] = self.data.mocap_pos
        mujoco.mj_forward(self.model, self._diagnostic_data)
        return float(
            np.linalg.norm(
                self._diagnostic_data.site("end_effector").xpos
                - self._diagnostic_data.mocap_pos[0]
            )
        )

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
        if self._branch_controller is not None:
            self._branch_controller.select_branch(self.data)

        self._step_count = 0
        self._previous_distance = self._distance_to_target()
        self._held_steps = 0
        self._outside_after_hold = False
        self._diagnostic_held_steps = 0
        self._max_contact_count = 0
        self._contact_geom_pairs = set()
        return self._observation(), {}

    def step(
        self, action: np.ndarray
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        policy_action = np.clip(
            np.asarray(self.policy_io.action(action), dtype=np.float64),
            self.action_space.low,
            self.action_space.high,
        )
        if self._branch_controller is None:
            guidance_action = np.zeros_like(policy_action)
            applied_action = policy_action
            controller_diagnostics = {
                "control_phase": None,
                "braking_active": False,
                "braking_phase": False,
                "guidance_weight": 0.0,
                "residual_weight": 1.0,
                # These quantities are defined relative to the latched
                # branch controller and are unavailable for direct policies.
                "joint_error_norm_rad": None,
                "joint_speed_norm_rad_s": None,
                "inward_joint_speed_rad_s": None,
                "target_distance_m": None,
            }
        else:
            guidance_action, applied_action = self._branch_controller.apply(
                policy_action, self.data
            )
        action = applied_action
        self.data.ctrl[:] = action
        self._max_contact_count = 0
        self._contact_geom_pairs = set()
        for _ in range(self.frame_skip):
            mujoco.mj_step(self.model, self.data)
            self._capture_contacts()

        diagnostic_distance = self._diagnostic_distance()
        if diagnostic_distance <= self.success_threshold:
            self._diagnostic_held_steps += 1
        else:
            self._diagnostic_held_steps = 0

        distance = self._distance_to_target()
        if self._branch_controller is not None:
            controller_diagnostics = self._branch_controller.diagnostics(self.data)

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
        )
        self._previous_distance = distance

        self._step_count += 1
        terminated = self._held_steps >= self.hold_steps_required
        truncated = self._step_count >= self.max_episode_steps
        info = {
            "distance": distance,
            "is_success": terminated,
            "held_steps": self._held_steps,
            # These fields are diagnostic-only.  The established task fields
            # above intentionally retain their existing success semantics.
            "diagnostic_distance": diagnostic_distance,
            "diagnostic_held_steps": self._diagnostic_held_steps,
            "policy_action": [float(value) for value in policy_action],
            "guidance_action": [float(value) for value in guidance_action],
            "applied_action": [float(value) for value in applied_action],
            "branch_aware_activation": bool(self.branch_aware_active),
            **controller_diagnostics,
            "selected_branch": (
                None
                if self._branch_controller is None
                else self._branch_controller.selected_branch
            ),
            "selected_ik_target": (
                None
                if self._branch_controller is None
                else [
                    float(value)
                    for value in self._branch_controller.selected_target
                ]
            ),
            "action": [float(value) for value in action],
            "qpos": [float(value) for value in self.data.qpos],
            "qvel": [float(value) for value in self.data.qvel],
            "joint_limit_distance_rad": self._joint_limit_distances(),
            "max_contact_count": self._max_contact_count,
            "contact_geom_pairs": [
                list(pair) for pair in sorted(self._contact_geom_pairs)
            ],
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
