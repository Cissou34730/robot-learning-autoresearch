"""Executable laboratory check for evaluation stratification analysis.

This module uses controlled synthetic rows with known consequences.  It checks
the independent boundary rules and aggregate arithmetic, rather than claiming
anything about a scientific evaluation or its policy.
"""

from __future__ import annotations

import argparse
import copy
import json
import tempfile
from pathlib import Path
from typing import Any

from robot_learning.lab.analyze_evaluation_stratification import (
    ArtifactValidationError,
    analyze_evaluation_stratification,
)


def _synthetic_artifact() -> dict[str, Any]:
    rows = (
        (0, 6.0, -180.0, False, None, 0, 0),
        (1, 13.9, -90.0, False, 4, 40, 2),
        (2, 13.9, 0.0, True, 5, 100, 0),
        (3, 13.9, 90.0, False, 6, 99, 1),
        (4, 14.0, -180.0, True, 3, 100, 0),
        (5, 20.0, -90.0, False, None, 0, 0),
        (6, 20.0, 0.0, True, 7, 100, 0),
        (7, 20.0, 90.0, True, 8, 100, 0),
    )
    return {
        "episodes": len(rows),
        "episode_results": [
            {"episode": episode, "success": success}
            for episode, _, _, success, _, _, _ in rows
        ],
        "research_evidence": {
            "episode_diagnostics": [
                {
                    "episode": episode,
                    "target_radius_cm": radius,
                    "target_angle_degrees": angle,
                    "first_reach_step": first_reach,
                    "max_held_steps": max_held,
                    "hold_interruptions": interruptions,
                }
                for episode, radius, angle, success, first_reach, max_held, interruptions
                in rows
            ]
        },
    }


def _write_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _check_stratum(
    actual: dict[str, Any], expected: dict[str, Any], label: str
) -> None:
    for field, expected_value in expected.items():
        _require(
            actual.get(field) == expected_value,
            f"{label} field {field!r}: observed {actual.get(field)!r}, "
            f"expected {expected_value!r}",
        )


