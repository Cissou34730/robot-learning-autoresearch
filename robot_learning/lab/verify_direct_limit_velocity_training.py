"""Defect-sensitive checks for the direct limit/velocity training route.

The check uses controlled transitions and an independent qualitative reference
for boundary proximity and approach weighting.  It does not train, evaluate,
or claim that the route improves learned performance.
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
    DIRECT_LIMIT_VELOCITY_PROFILE,
    TARGETED_REGULATION_PROFILE,
    reach_reward,
)


SUCCESS_THRESHOLD = 0.01
HOLD_STEPS_REQUIRED = 100
OFFICIAL_TARGET_RADIUS_RANGE = (0.06, 0.20)
REGULATION_COMPONENTS = {
    "direct_limit_velocity_joint_limit",
    "direct_limit_velocity_joint_velocity",
    "direct_limit_velocity_endpoint_velocity",
    "direct_limit_velocity_action_regulation",
}
NON_LIMIT_REGULATION_COMPONENTS = REGULATION_COMPONENTS - {
    "direct_limit_velocity_joint_limit"
}
WEIGHT_COMPONENT = "direct_limit_velocity_weight"

UNCHECKED_SCOPE = [
    "learned-policy behavior, PPO optimization, and episode performance",
    "official evaluation success and the fixed 200-episode assessment",
    "causal improvement in acquisition or hold failures",
    "compiled dynamics beyond the controlled post-step transitions",
]

EXPECTED = {
    "training_route": {
        "control_profile": DIRECT_CONTROL_PROFILE,
        "reward_profile": DIRECT_LIMIT_VELOCITY_PROFILE,
        "target_radius_range": list(TRAINING_TARGET_RADIUS_RANGE),
    },
    "evaluation_route": {
        "control_profile": DIRECT_CONTROL_PROFILE,
        "reward_profile": DEFAULT_REWARD_PROFILE,
        "target_radius_range": list(OFFICIAL_TARGET_RADIUS_RANGE),
    },
    "hold_steps_required": HOLD_STEPS_REQUIRED,
    "regulation_terms": sorted(REGULATION_COMPONENTS),
    "approach_reference": (
        "a bounded decreasing function of distance, with greater weight near "
        "the 0.01 m boundary"
    ),
    "limit_reference": (
        "negative bounded mean proximity to the nearer lower or upper limit"
    ),
}


class VerificationFailure(AssertionError):
    """A controlled laboratory check failed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationFailure(message)


def _independent_limit_proximity(
    joint_position: np.ndarray, joint_ranges: np.ndarray
) -> float:
    """Independent linear reference for which states should be penalized."""
    widths = joint_ranges[:, 1] - joint_ranges[:, 0]
    reference_margin = float(np.min(widths) * 0.10)
    nearest_distance = np.minimum(
        joint_position - joint_ranges[:, 0],
        joint_ranges[:, 1] - joint_position,
    )
    proximity = np.clip(1.0 - nearest_distance / reference_margin, 0.0, 1.0)
    return float(np.mean(proximity))


def _independent_approach_weight(
    distance: float, success_threshold: float
) -> float:
    """Independent smooth reference for the desired distance ordering."""
    excess_distance = max(distance - success_threshold, 0.0)
    return 1.0 / (1.0 + excess_distance / (3.0 * success_threshold))


def _reward_case(
    *,
    previous_distance: float,
    current_distance: float,
    held_steps: int,
    previous_held_steps: int,
    action: np.ndarray,
    joint_position: np.ndarray,
    joint_velocity: np.ndarray,
    endpoint_velocity: float,
    joint_ranges: np.ndarray,
):
    return reach_reward(
        previous_distance,
        current_distance,
        SUCCESS_THRESHOLD,
        action,
        held_steps=held_steps,
        previous_held_steps=previous_held_steps,
        hold_steps_required=HOLD_STEPS_REQUIRED,
        reward_profile=DIRECT_LIMIT_VELOCITY_PROFILE,
        joint_position=joint_position,
        joint_velocity=joint_velocity,
        endpoint_velocity=endpoint_velocity,
        joint_ranges=joint_ranges,
    )


