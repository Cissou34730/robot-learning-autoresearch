"""Training-only environment construction for the baseline recipe.

Only the target distribution the policy trains on lives here. Task mechanics,
success semantics and evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what the
policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

import gymnasium as gym
import numpy as np

from robot_learning.benchmark.spec import TARGET_RADIUS_RANGE
from robot_learning.scenario.environment import TwoJointArmReachEnv

TRAINING_TARGET_RADIUS_RANGE = TARGET_RADIUS_RANGE
FOCUSED_ANGLE_RANGE = (np.deg2rad(-150.0), np.deg2rad(-105.0))
FOCUSED_ANGLE_PROBABILITY = 0.5


class CoverageFocusedTrainingEnv(TwoJointArmReachEnv):
    """Train on the official radius range with extra measured-hard targets."""

    def _sample_target_position(self) -> None:
        if self.np_random.random() < FOCUSED_ANGLE_PROBABILITY:
            angle = float(
                self.np_random.uniform(FOCUSED_ANGLE_RANGE[0], FOCUSED_ANGLE_RANGE[1])
            )
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
    return CoverageFocusedTrainingEnv(
        target_radius_range=TRAINING_TARGET_RADIUS_RANGE
    )
