"""Training-only environment construction for the full-radius recipe.

Only the target distribution the policy trains on lives here. Task mechanics,
success semantics and evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what the
policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

import gymnasium as gym

from robot_learning.scenario.environment import TwoJointArmReachEnv
from robot_learning.scenario.policy_io import DIRECT_CONTROL_PROFILE
from robot_learning.training.reward import DEFAULT_REWARD_PROFILE

TRAINING_TARGET_RADIUS_RANGE = (0.06, 0.20)


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return TwoJointArmReachEnv(
        target_radius_range=TRAINING_TARGET_RADIUS_RANGE,
        reward_profile=DEFAULT_REWARD_PROFILE,
        control_profile=DIRECT_CONTROL_PROFILE,
    )
