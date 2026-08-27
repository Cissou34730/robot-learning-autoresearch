"""Frozen metric calculations shared by evaluation and checkpoint selection."""

import statistics

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


def achieved_goal(distances: list[float], control_dt: float) -> bool:
    required = milestone_steps(HOLD_SECONDS, control_dt)
    return maximum_consecutive_hold_steps(distances) >= required


def summarize_consecutive_hold_steps(values: list[int], required: int) -> dict:
    return {
        "median": float(statistics.median(values)),
        "mean": float(statistics.fmean(values)),
        "required": required,
    }


def evaluation_rank(metrics: dict) -> tuple[float, float, float, float]:
    hold_steps = metrics["consecutive_hold_steps"]
    return (
        float(metrics["success_percent"]),
        float(hold_steps["median"]),
        float(hold_steps["mean"]),
        -float(metrics["closest_distance_cm"]["median"]),
    )
