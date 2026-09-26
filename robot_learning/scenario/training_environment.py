"""Training-only environment construction for the current recipe.

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

HARD_ANGLE_RANGE_DEGREES = (-165.0, -115.0)
HARD_ANGLE_PROBABILITY = 0.5


class TargetCoverageTrainingEnv(TwoJointArmReachEnv):
    """Expose the measured failure sector more often during training."""

    def _sample_target_position(self) -> None:
        if self.np_random.uniform() < HARD_ANGLE_PROBABILITY:
            angle = float(
                self.np_random.uniform(
                    np.deg2rad(HARD_ANGLE_RANGE_DEGREES[0]),
                    np.deg2rad(HARD_ANGLE_RANGE_DEGREES[1]),
                )
            )
        else:
            angle = float(self.np_random.uniform(-np.pi, np.pi))
        radius = float(
            self.np_random.uniform(
                TARGET_RADIUS_RANGE[0], TARGET_RADIUS_RANGE[1]
            )
        )
        target_z = float(self._end_effector_position()[2])
        self.data.mocap_pos[0] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            target_z,
        ]


def make_training_env() -> gym.Env:
    """Build the targeted-coverage environment used for training."""
    return TargetCoverageTrainingEnv()
