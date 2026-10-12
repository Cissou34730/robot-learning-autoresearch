"""Scenario-owned reward.

This file is research code, not runner configuration. A future experiment may
replace its terms, coefficients, or mathematical form entirely without touching
generic AutoResearch code; Git code lineage records the exact implementation
that produced every experiment.

`components` is an arbitrary mapping. No generic module may depend on any
particular component name.
"""

from dataclasses import dataclass

import numpy as np

PROGRESS_COEFFICIENT = 10.0
CLOSENESS_COEFFICIENT = 4.0
CLOSENESS_LENGTH_SCALE = 0.05
ACTION_COST_COEFFICIENT = 0.01
HOLD_PROGRESS_BONUS = 50.0
HOLD_PROGRESS_EXPONENT = 1.0
HOLD_EXIT_FORFEIT_FRACTION = 0.0
OUTSIDE_BAND_WIDTH = 0.01
OUTSIDE_BAND_PENALTY = 0.1
HOLD_COMPLETE_BONUS = 50.0
TERMINAL_STABILIZATION_DISTANCE = 0.015
TERMINAL_STABILIZATION_SPEED_THRESHOLD = 1.0
TERMINAL_STABILIZATION_COEFFICIENT = 0.02


@dataclass(frozen=True)
class RewardResult:
    """Scalar reward consumed by the RL algorithm plus free-form attribution."""

    total: float
    components: dict[str, float]


def _closeness_potential(distance: float) -> float:
    return CLOSENESS_COEFFICIENT * float(np.exp(-distance / CLOSENESS_LENGTH_SCALE))


def _hold_progress_potential(held_steps: int, hold_steps_required: int) -> float:
    if hold_steps_required <= 0:
        raise ValueError("hold_steps_required must be positive")
    progress = np.clip(held_steps / hold_steps_required, 0.0, 1.0)
    return HOLD_PROGRESS_BONUS * float(progress**HOLD_PROGRESS_EXPONENT)


def _finite_scalar(value: float, name: str) -> float:
    value_array = np.asarray(value, dtype=np.float64)
    if value_array.shape != ():
        raise ValueError(f"{name} must be scalar")
    value = float(value_array)
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def reach_reward(
    previous_distance: float,
    current_distance: float,
    success_threshold: float,
    action: np.ndarray | None = None,
    held_steps: int = 0,
    previous_held_steps: int = 0,
    hold_steps_required: int = 100,
    penalize_outside: bool = False,
    joint_velocities: np.ndarray | None = None,
) -> RewardResult:
    previous_distance = _finite_scalar(previous_distance, "previous_distance")
    current_distance = _finite_scalar(current_distance, "current_distance")
    success_threshold = _finite_scalar(success_threshold, "success_threshold")
    if action is not None:
        action = np.asarray(action, dtype=np.float64)
        if action.shape != (2,):
            raise ValueError("action must have shape (2,)")
        if not np.all(np.isfinite(action)):
            raise ValueError("action must contain only finite values")

    joint_speed_norm = 0.0
    if joint_velocities is not None:
        joint_velocities = np.asarray(joint_velocities, dtype=np.float64)
        if joint_velocities.shape != (2,):
            raise ValueError("joint_velocities must have shape (2,)")
        if not np.all(np.isfinite(joint_velocities)):
            raise ValueError("joint_velocities must contain only finite values")
        joint_speed_norm = float(np.linalg.norm(joint_velocities))
        if not np.isfinite(joint_speed_norm):
            raise ValueError("joint velocity norm must be finite")

    progress = PROGRESS_COEFFICIENT * (previous_distance - current_distance)
    reward = progress

    closeness = _closeness_potential(current_distance) - _closeness_potential(
        previous_distance
    )
    reward += closeness

    current_hold_capital = _hold_progress_potential(held_steps, hold_steps_required)
    previous_hold_capital = _hold_progress_potential(
        previous_held_steps, hold_steps_required
    )
    if held_steps == 0 and previous_held_steps > 0:
        if not 0 <= HOLD_EXIT_FORFEIT_FRACTION <= 1:
            raise ValueError("HOLD_EXIT_FORFEIT_FRACTION must be between 0 and 1")
        hold_progress = -(HOLD_EXIT_FORFEIT_FRACTION * previous_hold_capital)
    else:
        hold_progress = current_hold_capital - previous_hold_capital
    reward += hold_progress

    outside_band = 0.0
    if penalize_outside and current_distance > success_threshold:
        if OUTSIDE_BAND_WIDTH <= 0:
            raise ValueError("OUTSIDE_BAND_WIDTH must be positive")
        outside_fraction = min(
            (current_distance - success_threshold) / OUTSIDE_BAND_WIDTH,
            1.0,
        )
        outside_band = -(OUTSIDE_BAND_PENALTY * outside_fraction)
    reward += outside_band

    hold_complete = 0.0
    if held_steps >= hold_steps_required and previous_held_steps < hold_steps_required:
        hold_complete = HOLD_COMPLETE_BONUS
    reward += hold_complete

    terminal_stabilization = 0.0
    if (
        joint_velocities is not None
        and current_distance <= TERMINAL_STABILIZATION_DISTANCE
        and joint_speed_norm > TERMINAL_STABILIZATION_SPEED_THRESHOLD
    ):
        terminal_stabilization = -TERMINAL_STABILIZATION_COEFFICIENT * (
            joint_speed_norm - TERMINAL_STABILIZATION_SPEED_THRESHOLD
        )
    reward += terminal_stabilization

    action_cost = 0.0
    if action is not None:
        action_cost = -(ACTION_COST_COEFFICIENT * float(np.sum(np.square(action))))
    reward += action_cost

    return RewardResult(
        total=float(reward),
        components={
            "progress": float(progress),
            "closeness": float(closeness),
            "hold_progress": float(hold_progress),
            "outside_band": float(outside_band),
            "hold_complete": float(hold_complete),
            "terminal_stabilization": float(terminal_stabilization),
            "action_cost": float(action_cost),
        },
    )
