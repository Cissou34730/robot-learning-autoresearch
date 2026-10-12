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
HOLD_RECOVERY_PROFILE = "hold_recovery"
DIRECT_LIMIT_VELOCITY_PROFILE = "direct_limit_velocity"
BRAKING_DISTANCE = 0.05
TARGETED_JOINT_VELOCITY_COEFFICIENT = 0.01
TARGETED_JOINT_VELOCITY_SCALE = 4.0
TARGETED_ENDPOINT_VELOCITY_COEFFICIENT = 0.05
TARGETED_ENDPOINT_VELOCITY_SCALE = 0.25
TARGETED_ACTION_REGULATION_COEFFICIENT = 0.03
HOLD_RECOVERY_PROGRESS_BONUS = 100.0
HOLD_RECOVERY_PROGRESS_EXPONENT = 2.0
HOLD_RECOVERY_EXIT_FORFEIT_FRACTION = 1.0
HOLD_RECOVERY_JOINT_VELOCITY_COEFFICIENT = 0.01
HOLD_RECOVERY_JOINT_VELOCITY_SCALE = 4.0
HOLD_RECOVERY_ENDPOINT_VELOCITY_COEFFICIENT = 0.05
HOLD_RECOVERY_ENDPOINT_VELOCITY_SCALE = 0.25
HOLD_RECOVERY_ACTION_REGULATION_COEFFICIENT = 0.03
DIRECT_LIMIT_VELOCITY_JOINT_LIMIT_MARGIN = np.deg2rad(20.0)
DIRECT_LIMIT_VELOCITY_JOINT_LIMIT_COEFFICIENT = 0.08
DIRECT_LIMIT_VELOCITY_JOINT_VELOCITY_COEFFICIENT = 0.02
DIRECT_LIMIT_VELOCITY_JOINT_VELOCITY_SCALE = 4.0
DIRECT_LIMIT_VELOCITY_ENDPOINT_VELOCITY_COEFFICIENT = 0.08
DIRECT_LIMIT_VELOCITY_ENDPOINT_VELOCITY_SCALE = 0.25
DIRECT_LIMIT_VELOCITY_ACTION_REGULATION_COEFFICIENT = 0.04
DIRECT_LIMIT_VELOCITY_DISTANCE_SCALE = 0.02


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


def _hold_recovery_progress_potential(
    held_steps: int, hold_steps_required: int
) -> float:
    if hold_steps_required <= 0:
        raise ValueError("hold_steps_required must be positive")
    progress = np.clip(held_steps / hold_steps_required, 0.0, 1.0)
    return HOLD_RECOVERY_PROGRESS_BONUS * float(
        progress**HOLD_RECOVERY_PROGRESS_EXPONENT
    )


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


