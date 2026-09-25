"""Training-only environment construction for the geometry-focused recipe.

Only the target distribution the policy trains on lives here. Task mechanics,
success semantics and evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what the
policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

import gymnasium as gym
import numpy as np

from robot_learning.scenario.environment import TwoJointArmReachEnv

FULL_TARGET_RADIUS_RANGE = (0.06, 0.20)
INNER_TARGET_RADIUS_RANGE = (0.06, 0.10)
HARD_ANGLE_RANGE = tuple(np.deg2rad((-170.0, -100.0)))


class GeometryMixtureReachEnv(TwoJointArmReachEnv):
    """Expose recurring hard target geometries without changing task mechanics."""

    def _sample_target_position(self) -> None:
        draw = float(self.np_random.random())
        if draw < 0.5:
            angle_range = HARD_ANGLE_RANGE
            radius_range = FULL_TARGET_RADIUS_RANGE
        elif draw < 0.75:
            angle_range = (-np.pi, np.pi)
            radius_range = INNER_TARGET_RADIUS_RANGE
        else:
            angle_range = (-np.pi, np.pi)
            radius_range = FULL_TARGET_RADIUS_RANGE

        angle = float(self.np_random.uniform(*angle_range))
        radius = float(self.np_random.uniform(*radius_range))
        target_z = float(self._end_effector_position()[2])
        self.data.mocap_pos[0] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            target_z,
        ]


def make_training_env() -> gym.Env:
    """Build the geometry-focused Gymnasium environment used for training."""
    return GeometryMixtureReachEnv(target_radius_range=FULL_TARGET_RADIUS_RANGE)
