"""Mechanism summaries for one preserved research-evaluation artifact.

This is a development-evidence analysis, not an evaluator and not an official
assessment.  The input artifact is read only.  Schema and row-consistency
checks are intentionally strict so that an outcome is never paired with the
diagnostics of another episode.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import median
from typing import Any


RADIUS_BINS = (
    ("[6,10)", 6.0, 10.0, False),
    ("[10,14)", 10.0, 14.0, False),
    ("[14,20]", 14.0, 20.0, True),
)
ANGLE_SECTORS = (
    ("[-180,-90)", -180.0, -90.0, False),
    ("[-90,0)", -90.0, 0.0, False),
    ("[0,90)", 0.0, 90.0, False),
    ("[90,180]", 90.0, 180.0, True),
)

_REQUIRED_DIAGNOSTIC_FIELDS = {
    "episode",
    "episode_seed",
    "target_radius_cm",
    "target_angle_degrees",
    "min_distance_cm",
    "final_distance_cm",
    "first_reach_step",
    "max_held_steps",
    "in_tolerance_steps",
    "hold_interruptions",
    "open_branch_occupancy_steps",
    "folded_branch_occupancy_steps",
    "open_branch_occupancy_fraction",
    "folded_branch_occupancy_fraction",
    "branch_switches",
    "branch_at_first_reach",
    "branch_at_max_held_run",
    "min_open_branch_error_norm",
    "min_folded_branch_error_norm",
}


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _positive_int_or_none(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be null or a positive integer")
    return value


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _outcome_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    denominator = len(rows)
    successes = sum(bool(row["success"]) for row in rows)
    failures = denominator - successes
    no_reach = sum(
        not row["success"] and row["first_reach_step"] is None for row in rows
    )
    hold_failures = sum(
        not row["success"] and row["first_reach_step"] is not None for row in rows
    )
    return {
        "count": denominator,
        "denominator": denominator,
        "successes": successes,
        "failures": failures,
        "success_rate": _rate(successes, denominator),
        "failure_rate": _rate(failures, denominator),
        "no_reach_failures": no_reach,
        "sampled_hold_failures": hold_failures,
    }


def _numeric_summary(values: list[int]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "denominator": 0,
            "total": 0,
            "mean": None,
            "median": None,
            "minimum": None,
            "maximum": None,
        }
    return {
        "count": len(values),
        "denominator": len(values),
        "total": sum(values),
        "mean": sum(values) / len(values),
        "median": median(values),
        "minimum": min(values),
        "maximum": max(values),
    }


def _classify_radius(radius: float) -> str:
    for label, lower, upper, upper_inclusive in RADIUS_BINS:
        if lower <= radius < upper or (
            upper_inclusive and lower <= radius <= upper
        ):
            return label
    raise ValueError(
        f"target_radius_cm={radius} is outside the required [6,20] cm panel"
    )


def _classify_angle(angle_degrees: float) -> str:
    for label, lower, upper, upper_inclusive in ANGLE_SECTORS:
        if lower <= angle_degrees < upper or (
            upper_inclusive and lower <= angle_degrees <= upper
        ):
            return label
    raise ValueError(
        f"target_angle_degrees={angle_degrees} is outside the [-180,180] panel"
    )


def _validate_artifact(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    if artifact.get("schema_version") != 6:
        raise ValueError("the research-evaluation artifact must have schema_version 6")
    if artifact.get("official_benchmark") is not False:
        raise ValueError("analysis requires a development artifact, not an official benchmark")

    outcomes = artifact.get("episode_results")
    evidence = artifact.get("research_evidence")
    diagnostics = evidence.get("episode_diagnostics") if isinstance(evidence, dict) else None
    if not isinstance(outcomes, list) or not isinstance(diagnostics, list):
        raise ValueError("episode_results and research_evidence/episode_diagnostics must be arrays")
    if len(outcomes) != len(diagnostics):
        raise ValueError("episode_results and episode_diagnostics have different lengths")
    if not outcomes:
        raise ValueError("the artifact contains no episode rows")
    if artifact.get("episodes") != len(outcomes):
        raise ValueError("artifact episodes does not match episode_results length")

    rows: list[dict[str, Any]] = []
    seen_episodes: set[int] = set()
    for index, (outcome, diagnostic) in enumerate(zip(outcomes, diagnostics)):
        if not isinstance(outcome, dict) or not isinstance(diagnostic, dict):
            raise ValueError(f"episode row {index} is not an object")
        missing = sorted(_REQUIRED_DIAGNOSTIC_FIELDS - diagnostic.keys())
        if missing:
            raise ValueError(
                f"episode diagnostic {index} is missing M4 fields: {', '.join(missing)}"
            )

        episode = outcome.get("episode")
        diagnostic_episode = diagnostic.get("episode")
        seed = outcome.get("episode_seed")
        diagnostic_seed = diagnostic.get("episode_seed")
        if (
            isinstance(episode, bool)
            or not isinstance(episode, int)
            or episode in seen_episodes
            or diagnostic_episode != episode
            or diagnostic_seed != seed
        ):
            raise ValueError(
                f"episode outcome and diagnostic rows are not aligned at index {index}"
            )
        seen_episodes.add(episode)
        success = outcome.get("success")
        if not isinstance(success, bool):
            raise ValueError(f"episode {episode} success must be boolean")
        steps = _positive_int_or_none(outcome.get("steps"), f"episode {episode} steps")
        if steps is None:
            raise ValueError(f"episode {episode} steps must be positive")

        radius = _finite_number(
            diagnostic["target_radius_cm"], f"episode {episode} target_radius_cm"
        )
        angle = _finite_number(
            diagnostic["target_angle_degrees"], f"episode {episode} target_angle_degrees"
        )
        radius_bin = _classify_radius(radius)
        angle_sector = _classify_angle(angle)
        first_reach = _positive_int_or_none(
            diagnostic["first_reach_step"], f"episode {episode} first_reach_step"
        )
        max_held = _nonnegative_int(
            diagnostic["max_held_steps"], f"episode {episode} max_held_steps"
        )
        in_tolerance = _nonnegative_int(
            diagnostic["in_tolerance_steps"], f"episode {episode} in_tolerance_steps"
        )
        interruptions = _nonnegative_int(
            diagnostic["hold_interruptions"], f"episode {episode} hold_interruptions"
        )
        if first_reach is None and max_held != 0:
            raise ValueError(f"episode {episode} has held steps but no first reach")
        if first_reach is not None and max_held == 0:
            raise ValueError(f"episode {episode} has a first reach but no held steps")
        if first_reach is not None and first_reach > steps:
            raise ValueError(f"episode {episode} first reach is after episode end")
        if max_held > steps:
            raise ValueError(f"episode {episode} max held run exceeds episode length")
        if success and first_reach is None:
            raise ValueError(f"episode {episode} is successful but never reached")
        if in_tolerance > steps:
            raise ValueError(f"episode {episode} has more in-tolerance than control steps")

        open_steps = _nonnegative_int(
            diagnostic["open_branch_occupancy_steps"],
            f"episode {episode} open_branch_occupancy_steps",
        )
        folded_steps = _nonnegative_int(
            diagnostic["folded_branch_occupancy_steps"],
            f"episode {episode} folded_branch_occupancy_steps",
        )
        if open_steps + folded_steps != steps:
            raise ValueError(
                f"episode {episode} branch occupancy does not equal control steps"
            )
        for branch_fraction, branch_steps, field in (
            (
                diagnostic["open_branch_occupancy_fraction"],
                open_steps,
                "open_branch_occupancy_fraction",
            ),
            (
                diagnostic["folded_branch_occupancy_fraction"],
                folded_steps,
                "folded_branch_occupancy_fraction",
            ),
        ):
            if not math.isclose(
                _finite_number(branch_fraction, f"episode {episode} {field}"),
                branch_steps / steps,
                rel_tol=1e-9,
                abs_tol=1e-9,
            ):
                raise ValueError(f"episode {episode} has an inconsistent {field}")

        switches = _nonnegative_int(
            diagnostic["branch_switches"], f"episode {episode} branch_switches"
        )
        if switches > steps - 1:
            raise ValueError(f"episode {episode} has too many branch switches")
        allowed_branches = {"open", "folded", None}
        first_branch = diagnostic["branch_at_first_reach"]
        max_branch = diagnostic["branch_at_max_held_run"]
        if first_branch not in allowed_branches or max_branch not in allowed_branches:
            raise ValueError(f"episode {episode} has an invalid branch attribution")
        if (first_reach is None) != (first_branch is None):
            raise ValueError(f"episode {episode} has inconsistent first-reach attribution")
        if (max_held == 0) != (max_branch is None):
            raise ValueError(f"episode {episode} has inconsistent max-held attribution")
        for field in (
            "min_distance_cm",
            "final_distance_cm",
            "min_open_branch_error_norm",
            "min_folded_branch_error_norm",
        ):
            value = _finite_number(diagnostic[field], f"episode {episode} {field}")
            if field.endswith("error_norm") and value < 0:
                raise ValueError(f"episode {episode} {field} must be non-negative")

        rows.append(
            {
                "episode": episode,
                "success": success,
                "steps": steps,
                "radius_bin": radius_bin,
                "angle_sector": angle_sector,
                "first_reach_step": first_reach,
                "max_held_steps": max_held,
                "hold_interruptions": interruptions,
                "open_branch_occupancy_steps": open_steps,
                "folded_branch_occupancy_steps": folded_steps,
                "branch_switches": switches,
                "branch_at_first_reach": first_branch,
                "branch_at_max_held_run": max_branch,
            }
        )
    return rows


def _branch_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    denominator = len(rows)
    total_steps = sum(row["steps"] for row in rows)
    open_steps = sum(row["open_branch_occupancy_steps"] for row in rows)
    folded_steps = sum(row["folded_branch_occupancy_steps"] for row in rows)

    def attribution(field: str) -> dict[str, Any]:
        counts = {
            branch: sum(row[field] == branch for row in rows)
            for branch in ("open", "folded")
        }
        counts["null"] = sum(row[field] is None for row in rows)
        return {
            "counts": counts,
            "denominator": denominator,
            "non_null_denominator": denominator - counts["null"],
            "open_fraction_of_non_null": _rate(
                counts["open"], denominator - counts["null"]
            ),
            "folded_fraction_of_non_null": _rate(
                counts["folded"], denominator - counts["null"]
            ),
        }

    switches = [row["branch_switches"] for row in rows]
    return {
        "episode_denominator": denominator,
        "occupancy_denominator_steps": total_steps,
        "occupancy": {
            "open_steps": open_steps,
            "folded_steps": folded_steps,
            "open_fraction": _rate(open_steps, total_steps),
            "folded_fraction": _rate(folded_steps, total_steps),
        },
        "branch_at_first_reach": attribution("branch_at_first_reach"),
        "branch_at_max_held_run": attribution("branch_at_max_held_run"),
        "branch_switches": {
            "total": sum(switches),
            "episodes_with_switches": sum(value > 0 for value in switches),
            "denominator": denominator,
            "mean_per_episode": _rate(sum(switches), denominator),
        },
    }


def _group_summaries(rows: list[dict[str, Any]], field: str, labels: tuple[str, ...]) -> dict[str, Any]:
    return {
        label: _outcome_summary([row for row in rows if row[field] == label])
        for label in labels
    }


def analyze_artifact(input_path: Path) -> dict[str, Any]:
    """Load and analyze one schema-6 development artifact without rewriting it."""
    with input_path.open("r", encoding="utf-8") as handle:
        artifact = json.load(handle)
    if not isinstance(artifact, dict):
        raise ValueError("the input JSON root must be an object")

    rows = _validate_artifact(artifact)
    failures = [row for row in rows if not row["success"]]
    reached_failures = [row for row in failures if row["first_reach_step"] is not None]
    return {
        "analysis": "research_evaluation_mechanisms",
        "analysis_version": 1,
        "evidence_status": (
            "development evidence only; this analysis is not official certification"
        ),
        "source_artifact": str(input_path),
        "validated_schema_version": 6,
        "validated_episode_count": len(rows),
        "overall": _outcome_summary(rows),
        "radius_bins": _group_summaries(
            rows, "radius_bin", tuple(item[0] for item in RADIUS_BINS)
        ),
        "angle_sectors": _group_summaries(
            rows, "angle_sector", tuple(item[0] for item in ANGLE_SECTORS)
        ),
        "reached_failure_summaries": {
            "denominator": len(reached_failures),
            "max_held_steps": _numeric_summary(
                [row["max_held_steps"] for row in reached_failures]
            ),
            "hold_interruptions": _numeric_summary(
                [row["hold_interruptions"] for row in reached_failures]
            ),
            "episodes_with_hold_interruptions": sum(
                row["hold_interruptions"] > 0 for row in reached_failures
            ),
        },
        "branch_summaries": {
            "overall": _branch_summary(rows),
            "failures": _branch_summary(failures),
        },
    }


def write_analysis(input_path: Path, output_path: Path) -> dict[str, Any]:
    result = analyze_artifact(input_path)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_json", type=Path)
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args(argv)
    write_analysis(args.input_json, args.output_json)


if __name__ == "__main__":
    main()
