import numpy as np

from robot_learning.training.research_config import load_experiment_config

_VALUES = load_experiment_config()["reward"]

PROGRESS_COEFFICIENT = _VALUES["PROGRESS_COEFFICIENT"]
CLOSENESS_COEFFICIENT = _VALUES["CLOSENESS_COEFFICIENT"]
CLOSENESS_LENGTH_SCALE = _VALUES["CLOSENESS_LENGTH_SCALE"]
ACTION_COST_COEFFICIENT = _VALUES["ACTION_COST_COEFFICIENT"]
DWELL_BONUS_PER_STEP = _VALUES["DWELL_BONUS_PER_STEP"]
HOLD_COMPLETE_BONUS = _VALUES["HOLD_COMPLETE_BONUS"]

REWARD_PARAMETER_KEYS = frozenset(_VALUES)


def apply_reward_overrides(overrides: dict[str, float]) -> None:
    invalid = set(overrides) - REWARD_PARAMETER_KEYS
    if invalid:
        raise ValueError(f"unknown reward parameters: {sorted(invalid)}")
    for key, value in overrides.items():
        globals()[key] = float(value)


def _closeness_potential(distance: float) -> float:
    return CLOSENESS_COEFFICIENT * float(np.exp(-distance / CLOSENESS_LENGTH_SCALE))


def reach_reward(
    previous_distance: float,
    current_distance: float,
    success_threshold: float,
    action: np.ndarray | None = None,
    held_steps: int = 0,
    hold_steps_required: int = 100,
) -> float:
    reward = PROGRESS_COEFFICIENT * (previous_distance - current_distance)
    reward += _closeness_potential(current_distance) - _closeness_potential(
        previous_distance
    )
    if current_distance <= success_threshold:
        reward += DWELL_BONUS_PER_STEP * held_steps / hold_steps_required
        if held_steps >= hold_steps_required:
            reward += HOLD_COMPLETE_BONUS
    if action is not None:
        reward -= ACTION_COST_COEFFICIENT * float(np.sum(np.square(action)))
    return float(reward)
