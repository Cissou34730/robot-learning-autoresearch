"""Training-only environment construction for the baseline recipe.

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
TRAINING_FOCUSED_ANGLE_RANGE = np.deg2rad((-170.0, -110.0))
TRAINING_FOCUSED_ANGLE_PROBABILITY = 0.5


def _sample_training_angle(rng: np.random.Generator) -> float:
    if rng.random() < TRAINING_FOCUSED_ANGLE_PROBABILITY:
        return float(rng.uniform(*TRAINING_FOCUSED_ANGLE_RANGE))
    return float(rng.uniform(-np.pi, np.pi))


class FocusedAngleTrainingEnv(TwoJointArmReachEnv):
    def _sample_target_position(self) -> None:
        angle = _sample_training_angle(self.np_random)
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
    return FocusedAngleTrainingEnv(
        target_radius_range=TRAINING_TARGET_RADIUS_RANGE,
    )
