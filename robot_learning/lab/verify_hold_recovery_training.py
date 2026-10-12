"""Defect-sensitive checks for the training-only hold-recovery route.

The checks use controlled reward inputs and synthetic distance transitions.
They do not train, evaluate, or claim that the route improves learned
performance.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from robot_learning.scenario.environment import make_evaluation_env
from robot_learning.scenario.policy_io import DIRECT_CONTROL_PROFILE
from robot_learning.training.environment import (
    TRAINING_TARGET_RADIUS_RANGE,
    make_training_env,
)
from robot_learning.training.reward import (
    DEFAULT_REWARD_PROFILE,
    HOLD_RECOVERY_PROFILE,
    TARGETED_REGULATION_PROFILE,
    reach_reward,
)


SUCCESS_THRESHOLD = 0.01
HOLD_STEPS_REQUIRED = 100
OFFICIAL_TARGET_RADIUS_RANGE = (0.06, 0.20)
PROGRESS_COEFFICIENT = 10.0
CLOSENESS_COEFFICIENT = 4.0
CLOSENESS_LENGTH_SCALE = 0.05
ACTION_COST_COEFFICIENT = 0.01
HOLD_RECOVERY_PROGRESS_BONUS = 100.0
HOLD_RECOVERY_PROGRESS_EXPONENT = 2.0
HOLD_RECOVERY_EXIT_FORFEIT_FRACTION = 1.0
HOLD_RECOVERY_JOINT_VELOCITY_COEFFICIENT = 0.01
HOLD_RECOVERY_JOINT_VELOCITY_SCALE = 4.0
HOLD_RECOVERY_ENDPOINT_VELOCITY_COEFFICIENT = 0.05
HOLD_RECOVERY_ENDPOINT_VELOCITY_SCALE = 0.25
HOLD_RECOVERY_ACTION_REGULATION_COEFFICIENT = 0.03
HOLD_COMPLETE_BONUS = 50.0
OUTSIDE_BAND_WIDTH = 0.01
OUTSIDE_BAND_PENALTY = 0.1

RECOVERY_COMPONENTS = {
    "hold_recovery_joint_velocity",
    "hold_recovery_endpoint_velocity",
    "hold_recovery_action_regulation",
}

UNCHECKED_SCOPE = [
    "learned-policy performance, PPO behavior, and official evaluation success",
    "whether hold-recovery shaping improves complete holds or no-first-reach failures",
    "causal validity of the route-level intervention",
    "long-horizon dynamics beyond the controlled synthetic transitions",
]

EXPECTED = {
    "training_route": {
        "control_profile": DIRECT_CONTROL_PROFILE,
        "reward_profile": HOLD_RECOVERY_PROFILE,
        "target_radius_range": list(TRAINING_TARGET_RADIUS_RANGE),
    },
    "evaluation_route": {
        "control_profile": DIRECT_CONTROL_PROFILE,
        "reward_profile": DEFAULT_REWARD_PROFILE,
        "target_radius_range": list(OFFICIAL_TARGET_RADIUS_RANGE),
    },
    "hold_steps_required": HOLD_STEPS_REQUIRED,
    "recovery_progress": "100 * (held_steps / 100) ** 2",
    "interruption_forfeit": "100% of prior accumulated recovery progress",
    "regulation_activation": "current_distance <= 0.01",
}


class VerificationFailure(AssertionError):
    """A controlled laboratory check failed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationFailure(message)


def _bounded_squared(value: np.ndarray | float, scale: float) -> float:
    magnitude = float(np.linalg.norm(np.asarray(value, dtype=np.float64)))
    return float(np.tanh(magnitude / scale) ** 2)


