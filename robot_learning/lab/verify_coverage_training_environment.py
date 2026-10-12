"""Executable checks for the coverage-focused training target distribution.

This module is intended for the ``python_module`` instrument.  It does not
train a policy or evaluate task performance; it checks the production
environment construction and the reset-time target consequence of the recipe.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from robot_learning.scenario.environment import make_evaluation_env
from robot_learning.training.environment import make_training_env

OFFICIAL_TARGET_RADIUS_RANGE = (0.06, 0.20)
OLD_TRAINING_LOWER_BOUND = 0.14
RESET_COUNT = 64


def _target_radius(env: Any) -> float:
    target_xy = np.asarray(env.data.mocap_pos[0], dtype=np.float64)[:2]
    return float(np.linalg.norm(target_xy))


def _write_artifact(output: str, payload: dict[str, Any]) -> None:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _compatibility_check(output: str) -> int:
    """Exercise the changed training construction with controlled resets."""
    observed: dict[str, Any] = {}
    failures: list[str] = []
    try:
        env = make_training_env()
        configured = tuple(float(value) for value in env.target_radius_range)
        observed["configured_training_range"] = list(configured)

        if configured != OFFICIAL_TARGET_RADIUS_RANGE:
            failures.append(
                "make_training_env did not construct the complete official range"
            )

        radii = []
        for seed in (1729, 2718, 31415):
            env.reset(seed=seed)
            radii.append(_target_radius(env))
        observed["seeded_reset_radii"] = radii
        lower, upper = OFFICIAL_TARGET_RADIUS_RANGE
        if not all(lower <= radius <= upper for radius in radii):
            failures.append("a controlled reset sampled outside the official range")

        env.reset(seed=1729)
        transition_radius = _target_radius(env)
        transition_lengths = []
        zero_action = np.zeros(env.action_space.shape, dtype=env.action_space.dtype)
        for _ in range(2):
            transition_lengths.append(len(env.step(zero_action)))
        observed["transition_output_lengths"] = transition_lengths
        observed["target_held_during_transitions"] = (
            _target_radius(env) == transition_radius
        )
        if transition_lengths != [5, 5] or not observed["target_held_during_transitions"]:
            failures.append("controlled training transitions did not preserve the reset target")
    except Exception as exc:  # pragma: no cover - exercised by the instrument
        observed["error"] = f"{type(exc).__name__}: {exc}"
        failures.append("the production training environment path could not run")

    artifact = {
        "status": "passed" if not failures else "failed",
        "observed": observed,
        "expected": {
            "configured_training_range": list(OFFICIAL_TARGET_RADIUS_RANGE),
            "seeded_reset_radii_within": list(OFFICIAL_TARGET_RADIUS_RANGE),
        },
        "checked_scope": [
            "make_training_env construction",
            "three controlled reset-time target samples",
            "two controlled training transitions after reset",
        ],
        "unchecked_scope": [
            "policy learning and PPO behavior",
            "official evaluation performance",
        ],
        "failures": failures,
    }
    _write_artifact(output, artifact)
    return 0 if not failures else 1


def _behavioral_check(output: str) -> int:
    """Check bounds, repeated reset sampling, and evaluation isolation."""
    observed: dict[str, Any] = {}
    failures: list[str] = []
    try:
        training_env = make_training_env()
        configured = tuple(float(value) for value in training_env.target_radius_range)
        observed["configured_training_range"] = list(configured)

        if configured != OFFICIAL_TARGET_RADIUS_RANGE:
            failures.append(
                "configured training range is not exactly the official 0.06-0.20 m range"
            )
        if configured[0] == OLD_TRAINING_LOWER_BOUND:
            failures.append("the old 0.14 m training lower bound is still present")
        if configured[0] != OFFICIAL_TARGET_RADIUS_RANGE[0]:
            failures.append("the training lower bound was not changed to 0.06 m")
        if configured[1] != OFFICIAL_TARGET_RADIUS_RANGE[1]:
            failures.append("the training upper bound was changed unexpectedly")

        seeded_env = make_training_env()
        seeded_env.reset(seed=20261012)
        first_sequence = [_target_radius(seeded_env)]
        for _ in range(RESET_COUNT - 1):
            seeded_env.reset()
            first_sequence.append(_target_radius(seeded_env))

        repeated_env = make_training_env()
        repeated_env.reset(seed=20261012)
        second_sequence = [_target_radius(repeated_env)]
        for _ in range(RESET_COUNT - 1):
            repeated_env.reset()
            second_sequence.append(_target_radius(repeated_env))

        observed["reset_count"] = RESET_COUNT
        observed["sampled_radius_min"] = min(first_sequence)
        observed["sampled_radius_max"] = max(first_sequence)
        observed["sampled_radius_below_old_lower_bound"] = sum(
            radius < OLD_TRAINING_LOWER_BOUND for radius in first_sequence
        )
        observed["seed_replay_matches"] = bool(
            np.allclose(first_sequence, second_sequence, rtol=0.0, atol=1e-12)
        )

        lower, upper = OFFICIAL_TARGET_RADIUS_RANGE
        if not all(lower <= radius <= upper for radius in first_sequence):
            failures.append("a repeated reset sampled a target outside the official range")
        if not observed["seed_replay_matches"]:
            failures.append("identical controlled reset seeds did not replay the same samples")
        if observed["sampled_radius_below_old_lower_bound"] == 0:
            failures.append(
                "the controlled repeated-reset sample never demonstrated the new inner range"
            )

        training_env.reset(seed=20261012)
        transition_radius = _target_radius(training_env)
        transition_lengths = []
        zero_action = np.zeros(
            training_env.action_space.shape, dtype=training_env.action_space.dtype
        )
        for _ in range(2):
            transition_lengths.append(len(training_env.step(zero_action)))
        observed["transition_output_lengths"] = transition_lengths
        observed["target_held_during_transitions"] = (
            _target_radius(training_env) == transition_radius
        )
        if transition_lengths != [5, 5] or not observed["target_held_during_transitions"]:
            failures.append("training transitions did not preserve the reset target")

        evaluation_env = make_evaluation_env()
        evaluation_range = tuple(
            float(value) for value in evaluation_env.target_radius_range
        )
        observed["evaluation_range"] = list(evaluation_range)
        if evaluation_range != OFFICIAL_TARGET_RADIUS_RANGE:
            failures.append("the official evaluation range is not unchanged")
    except Exception as exc:  # pragma: no cover - exercised by the instrument
        observed["error"] = f"{type(exc).__name__}: {exc}"
        failures.append("the production environment paths could not run")

    artifact = {
        "status": "passed" if not failures else "failed",
        "observed": observed,
        "expected": {
            "training_range": list(OFFICIAL_TARGET_RADIUS_RANGE),
            "old_training_lower_bound": OLD_TRAINING_LOWER_BOUND,
            "reset_count": RESET_COUNT,
            "every_sample_within": list(OFFICIAL_TARGET_RADIUS_RANGE),
            "at_least_one_sample_below_old_lower_bound": True,
            "same_seed_replay": True,
            "transition_output_lengths": [5, 5],
            "target_held_during_transitions": True,
            "evaluation_range": list(OFFICIAL_TARGET_RADIUS_RANGE),
        },
        "checked_scope": [
            "exact training lower and upper bounds",
            "explicit absence of the old 0.14 m lower bound",
            "64 repeated reset-time samples from the production training constructor",
            "controlled-seed replay of the repeated sampling sequence",
            "two controlled transitions after reset without target resampling",
            "evaluation constructor range isolation",
        ],
        "unchecked_scope": [
            "angle distribution and branch representation",
            "observation and action interfaces",
            "PPO parameters and training outcomes",
            "official success measurement",
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
        help="run the small artifact-independent production-path check",
    )
    args = parser.parse_args()
    if args.compatibility:
        return _compatibility_check(args.output)
    return _behavioral_check(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
