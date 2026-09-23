"""Training-only environment construction for the current recipe.

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
INNER_TARGET_RADIUS_RANGE = (0.06, 0.12)
INNER_TARGET_PROBABILITY = 0.65


class InnerFocusedTrainingEnv(TwoJointArmReachEnv):
    """Sample the difficult inner-radius targets more often during training."""

    def _sample_target_position(self) -> None:
        angle = float(self.np_random.uniform(-np.pi, np.pi))
        radius_range = (
            INNER_TARGET_RADIUS_RANGE
            if self.np_random.random() < INNER_TARGET_PROBABILITY
            else (INNER_TARGET_RADIUS_RANGE[1], TRAINING_TARGET_RADIUS_RANGE[1])
        )
        radius = float(self.np_random.uniform(*radius_range))
        target_z = float(self._end_effector_position()[2])
        self.data.mocap_pos[0] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            target_z,
        ]


def make_training_env() -> gym.Env:
    """Build the inner-focused environment used for training this scenario."""
    return InnerFocusedTrainingEnv(target_radius_range=TRAINING_TARGET_RADIUS_RANGE)
