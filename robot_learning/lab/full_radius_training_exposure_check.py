"""Executable check for the full-radius training exposure recipe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from contracts.task_spec import TARGET_RADIUS_RANGE
from robot_learning.training.environment import (
    TRAINING_TARGET_RADIUS_RANGE,
    make_training_env,
)

EXPECTED_RANGE = (0.06, 0.20)
RESET_SEEDS = tuple(range(32))


def _radius_from_target(target: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(target, dtype=np.float64)[:2]))


def run_check(output: Path) -> None:
    observed: dict[str, object] = {
        "training_constant": list(TRAINING_TARGET_RADIUS_RANGE),
        "evaluation_range": list(TARGET_RADIUS_RANGE),
        "environment_range": None,
        "sample_count": 0,
        "sampled_radii": [],
    }
    failures: list[str] = []
    expected = {
        "training_constant": list(EXPECTED_RANGE),
        "environment_range": list(EXPECTED_RANGE),
        "evaluation_range": list(EXPECTED_RANGE),
        "sample_bounds": {
            "minimum_inclusive": EXPECTED_RANGE[0],
            "maximum_inclusive": EXPECTED_RANGE[1],
        },
    }

    if tuple(TRAINING_TARGET_RADIUS_RANGE) != EXPECTED_RANGE:
        failures.append("training constant does not equal the expected full-radius range")
    if tuple(TARGET_RADIUS_RANGE) != EXPECTED_RANGE:
        failures.append("official evaluation range changed from the scenario contract")

    env = make_training_env()
    try:
        configured_range = tuple(env.target_radius_range)
        observed["environment_range"] = list(configured_range)
        if configured_range != EXPECTED_RANGE:
            failures.append("training environment is not configured with the expected range")

        sampled_radii: list[float] = []
        for seed in RESET_SEEDS:
            env.reset(seed=seed)
            radius = _radius_from_target(env.data.mocap_pos[0])
            sampled_radii.append(radius)
            if not EXPECTED_RANGE[0] <= radius <= EXPECTED_RANGE[1]:
                failures.append(
                    f"seeded reset {seed} sampled radius {radius} outside the expected range"
                )
        observed["sample_count"] = len(sampled_radii)
        observed["sampled_radii"] = sampled_radii
    finally:
        env.close()

    artifact = {
        "check": "full_radius_training_exposure",
        "status": "failed" if failures else "passed",
        "observed": observed,
        "expected": expected,
        "checked_scope": [
            "the production training range constant",
            "the range passed through make_training_env",
            "the official evaluation range from contracts.task_spec",
            "target radii from repeated seeded production-environment resets",
        ],
        "unchecked_scope": [
            "training convergence or policy performance",
            "official evaluation outcomes",
            "target sampling distribution beyond these seeded resets",
            "task mechanics, reward, observations, runtime, and PPO settings",
        ],
    }
    output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    if failures:
        raise AssertionError("; ".join(failures))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run_check(args.output)


if __name__ == "__main__":
    main()