def run_check(output_path: str | Path) -> dict[str, Any]:
    """Run the controlled-input check and write its JSON observation artifact."""
    output_path = Path(output_path)
    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary = Path(temporary_directory)
        input_path = temporary / "synthetic_evaluation.json"
        analysis_path = temporary / "analysis.json"
        synthetic = _synthetic_artifact()
        _write_json(input_path, synthetic)
        observed = analyze_evaluation_stratification(input_path, analysis_path)

        _require(observed["total_episodes"] == 8, "total episode count mismatch")
        _require(observed["total_successes"] == 4, "total success count mismatch")
        _require(observed["success_percent"] == 50.0, "total success percent mismatch")

        bands = {item["name"]: item for item in observed["radius_bands"]}
        sectors = {item["name"]: item for item in observed["angle_sectors"]}
        _require(set(bands) == {"inner", "outer"}, "radius bands are incomplete")
        _require(
            set(sectors) == {"[-180,-90)", "[-90,0)", "[0,90)", "[90,180)"},
            "angle sectors are incomplete",
        )
        _check_stratum(
            bands["inner"],
            {
                "episode_count": 4,
                "successes": 1,
                "success_percent": 25.0,
                "reach_count": 3,
                "reach_percent": 75.0,
                "mean_first_reach_step": 5.0,
                "mean_max_held_steps": 59.75,
                "maximum_max_held_steps": 100,
                "interruption_episode_count": 2,
                "total_interruptions": 3,
                "failures_before_any_reach": 1,
                "failures_after_reach_without_complete_hold": 2,
            },
            "inner radius band",
        )
        _check_stratum(
            bands["outer"],
            {
                "episode_count": 4,
                "successes": 3,
                "success_percent": 75.0,
                "reach_count": 3,
                "reach_percent": 75.0,
                "mean_first_reach_step": 6.0,
                "mean_max_held_steps": 75.0,
                "maximum_max_held_steps": 100,
                "interruption_episode_count": 0,
                "total_interruptions": 0,
                "failures_before_any_reach": 1,
                "failures_after_reach_without_complete_hold": 0,
            },
            "outer radius band",
        )

        _require(
            bands["inner"]["coverage"]
            == {
                "radius_min_cm": 6.0,
                "radius_max_cm": 13.9,
                "radius_count": 4,
                "angle_min_degrees": -180.0,
                "angle_max_degrees": 90.0,
                "angle_count": 4,
            },
            "inner radius boundary or coverage mismatch",
        )
        _require(
            bands["outer"]["coverage"]["radius_min_cm"] == 14.0
            and bands["outer"]["coverage"]["radius_max_cm"] == 20.0,
            "radius 14.0 or 20.0 was assigned incorrectly",
        )
        expected_sector_coverage = {
            "[-180,-90)": {
                "radius_min_cm": 6.0,
                "radius_max_cm": 14.0,
                "radius_count": 2,
                "angle_min_degrees": -180.0,
                "angle_max_degrees": -180.0,
                "angle_count": 2,
            },
            "[-90,0)": {
                "radius_min_cm": 13.9,
                "radius_max_cm": 20.0,
                "radius_count": 2,
                "angle_min_degrees": -90.0,
                "angle_max_degrees": -90.0,
                "angle_count": 2,
            },
            "[0,90)": {
                "radius_min_cm": 13.9,
                "radius_max_cm": 20.0,
                "radius_count": 2,
                "angle_min_degrees": 0.0,
                "angle_max_degrees": 0.0,
                "angle_count": 2,
            },
            "[90,180)": {
                "radius_min_cm": 13.9,
                "radius_max_cm": 20.0,
                "radius_count": 2,
                "angle_min_degrees": 90.0,
                "angle_max_degrees": 90.0,
                "angle_count": 2,
            },
        }
        for name, expected_coverage in expected_sector_coverage.items():
            _require(
                sectors[name]["coverage"] == expected_coverage,
                f"angle sector {name} coverage mismatch",
            )
        expected_sector_values = {
            "[-180,-90)": (2, 1, 50.0, 1, 50.0, 3.0, 50.0, 100, 0, 0, 1, 0),
            "[-90,0)": (2, 0, 0.0, 1, 50.0, 4.0, 20.0, 40, 1, 2, 1, 1),
            "[0,90)": (2, 2, 100.0, 2, 100.0, 6.0, 100.0, 100, 0, 0, 0, 0),
            "[90,180)": (2, 1, 50.0, 2, 100.0, 7.0, 99.5, 100, 1, 1, 0, 1),
        }
        for name, values in expected_sector_values.items():
            (
                episode_count,
                successes,
                success_percent,
                reach_count,
                reach_percent,
                mean_first_reach_step,
                mean_max_held_steps,
                maximum_max_held_steps,
                interruption_episode_count,
                total_interruptions,
                failures_before_any_reach,
                failures_after_reach_without_complete_hold,
            ) = values
            _check_stratum(
                sectors[name],
                {
                    "episode_count": episode_count,
                    "successes": successes,
                    "success_percent": success_percent,
                    "reach_count": reach_count,
                    "reach_percent": reach_percent,
                    "mean_first_reach_step": mean_first_reach_step,
                    "mean_max_held_steps": mean_max_held_steps,
                    "maximum_max_held_steps": maximum_max_held_steps,
                    "interruption_episode_count": interruption_episode_count,
                    "total_interruptions": total_interruptions,
                    "failures_before_any_reach": failures_before_any_reach,
                    "failures_after_reach_without_complete_hold": (
                        failures_after_reach_without_complete_hold
                    ),
                },
                f"angle sector {name}",
            )

        incomplete = copy.deepcopy(synthetic)
        del incomplete["research_evidence"]["episode_diagnostics"][1][
            "hold_interruptions"
        ]
        incomplete_path = temporary / "incomplete_evaluation.json"
        _write_json(incomplete_path, incomplete)
        try:
            analyze_evaluation_stratification(incomplete_path, analysis_path)
        except ArtifactValidationError as exc:
            incomplete_error = str(exc)
        else:
            raise AssertionError(
                "an incomplete diagnostic row did not raise ArtifactValidationError"
            )
        _require(
            "hold_interruptions" in incomplete_error,
            "incomplete diagnostic error did not name the missing field",
        )

        result = {
            "check": "evaluation_stratification",
            "observed": {
                "total_episodes": observed["total_episodes"],
                "total_successes": observed["total_successes"],
                "radius_bands": bands,
                "angle_sectors": sectors,
                "incomplete_diagnostic_error": incomplete_error,
            },
            "expected": {
                "total_episodes": 8,
                "total_successes": 4,
                "radius_bands": {
                    "inner": {
                        "episode_count": 4,
                        "successes": 1,
                        "reach_count": 3,
                        "mean_first_reach_step": 5.0,
                        "mean_max_held_steps": 59.75,
                        "maximum_max_held_steps": 100,
                        "interruption_episode_count": 2,
                        "total_interruptions": 3,
                        "failures_before_any_reach": 1,
                        "failures_after_reach_without_complete_hold": 2,
                    },
                    "outer": {
                        "episode_count": 4,
                        "successes": 3,
                        "reach_count": 3,
                        "mean_first_reach_step": 6.0,
                        "mean_max_held_steps": 75.0,
                        "maximum_max_held_steps": 100,
                        "interruption_episode_count": 0,
                        "total_interruptions": 0,
                        "failures_before_any_reach": 1,
                        "failures_after_reach_without_complete_hold": 0,
                    },
                },
                "angle_sector_coverage": expected_sector_coverage,
                "angle_sector_aggregate_tuples": expected_sector_values,
                "boundary_assignments": {
                    "inner_radius": "[6.0,14.0)",
                    "outer_radius": "[14.0,20.0]",
                    "angle_sectors": [
                        "[-180,-90)",
                        "[-90,0)",
                        "[0,90)",
                        "[90,180)",
                    ],
                },
                "failure_classes": (
                    "pre-reach and post-reach incomplete-hold failures are "
                    "counted separately"
                ),
            },
            "checked_scope": [
                "joined episode IDs, duplicate/missing diagnostic detection",
                "inner and outer radius boundaries including 14.0 cm",
                "all four angle sectors including -180 and excluding 180",
                "success, reach, hold, interruption, and failure-class aggregates",
                "raw radius and angle coverage in every stratum",
                "explicit rejection of an incomplete diagnostic row",
            ],
            "unchecked_scope": [
                "scientific validity of the evaluator or policy",
                "real campaign artifact contents and sampling quality",
                "causal interpretation of any failure class",
            ],
        }
    _write_json(output_path, result)
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Check evaluation stratification analysis with controlled inputs."
    )
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args(argv)
    run_check(args.output_json)


if __name__ == "__main__":
    main()
