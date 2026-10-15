"""Training-only environment construction for the full official radius range.

The policy trains on the full official target-radius range of 0.06-0.20 m.
Only that target distribution lives here. Task mechanics, success semantics and
evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what the
policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

import gymnasium as gym

from robot_learning.scenario.environment import TwoJointArmReachEnv

TRAINING_TARGET_RADIUS_RANGE = (0.06, 0.20)


def make_training_env() -> gym.Env:
    """Build the training environment covering the full official radius range."""
    return TwoJointArmReachEnv(target_radius_range=TRAINING_TARGET_RADIUS_RANGE)
