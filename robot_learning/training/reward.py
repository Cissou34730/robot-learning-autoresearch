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
PHASE_SEPARATED_HOLD_EXIT_FORFEIT_FRACTION = 1.0
OUTSIDE_BAND_WIDTH = 0.01
OUTSIDE_BAND_PENALTY = 0.1
HOLD_COMPLETE_BONUS = 50.0
IK_BRANCH_PROGRESS_COEFFICIENT = 2.0
RESET_ESCAPE_PROGRESS_COEFFICIENT = 1.0
IK_BRANCH_ERROR_NORMALIZER = float(np.sqrt(2.0) * np.pi)
TARGET_ELBOW_EPSILON = 1e-8


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


def _ik_branch_potential(
    branch_errors: np.ndarray, branch_validity: np.ndarray
) -> float:
    """Bound the nearer branch's wrapped joint error in radians to [0, 1]."""
    errors = np.asarray(branch_errors, dtype=np.float64)
    valid = np.asarray(branch_validity, dtype=bool)
    if errors.shape != (2, 2) or valid.shape != (2,):
        return 0.0
    branch_norms = [
        float(np.linalg.norm(branch_error))
        for branch_error, is_valid in zip(errors, valid)
        if is_valid and np.isfinite(branch_error).all()
    ]
    if not branch_norms:
        return 0.0
    normalized_error = np.clip(
        min(branch_norms) / IK_BRANCH_ERROR_NORMALIZER, 0.0, 1.0
    )
    return float(1.0 - normalized_error)


def _reset_escape_potential(q2: float, target_elbow_magnitude: float) -> float:
    """Bound progress from q2=0 toward the target elbow magnitude."""
    if not np.isfinite(q2) or not np.isfinite(target_elbow_magnitude):
        return 0.0
    if target_elbow_magnitude <= TARGET_ELBOW_EPSILON:
        return 0.0
    progress = abs(float(q2)) / float(target_elbow_magnitude)
    return float(np.clip(progress, 0.0, 1.0))


def reach_reward(
    previous_distance: float,
    current_distance: float,
    success_threshold: float,
    action: np.ndarray | None = None,
    held_steps: int = 0,
    previous_held_steps: int = 0,
    hold_steps_required: int = 100,
    penalize_outside: bool = False,
    trajectory_shaping: bool = False,
    previous_branch_errors: np.ndarray | None = None,
    current_branch_errors: np.ndarray | None = None,
    previous_branch_validity: np.ndarray | None = None,
    current_branch_validity: np.ndarray | None = None,
    previous_q2: float | None = None,
    current_q2: float | None = None,
    target_elbow_magnitude: float | None = None,
    phase_separated_shaping: bool = False,
    approach_phase: bool = True,
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
        forfeiture_fraction = (
            PHASE_SEPARATED_HOLD_EXIT_FORFEIT_FRACTION
            if phase_separated_shaping
            else HOLD_EXIT_FORFEIT_FRACTION
        )
        if not 0 <= forfeiture_fraction <= 1:
            raise ValueError("hold exit forfeiture fraction must be between 0 and 1")
        hold_progress = -(forfeiture_fraction * previous_hold_capital)
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

    if trajectory_shaping:
        if (
            previous_branch_errors is None
            or current_branch_errors is None
            or previous_branch_validity is None
            or current_branch_validity is None
            or previous_q2 is None
            or current_q2 is None
            or target_elbow_magnitude is None
        ):
            raise ValueError(
                "trajectory shaping requires branch errors, q2 values, "
                "and target elbow magnitude"
            )
        previous_branch_potential = _ik_branch_potential(
            previous_branch_errors, previous_branch_validity
        )
        current_branch_potential = _ik_branch_potential(
            current_branch_errors, current_branch_validity
        )
        if phase_separated_shaping and not approach_phase:
            ik_branch_progress = 0.0
            reset_escape_progress = 0.0
        else:
            ik_branch_progress = IK_BRANCH_PROGRESS_COEFFICIENT * (
                current_branch_potential - previous_branch_potential
            )
            previous_escape_potential = _reset_escape_potential(
                previous_q2, target_elbow_magnitude
            )
            current_escape_potential = _reset_escape_potential(
                current_q2, target_elbow_magnitude
            )
            reset_escape_progress = RESET_ESCAPE_PROGRESS_COEFFICIENT * (
                current_escape_potential - previous_escape_potential
            )
        reward += ik_branch_progress + reset_escape_progress
        components.update(
            {
                "ik_branch_progress": float(ik_branch_progress),
                "reset_escape_progress": float(reset_escape_progress),
            }
        )

    return RewardResult(total=float(reward), components=components)
