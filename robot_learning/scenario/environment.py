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
from robot_learning.scenario.policy_io import make_policy_io
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

        self.model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
        self.data = mujoco.MjData(self.model)
        self._end_effector_site_id = mujoco.mj_name2id(
            self.model, mujoco.mjtObj.mjOBJ_SITE, "end_effector"
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

    def _end_effector_position(self) -> np.ndarray:
        return self.data.site("end_effector").xpos.copy()

    def _distance_to_target(self) -> float:
        return float(
            np.linalg.norm(self._end_effector_position() - self.data.mocap_pos[0])
        )

    def _end_effector_linear_velocity(self) -> np.ndarray:
        object_velocity = np.empty(6, dtype=np.float64)
        mujoco.mj_objectVelocity(
            self.model,
            self.data,
            mujoco.mjtObj.mjOBJ_SITE,
            self._end_effector_site_id,
            object_velocity,
            0,
        )
        # mj_objectVelocity returns (angular, linear) velocity in world
        # coordinates when flg_local=0.
        return object_velocity[3:6].copy()

    @staticmethod
    def _wrap_to_pi(angle: float) -> float:
        return float((angle + np.pi) % (2.0 * np.pi) - np.pi)

    def _ik_branch_diagnostics(self) -> tuple[dict[str, list[float]], str]:
        target_x = float(self.data.mocap_pos[0][0])
        target_y = float(self.data.mocap_pos[0][1])
        cos_elbow = (
            target_x**2 + target_y**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
        ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
        elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))

        def residuals(elbow: float) -> list[float]:
            shoulder = float(
                np.arctan2(target_y, target_x)
                - np.arctan2(
                    FOREARM_LENGTH * np.sin(elbow),
                    UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
                )
            )
            return [
                self._wrap_to_pi(shoulder - float(self.data.qpos[0])),
                self._wrap_to_pi(elbow - float(self.data.qpos[1])),
            ]

        residual_by_branch = {
            "open": residuals(elbow_open),
            "folded": residuals(-elbow_open),
        }
        branch_norms = {
            branch: float(np.linalg.norm(residual))
            for branch, residual in residual_by_branch.items()
        }
        selected_branch = min(branch_norms, key=branch_norms.get)
        return residual_by_branch, selected_branch

    def _control_boundary_diagnostics(
        self, action: np.ndarray, mapped_action: np.ndarray
    ) -> dict[str, Any]:
        residuals, selected_branch = self._ik_branch_diagnostics()
        residual_norms = {
            branch: float(np.linalg.norm(branch_residuals))
            for branch, branch_residuals in residuals.items()
        }
        joint_limit_margin = float(
            np.min(
                np.minimum(
                    self.data.qpos[:2] - self.model.jnt_range[:2, 0],
                    self.model.jnt_range[:2, 1] - self.data.qpos[:2],
                )
            )
        )
        action_saturated_per_joint = np.logical_or(
            action <= self.action_space.low, action >= self.action_space.high
        )
        action_clipped_per_joint = np.not_equal(mapped_action, action)
        return {
            "actual_action": [float(value) for value in action],
            "action_saturated_per_joint": [
                bool(value) for value in action_saturated_per_joint
            ],
            "action_saturated": bool(np.any(action_saturated_per_joint)),
            "action_clipped_per_joint": [
                bool(value) for value in action_clipped_per_joint
            ],
            "action_clipped": bool(np.any(action_clipped_per_joint)),
            "joint_velocity_rad_per_s": [
                float(value) for value in self.data.qvel[:2]
            ],
            "end_effector_position_m": [
                float(value) for value in self._end_effector_position()
            ],
            "end_effector_linear_velocity_m_per_s": [
                float(value) for value in self._end_effector_linear_velocity()
            ],
            "ik_branch_residuals_rad": {
                branch: [float(value) for value in branch_residuals]
                for branch, branch_residuals in residuals.items()
            },
            "ik_branch_residual_norms_rad": residual_norms,
            "selected_ik_branch": selected_branch,
            "joint_limit_margin_rad": joint_limit_margin,
        }

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
        mapped_action = np.asarray(self.policy_io.action(action), dtype=np.float64)
        action = np.clip(
            mapped_action,
            self.action_space.low,
            self.action_space.high,
        )
        self.data.ctrl[:] = action
        substep_distance_m: list[float] = []
        substep_endpoint_linear_speed_m_per_s: list[float] = []
        for _ in range(self.frame_skip):
            mujoco.mj_step(self.model, self.data)
            substep_distance_m.append(self._distance_to_target())
            substep_endpoint_linear_speed_m_per_s.append(
                float(np.linalg.norm(self._end_effector_linear_velocity()))
            )

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
        )
        self._previous_distance = distance

        self._step_count += 1
        terminated = self._held_steps >= self.hold_steps_required
        truncated = self._step_count >= self.max_episode_steps
        diagnostics = self._control_boundary_diagnostics(action, mapped_action)
        info = {
            "distance": distance,
            "is_success": terminated,
            "held_steps": self._held_steps,
            # Measurement-only diagnostics sampled after each physics substep;
            # these do not participate in policy observations or task semantics.
            "substep_distance_m": substep_distance_m,
            "substep_endpoint_linear_speed_m_per_s": (
                substep_endpoint_linear_speed_m_per_s
            ),
            # Arbitrary scenario-owned attribution; the RL algorithm still only
            # ever sees `reward.total`.
            "reward_components": reward.components,
            **diagnostics,
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
