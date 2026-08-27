"""Frozen metric calculations shared by evaluation and checkpoint selection."""

from robot_learning.benchmark.spec import HOLD_SECONDS, SUCCESS_THRESHOLD


def milestone_steps(hold_seconds: float, control_dt: float) -> int:
    return max(round(hold_seconds / control_dt), 1)


def achieved_goal(distances: list[float], control_dt: float) -> bool:
    required = milestone_steps(HOLD_SECONDS, control_dt)
    streak = 0
    for distance in distances:
        streak = streak + 1 if distance <= SUCCESS_THRESHOLD else 0
        if streak >= required:
            return True
    return False
