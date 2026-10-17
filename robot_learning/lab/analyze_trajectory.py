"""Validate and summarize a trajectory-enabled research evaluation.

This module is a descriptive analysis instrument.  It does not run a policy,
modify the input evaluation, alter evaluation semantics, or make a causal or
official-assessment claim.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


EXPECTED_SCHEMA_VERSION = 5
SUCCESS_THRESHOLD_M = 0.01
REQUIRED_HOLD_STEPS = 100
RADIUS_MIN_CM = 6.0
RADIUS_MAX_CM = 20.0
RADIUS_BIN_WIDTH_CM = 2.0
ANGLE_MIN_DEGREES = -180.0
ANGLE_MAX_DEGREES = 180.0
ANGLE_BIN_WIDTH_DEGREES = 45.0
BRANCH_LABELS = ("open", "folded", "singular")
TRAJECTORY_FIELDS = (
    "control_step",
    "end_effector_position_m",
    "target_relative_error_m",
    "joint_positions_rad",
    "joint_velocities_rad_per_s",
    "endpoint_velocity_mps",
    "endpoint_speed_mps",
    "distance_m",
    "applied_action",
    "action_saturated",
    "elbow_qpos_rad",
    "elbow_branch",
    "held_steps",
    "in_tolerance",
)
EXPECTED_ROW_SEMANTICS = (
    "One row per visible control step, sampled at the post-control-boundary "
    "state. control_step is one-based and rows continue through termination "
    "or truncation."
)
EXPECTED_TRAJECTORY_METADATA = {
    "control_step": (
        "control_steps",
        "One-based visible control-step index.",
    ),
    "end_effector_position_m": (
        "m",
        "World-frame end-effector position after the control interval.",
    ),
    "target_relative_error_m": (
        "m",
        "End-effector position minus the fixed target position at the same boundary.",
    ),
    "joint_positions_rad": (
        "rad",
        "Two joint positions at the post-control boundary, ordered shoulder then elbow.",
    ),
    "joint_velocities_rad_per_s": (
        "rad_per_s",
        "Two joint velocities at the post-control boundary, ordered shoulder then elbow.",
    ),
    "endpoint_velocity_mps": (
        "m_per_s",
        "World-frame end-effector linear velocity at the post-control boundary.",
    ),
    "endpoint_speed_mps": (
        "m_per_s",
        "Euclidean norm of endpoint_velocity_mps.",
    ),
    "distance_m": (
        "m",
        "Three-dimensional Euclidean distance computed from the post-control-boundary position and target-relative error in this row.",
    ),
    "applied_action": (
        "dimensionless_action",
        "Post-adapter action after environment clipping, in the order applied to the two actuators.",
    ),
    "action_saturated": (
        "boolean_per_joint",
        "Whether the corresponding applied action equals an inclusive action bound.",
    ),
    "elbow_qpos_rad": (
        "rad",
        "Relative elbow joint configuration.",
    ),
    "elbow_branch": (
        "label",
        "Branch label derived from elbow_qpos_rad: open, folded, or singular.",
    ),
    "held_steps": (
        "control_steps",
        "Existing environment task hold counter reported for this control step; zero after a task-level interruption.",
    ),
    "in_tolerance": (
        "boolean",
        "Whether this row's post-control-boundary distance is within the success threshold; the existing task counter remains in held_steps.",
    ),
}


def _fail(message: str) -> ValueError:
    return ValueError(f"malformed trajectory research evaluation: {message}")


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _fail(f"{label} must be an object")
    return value


def _field(record: dict[str, Any], name: str, label: str) -> Any:
    if name not in record:
        raise _fail(f"{label} is missing required field {name!r}")
    return record[name]


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail(f"{label} must be an integer")
    return value


def _nonnegative_integer(value: Any, label: str) -> int:
    result = _integer(value, label)
    if result < 0:
        raise _fail(f"{label} must be non-negative")
    return result


def _positive_integer(value: Any, label: str) -> int:
    result = _integer(value, label)
    if result <= 0:
        raise _fail(f"{label} must be positive")
    return result


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise _fail(f"{label} must be a finite number")
    return result


def _nonnegative(value: Any, label: str) -> float:
    result = _finite(value, label)
    if result < 0.0:
        raise _fail(f"{label} must be non-negative")
    return result


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _fail(f"{label} must be a non-empty string")
    return value


def _vector(value: Any, size: int, label: str) -> list[float]:
    if not isinstance(value, list) or len(value) != size:
        raise _fail(f"{label} must be a {size}-element array")
    return [_finite(item, f"{label}[{index}]") for index, item in enumerate(value)]


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise _fail(f"{label} must be a boolean")
    return value


def _close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-12)


def _require_consistent(
    actual: float, expected: float, label: str, *, tolerance: bool = True
) -> None:
    if tolerance and _close(actual, expected):
        return
    if not tolerance and actual == expected:
        return
    raise _fail(f"{label} is inconsistent with its documented components")


def _fraction(saturated: list[bool]) -> float:
    return sum(saturated) / len(saturated)


@dataclass
class Episode:
    result: dict[str, Any]
    diagnostic: dict[str, Any]
    rows: list[dict[str, Any]]

    @property
    def success(self) -> bool:
        return self.result["success"]

    @property
    def first_reach_step(self) -> int | None:
        return self.diagnostic["first_reach_step"]


def _validate_trajectory_schema(evidence: dict[str, Any]) -> str:
    schema = _object(
        _field(evidence, "trajectory_schema", "research_evidence"),
        "research_evidence.trajectory_schema",
    )
    row_semantics = _string(
        _field(schema, "row_semantics", "research_evidence.trajectory_schema"),
        "research_evidence.trajectory_schema.row_semantics",
    )
    if row_semantics != EXPECTED_ROW_SEMANTICS:
        raise _fail(
            "research_evidence.trajectory_schema.row_semantics does not "
            "match the evaluator's schema-version-5 semantics"
        )
    fields = _object(
        _field(schema, "fields", "research_evidence.trajectory_schema"),
        "research_evidence.trajectory_schema.fields",
    )
    for name in TRAJECTORY_FIELDS:
        field_schema = _object(
            _field(fields, name, "research_evidence.trajectory_schema.fields"),
            f"research_evidence.trajectory_schema.fields.{name}",
        )
        units = _string(
            _field(field_schema, "units", f"trajectory field {name}"),
            f"trajectory field {name}.units",
        )
        semantics = _string(
            _field(field_schema, "semantics", f"trajectory field {name}"),
            f"trajectory field {name}.semantics",
        )
        expected_units, expected_semantics = EXPECTED_TRAJECTORY_METADATA[name]
        if units != expected_units:
            raise _fail(
                f"trajectory field {name}.units must be {expected_units!r}"
            )
        if semantics != expected_semantics:
            raise _fail(
                f"trajectory field {name}.semantics does not match the "
                "evaluator's schema-version-5 semantics"
            )
    return row_semantics


def _validate_row(
    raw_row: Any, episode_index: int, row_index: int
) -> dict[str, Any]:
    row = _object(raw_row, f"episode {episode_index} trajectory row {row_index}")
    label = f"episode {episode_index} trajectory row {row_index}"
    for name in TRAJECTORY_FIELDS:
        if name not in row:
            raise _fail(f"{label} is missing required field {name!r}")

    control_step = _positive_integer(
        row["control_step"], f"{label}.control_step"
    )
    end_position = _vector(
        row["end_effector_position_m"], 3, f"{label}.end_effector_position_m"
    )
    relative_error = _vector(
        row["target_relative_error_m"], 3, f"{label}.target_relative_error_m"
    )
    joint_positions = _vector(
        row["joint_positions_rad"], 2, f"{label}.joint_positions_rad"
    )
    joint_velocities = _vector(
        row["joint_velocities_rad_per_s"],
        2,
        f"{label}.joint_velocities_rad_per_s",
    )
    endpoint_velocity = _vector(
        row["endpoint_velocity_mps"], 3, f"{label}.endpoint_velocity_mps"
    )
    endpoint_speed = _nonnegative(
        row["endpoint_speed_mps"], f"{label}.endpoint_speed_mps"
    )
    _require_consistent(
        endpoint_speed,
        math.sqrt(sum(component * component for component in endpoint_velocity)),
        f"{label}.endpoint_speed_mps",
    )
    distance = _nonnegative(row["distance_m"], f"{label}.distance_m")
    _require_consistent(
        distance,
        math.sqrt(sum(component * component for component in relative_error)),
        f"{label}.distance_m",
    )
    applied_action = _vector(
        row["applied_action"], 2, f"{label}.applied_action"
    )
    if any(action < -1.0 or action > 1.0 for action in applied_action):
        raise _fail(f"{label}.applied_action must be within [-1, 1]")
    saturated = row["action_saturated"]
    if not isinstance(saturated, list) or len(saturated) != 2:
        raise _fail(f"{label}.action_saturated must be a 2-element array")
    saturated = [
        _boolean(value, f"{label}.action_saturated[{index}]")
        for index, value in enumerate(saturated)
    ]
    for index, (action, is_saturated) in enumerate(zip(applied_action, saturated)):
        expected = action == -1.0 or action == 1.0
        if is_saturated != expected:
            raise _fail(
                f"{label}.action_saturated[{index}] disagrees with "
                "the inclusive action bound"
            )
    elbow_qpos = _finite(row["elbow_qpos_rad"], f"{label}.elbow_qpos_rad")
    branch = _string(row["elbow_branch"], f"{label}.elbow_branch")
    if branch not in BRANCH_LABELS:
        raise _fail(
            f"{label}.elbow_branch must be one of {list(BRANCH_LABELS)!r}"
        )
    held_steps = _nonnegative_integer(
        row["held_steps"], f"{label}.held_steps"
    )
    in_tolerance = _boolean(row["in_tolerance"], f"{label}.in_tolerance")
    expected_in_tolerance = distance <= SUCCESS_THRESHOLD_M
    if in_tolerance != expected_in_tolerance:
        raise _fail(
            f"{label}.in_tolerance disagrees with the documented 1 cm "
            "success threshold"
        )
    if in_tolerance != (held_steps > 0):
        raise _fail(
            f"{label}.held_steps is phase-inconsistent with in_tolerance"
        )
    return {
        "control_step": control_step,
        "end_effector_position_m": end_position,
        "target_relative_error_m": relative_error,
        "joint_positions_rad": joint_positions,
        "joint_velocities_rad_per_s": joint_velocities,
        "endpoint_velocity_mps": endpoint_velocity,
        "endpoint_speed_mps": endpoint_speed,
        "distance_m": distance,
        "applied_action": applied_action,
        "action_saturated": saturated,
        "saturation_fraction": _fraction(saturated),
        "elbow_qpos_rad": elbow_qpos,
        "elbow_branch": branch,
        "held_steps": held_steps,
        "in_tolerance": in_tolerance,
        "joint_speed_rad_per_s": math.sqrt(
            sum(component * component for component in joint_velocities)
        ),
    }


def _validate_diagnostic(
    raw_diagnostic: Any, episode_index: int, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    diagnostic = _object(raw_diagnostic, f"episode_diagnostics[{episode_index}]")
    label = f"episode_diagnostics[{episode_index}]"
    episode = _nonnegative_integer(
        _field(diagnostic, "episode", label), f"{label}.episode"
    )
    radius = _finite(
        _field(diagnostic, "target_radius_cm", label),
        f"{label}.target_radius_cm",
    )
    if not RADIUS_MIN_CM <= radius <= RADIUS_MAX_CM:
        raise _fail(
            f"{label}.target_radius_cm must be within "
            f"[{RADIUS_MIN_CM:g}, {RADIUS_MAX_CM:g}] cm"
        )
    angle = _finite(
        _field(diagnostic, "target_angle_degrees", label),
        f"{label}.target_angle_degrees",
    )
    if not ANGLE_MIN_DEGREES <= angle < ANGLE_MAX_DEGREES:
        raise _fail(
            f"{label}.target_angle_degrees must be in "
            f"[{ANGLE_MIN_DEGREES:g}, {ANGLE_MAX_DEGREES:g})"
        )

    required_numeric = (
        "initial_elbow_qpos_rad",
        "min_distance_cm",
        "final_distance_cm",
        "max_endpoint_speed_mps",
        "final_endpoint_speed_mps",
        "final_elbow_qpos_rad",
    )
    for name in required_numeric:
        _finite(_field(diagnostic, name, label), f"{label}.{name}")
    for name in (
        "min_distance_cm",
        "final_distance_cm",
        "max_endpoint_speed_mps",
        "final_endpoint_speed_mps",
    ):
        _nonnegative(diagnostic[name], f"{label}.{name}")

    first_reach = _field(diagnostic, "first_reach_step", label)
    if first_reach is not None:
        first_reach = _positive_integer(first_reach, f"{label}.first_reach_step")
    max_held = _nonnegative_integer(
        _field(diagnostic, "max_held_steps", label), f"{label}.max_held_steps"
    )
    in_tolerance_steps = _nonnegative_integer(
        _field(diagnostic, "in_tolerance_steps", label),
        f"{label}.in_tolerance_steps",
    )
    hold_interruptions = _nonnegative_integer(
        _field(diagnostic, "hold_interruptions", label),
        f"{label}.hold_interruptions",
    )
    first_reach_speed = _field(diagnostic, "first_reach_endpoint_speed_mps", label)
    if first_reach_speed is not None:
        first_reach_speed = _nonnegative(
            first_reach_speed, f"{label}.first_reach_endpoint_speed_mps"
        )
    initial_branch = _string(
        _field(diagnostic, "initial_elbow_branch", label),
        f"{label}.initial_elbow_branch",
    )
    final_branch = _string(
        _field(diagnostic, "final_elbow_branch", label),
        f"{label}.final_elbow_branch",
    )
    if initial_branch not in BRANCH_LABELS or final_branch not in BRANCH_LABELS:
        raise _fail(f"{label} contains an unknown elbow branch label")

    occupancy = _object(
        _field(diagnostic, "elbow_branch_occupancy_counts", label),
        f"{label}.elbow_branch_occupancy_counts",
    )
    if set(occupancy) != set(BRANCH_LABELS):
        raise _fail(
            f"{label}.elbow_branch_occupancy_counts must contain exactly "
            f"{list(BRANCH_LABELS)!r}"
        )
    occupancy_counts = {
        branch: _nonnegative_integer(
            occupancy[branch], f"{label}.elbow_branch_occupancy_counts.{branch}"
        )
        for branch in BRANCH_LABELS
    }

    saturation_count = _nonnegative_integer(
        _field(diagnostic, "action_saturation_count", label),
        f"{label}.action_saturation_count",
    )
    saturation_fraction = _finite(
        _field(diagnostic, "action_saturation_fraction", label),
        f"{label}.action_saturation_fraction",
    )
    if not 0.0 <= saturation_fraction <= 1.0:
        raise _fail(f"{label}.action_saturation_fraction must be between 0 and 1")
    per_joint_counts_value = _field(
        diagnostic, "action_saturation_count_per_joint", label
    )
    if not isinstance(per_joint_counts_value, list) or len(per_joint_counts_value) != 2:
        raise _fail(
            f"{label}.action_saturation_count_per_joint must be a 2-element array"
        )
    per_joint_counts = [
        _nonnegative_integer(
            value, f"{label}.action_saturation_count_per_joint[{index}]"
        )
        for index, value in enumerate(per_joint_counts_value)
    ]
    per_joint_fractions_value = _field(
        diagnostic, "action_saturation_fraction_per_joint", label
    )
    if (
        not isinstance(per_joint_fractions_value, list)
        or len(per_joint_fractions_value) != 2
    ):
        raise _fail(
            f"{label}.action_saturation_fraction_per_joint must be a 2-element array"
        )
    per_joint_fractions = [
        _finite(
            value, f"{label}.action_saturation_fraction_per_joint[{index}]"
        )
        for index, value in enumerate(per_joint_fractions_value)
    ]
    if any(not 0.0 <= value <= 1.0 for value in per_joint_fractions):
        raise _fail(
            f"{label}.action_saturation_fraction_per_joint must be between 0 and 1"
        )

    if not rows:
        raise _fail(f"{label} has no trajectory rows")
    if rows[0]["held_steps"] != (1 if rows[0]["in_tolerance"] else 0):
        raise _fail(
            f"{label} first trajectory row has an invalid held_steps phase"
        )
    if first_reach != next(
        (row["control_step"] for row in rows if row["in_tolerance"]), None
    ):
        raise _fail(f"{label}.first_reach_step is inconsistent with trajectory rows")
    if first_reach is None and first_reach_speed is not None:
        raise _fail(f"{label}.first_reach_endpoint_speed_mps must be null without reach")
    if first_reach is not None:
        first_row = rows[first_reach - 1]
        if first_reach_speed is None or not _close(
            first_reach_speed, first_row["endpoint_speed_mps"]
        ):
            raise _fail(
                f"{label}.first_reach_endpoint_speed_mps is inconsistent "
                "with trajectory rows"
            )
    if max_held != max(row["held_steps"] for row in rows):
        raise _fail(f"{label}.max_held_steps is inconsistent with trajectory rows")
    if in_tolerance_steps != sum(row["in_tolerance"] for row in rows):
        raise _fail(f"{label}.in_tolerance_steps is inconsistent with trajectory rows")
    expected_interruptions = sum(
        previous["in_tolerance"] and not current["in_tolerance"]
        for previous, current in zip(rows, rows[1:])
    )
    if hold_interruptions != expected_interruptions:
        raise _fail(f"{label}.hold_interruptions is inconsistent with trajectory rows")
    if not _close(
        diagnostic["min_distance_cm"], 100.0 * min(row["distance_m"] for row in rows)
    ):
        raise _fail(f"{label}.min_distance_cm is inconsistent with trajectory rows")
    if not _close(
        diagnostic["final_distance_cm"], 100.0 * rows[-1]["distance_m"]
    ):
        raise _fail(f"{label}.final_distance_cm is inconsistent with trajectory rows")
    if not _close(
        diagnostic["max_endpoint_speed_mps"],
        max(row["endpoint_speed_mps"] for row in rows),
    ):
        raise _fail(
            f"{label}.max_endpoint_speed_mps is inconsistent with trajectory rows"
        )
    if not _close(
        diagnostic["final_endpoint_speed_mps"], rows[-1]["endpoint_speed_mps"]
    ):
        raise _fail(
            f"{label}.final_endpoint_speed_mps is inconsistent with trajectory rows"
        )
    if not _close(diagnostic["final_elbow_qpos_rad"], rows[-1]["elbow_qpos_rad"]):
        raise _fail(
            f"{label}.final_elbow_qpos_rad is inconsistent with trajectory rows"
        )
    if final_branch != rows[-1]["elbow_branch"]:
        raise _fail(f"{label}.final_elbow_branch is inconsistent with trajectory rows")
    if sum(occupancy_counts.values()) != len(rows):
        raise _fail(
            f"{label}.elbow_branch_occupancy_counts does not cover all rows"
        )
    for branch in BRANCH_LABELS:
        if occupancy_counts[branch] != sum(
            row["elbow_branch"] == branch for row in rows
        ):
            raise _fail(
                f"{label}.elbow_branch_occupancy_counts is inconsistent "
                "with trajectory rows"
            )
    actual_per_joint_counts = [
        sum(row["action_saturated"][joint] for row in rows) for joint in range(2)
    ]
    if per_joint_counts != actual_per_joint_counts:
        raise _fail(
            f"{label}.action_saturation_count_per_joint is inconsistent "
            "with trajectory rows"
        )
    if saturation_count != sum(actual_per_joint_counts):
        raise _fail(
            f"{label}.action_saturation_count is inconsistent with trajectory rows"
        )
    expected_fraction = saturation_count / (len(rows) * 2)
    if not _close(saturation_fraction, expected_fraction):
        raise _fail(
            f"{label}.action_saturation_fraction is inconsistent with trajectory rows"
        )
    for joint in range(2):
        expected_joint_fraction = actual_per_joint_counts[joint] / len(rows)
        if not _close(per_joint_fractions[joint], expected_joint_fraction):
            raise _fail(
                f"{label}.action_saturation_fraction_per_joint is inconsistent "
                "with trajectory rows"
            )
    return {
        **diagnostic,
        "episode": episode,
        "target_radius_cm": radius,
        "target_angle_degrees": angle,
        "first_reach_step": first_reach,
        "first_reach_endpoint_speed_mps": first_reach_speed,
        "max_held_steps": max_held,
        "in_tolerance_steps": in_tolerance_steps,
        "hold_interruptions": hold_interruptions,
        "final_elbow_branch": final_branch,
        "action_saturation_fraction": saturation_fraction,
    }


def _validate_input(
    artifact: Any,
) -> tuple[dict[str, Any], str, list[Episode]]:
    root = _object(artifact, "artifact")
    if _field(root, "official_benchmark", "artifact") is not False:
        raise _fail("artifact.official_benchmark must be boolean false")
    _string(_field(root, "model", "artifact"), "artifact.model")
    if _integer(_field(root, "schema_version", "artifact"), "artifact.schema_version") != EXPECTED_SCHEMA_VERSION:
        raise _fail(f"artifact.schema_version must be {EXPECTED_SCHEMA_VERSION}")

    result_values = _field(root, "episode_results", "artifact")
    if not isinstance(result_values, list) or not result_values:
        raise _fail("artifact.episode_results must be a non-empty array")
    declared_episodes = _positive_integer(
        _field(root, "episodes", "artifact"), "artifact.episodes"
    )
    if declared_episodes != len(result_values):
        raise _fail("artifact.episodes does not match episode_results length")
    results: dict[int, dict[str, Any]] = {}
    for position, raw_result in enumerate(result_values):
        result = _object(raw_result, f"episode_results[{position}]")
        episode = _nonnegative_integer(
            _field(result, "episode", f"episode_results[{position}]"),
            f"episode_results[{position}].episode",
        )
        if episode in results:
            raise _fail(f"duplicate episode_results episode {episode}")
        success = _boolean(
            _field(result, "success", f"episode_results[{position}]"),
            f"episode_results[{position}].success",
        )
        steps = _positive_integer(
            _field(result, "steps", f"episode_results[{position}]"),
            f"episode_results[{position}].steps",
        )
        results[episode] = {**result, "episode": episode, "success": success, "steps": steps}
    expected_ids = set(range(declared_episodes))
    if set(results) != expected_ids:
        raise _fail("episode indices must be the consecutive range 0..episodes-1")

    evidence = _object(
        _field(root, "research_evidence", "artifact"), "artifact.research_evidence"
    )
    row_semantics = _validate_trajectory_schema(evidence)
    diagnostic_values = _field(evidence, "episode_diagnostics", "research_evidence")
    if not isinstance(diagnostic_values, list):
        raise _fail("research_evidence.episode_diagnostics must be an array")
    if len(diagnostic_values) != declared_episodes:
        raise _fail("episode_diagnostics length must equal artifact.episodes")

    diagnostics: dict[int, dict[str, Any]] = {}
    episodes: list[Episode] = []
    for position, raw_diagnostic in enumerate(diagnostic_values):
        diagnostic_object = _object(raw_diagnostic, f"episode_diagnostics[{position}]")
        episode = _nonnegative_integer(
            _field(diagnostic_object, "episode", f"episode_diagnostics[{position}]"),
            f"episode_diagnostics[{position}].episode",
        )
        if episode in diagnostics:
            raise _fail(f"duplicate episode_diagnostics episode {episode}")
        if episode not in results:
            raise _fail(f"episode_diagnostics episode {episode} has no result")
        result = results[episode]
        trajectory = _field(
            diagnostic_object, "trajectory", f"episode_diagnostics[{position}]"
        )
        if not isinstance(trajectory, list):
            raise _fail(f"episode {episode} trajectory must be an array")
        if len(trajectory) != result["steps"]:
            raise _fail(
                f"episode {episode} trajectory length does not match "
                f"episode steps ({len(trajectory)} != {result['steps']})"
            )
        rows = [_validate_row(row, episode, index) for index, row in enumerate(trajectory)]
        for expected_step, row in enumerate(rows, start=1):
            if row["control_step"] != expected_step:
                raise _fail(
                    f"episode {episode} trajectory control_step values must "
                    "be one-based and strictly ordered"
                )
        for previous, current in zip(rows, rows[1:]):
            expected_held = previous["held_steps"] + 1 if current["in_tolerance"] else 0
            if current["held_steps"] != expected_held:
                raise _fail(
                    f"episode {episode} trajectory held_steps is not "
                    "consecutive at control_step "
                    f"{current['control_step']}"
                )
        diagnostic = _validate_diagnostic(diagnostic_object, episode, rows)
        if diagnostic["first_reach_step"] is None and result["success"]:
            raise _fail(f"episode {episode} is successful but never reached tolerance")
        if result["success"] != (diagnostic["max_held_steps"] >= REQUIRED_HOLD_STEPS):
            raise _fail(
                f"episode {episode} success is inconsistent with the "
                f"{REQUIRED_HOLD_STEPS}-step hold phase"
            )
        diagnostics[episode] = diagnostic
        episodes.append(Episode(result, diagnostic, rows))
    if set(diagnostics) != expected_ids:
        raise _fail("episode_results and episode_diagnostics have different episode indices")
    episodes.sort(key=lambda item: item.result["episode"])
    return root, row_semantics, episodes


def _mean(values: list[float]) -> float | None:
    return None if not values else sum(values) / len(values)


def _metric(values: list[float], unit: str) -> dict[str, Any]:
    return {
        "mean": _mean(values),
        "denominator": len(values),
        "denominator_unit": unit,
    }


def _episode_launch_values(episode: Episode) -> dict[str, float]:
    rows = [row for row in episode.rows if row["control_step"] <= 20]
    return {
        "endpoint_speed_mps": sum(row["endpoint_speed_mps"] for row in rows) / len(rows),
        "joint_speed_rad_per_s": sum(row["joint_speed_rad_per_s"] for row in rows) / len(rows),
        "distance_m": sum(row["distance_m"] for row in rows) / len(rows),
        "saturation_fraction": sum(row["saturation_fraction"] for row in rows) / len(rows),
    }


def _launch_window(
    episodes: list[Episode],
) -> dict[str, Any]:
    values = [_episode_launch_values(episode) for episode in episodes]
    return {
        "control_step_definition": "Available trajectory rows with 1 <= control_step <= 20.",
        "episode_count": len(values),
        "row_count": sum(min(20, len(episode.rows)) for episode in episodes),
        "endpoint_speed_mps": _metric(
            [item["endpoint_speed_mps"] for item in values], "episodes"
        ),
        "joint_speed_rad_per_s": _metric(
            [item["joint_speed_rad_per_s"] for item in values], "episodes"
        ),
        "distance_m": _metric(
            [item["distance_m"] for item in values], "episodes"
        ),
        "saturation_fraction": _metric(
            [item["saturation_fraction"] for item in values], "episodes"
        ),
    }


def _post_reach_window(episodes: list[Episode]) -> dict[str, Any]:
    reached = [episode for episode in episodes if episode.first_reach_step is not None]
    post_rows = [
        row
        for episode in reached
        for row in episode.rows
        if row["control_step"] >= episode.first_reach_step
    ]
    post_episode_values = []
    for episode in reached:
        rows = [
            row
            for row in episode.rows
            if row["control_step"] >= episode.first_reach_step
        ]
        post_episode_values.append(
            {
                "maximum_distance_m": max(row["distance_m"] for row in rows),
                "endpoint_speed_mps": sum(
                    row["endpoint_speed_mps"] for row in rows
                )
                / len(rows),
                "saturation_fraction": sum(
                    row["saturation_fraction"] for row in rows
                )
                / len(rows),
            }
        )
    return {
        "control_step_definition": (
            "Available trajectory rows with control_step >= first_reach_step, "
            "including the first-reach row."
        ),
        "episode_count": len(reached),
        "row_count": len(post_rows),
        "maximum_distance_m": _metric(
            [item["maximum_distance_m"] for item in post_episode_values], "episodes"
        ),
        "endpoint_speed_mps": _metric(
            [item["endpoint_speed_mps"] for item in post_episode_values], "episodes"
        ),
        "saturation_fraction": _metric(
            [item["saturation_fraction"] for item in post_episode_values], "episodes"
        ),
    }


def _no_reach_summary(episodes: list[Episode]) -> dict[str, Any]:
    no_reach = [episode for episode in episodes if episode.first_reach_step is None]
    return {
        "episode_count": len(no_reach),
        "launch_window": _launch_window(no_reach),
        "full_trajectory": {
            "definition": (
                "Per-episode final endpoint speed and distance, and the "
                "fraction of all trajectory joint samples saturated."
            ),
            "endpoint_speed_mps": _metric(
                [episode.rows[-1]["endpoint_speed_mps"] for episode in no_reach],
                "episodes",
            ),
            "final_distance_m": _metric(
                [episode.rows[-1]["distance_m"] for episode in no_reach],
                "episodes",
            ),
            "saturation_fraction": _metric(
                [
                    sum(row["saturation_fraction"] for row in episode.rows)
                    / len(episode.rows)
                    for episode in no_reach
                ],
                "episodes",
            ),
        },
    }


def _branch_counts(
    episodes: list[Episode], *, first_reach: bool = False
) -> dict[str, Any]:
    counts = {branch: 0 for branch in BRANCH_LABELS}
    selected = []
    for episode in episodes:
        if first_reach:
            if episode.first_reach_step is None:
                continue
            selected.append(episode.rows[episode.first_reach_step - 1]["elbow_branch"])
        else:
            selected.append(episode.rows[min(20, len(episode.rows)) - 1]["elbow_branch"])
    for branch in selected:
        counts[branch] += 1
    return {
        "counts": counts,
        "denominator": len(selected),
        "denominator_unit": "episodes",
    }


def _phase_counts(episodes: list[Episode]) -> dict[str, Any]:
    reached = [episode for episode in episodes if episode.first_reach_step is not None]
    successes = [episode for episode in episodes if episode.success]
    return {
        "episode_count": len(episodes),
        "success_count": len(successes),
        "first_reach_count": len(reached),
        "no_reach_count": len(episodes) - len(reached),
        "hold_failure_count": sum(
            episode.first_reach_step is not None and not episode.success
            for episode in episodes
        ),
    }


def _branch_record(episodes: list[Episode], branch: str) -> dict[str, Any]:
    failures = [
        episode
        for episode in episodes
        if episode.first_reach_step is not None and not episode.success
    ]
    return {
        "branch": branch,
        "counts": _phase_counts(episodes),
        "launch_window": _launch_window(episodes),
        "post_first_reach": _post_reach_window(episodes),
        "reached_but_unsuccessful": {
            "counts": _phase_counts(failures),
            "launch_window": _launch_window(failures),
            "post_first_reach": _post_reach_window(failures),
        },
    }


def _branch_conditioned(episodes: list[Episode]) -> dict[str, Any]:
    control_step_members = {branch: [] for branch in BRANCH_LABELS}
    first_reach_members = {branch: [] for branch in BRANCH_LABELS}
    for episode in episodes:
        launch_branch = episode.rows[min(20, len(episode.rows)) - 1]["elbow_branch"]
        control_step_members[launch_branch].append(episode)
        if episode.first_reach_step is not None:
            reach_branch = episode.rows[episode.first_reach_step - 1]["elbow_branch"]
            first_reach_members[reach_branch].append(episode)
    return {
        "control_step_20_or_final_available": {
            "selection_definition": (
                "Each episode is assigned using elbow_branch at control step "
                "20, or its final available control step when shorter."
            ),
            "branches": {
                branch: _branch_record(members, branch)
                for branch, members in control_step_members.items()
            },
        },
        "first_reach": {
            "selection_definition": (
                "Only reached episodes are assigned using elbow_branch on "
                "their first-reach row."
            ),
            "branches": {
                branch: _branch_record(members, branch)
                for branch, members in first_reach_members.items()
            },
        },
    }


def _summary(episodes: list[Episode]) -> dict[str, Any]:
    reached = [episode for episode in episodes if episode.first_reach_step is not None]
    successes = [episode for episode in episodes if episode.success]
    hold_failures = [episode for episode in reached if not episode.success]
    phase_counts = _phase_counts(episodes)
    launch = _launch_window(episodes)
    summary = {
        **phase_counts,
        "success_rate": None if not episodes else len(successes) / len(episodes),
        "first_reach_rate": None if not episodes else len(reached) / len(episodes),
        "means": {
            "first_reach_step": _metric(
                [float(episode.first_reach_step) for episode in reached], "episodes"
            ),
            "first_reach_endpoint_speed_mps": _metric(
                [
                    float(episode.diagnostic["first_reach_endpoint_speed_mps"])
                    for episode in reached
                ],
                "episodes",
            ),
            "max_held_steps": _metric(
                [float(episode.diagnostic["max_held_steps"]) for episode in episodes],
                "episodes",
            ),
            "hold_interruptions": _metric(
                [float(episode.diagnostic["hold_interruptions"]) for episode in episodes],
                "episodes",
            ),
            "final_endpoint_speed_mps": _metric(
                [float(episode.rows[-1]["endpoint_speed_mps"]) for episode in episodes],
                "episodes",
            ),
            "early_launch_endpoint_speed_mps": launch["endpoint_speed_mps"],
            "early_launch_joint_speed_rad_per_s": launch["joint_speed_rad_per_s"],
            "early_launch_distance_m": launch["distance_m"],
            "early_launch_saturation_fraction": launch["saturation_fraction"],
            "post_first_reach_maximum_distance_m": _post_reach_window(episodes)[
                "maximum_distance_m"
            ],
            "post_first_reach_endpoint_speed_mps": _post_reach_window(episodes)[
                "endpoint_speed_mps"
            ],
            "post_first_reach_saturation_fraction": _post_reach_window(episodes)[
                "saturation_fraction"
            ],
        },
        "launch_window": launch,
        "post_first_reach": _post_reach_window(episodes),
        "no_reach": _no_reach_summary(episodes),
        "reached_but_unsuccessful": {
            "counts": _phase_counts(hold_failures),
            "launch_window": _launch_window(hold_failures),
            "post_first_reach": _post_reach_window(hold_failures),
        },
        "branch_counts": {
            "control_step_20_or_final_available": _branch_counts(episodes),
            "first_reach": _branch_counts(episodes, first_reach=True),
        },
    }
    summary["branch_conditioned"] = _branch_conditioned(episodes)
    return summary


def _radius_bins() -> list[dict[str, Any]]:
    bins = []
    for index in range(7):
        lower = RADIUS_MIN_CM + index * RADIUS_BIN_WIDTH_CM
        upper = lower + RADIUS_BIN_WIDTH_CM
        bins.append(
            {
                "label": (
                    f"[{lower:g}, {upper:g}) cm"
                    if upper < RADIUS_MAX_CM
                    else f"[{lower:g}, {upper:g}] cm"
                ),
                "lower_cm": lower,
                "upper_cm": upper,
                "upper_inclusive": upper == RADIUS_MAX_CM,
            }
        )
    return bins


def _angle_bins() -> list[dict[str, Any]]:
    bins = []
    for index in range(8):
        lower = ANGLE_MIN_DEGREES + index * ANGLE_BIN_WIDTH_DEGREES
        upper = lower + ANGLE_BIN_WIDTH_DEGREES
        bins.append(
            {
                "label": f"[{lower:g}, {upper:g}) degrees",
                "lower_degrees": lower,
                "upper_degrees": upper,
            }
        )
    return bins


def _bin_index(value: float, bins: list[dict[str, Any]], lower_key: str) -> int:
    upper_key = "upper_cm" if lower_key == "lower_cm" else "upper_degrees"
    for index, bin_record in enumerate(bins):
        lower = bin_record[lower_key]
        upper = bin_record[upper_key]
        if lower <= value < upper or (
            index == len(bins) - 1 and value == upper
        ):
            return index
    raise _fail(f"value {value!r} does not fit the declared bin convention")


def analyze_trajectory(artifact: Any, input_path: str) -> dict[str, Any]:
    """Validate and produce descriptive stratified trajectory summaries."""
    root, row_semantics, episodes = _validate_input(artifact)
    radius_bins = _radius_bins()
    angle_bins = _angle_bins()
    radius_members = [[] for _ in radius_bins]
    angle_members = [[] for _ in angle_bins]
    for episode in episodes:
        radius_index = _bin_index(
            episode.diagnostic["target_radius_cm"], radius_bins, "lower_cm"
        )
        angle_index = _bin_index(
            episode.diagnostic["target_angle_degrees"], angle_bins, "lower_degrees"
        )
        radius_members[radius_index].append(episode)
        angle_members[angle_index].append(episode)

    overall = _summary(episodes)
    inner = [
        episode
        for episode in episodes
        if RADIUS_MIN_CM <= episode.diagnostic["target_radius_cm"] < 14.0
    ]
    outer = [
        episode
        for episode in episodes
        if 14.0 <= episode.diagnostic["target_radius_cm"] <= RADIUS_MAX_CM
    ]
    radius_output = []
    for bin_record, members in zip(radius_bins, radius_members):
        radius_output.append({**bin_record, "statistics": _summary(members)})
    angle_output = []
    for bin_record, members in zip(angle_bins, angle_members):
        angle_output.append({**bin_record, "statistics": _summary(members)})

    input_metadata = {
        "path": input_path,
        "schema_version": root["schema_version"],
        "model": root["model"],
    }
    return {
        "analysis": {
            "kind": "trajectory_phase_stratified_descriptive_analysis",
            "declaration": (
                "Descriptive only: this output is not an official assessment "
                "and does not infer causality or identify an intervention."
            ),
            "descriptive_only": True,
            "official_assessment": False,
            "causal_inference": False,
            "input_artifact": input_metadata,
            "trajectory_row_semantics": row_semantics,
            "success_threshold": {
                "distance_m": SUCCESS_THRESHOLD_M,
                "distance_cm": 1.0,
                "meaning": (
                    "in_tolerance is true when the post-control-boundary "
                    "distance is at most 1 cm."
                ),
            },
            "launch_window": {
                "definition": "Available rows with one-based control_step <= 20.",
                "control_step_minimum": 1,
                "control_step_maximum": 20,
            },
            "post_first_reach_window": {
                "definition": (
                    "Rows with control_step >= first_reach_step for episodes "
                    "that reached tolerance; the first-reach row is included."
                ),
                "first_reach_row_included": True,
            },
            "radius_bin_convention": (
                "Seven bins, lower inclusive and upper exclusive except the "
                "last upper bound: [6,8), [8,10), [10,12), [12,14), "
                "[14,16), [16,18), [18,20] cm."
            ),
            "angle_bin_convention": (
                "Eight 45-degree bins, lower inclusive and upper exclusive, "
                "spanning [-180,180) degrees."
            ),
            "phase_classification_table": [
                {
                    "phase": "no_reach",
                    "definition": "first_reach_step is null; no row entered the 1 cm tolerance.",
                    "count": overall["no_reach_count"],
                    "interpretation": "Report launch and full-trajectory observations without causal attribution.",
                },
                {
                    "phase": "reached_but_unsuccessful",
                    "definition": "first_reach_step is present and success is false.",
                    "count": overall["hold_failure_count"],
                    "interpretation": "Report post-reach observations and hold interruptions without causal attribution.",
                },
            ],
        },
        "input_artifact": input_metadata,
        "episode_count": len(episodes),
        "overall": overall,
        "inner_outer": {
            "inner_6_14_cm": _summary(inner),
            "outer_14_20_cm": _summary(outer),
        },
        "radius_bins": {
            "range_cm": [RADIUS_MIN_CM, RADIUS_MAX_CM],
            "bins": radius_output,
        },
        "angle_bins": {
            "range_degrees": [ANGLE_MIN_DEGREES, ANGLE_MAX_DEGREES],
            "bins": angle_output,
        },
    }


def _input_path(argument: str) -> Path:
    if not argument.strip():
        raise ValueError("input JSON path must not be empty")
    path = Path(argument)
    if not path.exists():
        raise ValueError(f"input JSON path does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"input JSON path is not a file: {path}")
    return path


def _output_path(argument: str, input_path: Path) -> Path:
    if not argument.strip():
        raise ValueError("output JSON path must not be empty")
    path = Path(argument)
    if path.exists() and path.is_dir():
        raise ValueError(f"output path is a directory, not a JSON file: {path}")
    if not path.parent.exists() or not path.parent.is_dir():
        raise ValueError(f"output parent directory does not exist: {path.parent}")
    if path.resolve() == input_path.resolve():
        raise ValueError("output JSON path must differ from the input artifact path")
    return path


def _load_json(path: Path) -> Any:
    def reject_nonfinite_constant(value: str) -> Any:
        raise ValueError(f"non-finite JSON constant {value!r} is not permitted")

    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=reject_nonfinite_constant,
        )
    except OSError as error:
        raise ValueError(f"could not read input JSON {path}: {error}") from error
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"input JSON is invalid: {error}") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate and analyze one trajectory research artifact."
    )
    parser.add_argument("input_json", help="completed research-evaluation JSON path")
    parser.add_argument("output_json", help="output analysis JSON path")
    args = parser.parse_args(argv)
    try:
        input_path = _input_path(args.input_json)
        output_path = _output_path(args.output_json, input_path)
        output = analyze_trajectory(_load_json(input_path), str(input_path))
        output_path.write_text(
            json.dumps(output, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except Exception as error:
        print(f"trajectory analysis failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
