"""Training-only environment construction for the current target distribution.

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
FOCUSED_TARGET_ANGLE_RANGE = tuple(np.deg2rad((-160.0, -120.0)))
FOCUSED_TARGET_ANGLE_PROBABILITY = 0.5


class AngleFocusedTrainingEnv(TwoJointArmReachEnv):
    """Keep full coverage while oversampling the recurring difficult sector."""

    def _sample_target_position(self) -> None:
        if self.np_random.uniform() < FOCUSED_TARGET_ANGLE_PROBABILITY:
            angle_range = FOCUSED_TARGET_ANGLE_RANGE
        else:
            angle_range = (-np.pi, np.pi)
        angle = float(self.np_random.uniform(*angle_range))
        radius = float(self.np_random.uniform(*TRAINING_TARGET_RADIUS_RANGE))
        target_z = float(self._end_effector_position()[2])
        self.data.mocap_pos[0] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            target_z,
        ]


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return AngleFocusedTrainingEnv(target_radius_range=TRAINING_TARGET_RADIUS_RANGE)
