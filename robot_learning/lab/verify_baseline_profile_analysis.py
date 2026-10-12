"""Defect-sensitive synthetic verification for baseline profile analysis.

The module is intended for the existing ``python_module`` instrument.  It
does not read a campaign artifact or assert a scientific conclusion.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from robot_learning.lab.analyze_baseline_profile import analyze_document


def _diagnostic(
    episode: int,
    radius: float,
    angle: float,
    *,
    first_reach: int | None,
    held: int | None,
    interruptions: int | None,
    target_branches: list[str] | None,
    first_branch: str | None,
    final_branch: str | None,
) -> dict[str, Any]:
    return {
        "episode": episode,
        "target_radius_cm": radius,
        "target_angle_degrees": angle,
        "min_distance_cm": radius / 10.0,
        "final_distance_cm": radius / 20.0,
        "first_reach_step": first_reach,
        "max_held_steps": held,
        "hold_interruptions": interruptions,
        "first_entry_joint_speed_norm_rad_per_s": (
            None if first_reach is None else float(first_reach)
        ),
        "max_joint_speed_norm_rad_per_s": float(radius),
        "first_entry_cartesian_speed_m_per_s": (
            None if first_reach is None else float(first_reach) / 10.0
        ),
        "max_cartesian_speed_m_per_s": float(radius) / 100.0,
        "min_joint_limit_margin_rad": float(episode + 1) / 100.0,
        "ik_branch_context": {
            "target": (
                None
                if target_branches is None
                else {"feasible_branches": target_branches}
            ),
            "first_entry": (
                None
                if first_branch is None
                else {"nearest_branch": first_branch}
            ),
            "final_boundary": (
                None
                if final_branch is None
                else {"nearest_branch": final_branch}
            ),
        },
    }


def _synthetic_artifact() -> dict[str, Any]:
    episodes = [
        (0, True),
        (1, False),
        (2, False),
        (3, True),
        (4, False),
        (5, False),
        (6, True),
        (7, False),
    ]
    # Deliberately reverse the outcome-table order relative to diagnostics.
    results = [
        {"episode": episode, "success": success}
        for episode, success in reversed(episodes)
    ]
    diagnostics = [
        _diagnostic(
            7, 16.999, 135.0, first_reach=7, held=50, interruptions=1,
            target_branches=["folded"], first_branch="folded", final_branch="folded",
        ),
        _diagnostic(
            2, 14.0, 0.0, first_reach=None, held=0, interruptions=0,
            target_branches=[], first_branch=None, final_branch=None,
        ),
        _diagnostic(
            5, 9.99, 179.999, first_reach=None, held=0, interruptions=0,
            target_branches=None, first_branch=None, final_branch=None,
        ),
        _diagnostic(
            0, 6.0, 180.0, first_reach=3, held=100, interruptions=0,
            target_branches=["open", "folded"], first_branch="open", final_branch="open",
        ),
        _diagnostic(
            4, 20.0, -180.0, first_reach=4, held=99, interruptions=2,
            target_branches=["open", "folded"], first_branch="folded", final_branch="open",
        ),
        _diagnostic(
            6, 13.999, -90.0, first_reach=6, held=100, interruptions=0,
            target_branches=["open"], first_branch="open", final_branch="open",
        ),
        _diagnostic(
            3, 17.0, 45.0, first_reach=2, held=100, interruptions=0,
            target_branches=["folded"], first_branch="folded", final_branch="folded",
        ),
        _diagnostic(
            1, 10.0, -135.0, first_reach=5, held=40, interruptions=2,
            target_branches=["open"], first_branch="open", final_branch="ambiguous",
        ),
    ]
    return {
        "episode_results": results,
        "research_evidence": {"episode_diagnostics": diagnostics},
    }


def _assert_equal(observed: Any, expected: Any, label: str) -> None:
    if observed != expected:
        raise AssertionError(f"{label}: observed {observed!r}, expected {expected!r}")


def _assert_close(observed: float, expected: float, label: str) -> None:
    if abs(observed - expected) > 1e-12:
        raise AssertionError(f"{label}: observed {observed!r}, expected {expected!r}")


def run_check() -> dict[str, Any]:
    first_input = _synthetic_artifact()
    first_report = analyze_document(first_input)
    second_report = analyze_document(copy.deepcopy(_synthetic_artifact()))

    expected_radius_counts = {
        "[6,10)": 2,
        "[10,14)": 2,
        "[14,17)": 2,
        "[17,20]": 2,
    }
    observed_radius_counts = {
        label: first_report["radius_strata"][label]["count"]
        for label in expected_radius_counts
    }
    _assert_equal(observed_radius_counts, expected_radius_counts, "radius bins")
    _assert_equal(
        first_report["angle_strata"]["[-180,-135)"]["count"],
        2,
        "+180/-180 angle wrapping",
    )
    _assert_equal(
        first_report["angle_strata"]["[-135,-90)"]["count"],
        1,
        "lower angle boundary",
    )
    _assert_equal(first_report["overall"]["count"], 8, "joined row count")
    _assert_equal(first_report["overall"]["successes"], 3, "outcome join successes")
    _assert_equal(first_report["overall"]["failures"], 5, "outcome join failures")
    _assert_equal(first_report["overall"]["first_reach_count"], 6, "first reach count")
    _assert_equal(first_report["overall"]["first_reach_rate"], 75.0, "first reach rate")
    _assert_equal(first_report["overall"]["never_reached_count"], 2, "never reached")
    _assert_equal(first_report["overall"]["complete_hold_count"], 3, "complete hold")
    _assert_equal(
        first_report["overall"]["reached_but_not_complete_count"],
        3,
        "reached but incomplete hold",
    )
    _assert_equal(first_report["overall"]["mean_first_reach_step"], 4.5, "reach mean")
    _assert_equal(first_report["overall"]["max_held_steps"], 100.0, "held maximum")
    _assert_equal(first_report["overall"]["mean_held_steps"], 61.125, "held mean")
    _assert_equal(first_report["overall"]["hold_interruptions"], 5, "interruptions")
    _assert_close(
        first_report["overall"]["mean_first_entry_joint_speed_norm_rad_per_s"],
        4.5,
        "first-entry joint speed",
    )
    _assert_close(
        first_report["overall"]["mean_max_joint_speed_norm_rad_per_s"],
        13.4985,
        "maximum joint speed",
    )
    _assert_close(
        first_report["overall"]["mean_max_cartesian_speed_m_per_s"],
        0.134985,
        "maximum Cartesian speed",
    )
    _assert_close(
        first_report["overall"]["mean_min_joint_limit_margin_rad"],
        0.045,
        "joint-limit margin",
    )
    _assert_equal(
        first_report["class_summaries"]["successes"]["count"], 3, "success class"
    )
    _assert_equal(
        first_report["class_summaries"]["failures"]["count"], 5, "failure class"
    )
    _assert_equal(
        first_report["class_summaries"]["never_reached"]["count"],
        2,
        "never-reached class",
    )
    _assert_equal(
        first_report["class_summaries"]["reached_but_not_complete"]["count"],
        3,
        "reached-incomplete class",
    )
    _assert_equal(
        first_report["branch_context_counts"]["target_feasible_branch_sets"],
        {"open+folded": 2, "none": 1, "missing_or_null": 1, "open": 2, "folded": 2},
        "target branch counts",
    )
    _assert_equal(
        first_report["branch_context_counts"]["first_entry_nearest_branch"],
        {"open": 3, "folded": 3, "missing_or_null": 2},
        "first-entry branch counts",
    )
    _assert_equal(
        first_report["branch_context_counts"]["final_boundary_nearest_branch"],
        {"open": 3, "folded": 2, "ambiguous": 1, "missing_or_null": 2},
        "final-boundary branch counts",
    )
    _assert_equal(first_report, second_report, "independent fresh invocation")

    return {
        "status": "passed",
        "observed": {
            "overall": first_report["overall"],
            "radius_counts": observed_radius_counts,
            "wrapped_angle_count": first_report["angle_strata"]["[-180,-135)"][
                "count"
            ],
            "branch_context_counts": first_report["branch_context_counts"],
        },
        "expected": {
            "overall_count": 8,
            "successes": 3,
            "failures": 5,
            "first_reach_count": 6,
            "never_reached_count": 2,
            "complete_hold_count": 3,
            "reached_but_not_complete_count": 3,
            "radius_counts": expected_radius_counts,
            "wrapped_angle_count": 2,
            "fresh_invocation_equal": True,
        },
        "checked_scope": [
            "radius edge inclusion and exclusion",
            "angle sector boundaries and +180 wrapping to -180",
            "episode-key outcome/diagnostic join with shuffled table order",
            "success/failure and reach/complete-hold classifications",
            "aggregate counts, rates, and means",
            "target, first-entry, and final-boundary branch counts",
            "independent fresh-input invocation without state carry-over",
        ],
        "unchecked_scope": [
            "the completed campaign artifact's full schema and values",
            "scientific validity or causal interpretation of any profile",
            "continuous within-frame hold behavior not present in the artifact",
        ],
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="verification artifact path")
    args = parser.parse_args(argv)
    result = run_check()
    with Path(args.output).open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")


if __name__ == "__main__":
    main()
