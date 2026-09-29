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
BOUNDARY_BAND_WIDTH = 0.005
JOINT_VELOCITY_PENALTY = 0.01
ENDPOINT_VELOCITY_PENALTY = 1.0
BOUNDARY_ACTION_PENALTY = 0.05
TERMINAL_JOINT_VELOCITY_PENALTY = 0.01
TERMINAL_ENDPOINT_VELOCITY_PENALTY = 0.5


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


def _boundary_braking_penalties(
    distance: float,
    success_threshold: float,
    action: np.ndarray | None,
    joint_velocity: np.ndarray | None,
    endpoint_velocity: np.ndarray | None,
    scale: float,
) -> tuple[float, float, float]:
    if BOUNDARY_BAND_WIDTH <= 0:
        raise ValueError("BOUNDARY_BAND_WIDTH must be positive")
    if not 0.0 <= scale <= 1.0:
        raise ValueError("boundary braking scale must be between 0 and 1")
    boundary_weight = float(
        np.exp(
            -0.5
            * ((distance - success_threshold) / BOUNDARY_BAND_WIDTH) ** 2
        )
    )
    boundary_weight *= scale
    joint_velocity_penalty = 0.0
    if joint_velocity is not None:
        joint_velocity_penalty = -(
            boundary_weight
            * JOINT_VELOCITY_PENALTY
            * float(np.sum(np.square(joint_velocity)))
        )
    endpoint_velocity_penalty = 0.0
    if endpoint_velocity is not None:
        endpoint_velocity_penalty = -(
            boundary_weight
            * ENDPOINT_VELOCITY_PENALTY
            * float(np.sum(np.square(endpoint_velocity)))
        )
    action_penalty = 0.0
    if action is not None:
        action_penalty = -(
            boundary_weight
            * BOUNDARY_ACTION_PENALTY
            * float(np.sum(np.square(action)))
        )
    return (
        float(joint_velocity_penalty),
        float(endpoint_velocity_penalty),
        float(action_penalty),
    )


def _terminal_stabilization_penalties(
    distance: float,
    success_threshold: float,
    joint_velocity: np.ndarray | None,
    endpoint_velocity: np.ndarray | None,
    scale: float,
) -> tuple[float, float]:
    if not 0.0 <= scale <= 1.0:
        raise ValueError("terminal stabilization scale must be between 0 and 1")
    terminal_weight = scale * float(distance <= success_threshold)
    joint_velocity_penalty = 0.0
    if joint_velocity is not None:
        joint_velocity_penalty = -(
            terminal_weight
            * TERMINAL_JOINT_VELOCITY_PENALTY
            * float(np.sum(np.square(joint_velocity)))
        )
    endpoint_velocity_penalty = 0.0
    if endpoint_velocity is not None:
        endpoint_velocity_penalty = -(
            terminal_weight
            * TERMINAL_ENDPOINT_VELOCITY_PENALTY
            * float(np.sum(np.square(endpoint_velocity)))
        )
    return float(joint_velocity_penalty), float(endpoint_velocity_penalty)


def reach_reward(
    previous_distance: float,
    current_distance: float,
    success_threshold: float,
    action: np.ndarray | None = None,
    held_steps: int = 0,
    previous_held_steps: int = 0,
    hold_steps_required: int = 100,
    penalize_outside: bool = False,
    joint_velocity: np.ndarray | None = None,
    endpoint_velocity: np.ndarray | None = None,
    boundary_braking_scale: float = 1.0,
    terminal_stabilization_scale: float = 0.0,
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

    (
        joint_velocity_penalty,
        endpoint_velocity_penalty,
        boundary_action_penalty,
    ) = _boundary_braking_penalties(
        current_distance,
        success_threshold,
        action,
        joint_velocity,
        endpoint_velocity,
        boundary_braking_scale,
    )
    (
        terminal_joint_velocity_penalty,
        terminal_endpoint_velocity_penalty,
    ) = _terminal_stabilization_penalties(
        current_distance,
        success_threshold,
        joint_velocity,
        endpoint_velocity,
        terminal_stabilization_scale,
    )
    reward += (
        joint_velocity_penalty
        + endpoint_velocity_penalty
        + boundary_action_penalty
        + terminal_joint_velocity_penalty
        + terminal_endpoint_velocity_penalty
    )

    return RewardResult(
        total=float(reward),
        components={
            "progress": float(progress),
            "closeness": float(closeness),
            "hold_progress": float(hold_progress),
            "outside_band": float(outside_band),
            "hold_complete": float(hold_complete),
            "action_cost": float(action_cost),
            "boundary_joint_velocity": joint_velocity_penalty,
            "boundary_endpoint_velocity": endpoint_velocity_penalty,
            "boundary_action": boundary_action_penalty,
            "terminal_joint_velocity": terminal_joint_velocity_penalty,
            "terminal_endpoint_velocity": terminal_endpoint_velocity_penalty,
        },
    )
