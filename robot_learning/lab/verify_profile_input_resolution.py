"""Focused verification for profile-input resolution and report compatibility.

The module is intended for the existing ``python_module`` instrument.  It
uses temporary synthetic artifacts and does not read campaign evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from robot_learning.lab.analyze_baseline_profile import (
    M27_T2_REFERENCE_FILENAME,
    M28_T2_PROFILE_FILENAME,
    M28_T2_ARTIFACT_FINGERPRINT,
    M30_T2_REFERENCE_FILENAME,
    analyze_document,
    analyze_path,
    resolve_profile_input,
)


def _synthetic_artifact() -> dict[str, Any]:
    return {
        "episode_results": [{"episode": 0, "success": True}],
        "research_evidence": {
            "episode_diagnostics": [
                {
                    "episode": 0,
                    "target_radius_cm": 10.0,
                    "target_angle_degrees": 0.0,
                    "min_distance_cm": 1.0,
                    "final_distance_cm": 1.0,
                    "first_reach_step": 1,
                    "max_held_steps": 100,
                    "hold_interruptions": 0,
                }
            ]
        },
    }


def _assert_equal(observed: Any, expected: Any, label: str) -> None:
    if observed != expected:
        raise AssertionError(f"{label}: observed {observed!r}, expected {expected!r}")


def _assert_raises_file_not_found(callable_: Any, label: str) -> None:
    try:
        callable_()
    except FileNotFoundError:
        return
    raise AssertionError(f"{label}: expected FileNotFoundError")


def run_compatibility_check() -> dict[str, Any]:
    """Exercise the changed path boundary without a campaign artifact."""
    with TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        exact_m30_path = directory / M30_T2_REFERENCE_FILENAME
        backslash_m30_text = str(exact_m30_path).replace("/", "\\")
        requested_path = Path(backslash_m30_text)

        resolved_path, source_kind = resolve_profile_input(backslash_m30_text)
        _assert_equal(
            resolved_path, requested_path, "compatibility snapshot resolution"
        )
        _assert_equal(
            source_kind,
            "m28_profile_snapshot_fallback",
            "compatibility snapshot source kind",
        )
        report = analyze_path(backslash_m30_text)
        expected_resolution = {
            "requested_path": str(requested_path),
            "resolved_path": str(requested_path),
            "fallback_used": True,
            "source_kind": "m28_profile_snapshot_fallback",
            "snapshot_used": True,
            "source_operation": "M28",
            "source_artifact_fingerprint": M28_T2_ARTIFACT_FINGERPRINT,
        }
        _assert_equal(
            report["source_resolution"],
            expected_resolution,
            "compatibility snapshot provenance",
        )

    return {
        "status": "passed",
        "observed": {
            "source_kind": source_kind,
            "source_resolution": report["source_resolution"],
        },
        "expected": {
            "source_kind": "m28_profile_snapshot_fallback",
            "backslash_form_exact_m30_path_is_accepted": True,
            "snapshot_provenance_is_emitted": True,
        },
        "checked_scope": [
            "backslash-form exact M30 T2 input at the production resolution boundary",
            "artifact-independent M28 snapshot fallback selection",
            "snapshot source provenance emitted by analyze_path",
        ],
        "unchecked_scope": [
            "sibling-file fallback behavior covered by the behavioral check",
            "completed campaign artifact schema and values",
            "scientific validity or interpretation of the profile",
        ],
        "execution_note": "This check has not been executed.",
    }


def run_check() -> dict[str, Any]:
    artifact = _synthetic_artifact()
    required_sections = (
        "overall",
        "radius_strata",
        "angle_strata",
        "class_summaries",
        "branch_context_counts",
    )
    with TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        present_path = directory / "present.json"
        present_path.write_text(json.dumps(artifact), encoding="utf-8")
        resolved_present, present_source_kind = resolve_profile_input(present_path)
        _assert_equal(resolved_present, present_path, "present-path resolution")
        _assert_equal(
            present_source_kind,
            "requested_evaluation",
            "present-path source kind",
        )

        m27_fallback_path = directory / M27_T2_REFERENCE_FILENAME
        m27_fallback_path.write_text(json.dumps(artifact), encoding="utf-8")
        requested_m30_path = directory / M30_T2_REFERENCE_FILENAME
        resolved_m27, m27_source_kind = resolve_profile_input(requested_m30_path)
        _assert_equal(
            resolved_m27, m27_fallback_path, "exact M30-to-M27 fallback"
        )
        _assert_equal(
            m27_source_kind,
            "m27_evaluation_fallback",
            "M27 fallback source kind",
        )

        m27_report = analyze_path(requested_m30_path)
        _assert_equal(
            m27_report["source_resolution"],
            {
                "requested_path": str(requested_m30_path),
                "resolved_path": str(m27_fallback_path),
                "fallback_used": True,
                "source_kind": "m27_evaluation_fallback",
            },
            "M27 fallback provenance",
        )

        m28_directory = directory / "with_m28_profile"
        m28_directory.mkdir()
        m28_profile_path = m28_directory / M28_T2_PROFILE_FILENAME
        profile_document = analyze_document(artifact)
        profile_document["overall"]["count"] = 999
        profile_document["profile_marker"] = "loaded_without_recomputation"
        m28_profile_path.write_text(
            json.dumps(profile_document), encoding="utf-8"
        )
        requested_m30_with_m28 = m28_directory / M30_T2_REFERENCE_FILENAME
        resolved_m28, m28_source_kind = resolve_profile_input(
            requested_m30_with_m28
        )
        _assert_equal(
            resolved_m28, m28_profile_path, "exact M30-to-M28 profile fallback"
        )
        _assert_equal(
            m28_source_kind,
            "m28_profile_fallback",
            "M28 fallback source kind",
        )
        m28_report = analyze_path(requested_m30_with_m28)
        _assert_equal(
            m28_report["overall"]["count"],
            999,
            "M28 profile loaded without recomputation",
        )
        _assert_equal(
            m28_report["profile_marker"],
            "loaded_without_recomputation",
            "M28 profile content preserved",
        )
        for section in required_sections:
            if section not in m28_report:
                raise AssertionError(
                    f"M28 profile section missing after fallback: {section}"
                )
        _assert_equal(
            m28_report["source_resolution"],
            {
                "requested_path": str(requested_m30_with_m28),
                "resolved_path": str(m28_profile_path),
                "fallback_used": True,
                "source_kind": "m28_profile_fallback",
            },
            "M28 fallback provenance",
        )

        missing_m30_directory = directory / "without_profile_files"
        missing_m30_directory.mkdir()
        missing_m30_path = missing_m30_directory / M30_T2_REFERENCE_FILENAME
        _assert_equal(
            missing_m30_path.exists(),
            False,
            "snapshot input is absent before fallback",
        )
        snapshot_report = analyze_path(missing_m30_path)
        _assert_equal(
            missing_m30_path.exists(),
            False,
            "snapshot fallback does not create an input file",
        )
        _assert_equal(
            snapshot_report["report_source"],
            "m28_profile_snapshot_fallback",
            "M28 snapshot report source",
        )
        _assert_equal(
            snapshot_report["source_operation"],
            "M28",
            "M28 snapshot operation provenance",
        )
        _assert_equal(
            snapshot_report["source_artifact_fingerprint"],
            M28_T2_ARTIFACT_FINGERPRINT,
            "M28 snapshot artifact provenance",
        )
        _assert_equal(
            snapshot_report["snapshot_used"],
            True,
            "M28 snapshot usage marker",
        )
        _assert_equal(
            snapshot_report["source_resolution"],
            {
                "requested_path": str(missing_m30_path),
                "resolved_path": str(missing_m30_path),
                "fallback_used": True,
                "source_kind": "m28_profile_snapshot_fallback",
                "snapshot_used": True,
                "source_operation": "M28",
                "source_artifact_fingerprint": M28_T2_ARTIFACT_FINGERPRINT,
            },
            "M28 snapshot provenance",
        )
        _assert_equal(
            snapshot_report["overall"]["count"],
            160,
            "M28 snapshot overall count",
        )
        _assert_equal(
            snapshot_report["overall"]["successes"],
            150,
            "M28 snapshot overall successes",
        )
        _assert_equal(
            snapshot_report["overall"]["first_reach_count"],
            153,
            "M28 snapshot overall first reaches",
        )
        _assert_equal(
            snapshot_report["radius_strata"]["[14,17)"],
            {
                "count": 31,
                "successes": 28,
                "complete_hold_count": 28,
                "first_reach_count": 29,
            },
            "M28 snapshot radius strata",
        )
        _assert_equal(
            snapshot_report["angle_strata"]["[-180,-135)"]["first_reach_count"],
            22,
            "M28 snapshot [-180,-135) first reaches",
        )
        _assert_equal(
            snapshot_report["angle_strata"]["[-45,0)"]["first_reach_count"],
            11,
            "M28 snapshot [-45,0) first reaches",
        )
        _assert_equal(
            snapshot_report["angle_strata"]["[-135,-90)"],
            {
                "count": 26,
                "successes": 23,
                "complete_hold_count": 23,
                "first_reach_count": 23,
                "never_reached_count": 3,
            },
            "M28 snapshot angle strata",
        )
        _assert_equal(
            snapshot_report["class_summaries"]["reached_but_not_complete"][
                "count"
            ],
            3,
            "M28 snapshot class count",
        )
        _assert_equal(
            snapshot_report["branch_context_counts"][
                "target_feasible_branch_sets"
            ],
            {"folded": 14, "open": 6, "open+folded": 140},
            "M28 snapshot branch counts",
        )

        backslash_m30_text = str(missing_m30_path).replace("/", "\\")
        backslash_m30_path = Path(backslash_m30_text)
        resolved_backslash_m30, backslash_m30_source_kind = resolve_profile_input(
            backslash_m30_text
        )
        _assert_equal(
            resolved_backslash_m30,
            backslash_m30_path,
            "backslash-form exact M30 snapshot resolution",
        )
        _assert_equal(
            backslash_m30_source_kind,
            "m28_profile_snapshot_fallback",
            "backslash-form M28 snapshot source kind",
        )
        backslash_snapshot_report = analyze_path(backslash_m30_text)
        _assert_equal(
            backslash_snapshot_report["source_resolution"],
            {
                "requested_path": str(backslash_m30_path),
                "resolved_path": str(backslash_m30_path),
                "fallback_used": True,
                "source_kind": "m28_profile_snapshot_fallback",
                "snapshot_used": True,
                "source_operation": "M28",
                "source_artifact_fingerprint": M28_T2_ARTIFACT_FINGERPRINT,
            },
            "backslash-form M28 snapshot provenance",
        )

        non_m30_missing_path = directory / "missing.json"
        _assert_raises_file_not_found(
            lambda: resolve_profile_input(non_m30_missing_path),
            "non-M30 missing input",
        )
        unrelated_missing_path = directory / "unrelated.json"
        _assert_raises_file_not_found(
            lambda: resolve_profile_input(unrelated_missing_path),
            "unrelated missing input",
        )

        observed = {
            "present_resolution": {
                "resolved_path": str(resolved_present),
                "fallback_used": False,
                "source_kind": present_source_kind,
            },
            "m27_fallback_resolution": {
                "resolved_path": str(resolved_m27),
                "source_kind": m27_source_kind,
            },
            "m27_report_source_resolution": m27_report[
                "source_resolution"
            ],
            "m28_fallback_resolution": {
                "resolved_path": str(resolved_m28),
                "source_kind": m28_source_kind,
            },
            "m28_report_source_resolution": m28_report[
                "source_resolution"
            ],
            "backslash_m30_snapshot_source_resolution": backslash_snapshot_report[
                "source_resolution"
            ],
            "m28_preserved_profile_marker": m28_report["profile_marker"],
            "m28_snapshot_corrected_first_reach_counts": {
                "[-180,-135)": snapshot_report["angle_strata"]["[-180,-135)"][
                    "first_reach_count"
                ],
                "[-45,0)": snapshot_report["angle_strata"]["[-45,0)"][
                    "first_reach_count"
                ],
            },
            "rejected_missing_inputs": 2,
            "analysis_sections": list(required_sections),
        }

    return {
        "status": "passed",
        "observed": observed,
        "expected": {
            "present_path_uses_requested_file": True,
            "exact_m30_path_uses_m27_sibling_only_when_present": True,
            "exact_m30_path_uses_m28_profile_only_when_m27_is_absent": True,
            "m28_profile_is_loaded_without_recomputation": True,
            "missing_exact_m30_path_uses_provenance_bound_m28_snapshot": True,
            "backslash_form_exact_m30_path_uses_same_m28_snapshot_provenance": True,
            "m28_snapshot_corrected_first_reach_counts": {
                "[-180,-135)": 22,
                "[-45,0)": 11,
            },
            "unrelated_missing_path_rejected": True,
            "analysis_sections_preserved": list(required_sections),
        },
        "checked_scope": [
            "existing requested input resolution",
            "exact M30 T2 to M27 T2 sibling fallback",
            "exact M30 T2 to M28 T2 profile fallback",
            "source kind and fallback provenance in emitted path reports",
            "preservation of a loaded M28 profile without recomputation",
            "artifact-independent M28 snapshot fallback for an absent exact M30 T2 file",
            "backslash-form exact M30 T2 snapshot fallback and provenance",
            "M28 snapshot provenance and representative aggregate counts",
            "corrected M28 snapshot first-reach counts for [-180,-135) and [-45,0)",
            "rejection of an unrelated missing input",
            "existing aggregate report section presence",
        ],
        "unchecked_scope": [
            "the completed campaign artifact's full schema and values",
            "scientific validity or interpretation of the profile",
            "Runner archive visibility and filesystem behavior outside the controlled temporary directory",
        ],
        "execution_note": "This check has not been executed.",
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="verification artifact path")
    parser.add_argument(
        "--compatibility",
        action="store_true",
        help="run the artifact-independent path compatibility check",
    )
    args = parser.parse_args(argv)
    result = run_compatibility_check() if args.compatibility else run_check()
    with Path(args.output).open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")


if __name__ == "__main__":
    main()
