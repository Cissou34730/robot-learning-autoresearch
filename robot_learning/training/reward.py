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
# These terms are deliberately terminal-focused: ordinary reaching remains
# unshaped, while a narrow limit margin or extreme arrival speed gets a small
# stabilizing signal.  The 10% normalized margin and 2.5-to-10 speed window
# leave routine motion untouched while reserving the bounded penalties for
# near-boundary or unusually fast arrival states.  The distance gate below
# keeps these signals out of the bend-then-translate approach trajectory.
JOINT_LIMIT_SAFE_MARGIN = 0.10
JOINT_LIMIT_PENALTY_COEFFICIENT = 0.05
JOINT_SPEED_SAFE_NORM = 2.5
JOINT_SPEED_PENALTY_NORM = 10.0
JOINT_SPEED_PENALTY_COEFFICIENT = 0.005
TERMINAL_SHAPING_DISTANCE = 0.02


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


def _joint_shaping(
    joint_positions: np.ndarray | None,
    joint_velocities: np.ndarray | None,
    joint_ranges: np.ndarray | None,
) -> tuple[float, float]:
    """Return bounded penalties for limit proximity and excessive speed."""
    values = (joint_positions, joint_velocities, joint_ranges)
    if all(value is None for value in values):
        return 0.0, 0.0
    if any(value is None for value in values):
        raise ValueError(
            "joint positions, velocities, and ranges must be supplied together"
        )
    positions = np.asarray(joint_positions, dtype=np.float64)
    velocities = np.asarray(joint_velocities, dtype=np.float64)
    ranges = np.asarray(joint_ranges, dtype=np.float64)
    if (
        positions.shape != (2,)
        or velocities.shape != (2,)
        or ranges.shape != (2, 2)
    ):
        raise ValueError("joint shaping expects two positions, velocities, and ranges")
    if (
        not np.all(np.isfinite(positions))
        or not np.all(np.isfinite(velocities))
        or not np.all(np.isfinite(ranges))
    ):
        raise ValueError("joint shaping inputs must be finite")
    if np.any(ranges[:, 1] <= ranges[:, 0]):
        raise ValueError("joint ranges must have positive width")

    if JOINT_LIMIT_SAFE_MARGIN <= 0.0:
        raise ValueError("JOINT_LIMIT_SAFE_MARGIN must be positive")
    half_ranges = 0.5 * (ranges[:, 1] - ranges[:, 0])
    normalized_margins = np.minimum(
        positions - ranges[:, 0], ranges[:, 1] - positions
    ) / half_ranges
    minimum_margin = float(np.min(normalized_margins))
    limit_fraction = float(
        np.clip(
            (JOINT_LIMIT_SAFE_MARGIN - minimum_margin)
            / JOINT_LIMIT_SAFE_MARGIN,
            0.0,
            1.0,
        )
        ** 2
    )
    limit_penalty = -JOINT_LIMIT_PENALTY_COEFFICIENT * limit_fraction

    if JOINT_SPEED_PENALTY_NORM <= JOINT_SPEED_SAFE_NORM:
        raise ValueError(
            "JOINT_SPEED_PENALTY_NORM must exceed JOINT_SPEED_SAFE_NORM"
        )
    speed_norm = float(np.linalg.norm(velocities))
    speed_fraction = float(
        np.clip(
            (speed_norm - JOINT_SPEED_SAFE_NORM)
            / (JOINT_SPEED_PENALTY_NORM - JOINT_SPEED_SAFE_NORM),
            0.0,
            1.0,
        )
        ** 2
    )
    speed_penalty = -JOINT_SPEED_PENALTY_COEFFICIENT * speed_fraction
    return float(limit_penalty), float(speed_penalty)


def _terminal_shaping_active(current_distance: float) -> bool:
    """Enable joint stabilization only in the current terminal neighborhood."""
    if TERMINAL_SHAPING_DISTANCE <= 0.0:
        raise ValueError("TERMINAL_SHAPING_DISTANCE must be positive")
    return current_distance <= TERMINAL_SHAPING_DISTANCE


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
    joint_positions: np.ndarray | None = None,
    joint_velocities: np.ndarray | None = None,
    joint_ranges: np.ndarray | None = None,
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

    joint_limit_penalty, joint_speed_penalty = _joint_shaping(
        joint_positions,
        joint_velocities,
        joint_ranges,
    )
    if not _terminal_shaping_active(current_distance):
        joint_limit_penalty = 0.0
        joint_speed_penalty = 0.0
    reward += joint_limit_penalty + joint_speed_penalty

    return RewardResult(
        total=float(reward),
        components={
            "progress": float(progress),
            "closeness": float(closeness),
            "hold_progress": float(hold_progress),
            "outside_band": float(outside_band),
            "hold_complete": float(hold_complete),
            "action_cost": float(action_cost),
            "joint_limit": float(joint_limit_penalty),
            "joint_speed": float(joint_speed_penalty),
        },
    )
