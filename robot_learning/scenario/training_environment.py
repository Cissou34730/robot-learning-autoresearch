"""Training-only environment construction for the acquisition intervention.

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
HARD_BEARING_RANGE = (-5.0 * np.pi / 6.0, -2.0 * np.pi / 3.0)
NEGATIVE_BEARING_RANGE = (-np.pi, 0.0)
SINGULARITY_ESCAPE_REWARD_COEFFICIENT = 1.0


class AcquisitionFocusedReachEnv(TwoJointArmReachEnv):
    """Full-range training with extra exposure to the observed hard sector."""

    def __init__(self) -> None:
        super().__init__(
            target_radius_range=TRAINING_TARGET_RADIUS_RANGE,
            singularity_escape_reward_coefficient=(
                SINGULARITY_ESCAPE_REWARD_COEFFICIENT
            ),
        )

    def _sample_target_position(self) -> None:
        bearing_draw = float(self.np_random.uniform())
        if bearing_draw < 0.30:
            bearing_range = HARD_BEARING_RANGE
        elif bearing_draw < 0.50:
            bearing_range = NEGATIVE_BEARING_RANGE
        else:
            bearing_range = (-np.pi, np.pi)

        angle = float(self.np_random.uniform(*bearing_range))
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
    return AcquisitionFocusedReachEnv()
