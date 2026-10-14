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
from pathlib import Path
from typing import Any

from robot_learning.training.environment import (
    TRAINING_TARGET_RADIUS_RANGE,
    make_training_env,
)

EXPECTED_TARGET_RADIUS_RANGE = (0.06, 0.20)
COMPATIBILITY_SEEDS = (0, 1, 2)


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--compatibility", action="store_true")
    args = parser.parse_args()

    result = run_check(compatibility=args.compatibility)
    args.artifact.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