def _reference_hold_recovery(
    previous_distance: float,
    current_distance: float,
    held_steps: int,
    previous_held_steps: int,
    action: np.ndarray,
    joint_velocity: np.ndarray,
    endpoint_velocity: float,
    *,
    penalize_outside: bool,
) -> dict[str, float]:
    """Independent equations for the new profile's controlled cases."""
    progress = PROGRESS_COEFFICIENT * (previous_distance - current_distance)
    closeness = CLOSENESS_COEFFICIENT * (
        np.exp(-current_distance / CLOSENESS_LENGTH_SCALE)
        - np.exp(-previous_distance / CLOSENESS_LENGTH_SCALE)
    )
    current_capital = HOLD_RECOVERY_PROGRESS_BONUS * (
        np.clip(held_steps / HOLD_STEPS_REQUIRED, 0.0, 1.0)
        ** HOLD_RECOVERY_PROGRESS_EXPONENT
    )
    previous_capital = HOLD_RECOVERY_PROGRESS_BONUS * (
        np.clip(previous_held_steps / HOLD_STEPS_REQUIRED, 0.0, 1.0)
        ** HOLD_RECOVERY_PROGRESS_EXPONENT
    )
    if held_steps == 0 and previous_held_steps > 0:
        hold_progress = -(
            HOLD_RECOVERY_EXIT_FORFEIT_FRACTION * previous_capital
        )
    else:
        hold_progress = current_capital - previous_capital

    outside_band = 0.0
    if penalize_outside and current_distance > SUCCESS_THRESHOLD:
        outside_band = -OUTSIDE_BAND_PENALTY * min(
            (current_distance - SUCCESS_THRESHOLD) / OUTSIDE_BAND_WIDTH,
            1.0,
        )

    hold_complete = float(
        HOLD_COMPLETE_BONUS
        if held_steps >= HOLD_STEPS_REQUIRED
        and previous_held_steps < HOLD_STEPS_REQUIRED
        else 0.0
    )
    action_cost = -ACTION_COST_COEFFICIENT * float(np.sum(action**2))
    components = {
        "progress": float(progress),
        "closeness": float(closeness),
        "hold_progress": float(hold_progress),
        "outside_band": float(outside_band),
        "hold_complete": hold_complete,
        "action_cost": float(action_cost),
    }
    if current_distance <= SUCCESS_THRESHOLD:
        components.update(
            {
                "hold_recovery_joint_velocity": -(
                    HOLD_RECOVERY_JOINT_VELOCITY_COEFFICIENT
                    * _bounded_squared(
                        joint_velocity, HOLD_RECOVERY_JOINT_VELOCITY_SCALE
                    )
                ),
                "hold_recovery_endpoint_velocity": -(
                    HOLD_RECOVERY_ENDPOINT_VELOCITY_COEFFICIENT
                    * _bounded_squared(
                        endpoint_velocity,
                        HOLD_RECOVERY_ENDPOINT_VELOCITY_SCALE,
                    )
                ),
                "hold_recovery_action_regulation": -(
                    HOLD_RECOVERY_ACTION_REGULATION_COEFFICIENT
                    * _bounded_squared(action, 1.0)
                ),
            }
        )
    return components


def _assert_reward_matches(
    label: str,
    result: Any,
    expected: dict[str, float],
    records: dict[str, Any],
) -> None:
    _require(
        set(result.components) == set(expected),
        f"{label} reward component set differs from independent reference",
    )
    for name, expected_value in expected.items():
        _require(
            np.isclose(
                result.components[name], expected_value, atol=1.0e-12
            ),
            f"{label} component {name} differs from independent reference",
        )
    expected_total = float(sum(expected.values()))
    _require(
        np.isclose(result.total, expected_total, atol=1.0e-12),
        f"{label} total differs from independent reference",
    )
    records[label] = {
        "observed": {
            "total": result.total,
            "components": result.components,
        },
        "expected": {"total": expected_total, "components": expected},
    }


