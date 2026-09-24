"""Training-only environment construction for the baseline recipe.

Only the target distribution the policy trains on lives here. Task mechanics,
success semantics and evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what the
policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

import gymnasium as gym

from robot_learning.scenario.environment import TwoJointArmReachEnv

TRAINING_TARGET_RADIUS_RANGE = (0.14, 0.20)
TRAINING_TARGET_ANGLE_FOCUS = (-2.8, -2.0)
TRAINING_TARGET_ANGLE_FOCUS_PROBABILITY = 0.5


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return TwoJointArmReachEnv(
        target_radius_range=TRAINING_TARGET_RADIUS_RANGE,
        target_angle_focus=TRAINING_TARGET_ANGLE_FOCUS,
        target_angle_focus_probability=TRAINING_TARGET_ANGLE_FOCUS_PROBABILITY,
    )
