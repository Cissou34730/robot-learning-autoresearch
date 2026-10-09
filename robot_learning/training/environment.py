"""Training-only environment construction for incremental transfer training.

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
OFFICIAL_TARGET_RADIUS_RANGE = (0.06, 0.20)
CURRICULUM_EPISODES = 300


class IncrementalRadiusTrainingEnv(TwoJointArmReachEnv):
    """Broaden inward reach coverage while retaining uniform angle coverage."""

    def __init__(self) -> None:
        super().__init__(target_radius_range=BASELINE_TARGET_RADIUS_RANGE)
        self._episodes_seen = 0

    def _sample_target_position(self) -> None:
        progress = min(self._episodes_seen / CURRICULUM_EPISODES, 1.0)
        minimum_radius = float(
            BASELINE_TARGET_RADIUS_RANGE[0]
            + progress
            * (OFFICIAL_TARGET_RADIUS_RANGE[0] - BASELINE_TARGET_RADIUS_RANGE[0])
        )
        radius = float(
            self.np_random.uniform(minimum_radius, OFFICIAL_TARGET_RADIUS_RANGE[1])
        )
        angle = float(self.np_random.uniform(-np.pi, np.pi))
        target_z = float(self._end_effector_position()[2])
        self.data.mocap_pos[0] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            target_z,
        ]
        self._episodes_seen += 1


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return IncrementalRadiusTrainingEnv()