def _check_routes_and_direct_control(observed: dict[str, Any]) -> None:
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
            "training route is not direct-control full-radius limit/velocity",
        )
        _require(
            evaluation_route == EXPECTED["evaluation_route"],
            "evaluation default route changed",
        )

        sampled_radii = []
        for seed in (3, 19, 37, 53, 71, 89):
            training.reset(seed=seed)
            sampled_radii.append(
                float(np.linalg.norm(training.data.mocap_pos[0][:2]))
            )
        _require(
            all(
                TRAINING_TARGET_RADIUS_RANGE[0] <= radius
                <= TRAINING_TARGET_RADIUS_RANGE[1]
                for radius in sampled_radii
            ),
            "training reset sampled outside the full-radius range",
        )

        training.reset(seed=17)
        training._previous_distance = 0.08
        original_distance = training._distance_to_target
        original_endpoint_velocity = training._endpoint_linear_velocity
        training._distance_to_target = lambda: 0.04
        training._endpoint_linear_velocity = lambda: 0.20
        try:
            raw_action = np.asarray((1.4, -1.3), dtype=np.float64)
            transition = training.step(raw_action)
        finally:
            training._distance_to_target = original_distance
            training._endpoint_linear_velocity = original_endpoint_velocity
        components = transition[4]["reward_components"]
        _require(
            REGULATION_COMPONENTS.union({WEIGHT_COMPONENT}).issubset(
                components
            ),
            "outside-boundary acquisition omitted direct regulation terms",
        )
        _require(
            np.isfinite(
                components["direct_limit_velocity_joint_limit"]
            )
            and components["direct_limit_velocity_joint_limit"] <= 0.0,
            "outside-boundary acquisition returned an invalid joint-limit term",
        )
        _require(
            all(
                np.isfinite(components[name]) and abs(components[name]) > 0.0
                for name in NON_LIMIT_REGULATION_COMPONENTS
            ),
            "controlled acquisition did not activate velocity/action regulation",
        )
        _require(
            np.all(np.isfinite(training.data.qvel[:2]))
            and np.linalg.norm(training.data.qvel[:2]) > 0.0,
            "controlled acquisition did not produce nonzero joint velocity",
        )
        _require(
            np.allclose(
                training.data.ctrl,
                np.clip(raw_action, -1.0, 1.0),
                atol=1.0e-12,
            ),
            "training route is not direct control",
        )
        observed["routes_and_acquisition"] = {
            "training": training_route,
            "evaluation": evaluation_route,
            "sampled_radii": sampled_radii,
            "acquisition_distance": transition[4]["distance"],
            "acquisition_components": components,
            "clipped_control": training.data.ctrl.tolist(),
        }
    finally:
        training.close()
        evaluation.close()


