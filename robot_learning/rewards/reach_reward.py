import numpy as np

from robot_learning.training.research_config import load_experiment_config

_VALUES = load_experiment_config()["reward"]

PROGRESS_COEFFICIENT = _VALUES["PROGRESS_COEFFICIENT"]
CLOSENESS_COEFFICIENT = _VALUES["CLOSENESS_COEFFICIENT"]
CLOSENESS_LENGTH_SCALE = _VALUES["CLOSENESS_LENGTH_SCALE"]
ACTION_COST_COEFFICIENT = _VALUES["ACTION_COST_COEFFICIENT"]
HOLD_PROGRESS_BONUS = _VALUES["HOLD_PROGRESS_BONUS"]
HOLD_PROGRESS_EXPONENT = _VALUES["HOLD_PROGRESS_EXPONENT"]
HOLD_EXIT_FORFEIT_FRACTION = _VALUES["HOLD_EXIT_FORFEIT_FRACTION"]
OUTSIDE_BAND_WIDTH = _VALUES["OUTSIDE_BAND_WIDTH"]
OUTSIDE_BAND_PENALTY = _VALUES["OUTSIDE_BAND_PENALTY"]
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


def _hold_progress_potential(held_steps: int, hold_steps_required: int) -> float:
    if hold_steps_required <= 0:
        raise ValueError("hold_steps_required must be positive")
    progress = np.clip(held_steps / hold_steps_required, 0.0, 1.0)
    return HOLD_PROGRESS_BONUS * float(progress**HOLD_PROGRESS_EXPONENT)


def reach_reward(
    previous_distance: float,
    current_distance: float,
    success_threshold: float,
    action: np.ndarray | None = None,
    held_steps: int = 0,
    previous_held_steps: int = 0,
    hold_steps_required: int = 100,
    penalize_outside: bool = False,
) -> float:
    reward = PROGRESS_COEFFICIENT * (previous_distance - current_distance)
    reward += _closeness_potential(current_distance) - _closeness_potential(
        previous_distance
    )
    current_hold_capital = _hold_progress_potential(held_steps, hold_steps_required)
    previous_hold_capital = _hold_progress_potential(
        previous_held_steps, hold_steps_required
    )
    if held_steps == 0 and previous_held_steps > 0:
        if not 0 <= HOLD_EXIT_FORFEIT_FRACTION <= 1:
            raise ValueError("HOLD_EXIT_FORFEIT_FRACTION must be between 0 and 1")
        reward -= HOLD_EXIT_FORFEIT_FRACTION * previous_hold_capital
    else:
        reward += current_hold_capital - previous_hold_capital

    if penalize_outside and current_distance > success_threshold:
        if OUTSIDE_BAND_WIDTH <= 0:
            raise ValueError("OUTSIDE_BAND_WIDTH must be positive")
        outside_fraction = min(
            (current_distance - success_threshold) / OUTSIDE_BAND_WIDTH,
            1.0,
        )
        reward -= OUTSIDE_BAND_PENALTY * outside_fraction

    if (
        held_steps >= hold_steps_required
        and previous_held_steps < hold_steps_required
    ):
        reward += HOLD_COMPLETE_BONUS
    if action is not None:
        reward -= ACTION_COST_COEFFICIENT * float(np.sum(np.square(action)))
    return float(reward)
