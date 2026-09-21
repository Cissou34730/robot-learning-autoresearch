"""Training-only environment construction for the current research recipe.

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
FOCUSED_ANGLE_RANGE = (np.deg2rad(-160.0), np.deg2rad(-100.0))
FOCUSED_ANGLE_PROBABILITY = 0.5


def sample_training_angle(rng: np.random.Generator) -> float:
    if rng.random() < FOCUSED_ANGLE_PROBABILITY:
        return float(rng.uniform(*FOCUSED_ANGLE_RANGE))
    return float(rng.uniform(-np.pi, np.pi))


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return TwoJointArmReachEnv(
        target_radius_range=TRAINING_TARGET_RADIUS_RANGE,
        target_angle_sampler=sample_training_angle,
    )