def _check_reward_orderings(observed: dict[str, Any]) -> None:
    ranges = np.asarray(
        [[-np.deg2rad(170.0), np.deg2rad(170.0)]] * 2,
        dtype=np.float64,
    )
    action = np.asarray((0.4, -0.2), dtype=np.float64)
    velocity = np.asarray((1.2, -0.8), dtype=np.float64)
    center = np.zeros(2, dtype=np.float64)
    near_lower = ranges[:, 0] + 0.01
    near_upper = ranges[:, 1] - 0.01
    middle_lower = ranges[:, 0] + 0.10

    center_reward = _reward_case(
        previous_distance=0.08,
        current_distance=0.04,
        held_steps=0,
        previous_held_steps=0,
        action=action,
        joint_position=center,
        joint_velocity=velocity,
        endpoint_velocity=0.20,
        joint_ranges=ranges,
    )
    lower_reward = _reward_case(
        previous_distance=0.08,
        current_distance=0.04,
        held_steps=0,
        previous_held_steps=0,
        action=action,
        joint_position=near_lower,
        joint_velocity=velocity,
        endpoint_velocity=0.20,
        joint_ranges=ranges,
    )
    upper_reward = _reward_case(
        previous_distance=0.08,
        current_distance=0.04,
        held_steps=0,
        previous_held_steps=0,
        action=action,
        joint_position=near_upper,
        joint_velocity=velocity,
        endpoint_velocity=0.20,
        joint_ranges=ranges,
    )
    middle_reward = _reward_case(
        previous_distance=0.08,
        current_distance=0.04,
        held_steps=0,
        previous_held_steps=0,
        action=action,
        joint_position=middle_lower,
        joint_velocity=velocity,
        endpoint_velocity=0.20,
        joint_ranges=ranges,
    )
    reference_center = _independent_limit_proximity(center, ranges)
    reference_near = _independent_limit_proximity(near_lower, ranges)
    _require(
        reference_near > reference_center,
        "independent limit reference did not identify near-limit state",
    )
    for label, result in (
        ("lower", lower_reward),
        ("upper", upper_reward),
    ):
        _require(
            result.components["direct_limit_velocity_joint_limit"]
            < center_reward.components["direct_limit_velocity_joint_limit"],
            f"{label} limit proximity was not more penalized than center",
        )
    _require(
        lower_reward.components["direct_limit_velocity_joint_limit"]
        < middle_reward.components["direct_limit_velocity_joint_limit"],
        "limit penalty was not monotonic toward the lower limit",
    )

    outside = _reward_case(
        previous_distance=0.08,
        current_distance=0.04,
        held_steps=0,
        previous_held_steps=0,
        action=action,
        joint_position=center,
        joint_velocity=velocity,
        endpoint_velocity=0.20,
        joint_ranges=ranges,
    )
    first_hold = _reward_case(
        previous_distance=0.04,
        current_distance=0.008,
        held_steps=1,
        previous_held_steps=0,
        action=action,
        joint_position=center,
        joint_velocity=velocity,
        endpoint_velocity=0.20,
        joint_ranges=ranges,
    )
    repeated_hold = _reward_case(
        previous_distance=0.008,
        current_distance=0.008,
        held_steps=2,
        previous_held_steps=1,
        action=action,
        joint_position=center,
        joint_velocity=velocity,
        endpoint_velocity=0.20,
        joint_ranges=ranges,
    )
    expected_outside_weight = _independent_approach_weight(
        0.04, SUCCESS_THRESHOLD
    )
    expected_inside_weight = _independent_approach_weight(
        0.008, SUCCESS_THRESHOLD
    )
    _require(
        expected_inside_weight > expected_outside_weight,
        "independent approach reference did not strengthen near the boundary",
    )
    for result in (outside, first_hold, repeated_hold):
        _require(
            REGULATION_COMPONENTS.union({WEIGHT_COMPONENT}).issubset(
                result.components
            ),
            "repeated post-step reward update omitted a regulation term",
        )
        _require(
            np.isfinite(
                result.components["direct_limit_velocity_joint_limit"]
            )
            and result.components["direct_limit_velocity_joint_limit"] <= 0.0,
            "repeated post-step update returned an invalid joint-limit term",
        )
        _require(
            all(
                np.isfinite(result.components[name])
                and abs(result.components[name]) > 0.0
                for name in NON_LIMIT_REGULATION_COMPONENTS
            ),
            "repeated post-step update contained an inactive velocity/action term",
        )
    _require(
        first_hold.components["direct_limit_velocity_weight"]
        > outside.components["direct_limit_velocity_weight"],
        "approach weighting did not strengthen inside the tolerance boundary",
    )
    _require(
        first_hold.components["direct_limit_velocity_endpoint_velocity"]
        < outside.components["direct_limit_velocity_endpoint_velocity"]
        and first_hold.components["direct_limit_velocity_action_regulation"]
        < outside.components["direct_limit_velocity_action_regulation"],
        "endpoint/action regulation was not stronger near the boundary",
    )

    default_with_inputs = reach_reward(
        0.08,
        0.04,
        SUCCESS_THRESHOLD,
        action,
        held_steps=1,
        previous_held_steps=0,
        joint_velocity=velocity,
        endpoint_velocity=2.0,
    )
    default_without_inputs = reach_reward(
        0.08,
        0.04,
        SUCCESS_THRESHOLD,
        action,
        held_steps=1,
        previous_held_steps=0,
    )
    _require(
        default_with_inputs == default_without_inputs,
        "default reward changed when new inputs were supplied",
    )
    targeted = reach_reward(
        0.03,
        0.03,
        SUCCESS_THRESHOLD,
        action,
        reward_profile=TARGETED_REGULATION_PROFILE,
        joint_velocity=velocity,
        endpoint_velocity=0.20,
    )
    _require(
        any(
            name.startswith("targeted_")
            for name in targeted.components
        ),
        "targeted regulation profile was replaced",
    )

    observed["independent_reward_orderings"] = {
        "limit_reference": {
            "center": reference_center,
            "near_limit": reference_near,
        },
        "observed_limit_penalties": {
            "center": center_reward.components[
                "direct_limit_velocity_joint_limit"
            ],
            "middle": middle_reward.components[
                "direct_limit_velocity_joint_limit"
            ],
            "lower": lower_reward.components[
                "direct_limit_velocity_joint_limit"
            ],
            "upper": upper_reward.components[
                "direct_limit_velocity_joint_limit"
            ],
        },
        "approach_reference": {
            "outside": expected_outside_weight,
            "inside": expected_inside_weight,
        },
        "observed_approach_weights": {
            "outside": outside.components[WEIGHT_COMPONENT],
            "first_hold": first_hold.components[WEIGHT_COMPONENT],
            "repeated_hold": repeated_hold.components[WEIGHT_COMPONENT],
        },
        "observed_repeated_components": {
            "outside": outside.components,
            "first_hold": first_hold.components,
            "repeated_hold": repeated_hold.components,
        },
    }


def _expect_value_error(callable_object, label: str) -> None:
    try:
        callable_object()
    except ValueError:
        return
    raise VerificationFailure(f"{label} was silently accepted")


