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
NEGATIVE_ANGLE_RANGE = (-np.pi, -np.pi / 2.0)
NON_NEGATIVE_ANGLE_RANGE = (-np.pi / 2.0, np.pi)


class AngleBalancedTrainingEnv(TwoJointArmReachEnv):
    """Train equally on the negative-angle sector and its complement."""

    def _sample_target_position(self) -> None:
        if self.np_random.random() < 0.5:
            angle_range = NEGATIVE_ANGLE_RANGE
        else:
            angle_range = NON_NEGATIVE_ANGLE_RANGE
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
    """Build the angle-balanced environment used for this experiment."""
    return AngleBalancedTrainingEnv(target_radius_range=TRAINING_TARGET_RADIUS_RANGE)
