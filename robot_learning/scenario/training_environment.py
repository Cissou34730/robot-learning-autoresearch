"""Training-only environment construction for the baseline recipe.

Only the target distribution the policy trains on lives here. Task mechanics,
success semantics and evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what the
policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

import math

import gymnasium as gym
import numpy as np

from robot_learning.scenario.environment import TwoJointArmReachEnv

TRAINING_TARGET_RADIUS_RANGE = (0.14, 0.20)
TRAINING_HARD_ANGLE_RANGE = (math.radians(-160.0), math.radians(-110.0))
TRAINING_HARD_ANGLE_PROBABILITY = 0.35


def sample_training_angle(rng: np.random.Generator) -> float:
    """Oversample the negative-angle sector where the parent fails most often."""
    if rng.random() < TRAINING_HARD_ANGLE_PROBABILITY:
        return float(rng.uniform(*TRAINING_HARD_ANGLE_RANGE))
    return float(rng.uniform(-math.pi, math.pi))


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return TwoJointArmReachEnv(
        target_radius_range=TRAINING_TARGET_RADIUS_RANGE,
        target_angle_sampler=sample_training_angle,
    )
