"""Single source of truth for experiment parameters.

All tunable parameters live in `research/current_params.json`. Nothing else in
the codebase may define parameter defaults: this module loads and validates the
file, and every consumer (training, evaluation, runner) reads it through here.

Machine-enforced boundaries live in IMMUTABLE_INVARIANTS and
assert_immutable_invariants(): these properties define the task and may never
be modified by experiments.
"""

import copy
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "research" / "current_params.json"

def validate_param_overrides(overrides: dict) -> None:
    if not isinstance(overrides, dict):
        raise TypeError("experiment parameters must be a JSON object")


def merge_param_overrides(current: dict, overrides: dict) -> dict:
    effective = copy.deepcopy(current)
    for section, values in overrides.items():
        if isinstance(effective.get(section), dict) and isinstance(values, dict):
            effective[section] = merge_param_overrides(effective[section], values)
        else:
            effective[section] = copy.deepcopy(values)
    return effective


def load_experiment_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"{CONFIG_PATH} is missing - it is the single source of truth for "
            "experiment parameters and must exist."
        )
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    validate_param_overrides(config)
    return config


def write_experiment_config(config: dict) -> None:
    validate_param_overrides(config)
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")


def assert_immutable_invariants(env) -> None:
    from robot_learning.benchmark.spec import (
        FRAME_SKIP,
        HOLD_SECONDS,
        MAX_EPISODE_STEPS,
        SUCCESS_THRESHOLD,
        TARGET_RADIUS_RANGE,
    )

    control_dt = env.model.opt.timestep * env.frame_skip
    assert env.success_threshold == SUCCESS_THRESHOLD
    assert env.hold_steps_required == round(HOLD_SECONDS / control_dt)
    assert env.target_radius_range == TARGET_RADIUS_RANGE
    assert env.max_episode_steps == MAX_EPISODE_STEPS
    assert env.frame_skip == FRAME_SKIP