def _validated_direct_limit_velocity_inputs(
    action: np.ndarray | None,
    joint_position: np.ndarray | None,
    joint_velocity: np.ndarray | None,
    endpoint_velocity: float | None,
    joint_ranges: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, np.ndarray]:
    if (
        action is None
        or joint_position is None
        or joint_velocity is None
        or endpoint_velocity is None
        or joint_ranges is None
    ):
        raise ValueError(
            "direct limit velocity requires action, joint position, joint "
            "velocity, endpoint velocity, and joint ranges"
        )

    action_array = np.asarray(action, dtype=np.float64)
    position_array = np.asarray(joint_position, dtype=np.float64)
    velocity_array = np.asarray(joint_velocity, dtype=np.float64)
    ranges_array = np.asarray(joint_ranges, dtype=np.float64)
    if action_array.ndim != 1 or position_array.ndim != 1:
        raise ValueError("action and joint position must be one-dimensional")
    if velocity_array.shape != position_array.shape:
        raise ValueError("joint velocity must match joint position shape")
    if action_array.shape != position_array.shape:
        raise ValueError("action must match joint position shape")
    if ranges_array.shape != (position_array.size, 2):
        raise ValueError("joint ranges must have shape (joint_count, 2)")
    if not (
        np.all(np.isfinite(action_array))
        and np.all(np.isfinite(position_array))
        and np.all(np.isfinite(velocity_array))
        and np.all(np.isfinite(ranges_array))
    ):
        raise ValueError("direct limit velocity inputs must be finite")
    if np.any(action_array < -1.0) or np.any(action_array > 1.0):
        raise ValueError("direct limit velocity action must be in [-1, 1]")
    if np.any(ranges_array[:, 0] >= ranges_array[:, 1]):
        raise ValueError("joint range lower bounds must be below upper bounds")
    if np.any(
        (ranges_array[:, 1] - ranges_array[:, 0])
        <= 2.0 * DIRECT_LIMIT_VELOCITY_JOINT_LIMIT_MARGIN
    ):
        raise ValueError("joint ranges must contain the configured limit margin")

    endpoint_velocity_array = np.asarray(
        endpoint_velocity, dtype=np.float64
    )
    if endpoint_velocity_array.shape != ():
        raise ValueError("endpoint velocity must be a scalar")
    endpoint_velocity_value = float(endpoint_velocity_array)
    if not np.isfinite(endpoint_velocity_value) or endpoint_velocity_value < 0.0:
        raise ValueError("endpoint velocity must be a finite non-negative scalar")
    return (
        action_array,
        position_array,
        velocity_array,
        endpoint_velocity_value,
        ranges_array,
    )


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
    joint_position: np.ndarray | None = None,
    joint_ranges: np.ndarray | None = None,
) -> RewardResult:
    if reward_profile not in {
        DEFAULT_REWARD_PROFILE,
        TARGETED_REGULATION_PROFILE,
        HOLD_RECOVERY_PROFILE,
        DIRECT_LIMIT_VELOCITY_PROFILE,
    }:
        raise ValueError(f"unknown reward profile: {reward_profile}")

    progress = PROGRESS_COEFFICIENT * (previous_distance - current_distance)
    reward = progress

    closeness = _closeness_potential(current_distance) - _closeness_potential(
        previous_distance
    )
    reward += closeness

    if reward_profile == HOLD_RECOVERY_PROFILE:
        current_hold_capital = _hold_recovery_progress_potential(
            held_steps, hold_steps_required
        )
        previous_hold_capital = _hold_recovery_progress_potential(
            previous_held_steps, hold_steps_required
        )
    else:
        current_hold_capital = _hold_progress_potential(
            held_steps, hold_steps_required
        )
        previous_hold_capital = _hold_progress_potential(
            previous_held_steps, hold_steps_required
        )
    if held_steps == 0 and previous_held_steps > 0:
        if reward_profile == HOLD_RECOVERY_PROFILE:
            forfeiture_fraction = HOLD_RECOVERY_EXIT_FORFEIT_FRACTION
            if not 0 <= forfeiture_fraction <= 1:
                raise ValueError(
                    "HOLD_RECOVERY_EXIT_FORFEIT_FRACTION must be between 0 and 1"
                )
        else:
            forfeiture_fraction = HOLD_EXIT_FORFEIT_FRACTION
            if not 0 <= forfeiture_fraction <= 1:
                raise ValueError(
                    "HOLD_EXIT_FORFEIT_FRACTION must be between 0 and 1"
                )
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

    if reward_profile == DIRECT_LIMIT_VELOCITY_PROFILE:
        if (
            not np.isfinite(current_distance)
            or current_distance < 0.0
            or not np.isfinite(success_threshold)
            or success_threshold <= 0.0
            or DIRECT_LIMIT_VELOCITY_DISTANCE_SCALE <= 0.0
        ):
            raise ValueError(
                "direct limit velocity distances and scale must be finite "
                "and positive"
            )
        (
            validated_action,
            validated_position,
            validated_velocity,
            validated_endpoint_velocity,
            validated_ranges,
        ) = _validated_direct_limit_velocity_inputs(
            action,
            joint_position,
            joint_velocity,
            endpoint_velocity,
            joint_ranges,
        )
        lower_distance = validated_position - validated_ranges[:, 0]
        upper_distance = validated_ranges[:, 1] - validated_position
        nearest_limit_distance = np.minimum(lower_distance, upper_distance)
        normalized_limit_distance = np.clip(
            nearest_limit_distance
            / DIRECT_LIMIT_VELOCITY_JOINT_LIMIT_MARGIN,
            0.0,
            1.0,
        )
        limit_proximity = 1.0 - (
            normalized_limit_distance**2
            * (3.0 - 2.0 * normalized_limit_distance)
        )
        joint_limit_penalty = -(
            DIRECT_LIMIT_VELOCITY_JOINT_LIMIT_COEFFICIENT
            * float(np.mean(limit_proximity))
        )
        approach_weight = 1.0 / (
            1.0
            + np.exp(
                (current_distance - success_threshold)
                / DIRECT_LIMIT_VELOCITY_DISTANCE_SCALE
            )
        )
        joint_velocity_penalty = -(
            DIRECT_LIMIT_VELOCITY_JOINT_VELOCITY_COEFFICIENT
            * approach_weight
            * _bounded_squared_magnitude(
                validated_velocity,
                DIRECT_LIMIT_VELOCITY_JOINT_VELOCITY_SCALE,
            )
        )
        endpoint_velocity_penalty = -(
            DIRECT_LIMIT_VELOCITY_ENDPOINT_VELOCITY_COEFFICIENT
            * approach_weight
            * _bounded_squared_magnitude(
                validated_endpoint_velocity,
                DIRECT_LIMIT_VELOCITY_ENDPOINT_VELOCITY_SCALE,
            )
        )
        action_regulation_penalty = -(
            DIRECT_LIMIT_VELOCITY_ACTION_REGULATION_COEFFICIENT
            * approach_weight
            * _bounded_squared_magnitude(validated_action, 1.0)
        )
        reward += (
            joint_limit_penalty
            + joint_velocity_penalty
            + endpoint_velocity_penalty
            + action_regulation_penalty
        )
        components.update(
            {
                "direct_limit_velocity_weight": float(approach_weight),
                "direct_limit_velocity_joint_limit": float(
                    joint_limit_penalty
                ),
                "direct_limit_velocity_joint_velocity": float(
                    joint_velocity_penalty
                ),
                "direct_limit_velocity_endpoint_velocity": float(
                    endpoint_velocity_penalty
                ),
                "direct_limit_velocity_action_regulation": float(
                    action_regulation_penalty
                ),
            }
        )

    if reward_profile == HOLD_RECOVERY_PROFILE:
        if joint_velocity is None or endpoint_velocity is None:
            raise ValueError(
                "hold recovery requires joint and endpoint velocity"
            )

        joint_velocity_penalty = 0.0
        endpoint_velocity_penalty = 0.0
        action_regulation_penalty = 0.0
        if current_distance <= success_threshold:
            joint_velocity_penalty = -(
                HOLD_RECOVERY_JOINT_VELOCITY_COEFFICIENT
                * _bounded_squared_magnitude(
                    joint_velocity, HOLD_RECOVERY_JOINT_VELOCITY_SCALE
                )
            )
            endpoint_velocity_penalty = -(
                HOLD_RECOVERY_ENDPOINT_VELOCITY_COEFFICIENT
                * _bounded_squared_magnitude(
                    endpoint_velocity, HOLD_RECOVERY_ENDPOINT_VELOCITY_SCALE
                )
            )
            action_regulation_penalty = -(
                HOLD_RECOVERY_ACTION_REGULATION_COEFFICIENT
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
                    "hold_recovery_joint_velocity": float(
                        joint_velocity_penalty
                    ),
                    "hold_recovery_endpoint_velocity": float(
                        endpoint_velocity_penalty
                    ),
                    "hold_recovery_action_regulation": float(
                        action_regulation_penalty
                    ),
                }
            )

    return RewardResult(
        total=float(reward),
        components=components,
    )
