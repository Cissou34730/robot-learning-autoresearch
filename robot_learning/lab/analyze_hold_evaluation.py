"""Analyze a research-evaluation artifact for reach, geometry, and hold failure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import fmean
from typing import Any


RADIUS_BINS = (
    ("0.06-0.10 m", 6.0, 10.0),
    ("0.10-0.14 m", 10.0, 14.0),
    ("0.14-0.18 m", 14.0, 18.0),
    ("0.18-0.20 m", 18.0, 20.01),
)
ANGLE_BINS = (
    ("-180--135 deg", -180.0, -135.0),
    ("-135--90 deg", -135.0, -90.0),
    ("-90--45 deg", -90.0, -45.0),
    ("-45-0 deg", -45.0, 0.0),
    ("0-45 deg", 0.0, 45.0),
    ("45-90 deg", 45.0, 90.0),
    ("90-135 deg", 90.0, 135.0),
    ("135-180 deg", 135.0, 180.01),
)
MARGIN_BINS = (
    ("<20 deg", float("-inf"), 20.0),
    ("20-40 deg", 20.0, 40.0),
    (">=40 deg", 40.0, float("inf")),
)


def _mean(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [float(row[field]) for row in rows if row.get(field) is not None]
    return fmean(values) if values else None


def _group_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    successes = sum(bool(row["success"]) for row in rows)
    reached = [row for row in rows if row["first_reach_step"] is not None]
    post_entry_failures = [
        row for row in reached if not bool(row["success"])
    ]
    timeouts = [row for row in rows if row["first_reach_step"] is None]
    return {
        "episodes": len(rows),
        "successes": successes,
        "success_percent": 100.0 * successes / len(rows) if rows else None,
        "first_entry_count": len(reached),
        "first_entry_percent": 100.0 * len(reached) / len(rows) if rows else None,
        "post_entry_failure_count": len(post_entry_failures),
        "timeout_count": len(timeouts),
        "mean_first_entry_step": _mean(rows, "first_reach_step"),
        "mean_max_held_steps": _mean(rows, "max_held_steps"),
        "mean_hold_interruptions": _mean(rows, "hold_interruptions"),
        "mean_peak_joint_speed": _mean(rows, "peak_joint_speed"),
        "mean_peak_endpoint_speed": _mean(rows, "peak_endpoint_speed"),
        "mean_peak_action_abs_max": _mean(rows, "peak_action_abs_max"),
        "mean_hold_peak_joint_speed": _mean(rows, "hold_peak_joint_speed"),
        "mean_hold_peak_endpoint_speed": _mean(rows, "hold_peak_endpoint_speed"),
        "mean_hold_peak_action_abs": _mean(rows, "hold_peak_action_abs"),
    }


def _bin_rows(
    rows: list[dict[str, Any]], field: str, bins: tuple[tuple[str, float, float], ...]
) -> list[dict[str, Any]]:
    result = []
    for label, lower, upper in bins:
        selected = [
            row
            for row in rows
            if lower <= float(row[field]) < upper
        ]
        result.append({"bin": label, **_group_summary(selected)})
    return result


def _failure_modes(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_cause: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_cause.setdefault(str(row["termination_cause"]), []).append(row)
    return {
        cause: _group_summary(cause_rows)
        for cause, cause_rows in sorted(by_cause.items())
    }


def analyze(source: Path, artifact: Path) -> None:
    evaluation = json.loads(source.read_text(encoding="utf-8"))
    results = evaluation["episode_results"]
    diagnostics = evaluation["research_evidence"]["episode_diagnostics"]
    if len(results) != len(diagnostics):
        raise ValueError("episode results and diagnostics have different lengths")

    rows = []
    for result, diagnostic in zip(results, diagnostics):
        if result["episode"] != diagnostic["episode"]:
            raise ValueError("episode result and diagnostic ordering differs")
        rows.append({**result, **diagnostic})

    output = {
        "schema_version": 1,
        "experiment": "hold_evaluation_failure_allocation",
        "source": str(source),
        "evaluation": {
            "episodes": len(rows),
            "successes": sum(bool(row["success"]) for row in rows),
            "success_percent": evaluation["success_percent"],
        },
        "overall": _group_summary(rows),
        "failure_modes": _failure_modes(rows),
        "by_radius": _bin_rows(rows, "target_radius_cm", RADIUS_BINS),
        "by_angle": _bin_rows(rows, "target_angle_degrees", ANGLE_BINS),
        "by_best_branch_margin": _bin_rows(
            rows,
            "best_joint_limit_margin_degrees",
            MARGIN_BINS,
        ),
        "comparison": {
            "successful_episodes": _group_summary(
                [row for row in rows if row["success"]]
            ),
            "post_entry_failures": _group_summary(
                [
                    row
                    for row in rows
                    if not row["success"] and row["first_reach_step"] is not None
                ]
            ),
            "maneuver_timeouts": _group_summary(
                [
                    row
                    for row in rows
                    if row["first_reach_step"] is None
                ]
            ),
        },
    }
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--artifact", required=True, type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    analyze(arguments.source, arguments.artifact)
