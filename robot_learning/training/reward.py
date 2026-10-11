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

DEFAULT_REWARD_PROFILE = "default"
TARGETED_REGULATION_PROFILE = "targeted_regulation"
BRAKING_DISTANCE = 0.05
TARGETED_JOINT_VELOCITY_COEFFICIENT = 0.01
TARGETED_JOINT_VELOCITY_SCALE = 4.0
TARGETED_ENDPOINT_VELOCITY_COEFFICIENT = 0.05
TARGETED_ENDPOINT_VELOCITY_SCALE = 0.25
TARGETED_ACTION_REGULATION_COEFFICIENT = 0.03


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


def _smoothstep(value: float) -> float:
    value = float(np.clip(value, 0.0, 1.0))
    return value * value * (3.0 - 2.0 * value)


def _bounded_squared_magnitude(
    value: np.ndarray | float, scale: float
) -> float:
    if scale <= 0:
        raise ValueError("a bounded magnitude scale must be positive")
    magnitude = float(np.linalg.norm(np.asarray(value, dtype=np.float64)))
    return float(np.tanh(magnitude / scale) ** 2)


def reach_reward(
    previous_distance: float,
    current_distance: float,
    success_threshold: float,
    action: np.ndarray | None = None,
    held_steps: int = 0,
    previous_held_steps: int = 0,
    hold_steps_required: int = 100,
    penalize_outside: bool = False,
    *,
    reward_profile: str = DEFAULT_REWARD_PROFILE,
    joint_velocity: np.ndarray | None = None,
    endpoint_velocity: float | None = None,
) -> RewardResult:
    if reward_profile not in {
        DEFAULT_REWARD_PROFILE,
        TARGETED_REGULATION_PROFILE,
    }:
        raise ValueError(f"unknown reward profile: {reward_profile}")

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

    components = {
        "progress": float(progress),
        "closeness": float(closeness),
        "hold_progress": float(hold_progress),
        "outside_band": float(outside_band),
        "hold_complete": float(hold_complete),
        "action_cost": float(action_cost),
    }

    if reward_profile == TARGETED_REGULATION_PROFILE:
        if joint_velocity is None or endpoint_velocity is None:
            raise ValueError(
                "targeted regulation requires joint and endpoint velocity"
            )
        if BRAKING_DISTANCE <= success_threshold:
            raise ValueError("BRAKING_DISTANCE must exceed success_threshold")

        braking_weight = _smoothstep(
            (BRAKING_DISTANCE - current_distance)
            / (BRAKING_DISTANCE - success_threshold)
        )
        joint_velocity_penalty = -(
            TARGETED_JOINT_VELOCITY_COEFFICIENT
            * _bounded_squared_magnitude(
                joint_velocity, TARGETED_JOINT_VELOCITY_SCALE
            )
        )
        endpoint_velocity_penalty = -(
            TARGETED_ENDPOINT_VELOCITY_COEFFICIENT
            * braking_weight
            * _bounded_squared_magnitude(
                endpoint_velocity, TARGETED_ENDPOINT_VELOCITY_SCALE
            )
        )
        action_regulation_penalty = -(
            TARGETED_ACTION_REGULATION_COEFFICIENT
            * braking_weight
            * _bounded_squared_magnitude(
                np.zeros(1, dtype=np.float64)
                if action is None
                else action,
                1.0,
            )
        )
        reward += (
            joint_velocity_penalty
            + endpoint_velocity_penalty
            + action_regulation_penalty
        )
        components.update(
            {
                "braking_weight": float(braking_weight),
                "targeted_joint_velocity": float(joint_velocity_penalty),
                "targeted_endpoint_velocity": float(endpoint_velocity_penalty),
                "targeted_action_regulation": float(action_regulation_penalty),
            }
        )

    return RewardResult(
        total=float(reward),
        components=components,
    )