def _check_routes_and_acquisition(observed: dict[str, Any]) -> None:
    training = make_training_env()
    evaluation = make_evaluation_env()
    try:
        training_route = {
            "control_profile": training.control_profile,
            "reward_profile": training.reward_profile,
            "target_radius_range": list(training.target_radius_range),
        }
        evaluation_route = {
            "control_profile": evaluation.control_profile,
            "reward_profile": evaluation.reward_profile,
            "target_radius_range": list(evaluation.target_radius_range),
        }
        _require(
            training_route == EXPECTED["training_route"],
            "training route is not direct full-radius hold recovery",
        )
        _require(
            evaluation_route == EXPECTED["evaluation_route"],
            "evaluation route is not the unchanged default route",
        )

        training.reset(seed=17)
        training._previous_distance = 0.08
        original_distance = training._distance_to_target
        original_endpoint_velocity = training._endpoint_linear_velocity
        training._distance_to_target = lambda: 0.02
        training._endpoint_linear_velocity = lambda: 2.0
        try:
            raw_action = np.asarray((1.4, -1.3), dtype=np.float64)
            transition = training.step(raw_action)
        finally:
            training._distance_to_target = original_distance
            training._endpoint_linear_velocity = original_endpoint_velocity
        components = transition[4]["reward_components"]
        _require(
            not RECOVERY_COMPONENTS.intersection(components),
            "outside-boundary acquisition was shaped by hold-recovery terms",
        )
        _require(
            {"progress", "closeness", "action_cost"}.issubset(components),
            "acquisition did not retain progress, closeness, and action terms",
        )
        _require(
            np.allclose(
                training.data.ctrl,
                np.clip(raw_action, -1.0, 1.0),
                atol=1.0e-12,
            ),
            "training route is not direct control",
        )
        observed["routes_and_outside_acquisition"] = {
            "training": training_route,
            "evaluation": evaluation_route,
            "acquisition_distance": transition[4]["distance"],
            "acquisition_components": components,
            "clipped_control": training.data.ctrl.tolist(),
        }
    finally:
        training.close()
        evaluation.close()


def _check_reward_equations(observed: dict[str, Any]) -> None:
    action = np.asarray((0.4, -0.2), dtype=np.float64)
    joint_velocity = np.asarray((1.2, -0.8), dtype=np.float64)
    records: dict[str, Any] = {}
    cases = (
        (
            "first_in_tolerance_update",
            (0.012, 0.008, 1, 0, False),
        ),
        (
            "repeated_in_tolerance_update",
            (0.008, 0.008, 50, 49, False),
        ),
        (
            "late_in_tolerance_update",
            (0.008, 0.008, 100, 99, False),
        ),
        (
            "late_hold_interruption",
            (0.008, 0.02, 0, 99, True),
        ),
        (
            "reentry_after_interruption",
            (0.02, 0.008, 1, 0, False),
        ),
    )
    for label, values in cases:
        previous_distance, current_distance, held, previous_held, outside = (
            values
        )
        result = reach_reward(
            previous_distance,
            current_distance,
            SUCCESS_THRESHOLD,
            action,
            held_steps=held,
            previous_held_steps=previous_held,
            hold_steps_required=HOLD_STEPS_REQUIRED,
            penalize_outside=outside,
            reward_profile=HOLD_RECOVERY_PROFILE,
            joint_velocity=joint_velocity,
            endpoint_velocity=0.2,
        )
        expected = _reference_hold_recovery(
            previous_distance,
            current_distance,
            held,
            previous_held,
            action,
            joint_velocity,
            0.2,
            penalize_outside=outside,
        )
        _assert_reward_matches(label, result, expected, records)

    _require(
        records["late_in_tolerance_update"]["observed"]["components"][
            "hold_progress"
        ]
        > records["repeated_in_tolerance_update"]["observed"]["components"][
            "hold_progress"
        ],
        "late uninterrupted-hold credit did not strengthen",
    )
    _require(
        records["late_hold_interruption"]["observed"]["components"][
            "hold_progress"
        ]
        == -HOLD_RECOVERY_PROGRESS_BONUS * 0.99**2,
        "interruption did not forfeit accumulated recovery progress",
    )

    default = reach_reward(
        0.08,
        0.04,
        SUCCESS_THRESHOLD,
        action,
        held_steps=1,
        previous_held_steps=0,
        hold_steps_required=HOLD_STEPS_REQUIRED,
        joint_velocity=np.asarray((20.0, 20.0)),
        endpoint_velocity=5.0,
    )
    explicit_default = reach_reward(
        0.08,
        0.04,
        SUCCESS_THRESHOLD,
        action,
        held_steps=1,
        previous_held_steps=0,
        hold_steps_required=HOLD_STEPS_REQUIRED,
        reward_profile=DEFAULT_REWARD_PROFILE,
        joint_velocity=np.asarray((20.0, 20.0)),
        endpoint_velocity=5.0,
    )
    _require(
        default == explicit_default,
        "default reward changed when velocity inputs were supplied",
    )
    targeted = reach_reward(
        0.03,
        0.03,
        SUCCESS_THRESHOLD,
        action,
        hold_steps_required=HOLD_STEPS_REQUIRED,
        reward_profile=TARGETED_REGULATION_PROFILE,
        joint_velocity=joint_velocity,
        endpoint_velocity=0.2,
    )
    _require(
        any(name.startswith("targeted_") for name in targeted.components)
        and not RECOVERY_COMPONENTS.intersection(targeted.components),
        "targeted regulation profile was replaced or renamed",
    )
    observed["independent_reward_equations"] = records
    observed["unchanged_profiles"] = {
        "default_components": default.components,
        "targeted_components": targeted.components,
    }


