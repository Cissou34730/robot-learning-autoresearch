"""Training-only environment construction.

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
TRAINING_TARGET_RADIUS_BANDS = ((0.06, 0.10), (0.10, 0.20))
TRAINING_TARGET_RADIUS_BAND_PROBABILITIES = (0.60, 0.40)
FOCUSED_TARGET_ANGLE_RANGE = (np.deg2rad(-170.0), np.deg2rad(-110.0))
FOCUSED_TARGET_ANGLE_PROBABILITY = 0.25


class FocusedAngleReachEnv(TwoJointArmReachEnv):
    """Training environment with extra coverage of the observed failure sector."""

    def _sample_target_position(self) -> None:
        if self.np_random.random() < FOCUSED_TARGET_ANGLE_PROBABILITY:
            angle = float(self.np_random.uniform(*FOCUSED_TARGET_ANGLE_RANGE))
        else:
            angle = float(self.np_random.uniform(-np.pi, np.pi))

        if self.target_radius_bands is None:
            radius = float(
                self.np_random.uniform(
                    self.target_radius_range[0], self.target_radius_range[1]
                )
            )
        else:
            band_index = int(
                self.np_random.choice(
                    len(self.target_radius_bands),
                    p=self.target_radius_band_probabilities,
                )
            )
            radius = float(
                self.np_random.uniform(*self.target_radius_bands[band_index])
            )

        target_z = float(self._end_effector_position()[2])
        self.data.mocap_pos[0] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            target_z,
        ]


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return FocusedAngleReachEnv(
        target_radius_range=TRAINING_TARGET_RADIUS_RANGE,
        target_radius_bands=TRAINING_TARGET_RADIUS_BANDS,
        target_radius_band_probabilities=TRAINING_TARGET_RADIUS_BAND_PROBABILITIES,
    )
