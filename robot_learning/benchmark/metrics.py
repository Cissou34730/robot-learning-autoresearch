"""Frozen task metrics shared by evaluation and checkpoint selection."""

from robot_learning.benchmark.spec import HOLD_SECONDS, SUCCESS_THRESHOLD


def milestone_steps(hold_seconds: float, control_dt: float) -> int:
    return max(round(hold_seconds / control_dt), 1)


def maximum_consecutive_hold_steps(distances: list[float]) -> int:
    streak = 0
    maximum = 0
    for distance in distances:
        streak = streak + 1 if distance <= SUCCESS_THRESHOLD else 0
        maximum = max(maximum, streak)
    return maximum


def episode_hold_progress(distances: list[float], required: int) -> dict:
    """Measure progress toward one complete hold without rewarding extra centering."""
    if required < 1:
        raise ValueError("required hold steps must be positive")
    if not distances:
        raise ValueError("an episode must contain at least one distance")

    longest = min(maximum_consecutive_hold_steps(distances), required)
    if len(distances) < required:
        windows = [distances]
    else:
        windows = (
            distances[start : start + required]
            for start in range(len(distances) - required + 1)
        )

    best_inside = -1
    best_excess_cm = float("inf")
    for window in windows:
        inside = sum(distance <= SUCCESS_THRESHOLD for distance in window)
        excess_cm = 100 * sum(
            max(distance - SUCCESS_THRESHOLD, 0.0) for distance in window
        )
        if (inside, -excess_cm) > (best_inside, -best_excess_cm):
            best_inside = inside
            best_excess_cm = excess_cm

    return {
        "success": longest >= required,
        "longest_consecutive_steps": longest,
        "best_window_inside_steps": best_inside,
        "best_window_excess_cm": best_excess_cm,
        "required_steps": required,
    }


def achieved_goal(distances: list[float], control_dt: float) -> bool:
    required = milestone_steps(HOLD_SECONDS, control_dt)
    return maximum_consecutive_hold_steps(distances) >= required


def summarize_hold_progress(episodes: list[dict], required: int) -> dict:
    failures = [episode for episode in episodes if not episode["success"]]
    if failures:
        count = len(failures)
        longest = sum(item["longest_consecutive_steps"] for item in failures) / count
        inside = sum(item["best_window_inside_steps"] for item in failures) / count
        excess = sum(item["best_window_excess_cm"] for item in failures) / count
    else:
        count = 0
        longest = float(required)
        inside = float(required)
        excess = 0.0
    return {
        "failed_episodes": count,
        "longest_consecutive_steps_mean": float(longest),
        "best_window_inside_steps_mean": float(inside),
        "best_window_excess_cm_mean": float(excess),
        "required_steps": required,
    }


def evaluation_rank(metrics: dict) -> tuple[float, float, float, float]:
    progress = metrics["failed_episode_progress"]
    return (
        float(metrics["success_percent"]),
        float(progress["longest_consecutive_steps_mean"]),
        float(progress["best_window_inside_steps_mean"]),
        -float(progress["best_window_excess_cm_mean"]),
    )
