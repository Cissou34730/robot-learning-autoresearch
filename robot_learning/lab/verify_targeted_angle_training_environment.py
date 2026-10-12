"""Executable checks for the targeted-exposure training environment.

The checks use the production training and evaluation constructors. They do
not train a policy or measure task performance; they characterize reset
sampling, interface preservation, transition target persistence, and
training/evaluation construction isolation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from robot_learning.scenario.environment import (
    TwoJointArmReachEnv,
    make_evaluation_env,
)
from robot_learning.training.environment import (
    TRAINING_TARGET_RADIUS_RANGE,
    make_training_env,
)

OFFICIAL_TARGET_RADIUS_RANGE = (0.06, 0.20)
RESET_COUNT = 1024
UNION_FRACTION_EXPECTATION = 0.6875
UNION_FRACTION_BOUNDS = (0.625, 0.75)


def _target_position(env: Any) -> np.ndarray:
    return np.asarray(env.data.mocap_pos[0], dtype=np.float64).copy()


def _target_radius_and_angle(env: Any) -> tuple[float, float]:
    target_xy = _target_position(env)[:2]
    return float(np.linalg.norm(target_xy)), float(
        np.degrees(np.arctan2(target_xy[1], target_xy[0]))
    )


def _in_observed_failure_union(angle_degrees: float) -> bool:
    return (
        -180.0 <= angle_degrees < -90.0
        or -45.0 <= angle_degrees < 0.0
    )


def _write_artifact(output: str, payload: dict[str, Any]) -> None:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _run_check(output: str, mode: str) -> int:
    observed: dict[str, Any] = {}
    failures: list[str] = []
    try:
        training_env = make_training_env()
        configured_range = tuple(
            float(value) for value in training_env.target_radius_range
        )
        observed["configured_training_range"] = list(configured_range)
        if configured_range != OFFICIAL_TARGET_RADIUS_RANGE:
            failures.append(
                "the training constructor did not preserve the official radius range"
            )
        if tuple(TRAINING_TARGET_RADIUS_RANGE) != OFFICIAL_TARGET_RADIUS_RANGE:
            failures.append("the training radius constant drifted from the official range")

        first_sequence: list[tuple[float, float, np.ndarray]] = []
        training_env.reset(seed=20261012)
        for _ in range(RESET_COUNT):
            radius, angle = _target_radius_and_angle(training_env)
            first_sequence.append((radius, angle, _target_position(training_env)))
            training_env.reset()

        repeated_env = make_training_env()
        repeated_sequence: list[tuple[float, float, np.ndarray]] = []
        repeated_env.reset(seed=20261012)
        for _ in range(RESET_COUNT):
            radius, angle = _target_radius_and_angle(repeated_env)
            repeated_sequence.append(
                (radius, angle, _target_position(repeated_env))
            )
            repeated_env.reset()

        lower, upper = OFFICIAL_TARGET_RADIUS_RANGE
        radii = [sample[0] for sample in first_sequence]
        angles = [sample[1] for sample in first_sequence]
        union_hits = sum(
            _in_observed_failure_union(angle) for angle in angles
        )
        union_fraction = union_hits / RESET_COUNT
        observed["reset_count"] = RESET_COUNT
        observed["sampled_radius_min"] = min(radii)
        observed["sampled_radius_max"] = max(radii)
        observed["sampled_angle_min_degrees"] = min(angles)
        observed["sampled_angle_max_degrees"] = max(angles)
        observed["observed_union_hits"] = union_hits
        observed["observed_union_fraction"] = union_fraction
        observed["expected_union_fraction"] = UNION_FRACTION_EXPECTATION
        observed["union_fraction_bounds"] = list(UNION_FRACTION_BOUNDS)
        observed["seed_replay_matches"] = all(
            first[0] == second[0]
            and first[1] == second[1]
            and np.array_equal(first[2], second[2])
            for first, second in zip(first_sequence, repeated_sequence)
        )

        if not all(lower <= radius <= upper for radius in radii):
            failures.append("a reset sampled outside the official radius range")
        if not all(-180.0 <= angle < 180.0 for angle in angles):
            failures.append("a reset sampled an angle outside [-180, 180) degrees")
        if not UNION_FRACTION_BOUNDS[0] <= union_fraction <= UNION_FRACTION_BOUNDS[1]:
            failures.append(
                "the observed failure-sector fraction is outside the enriched bounds"
            )
        if not observed["seed_replay_matches"]:
            failures.append("identical seeded reset sequences did not replay")

        observation, _ = training_env.reset(seed=2718)
        observed["observation_shape"] = list(observation.shape)
        observed["observation_space_shape"] = list(training_env.observation_space.shape)
        observed["action_space_shape"] = list(training_env.action_space.shape)
        observed["action_space_bounds"] = [
            float(np.min(training_env.action_space.low)),
            float(np.max(training_env.action_space.high)),
        ]
        if observation.shape != (11,):
            failures.append("the training reset observation is not 11 values")
        if training_env.observation_space.shape != (11,):
            failures.append("the training observation space is not 11 values")
        if training_env.action_space.shape != (2,):
            failures.append("the training action space is not a two-vector")
        if not (
            np.array_equal(training_env.action_space.low, [-1.0, -1.0])
            and np.array_equal(training_env.action_space.high, [1.0, 1.0])
        ):
            failures.append("the training action bounds are not [-1, 1] for both actions")

        target_before_steps = _target_position(training_env)
        controlled_action = np.asarray(
            [0.25, -0.4], dtype=training_env.action_space.dtype
        )
        zero_action = np.zeros(
            training_env.action_space.shape,
            dtype=training_env.action_space.dtype,
        )
        transition_lengths = []
        next_observation, _, _, _, _ = training_env.step(controlled_action)
        transition_lengths.append(len(next_observation))
        controlled_action_applied = np.allclose(
            training_env.data.ctrl,
            controlled_action,
            rtol=0.0,
            atol=0.0,
        )
        for _ in range(1):
            next_observation, _, _, _, _ = training_env.step(zero_action)
            transition_lengths.append(len(next_observation))
        target_after_steps = _target_position(training_env)
        observed["transition_output_lengths"] = transition_lengths
        observed["controlled_action_applied"] = controlled_action_applied
        observed["target_held_during_transitions"] = bool(
            np.array_equal(target_before_steps, target_after_steps)
        )
        if transition_lengths != [11, 11]:
            failures.append("a training transition returned a non-11-value observation")
        if not observed["controlled_action_applied"]:
            failures.append("the controlled action mapping did not reach data.ctrl")
        if not observed["target_held_during_transitions"]:
            failures.append("the target changed during controlled transitions")

        evaluation_env = make_evaluation_env()
        evaluation_range = tuple(
            float(value) for value in evaluation_env.target_radius_range
        )
        observed["evaluation_range"] = list(evaluation_range)
        observed["evaluation_is_shared_scenario_type"] = type(
            evaluation_env
        ) is TwoJointArmReachEnv
        if evaluation_range != OFFICIAL_TARGET_RADIUS_RANGE:
            failures.append("the evaluation constructor range was changed")
        if not observed["evaluation_is_shared_scenario_type"]:
            failures.append("the evaluation constructor no longer uses the shared environment")
    except Exception as exc:  # pragma: no cover - exercised by the instrument
        observed["error"] = f"{type(exc).__name__}: {exc}"
        failures.append("the production training/evaluation paths could not run")

    artifact = {
        "status": "passed" if not failures else "failed",
        "mode": mode,
        "observed": observed,
        "expected": {
            "training_radius_range": list(OFFICIAL_TARGET_RADIUS_RANGE),
            "angle_range_degrees": [-180.0, 180.0],
            "reset_count": RESET_COUNT,
            "union_fraction_expectation": UNION_FRACTION_EXPECTATION,
            "union_fraction_bounds": list(UNION_FRACTION_BOUNDS),
            "same_seed_replay": True,
            "observation_shape": [11],
            "action_shape": [2],
            "action_bounds": [-1.0, 1.0],
            "controlled_action_applied": True,
            "transition_observation_lengths": [11, 11],
            "target_held_during_transitions": True,
            "evaluation_range": list(OFFICIAL_TARGET_RADIUS_RANGE),
        },
        "checked_scope": [
            "production targeted training constructor and exact radius range",
            "1024 deterministic reset samples and full angular bounds",
            "enriched observed-failure-sector fraction",
            "same-seed reset sequence replay",
            "11-value observation and two-action interface",
            "two controlled transitions with target persistence",
            "shared evaluation constructor and official evaluation range isolation",
        ],
        "unchecked_scope": [
            "radius/angle statistical independence beyond the controlled sampler path",
            "policy learning, PPO/runtime behavior, and episode performance",
            "official evaluation outcomes and continuous-hold interpretation",
        ],
        "failures": failures,
    }
    _write_artifact(output, artifact)
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, help="JSON artifact path")
    parser.add_argument(
        "--compatibility",
        action="store_true",
        help="run the production-path compatibility check",
    )
    args = parser.parse_args()
    return _run_check(
        args.output,
        "compatibility" if args.compatibility else "behavioral",
    )


if __name__ == "__main__":
    raise SystemExit(main())
