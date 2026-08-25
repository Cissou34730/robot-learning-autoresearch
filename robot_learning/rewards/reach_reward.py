import numpy as np

PROGRESS_COEFFICIENT = 10.0
CLOSENESS_COEFFICIENT = 4.0
CLOSENESS_LENGTH_SCALE = 0.05
ACTION_COST_COEFFICIENT = 0.05
DWELL_BONUS_PER_STEP = 0.5
HOLD_COMPLETE_BONUS = 50.0


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
