"""Executable, synthetic verification for the research-evaluation analysis.

The checks use a small independent artifact with exact boundary values.  They
exercise the public analysis path and write observations and expectations to
the supplied artifact path.  They do not inspect or alter the completed M4
artifact.
"""

from __future__ import annotations

import argparse
import copy
import json
import tempfile
from pathlib import Path
from typing import Any

from robot_learning.lab.analyze_research_evaluation import analyze_artifact, write_analysis


def _diagnostic(
    episode: int,
    seed: int,
    *,
    radius: float,
    angle: float,
    steps: int,
    held_steps: list[int],
    branches: list[str],
    first_reach: int | None,
    max_held: int,
    interruptions: int,
) -> dict[str, Any]:
    open_steps = branches.count("open")
    folded_steps = branches.count("folded")
    return {
        "episode": episode,
        "episode_seed": seed,
        "target_radius_cm": radius,
        "target_angle_degrees": angle,
        "min_distance_cm": 0.5,
        "final_distance_cm": 1.0,
        "first_reach_step": first_reach,
        "max_held_steps": max_held,
        "in_tolerance_steps": sum(value > 0 for value in held_steps),
        "hold_interruptions": interruptions,
        "open_branch_occupancy_steps": open_steps,
        "folded_branch_occupancy_steps": folded_steps,
        "open_branch_occupancy_fraction": open_steps / steps,
        "folded_branch_occupancy_fraction": folded_steps / steps,
        "branch_switches": sum(
            previous != current
            for previous, current in zip(branches, branches[1:])
        ),
        "branch_at_first_reach": (
            branches[first_reach - 1] if first_reach is not None else None
        ),
        "branch_at_max_held_run": (
            branches[held_steps.index(max_held)] if max_held else None
        ),
        "min_open_branch_error_norm": 0.1,
        "min_folded_branch_error_norm": 0.2,
    }


def _synthetic_artifact() -> dict[str, Any]:
    specifications = (
        # The four radius and angle boundaries are intentional.
        (0, 100, True, 6.0, -180.0, 5, [0, 3, 5, 4, 0], ["open", "open", "folded", "folded", "open"], 2, 5, 0),
        (1, 101, False, 10.0, -90.0, 4, [0, 0, 0, 0], ["open"] * 4, None, 0, 0),
        (2, 102, False, 14.0, 0.0, 3, [1, 3, 0], ["folded"] * 3, 1, 3, 2),
        (3, 103, False, 20.0, 90.0, 3, [1, 2, 0], ["open", "folded", "open"], 1, 2, 1),
    )
    outcomes = []
    diagnostics = []
    for (
        episode,
        seed,
        success,
        radius,
        angle,
        steps,
        held_steps,
        branches,
        first_reach,
        max_held,
        interruptions,
    ) in specifications:
        outcomes.append(
            {
                "episode": episode,
                "episode_seed": seed,
                "success": success,
                "steps": steps,
                "terminated": True,
                "truncated": False,
            }
        )
        diagnostics.append(
            _diagnostic(
                episode,
                seed,
                radius=radius,
                angle=angle,
                steps=steps,
                held_steps=held_steps,
                branches=branches,
                first_reach=first_reach,
                max_held=max_held,
                interruptions=interruptions,
            )
        )
    return {
        "schema_version": 6,
        "episodes": len(outcomes),
        "official_benchmark": False,
        "episode_results": outcomes,
        "research_evidence": {"episode_diagnostics": diagnostics},
    }


def _expect_rejection(artifact: dict[str, Any], label: str) -> str:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / f"{label}.json"
        path.write_text(json.dumps(artifact), encoding="utf-8")
        try:
            analyze_artifact(path)
        except ValueError:
            return "rejected"
    raise AssertionError(f"{label} was accepted")


