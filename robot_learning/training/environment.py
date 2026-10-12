"""Training-only environment construction for the full-radius recipe.

Only the target distribution the policy trains on lives here. Task mechanics,
success semantics and evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what the
policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

from typing import Any

import gymnasium as gym
import mujoco
import numpy as np

from robot_learning.scenario.environment import (
    TwoJointArmReachEnv,
    _residual_control_action,
)
from robot_learning.scenario.policy_io import (
    DIRECT_CONTROL_PROFILE,
    RESIDUAL_TORQUE_PROFILE,
)
from robot_learning.training.reward import (
    DIRECT_LIMIT_VELOCITY_PROFILE,
    reach_reward,
)

TRAINING_TARGET_RADIUS_RANGE = (0.06, 0.20)


class DirectLimitVelocityTrainingEnv(TwoJointArmReachEnv):
    """Full-radius direct-control route with live regulation inputs."""

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

        reward = reach_reward(
            self._previous_distance,
            distance,
            self.success_threshold,
            action,
            held_steps=self._held_steps,
            previous_held_steps=previous_held_steps,
            hold_steps_required=self.hold_steps_required,
            penalize_outside=self._outside_after_hold,
            reward_profile=self.reward_profile,
            joint_velocity=self.data.qvel[:2].copy(),
            endpoint_velocity=self._endpoint_linear_velocity(),
            joint_position=self.data.qpos[:2].copy(),
            joint_ranges=self.model.jnt_range[:2].copy(),
        )
        self._previous_distance = distance

        self._step_count += 1
        terminated = self._held_steps >= self.hold_steps_required
        truncated = self._step_count >= self.max_episode_steps
        info = {
            "distance": distance,
            "is_success": terminated,
            "held_steps": self._held_steps,
            "reward_components": reward.components,
        }
        return self._observation(), float(reward.total), terminated, truncated, info


# Preserve the previous import name while the factory selects the new route.
HoldRecoveryTrainingEnv = DirectLimitVelocityTrainingEnv


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return DirectLimitVelocityTrainingEnv(
        target_radius_range=TRAINING_TARGET_RADIUS_RANGE,
        reward_profile=DIRECT_LIMIT_VELOCITY_PROFILE,
        control_profile=DIRECT_CONTROL_PROFILE,
    )
