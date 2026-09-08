"""Training-only construction for the scenario environment.

Nothing here affects how a saved policy is replayed or whether an episode is a
success, so editing this module must not invalidate completed measurements.
"""

import gymnasium as gym

from robot_learning.scenario.environment import TwoJointArmReachEnv

TRAINING_TARGET_RADIUS_RANGE = (0.14, 0.20)


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return TwoJointArmReachEnv(target_radius_range=TRAINING_TARGET_RADIUS_RANGE)
