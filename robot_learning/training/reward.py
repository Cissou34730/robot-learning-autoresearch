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
NEAR_TARGET_VELOCITY_COST_COEFFICIENT = 0.005
NEAR_TARGET_DISTANCE = 0.03
BRANCH_GUIDANCE_COEFFICIENT = 0.02
BRANCH_ERROR_CLIP = 1.0
JOINT_LIMIT_RADIANS = float(np.deg2rad(170.0))
LIMIT_MARGIN_RADIANS = float(np.deg2rad(15.0))
LIMIT_PROXIMITY_COEFFICIENT = 0.02
LIMIT_AWARE_DISTANCE = 0.05
HOLD_PROGRESS_BONUS = 50.0
HOLD_PROGRESS_EXPONENT = 1.0
HOLD_EXIT_FORFEIT_FRACTION = 0.0
OUTSIDE_BAND_WIDTH = 0.01
OUTSIDE_BAND_PENALTY = 0.1
HOLD_COMPLETE_BONUS = 50.0


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


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _branch_limit_aware_reward(
    current_distance: float,
    joint_position: np.ndarray,
    branch_errors: np.ndarray,
) -> tuple[float, float]:
    errors = np.asarray(branch_errors, dtype=np.float64).reshape(2, 2)
    position = np.asarray(joint_position, dtype=np.float64)
    branch_targets = np.asarray(
        [
            [
                _wrap_to_pi(position[0] + errors[0, 0]),
                _wrap_to_pi(position[1] + errors[0, 1]),
            ],
            [
                _wrap_to_pi(position[0] + errors[1, 0]),
                _wrap_to_pi(position[1] + errors[1, 1]),
            ],
        ]
    )
    margins = JOINT_LIMIT_RADIANS - np.abs(branch_targets)
    valid = np.all(margins >= 0.0, axis=1)
    if np.any(valid):
        selected = int(np.argmax(np.where(valid, np.min(margins, axis=1), -np.inf)))
    else:
        selected = int(np.argmin(np.sum(np.square(errors), axis=1)))

    selected_error = float(np.linalg.norm(errors[selected]))
    branch_guidance = -BRANCH_GUIDANCE_COEFFICIENT * min(
        selected_error, BRANCH_ERROR_CLIP
    ) ** 2

    limit_proximity = 0.0
    selected_margin = float(np.min(margins[selected]))
    if (
        current_distance <= LIMIT_AWARE_DISTANCE
        and valid[selected]
        and selected_margin >= LIMIT_MARGIN_RADIANS
    ):
        shoulder_margin = JOINT_LIMIT_RADIANS - abs(float(position[0]))
        risk = np.clip(
            (LIMIT_MARGIN_RADIANS - shoulder_margin) / LIMIT_MARGIN_RADIANS,
            0.0,
            1.0,
        )
        limit_proximity = -LIMIT_PROXIMITY_COEFFICIENT * float(risk)
    return branch_guidance, limit_proximity


def reach_reward(
    previous_distance: float,
    current_distance: float,
    success_threshold: float,
    action: np.ndarray | None = None,
    joint_velocity: np.ndarray | None = None,
    held_steps: int = 0,
    previous_held_steps: int = 0,
    hold_steps_required: int = 100,
    penalize_outside: bool = False,
    joint_position: np.ndarray | None = None,
    branch_errors: np.ndarray | None = None,
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

    near_target_velocity_cost = 0.0
    if joint_velocity is not None and current_distance <= NEAR_TARGET_DISTANCE:
        near_target_velocity_cost = -(
            NEAR_TARGET_VELOCITY_COST_COEFFICIENT
            * float(np.sum(np.square(joint_velocity)))
        )
        reward += near_target_velocity_cost

    branch_guidance = 0.0
    limit_proximity = 0.0
    if joint_position is not None and branch_errors is not None:
        branch_guidance, limit_proximity = _branch_limit_aware_reward(
            current_distance,
            joint_position,
            branch_errors,
        )
        reward += branch_guidance + limit_proximity

    hold_complete = 0.0
    if held_steps >= hold_steps_required and previous_held_steps < hold_steps_required:
        hold_complete = HOLD_COMPLETE_BONUS
    reward += hold_complete

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
            "near_target_velocity": float(near_target_velocity_cost),
            "branch_guidance": float(branch_guidance),
            "limit_proximity": float(limit_proximity),
            "hold_complete": float(hold_complete),
            "action_cost": float(action_cost),
        },
    )
