"""Verify the production training target-exposure recipe.

This is a laboratory check for the training sampler, not an evaluation of a
policy or of scientific efficacy.  It writes a JSON result to the requested
output path and raises after writing when a checked invariant is violated.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from robot_learning.training.environment import make_training_env


OFFICIAL_RADIUS_RANGE = (0.06, 0.20)
DIFFICULT_SECTOR_DEGREES = (-90.0, 0.0)
FULL_ANGLE_SECTORS = (
    ("[-180,-90)", -180.0, -90.0, False),
    ("[-90,0)", -90.0, 0.0, False),
    ("[0,90)", 0.0, 90.0, False),
    ("[90,180]", 90.0, 180.0, True),
)
TARGETED_DIFFICULT_FRACTION = 0.625
SAMPLE_COUNT = 512
SAMPLE_SEED = 20261012
CONFIDENCE_FAILURE_PROBABILITY = 0.01


def _target_geometry(env: Any) -> tuple[float, float]:
    target_xy = np.asarray(env.data.mocap_pos[0][:2], dtype=np.float64)
    radius = float(np.linalg.norm(target_xy))
    angle_degrees = math.degrees(math.atan2(float(target_xy[1]), float(target_xy[0])))
    return radius, angle_degrees


def _angle_sector(angle_degrees: float) -> str:
    for label, lower, upper, upper_inclusive in FULL_ANGLE_SECTORS:
        if lower <= angle_degrees < upper or (
            upper_inclusive and lower <= angle_degrees <= upper
        ):
            return label
    raise AssertionError(f"sampled angle is outside the full range: {angle_degrees}")


def _collect_targets(env: Any, count: int, seed: int) -> np.ndarray:
    env.reset(seed=seed)
    samples = [_target_geometry(env)]
    for _ in range(count - 1):
        env.reset()
        samples.append(_target_geometry(env))
    return np.asarray(samples, dtype=np.float64)


def _write_result(output_path: Path, result: dict[str, Any]) -> None:
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _compatibility_result() -> dict[str, Any]:
    """Exercise the changed environment through reset and a few real steps."""
    env = make_training_env()
    failures: list[str] = []
    observations: list[dict[str, Any]] = []
    try:
        observation, reset_info = env.reset(seed=SAMPLE_SEED)
        expected_shape = tuple(env.observation_space.shape)
        observations.append(
            {
                "reset_observation_shape": list(observation.shape),
                "reset_observation_dtype": str(observation.dtype),
                "reset_info_type": type(reset_info).__name__,
            }
        )
        if observation.shape != expected_shape:
            failures.append("reset observation shape does not match observation_space")
        if not np.isfinite(observation).all():
            failures.append("reset observation contains a non-finite value")
        if not isinstance(reset_info, dict):
            failures.append("reset info is not a dictionary")

        for step_index in range(3):
            step_result = env.step(np.zeros(env.action_space.shape, dtype=np.float32))
            next_observation, reward, terminated, truncated, info = step_result
            observations.append(
                {
                    "step": step_index,
                    "observation_shape": list(next_observation.shape),
                    "reward": float(reward),
                    "terminated_type": type(terminated).__name__,
                    "truncated_type": type(truncated).__name__,
                    "info_type": type(info).__name__,
                }
            )
            if next_observation.shape != expected_shape:
                failures.append(f"step {step_index} observation shape changed")
            if not np.isfinite(next_observation).all() or not math.isfinite(
                float(reward)
            ):
                failures.append(f"step {step_index} produced a non-finite result")
            if not isinstance(terminated, (bool, np.bool_)) or not isinstance(
                truncated, (bool, np.bool_)
            ):
                failures.append(f"step {step_index} returned non-boolean termination flags")
            if not isinstance(info, dict):
                failures.append(f"step {step_index} info is not a dictionary")

        return {
            "check": "training_exposure_compatibility",
            "status": "passed" if not failures else "failed",
            "observed": {
                "environment_type": type(env).__name__,
                "observation_space_shape": list(env.observation_space.shape),
                "action_space_shape": list(env.action_space.shape),
                "reset_and_step_records": observations,
            },
            "expected": {
                "reset_and_step_api": (
                    "finite observations matching observation_space, finite rewards, "
                    "boolean termination flags, and dictionary info"
                ),
                "production_path": "make_training_env",
            },
            "checked_scope": [
                "production training-environment construction",
                "one seeded reset",
                "three zero-action MuJoCo transitions",
                "reset/step observation, reward, termination, and info contracts",
            ],
            "unchecked_scope": [
                "large-sample exposure distribution",
                "policy learning or evaluation success",
                "continuous-time hold behavior between control checks",
            ],
            "failures": failures,
            "author_execution_note": (
                "This compatibility check has not been executed by the author."
            ),
        }
    finally:
        env.close()


def _behavior_result() -> dict[str, Any]:
    env_a = make_training_env()
    env_b = make_training_env()
    failures: list[str] = []
    try:
        samples_a = _collect_targets(env_a, SAMPLE_COUNT, SAMPLE_SEED)
        samples_b = _collect_targets(env_b, SAMPLE_COUNT, SAMPLE_SEED)
        seeded_targets_match = bool(np.array_equal(samples_a, samples_b))
        if not seeded_targets_match:
            failures.append("same seed did not reproduce the target sequence")

        radii = samples_a[:, 0]
        angles = samples_a[:, 1]
        radius_min, radius_max = OFFICIAL_RADIUS_RANGE
        radius_in_range = bool(
            np.all((radii >= radius_min) & (radii <= radius_max))
        )
        if not radius_in_range:
            failures.append("a sampled radius is outside the official interval")

        sectors = [_angle_sector(angle) for angle in angles]
        sector_counts = {
            label: sectors.count(label) for label, *_ in FULL_ANGLE_SECTORS
        }
        represented_sectors = [
            label for label, count in sector_counts.items() if count > 0
        ]
        expected_sectors = [label for label, *_ in FULL_ANGLE_SECTORS]
        if represented_sectors != expected_sectors:
            failures.append("not every official angular sector was represented")

        difficult_count = int(
            sum(
                DIFFICULT_SECTOR_DEGREES[0] <= angle < DIFFICULT_SECTOR_DEGREES[1]
                for angle in angles
            )
        )
        difficult_fraction = difficult_count / SAMPLE_COUNT
        one_sided_epsilon = math.sqrt(
            math.log(1.0 / CONFIDENCE_FAILURE_PROBABILITY)
            / (2.0 * SAMPLE_COUNT)
        )
        two_sided_epsilon = math.sqrt(
            math.log(2.0 / CONFIDENCE_FAILURE_PROBABILITY)
            / (2.0 * SAMPLE_COUNT)
        )
        lower_bound_against_uniform = difficult_fraction - one_sided_epsilon
        targeted_fraction_interval = (
            TARGETED_DIFFICULT_FRACTION - two_sided_epsilon,
            TARGETED_DIFFICULT_FRACTION + two_sided_epsilon,
        )
        difficult_fraction_is_targeted = (
            targeted_fraction_interval[0]
            <= difficult_fraction
            <= targeted_fraction_interval[1]
        )
        materially_above_uniform = lower_bound_against_uniform > 0.25
        if not materially_above_uniform:
            failures.append(
                "difficult-sector fraction is not above the uniform-only 25% "
                "expectation under the one-sided finite-sample bound"
            )
        if not difficult_fraction_is_targeted:
            failures.append(
                "difficult-sector fraction is inconsistent with the 50% "
                "targeted/full-angle mixture at the two-sided finite-sample bound"
            )

        radius_bin_edges = np.linspace(radius_min, radius_max, 4)
        radius_bin_counts = [
            int(
                np.sum(
                    (radii >= radius_bin_edges[index])
                    & (
                        (radii < radius_bin_edges[index + 1])
                        if index < 2
                        else (radii <= radius_bin_edges[index + 1])
                    )
                )
            )
            for index in range(3)
        ]
        radius_bin_epsilon = math.sqrt(
            math.log(2.0 * 3.0 / CONFIDENCE_FAILURE_PROBABILITY)
            / (2.0 * SAMPLE_COUNT)
        )
        radius_bin_fractions = [
            count / SAMPLE_COUNT for count in radius_bin_counts
        ]
        radius_bins_compatible = all(
            abs(fraction - (1.0 / 3.0)) <= radius_bin_epsilon
            for fraction in radius_bin_fractions
        )
        if not radius_bins_compatible:
            failures.append(
                "radius-bin frequencies are inconsistent with uniform sampling "
                "under the finite-sample bound"
            )

        return {
            "check": "training_exposure_behavior",
            "status": "passed" if not failures else "failed",
            "observed": {
                "sample_count": SAMPLE_COUNT,
                "seed": SAMPLE_SEED,
                "seeded_targets_match": seeded_targets_match,
                "radius_min": float(np.min(radii)),
                "radius_max": float(np.max(radii)),
                "all_radii_in_official_interval": radius_in_range,
                "angle_min_degrees": float(np.min(angles)),
                "angle_max_degrees": float(np.max(angles)),
                "angle_sector_counts": sector_counts,
                "represented_angle_sectors": represented_sectors,
                "difficult_sector_count": difficult_count,
                "difficult_sector_fraction": difficult_fraction,
                "radius_bin_edges": radius_bin_edges.tolist(),
                "radius_bin_counts": radius_bin_counts,
                "radius_bin_fractions": radius_bin_fractions,
            },
            "expected": {
                "official_radius_interval_m": list(OFFICIAL_RADIUS_RANGE),
                "radius_sampling": "uniform; each of three equal-width bins is "
                f"within {radius_bin_epsilon:.6f} of 1/3",
                "angle_sectors": expected_sectors,
                "targeted_difficult_fraction": TARGETED_DIFFICULT_FRACTION,
                "uniform_only_difficult_fraction": 0.25,
                "difficult_fraction_two_sided_interval": list(
                    targeted_fraction_interval
                ),
                "difficult_fraction_lower_bound_against_uniform": (
                    lower_bound_against_uniform
                ),
                "difficult_fraction_one_sided_epsilon": one_sided_epsilon,
                "confidence_failure_probability": CONFIDENCE_FAILURE_PROBABILITY,
            },
            "checked_scope": [
                "production make_training_env construction",
                "deterministic seeded reset sequence",
                "all sampled radii in the official 0.06-0.20 m interval",
                "radius-bin frequencies consistent with uniform sampling",
                "representation of all four official angular sectors",
                "difficult-sector fraction versus uniform-only and targeted-mixture "
                "finite-sample bounds",
            ],
            "unchecked_scope": [
                "policy training or policy success",
                "causal effect of exposure on no-reach failures",
                "evaluation-environment behavior beyond the unchanged scenario "
                "implementation",
                "continuous-time target or hold behavior between control checks",
            ],
            "failures": failures,
            "author_execution_note": (
                "This behavioral check has not been executed by the author."
            ),
        }
    finally:
        env_a.close()
        env_b.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compatibility", action="store_true")
    args = parser.parse_args(argv)

    result = (
        _compatibility_result() if args.compatibility else _behavior_result()
    )
    _write_result(args.output, result)
    if result["status"] != "passed":
        raise AssertionError("; ".join(result["failures"]))


if __name__ == "__main__":
    main()
