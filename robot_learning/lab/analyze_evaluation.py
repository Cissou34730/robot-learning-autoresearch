"""Analyze one completed research-evaluation JSON artifact.

This is an analysis-only instrument.  It validates the episode-level
measurements recorded by :mod:`robot_learning.scenario.evaluation` and
produces descriptive radius- and angle-stratified summaries.  It does not
run a policy, alter evaluation behavior, or make an official-assessment or
causal claim.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


EXPECTED_SCHEMA_VERSION = 5
RADIUS_MIN_CM = 6.0
RADIUS_MAX_CM = 20.0
RADIUS_BIN_WIDTH_CM = 2.0
ANGLE_MIN_DEGREES = -180.0
ANGLE_MAX_DEGREES = 180.0
ANGLE_BIN_COUNT = 8
ANGLE_BIN_WIDTH_DEGREES = (
    ANGLE_MAX_DEGREES - ANGLE_MIN_DEGREES
) / ANGLE_BIN_COUNT


def _fail(message: str) -> ValueError:
    return ValueError(f"malformed research evaluation: {message}")


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _fail(f"{label} must be an object")
    return value


def _require_field(record: dict[str, Any], field: str, label: str) -> Any:
    if field not in record:
        raise _fail(f"{label} is missing required field {field!r}")
    return record[field]


def _require_integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail(f"{label} must be an integer")
    return value


def _require_nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _fail(f"{label} must be a non-empty string")
    return value


def _require_nonnegative_integer(value: Any, label: str) -> int:
    result = _require_integer(value, label)
    if result < 0:
        raise _fail(f"{label} must be non-negative")
    return result


def _require_finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise _fail(f"{label} must be a finite number")
    return result


def _require_nonnegative_number(value: Any, label: str) -> float:
    result = _require_finite_number(value, label)
    if result < 0.0:
        raise _fail(f"{label} must be non-negative")
    return result


def _optional_nonnegative_number(
    record: dict[str, Any], field: str, label: str
) -> float | None:
    if field not in record or record[field] is None:
        return None
    return _require_nonnegative_number(record[field], label)


def _validate_fraction(
    record: dict[str, Any], field: str, label: str
) -> float | None:
    value = _optional_nonnegative_number(record, field, label)
    if value is not None and value > 1.0:
        raise _fail(f"{label} must be between 0 and 1")
    return value


def _validate_input(
    artifact: Any,
) -> tuple[dict[str, Any], dict[int, dict[str, Any]], dict[int, dict[str, Any]]]:
    root = _require_object(artifact, "artifact")

    official_benchmark = _require_field(root, "official_benchmark", "artifact")
    if official_benchmark is not False:
        raise _fail("artifact.official_benchmark must be boolean false")
    _require_nonempty_string(
        _require_field(root, "model", "artifact"), "artifact.model"
    )

    schema_version = _require_field(root, "schema_version", "artifact")
    if _require_integer(schema_version, "artifact.schema_version") != EXPECTED_SCHEMA_VERSION:
        raise _fail(
            "artifact.schema_version must be "
            f"{EXPECTED_SCHEMA_VERSION} for a research evaluation"
        )

    episode_results_value = _require_field(root, "episode_results", "artifact")
    if not isinstance(episode_results_value, list) or not episode_results_value:
        raise _fail("artifact.episode_results must be a non-empty array")

    declared_episodes = _require_field(root, "episodes", "artifact")
    declared_episodes = _require_nonnegative_integer(
        declared_episodes, "artifact.episodes"
    )
    if declared_episodes != len(episode_results_value):
        raise _fail(
            "artifact.episodes does not match the episode_results length "
            f"({declared_episodes} != {len(episode_results_value)})"
        )

    results_by_episode: dict[int, dict[str, Any]] = {}
    for position, raw_result in enumerate(episode_results_value):
        result = _require_object(raw_result, f"episode_results[{position}]")
        episode = _require_nonnegative_integer(
            _require_field(result, "episode", f"episode_results[{position}]"),
            f"episode_results[{position}].episode",
        )
        if episode in results_by_episode:
            raise _fail(f"episode_results has duplicate episode index {episode}")
        success = _require_field(
            result, "success", f"episode_results[{position}]"
        )
        if not isinstance(success, bool):
            raise _fail(
                f"episode_results[{position}].success must be a boolean"
            )
        results_by_episode[episode] = result

    evidence = _require_object(
        _require_field(root, "research_evidence", "artifact"),
        "artifact.research_evidence",
    )
    diagnostics_value = _require_field(
        evidence, "episode_diagnostics", "artifact.research_evidence"
    )
    if not isinstance(diagnostics_value, list):
        raise _fail(
            "artifact.research_evidence.episode_diagnostics must be an array"
        )
    if len(diagnostics_value) != len(episode_results_value):
        raise _fail(
            "episode_diagnostics must contain exactly one row per episode "
            f"({len(diagnostics_value)} != {len(episode_results_value)})"
        )

    diagnostics_by_episode: dict[int, dict[str, Any]] = {}
    for position, raw_diagnostic in enumerate(diagnostics_value):
        diagnostic = _require_object(
            raw_diagnostic, f"episode_diagnostics[{position}]"
        )
        episode = _require_nonnegative_integer(
            _require_field(
                diagnostic, "episode", f"episode_diagnostics[{position}]"
            ),
            f"episode_diagnostics[{position}].episode",
        )
        if episode in diagnostics_by_episode:
            raise _fail(
                f"episode_diagnostics has duplicate episode index {episode}"
            )
        if episode not in results_by_episode:
            raise _fail(
                f"episode_diagnostics episode {episode} has no matching "
                "episode_result"
            )

        radius = _require_finite_number(
            _require_field(
                diagnostic,
                "target_radius_cm",
                f"episode_diagnostics[{position}]",
            ),
            f"episode_diagnostics[{position}].target_radius_cm",
        )
        if not RADIUS_MIN_CM <= radius <= RADIUS_MAX_CM:
            raise _fail(
                f"episode_diagnostics[{position}].target_radius_cm must be "
                f"within [{RADIUS_MIN_CM:g}, {RADIUS_MAX_CM:g}] cm"
            )

        angle = _require_finite_number(
            _require_field(
                diagnostic,
                "target_angle_degrees",
                f"episode_diagnostics[{position}]",
            ),
            f"episode_diagnostics[{position}].target_angle_degrees",
        )
        if not ANGLE_MIN_DEGREES <= angle < ANGLE_MAX_DEGREES:
            raise _fail(
                f"episode_diagnostics[{position}].target_angle_degrees must "
                f"be in [{ANGLE_MIN_DEGREES:g}, {ANGLE_MAX_DEGREES:g})"
            )

        first_reach_step = _require_field(
            diagnostic,
            "first_reach_step",
            f"episode_diagnostics[{position}]",
        )
        if first_reach_step is not None:
            _require_nonnegative_integer(
                first_reach_step,
                f"episode_diagnostics[{position}].first_reach_step",
            )
        _require_nonnegative_integer(
            _require_field(
                diagnostic, "max_held_steps", f"episode_diagnostics[{position}]"
            ),
            f"episode_diagnostics[{position}].max_held_steps",
        )
        _require_nonnegative_number(
            _require_field(
                diagnostic,
                "final_endpoint_speed_mps",
                f"episode_diagnostics[{position}]",
            ),
            f"episode_diagnostics[{position}].final_endpoint_speed_mps",
        )
        branch = _require_field(
            diagnostic,
            "final_elbow_branch",
            f"episode_diagnostics[{position}]",
        )
        if not isinstance(branch, str) or not branch:
            raise _fail(
                f"episode_diagnostics[{position}].final_elbow_branch must "
                "be a non-empty string"
            )

        # Validate optional measurements here, even when they are not used in
        # a particular aggregate.  Null means that the measurement did not
        # apply; malformed present values must not be silently skipped.
        _optional_nonnegative_number(
            diagnostic,
            "first_reach_endpoint_speed_mps",
            f"episode_diagnostics[{position}].first_reach_endpoint_speed_mps",
        )
        _validate_fraction(
            diagnostic,
            "action_saturation_fraction",
            f"episode_diagnostics[{position}].action_saturation_fraction",
        )
        diagnostics_by_episode[episode] = diagnostic

    if set(results_by_episode) != set(diagnostics_by_episode):
        raise _fail(
            "episode_results and episode_diagnostics must have the same "
            "episode indices"
        )
    return root, results_by_episode, diagnostics_by_episode


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _radius_bins() -> list[dict[str, Any]]:
    bins: list[dict[str, Any]] = []
    count = int((RADIUS_MAX_CM - RADIUS_MIN_CM) / RADIUS_BIN_WIDTH_CM)
    for index in range(count):
        lower = RADIUS_MIN_CM + index * RADIUS_BIN_WIDTH_CM
        upper = lower + RADIUS_BIN_WIDTH_CM
        bins.append(
            {
                "label": f"[{lower:g}, {upper:g}) cm"
                if upper < RADIUS_MAX_CM
                else f"[{lower:g}, {upper:g}] cm",
                "lower_cm": lower,
                "upper_cm": upper,
                "lower_inclusive": True,
                "upper_inclusive": upper == RADIUS_MAX_CM,
                "episodes": [],
            }
        )
    return bins


def _angle_bins() -> list[dict[str, Any]]:
    bins: list[dict[str, Any]] = []
    for index in range(ANGLE_BIN_COUNT):
        lower = ANGLE_MIN_DEGREES + index * ANGLE_BIN_WIDTH_DEGREES
        upper = lower + ANGLE_BIN_WIDTH_DEGREES
        bins.append(
            {
                "label": f"[{lower:g}, {upper:g}) degrees",
                "lower_degrees": lower,
                "upper_degrees": upper,
                "lower_inclusive": True,
                "upper_inclusive": False,
                "episodes": [],
            }
        )
    return bins


def _bin_for(value: float, bins: list[dict[str, Any]], lower_key: str) -> int:
    for index, bin_record in enumerate(bins):
        lower = bin_record[lower_key]
        upper_key = (
            "upper_cm" if lower_key == "lower_cm" else "upper_degrees"
        )
        upper = bin_record[upper_key]
        is_last = index == len(bins) - 1
        if lower <= value < upper or (is_last and value == upper):
            return index
    raise _fail(f"value {value!r} did not fit a declared analysis bin")


def _bin_summary(
    episodes: list[tuple[dict[str, Any], dict[str, Any]]],
) -> dict[str, Any]:
    episode_count = len(episodes)
    success_count = sum(
        1 for result, _ in episodes if result["success"] is True
    )
    reached = [
        (result, diagnostic)
        for result, diagnostic in episodes
        if diagnostic["first_reach_step"] is not None
    ]
    reach_count = len(reached)
    hold_failure_count = sum(
        1 for result, diagnostic in reached if result["success"] is False
    )

    first_reach_steps = [
        float(diagnostic["first_reach_step"])
        for _, diagnostic in reached
    ]
    max_held_steps = [
        float(diagnostic["max_held_steps"]) for _, diagnostic in episodes
    ]
    first_reach_speeds = [
        speed
        for _, diagnostic in reached
        if (
            speed := _optional_nonnegative_number(
                diagnostic,
                "first_reach_endpoint_speed_mps",
                "first_reach_endpoint_speed_mps",
            )
        )
        is not None
    ]
    final_endpoint_speeds = [
        float(diagnostic["final_endpoint_speed_mps"])
        for _, diagnostic in episodes
    ]
    saturation_fractions = [
        fraction
        for _, diagnostic in episodes
        if (
            fraction := _validate_fraction(
                diagnostic,
                "action_saturation_fraction",
                "action_saturation_fraction",
            )
        )
        is not None
    ]

    return {
        "episode_count": episode_count,
        "success_count": success_count,
        "success_rate": _rate(success_count, episode_count),
        "first_reach_count": reach_count,
        "first_reach_rate": _rate(reach_count, episode_count),
        "no_reach_count": episode_count - reach_count,
        "hold_failure_count": hold_failure_count,
        "mean_first_reach_step": _mean(first_reach_steps),
        "mean_max_held_steps": _mean(max_held_steps),
        "mean_first_reach_endpoint_speed_mps": _mean(first_reach_speeds),
        "mean_final_endpoint_speed_mps": _mean(final_endpoint_speeds),
        "mean_action_saturation_fraction": _mean(saturation_fractions),
    }


def analyze_evaluation(artifact: Any, input_path: str) -> dict[str, Any]:
    """Validate and summarize a loaded research-evaluation artifact."""

    root, results_by_episode, diagnostics_by_episode = _validate_input(artifact)
    episodes = [
        (results_by_episode[episode], diagnostics_by_episode[episode])
        for episode in sorted(results_by_episode)
    ]

    radius_bins = _radius_bins()
    angle_bins = _angle_bins()
    for result, diagnostic in episodes:
        radius_index = _bin_for(
            float(diagnostic["target_radius_cm"]), radius_bins, "lower_cm"
        )
        angle_index = _bin_for(
            float(diagnostic["target_angle_degrees"]),
            angle_bins,
            "lower_degrees",
        )
        radius_bins[radius_index]["episodes"].append((result, diagnostic))
        angle_bins[angle_index]["episodes"].append((result, diagnostic))

    overall = _bin_summary(episodes)
    for bin_record in radius_bins:
        bin_record["statistics"] = _bin_summary(bin_record.pop("episodes"))
    for bin_record in angle_bins:
        bin_record["statistics"] = _bin_summary(bin_record.pop("episodes"))

    branch_counts: dict[str, int] = {}
    for _, diagnostic in episodes:
        branch = diagnostic["final_elbow_branch"]
        branch_counts[branch] = branch_counts.get(branch, 0) + 1

    saturation_values = [
        fraction
        for _, diagnostic in episodes
        if (
            fraction := _validate_fraction(
                diagnostic,
                "action_saturation_fraction",
                "action_saturation_fraction",
            )
        )
        is not None
    ]
    saturation_present_count = len(saturation_values)
    saturated_episode_count = sum(
        1 for fraction in saturation_values if fraction > 0.0
    )

    return {
        "analysis": {
            "kind": "research_evaluation_stratified_analysis",
            "analysis_only": True,
            "official_assessment": False,
            "scientific_causality_inferred": False,
        },
        "input_artifact": {
            "path": input_path,
            "schema_version": root["schema_version"],
            "model": root["model"],
        },
        "episode_count": len(episodes),
        "overall": overall,
        "radius_bins": {
            "range_cm": [RADIUS_MIN_CM, RADIUS_MAX_CM],
            "boundary_convention": (
                "Seven explicit 2 cm bins; lower bounds are inclusive, "
                "upper bounds are exclusive except the final upper bound, "
                "which is inclusive: [6,8), [8,10), [10,12), [12,14), "
                "[14,16), [16,18), [18,20]."
            ),
            "bins": radius_bins,
        },
        "angle_bins": {
            "range_degrees": [ANGLE_MIN_DEGREES, ANGLE_MAX_DEGREES],
            "boundary_convention": (
                "Eight equal-width 45 degree bins; lower bounds are "
                "inclusive and upper bounds are exclusive, spanning "
                "[-180,180)."
            ),
            "bins": angle_bins,
        },
        "final_elbow_branch_counts": branch_counts,
        "saturation_summary": {
            "episode_count": len(episodes),
            "fraction_present_episode_count": saturation_present_count,
            "saturated_episode_count": saturated_episode_count,
            "saturated_episode_rate": _rate(
                saturated_episode_count, saturation_present_count
            ),
            "mean_action_saturation_fraction": _mean(saturation_values),
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


def _output_path(argument: str) -> Path:
    if not argument.strip():
        raise ValueError("output JSON path must not be empty")
    path = Path(argument)
    if path.exists() and path.is_dir():
        raise ValueError(f"output path is a directory, not a JSON file: {path}")
    if not path.parent.exists():
        raise ValueError(f"output parent directory does not exist: {path.parent}")
    if not path.parent.is_dir():
        raise ValueError(f"output parent is not a directory: {path.parent}")
    return path


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"could not read input JSON {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ValueError(
            f"input JSON is invalid at line {error.lineno}, column "
            f"{error.colno}: {error.msg}"
        ) from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and summarize one completed research-evaluation JSON "
            "artifact."
        )
    )
    parser.add_argument("input_json", help="completed evaluation JSON artifact")
    parser.add_argument("output_json", help="path for the analysis JSON artifact")
    args = parser.parse_args(argv)
    try:
        input_path = _input_path(args.input_json)
        output_path = _output_path(args.output_json)
        analysis = analyze_evaluation(
            _load_json(input_path), str(input_path)
        )
        output_path.write_text(
            json.dumps(analysis, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except Exception as error:
        print(f"evaluation analysis failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
