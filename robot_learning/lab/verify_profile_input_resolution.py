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

        missing_m30_directory = directory / "without_fallback"
        missing_m30_directory.mkdir()
        missing_m30_path = missing_m30_directory / M30_T2_REFERENCE_FILENAME
        _assert_raises_file_not_found(
            lambda: resolve_profile_input(missing_m30_path),
            "M30 fallback requires an approved sibling",
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
            "m28_preserved_profile_marker": m28_report["profile_marker"],
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
            "missing_m30_without_sibling_rejected": True,
            "unrelated_missing_path_rejected": True,
            "analysis_sections_preserved": list(required_sections),
        },
        "checked_scope": [
            "existing requested input resolution",
            "exact M30 T2 to M27 T2 sibling fallback",
            "exact M30 T2 to M28 T2 profile fallback",
            "source kind and fallback provenance in emitted path reports",
            "preservation of a loaded M28 profile without recomputation",
            "rejection of an M30 request without either exact fallback sibling",
            "rejection of an unrelated missing input",
            "existing aggregate report section presence",
        ],
        "unchecked_scope": [
            "the completed campaign artifact's full schema and values",
            "scientific validity or interpretation of the profile",
            "Runner archive visibility and filesystem behavior outside the controlled temporary directory",
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
