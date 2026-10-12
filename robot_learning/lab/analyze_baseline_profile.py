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
ANALYSIS_SCHEMA_VERSION = 1

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
)


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
            elif field in {"first_reach_step", "max_held_steps", "hold_interruptions"}:
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
            "not infer excursions between boundaries."
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


def analyze_path(artifact_path: str | Path) -> dict[str, Any]:
    with Path(artifact_path).open("r", encoding="utf-8") as handle:
        return analyze_document(json.load(handle))


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
