"""Scenario-owned reward.

This file is research code, not runner configuration. A future experiment may
replace its terms, coefficients, or mathematical form entirely without touching
generic AutoResearch code; Git code lineage records the exact implementation
that produced every experiment.

This module is a deliberate experimental reward for a single campaign. Every
step it charges a direct state cost proportional to the current distance plus a
small fixed step cost, and it pays a one-time terminal bonus on the step that
first reaches the required hold length:

    reward = -(DISTANCE_COST_COEFFICIENT * current_distance)
    reward += -STEP_COST
    reward += HOLD_PROGRESS_BONUS if held_steps > 0 else 0.0
    reward += SUCCESS_BONUS if held_steps >= hold_steps_required
              and previous_held_steps < hold_steps_required else 0.0

`components` is an arbitrary mapping. No generic module may depend on any
particular component name.
"""

from dataclasses import dataclass

import numpy as np

DISTANCE_COST_COEFFICIENT = 5.0
STEP_COST = 0.01
HOLD_PROGRESS_BONUS = 0.05
SUCCESS_BONUS = 10.0


@dataclass(frozen=True)
class RewardResult:
    """Scalar reward consumed by the RL algorithm plus free-form attribution."""

    total: float
    components: dict[str, float]


def reach_reward(
    previous_distance: float,
    current_distance: float,
    success_threshold: float,
    action: np.ndarray | None = None,
    held_steps: int = 0,
    previous_held_steps: int = 0,
    hold_steps_required: int = 100,
    penalize_outside: bool = False,
) -> RewardResult:
    distance_cost = -(DISTANCE_COST_COEFFICIENT * current_distance)
    step_cost = -STEP_COST
    hold_progress = HOLD_PROGRESS_BONUS if held_steps > 0 else 0.0

    success_bonus = 0.0
    if held_steps >= hold_steps_required and previous_held_steps < hold_steps_required:
        success_bonus = SUCCESS_BONUS

    reward = distance_cost + step_cost + hold_progress + success_bonus

    return RewardResult(
        total=float(reward),
        components={
            "distance_cost": float(distance_cost),
            "step_cost": float(step_cost),
            "hold_progress": float(hold_progress),
            "success_bonus": float(success_bonus),
        },
    )
