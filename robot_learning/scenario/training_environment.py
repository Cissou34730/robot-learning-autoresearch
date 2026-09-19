"""Training-only environment construction for the baseline recipe.

Only the target distribution the policy trains on lives here. Task mechanics,
success semantics and evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what the
policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

import gymnasium as gym
import numpy as np

from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.environment import TwoJointArmReachEnv

TRAINING_TARGET_RADIUS_RANGE = (0.06, 0.20)

# Fraction of training targets drawn from the folded-required sector. The uniform
# official distribution samples that sector at about 5.5%, leaving its deepest
# band (|wrapped open shoulder| 176-180 degrees) only about 2% of training
# targets. The remaining targets are ordinary uniform draws.
FOLDED_TARGET_FRACTION = 0.5
MAX_FOLDED_RESAMPLE_ATTEMPTS = 200
SHOULDER_LIMIT_DEGREES = 170.0


def _wrapped_open_shoulder_degrees(target_x: float, target_y: float) -> float:
    """Open-branch IK shoulder angle for a planar target, wrapped to +/-180 deg."""
    cos_elbow = (
        target_x**2 + target_y**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))
    shoulder_open = float(np.arctan2(target_y, target_x)) - float(
        np.arctan2(
            FOREARM_LENGTH * np.sin(elbow_open),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow_open),
        )
    )
    wrapped = (shoulder_open + np.pi) % (2.0 * np.pi) - np.pi
    return float(np.degrees(wrapped))


class FoldedTargetCurriculumEnv(TwoJointArmReachEnv):
    """Training-only environment that oversamples folded-required targets."""

    def _sample_target_position(self) -> None:
        if self.np_random.random() >= FOLDED_TARGET_FRACTION:
            super()._sample_target_position()
            return
        for _ in range(MAX_FOLDED_RESAMPLE_ATTEMPTS):
            super()._sample_target_position()
            wrapped = _wrapped_open_shoulder_degrees(
                float(self.data.mocap_pos[0][0]), float(self.data.mocap_pos[0][1])
            )
            if abs(wrapped) > SHOULDER_LIMIT_DEGREES:
                return


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return FoldedTargetCurriculumEnv(
        target_radius_range=TRAINING_TARGET_RADIUS_RANGE
    )
