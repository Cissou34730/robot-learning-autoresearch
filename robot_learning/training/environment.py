"""Training-only environment construction for the targeted-exposure recipe.

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
TARGETED_ANGLE_SECTORS = (
    (-np.pi, -3.0 * np.pi / 4.0),
    (-3.0 * np.pi / 4.0, -np.pi / 2.0),
    (-np.pi / 4.0, 0.0),
)


class TargetedAngleTrainingEnv(TwoJointArmReachEnv):
    """Scenario environment with the I7 reset-time angle mixture."""

    def _sample_target_position(self) -> None:
        if float(self.np_random.random()) < 0.5:
            sector = TARGETED_ANGLE_SECTORS[
                int(self.np_random.integers(len(TARGETED_ANGLE_SECTORS)))
            ]
            angle = float(self.np_random.uniform(sector[0], sector[1]))
        else:
            angle = float(self.np_random.uniform(-np.pi, np.pi))
        radius = float(
            self.np_random.uniform(
                self.target_radius_range[0], self.target_radius_range[1]
            )
        )
        # The arm is planar but its plane sits above the world origin. Keep the
        # target in that same plane so the 3-D distance can genuinely reach zero.
        target_z = float(self._end_effector_position()[2])
        self.data.mocap_pos[0] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            target_z,
        ]


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return TargetedAngleTrainingEnv(
        target_radius_range=TRAINING_TARGET_RADIUS_RANGE
    )
