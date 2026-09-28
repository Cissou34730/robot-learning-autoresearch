"""Training-only environment construction for targeted posture adaptation.

Only the target distribution the policy trains on lives here. Task mechanics,
success semantics and evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what the
policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

import gymnasium as gym
import numpy as np

from robot_learning.scenario.environment import TwoJointArmReachEnv

BASELINE_TARGET_RADIUS_RANGE = (0.14, 0.20)
HARD_TARGET_RADIUS_RANGE = (0.06, 0.20)
HARD_TARGET_ANGLE_RANGE = (np.deg2rad(-155.0), np.deg2rad(-105.0))
HARD_TARGET_PROBABILITY = 0.2


class PostureAdaptationEnv(TwoJointArmReachEnv):
    """Preserve T1's task distribution while oversampling diagnosed failures."""

    def _sample_target_position(self) -> None:
        if float(self.np_random.random()) >= HARD_TARGET_PROBABILITY:
            super()._sample_target_position()
            return

        angle = float(self.np_random.uniform(*HARD_TARGET_ANGLE_RANGE))
        radius = float(self.np_random.uniform(*HARD_TARGET_RADIUS_RANGE))
        target_z = float(self._end_effector_position()[2])
        self.data.mocap_pos[0] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            target_z,
        ]


def make_training_env() -> gym.Env:
    """Build the T1-preserving training environment."""
    return PostureAdaptationEnv(target_radius_range=BASELINE_TARGET_RADIUS_RANGE)
