"""Artifact-independent verification for the full training target distribution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from contracts.task_spec import TARGET_RADIUS_RANGE
from robot_learning.scenario.environment import make_evaluation_env
from robot_learning.training.environment import make_training_env

SAMPLE_COUNT = 32


def _target_radius(env: Any) -> float:
    target = np.asarray(env.data.mocap_pos[0], dtype=np.float64)
    return float(np.linalg.norm(target[:2]))


def _range_as_floats(radius_range: tuple[float, float]) -> list[float]:
    return [float(radius_range[0]), float(radius_range[1])]


def _write_report(artifact: str, report: dict[str, Any]) -> None:
    Path(artifact).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _verify_full_distribution(artifact: str) -> None:
    training_env = make_training_env()
    evaluation_env = make_evaluation_env()
    try:
        expected_range = tuple(float(value) for value in TARGET_RADIUS_RANGE)
        training_range = tuple(float(value) for value in training_env.target_radius_range)
        evaluation_range = tuple(
            float(value) for value in evaluation_env.target_radius_range
        )

        assert training_range == expected_range, (
            "training target distribution must be the full official range: "
            f"{training_range!r} != {expected_range!r}"
        )
        assert evaluation_range == expected_range, (
            "evaluation target distribution changed: "
            f"{evaluation_range!r} != {expected_range!r}"
        )

        sampled_radii = []
        for seed in range(SAMPLE_COUNT):
            training_env.reset(seed=seed)
            sampled_radii.append(_target_radius(training_env))

        assert all(
            expected_range[0] <= radius <= expected_range[1]
            for radius in sampled_radii
        ), "a reset target fell outside the configured training range"

        _write_report(
            artifact,
            {
                "check": "full_training_target_radius_distribution",
                "training_target_radius_range": _range_as_floats(training_range),
                "evaluation_target_radius_range": _range_as_floats(evaluation_range),
                "sample_count": SAMPLE_COUNT,
                "sample_seed_range": [0, SAMPLE_COUNT - 1],
                "sampled_radius_min": min(sampled_radii),
                "sampled_radius_max": max(sampled_radii),
                "all_samples_within_training_range": True,
            },
        )
    finally:
        training_env.close()
        evaluation_env.close()


def _verify_production_path_compatibility(artifact: str) -> None:
    """Exercise the builders and Gym reset/step path without a model artifact."""
    training_env = make_training_env()
    evaluation_env = make_evaluation_env()
    try:
        expected_range = tuple(float(value) for value in TARGET_RADIUS_RANGE)
        assert tuple(training_env.target_radius_range) == expected_range
        assert tuple(evaluation_env.target_radius_range) == expected_range

        reset_observation, reset_info = training_env.reset(seed=2026)
        assert training_env.observation_space.contains(reset_observation)
        assert reset_info == {}
        step_result = training_env.step(
            np.zeros(training_env.action_space.shape, dtype=np.float32)
        )
        assert len(step_result) == 5
        assert training_env.observation_space.contains(step_result[0])

        evaluation_observation, evaluation_info = evaluation_env.reset(seed=2026)
        assert evaluation_env.observation_space.contains(evaluation_observation)
        assert evaluation_info == {}

        _write_report(
            artifact,
            {
                "check": "production_path_compatibility",
                "artifact_independent": True,
                "training_target_radius_range": _range_as_floats(
                    tuple(training_env.target_radius_range)
                ),
                "evaluation_target_radius_range": _range_as_floats(
                    tuple(evaluation_env.target_radius_range)
                ),
                "training_reset_and_step_api": "compatible",
                "evaluation_reset_api": "compatible",
            },
        )
    finally:
        training_env.close()
        evaluation_env.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True)
    parser.add_argument(
        "--mode",
        choices=("full", "compatibility"),
        default="full",
    )
    args = parser.parse_args()

    if args.mode == "compatibility":
        _verify_production_path_compatibility(args.artifact)
    else:
        _verify_full_distribution(args.artifact)


if __name__ == "__main__":
    main()