def _check_transitions_and_resets(observed: dict[str, Any]) -> None:
    env = make_training_env()
    try:
        env.reset(seed=201)
        env._previous_distance = 0.08
        original_distance = env._distance_to_target
        original_endpoint_velocity = env._endpoint_linear_velocity
        distances = iter((0.04, 0.008, 0.008, 0.008))
        env._distance_to_target = lambda: next(distances)
        env._endpoint_linear_velocity = lambda: 0.10
        try:
            transitions = [
                env.step(np.asarray((0.2, -0.1), dtype=np.float64))
                for _ in range(4)
            ]
        finally:
            env._distance_to_target = original_distance
            env._endpoint_linear_velocity = original_endpoint_velocity
        _require(
            [item[4]["held_steps"] for item in transitions] == [0, 1, 2, 3],
            "repeated outside/acquisition and hold updates lost counter state",
        )
        _require(
            all(
                REGULATION_COMPONENTS.union({WEIGHT_COMPONENT}).issubset(
                    item[4]["reward_components"]
                )
                for item in transitions
            ),
            "route transitions did not attribute all repeated shaping terms",
        )

        env.reset(seed=202)
        original_distance = env._distance_to_target
        original_endpoint_velocity = env._endpoint_linear_velocity
        env._distance_to_target = lambda: 0.008
        env._endpoint_linear_velocity = lambda: 0.0
        try:
            hold_transitions = [
                env.step(np.zeros(2, dtype=np.float64))
                for _ in range(HOLD_STEPS_REQUIRED)
            ]
        finally:
            env._distance_to_target = original_distance
            env._endpoint_linear_velocity = original_endpoint_velocity
        _require(
            not any(item[2] for item in hold_transitions[:-1])
            and hold_transitions[-1][2]
            and hold_transitions[-1][4]["held_steps"] == HOLD_STEPS_REQUIRED,
            "complete hold did not terminate after exactly 100 updates",
        )
        _require(
            all(
                REGULATION_COMPONENTS.union({WEIGHT_COMPONENT}).issubset(
                    item[4]["reward_components"]
                )
                for item in hold_transitions
            ),
            "complete hold did not retain repeated reward attribution",
        )

        env.reset(seed=203)
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
            and interruption[4]["reward_components"][
                "direct_limit_velocity_endpoint_velocity"
            ]
            <= 0.0,
            "hold interruption did not reset the counter",
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
            and not env._outside_after_hold,
            "re-entry after interruption did not restart hold state",
        )

        reset_records = []
        for seed in (301, 302, 303):
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
                f"repeated reset {seed} did not restore state",
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

        ranges = env.model.jnt_range[:2].copy()
        valid = dict(
            action=np.zeros(2),
            joint_position=np.zeros(2),
            joint_velocity=np.zeros(2),
            endpoint_velocity=0.0,
            joint_ranges=ranges,
        )
        _expect_value_error(
            lambda: _reward_case(
                previous_distance=0.02,
                current_distance=0.02,
                held_steps=0,
                previous_held_steps=0,
                **{**valid, "joint_ranges": None},
            ),
            "missing compiled joint ranges",
        )
        _expect_value_error(
            lambda: _reward_case(
                previous_distance=0.02,
                current_distance=0.02,
                held_steps=0,
                previous_held_steps=0,
                **{**valid, "joint_position": np.zeros(1)},
            ),
            "malformed joint position",
        )
        observed["transitions_and_resets"] = {
            "repeated_held_steps": [
                item[4]["held_steps"] for item in transitions
            ],
            "complete_hold": {
                "steps": len(hold_transitions),
                "final_held_steps": hold_transitions[-1][4]["held_steps"],
                "terminated": hold_transitions[-1][2],
            },
            "interruption": {
                "held_steps": interruption[4]["held_steps"],
                "regulation_components": interruption[4]["reward_components"],
            },
            "reentry": {
                "held_steps": reentry[4]["held_steps"],
                "outside_after_hold": env._outside_after_hold,
            },
            "resets": reset_records,
            "validation": "missing ranges and malformed position rejected",
        }
    finally:
        env.close()


def run_checks() -> dict[str, Any]:
    observed: dict[str, Any] = {}
    _check_routes_and_direct_control(observed)
    _check_reward_orderings(observed)
    _check_transitions_and_resets(observed)
    return {
        "status": "passed",
        "observed_vs_expected": observed,
        "expected": EXPECTED,
        "checked_scope": [
            "direct-control training route and full-radius reset sampling",
            "unchanged direct/default official evaluation route",
            "outside-boundary acquisition and repeated in-hold attribution",
            "independent joint-limit proximity and approach-weight orderings",
            "both lower and upper joint-limit monotonicity",
            "complete hold, interruption, re-entry, and repeated reset semantics",
            "explicit rejection of missing or malformed shaping inputs",
            "preservation of default and targeted reward profile dispatch",
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
