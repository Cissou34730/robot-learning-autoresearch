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
    with TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        present_path = directory / "present.json"
        present_path.write_text(json.dumps(artifact), encoding="utf-8")
        resolved_present, present_fallback = resolve_profile_input(present_path)
        _assert_equal(resolved_present, present_path, "present-path resolution")
        _assert_equal(present_fallback, False, "present-path fallback flag")

        fallback_path = directory / M27_T2_REFERENCE_FILENAME
        fallback_path.write_text(json.dumps(artifact), encoding="utf-8")
        requested_m30_path = directory / M30_T2_REFERENCE_FILENAME
        resolved_fallback, fallback_used = resolve_profile_input(requested_m30_path)
        _assert_equal(resolved_fallback, fallback_path, "exact M30-to-M27 fallback")
        _assert_equal(fallback_used, True, "explicit fallback flag")

        fallback_report = analyze_path(requested_m30_path)
        _assert_equal(
            fallback_report["source_resolution"],
            {
                "requested_path": str(requested_m30_path),
                "resolved_path": str(fallback_path),
                "fallback_used": True,
            },
            "fallback provenance",
        )

        missing_m30_directory = directory / "without_fallback"
        missing_m30_directory.mkdir()
        missing_m30_path = missing_m30_directory / M30_T2_REFERENCE_FILENAME
        _assert_raises_file_not_found(
            lambda: resolve_profile_input(missing_m30_path),
            "M30 fallback requires its M27 sibling",
        )

        unrelated_missing_path = directory / "unrelated.json"
        _assert_raises_file_not_found(
            lambda: resolve_profile_input(unrelated_missing_path),
            "unrelated missing input",
        )

        report = analyze_document(artifact)
        required_sections = (
            "overall",
            "radius_strata",
            "angle_strata",
            "class_summaries",
            "branch_context_counts",
        )
        for section in required_sections:
            if section not in report:
                raise AssertionError(f"analysis section missing: {section}")

        observed = {
            "present_resolution": {
                "resolved_path": str(resolved_present),
                "fallback_used": present_fallback,
            },
            "fallback_resolution": {
                "resolved_path": str(resolved_fallback),
                "fallback_used": fallback_used,
            },
            "fallback_report_source_resolution": fallback_report[
                "source_resolution"
            ],
            "rejected_missing_inputs": 2,
            "analysis_sections": list(required_sections),
        }

    return {
        "status": "passed",
        "observed": observed,
        "expected": {
            "present_path_uses_requested_file": True,
            "exact_m30_path_uses_m27_sibling_only_when_present": True,
            "missing_m30_without_sibling_rejected": True,
            "unrelated_missing_path_rejected": True,
            "analysis_sections_preserved": list(required_sections),
        },
        "checked_scope": [
            "existing requested input resolution",
            "exact M30 T2 to M27 T2 sibling fallback",
            "fallback provenance in the emitted path report",
            "rejection of an M30 request without its exact fallback sibling",
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
