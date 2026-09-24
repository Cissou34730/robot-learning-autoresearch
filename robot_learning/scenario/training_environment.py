"""Training-only environment construction for the baseline recipe.

Only the target distribution the policy trains on lives here. Task mechanics,
success semantics and evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what the
policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

import gymnasium as gym
import numpy as np

from robot_learning.scenario.environment import TwoJointArmReachEnv

TRAINING_TARGET_RADIUS_RANGE = (0.14, 0.20)
HARD_TARGET_ANGLE_RANGE = (np.deg2rad(-180.0), np.deg2rad(-90.0))
HARD_TARGET_ANGLE_PROBABILITY = 0.5


class AngleBalancedReachEnv(TwoJointArmReachEnv):
    """Train with extra coverage of the repeatedly failing angle sector."""

    def _sample_target_position(self) -> None:
        if self.np_random.random() < HARD_TARGET_ANGLE_PROBABILITY:
            angle_range = HARD_TARGET_ANGLE_RANGE
        else:
            angle_range = (-np.pi, np.pi)
        angle = float(self.np_random.uniform(*angle_range))
        radius = float(
            self.np_random.uniform(
                self.target_radius_range[0], self.target_radius_range[1]
            )
        )
        target_z = float(self._end_effector_position()[2])
        self.data.mocap_pos[0] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            target_z,
        ]


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return AngleBalancedReachEnv(target_radius_range=TRAINING_TARGET_RADIUS_RANGE)
