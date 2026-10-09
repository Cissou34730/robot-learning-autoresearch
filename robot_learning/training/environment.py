"""Training-only environment construction for the active coverage intervention.

Only the target distribution the policy trains on lives here. Task mechanics,
success semantics and evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what the
policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

import gymnasium as gym

from robot_learning.scenario.environment import TwoJointArmReachEnv

TRAINING_TARGET_RADIUS_RANGE = (0.06, 0.20)
TRAINING_INNER_RADIUS_RANGE = (0.06, 0.14)
TRAINING_OUTER_RADIUS_RANGE = (0.14, 0.20)
TRAINING_INNER_RADIUS_PROBABILITY = 0.5


def sample_training_target_radius(rng) -> float:
    if rng.uniform() < TRAINING_INNER_RADIUS_PROBABILITY:
        lower, upper = TRAINING_INNER_RADIUS_RANGE
    else:
        lower, upper = TRAINING_OUTER_RADIUS_RANGE
    return float(rng.uniform(lower, upper))


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return TwoJointArmReachEnv(
        target_radius_range=TRAINING_TARGET_RADIUS_RANGE,
        target_radius_sampler=sample_training_target_radius,
        branch_guidance=True,
    )
