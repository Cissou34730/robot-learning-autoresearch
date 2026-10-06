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


class CoverageBalancedReachEnv(TwoJointArmReachEnv):
    """Preserve the official annulus while giving its hard outer half equal mass."""

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


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return CoverageBalancedReachEnv(target_radius_range=TRAINING_TARGET_RADIUS_RANGE)
