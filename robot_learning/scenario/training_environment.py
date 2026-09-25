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
HARD_TARGET_PROBABILITY = 0.20
HARD_TARGET_RADIUS_RANGE = (0.06, 0.14)
HARD_TARGET_ANGLE_MIN = 2.0 * np.pi / 3.0
HARD_TARGET_ANGLE_SIGN = -1.0


class TargetMixtureArmReachEnv(TwoJointArmReachEnv):
    """Keep broad training coverage while revisiting the difficult target band."""

    def _sample_target_position(self) -> None:
        if self.np_random.random() >= HARD_TARGET_PROBABILITY:
            super()._sample_target_position()
            return

        angle = float(
            HARD_TARGET_ANGLE_SIGN
            * self.np_random.uniform(HARD_TARGET_ANGLE_MIN, np.pi)
        )
        radius = float(
            self.np_random.uniform(
                HARD_TARGET_RADIUS_RANGE[0], HARD_TARGET_RADIUS_RANGE[1]
            )
        )
        target_z = float(self._end_effector_position()[2])
        self.data.mocap_pos[0] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            target_z,
        ]


def make_training_env() -> gym.Env:
    """Build the training environment used by the current research recipe."""
    return TargetMixtureArmReachEnv(target_radius_range=TRAINING_TARGET_RADIUS_RANGE)
