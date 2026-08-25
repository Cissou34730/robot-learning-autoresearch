import numpy as np

PROGRESS_COEFFICIENT = 10.0
SUCCESS_BONUS = 5.0
ACTION_COST_COEFFICIENT = 0.05


def reach_reward(
    previous_distance: float,
    current_distance: float,
    success_threshold: float,
    action: np.ndarray | None = None,
) -> float:
    reward = PROGRESS_COEFFICIENT * (previous_distance - current_distance)
    if current_distance <= success_threshold:
        reward += SUCCESS_BONUS
    if action is not None:
        reward -= ACTION_COST_COEFFICIENT * float(np.sum(np.square(action)))
    return float(reward)