def _check_transitions_resets_and_complete_hold(
    observed: dict[str, Any],
) -> None:
    env = make_training_env()
    try:
        sampled_radii = []
        for seed in (3, 19, 37, 53):
            env.reset(seed=seed)
            sampled_radii.append(float(np.linalg.norm(env.data.mocap_pos[0][:2])))
        _require(
            min(sampled_radii) >= TRAINING_TARGET_RADIUS_RANGE[0]
            and max(sampled_radii) <= TRAINING_TARGET_RADIUS_RANGE[1],
            "training reset sampled outside the full-radius range",
        )

        reset_records = []
        for seed in (101, 102, 103):
            env.reset(seed=seed)
            env.data.qpos[:2] = (0.4, -0.3)
            env.data.qvel[:2] = (0.2, -0.1)
            env._held_steps = 8
            env._outside_after_hold = True
            env.reset(seed=seed + 1000)
            _require(
                np.allclose(env.data.qpos[:2], 0.0)
                and np.allclose(env.data.qvel[:2], 0.0)
                and env._held_steps == 0
                and not env._outside_after_hold,
                f"repeated reset {seed} did not restore hold state",
            )
            reset_records.append(
                {
                    "seed": seed + 1000,
                    "qpos": env.data.qpos[:2].tolist(),
                    "qvel": env.data.qvel[:2].tolist(),
                    "held_steps": env._held_steps,
                    "outside_after_hold": env._outside_after_hold,
                }
            )

        env.reset(seed=201)
        env._previous_distance = 0.008
        env._held_steps = 99
        env._outside_after_hold = False
        original_distance = env._distance_to_target
        original_endpoint_velocity = env._endpoint_linear_velocity
        env._distance_to_target = lambda: 0.02
        env._endpoint_linear_velocity = lambda: 0.0
        try:
            interruption = env.step(np.zeros(2, dtype=np.float64))
        finally:
            env._distance_to_target = original_distance
            env._endpoint_linear_velocity = original_endpoint_velocity
        _require(
            interruption[4]["held_steps"] == 0
            and not interruption[2]
            and np.isclose(
                interruption[4]["reward_components"]["hold_progress"],
                -HOLD_RECOVERY_PROGRESS_BONUS * 0.99**2,
            ),
            "late environment interruption did not reset and forfeit hold state",
        )

        original_distance = env._distance_to_target
        original_endpoint_velocity = env._endpoint_linear_velocity
        env._distance_to_target = lambda: 0.008
        env._endpoint_linear_velocity = lambda: 0.0
        try:
            reentry = env.step(np.zeros(2, dtype=np.float64))
        finally:
            env._distance_to_target = original_distance
            env._endpoint_linear_velocity = original_endpoint_velocity
        _require(
            reentry[4]["held_steps"] == 1
            and reentry[4]["reward_components"]["hold_progress"] == 0.01
            and RECOVERY_COMPONENTS.issubset(reentry[4]["reward_components"]),
            "re-entry did not restart recovery shaping from zero",
        )

        env.reset(seed=202)
        original_distance = env._distance_to_target
        original_endpoint_velocity = env._endpoint_linear_velocity
        env._distance_to_target = lambda: 0.005
        env._endpoint_linear_velocity = lambda: 0.0
        hold_transitions = []
        try:
            for _ in range(HOLD_STEPS_REQUIRED):
                hold_transitions.append(
                    env.step(np.zeros(2, dtype=np.float64))
                )
        finally:
            env._distance_to_target = original_distance
            env._endpoint_linear_velocity = original_endpoint_velocity
        _require(
            not any(item[2] for item in hold_transitions[:-1])
            and hold_transitions[-1][2]
            and hold_transitions[-1][4]["held_steps"] == HOLD_STEPS_REQUIRED,
            "complete hold did not terminate after exactly 100 in-tolerance updates",
        )
        _require(
            all(
                RECOVERY_COMPONENTS.issubset(item[4]["reward_components"])
                for item in hold_transitions
            ),
            "repeated in-tolerance updates did not use recovery regulation terms",
        )
        observed["sampling_resets_and_transitions"] = {
            "sampled_radii": sampled_radii,
            "resets": reset_records,
            "interruption": {
                "held_steps": interruption[4]["held_steps"],
                "hold_progress": interruption[4]["reward_components"][
                    "hold_progress"
                ],
            },
            "reentry": {
                "held_steps": reentry[4]["held_steps"],
                "hold_progress": reentry[4]["reward_components"][
                    "hold_progress"
                ],
            },
            "complete_hold": {
                "steps": len(hold_transitions),
                "final_held_steps": hold_transitions[-1][4]["held_steps"],
                "terminated": hold_transitions[-1][2],
            },
        }
    finally:
        env.close()


