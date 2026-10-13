"""Small, artifact-independent checks for the full-radius analysis.

This is a laboratory verification proposal.  It uses controlled records and
can also exercise the complete in-memory production analysis path without
requiring a completed campaign artifact.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from robot_learning.lab.analyze_full_radius_comparison import (
    analyze_documents,
    radius_stratum,
)


def _diagnostic(
    episode: int,
    radius: float,
    *,
    first_reach_step: int | None,
    branch: str | None,
    hold_interruptions: int,
    rollout_margin: float | None = 0.2,
    speed: float | None = 1.0,
    action: float | None = 0.5,
    substep: float | None = 1.2,
    substep_above: float | None = 1.1,
    above_count: int = 1,
) -> dict[str, Any]:
    branch_record = {
        "joint_angles_rad": [0.1, 0.2],
        "joint_limit_margins_rad": [0.3, 0.4],
        "minimum_joint_limit_margin_rad": 0.3,
    }
    return {
        "episode": episode,
        "target_radius_cm": radius,
        "first_reach_step": first_reach_step,
        "hold_interruptions": hold_interruptions,
        "target_ik_branches": {
            "open": branch_record,
            "folded": None,
        },
        "nearest_target_ik_branch_at_first_entry": (
            None
            if branch is None
            else {"branch": branch, "configuration_distance_rad": 0.1}
        ),
        "min_joint_limit_margin_rad": rollout_margin,
        "max_joint_speed_norm_rad_per_s": speed,
        "max_absolute_action": action,
        "max_internal_substep_distance_cm": substep,
        "max_internal_substep_distance_above_threshold_cm": substep_above,
        "internal_substeps_above_threshold": above_count,
    }


def _document(
    successes: list[bool],
    radii: list[float],
    diagnostics: list[dict[str, Any]],
    *,
    seed: int = 5000,
) -> dict[str, Any]:
    return {
        "schema_version": 5,
        "episodes": len(successes),
        "seed": seed,
        "model": "controlled",
        "episode_results": [
            {
                "episode": episode,
                "episode_seed": seed + episode,
                "success": success,
            }
            for episode, success in enumerate(successes)
        ],
        "research_evidence": {
            "episode_diagnostics": diagnostics,
            "units": {"distance": "cm"},
        },
    }


def _controlled_pair() -> tuple[dict[str, Any], dict[str, Any]]:
    radii = [6.0, 10.0, 14.0, 17.0, 20.0]
    candidate_diagnostics = [
        _diagnostic(
            episode,
            radius,
            first_reach_step=None if episode in (0, 2) else 4,
            branch=None if episode in (0, 2) else ("open" if episode == 1 else "folded"),
            hold_interruptions=1 if episode == 3 else 0,
            above_count=episode,
        )
        for episode, radius in enumerate(radii)
    ]
    reference_diagnostics = [
        _diagnostic(
            episode,
            radius,
            first_reach_step=None if episode == 0 else 5,
            branch=None if episode == 0 else "open",
            hold_interruptions=0,
            rollout_margin=0.1,
            speed=2.0,
            action=0.7,
            substep=1.4,
            substep_above=1.3,
            above_count=2,
        )
        for episode, radius in enumerate(radii)
    ]
    # Candidate wins: episodes 1 and 3.  Reference wins: episode 4.
    return (
        _document([False, True, False, True, False], radii, candidate_diagnostics),
        _document([False, False, False, True, True], radii, reference_diagnostics),
    )


def run_checks() -> dict[str, Any]:
    """Check boundaries, null handling, discordance, and summary arithmetic."""
    expected_boundaries = {
        6.0: "[6,10)",
        9.999999: "[6,10)",
        10.0: "[10,14)",
        13.999999: "[10,14)",
        14.0: "[14,17)",
        16.999999: "[14,17)",
        17.0: "[17,20]",
        20.0: "[17,20]",
    }
    for radius, expected in expected_boundaries.items():
        actual = radius_stratum(radius)
        if actual != expected:
            raise AssertionError(f"radius boundary {radius}: {actual} != {expected}")

    candidate, reference = _controlled_pair()
    comparison = analyze_documents(candidate, reference)
    overall = comparison["overall"]
    if overall["candidate"] != {"episodes": 5, "successes": 2, "success_percent": 40.0}:
        raise AssertionError("candidate overall arithmetic is incorrect")
    if overall["reference"] != {"episodes": 5, "successes": 2, "success_percent": 40.0}:
        raise AssertionError("reference overall arithmetic is incorrect")
    if overall["paired_discordance"] != {
        "candidate_wins": 1,
        "reference_wins": 1,
        "ties": 3,
        "discordant": 2,
    }:
        raise AssertionError("paired discordance arithmetic is incorrect")

    strata = comparison["radius_strata"]
    if [item["stratum"] for item in strata] != [
        "[6,10)",
        "[10,14)",
        "[14,17)",
        "[17,20]",
    ]:
        raise AssertionError("radius strata are not ordered as specified")
    if strata[0]["candidate"]["episodes"] != 2 or strata[0]["candidate"]["successes"] != 1:
        raise AssertionError("stratum [6,10) arithmetic is incorrect")
    if comparison["candidate"]["failures"] != {
        "no_entry_failures": 2,
        "post_entry_unsuccessful": 1,
        "hold_interruption_count": 1,
        "episodes_with_hold_interruptions": 1,
    }:
        raise AssertionError("null-safe failure classification is incorrect")
    if comparison["candidate"]["branch_at_first_entry"] != {
        "open": 1,
        "folded": 2,
        "null": 2,
    }:
        raise AssertionError("null-safe branch counting is incorrect")
    if comparison["candidate"]["first_entry"]["rate_percent"] != 60.0:
        raise AssertionError("first-entry rate arithmetic is incorrect")
    if (
        comparison["candidate"]["joint_limit_margin"]["target"]["open"]["mean"] != 0.3
        or comparison["candidate"]["joint_speed_and_action"][
            "max_joint_speed_norm_rad_per_s"
        ]["max"]
        != 1.0
        or comparison["candidate"]["joint_speed_and_action"]["max_absolute_action"]["max"]
        != 0.5
    ):
        raise AssertionError("joint-limit, speed, or action summaries are incorrect")
    if comparison["candidate"]["joint_limit_margin"]["rollout"]["mean"] != 0.2:
        raise AssertionError("rollout margin summary arithmetic is incorrect")
    if (
        comparison["candidate"]["internal_substeps"]["max_distance_cm"]["max"] != 1.2
        or comparison["candidate"]["internal_substeps"]["above_threshold_count"] != 10
    ):
        raise AssertionError("substep threshold count arithmetic is incorrect")
    malformed_reference = {
        **reference,
        "episode_results": [
            {**record, "episode_seed": 9999}
            if record["episode"] == 1
            else record
            for record in reference["episode_results"]
        ],
    }
    try:
        analyze_documents(candidate, malformed_reference)
    except ValueError:
        pass
    else:
        raise AssertionError("mismatched paired artifacts were not rejected")
    return {
        "status": "passed",
        "checks": [
            "radius boundary stratification",
            "null-safe failure and branch classification",
            "paired discordance",
            "summary arithmetic",
            "malformed pair rejection",
        ],
    }


def run_compatibility_check() -> dict[str, Any]:
    """Exercise the complete production analysis path with controlled data."""
    candidate, reference = _controlled_pair()
    comparison = analyze_documents(candidate, reference)
    if comparison["schema_version"] != 1:
        raise AssertionError("production analysis did not emit its schema version")
    if len(comparison["radius_strata"]) != 4:
        raise AssertionError("production analysis did not emit all radius strata")
    if comparison["overall"]["paired_discordance"]["discordant"] != 2:
        raise AssertionError("production-path discordance is incorrect")
    return {
        "status": "passed",
        "checks": [
            "in-memory evaluator-document validation",
            "production analysis assembly without campaign artifacts",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--compatibility", action="store_true")
    args = parser.parse_args()
    result = run_compatibility_check() if args.compatibility else run_checks()
    args.artifact.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
