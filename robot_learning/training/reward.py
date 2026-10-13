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
STABILIZATION_BAND_WIDTH = 0.005
STABILIZATION_VELOCITY_COST_COEFFICIENT = 0.02


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


def _stabilization_band_weight(
    distance: float, success_threshold: float
) -> float:
    """Weight velocity cost near the tolerance boundary.

    The cost is full inside the tolerance and tapers smoothly to zero over a
    narrow outside band.  The outside portion supplies a braking signal before
    the hold counter can start, without changing the binary success test.
    """
    if STABILIZATION_BAND_WIDTH <= 0:
        raise ValueError("STABILIZATION_BAND_WIDTH must be positive")
    if distance <= success_threshold:
        return 1.0
    if distance >= success_threshold + STABILIZATION_BAND_WIDTH:
        return 0.0

    fraction = (distance - success_threshold) / STABILIZATION_BAND_WIDTH
    smoothstep = fraction * fraction * (3.0 - 2.0 * fraction)
    return float(1.0 - smoothstep)


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

    action_cost = 0.0
    if action is not None:
        action_cost = -(ACTION_COST_COEFFICIENT * float(np.sum(np.square(action))))
    reward += action_cost

    stabilization_penalty = 0.0
    if joint_velocities is not None:
        velocity_energy = float(
            np.sum(np.square(np.asarray(joint_velocities, dtype=np.float64)))
        )
        stabilization_penalty = -(
            STABILIZATION_VELOCITY_COST_COEFFICIENT
            * _stabilization_band_weight(current_distance, success_threshold)
            * velocity_energy
        )
    reward += stabilization_penalty

    return RewardResult(
        total=float(reward),
        components={
            "progress": float(progress),
            "closeness": float(closeness),
            "hold_progress": float(hold_progress),
            "outside_band": float(outside_band),
            "hold_complete": float(hold_complete),
            "action_cost": float(action_cost),
            "stabilization_penalty": float(stabilization_penalty),
        },
    )
