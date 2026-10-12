"""Training-only environment construction for the active recipe.

Only the target distribution the policy trains on lives here. Task mechanics,
success semantics and evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what the
policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

import json
from pathlib import Path

import gymnasium as gym

from contracts.task_spec import TARGET_RADIUS_RANGE
from robot_learning.scenario.environment import TwoJointArmReachEnv
from robot_learning.training.reward import validate_reward_variant

TRAINING_TARGET_RADIUS_RANGE = TARGET_RADIUS_RANGE
CURRENT_PARAMS_PATH = Path(__file__).with_name("current_params.json")


def _configured_training_variant() -> str:
    with CURRENT_PARAMS_PATH.open(encoding="utf-8") as params_file:
        params = json.load(params_file)
    training_variant = params.get("training_variant", "baseline")
    return validate_reward_variant(training_variant)


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return TwoJointArmReachEnv(
        target_radius_range=TRAINING_TARGET_RADIUS_RANGE,
        training_variant=_configured_training_variant(),
    )
