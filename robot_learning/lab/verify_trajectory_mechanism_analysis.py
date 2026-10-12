"""Executable laboratory check for trajectory-mechanism post-processing.

This check uses controlled synthetic traces.  It checks the production
analysis path, not scientific validity, and writes only a compact JSON result.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from robot_learning.lab.analyze_trajectory_mechanism import analyze_document


def _row(
    step: int,
    *,
    rank: int,
    condition: float | None,
    qvel: list[float],
    action: list[float] | None,
    radial: float | None,
    tangential: float | None,
    margin: float,
    held: int,
    in_tolerance: bool,
    physics: list[float],
) -> dict[str, Any]:
    return {
        "control_step": step,
        "qpos_rad": [0.0, 0.0],
        "qvel_rad_per_s": qvel,
        "applied_clipped_action": action,
        "jacobian": {
            "rank": rank,
            "rank_deficient": rank < 2,
            "condition_number": condition,
        },
        "radial_cartesian_velocity_m_per_s": radial,
        "tangential_cartesian_velocity_m_per_s": tangential,
        "joint_limit_margin_rad": margin,
        "held_steps": held,
        "in_tolerance": in_tolerance,
        "physics_step_distances_cm": physics,
    }


def _diagnostic(
    episode: int,
    radius: float,
    angle: float,
    first_reach: int | None,
    max_held: int,
    trace: list[dict[str, Any]],
    branches: list[str] | None | object,
) -> dict[str, Any]:
    diagnostic: dict[str, Any] = {
        "episode": episode,
        "target_radius_cm": radius,
        "target_angle_degrees": angle,
        "first_reach_step": first_reach,
        "max_held_steps": max_held,
        # Deliberately untrusted endpoint summaries.  The production analysis
        # must obtain the requested quantities from trajectory_trace instead.
        "max_joint_speed_norm_rad_per_s": -999.0,
        "max_physics_step_distance_cm": -999.0,
        "trajectory_trace": trace,
    }
    if branches is not _MISSING:
        diagnostic["ik_branch_context"] = (
            None
            if branches is None
            else {"target": {"feasible_branches": branches}}
        )
    return diagnostic


_MISSING = object()


def _artifact() -> dict[str, Any]:
    success_trace = [
        _row(0, rank=1, condition=None, qvel=[0.0, 0.0], action=None, radial=None, tangential=None, margin=0.5, held=0, in_tolerance=False, physics=[]),
        _row(1, rank=2, condition=4.0, qvel=[1.0, 0.0], action=[1.0, -0.25], radial=None, tangential=None, margin=0.2, held=0, in_tolerance=False, physics=[1.0, 2.0]),
        _row(2, rank=2, condition=2.0, qvel=[3.0, 4.0], action=[0.5, -1.0], radial=-0.2, tangential=0.3, margin=0.1, held=1, in_tolerance=True, physics=[2.0, 1.0]),
        _row(3, rank=2, condition=1.0, qvel=[0.0, 6.0], action=[0.5, -1.0], radial=0.4, tangential=-0.5, margin=0.2, held=100, in_tolerance=True, physics=[3.0]),
    ]
    reached_trace = [
        _row(0, rank=1, condition=None, qvel=[0.0, 0.0], action=None, radial=None, tangential=None, margin=0.4, held=0, in_tolerance=False, physics=[]),
        _row(1, rank=2, condition=3.0, qvel=[1.0, 2.0], action=[0.1, 0.2], radial=0.1, tangential=0.4, margin=0.05, held=1, in_tolerance=True, physics=[0.5]),
        _row(2, rank=2, condition=2.0, qvel=[0.0, 1.0], action=[0.2, 0.3], radial=None, tangential=None, margin=0.08, held=0, in_tolerance=False, physics=[4.0]),
    ]
    never_trace = [
        _row(0, rank=1, condition=None, qvel=[0.0, 0.0], action=None, radial=None, tangential=None, margin=0.3, held=0, in_tolerance=False, physics=[]),
        _row(1, rank=1, condition=None, qvel=[0.0, 1.0], action=[0.0, 0.0], radial=0.2, tangential=0.3, margin=0.2, held=0, in_tolerance=False, physics=[1.0]),
        _row(2, rank=2, condition=5.0, qvel=[0.0, 2.0], action=[0.5, 0.0], radial=0.3, tangential=None, margin=0.15, held=0, in_tolerance=False, physics=[2.0]),
    ]
    return {
        "schema_version": 7,
        "model": "synthetic-policy.zip",
        "episodes": 3,
        "seed": 11,
        "official_benchmark": False,
        "success_percent": 33.333333333333336,
        "episode_results": [
            {"episode": 0, "success": True},
            {"episode": 1, "success": False},
            {"episode": 2, "success": False},
        ],
        "research_evidence": {
            "episode_diagnostics": [
                _diagnostic(0, 8.0, -170.0, 2, 100, success_trace, ["open", "folded"]),
                _diagnostic(1, 15.0, 20.0, 1, 1, reached_trace, ["open"]),
                _diagnostic(2, 19.0, 100.0, None, 0, never_trace, None),
            ]
        },
    }


def _must_fail(document: dict[str, Any], expected_text: str) -> str:
    try:
        analyze_document(document)
    except ValueError as error:
        if expected_text not in str(error):
            raise AssertionError(
                f"malformed-input error did not mention {expected_text!r}: {error}"
            ) from error
        return str(error)
    raise AssertionError("malformed input was accepted")


def run_check() -> dict[str, Any]:
    document = _artifact()
    report = analyze_document(document)
    profiles = {profile["episode"]: profile for profile in report["episode_profiles"]}
    success = profiles[0]["trajectory"]
    reached = profiles[1]["trajectory"]
    never = profiles[2]["trajectory"]

    assert report["input_episode_count"] == 3
    assert [profile["classification"] for profile in report["episode_profiles"]] == [
        "success",
        "reached_but_not_complete",
        "never_reached",
    ]
    assert report["class_summaries"]["never_reached"]["count"] == 1
    assert report["class_summaries"]["reached_but_not_complete"]["count"] == 1
    assert success["reset_jacobian_rank"] == 1
    assert success["first_full_planar_rank_control_step"] == 1
    assert success["condition_number_finite_values"]["available_count"] == 3
    assert success["condition_number_finite_values"]["missing_or_null_count"] == 1
    assert success["signed_radial_velocity_m_per_s"]["available_count"] == 2
    assert success["absolute_tangential_velocity_m_per_s"]["maximum"] == 0.5
    assert success["max_qvel_norm_rad_per_s"] == 6.0
    assert success["max_qvel_norm_rad_per_s"] != -999.0
    assert success["max_absolute_applied_clipped_action"] == 1.0
    assert success["actuator_saturation"]["fraction_of_updated_rows"] == 1.0
    assert success["min_joint_limit_margin_rad"] == 0.1
    assert success["first_in_tolerance_control_step"] == 2
    assert success["maximum_held_steps"] == 100
    assert success["max_physics_step_distance_cm"] == 3.0
    assert success["max_physics_step_distance_cm"] != -999.0
    assert success["max_physics_step_distance_during_hold_cm"] == 3.0
    assert reached["max_physics_step_distance_cm"] == 4.0
    assert reached["max_physics_step_distance_during_hold_cm"] == 0.5
    assert never["first_full_planar_rank_control_step"] == 2
    assert report["overall"]["target_feasible_branch_counts"] == {
        "none": 0,
        "open+folded": 1,
        "open": 1,
        "folded": 0,
        "missing_or_null": 1,
    }
    assert report["panel_metadata"]["seed"] == 11

    missing_trace = copy.deepcopy(document)
    del missing_trace["research_evidence"]["episode_diagnostics"][2]["trajectory_trace"]
    missing_trace_error = _must_fail(missing_trace, "trajectory_trace")

    omitted_row = copy.deepcopy(document)
    omitted_row["research_evidence"]["episode_diagnostics"][0]["trajectory_trace"].pop(2)
    omitted_row_error = _must_fail(omitted_row, "control_step")

    reset_contamination = copy.deepcopy(document)
    reset_contamination["research_evidence"]["episode_diagnostics"][0]["trajectory_trace"][0]["qvel_rad_per_s"] = [100.0, 0.0]
    contaminated = analyze_document(reset_contamination)
    assert (
        contaminated["episode_profiles"][0]["trajectory"]["max_qvel_norm_rad_per_s"]
        == 100.0
    )

    return {
        "check": "trajectory_mechanism_analysis",
        "status": "passed",
        "observed": {
            "episode_classes": {
                "success": 1,
                "reached_but_not_complete": 1,
                "never_reached": 1,
            },
            "trace_derived_success_max_qvel": success["max_qvel_norm_rad_per_s"],
            "trace_derived_success_max_physics_distance_cm": success[
                "max_physics_step_distance_cm"
            ],
            "malformed_trace_rejected": True,
            "omitted_trace_row_rejected": True,
            "reset_row_included_in_trace_metrics": True,
        },
        "expected": {
            "trace_rows_drive_metrics": True,
            "null_velocity_and_condition_denominators_are_explicit": True,
            "branch_counts_include_missing_or_null": True,
            "reset_and_transition_rows_are_checked": True,
        },
        "checked_scope": [
            "Episode-key join and success/reached/never-reached classification.",
            "Repeated trace rows, reset row, rank transition, null velocities, and condition values.",
            "Trace-derived qvel, action saturation, joint margin, tolerance, and physics distances.",
            "Malformed and incomplete trace rejection.",
        ],
        "error_messages_observed": {
            "missing_trace": missing_trace_error,
            "omitted_row": omitted_row_error,
        },
        "unchecked_scope": [
            "Real evaluator artifact contents and panel representativeness.",
            "Official continuous-hold semantics between recorded boundaries.",
            "Causal interpretation or intervention selection.",
        ],
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="verification artifact path")
    args = parser.parse_args(argv)
    artifact = run_check()
    with Path(args.output).open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2, sort_keys=True)
        handle.write("\n")


if __name__ == "__main__":
    main()
