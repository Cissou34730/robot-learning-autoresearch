"""Training-only environment construction for the angle-focused recipe.

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
NEGATIVE_TARGET_ANGLE_PROBABILITY = 0.75


class AngleFocusedTrainingEnv(TwoJointArmReachEnv):
    """Sample negative target angles more often while retaining full coverage."""

    def _sample_target_position(self) -> None:
        if self.np_random.uniform() < NEGATIVE_TARGET_ANGLE_PROBABILITY:
            angle = float(self.np_random.uniform(-np.pi, 0.0))
        else:
            angle = float(self.np_random.uniform(0.0, np.pi))
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
    return AngleFocusedTrainingEnv(target_radius_range=TRAINING_TARGET_RADIUS_RANGE)