def run_checks() -> dict[str, Any]:
    observed: dict[str, Any] = {}
    _check_routes_and_acquisition(observed)
    _check_reward_equations(observed)
    _check_transitions_resets_and_complete_hold(observed)
    return {
        "status": "passed",
        "observed_vs_expected": observed,
        "expected": EXPECTED,
        "checked_scope": [
            "direct full-radius hold-recovery training route wiring",
            "unchanged direct/default evaluation route wiring",
            "outside-boundary acquisition without hold-recovery terms",
            "independent repeated in-tolerance and late interruption equations",
            "re-entry after interruption and repeated reset state restoration",
            "complete uninterrupted 100-step hold termination semantics",
        ],
        "unchecked_scope": UNCHECKED_SCOPE,
        "execution_note": (
            "This check was authored but has not been executed by the author."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args(argv)
    try:
        report = run_checks()
    except Exception as error:
        report = {
            "status": "failed",
            "observed_vs_expected": {
                "error_type": type(error).__name__,
                "error": str(error),
            },
            "expected": EXPECTED,
            "checked_scope": ["checks up to the first failure"],
            "unchecked_scope": [
                "checks after the first failure",
                *UNCHECKED_SCOPE,
            ],
            "execution_note": (
                "This check was authored but has not been executed by the author."
            ),
        }
        args.artifact.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        raise VerificationFailure(str(error))

    args.artifact.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
