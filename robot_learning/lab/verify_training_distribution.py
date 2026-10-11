"""Laboratory check for the training target-radius distribution.

This check samples the training environment directly rather than relying only
on the configured range.  It is intended to expose restoration of the former
0.14 m lower bound while also exercising ordinary environment transitions.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from contracts.task_spec import TARGET_RADIUS_RANGE
from robot_learning.training.environment import (
    TRAINING_TARGET_RADIUS_RANGE,
    make_training_env,
)


PREVIOUS_TRAINING_LOWER = 0.14
SEEDS = range(64)
TRANSITIONS_PER_RESET = 2


def _target_radius(env) -> float:
    """Measure the sampled planar radius from the environment state."""
    target = np.asarray(env.data.mocap_pos[0], dtype=np.float64)
    return float(np.hypot(target[0], target[1]))


def _run_check() -> dict[str, object]:
    official_range = tuple(float(value) for value in TARGET_RADIUS_RANGE)
    declared_range = tuple(float(value) for value in TRAINING_TARGET_RADIUS_RANGE)
    radii: list[float] = []
    failures: list[str] = []
    reset_count = 0
    transition_count = 0

    env = None
    try:
        env = make_training_env()
        zero_action = np.zeros(env.action_space.shape, dtype=np.float32)

        for seed in SEEDS:
            env.reset(seed=seed)
            radii.append(_target_radius(env))
            reset_count += 1

            for _ in range(TRANSITIONS_PER_RESET):
                transition = env.step(zero_action)
                if len(transition) != 5:
                    failures.append("step did not return the Gymnasium five-tuple")
                transition_count += 1

            env.reset(seed=10_000 + seed)
            radii.append(_target_radius(env))
            reset_count += 1
    except Exception as error:
        failures.append(f"environment sampling failed: {error}")
    finally:
        if env is not None:
            env.close()

    if declared_range != official_range:
        failures.append("training range does not equal the official range")

    lower, upper = official_range
    out_of_bounds = [
        radius for radius in radii if radius < lower or radius > upper
    ]
    if out_of_bounds:
        failures.append("a sampled target was outside the official bounds")

    inner_count = sum(radius < PREVIOUS_TRAINING_LOWER for radius in radii)
    outer_count = sum(radius >= PREVIOUS_TRAINING_LOWER for radius in radii)
    if inner_count == 0:
        failures.append("no sampled target entered the previously omitted inner band")
    if outer_count == 0:
        failures.append("no sampled target entered the outer band")

    observed = {
        "declared_training_range": list(declared_range),
        "official_range": list(official_range),
        "sample_count": len(radii),
        "minimum_sampled_radius": min(radii) if radii else None,
        "maximum_sampled_radius": max(radii) if radii else None,
        "inner_band_count": inner_count,
        "outer_band_count": outer_count,
        "out_of_bounds_count": len(out_of_bounds),
        "reset_count": reset_count,
        "transition_count": transition_count,
    }
    expected = {
        "training_range_equals_official_range": True,
        "all_sampled_radii_within_official_range": True,
        "inner_band_count": "> 0",
        "outer_band_count": "> 0",
        "transitions_per_reset": TRANSITIONS_PER_RESET,
    }
    return {
        "passed": not failures,
        "observed": observed,
        "expected": expected,
        "checked_scope": [
            "training range declaration versus contracts.task_spec.TARGET_RADIUS_RANGE",
            "target radii measured from reset environment state",
            "inner and outer radius bands across controlled seeded resets",
            "repeated zero-action step/reset transitions",
            "official lower and upper bounds for every sampled target",
        ],
        "unchecked_scope": [
            "policy learning or policy performance",
            "evaluation environment mechanics and benchmark evaluation",
            "target angles, dynamics quality, reward quality, and hold success",
        ],
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    artifact = _run_check()
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    if not artifact["passed"]:
        raise AssertionError("; ".join(artifact["failures"]))


if __name__ == "__main__":
    main()
