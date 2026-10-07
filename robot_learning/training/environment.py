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

TRAINING_TARGET_RADIUS_RANGE = (0.06, 0.20)
OUTER_RADIUS_RANGE = (0.14, 0.20)
OUTER_RADIUS_OVERSAMPLE_PROBABILITY = 0.25
HARD_ANGLE_RANGE = (3.0 * np.pi / 4.0, np.pi)
HARD_ANGLE_OVERSAMPLE_PROBABILITY = 0.10


def sample_training_radius(rng: np.random.Generator) -> float:
    """Retain full support while increasing exposure to timeout-prone targets."""
    if rng.random() < OUTER_RADIUS_OVERSAMPLE_PROBABILITY:
        lower, upper = OUTER_RADIUS_RANGE
    else:
        lower, upper = TRAINING_TARGET_RADIUS_RANGE
    return float(rng.uniform(lower, upper))


def sample_training_angle(rng: np.random.Generator) -> float:
    """Add limited exposure to seam-adjacent angles without abandoning coverage."""
    if rng.random() < HARD_ANGLE_OVERSAMPLE_PROBABILITY:
        lower, upper = HARD_ANGLE_RANGE
        if rng.random() < 0.5:
            lower, upper = -upper, -lower
        return float(rng.uniform(lower, upper))
    return float(rng.uniform(-np.pi, np.pi))


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return TwoJointArmReachEnv(
        target_radius_range=TRAINING_TARGET_RADIUS_RANGE,
        target_radius_sampler=sample_training_radius,
        target_angle_sampler=sample_training_angle,
    )
