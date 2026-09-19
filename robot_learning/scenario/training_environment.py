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

CURRICULUM_ANGLE_RANGE = (np.radians(-165.0), np.radians(-115.0))
CURRICULUM_PROBABILITY = 0.25


class CurriculumTwoJointArmReachEnv(TwoJointArmReachEnv):
    """Training environment that oversamples a target angular band."""

    def _sample_target_position(self) -> None:
        if float(self.np_random.uniform()) < CURRICULUM_PROBABILITY:
            angle = float(self.np_random.uniform(*CURRICULUM_ANGLE_RANGE))
        else:
            angle = float(self.np_random.uniform(-np.pi, np.pi))
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
    return CurriculumTwoJointArmReachEnv(
        target_radius_range=TRAINING_TARGET_RADIUS_RANGE
    )
