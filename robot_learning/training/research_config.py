"""Generic runtime configuration for training and research orchestration.

`research/current_params.json` holds generic runtime knobs only: algorithm
selection, PPO/SAC hyper-parameters, policy architecture and training
orchestration. Scenario science - reward, observations, task mechanics,
evaluation semantics - lives in `robot_learning/scenario/` and is versioned as
ordinary research code through the existing Git code lineage.

The research-evaluation defaults below are generic orchestration settings shared
by the runner and the evaluation CLI. Official benchmark parameters remain owned
by the protected scenario benchmark.
"""

import copy
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "research" / "current_params.json"

RESEARCH_EVALUATION_EPISODES = 200
RESEARCH_EVALUATION_SEED = 1000
RESEARCH_SUCCESS_TARGET_PERCENT = 98.0


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
            f"{CONFIG_PATH} is missing - it is the runtime training configuration "
            "and must exist."
        )
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    validate_param_overrides(config)
    return config


def write_experiment_config(config: dict) -> None:
    validate_param_overrides(config)
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
