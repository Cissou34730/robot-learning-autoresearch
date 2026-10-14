"""Scoped verification for the training target-radius distribution.

This check uses the same ``make_training_env`` factory as training, without
constructing a learner or running a training job.  The compatibility mode also
resets that production environment for a few fixed seeds and checks the
sampled target radius, so it does not depend on a saved model or other
campaign artifact.
"""

from __future__ import annotations

import argparse
import json
import math
import shlex
import sys
from pathlib import Path
from typing import Any

from robot_learning.training.environment import (
    TRAINING_TARGET_RADIUS_RANGE,
    make_training_env,
)

EXPECTED_TARGET_RADIUS_RANGE = (0.06, 0.20)
COMPATIBILITY_SEEDS = (0, 1, 2)
CAMPAIGN_EVALUATION_ROOT = (
    Path(__file__).resolve().parents[2]
    / "campaigns"
    / "evaluations"
    / "124dad80-0d01-4503-96cf-bff4755e3278"
)
PRIMARY_ARTIFACT_FILENAME = "full_radius_training_sampler_check.json"
COMPATIBILITY_ARTIFACT_FILENAME = "full_radius_training_sampler_compatibility.json"
MODULE_NAME = "robot_learning.lab.verify_full_radius_training_sampler"


def _configured_range(env: Any) -> tuple[float, float]:
    configured = tuple(float(value) for value in env.target_radius_range)
    if configured != EXPECTED_TARGET_RADIUS_RANGE:
        raise AssertionError(
            "training environment target-radius range is "
            f"{configured}, expected {EXPECTED_TARGET_RADIUS_RANGE}"
        )
    if tuple(TRAINING_TARGET_RADIUS_RANGE) != EXPECTED_TARGET_RADIUS_RANGE:
        raise AssertionError(
            "training constant does not match the expected official-compatible "
            f"range: {TRAINING_TARGET_RADIUS_RANGE}"
        )
    return configured


def _sampled_radius(env: Any) -> float:
    target = env.data.mocap_pos[0]
    return math.hypot(float(target[0]), float(target[1]))


def run_check(*, compatibility: bool) -> dict[str, Any]:
    env = make_training_env()
    try:
        lower, upper = _configured_range(env)
        result: dict[str, Any] = {
            "production_factory": "robot_learning.training.environment.make_training_env",
            "target_radius_range_m": {
                "lower": lower,
                "upper": upper,
            },
            "full_training_executed": False,
        }

        if compatibility:
            sampled_radii = []
            for seed in COMPATIBILITY_SEEDS:
                env.reset(seed=seed)
                radius = _sampled_radius(env)
                if not lower <= radius <= upper:
                    raise AssertionError(
                        f"seed {seed} sampled radius {radius}, outside "
                        f"[{lower}, {upper}]"
                    )
                sampled_radii.append(radius)
            result["reset_seeds"] = list(COMPATIBILITY_SEEDS)
            result["sampled_target_radii_m"] = sampled_radii
            result["production_reset_compatible"] = True
        return result
    finally:
        env.close()


def _artifact_path(
    artifact: Path | None, *, compatibility: bool
) -> Path:
    if artifact is not None:
        return artifact
    filename = (
        COMPATIBILITY_ARTIFACT_FILENAME
        if compatibility
        else PRIMARY_ARTIFACT_FILENAME
    )
    return CAMPAIGN_EVALUATION_ROOT / filename


def _normalize_argv(argv: list[str] | None = None) -> list[str]:
    normalized = list(sys.argv[1:] if argv is None else argv)
    if len(normalized) == 1:
        normalized = shlex.split(normalized[0])
    if normalized and normalized[0] == MODULE_NAME:
        normalized = normalized[1:]
    return normalized


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--compatibility", action="store_true")
    args = parser.parse_args(_normalize_argv(argv))

    result = run_check(compatibility=args.compatibility)
    artifact_argument = (
        None if args.artifact == Path("{artifact}") else args.artifact
    )
    artifact = _artifact_path(
        artifact_argument, compatibility=args.compatibility
    )
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
