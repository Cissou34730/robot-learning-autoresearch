"""Training-only environment construction for the current recipe.

Only the target distribution the policy trains on lives here. Task mechanics,
success semantics and evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what the
policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

from math import pi, radians

import gymnasium as gym

from robot_learning.scenario.environment import TwoJointArmReachEnv

TRAINING_TARGET_RADIUS_RANGE = (0.06, 0.20)
TRAINING_TARGET_ANGLE_RANGES = (
    (-pi, pi),
    (radians(-160.0), radians(-100.0)),
)
TRAINING_TARGET_ANGLE_WEIGHTS = (0.5, 0.5)


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return TwoJointArmReachEnv(
        target_radius_range=TRAINING_TARGET_RADIUS_RANGE,
        target_angle_ranges=TRAINING_TARGET_ANGLE_RANGES,
        target_angle_weights=TRAINING_TARGET_ANGLE_WEIGHTS,
    )
