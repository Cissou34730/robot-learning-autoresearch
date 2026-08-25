PROGRESS_COEFFICIENT = 10.0
SUCCESS_BONUS = 25.0


def reach_reward(
    previous_distance: float,
    current_distance: float,
    success_threshold: float,
) -> float:
    reward = PROGRESS_COEFFICIENT * (previous_distance - current_distance)
    if current_distance <= success_threshold:
        reward += SUCCESS_BONUS
    return float(reward)
