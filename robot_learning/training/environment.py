"""Training-only environment construction for the coverage intervention.

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
ENRICHED_TARGET_ANGLE_RANGE_DEGREES = (-151.0, -119.0)
ENRICHED_TARGET_ANGLE_PROBABILITY = 0.5


class CoverageTrainingEnv(TwoJointArmReachEnv):
    def _sample_target_position(self) -> None:
        if self.np_random.random() < ENRICHED_TARGET_ANGLE_PROBABILITY:
            angle_degrees = float(
                self.np_random.uniform(*ENRICHED_TARGET_ANGLE_RANGE_DEGREES)
            )
            angle = float(np.deg2rad(angle_degrees))
        else:
            angle = float(self.np_random.uniform(-np.pi, np.pi))
        radius = float(
            self.np_random.uniform(
                TRAINING_TARGET_RADIUS_RANGE[0], TRAINING_TARGET_RADIUS_RANGE[1]
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
    return CoverageTrainingEnv(target_radius_range=TRAINING_TARGET_RADIUS_RANGE)
