"""Training-only environment construction for the conservative hard-region recipe.

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
HARD_TARGET_RADIUS_RANGE = (0.06, 0.12)
HARD_TARGET_ANGLE_RANGE = np.radians((-160.0, -100.0))
HARD_TARGET_PROBABILITY = 0.25


class HardRegionTrainingEnv(TwoJointArmReachEnv):
    """Preserve most baseline coverage while supporting the recurring failure band."""

    def _sample_target_position(self) -> None:
        if self.np_random.random() < HARD_TARGET_PROBABILITY:
            radius_range = HARD_TARGET_RADIUS_RANGE
            angle_range = HARD_TARGET_ANGLE_RANGE
        else:
            radius_range = BASELINE_TARGET_RADIUS_RANGE
            angle_range = (-np.pi, np.pi)

        angle = float(self.np_random.uniform(*angle_range))
        radius = float(self.np_random.uniform(*radius_range))
        target_z = float(self._end_effector_position()[2])
        self.data.mocap_pos[0] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            target_z,
        ]


def make_training_env() -> gym.Env:
    """Build the environment with targeted support for recurring failures."""
    return HardRegionTrainingEnv(target_radius_range=BASELINE_TARGET_RADIUS_RANGE)
