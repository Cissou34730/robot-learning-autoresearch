"""Training-only environment construction for the target-coverage recipe.

Only the target distribution the policy trains on lives here. Task mechanics,
success semantics and evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what the
policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

import gymnasium as gym
import numpy as np

from robot_learning.scenario.environment import TwoJointArmReachEnv

TRAINING_TARGET_RADIUS_RANGE = (0.06, 0.20)
SHORT_RADIUS_RANGE = (0.06, 0.12)
LONG_RADIUS_RANGE = (0.12, 0.20)
SHORT_RADIUS_PROBABILITY = 0.75


class ShortRadiusFocusedReachEnv(TwoJointArmReachEnv):
    """Train on all angles while emphasizing the retained policy's hard radii."""

    def _sample_target_position(self) -> None:
        angle = float(self.np_random.uniform(-np.pi, np.pi))
        radius_range = (
            SHORT_RADIUS_RANGE
            if self.np_random.random() < SHORT_RADIUS_PROBABILITY
            else LONG_RADIUS_RANGE
        )
        radius = float(self.np_random.uniform(*radius_range))
        target_z = float(self._end_effector_position()[2])
        self.data.mocap_pos[0] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            target_z,
        ]


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return ShortRadiusFocusedReachEnv(
        target_radius_range=TRAINING_TARGET_RADIUS_RANGE
    )
