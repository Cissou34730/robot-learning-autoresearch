"""Aggregate synchronized reach-and-hold diagnostics for mechanism comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, median


def _summary(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"count": 0, "mean": None, "median": None}
    return {
        "count": len(values),
        "mean": float(mean(values)),
        "median": float(median(values)),
    }


def analyze(source: dict) -> dict:
    outcomes = {
        row["episode"]: bool(row["success"]) for row in source["episode_results"]
    }
    diagnostics = source["research_evidence"]["episode_diagnostics"]
    failures = [row for row in diagnostics if not outcomes[row["episode"]]]
    no_entry = [row for row in failures if row["first_reach_step"] is None]
    entered_failures = [row for row in failures if row["first_reach_step"] is not None]
    entered_successes = [
        row for row in diagnostics
        if outcomes[row["episode"]] and row["first_reach_step"] is not None
    ]

    no_entry_branch_status = {
        "at_least_one_feasible_branch": sum(
            max(row["branch_limit_margins_degrees"].values()) >= 0.0
            for row in no_entry
        ),
        "positive_branch_feasible": sum(
            row["branch_limit_margins_degrees"]["elbow_positive"] >= 0.0
            for row in no_entry
        ),
        "negative_only_feasible": sum(
            row["branch_limit_margins_degrees"]["elbow_positive"] < 0.0
            and row["branch_limit_margins_degrees"]["elbow_negative"] >= 0.0
            for row in no_entry
        ),
        "neither_branch_feasible": sum(
            max(row["branch_limit_margins_degrees"].values()) < 0.0
            for row in no_entry
        ),
    }

    return {
        "schema_version": 1,
        "source_episodes": len(diagnostics),
        "successes": sum(outcomes.values()),
        "failures": len(failures),
        "failure_decomposition": {
            "no_first_entry": len(no_entry),
            "entered_but_hold_incomplete": len(entered_failures),
            "entered_failure_with_interruptions": sum(
                row["hold_interruptions"] > 0 for row in entered_failures
            ),
        },
        "no_entry_branch_status": no_entry_branch_status,
        "first_entry_speed_m_s": {
            "successful_episodes": _summary(
                [row["first_entry_ee_speed_m_s"] for row in entered_successes]
            ),
            "failed_episodes": _summary(
                [row["first_entry_ee_speed_m_s"] for row in entered_failures]
            ),
        },
        "hold_interruptions": {
            "failed_episodes_total": sum(
                row["hold_interruptions"] > 0 for row in failures
            ),
            "failed_episodes_with_entry": sum(
                row["hold_interruptions"] > 0 for row in entered_failures
            ),
            "total": sum(row["hold_interruptions"] for row in failures),
        },
        "entered_episode_limit_and_action": {
            "successful_minimum_joint_limit_margin_degrees": _summary(
                [row["minimum_joint_limit_margin_degrees"] for row in entered_successes]
            ),
            "failed_minimum_joint_limit_margin_degrees": _summary(
                [row["minimum_joint_limit_margin_degrees"] for row in entered_failures]
            ),
            "successful_action_saturation_steps": _summary(
                [row["action_saturation_steps"] for row in entered_successes]
            ),
            "failed_action_saturation_steps": _summary(
                [row["action_saturation_steps"] for row in entered_failures]
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--artifact", required=True)
    args = parser.parse_args()

    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    artifact = Path(args.artifact)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(analyze(source), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
