"""Training-only environment construction for the baseline recipe.

Only the target distribution the policy trains on lives here. Task mechanics,
success semantics and evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what the
policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

import gymnasium as gym
import numpy as np

from contracts.task_spec import TARGET_RADIUS_RANGE
from robot_learning.scenario.environment import TwoJointArmReachEnv

TRAINING_TARGET_RADIUS_RANGE = TARGET_RADIUS_RANGE
TRAINING_TARGET_RADIUS_SPLIT = 0.14
TRAINING_TARGET_RADIUS_MIX_PROBABILITY = 0.5
BRANCH_GUIDANCE_COEFFICIENT = 0.5


class CoverageBalancedReachEnv(TwoJointArmReachEnv):
    """Train complementary branches for the inner and outer target ranges."""

    def _preferred_branch_potential(self, observation: np.ndarray) -> float:
        target_radius = float(np.hypot(*self.data.mocap_pos[0][:2]))
        residual_slice = (
            slice(7, 9)
            if target_radius < TRAINING_TARGET_RADIUS_SPLIT
            else slice(9, 11)
        )
        return -float(np.linalg.norm(observation[residual_slice]))

    def _sample_target_position(self) -> None:
        angle = float(self.np_random.uniform(-np.pi, np.pi))
        if self.np_random.random() < TRAINING_TARGET_RADIUS_MIX_PROBABILITY:
            radius_range = (
                TRAINING_TARGET_RADIUS_RANGE[0],
                TRAINING_TARGET_RADIUS_SPLIT,
            )
        else:
            radius_range = (
                TRAINING_TARGET_RADIUS_SPLIT,
                TRAINING_TARGET_RADIUS_RANGE[1],
            )
        radius = float(self.np_random.uniform(*radius_range))
        target_z = float(self._end_effector_position()[2])
        self.data.mocap_pos[0] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            target_z,
        ]

    def reset(self, *args, **kwargs):
        observation, info = super().reset(*args, **kwargs)
        self._previous_branch_potential = self._preferred_branch_potential(observation)
        return observation, info

    def step(self, action):
        observation, reward, terminated, truncated, info = super().step(action)
        branch_potential = self._preferred_branch_potential(observation)
        branch_guidance = BRANCH_GUIDANCE_COEFFICIENT * (
            branch_potential - self._previous_branch_potential
        )
        self._previous_branch_potential = branch_potential
        info["reward_components"]["branch_guidance"] = float(branch_guidance)
        return (
            observation,
            float(reward + branch_guidance),
            terminated,
            truncated,
            info,
        )


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return CoverageBalancedReachEnv(target_radius_range=TRAINING_TARGET_RADIUS_RANGE)
