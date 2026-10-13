"""Executable check for the branch-and-geometry training route.

This check exercises production resets rather than inspecting saved artifacts.
It independently recomputes the two legal IK branches from the compiled model
limits so that the focused-target assertion does not merely repeat the route's
acceptance predicate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from contracts.task_spec import TARGET_RADIUS_RANGE
from robot_learning.scenario.environment import (
    TwoJointArmReachEnv,
    make_evaluation_env,
)
from robot_learning.training.environment import (
    FOCUSED_BEARING_DEGREES,
    FOCUSED_ROUTE_PROBABILITY,
    TRAINING_TARGET_RADIUS_RANGE,
    make_training_env,
)

EXPECTED_RANGE = (0.06, 0.20)
RESET_SEEDS = tuple(range(64))
REPEAT_SEEDS = (0, 17, 63)


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _independent_ik_classification(model, target: np.ndarray) -> str:
    """Return branch legality using the compiled joint limits."""
    x, y = float(target[0]), float(target[1])
    radius = float(np.hypot(x, y))
    bearing = float(np.arctan2(y, x))
    cosine = (
        radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    legal: dict[str, bool] = {}
    shoulder_lower, shoulder_upper = np.asarray(
        model.jnt_range[0], dtype=np.float64
    )
    elbow_lower, elbow_upper = np.asarray(model.jnt_range[1], dtype=np.float64)

    for name, elbow_sign in (("open", 1.0), ("folded", -1.0)):
        branch_legal = False
        if abs(cosine) <= 1.0 + 1e-12:
            elbow = elbow_sign * float(np.arccos(np.clip(cosine, -1.0, 1.0)))
            shoulder = bearing - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
            shoulder = _wrap_to_pi(float(shoulder))
            branch_legal = (
                shoulder_lower - 1e-12 <= shoulder <= shoulder_upper + 1e-12
                and elbow_lower - 1e-12 <= elbow <= elbow_upper + 1e-12
            )
        legal[name] = branch_legal

    if legal["open"] and legal["folded"]:
        return "both"
    if legal["open"]:
        return "open_only"
    if legal["folded"]:
        return "folded_only"
    return "none"


def _radius_from_target(target: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(target, dtype=np.float64)[:2]))


def _bearing_from_target(target: np.ndarray) -> float:
    return float(np.degrees(np.arctan2(target[1], target[0])))


def _write_artifact(
    output: Path,
    *,
    check_name: str,
    observed: dict[str, object],
    expected: dict[str, object],
    checked_scope: list[str],
    unchecked_scope: list[str],
    failures: list[str],
) -> None:
    artifact = {
        "check": check_name,
        "status": "failed" if failures else "passed",
        "observed": observed,
        "expected": expected,
        "checked_scope": checked_scope,
        "unchecked_scope": unchecked_scope,
    }
    output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    if failures:
        raise AssertionError("; ".join(failures))


def run_compatibility_check(output: Path) -> None:
    """Exercise the changed reset and step path with controlled inputs."""
    observed: dict[str, object] = {
        "training_environment_type": None,
        "reset_observation_shape": None,
        "step_count": 0,
        "repeat_target_equal": None,
        "evaluation_reset_observation_shape": None,
    }
    failures: list[str] = []
    training_env = None
    evaluation_env = None
    try:
        training_env = make_training_env()
        observed["training_environment_type"] = type(training_env).__name__
        first_observation, _ = training_env.reset(seed=20261013)
        first_target = np.array(training_env.data.mocap_pos[0], copy=True)
        observed["reset_observation_shape"] = list(first_observation.shape)
        if first_observation.shape != training_env.observation_space.shape:
            failures.append("training reset observation shape does not match its space")

        for _ in range(3):
            result = training_env.step(
                np.zeros(training_env.action_space.shape, dtype=np.float32)
            )
            if len(result) != 5:
                failures.append("training step did not return the Gymnasium 5-tuple")
                break
            observed["step_count"] = int(observed["step_count"]) + 1

        training_env.reset(seed=20261013)
        repeated_target = np.array(training_env.data.mocap_pos[0], copy=True)
        repeat_equal = bool(np.array_equal(first_target, repeated_target))
        observed["repeat_target_equal"] = repeat_equal
        if not repeat_equal:
            failures.append("same Gymnasium seed did not reproduce the target")

        evaluation_env = make_evaluation_env()
        evaluation_observation, _ = evaluation_env.reset(seed=20261013)
        observed["evaluation_reset_observation_shape"] = list(
            evaluation_observation.shape
        )
    except Exception as error:
        failures.append(f"production compatibility path raised {error!r}")
    finally:
        if training_env is not None:
            training_env.close()
        if evaluation_env is not None:
            evaluation_env.close()

    _write_artifact(
        output,
        check_name="branch_geometry_training_compatibility",
        observed=observed,
        expected={
            "reset_returns_space_shaped_observation": True,
            "step_returns_five_values": True,
            "same_seed_reproduces_target": True,
            "evaluation_reset_succeeds": True,
        },
        checked_scope=[
            "the changed training environment construction",
            "the inherited production reset path",
            "three controlled production steps",
            "same-seed target reproducibility",
            "the production evaluation environment reset path",
        ],
        unchecked_scope=[
            "full seeded route coverage and IK classification",
            "training convergence or policy performance",
            "official evaluation outcomes",
            "long-horizon dynamics and termination behavior",
        ],
        failures=failures,
    )


def run_behavioral_check(output: Path) -> None:
    """Check route coverage, geometry, compiled-limit legality, and evaluation."""
    observed: dict[str, object] = {
        "training_constant": list(TRAINING_TARGET_RADIUS_RANGE),
        "focused_bearing_degrees": list(FOCUSED_BEARING_DEGREES),
        "focused_route_probability": FOCUSED_ROUTE_PROBABILITY,
        "sample_count": 0,
        "route_counts": {"uniform": 0, "focused": 0},
        "sampled_radii": [],
        "focused_radii": [],
        "uniform_bearings_degrees": [],
        "focused_classifications": [],
        "evaluation_range": list(TARGET_RADIUS_RANGE),
        "evaluation_environment_type": None,
        "evaluation_space_shapes": None,
    }
    failures: list[str] = []
    expected = {
        "training_range": list(EXPECTED_RANGE),
        "official_evaluation_range": list(EXPECTED_RANGE),
        "focused_bearing_degrees": list(FOCUSED_BEARING_DEGREES),
        "focused_classification": "folded_only",
        "mixture_probability": 0.5,
        "sample_bounds": {
            "minimum_inclusive": EXPECTED_RANGE[0],
            "maximum_inclusive": EXPECTED_RANGE[1],
        },
    }
    env = None
    evaluation_env = None
    targets_by_seed: dict[int, tuple[np.ndarray, str]] = {}
    try:
        if tuple(TRAINING_TARGET_RADIUS_RANGE) != EXPECTED_RANGE:
            failures.append("training radius constant changed from the official range")
        if tuple(TARGET_RADIUS_RANGE) != EXPECTED_RANGE:
            failures.append("official evaluation range changed")
        if FOCUSED_ROUTE_PROBABILITY != 0.5:
            failures.append("focused route is not the documented 50/50 mixture")

        env = make_training_env()
        for seed in RESET_SEEDS:
            env.reset(seed=seed)
            target = np.array(env.data.mocap_pos[0], dtype=np.float64, copy=True)
            route = str(getattr(env, "_last_target_route", "missing"))
            radius = _radius_from_target(target)
            bearing = _bearing_from_target(target)
            targets_by_seed[seed] = (target, route)
            observed["sample_count"] = int(observed["sample_count"]) + 1
            observed["sampled_radii"].append(radius)
            if route in observed["route_counts"]:
                observed["route_counts"][route] += 1
            else:
                failures.append(f"unknown reset route {route!r}")

            if not EXPECTED_RANGE[0] <= radius <= EXPECTED_RANGE[1]:
                failures.append(f"seed {seed} sampled radius {radius} outside the range")
            if route == "focused":
                classification = _independent_ik_classification(env.model, target)
                observed["focused_radii"].append(radius)
                observed["focused_classifications"].append(classification)
                if not (
                    FOCUSED_BEARING_DEGREES[0] - 1e-9
                    <= bearing
                    <= FOCUSED_BEARING_DEGREES[1] + 1e-9
                ):
                    failures.append(
                        f"focused seed {seed} bearing {bearing} outside the focused sector"
                    )
                if classification != "folded_only":
                    failures.append(
                        f"focused seed {seed} has compiled IK classification "
                        f"{classification!r}"
                    )
            elif route == "uniform":
                observed["uniform_bearings_degrees"].append(bearing)

        for seed in REPEAT_SEEDS:
            env.reset(seed=seed)
            repeated_target = np.array(env.data.mocap_pos[0], copy=True)
            prior_target, prior_route = targets_by_seed[seed]
            if not np.array_equal(repeated_target, prior_target):
                failures.append(f"seed {seed} did not reproduce its target")
            if str(getattr(env, "_last_target_route", "missing")) != prior_route:
                failures.append(f"seed {seed} did not reproduce its route")

        route_counts = observed["route_counts"]
        if route_counts["uniform"] == 0:
            failures.append("no uniform full-geometry reset route was observed")
        if route_counts["focused"] == 0:
            failures.append("no focused reset route was observed")
        if not any(
            bearing < FOCUSED_BEARING_DEGREES[0]
            or bearing > FOCUSED_BEARING_DEGREES[1]
            for bearing in observed["uniform_bearings_degrees"]
        ):
            failures.append(
                "uniform route did not produce a bearing outside the focus sector"
            )
        focused_radii = observed["focused_radii"]
        if focused_radii and (
            min(focused_radii) >= 0.10 or max(focused_radii) <= 0.16
        ):
            failures.append("focused route did not span the full radius range")
        if any(
            classification != "folded_only"
            for classification in observed["focused_classifications"]
        ):
            failures.append("a focused target was not independently folded_only")

        evaluation_env = make_evaluation_env()
        observed["evaluation_environment_type"] = type(evaluation_env).__name__
        observed["evaluation_space_shapes"] = {
            "observation": list(evaluation_env.observation_space.shape),
            "action": list(evaluation_env.action_space.shape),
        }
        if type(evaluation_env) is not TwoJointArmReachEnv:
            failures.append(
                "evaluation construction no longer returns the scenario environment"
            )
        if tuple(evaluation_env.target_radius_range) != EXPECTED_RANGE:
            failures.append("evaluation environment does not use the official radius range")
        if evaluation_env.observation_space.shape != (11,):
            failures.append("evaluation observation construction changed")
        if evaluation_env.action_space.shape != (2,):
            failures.append("evaluation action construction changed")
    except Exception as error:
        failures.append(f"production behavioral path raised {error!r}")
    finally:
        if env is not None:
            env.close()
        if evaluation_env is not None:
            evaluation_env.close()

    _write_artifact(
        output,
        check_name="branch_geometry_training",
        observed=observed,
        expected=expected,
        checked_scope=[
            "repeated seeded resets through make_training_env",
            "occurrence of uniform and focused reset routes",
            "radius bounds for every sampled target",
            "focused bearing-sector membership",
            "independent folded_only IK classification using compiled joint limits",
            "focused-route radius span",
            "same-seed target and route reproducibility",
            "official evaluation range and unchanged scenario environment construction",
        ],
        unchecked_scope=[
            "training convergence or policy performance",
            "official evaluation success outcomes",
            "the empirical target distribution beyond this finite reset panel",
            "reward, observations, task mechanics, and long-horizon dynamics",
            "whether the focused route improves the scientific objective",
        ],
        failures=failures,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("behavioral", "compatibility"), default="behavioral"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "compatibility":
        run_compatibility_check(args.output)
    else:
        run_behavioral_check(args.output)


if __name__ == "__main__":
    main()
