"""Bounded analysis for the I1 branch/limit versus hold inquiry."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from itertools import pairwise
from pathlib import Path
from typing import Any

UPPER_ARM_LENGTH = 0.12
FOREARM_LENGTH = 0.10
JOINT_LIMIT_DEGREES = 170.0
HOLD_STEPS_REQUIRED = 100


def wrap_to_pi(angle: float) -> float:
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def branch_solution(radius_m: float, angle_rad: float, elbow_sign: float) -> dict:
    cosine = (
        radius_m**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow = elbow_sign * math.acos(max(-1.0, min(1.0, cosine)))
    shoulder = angle_rad - math.atan2(
        FOREARM_LENGTH * math.sin(elbow),
        UPPER_ARM_LENGTH + FOREARM_LENGTH * math.cos(elbow),
    )
    shoulder_degrees = math.degrees(wrap_to_pi(shoulder))
    elbow_degrees = math.degrees(elbow)
    shoulder_margin = JOINT_LIMIT_DEGREES - abs(shoulder_degrees)
    elbow_margin = JOINT_LIMIT_DEGREES - abs(elbow_degrees)
    return {
        "shoulder_degrees": shoulder_degrees,
        "elbow_degrees": elbow_degrees,
        "shoulder_margin_degrees": shoulder_margin,
        "elbow_margin_degrees": elbow_margin,
        "minimum_margin_degrees": min(shoulder_margin, elbow_margin),
        "feasible": shoulder_margin >= 0.0 and elbow_margin >= 0.0,
    }


def load_evaluation(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        evaluation = json.load(handle)
    diagnostics = evaluation.get("research_evidence", {}).get("episode_diagnostics")
    results = evaluation.get("episode_results")
    if not isinstance(diagnostics, list) or not isinstance(results, list):
        raise TypeError(f"{path} does not contain the M1 episode evidence")
    if len(diagnostics) != len(results):
        raise ValueError(f"{path} has mismatched outcome and diagnostic counts")
    return evaluation


def interruption_class(result: dict[str, Any], diagnostic: dict[str, Any]) -> str:
    if bool(result["success"]):
        return "completed_hold"
    if diagnostic["first_reach_step"] is None:
        return "no_first_reach"
    if int(diagnostic["hold_interruptions"]) > 0:
        return "post_entry_interrupted_hold"
    return "post_entry_incomplete_hold"


def radius_bin(radius_cm: float) -> str:
    edges = (6.0, 10.0, 14.0, 17.0, 20.0)
    for lower, upper in pairwise(edges):
        if lower <= radius_cm < upper:
            return f"{lower:.0f}-{upper:.0f}cm"
    if radius_cm == edges[-1]:
        return f"{edges[-2]:.0f}-{edges[-1]:.0f}cm"
    raise ValueError(f"radius outside official range: {radius_cm}")


def angle_bin(angle_degrees: float) -> str:
    normalized = (angle_degrees + 180.0) % 360.0 - 180.0
    lower = -180.0 + 30.0 * math.floor((normalized + 180.0) / 30.0)
    upper = lower + 30.0
    return f"{lower:.0f}..{upper:.0f}deg"


def summarize_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    successes = sum(bool(row["success"]) for row in rows)
    reached = sum(row["first_reach_step"] is not None for row in rows)
    return {
        "episodes": len(rows),
        "successes": successes,
        "success_percent": 100.0 * successes / len(rows),
        "first_reach_count": reached,
        "first_reach_percent": 100.0 * reached / len(rows),
        "mean_first_reach_step": (
            sum(row["first_reach_step"] for row in rows if row["first_reach_step"] is not None)
            / reached
            if reached
            else None
        ),
        "mean_max_held_steps": sum(row["max_held_steps"] for row in rows) / len(rows),
        "maximum_observed_hold_steps": max(row["max_held_steps"] for row in rows),
        "interruption_classes": dict(
            sorted(Counter(row["interruption_class"] for row in rows).items())
        ),
    }


def analyze_candidate(evaluation: dict[str, Any], candidate: str) -> dict[str, Any]:
    results_by_episode = {
        int(row["episode"]): row for row in evaluation["episode_results"]
    }
    rows: list[dict[str, Any]] = []
    branch_counts = Counter()
    for diagnostic in evaluation["research_evidence"]["episode_diagnostics"]:
        episode = int(diagnostic["episode"])
        result = results_by_episode[episode]
        radius_cm = float(diagnostic["target_radius_cm"])
        angle_degrees = float(diagnostic["target_angle_degrees"])
        radius_m = radius_cm / 100.0
        angle_rad = math.radians(angle_degrees)
        open_branch = branch_solution(radius_m, angle_rad, 1.0)
        folded_branch = branch_solution(radius_m, angle_rad, -1.0)
        if open_branch["feasible"] and folded_branch["feasible"]:
            branch_pattern = "both_feasible"
        elif open_branch["feasible"]:
            branch_pattern = "open_only_feasible"
        elif folded_branch["feasible"]:
            branch_pattern = "folded_only_feasible"
        else:
            branch_pattern = "neither_feasible"
        branch_counts[branch_pattern] += 1
        rows.append(
            {
                "episode": episode,
                "episode_seed": int(diagnostic["episode_seed"]),
                "success": bool(result["success"]),
                "target_radius_cm": radius_cm,
                "target_angle_degrees": angle_degrees,
                "first_reach_step": diagnostic["first_reach_step"],
                "max_held_steps": int(diagnostic["max_held_steps"]),
                "hold_interruptions": int(diagnostic["hold_interruptions"]),
                "interruption_class": interruption_class(result, diagnostic),
                "open_branch": open_branch,
                "folded_branch": folded_branch,
                "branch_pattern": branch_pattern,
            }
        )

    grouped_radius: dict[str, list[dict[str, Any]]] = {}
    grouped_angle: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped_radius.setdefault(radius_bin(row["target_radius_cm"]), []).append(row)
        grouped_angle.setdefault(angle_bin(row["target_angle_degrees"]), []).append(row)

    return {
        "candidate": candidate,
        "episodes": len(rows),
        "success_percent": 100.0
        * sum(row["success"] for row in rows)
        / len(rows),
        "radius_conditioned": {
            key: summarize_group(grouped_radius[key])
            for key in sorted(
                grouped_radius,
                key=lambda value: float(value.split("-", 1)[0]),
            )
        },
        "angle_conditioned": {
            key: summarize_group(grouped_angle[key])
            for key in sorted(
                grouped_angle,
                key=lambda value: float(value.split("..", 1)[0]),
            )
        },
        "interruption_classes": dict(
            sorted(Counter(row["interruption_class"] for row in rows).items())
        ),
        "analytic_branch_margins": {
            "branch_counts": dict(sorted(branch_counts.items())),
            "open_branch_feasible_count": sum(
                row["open_branch"]["feasible"] for row in rows
            ),
            "folded_branch_feasible_count": sum(
                row["folded_branch"]["feasible"] for row in rows
            ),
            "failed_episode_branch_patterns": dict(
                sorted(
                    Counter(
                        row["branch_pattern"] for row in rows if not row["success"]
                    ).items()
                )
            ),
            "failed_episode_margin_rows": [
                {
                    "episode": row["episode"],
                    "episode_seed": row["episode_seed"],
                    "target_radius_cm": row["target_radius_cm"],
                    "target_angle_degrees": row["target_angle_degrees"],
                    "open_minimum_margin_degrees": row["open_branch"][
                        "minimum_margin_degrees"
                    ],
                    "folded_minimum_margin_degrees": row["folded_branch"][
                        "minimum_margin_degrees"
                    ],
                    "open_branch_feasible": row["open_branch"]["feasible"],
                    "folded_branch_feasible": row["folded_branch"]["feasible"],
                }
                for row in rows
                if not row["success"]
            ],
        },
    }


def analyze(inputs: list[tuple[str, Path]]) -> dict[str, Any]:
    evaluations = [(candidate, load_evaluation(path)) for candidate, path in inputs]
    if len(evaluations) != 2:
        raise ValueError("I1 requires exactly two candidate evaluations")
    first_results = evaluations[0][1]["episode_results"]
    second_results = evaluations[1][1]["episode_results"]
    first_outcomes = {
        int(row["episode_seed"]): bool(row["success"]) for row in first_results
    }
    second_outcomes = {
        int(row["episode_seed"]): bool(row["success"]) for row in second_results
    }
    if first_outcomes != second_outcomes:
        raise ValueError("I1 requires shared M1 episode outcomes")
    shared_failures = sorted(
        seed for seed, success in first_outcomes.items() if not success
    )
    return {
        "schema_version": 1,
        "inquiry": "I1",
        "episodes_per_candidate": len(first_results),
        "shared_failure_count": len(shared_failures),
        "shared_failure_episode_seeds": shared_failures,
        "candidates": [
            analyze_candidate(evaluation, candidate)
            for candidate, evaluation in evaluations
        ],
        "method": {
            "radius_bins_cm": [[6, 10], [10, 14], [14, 17], [17, 20]],
            "angle_bin_width_degrees": 30,
            "hold_steps_required": HOLD_STEPS_REQUIRED,
            "joint_limits_degrees": [-JOINT_LIMIT_DEGREES, JOINT_LIMIT_DEGREES],
            "branch_names": {
                "open": "positive-elbow",
                "folded": "negative-elbow",
            },
            "interruption_classes": [
                "completed_hold",
                "no_first_reach",
                "post_entry_interrupted_hold",
                "post_entry_incomplete_hold",
            ],
        },
    }


def parse_input(value: str) -> tuple[str, Path]:
    candidate, separator, path = value.partition("=")
    if not separator or not candidate or not path:
        raise argparse.ArgumentTypeError(
            "input must use CANDIDATE=PATH syntax"
        )
    return candidate, Path(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", type=parse_input, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
