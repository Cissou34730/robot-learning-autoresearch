"""Training-only environment construction for the baseline recipe.

Only the target distribution the policy trains on lives here. Task mechanics,
success semantics and evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what the
policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

import gymnasium as gym
import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.environment import TwoJointArmReachEnv

TRAINING_TARGET_RADIUS_RANGE = (0.14, 0.20)
FOLDED_ONLY_EXPOSURE_PROBABILITY = 0.5
JOINT_LIMIT_RADIANS = float(np.deg2rad(170.0))


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _folded_only_feasible(radius: float, angle: float) -> bool:
    cosine = (
        radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    elbow_folded = -elbow_open

    def shoulder_for_elbow(elbow: float) -> float:
        return float(
            angle
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )

    open_feasible = abs(_wrap_to_pi(shoulder_for_elbow(elbow_open))) <= (
        JOINT_LIMIT_RADIANS
    )
    folded_feasible = abs(_wrap_to_pi(shoulder_for_elbow(elbow_folded))) <= (
        JOINT_LIMIT_RADIANS
    )
    return folded_feasible and not open_feasible


class FoldedExposureReachEnv(TwoJointArmReachEnv):
    """Keep half of baseline exposure while oversampling folded-only targets."""

    def _sample_target_position(self) -> None:
        if self.np_random.random() < FOLDED_ONLY_EXPOSURE_PROBABILITY:
            while True:
                radius = float(
                    self.np_random.uniform(*self.target_radius_range)
                )
                angle = float(self.np_random.uniform(-np.pi, np.pi))
                if _folded_only_feasible(radius, angle):
                    break
        else:
            angle = float(self.np_random.uniform(-np.pi, np.pi))
            radius = float(self.np_random.uniform(*self.target_radius_range))

        target_z = float(self._end_effector_position()[2])
        self.data.mocap_pos[0] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            target_z,
        ]


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return FoldedExposureReachEnv(target_radius_range=TRAINING_TARGET_RADIUS_RANGE)
