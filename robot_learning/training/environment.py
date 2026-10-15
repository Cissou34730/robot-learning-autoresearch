"""Training-only environment construction for the baseline recipe.

Only the target distribution the policy trains on lives here. Task mechanics,
success semantics and evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what the
policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

import math

import gymnasium as gym

from contracts.task_spec import TARGET_RADIUS_RANGE
from robot_learning.scenario.environment import TwoJointArmReachEnv

TRAINING_TARGET_RADIUS_RANGE = TARGET_RADIUS_RANGE


def training_exposure_metadata() -> dict[str, object]:
    """Return the concrete target exposure used by the training environment."""
    return {
        "radius_range_m": [
            float(TRAINING_TARGET_RADIUS_RANGE[0]),
            float(TRAINING_TARGET_RADIUS_RANGE[1]),
        ],
        "radius_law": "uniform",
        "angle_range_radians": [-math.pi, math.pi],
        "angle_law": "uniform_full_circle",
    }


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return TwoJointArmReachEnv(target_radius_range=TRAINING_TARGET_RADIUS_RANGE)
