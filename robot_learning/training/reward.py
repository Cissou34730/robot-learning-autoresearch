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
HOLD_AWARE_OUTSIDE_BAND_PENALTY = 5.0
HOLD_COMPLETE_BONUS = 50.0
POSTURE_CONDITION_THRESHOLD = 20.0
POSTURE_CONDITION_PENALTY_COEFFICIENT = 1.0
POSTURE_LIMIT_MARGIN_SCALE = 0.2
POSTURE_LIMIT_PENALTY_COEFFICIENT = 2.0

REWARD_VARIANTS = (
    "baseline",
    "hold_aware",
    "posture_limit_aware",
)


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


def validate_reward_variant(reward_variant: str) -> str:
    if reward_variant not in REWARD_VARIANTS:
        allowed = ", ".join(REWARD_VARIANTS)
        raise ValueError(
            f"Unknown reward variant {reward_variant!r}; expected one of: {allowed}"
        )
    return reward_variant


def _posture_penalties(
    *,
    current_distance: float,
    success_threshold: float,
    jacobian_condition_number: float,
    minimum_joint_limit_margin: float,
) -> tuple[float, float]:
    if current_distance > success_threshold:
        return 0.0, 0.0
    if POSTURE_CONDITION_THRESHOLD <= 0:
        raise ValueError("POSTURE_CONDITION_THRESHOLD must be positive")
    if POSTURE_LIMIT_MARGIN_SCALE <= 0:
        raise ValueError("POSTURE_LIMIT_MARGIN_SCALE must be positive")

    if np.isfinite(jacobian_condition_number):
        condition_risk = max(
            (float(jacobian_condition_number) / POSTURE_CONDITION_THRESHOLD) - 1.0,
            0.0,
        )
    else:
        condition_risk = 10.0
    condition_penalty = -(
        POSTURE_CONDITION_PENALTY_COEFFICIENT * condition_risk
    )

    limit_risk = max(
        1.0 - (float(minimum_joint_limit_margin) / POSTURE_LIMIT_MARGIN_SCALE),
        0.0,
    )
    limit_penalty = -(POSTURE_LIMIT_PENALTY_COEFFICIENT * limit_risk)
    return float(condition_penalty), float(limit_penalty)


def reach_reward(
    previous_distance: float,
    current_distance: float,
    success_threshold: float,
    action: np.ndarray | None = None,
    held_steps: int = 0,
    previous_held_steps: int = 0,
    hold_steps_required: int = 100,
    penalize_outside: bool = False,
    reward_variant: str = "baseline",
    jacobian_condition_number: float | None = None,
    minimum_joint_limit_margin: float | None = None,
) -> RewardResult:
    reward_variant = validate_reward_variant(reward_variant)
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
        hold_exit_forfeit_fraction = (
            1.0
            if reward_variant == "hold_aware"
            else HOLD_EXIT_FORFEIT_FRACTION
        )
        if not 0 <= hold_exit_forfeit_fraction <= 1:
            raise ValueError("hold exit forfeiture must be between 0 and 1")
        hold_progress = -(hold_exit_forfeit_fraction * previous_hold_capital)
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
        outside_penalty = (
            HOLD_AWARE_OUTSIDE_BAND_PENALTY
            if reward_variant == "hold_aware"
            else OUTSIDE_BAND_PENALTY
        )
        outside_band = -(outside_penalty * outside_fraction)
    reward += outside_band

    hold_complete = 0.0
    if held_steps >= hold_steps_required and previous_held_steps < hold_steps_required:
        hold_complete = HOLD_COMPLETE_BONUS
    reward += hold_complete

    action_cost = 0.0
    if action is not None:
        action_cost = -(ACTION_COST_COEFFICIENT * float(np.sum(np.square(action))))
    reward += action_cost

    posture_condition = 0.0
    posture_limit = 0.0
    if reward_variant == "posture_limit_aware":
        if (
            jacobian_condition_number is None
            or minimum_joint_limit_margin is None
        ):
            raise ValueError(
                "posture_limit_aware requires Jacobian and joint-limit metrics"
            )
        posture_condition, posture_limit = _posture_penalties(
            current_distance=current_distance,
            success_threshold=success_threshold,
            jacobian_condition_number=jacobian_condition_number,
            minimum_joint_limit_margin=minimum_joint_limit_margin,
        )
        reward += posture_condition + posture_limit

    components = {
        "progress": float(progress),
        "closeness": float(closeness),
        "hold_progress": float(hold_progress),
        "outside_band": float(outside_band),
        "hold_complete": float(hold_complete),
        "action_cost": float(action_cost),
    }
    if reward_variant == "posture_limit_aware":
        components["posture_condition"] = posture_condition
        components["posture_limit"] = posture_limit

    return RewardResult(total=float(reward), components=components)
