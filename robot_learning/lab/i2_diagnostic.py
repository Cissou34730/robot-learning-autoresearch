"""Bounded analysis for the I2 intervention evaluation."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def load_evaluation(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        evaluation = json.load(handle)
    diagnostics = evaluation.get("research_evidence", {}).get(
        "episode_diagnostics"
    )
    results = evaluation.get("episode_results")
    if not isinstance(diagnostics, list) or not isinstance(results, list):
        raise TypeError(f"{path} does not contain research evaluation evidence")
    if len(diagnostics) != len(results):
        raise ValueError(f"{path} has mismatched outcome and diagnostic counts")
    return evaluation


def angle_bin(angle_degrees: float) -> str:
    normalized = (angle_degrees + 180.0) % 360.0 - 180.0
    lower = -180.0 + 30.0 * int((normalized + 180.0) // 30.0)
    return f"{lower:.0f}..{lower + 30.0:.0f}deg"


def group_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    successes = sum(bool(row["success"]) for row in rows)
    reached = sum(row["first_reach_step"] is not None for row in rows)
    return {
        "episodes": len(rows),
        "successes": successes,
        "success_percent": 100.0 * successes / len(rows),
        "first_reach_count": reached,
        "first_reach_percent": 100.0 * reached / len(rows),
        "mean_first_reach_step": (
            sum(
                row["first_reach_step"]
                for row in rows
                if row["first_reach_step"] is not None
            )
            / reached
            if reached
            else None
        ),
        "mean_max_held_steps": sum(row["max_held_steps"] for row in rows)
        / len(rows),
        "interruption_classes": dict(
            sorted(Counter(row["interruption_class"] for row in rows).items())
        ),
    }


def analyze_candidate(
    evaluation: dict[str, Any], candidate: str
) -> dict[str, Any]:
    results_by_episode = {
        int(row["episode"]): row for row in evaluation["episode_results"]
    }
    rows: list[dict[str, Any]] = []
    branch_patterns: Counter[str] = Counter()
    for diagnostic in evaluation["research_evidence"]["episode_diagnostics"]:
        episode = int(diagnostic["episode"])
        branches = diagnostic["analytic_branches"]
        pattern = branches["pattern"]
        branch_patterns[pattern] += 1
        result = results_by_episode[episode]
        rows.append(
            {
                "episode": episode,
                "episode_seed": int(diagnostic["episode_seed"]),
                "success": bool(result["success"]),
                "target_radius_cm": float(diagnostic["target_radius_cm"]),
                "target_angle_degrees": float(
                    diagnostic["target_angle_degrees"]
                ),
                "first_reach_step": diagnostic["first_reach_step"],
                "max_held_steps": int(diagnostic["max_held_steps"]),
                "interruption_class": diagnostic["interruption_class"],
                "branch_pattern": pattern,
                "open_branch_feasible": bool(branches["open"]["feasible"]),
                "folded_branch_feasible": bool(
                    branches["folded"]["feasible"]
                ),
            }
        )

    by_angle: dict[str, list[dict[str, Any]]] = {}
    by_pattern: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_angle.setdefault(angle_bin(row["target_angle_degrees"]), []).append(
            row
        )
        by_pattern.setdefault(row["branch_pattern"], []).append(row)

    return {
        "candidate": candidate,
        "episodes": len(rows),
        "success_percent": 100.0
        * sum(row["success"] for row in rows)
        / len(rows),
        "interruption_classes": dict(
            sorted(Counter(row["interruption_class"] for row in rows).items())
        ),
        "branch_patterns": dict(sorted(branch_patterns.items())),
        "angle_conditioned": {
            key: group_summary(by_angle[key]) for key in sorted(by_angle)
        },
        "branch_conditioned": {
            key: group_summary(by_pattern[key]) for key in sorted(by_pattern)
        },
    }


def analyze(
    intervention: tuple[str, Path], reference: tuple[str, Path]
) -> dict[str, Any]:
    intervention_name, intervention_path = intervention
    reference_name, reference_path = reference
    intervention_eval = load_evaluation(intervention_path)
    reference_eval = load_evaluation(reference_path)
    intervention_results = {
        int(row["episode_seed"]): bool(row["success"])
        for row in intervention_eval["episode_results"]
    }
    reference_results = {
        int(row["episode_seed"]): bool(row["success"])
        for row in reference_eval["episode_results"]
    }
    if set(intervention_results) != set(reference_results):
        raise ValueError("paired evaluations do not use the same episode seeds")
    discordant = [
        seed
        for seed in sorted(intervention_results)
        if intervention_results[seed] != reference_results[seed]
    ]
    return {
        "schema_version": 1,
        "inquiry": "I2",
        "intervention": analyze_candidate(intervention_eval, intervention_name),
        "reference": analyze_candidate(reference_eval, reference_name),
        "paired": {
            "episodes": len(intervention_results),
            "discordant_episodes": len(discordant),
            "intervention_wins": sum(
                intervention_results[seed] and not reference_results[seed]
                for seed in intervention_results
            ),
            "reference_wins": sum(
                reference_results[seed] and not intervention_results[seed]
                for seed in intervention_results
            ),
            "discordant_episode_seeds": discordant,
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
    parser.add_argument("--intervention", type=parse_input, required=True)
    parser.add_argument("--reference", type=parse_input, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.intervention, args.reference)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
