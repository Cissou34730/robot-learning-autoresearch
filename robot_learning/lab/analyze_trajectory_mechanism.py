"""Describe trajectory mechanisms in one completed evaluation artifact.

The analysis is intentionally post-processing only.  It joins episode outcomes
to their diagnostic traces, derives compact trajectory quantities, and does not
claim a cause for any observed outcome.
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
    (f"[{lower},{lower + 45})", float(lower), float(lower + 45), True, False)
    for lower in range(-180, 180, 45)
)

TRACE_FIELDS = (
    "control_step",
    "qpos_rad",
    "qvel_rad_per_s",
    "applied_clipped_action",
    "jacobian",
    "radial_cartesian_velocity_m_per_s",
    "tangential_cartesian_velocity_m_per_s",
    "joint_limit_margin_rad",
    "held_steps",
    "in_tolerance",
    "physics_step_distances_cm",
)


def _object(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be an object")
    return value


def _number(value: Any, location: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{location} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{location} must be a finite number")
    return result


def _optional_number(value: Any, location: str) -> float | None:
    if value is None:
        return None
    return _number(value, location)


def _nonnegative_int(value: Any, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{location} must be a non-negative integer")
    return int(value)


def _optional_nonnegative_int(value: Any, location: str) -> int | None:
    if value is None:
        return None
    return _nonnegative_int(value, location)


def _vector(value: Any, location: str, *, minimum: int = 1) -> list[float]:
    if not isinstance(value, list) or len(value) < minimum:
        raise ValueError(f"{location} must be a list with at least {minimum} values")
    return [_number(item, f"{location}[{index}]") for index, item in enumerate(value)]


def _stats(values: list[float], denominator: int | None = None) -> dict[str, Any]:
    denominator = len(values) if denominator is None else denominator
    return {
        "available_count": len(values),
        "missing_or_null_count": denominator - len(values),
        "minimum": None if not values else float(min(values)),
        "mean": None if not values else float(sum(values) / len(values)),
        "maximum": None if not values else float(max(values)),
    }


def _bool_stats(values: list[bool], denominator: int) -> dict[str, Any]:
    return {
        "available_count": len(values),
        "missing_or_null_count": denominator - len(values),
        "true_count": sum(values),
        "false_count": len(values) - sum(values),
    }


def _normalize_angle(value: float) -> float:
    return ((value + 180.0) % 360.0) - 180.0


def _radius_label(value: float) -> str:
    for label, lower, upper, lower_inclusive, upper_inclusive in RADIUS_BINS:
        lower_ok = value >= lower if lower_inclusive else value > lower
        upper_ok = value <= upper if upper_inclusive else value < upper
        if lower_ok and upper_ok:
            return label
    raise ValueError(
        f"target_radius_cm={value} is outside the official [6,20] cm domain"
    )


def _angle_label(value: float) -> str:
    wrapped = _normalize_angle(value)
    index = min(max(int(math.floor((wrapped + 180.0) / 45.0)), 0), 7)
    return ANGLE_BINS[index][0]


def _validate_jacobian(value: Any, location: str) -> dict[str, Any]:
    jacobian = _object(value, location)
    if "rank" not in jacobian or "rank_deficient" not in jacobian:
        raise ValueError(f"{location} requires rank and rank_deficient")
    rank = _nonnegative_int(jacobian["rank"], f"{location}.rank")
    if rank > 2:
        raise ValueError(f"{location}.rank must be at most 2")
    if not isinstance(jacobian["rank_deficient"], bool):
        raise ValueError(f"{location}.rank_deficient must be boolean")
    if jacobian["rank_deficient"] != (rank < 2):
        raise ValueError(f"{location}.rank_deficient disagrees with rank")
    condition = jacobian.get("condition_number")
    if condition is not None:
        _number(condition, f"{location}.condition_number")
    return {
        "rank": rank,
        "rank_deficient": jacobian["rank_deficient"],
        "condition_number": None if condition is None else float(condition),
    }


def _validate_trace(
    diagnostic: dict[str, Any], location: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_trace = diagnostic.get("trajectory_trace")
    if not isinstance(raw_trace, list) or not raw_trace:
        raise ValueError(f"{location}.trajectory_trace must be a non-empty array")

    trace: list[dict[str, Any]] = []
    for index, raw_row in enumerate(raw_trace):
        row = _object(raw_row, f"{location}.trajectory_trace[{index}]")
        missing = [field for field in TRACE_FIELDS if field not in row]
        if missing:
            raise ValueError(
                f"{location}.trajectory_trace[{index}] is missing {missing}"
            )
        control_step = _nonnegative_int(
            row["control_step"], f"{location}.trajectory_trace[{index}].control_step"
        )
        if control_step != index:
            raise ValueError(
                f"{location}.trajectory_trace control_step must be the sequence "
                f"0..n-1; row {index} is {control_step}"
            )
        qpos = _vector(row["qpos_rad"], f"{location}.trajectory_trace[{index}].qpos_rad", minimum=2)
        qvel = _vector(row["qvel_rad_per_s"], f"{location}.trajectory_trace[{index}].qvel_rad_per_s", minimum=2)
        action = row["applied_clipped_action"]
        if action is not None:
            action = _vector(
                action,
                f"{location}.trajectory_trace[{index}].applied_clipped_action",
                minimum=2,
            )
            if any(abs(value) > 1.0 + 1e-9 for value in action):
                raise ValueError(
                    f"{location}.trajectory_trace[{index}].applied_clipped_action "
                    "is outside [-1,1]"
                )
        elif index != 0:
            raise ValueError(
                f"{location}.trajectory_trace[{index}] has no applied action "
                "for an updated row"
            )
        jacobian = _validate_jacobian(
            row["jacobian"], f"{location}.trajectory_trace[{index}].jacobian"
        )
        radial = _optional_number(
            row["radial_cartesian_velocity_m_per_s"],
            f"{location}.trajectory_trace[{index}].radial_cartesian_velocity_m_per_s",
        )
        tangential = _optional_number(
            row["tangential_cartesian_velocity_m_per_s"],
            f"{location}.trajectory_trace[{index}].tangential_cartesian_velocity_m_per_s",
        )
        margin = _number(
            row["joint_limit_margin_rad"],
            f"{location}.trajectory_trace[{index}].joint_limit_margin_rad",
        )
        held_steps = _nonnegative_int(
            row["held_steps"], f"{location}.trajectory_trace[{index}].held_steps"
        )
        if not isinstance(row["in_tolerance"], bool):
            raise ValueError(
                f"{location}.trajectory_trace[{index}].in_tolerance must be boolean"
            )
        distances = row["physics_step_distances_cm"]
        if not isinstance(distances, list):
            raise ValueError(
                f"{location}.trajectory_trace[{index}].physics_step_distances_cm "
                "must be an array"
            )
        distances = [
            _number(value, f"{location}.trajectory_trace[{index}].physics_step_distances_cm")
            for value in distances
        ]
        if any(value < 0.0 for value in distances):
            raise ValueError(
                f"{location}.trajectory_trace[{index}].physics_step_distances_cm "
                "must be non-negative"
            )
        trace.append(
            {
                "control_step": control_step,
                "qpos": qpos,
                "qvel": qvel,
                "action": action,
                "jacobian": jacobian,
                "radial": radial,
                "tangential": tangential,
                "margin": margin,
                "held_steps": held_steps,
                "in_tolerance": row["in_tolerance"],
                "physics_distances": distances,
            }
        )

    if trace[0]["action"] is not None or trace[0]["in_tolerance"] or trace[0]["held_steps"] != 0:
        raise ValueError(f"{location}.trajectory_trace[0] is not a reset row")

    derived_first = next(
        (row["control_step"] for row in trace if row["in_tolerance"]), None
    )
    derived_max_held = max(row["held_steps"] for row in trace)
    return trace, {
        "first_in_tolerance_control_step": derived_first,
        "maximum_held_steps": derived_max_held,
    }


def _branch_set(diagnostic: dict[str, Any], location: str) -> list[str] | None:
    context = diagnostic.get("ik_branch_context")
    if context is None:
        return None
    context = _object(context, location)
    target = context.get("target")
    if target is None:
        return None
    target = _object(target, f"{location}.target")
    branches = target.get("feasible_branches")
    if branches is None:
        return None
    if not isinstance(branches, list) or any(
        branch not in {"open", "folded"} for branch in branches
    ):
        raise ValueError(
            f"{location}.target.feasible_branches must contain only open/folded"
        )
    if len(set(branches)) != len(branches):
        raise ValueError(f"{location}.target.feasible_branches must be unique")
    return list(branches)


def _branch_label(branches: list[str] | None) -> str:
    if branches is None:
        return "missing_or_null"
    if not branches:
        return "none"
    return "+".join(branch for branch in ("open", "folded") if branch in branches)


def _episode_profile(
    result: dict[str, Any], diagnostic: dict[str, Any], location: str
) -> dict[str, Any]:
    radius = _number(diagnostic["target_radius_cm"], f"{location}.target_radius_cm")
    angle = _number(diagnostic["target_angle_degrees"], f"{location}.target_angle_degrees")
    first_reach = _optional_nonnegative_int(
        diagnostic["first_reach_step"], f"{location}.first_reach_step"
    )
    endpoint_max_held = _nonnegative_int(
        diagnostic["max_held_steps"], f"{location}.max_held_steps"
    )
    trace, derived = _validate_trace(diagnostic, location)
    if first_reach != derived["first_in_tolerance_control_step"]:
        raise ValueError(
            f"{location}.first_reach_step disagrees with trajectory_trace"
        )
    if endpoint_max_held != derived["maximum_held_steps"]:
        raise ValueError(f"{location}.max_held_steps disagrees with trajectory_trace")

    success = result["success"]
    if success != (endpoint_max_held >= HOLD_STEPS_REQUIRED):
        raise ValueError(
            f"{location} success disagrees with the trace-derived complete hold"
        )
    if success:
        classification = "success"
    elif first_reach is None:
        classification = "never_reached"
    else:
        classification = "reached_but_not_complete"

    reset_jacobian = trace[0]["jacobian"]
    full_rank_steps = [
        row["control_step"] for row in trace if row["jacobian"]["rank"] >= 2
    ]
    condition_values = [
        row["jacobian"]["condition_number"]
        for row in trace
        if row["jacobian"]["condition_number"] is not None
    ]
    radial_values = [row["radial"] for row in trace if row["radial"] is not None]
    tangential_values = [
        abs(row["tangential"]) for row in trace if row["tangential"] is not None
    ]
    qvel_norms = [math.sqrt(sum(value * value for value in row["qvel"])) for row in trace]
    updated_rows = [row for row in trace if row["control_step"] > 0]
    action_values = [
        abs(value)
        for row in updated_rows
        if row["action"] is not None
        for value in row["action"]
    ]
    saturated_rows = [
        row
        for row in updated_rows
        if row["action"] is not None and any(abs(value) >= 1.0 - 1e-12 for value in row["action"])
    ]
    all_physics_distances = [
        value for row in trace for value in row["physics_distances"]
    ]
    hold_physics_distances = [
        value
        for row in trace
        if row["in_tolerance"]
        for value in row["physics_distances"]
    ]

    profile = {
        "episode": result["episode"],
        "classification": classification,
        "success": success,
        "target_radius_cm": radius,
        "target_angle_degrees": angle,
        "radius_stratum": _radius_label(radius),
        "angle_stratum": _angle_label(angle),
        "target_feasible_branches": _branch_set(
            diagnostic, f"{location}.ik_branch_context"
        ),
        "trajectory": {
            "trace_row_count": len(trace),
            "reset_jacobian_rank_deficient": reset_jacobian["rank_deficient"],
            "reset_jacobian_rank": reset_jacobian["rank"],
            "first_full_planar_rank_control_step": (
                min(full_rank_steps) if full_rank_steps else None
            ),
            "condition_number_finite_values": _stats(
                condition_values, denominator=len(trace)
            ),
            "signed_radial_velocity_m_per_s": _stats(
                radial_values, denominator=len(trace)
            ),
            "absolute_tangential_velocity_m_per_s": _stats(
                tangential_values, denominator=len(trace)
            ),
            "max_qvel_norm_rad_per_s": (
                max(qvel_norms) if qvel_norms else None
            ),
            "max_absolute_applied_clipped_action": (
                max(action_values) if action_values else None
            ),
            "actuator_saturation": {
                "saturated_updated_rows": len(saturated_rows),
                "updated_rows": len(updated_rows),
                "missing_or_null_updated_rows": len(updated_rows)
                - sum(row["action"] is not None for row in updated_rows),
                "fraction_of_updated_rows": (
                    len(saturated_rows) / len(updated_rows)
                    if updated_rows
                    else None
                ),
            },
            "min_joint_limit_margin_rad": min(row["margin"] for row in trace),
            "first_in_tolerance_control_step": derived[
                "first_in_tolerance_control_step"
            ],
            "maximum_held_steps": derived["maximum_held_steps"],
            "max_physics_step_distance_cm": (
                max(all_physics_distances) if all_physics_distances else None
            ),
            "max_physics_step_distance_during_hold_cm": (
                max(hold_physics_distances) if hold_physics_distances else None
            ),
        },
    }
    return profile


def _join_profiles(document: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    root = _object(document, "artifact")
    results = root.get("episode_results")
    evidence = _object(root.get("research_evidence"), "research_evidence")
    diagnostics = evidence.get("episode_diagnostics")
    if not isinstance(results, list) or not results:
        raise ValueError("episode_results must be a non-empty array")
    if not isinstance(diagnostics, list):
        raise ValueError("research_evidence.episode_diagnostics must be an array")
    if len(results) != len(diagnostics):
        raise ValueError("episode_results and episode_diagnostics must have equal length")

    result_by_episode: dict[int, dict[str, Any]] = {}
    for index, raw_result in enumerate(results):
        result = _object(raw_result, f"episode_results[{index}]")
        episode = _nonnegative_int(result.get("episode"), f"episode_results[{index}].episode")
        if episode in result_by_episode:
            raise ValueError(f"duplicate episode result key {episode}")
        if not isinstance(result.get("success"), bool):
            raise ValueError(f"episode_results[{index}].success must be boolean")
        result_by_episode[episode] = result

    profiles: list[dict[str, Any]] = []
    seen: set[int] = set()
    for index, raw_diagnostic in enumerate(diagnostics):
        diagnostic = _object(raw_diagnostic, f"episode_diagnostics[{index}]")
        episode = _nonnegative_int(
            diagnostic.get("episode"), f"episode_diagnostics[{index}].episode"
        )
        if episode in seen:
            raise ValueError(f"duplicate episode diagnostic key {episode}")
        seen.add(episode)
        if episode not in result_by_episode:
            raise ValueError(f"diagnostic episode {episode} has no episode result")
        for field in ("target_radius_cm", "target_angle_degrees", "first_reach_step", "max_held_steps"):
            if field not in diagnostic:
                raise ValueError(f"episode_diagnostics[{index}] requires {field}")
        profiles.append(
            _episode_profile(
                result_by_episode[episode],
                diagnostic,
                f"episode_diagnostics[{index}]",
            )
        )
    missing = sorted(set(result_by_episode) - seen)
    if missing:
        raise ValueError(f"episode result keys without diagnostics: {missing}")
    return root, profiles


SCALAR_METRICS = (
    "max_qvel_norm_rad_per_s",
    "max_absolute_applied_clipped_action",
    "min_joint_limit_margin_rad",
    "first_in_tolerance_control_step",
    "maximum_held_steps",
    "max_physics_step_distance_cm",
    "max_physics_step_distance_during_hold_cm",
    "first_full_planar_rank_control_step",
)
NESTED_METRICS = (
    "condition_number_finite_values",
    "signed_radial_velocity_m_per_s",
    "absolute_tangential_velocity_m_per_s",
)


def _combine_stats(stats: list[dict[str, Any]], denominators: list[int]) -> dict[str, Any]:
    available = sum(item["available_count"] for item in stats)
    denominator = sum(denominators)
    values_min = [item["minimum"] for item in stats if item["minimum"] is not None]
    values_max = [item["maximum"] for item in stats if item["maximum"] is not None]
    weighted_sum = sum(
        item["mean"] * item["available_count"]
        for item in stats
        if item["mean"] is not None
    )
    return {
        "available_count": available,
        "missing_or_null_count": denominator - available,
        "minimum": min(values_min) if values_min else None,
        "mean": weighted_sum / available if available else None,
        "maximum": max(values_max) if values_max else None,
    }


def _branch_counts(profiles: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {
        "none": 0,
        "open": 0,
        "folded": 0,
        "open+folded": 0,
        "missing_or_null": 0,
    }
    for profile in profiles:
        key = _branch_label(profile["target_feasible_branches"])
        counts[key] = counts.get(key, 0) + 1
    return counts


def _aggregate(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(profiles)
    trajectory = [profile["trajectory"] for profile in profiles]
    metrics: dict[str, Any] = {}
    for field in SCALAR_METRICS:
        metrics[field] = _stats(
            [item[field] for item in trajectory if item[field] is not None],
            denominator=count,
        )
    for field in NESTED_METRICS:
        nested = [item[field] for item in trajectory]
        metrics[field] = _combine_stats(
            nested, [item["trace_row_count"] for item in trajectory]
        )
    saturation_rows = sum(item["actuator_saturation"]["updated_rows"] for item in trajectory)
    saturated_rows = sum(item["actuator_saturation"]["saturated_updated_rows"] for item in trajectory)
    return {
        "count": count,
        "success_count": sum(profile["classification"] == "success" for profile in profiles),
        "target_feasible_branch_counts": _branch_counts(profiles),
        "metrics": metrics,
        "reset_jacobian_rank_deficient": _bool_stats(
            [item["reset_jacobian_rank_deficient"] for item in trajectory], count
        ),
        "reset_jacobian_rank": _stats(
            [float(item["reset_jacobian_rank"]) for item in trajectory], count
        ),
        "actuator_saturation": {
            "saturated_updated_rows": saturated_rows,
            "updated_rows": saturation_rows,
            "missing_or_null_updated_rows": sum(
                item["actuator_saturation"]["missing_or_null_updated_rows"]
                for item in trajectory
            ),
            "fraction_of_updated_rows": (
                saturated_rows / saturation_rows if saturation_rows else None
            ),
            "episode_fraction": _stats(
                [
                    item["actuator_saturation"]["fraction_of_updated_rows"]
                    for item in trajectory
                    if item["actuator_saturation"]["fraction_of_updated_rows"] is not None
                ],
                count,
            ),
        },
    }


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
        "hold_steps_required": HOLD_STEPS_REQUIRED,
        "missing_null_policy": (
            "Trace-derived summaries retain every episode and report explicit "
            "available and missing_or_null denominators. Null radial, tangential, "
            "or condition values are excluded only from their own finite-value "
            "summary. No missing trace is imputed."
        ),
    }


def analyze_document(document: Any) -> dict[str, Any]:
    """Return a compact, trace-derived report for one evaluation artifact."""
    root, profiles = _join_profiles(document)
    classes = {
        name: [profile for profile in profiles if profile["classification"] == name]
        for name in ("success", "reached_but_not_complete", "never_reached")
    }
    radius_strata = {
        label: _aggregate(
            [profile for profile in profiles if profile["radius_stratum"] == label]
        )
        for label, *_ in RADIUS_BINS
    }
    angle_strata = {
        label: _aggregate(
            [profile for profile in profiles if profile["angle_stratum"] == label]
        )
        for label, *_ in ANGLE_BINS
    }
    panel_metadata = {
        key: value
        for key, value in root.items()
        if key not in {"episode_results", "research_evidence"}
    }
    return {
        "analysis_schema_version": ANALYSIS_SCHEMA_VERSION,
        "panel_metadata": panel_metadata,
        "input_episode_count": len(profiles),
        "definitions": _bin_definitions(),
        "overall": _aggregate(profiles),
        "class_summaries": {
            "successes": _aggregate(classes["success"]),
            "reached_but_not_complete": _aggregate(classes["reached_but_not_complete"]),
            "never_reached": _aggregate(classes["never_reached"]),
        },
        "radius_strata": radius_strata,
        "angle_strata": angle_strata,
        "episode_profiles": profiles,
        "interpretation": (
            "Descriptive development evidence from the supplied trajectory "
            "artifact only. These summaries do not certify official continuous "
            "hold behavior and do not provide causal proof."
        ),
        "unchecked_scope": [
            "Official continuous-hold certification between recorded boundaries.",
            "Causal attribution among feasibility, control, and training exposure.",
            "Any behavior not represented in the supplied episode traces.",
        ],
    }


def analyze_path(artifact_path: str | Path) -> dict[str, Any]:
    path = Path(artifact_path)
    with path.open("r", encoding="utf-8") as handle:
        return analyze_document(json.load(handle))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True, help="evaluation JSON path")
    parser.add_argument("--output", required=True, help="compact report JSON path")
    args = parser.parse_args(argv)
    report = analyze_path(args.artifact)
    with Path(args.output).open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")


if __name__ == "__main__":
    main()
