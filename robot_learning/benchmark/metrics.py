"""Frozen metric calculations shared by evaluation and checkpoint selection."""

from robot_learning.benchmark.spec import CURRICULUM_STAGES


def milestone_steps(hold_seconds: float, control_dt: float) -> int:
    return max(round(hold_seconds / control_dt), 1)


def achieved_milestones(distances: list[float], control_dt: float) -> list[bool]:
    achieved: list[bool] = []
    for threshold, hold_seconds in CURRICULUM_STAGES:
        required = milestone_steps(hold_seconds, control_dt)
        streak = 0
        best_streak = 0
        for distance in distances:
            streak = streak + 1 if distance <= threshold else 0
            best_streak = max(best_streak, streak)
        achieved.append(best_streak >= required)
    return achieved