def run_check(output_path: Path) -> None:
    artifact = _synthetic_artifact()
    with tempfile.TemporaryDirectory() as directory:
        input_path = Path(directory) / "synthetic-m4.json"
        input_path.write_text(json.dumps(artifact), encoding="utf-8")
        observed = write_analysis(input_path, Path(directory) / "analysis.json")

    overall = observed["overall"]
    expected_overall = {
        "denominator": 4,
        "successes": 1,
        "failures": 3,
        "no_reach_failures": 1,
        "sampled_hold_failures": 2,
    }
    for field, expected in expected_overall.items():
        if overall[field] != expected:
            raise AssertionError(f"overall {field}: {overall[field]} != {expected}")

    expected_radius_counts = {
        "[6,10)": (1, 1, 0),
        "[10,14)": (0, 1, 1),
        "[14,20]": (0, 2, 1),
    }
    for label, (successes, failures, no_reach) in expected_radius_counts.items():
        group = observed["radius_bins"][label]
        expected = {
            "successes": successes,
            "failures": failures,
            "no_reach_failures": no_reach,
            "sampled_hold_failures": failures - no_reach,
            "denominator": successes + failures,
        }
        for field, value in expected.items():
            if group[field] != value:
                raise AssertionError(f"radius {label} {field}: {group[field]} != {value}")

    expected_angle_denominators = {
        "[-180,-90)": 1,
        "[-90,0)": 1,
        "[0,90)": 1,
        "[90,180]": 1,
    }
    for label, denominator in expected_angle_denominators.items():
        if observed["angle_sectors"][label]["denominator"] != denominator:
            raise AssertionError(f"angle boundary was assigned incorrectly for {label}")

    reached = observed["reached_failure_summaries"]
    if reached["denominator"] != 2:
        raise AssertionError("reached-failure denominator omitted a hold failure")
    if reached["max_held_steps"]["total"] != 5 or reached["hold_interruptions"]["total"] != 3:
        raise AssertionError("reached-failure mechanism summaries are incomplete")

    branches = observed["branch_summaries"]
    if branches["overall"]["occupancy"] != {
        "open_steps": 9,
        "folded_steps": 6,
        "open_fraction": 0.6,
        "folded_fraction": 0.4,
    }:
        raise AssertionError("overall branch occupancy is incorrect")
    failure_attribution = branches["failures"]["branch_at_first_reach"]["counts"]
    if failure_attribution != {"open": 1, "folded": 1, "null": 1}:
        raise AssertionError("failure branch-at-first-reach counts are incomplete")
    failure_max_attribution = branches["failures"]["branch_at_max_held_run"]["counts"]
    if failure_max_attribution != {"open": 0, "folded": 2, "null": 1}:
        raise AssertionError("failure branch-at-max-held-run counts are incomplete")
    if branches["failures"]["occupancy"] != {
        "open_steps": 6,
        "folded_steps": 4,
        "open_fraction": 0.6,
        "folded_fraction": 0.4,
    }:
        raise AssertionError("failure branch occupancy is incorrect")
    if branches["failures"]["branch_switches"]["total"] != 2:
        raise AssertionError("failure branch-switch total is incorrect")

    misaligned = copy.deepcopy(artifact)
    misaligned["research_evidence"]["episode_diagnostics"][0], misaligned[
        "research_evidence"
    ]["episode_diagnostics"][1] = (
        misaligned["research_evidence"]["episode_diagnostics"][1],
        misaligned["research_evidence"]["episode_diagnostics"][0],
    )
    alignment_result = _expect_rejection(misaligned, "misaligned")

    inconsistent = copy.deepcopy(artifact)
    inconsistent["episode_results"][1]["success"] = True
    inconsistency_result = _expect_rejection(inconsistent, "inconsistent")

    missing_field = copy.deepcopy(artifact)
    del missing_field["research_evidence"]["episode_diagnostics"][0][
        "branch_at_max_held_run"
    ]
    schema_result = _expect_rejection(missing_field, "missing-m4-field")

    report = {
        "check": "synthetic research-evaluation mechanism analysis",
        "observed": {
            "overall": {
                field: overall[field] for field in expected_overall
            },
            "radius_bins": {
                label: {
                    field: observed["radius_bins"][label][field]
                    for field in (
                        "denominator",
                        "successes",
                        "failures",
                        "no_reach_failures",
                        "sampled_hold_failures",
                    )
                }
                for label in expected_radius_counts
            },
            "angle_sector_denominators": {
                label: observed["angle_sectors"][label]["denominator"]
                for label in expected_angle_denominators
            },
            "reached_failure_max_held_total": reached["max_held_steps"]["total"],
            "reached_failure_interruptions_total": reached["hold_interruptions"]["total"],
            "failure_branch_at_first_reach": failure_attribution,
            "failure_branch_at_max_held_run": failure_max_attribution,
            "failure_branch_occupancy": branches["failures"]["occupancy"],
            "failure_branch_switch_total": branches["failures"]["branch_switches"]["total"],
            "rejection_checks": {
                "misaligned_rows": alignment_result,
                "inconsistent_outcome": inconsistency_result,
                "missing_m4_field": schema_result,
            },
        },
        "expected": {
            "failure_classes": {
                "no_reach_failures": 1,
                "sampled_hold_failures": 2,
            },
            "radius_bins": list(expected_radius_counts),
            "angle_sectors": list(expected_angle_denominators),
            "branch_occupancy_steps": {"open": 9, "folded": 6},
            "failure_branch_occupancy_steps": {"open": 6, "folded": 4},
            "failure_branch_switch_total": 2,
            "all_rejection_checks": "rejected",
        },
        "checked_scope": [
            "schema version and development-artifact guard",
            "episode and episode-seed alignment",
            "required M4 diagnostic fields",
            "success, no-reach, and reached-hold failure classification",
            "radius boundaries 6, 10, 14, and 20 cm",
            "four source-angle sector boundaries in [-180,180] degrees",
            "reached-failure max-held-step and interruption summaries",
            "overall and failure branch occupancy, attribution, and switches",
        ],
        "unchecked_scope": [
            "the completed M4 artifact's scientific validity",
            "policy behavior outside the synthetic rows",
            "causal interpretation or official certification",
        ],
    }
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args(argv)
    run_check(args.output_json)


if __name__ == "__main__":
    main()
