"""Training-only environment construction for endpoint-velocity observation."""

import gymnasium as gym

from robot_learning.scenario.environment import TwoJointArmReachEnv

TRAINING_TARGET_RADIUS_RANGE = (0.14, 0.20)


def make_training_env() -> gym.Env:
    """Build the baseline-recipe environment with the augmented observation."""
    return TwoJointArmReachEnv(target_radius_range=TRAINING_TARGET_RADIUS_RANGE)
