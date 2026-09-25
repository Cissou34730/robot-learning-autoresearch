"""Training-only environment construction for the active recipe.

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
HARD_TARGET_RADIUS_RANGE = (0.06, 0.14)
HARD_TARGET_ANGLE_RANGE = tuple(np.deg2rad((-155.0, -120.0)))
HARD_TARGET_PROBABILITY = 0.4


class TargetedTrainingReachEnv(TwoJointArmReachEnv):
    """Training environment with extra coverage of the observed hard sector."""

    def _sample_target_position(self) -> None:
        hard_target = self.np_random.random() < HARD_TARGET_PROBABILITY
        if hard_target:
            angle = float(self.np_random.uniform(*HARD_TARGET_ANGLE_RANGE))
            radius = float(self.np_random.uniform(*HARD_TARGET_RADIUS_RANGE))
        else:
            angle = float(self.np_random.uniform(-np.pi, np.pi))
            radius = float(self.np_random.uniform(*TRAINING_TARGET_RADIUS_RANGE))

        target_z = float(self._end_effector_position()[2])
        self.data.mocap_pos[0] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            target_z,
        ]


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return TargetedTrainingReachEnv(target_radius_range=TRAINING_TARGET_RADIUS_RANGE)
