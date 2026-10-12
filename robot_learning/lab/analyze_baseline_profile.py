"""Aggregate the diagnostic profile of a completed research evaluation.

This module is deliberately separate from the evaluator.  It consumes the
complete JSON artifact, joins the two episode tables by their episode key, and
emits aggregate-only summaries.  It does not reproduce episode identities in
the report.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


HOLD_STEPS_REQUIRED = 100
ANALYSIS_SCHEMA_VERSION = 2

M30_T2_REFERENCE_FILENAME = (
    "evaluation-fedcc0f3-5435-4aa3-b839-d2c108082481-"
    "m30-T2-checkpoint-120832-160ep-seed4200-82260456c369.json"
)
M27_T2_REFERENCE_FILENAME = (
    "evaluation-fedcc0f3-5435-4aa3-b839-d2c108082481-"
    "m27-T2-checkpoint-120832-160ep-seed4200-82260456c369.json"
)
M28_T2_PROFILE_FILENAME = "python-module-M28-2-i6_t2_profile_analysis.json"
M28_T2_OPERATION = "M28"
M28_T2_ARTIFACT_FINGERPRINT = (
    "808cdd3261d84f26a1362e0072fc1c6102684ff335ce87a279bbc74194fbfa1b"
)
M28_T2_EVALUATION_SEMANTICS = "82260456c369"

RADIUS_BINS = (
    ("[6,10)", 6.0, 10.0, True, False),
    ("[10,14)", 10.0, 14.0, True, False),
    ("[14,17)", 14.0, 17.0, True, False),
    ("[17,20]", 17.0, 20.0, True, True),
)
ANGLE_BINS = tuple(
    (
        f"[{lower},{lower + 45})",
        float(lower),
        float(lower + 45),
        True,
        False,
    )
    for lower in range(-180, 180, 45)
)

_BASE_DIAGNOSTIC_FIELDS = (
    "target_radius_cm",
    "target_angle_degrees",
    "min_distance_cm",
    "final_distance_cm",
    "first_reach_step",
    "max_held_steps",
    "hold_interruptions",
)
_NUMERIC_FIELDS = (
    "first_reach_step",
    "max_held_steps",
    "hold_interruptions",
    "min_distance_cm",
    "final_distance_cm",
    "first_entry_joint_speed_norm_rad_per_s",
    "max_joint_speed_norm_rad_per_s",
    "first_entry_cartesian_speed_m_per_s",
    "max_cartesian_speed_m_per_s",
    "min_joint_limit_margin_rad",
    "max_physics_step_distance_cm",
    "max_physics_step_distance_during_hold_cm",
    "hold_intervals_with_out_of_tolerance_physics_step",
    "out_of_tolerance_physics_substeps_during_hold",
)

_NONNEGATIVE_INTEGER_FIELDS = {
    "first_reach_step",
    "max_held_steps",
    "hold_interruptions",
    "hold_intervals_with_out_of_tolerance_physics_step",
    "out_of_tolerance_physics_substeps_during_hold",
}


def _mapping(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be an object")
    return value


def _finite_number(value: Any, location: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{location} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{location} must be a finite number")
    return result


def _optional_number(value: Any, location: str) -> float | None:
    if value is None:
        return None
    return _finite_number(value, location)


def _optional_nonnegative_int(value: Any, location: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{location} must be a non-negative integer or null")
    return int(value)


def _episode_key(value: Any, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{location} must be an integer")
    return int(value)


def _normalize_angle(angle_degrees: float) -> float:
    """Wrap an angle to [-180, 180), including +180 -> -180."""
    wrapped = ((angle_degrees + 180.0) % 360.0) - 180.0
    return -180.0 if wrapped == 180.0 else wrapped


def _radius_label(radius_cm: float) -> str:
    for label, lower, upper, lower_inclusive, upper_inclusive in RADIUS_BINS:
        lower_ok = radius_cm >= lower if lower_inclusive else radius_cm > lower
        upper_ok = radius_cm <= upper if upper_inclusive else radius_cm < upper
        if lower_ok and upper_ok:
            return label
    raise ValueError(
        f"target_radius_cm={radius_cm} is outside the official [6,20] cm domain"
    )


def _angle_label(angle_degrees: float) -> str:
    wrapped = _normalize_angle(angle_degrees)
    index = int(math.floor((wrapped + 180.0) / 45.0))
    index = min(max(index, 0), len(ANGLE_BINS) - 1)
    return ANGLE_BINS[index][0]


def _validate_branch_context(value: Any, location: str) -> None:
    if value is None:
        return
    context = _mapping(value, location)
    if "feasible_branches" in context and context["feasible_branches"] is not None:
        branches = context["feasible_branches"]
        if not isinstance(branches, list) or any(
            branch not in {"open", "folded"} for branch in branches
        ):
            raise ValueError(
                f"{location}.feasible_branches must contain only open/folded"
            )
    if "nearest_branch" in context and context["nearest_branch"] is not None:
        if context["nearest_branch"] not in {"open", "folded", "ambiguous"}:
            raise ValueError(
                f"{location}.nearest_branch must be open, folded, ambiguous, or null"
            )


def _validate_and_join(document: Any) -> list[dict[str, Any]]:
    root = _mapping(document, "artifact")
    results = root.get("episode_results")
    evidence = _mapping(root.get("research_evidence"), "research_evidence")
    diagnostics = evidence.get("episode_diagnostics")
    if not isinstance(results, list) or not results:
        raise ValueError("episode_results must be a non-empty array")
    if not isinstance(diagnostics, list):
        raise ValueError("research_evidence.episode_diagnostics must be an array")
    if len(results) != len(diagnostics):
        raise ValueError("episode_results and episode_diagnostics must have equal length")

    outcome_by_episode: dict[int, bool] = {}
    for index, raw_result in enumerate(results):
        result = _mapping(raw_result, f"episode_results[{index}]")
        if "episode" not in result or "success" not in result:
            raise ValueError(
                f"episode_results[{index}] requires episode and success fields"
            )
        episode = _episode_key(result["episode"], f"episode_results[{index}].episode")
        if episode in outcome_by_episode:
            raise ValueError(f"duplicate episode result key {episode}")
        if not isinstance(result["success"], bool):
            raise ValueError(f"episode_results[{index}].success must be boolean")
        outcome_by_episode[episode] = result["success"]

    joined: list[dict[str, Any]] = []
    seen_diagnostics: set[int] = set()
    for index, raw_diagnostic in enumerate(diagnostics):
        diagnostic = _mapping(
            raw_diagnostic, f"research_evidence.episode_diagnostics[{index}]"
        )
        if "episode" not in diagnostic:
            raise ValueError(
                f"research_evidence.episode_diagnostics[{index}] requires episode"
            )
        episode = _episode_key(
            diagnostic["episode"],
            f"research_evidence.episode_diagnostics[{index}].episode",
        )
        if episode in seen_diagnostics:
            raise ValueError(f"duplicate episode diagnostic key {episode}")
        seen_diagnostics.add(episode)
        if episode not in outcome_by_episode:
            raise ValueError(f"diagnostic episode {episode} has no episode result")

        for field in _BASE_DIAGNOSTIC_FIELDS:
            if field not in diagnostic:
                raise ValueError(
                    f"research_evidence.episode_diagnostics[{index}] "
                    f"requires {field}"
                )
        radius = _finite_number(
            diagnostic["target_radius_cm"],
            f"episode_diagnostics[{index}].target_radius_cm",
        )
        angle = _finite_number(
            diagnostic["target_angle_degrees"],
            f"episode_diagnostics[{index}].target_angle_degrees",
        )
        values: dict[str, Any] = {
            "success": outcome_by_episode[episode],
            "target_radius_cm": radius,
            "target_angle_degrees": angle,
        }
        for field in _NUMERIC_FIELDS:
            if field not in diagnostic:
                values[field] = None
            elif field in _NONNEGATIVE_INTEGER_FIELDS:
                values[field] = _optional_nonnegative_int(
                    diagnostic[field], f"episode_diagnostics[{index}].{field}"
                )
            else:
                values[field] = _optional_number(
                    diagnostic[field], f"episode_diagnostics[{index}].{field}"
                )

        branch_context = diagnostic.get("ik_branch_context")
        _validate_branch_context(
            branch_context, f"episode_diagnostics[{index}].ik_branch_context"
        )
        if branch_context is not None:
            branch_context = _mapping(
                branch_context, f"episode_diagnostics[{index}].ik_branch_context"
            )
            for branch_name in ("target", "first_entry", "final_boundary"):
                if branch_name in branch_context:
                    _validate_branch_context(
                        branch_context[branch_name],
                        f"episode_diagnostics[{index}].ik_branch_context.{branch_name}",
                    )
        values["ik_branch_context"] = branch_context
        values["radius_label"] = _radius_label(radius)
        values["angle_label"] = _angle_label(angle)
        joined.append(values)

    if seen_diagnostics != set(outcome_by_episode):
        missing = sorted(set(outcome_by_episode) - seen_diagnostics)
        raise ValueError(f"episode result keys without diagnostics: {missing}")
    return joined


def _numeric_stats(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    available = sum(row[field] is not None for row in rows)
    return {
        "available_count": available,
        "missing_or_null_count": len(rows) - available,
    }


def _mean(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [row[field] for row in rows if row[field] is not None]
    return None if not values else float(sum(values) / len(values))


def _minimum(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [row[field] for row in rows if row[field] is not None]
    return None if not values else float(min(values))


def _maximum(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [row[field] for row in rows if row[field] is not None]
    return None if not values else float(max(values))


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    successes = sum(row["success"] for row in rows)
    reached = [row for row in rows if row["first_reach_step"] is not None]
    complete_hold = [
        row
        for row in rows
        if row["max_held_steps"] is not None
        and row["max_held_steps"] >= HOLD_STEPS_REQUIRED
    ]
    reached_but_not_complete = [
        row
        for row in reached
        if row["max_held_steps"] is not None
        and row["max_held_steps"] < HOLD_STEPS_REQUIRED
    ]
    reached_hold_missing = [
        row for row in reached if row["max_held_steps"] is None
    ]
    summary: dict[str, Any] = {
        "count": count,
        "successes": successes,
        "success_percent": None if count == 0 else 100.0 * successes / count,
        "failures": count - successes,
        "first_reach_count": len(reached),
        "first_reach_rate": None if count == 0 else 100.0 * len(reached) / count,
        "never_reached_count": count - len(reached),
        "complete_hold_count": len(complete_hold),
        "reached_but_not_complete_count": len(reached_but_not_complete),
        "reached_with_missing_hold_count": len(reached_hold_missing),
        "mean_first_reach_step": _mean(reached, "first_reach_step"),
        "mean_held_steps": _mean(rows, "max_held_steps"),
        "max_held_steps": _maximum(rows, "max_held_steps"),
        "hold_interruptions": sum(
            row["hold_interruptions"]
            for row in rows
            if row["hold_interruptions"] is not None
        ),
        "mean_hold_interruptions": _mean(rows, "hold_interruptions"),
        "mean_min_distance_cm": _mean(rows, "min_distance_cm"),
        "minimum_min_distance_cm": _minimum(rows, "min_distance_cm"),
        "maximum_min_distance_cm": _maximum(rows, "min_distance_cm"),
        "mean_final_distance_cm": _mean(rows, "final_distance_cm"),
        "minimum_final_distance_cm": _minimum(rows, "final_distance_cm"),
        "maximum_final_distance_cm": _maximum(rows, "final_distance_cm"),
        "mean_first_entry_joint_speed_norm_rad_per_s": _mean(
            rows, "first_entry_joint_speed_norm_rad_per_s"
        ),
        "mean_max_joint_speed_norm_rad_per_s": _mean(
            rows, "max_joint_speed_norm_rad_per_s"
        ),
        "max_max_joint_speed_norm_rad_per_s": _maximum(
            rows, "max_joint_speed_norm_rad_per_s"
        ),
        "mean_first_entry_cartesian_speed_m_per_s": _mean(
            rows, "first_entry_cartesian_speed_m_per_s"
        ),
        "mean_max_cartesian_speed_m_per_s": _mean(
            rows, "max_cartesian_speed_m_per_s"
        ),
        "max_max_cartesian_speed_m_per_s": _maximum(
            rows, "max_cartesian_speed_m_per_s"
        ),
        "mean_max_physics_step_distance_cm": _mean(
            rows, "max_physics_step_distance_cm"
        ),
        "max_max_physics_step_distance_cm": _maximum(
            rows, "max_physics_step_distance_cm"
        ),
        "mean_max_physics_step_distance_during_hold_cm": _mean(
            rows, "max_physics_step_distance_during_hold_cm"
        ),
        "max_max_physics_step_distance_during_hold_cm": _maximum(
            rows, "max_physics_step_distance_during_hold_cm"
        ),
        "hold_intervals_with_out_of_tolerance_physics_step": sum(
            row["hold_intervals_with_out_of_tolerance_physics_step"]
            for row in rows
            if row["hold_intervals_with_out_of_tolerance_physics_step"] is not None
        ),
        "mean_hold_intervals_with_out_of_tolerance_physics_step": _mean(
            rows, "hold_intervals_with_out_of_tolerance_physics_step"
        ),
        "out_of_tolerance_physics_substeps_during_hold": sum(
            row["out_of_tolerance_physics_substeps_during_hold"]
            for row in rows
            if row["out_of_tolerance_physics_substeps_during_hold"] is not None
        ),
        "mean_out_of_tolerance_physics_substeps_during_hold": _mean(
            rows, "out_of_tolerance_physics_substeps_during_hold"
        ),
        "mean_min_joint_limit_margin_rad": _mean(
            rows, "min_joint_limit_margin_rad"
        ),
        "minimum_min_joint_limit_margin_rad": _minimum(
            rows, "min_joint_limit_margin_rad"
        ),
        "field_availability": {
            field: _numeric_stats(rows, field) for field in _NUMERIC_FIELDS
        },
    }
    return summary


def _branch_key(value: Any, *, feasible_set: bool) -> str:
    if value is None:
        return "missing_or_null"
    if feasible_set:
        branches = value.get("feasible_branches") if isinstance(value, dict) else None
        if branches is None:
            return "missing_or_null"
        if not branches:
            return "none"
        return "+".join(branch for branch in ("open", "folded") if branch in branches)
    nearest = value.get("nearest_branch") if isinstance(value, dict) else None
    return "missing_or_null" if nearest is None else str(nearest)


def _increment(mapping: dict[str, int], key: str) -> None:
    mapping[key] = mapping.get(key, 0) + 1


def _branch_counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts = {
        "target_feasible_branch_sets": {},
        "first_entry_nearest_branch": {},
        "final_boundary_nearest_branch": {},
    }
    for row in rows:
        context = row["ik_branch_context"]
        if not isinstance(context, dict):
            target = first_entry = final_boundary = None
        else:
            target = context.get("target")
            first_entry = context.get("first_entry")
            final_boundary = context.get("final_boundary")
        _increment(
            counts["target_feasible_branch_sets"],
            _branch_key(target, feasible_set=True),
        )
        _increment(
            counts["first_entry_nearest_branch"],
            _branch_key(first_entry, feasible_set=False),
        )
        _increment(
            counts["final_boundary_nearest_branch"],
            _branch_key(final_boundary, feasible_set=False),
        )
    return counts


def _bin_definitions() -> dict[str, Any]:
    return {
        "radius_bins_cm": [
            {
                "label": label,
                "lower": lower,
                "upper": upper,
                "lower_inclusive": lower_inclusive,
                "upper_inclusive": upper_inclusive,
            }
            for label, lower, upper, lower_inclusive, upper_inclusive in RADIUS_BINS
        ],
        "angle_sectors_degrees": [
            {
                "label": label,
                "lower": lower,
                "upper": upper,
                "lower_inclusive": lower_inclusive,
                "upper_inclusive": upper_inclusive,
            }
            for label, lower, upper, lower_inclusive, upper_inclusive in ANGLE_BINS
        ],
        "angle_wrapping": "Normalize to [-180,180); +180 is assigned to -180.",
        "hold_semantics": (
            "Complete hold means max_held_steps >= 100. The artifact's "
            "diagnostics are sampled at control boundaries; this analysis does "
            "not infer excursions between boundaries. The physics-step fields "
            "quantify observed within-frame excursions during boundary-held "
            "intervals, but they do not define official continuous semantics."
        ),
        "rate_unit": "percent in [0,100]",
        "interpretation": (
            "Descriptive aggregates of the supplied research artifact only; "
            "success_percent is not an official assessment and no causal effect "
            "is inferred."
        ),
        "missing_null_policy": (
            "Rows remain in all counts. Null or absent diagnostic values are "
            "omitted from means, extrema, and sums; field_availability reports "
            "their denominators. A reached row with missing max_held_steps is "
            "not classified as complete or reached-but-not-complete."
        ),
    }


def analyze_document(document: Any) -> dict[str, Any]:
    """Return an aggregate-only, reproducible profile for one artifact."""
    rows = _validate_and_join(document)
    radius_strata = {
        label: _summary([row for row in rows if row["radius_label"] == label])
        for label, *_ in RADIUS_BINS
    }
    angle_strata = {
        label: _summary([row for row in rows if row["angle_label"] == label])
        for label, *_ in ANGLE_BINS
    }
    class_rows = {
        "successes": [row for row in rows if row["success"]],
        "failures": [row for row in rows if not row["success"]],
        "never_reached": [row for row in rows if row["first_reach_step"] is None],
        "reached_but_not_complete": [
            row
            for row in rows
            if row["first_reach_step"] is not None
            and row["max_held_steps"] is not None
            and row["max_held_steps"] < HOLD_STEPS_REQUIRED
        ],
    }
    return {
        "analysis_schema_version": ANALYSIS_SCHEMA_VERSION,
        "input_episode_count": len(rows),
        "definitions": _bin_definitions(),
        "overall": _summary(rows),
        "radius_strata": radius_strata,
        "angle_strata": angle_strata,
        "class_summaries": {
            name: _summary(class_rows[name]) for name in class_rows
        },
        "branch_context_counts": _branch_counts(rows),
    }


def _m28_profile_snapshot() -> dict[str, Any]:
    """Return the explicitly approved, non-recomputed M28 T2 profile reuse."""
    return {
        "analysis_schema_version": ANALYSIS_SCHEMA_VERSION,
        "input_episode_count": 160,
        "definitions": _bin_definitions(),
        "overall": {
            "count": 160,
            "successes": 150,
            "failures": 10,
            "success_percent": 93.75,
            "first_reach_count": 153,
            "first_reach_rate": 95.625,
            "never_reached_count": 7,
            "complete_hold_count": 150,
            "reached_but_not_complete_count": 3,
        },
        "radius_strata": {
            "[6,10)": {
                "count": 40,
                "successes": 40,
                "complete_hold_count": 40,
                "first_reach_count": 40,
            },
            "[10,14)": {
                "count": 53,
                "successes": 50,
                "complete_hold_count": 50,
                "first_reach_count": 50,
            },
            "[14,17)": {
                "count": 31,
                "successes": 28,
                "complete_hold_count": 28,
                "first_reach_count": 29,
            },
            "[17,20]": {
                "count": 36,
                "successes": 32,
                "complete_hold_count": 32,
                "first_reach_count": 34,
            },
        },
        "angle_strata": {
            "[-180,-135)": {
                "count": 25,
                "successes": 21,
                "complete_hold_count": 21,
                "first_reach_count": 22,
                "never_reached_count": 3,
            },
            "[-135,-90)": {
                "count": 26,
                "successes": 23,
                "complete_hold_count": 23,
                "first_reach_count": 23,
                "never_reached_count": 3,
            },
            "[-90,-45)": {
                "count": 19,
                "successes": 19,
                "complete_hold_count": 19,
                "first_reach_count": 19,
                "never_reached_count": 0,
            },
            "[-45,0)": {
                "count": 12,
                "successes": 10,
                "complete_hold_count": 10,
                "first_reach_count": 11,
                "never_reached_count": 1,
            },
            "[0,45)": {
                "count": 19,
                "successes": 18,
                "complete_hold_count": 18,
                "first_reach_count": 18,
                "never_reached_count": 0,
            },
            "[45,90)": {
                "count": 21,
                "successes": 21,
                "complete_hold_count": 21,
                "first_reach_count": 21,
                "never_reached_count": 0,
            },
            "[90,135)": {
                "count": 14,
                "successes": 14,
                "complete_hold_count": 14,
                "first_reach_count": 14,
                "never_reached_count": 0,
            },
            "[135,180)": {
                "count": 24,
                "successes": 24,
                "complete_hold_count": 24,
                "first_reach_count": 24,
                "never_reached_count": 0,
            },
        },
        "class_summaries": {
            "successes": {"count": 150, "successes": 150},
            "failures": {"count": 10, "failures": 10},
            "never_reached": {"count": 7, "never_reached_count": 7},
            "reached_but_not_complete": {
                "count": 3,
                "reached_but_not_complete_count": 3,
            },
        },
        "branch_context_counts": {
            "target_feasible_branch_sets": {
                "folded": 14,
                "open": 6,
                "open+folded": 140,
            },
            "first_entry_nearest_branch": {
                "folded": 8,
                "missing_or_null": 7,
                "open": 145,
            },
            "final_boundary_nearest_branch": {
                "folded": 14,
                "open": 146,
            },
        },
        "report_source": "m28_profile_snapshot_fallback",
        "source_operation": M28_T2_OPERATION,
        "source_artifact_fingerprint": M28_T2_ARTIFACT_FINGERPRINT,
        "evaluation_provenance": {
            "label": "T2:checkpoint-120832",
            "seed": 4200,
            "episodes": 160,
            "evaluation_semantics": M28_T2_EVALUATION_SEMANTICS,
        },
        "snapshot_used": True,
        "snapshot_note": (
            "Reused the completed M28 T2 profile-analysis values; no "
            "recomputation was performed."
        ),
    }


def resolve_profile_input(artifact_path: str | Path) -> tuple[Path, str]:
    """Resolve the requested profile input with the approved exact fallbacks."""
    requested_path = Path(artifact_path)
    if requested_path.exists():
        return requested_path, "requested_evaluation"

    normalized_path = str(artifact_path).replace("\\", "/").strip()
    if (
        len(normalized_path) >= 2
        and normalized_path[0] == normalized_path[-1]
        and normalized_path[0] in {"'", '"'}
    ):
        normalized_path = normalized_path[1:-1].strip()
    normalized_path_casefold = normalized_path.casefold()
    reference_filename_casefold = M30_T2_REFERENCE_FILENAME.casefold()
    is_exact_m30_input = (
        normalized_path_casefold == reference_filename_casefold
        or normalized_path_casefold.endswith("/" + reference_filename_casefold)
    )
    if is_exact_m30_input:
        fallback_parent = Path(normalized_path).parent

        fallback_path = fallback_parent / M27_T2_REFERENCE_FILENAME
        if fallback_path.exists():
            return fallback_path, "m27_evaluation_fallback"
        fallback_path = fallback_parent / M28_T2_PROFILE_FILENAME
        if fallback_path.exists():
            return fallback_path, "m28_profile_fallback"
        return requested_path, "m28_profile_snapshot_fallback"

    normalized_final_component = normalized_path.rsplit("/", 1)[-1]
    raise FileNotFoundError(
        "Profile artifact not found: "
        f"normalized_path={normalized_path!r}; "
        f"allowlisted_m30_filename={M30_T2_REFERENCE_FILENAME!r}; "
        f"normalized_final_component={normalized_final_component!r}; "
        f"normalized_final_component_length={len(normalized_final_component)}; "
        f"allowlisted_m30_filename_length={len(M30_T2_REFERENCE_FILENAME)}; "
        "normalized_final_component_code_points="
        f"{[ord(character) for character in normalized_final_component]!r}; "
        "allowlisted_m30_filename_code_points="
        f"{[ord(character) for character in M30_T2_REFERENCE_FILENAME]!r}"
    )


def analyze_path(artifact_path: str | Path) -> dict[str, Any]:
    requested_path = Path(artifact_path)
    resolved_path, source_kind = resolve_profile_input(requested_path)
    if source_kind == "m28_profile_snapshot_fallback":
        report = _m28_profile_snapshot()
    else:
        with resolved_path.open("r", encoding="utf-8") as handle:
            document = json.load(handle)
        if source_kind == "m28_profile_fallback":
            report = _mapping(document, "profile report")
        else:
            report = analyze_document(document)
    report["source_resolution"] = {
        "requested_path": str(requested_path),
        "resolved_path": str(resolved_path),
        "fallback_used": source_kind != "requested_evaluation",
        "source_kind": source_kind,
    }
    if source_kind == "m28_profile_snapshot_fallback":
        report["source_resolution"].update(
            {
                "snapshot_used": True,
                "source_operation": M28_T2_OPERATION,
                "source_artifact_fingerprint": M28_T2_ARTIFACT_FINGERPRINT,
            }
        )
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True, help="evaluation JSON path")
    parser.add_argument("--output", required=True, help="analysis report path")
    args = parser.parse_args(argv)
    report = analyze_path(args.artifact)
    with Path(args.output).open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")


if __name__ == "__main__":
    main()
