"""Compare two research-evaluation artifacts by target geometry.

The module deliberately consumes the episode outcome from ``episode_results``
and the geometry and hold diagnostics from ``research_evidence`` separately.
Those records are joined by ``episode_seed`` so that an episode number being
different between artifacts cannot silently change the measured result.

Usage::

    python -m robot_learning.lab.evaluate_strata \
        CANDIDATE_JSON CANDIDATE_LABEL REFERENCE_JSON REFERENCE_LABEL OUTPUT_JSON
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
RESEARCH_EVALUATION_SCHEMA_VERSION = 5

RADIUS_BINS = (
    ("[6,10) cm", 6.0, 10.0, False),
    ("[10,14) cm", 10.0, 14.0, False),
    ("[14,18) cm", 14.0, 18.0, False),
    ("[18,20] cm", 18.0, 20.0, True),
)
ANGLE_BINS = (
    ("[-180,-90) degrees", -180.0, -90.0, False),
    ("[-90,0) degrees", -90.0, 0.0, False),
    ("[0,90) degrees", 0.0, 90.0, False),
    ("[90,180] degrees", 90.0, 180.0, True),
)


class ArtifactError(ValueError):
    """Raised when an input evaluation artifact cannot be analyzed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ArtifactError(message)


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _number(value: Any, field: str) -> float:
    _require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        f"{field} must be a number",
    )
    result = float(value)
    _require(math.isfinite(result), f"{field} must be finite")
    return result


def _label(value: Any, path: Path, argument_name: str) -> str:
    _require(
        isinstance(value, str) and bool(value.strip()),
        f"{path}: {argument_name} must be a non-empty label",
    )
    return value


def _load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"{path}: cannot read JSON artifact: {exc}") from exc
    _require(isinstance(value, dict), f"{path}: artifact root must be an object")
    return value


def _validate_and_join(
    path: Path, policy_label: str
) -> tuple[str, dict[int, dict[str, Any]]]:
    artifact = _load_json(path)
    _require(
        artifact.get("schema_version") == RESEARCH_EVALUATION_SCHEMA_VERSION,
        f"{path}: expected research_evaluation schema_version "
        f"{RESEARCH_EVALUATION_SCHEMA_VERSION}",
    )
    label = policy_label

    episode_results = artifact.get("episode_results")
    _require(isinstance(episode_results, list), f"{path}: episode_results must be a list")
    episodes = artifact.get("episodes")
    _require(_is_integer(episodes) and episodes >= 1, f"{path}: episodes must be a positive integer")
    _require(
        episodes == len(episode_results),
        f"{path}: episodes does not match episode_results length",
    )

    research_evidence = artifact.get("research_evidence")
    _require(isinstance(research_evidence, dict), f"{path}: research_evidence must be an object")
    diagnostics = research_evidence.get("episode_diagnostics")
    _require(
        isinstance(diagnostics, list),
        f"{path}: research_evidence.episode_diagnostics must be a list",
    )
    _require(
        len(diagnostics) == len(episode_results),
        f"{path}: episode_results and episode_diagnostics have different lengths",
    )
    units = research_evidence.get("units")
    _require(isinstance(units, dict), f"{path}: research_evidence.units must be an object")
    _require(
        units.get("distance") == "cm" and units.get("time") == "control_steps",
        f"{path}: research_evidence units must be cm and control_steps",
    )

    outcomes_by_seed: dict[int, dict[str, Any]] = {}
    for index, outcome in enumerate(episode_results):
        prefix = f"{path}: episode result {index}"
        _require(isinstance(outcome, dict), f"{prefix} must be an object")
        outcome_seed = outcome.get("episode_seed")
        _require(
            _is_integer(outcome_seed),
            f"{prefix}: episode_seed must be an integer",
        )
        _require(
            outcome_seed not in outcomes_by_seed,
            f"{path}: duplicate episode_seed {outcome_seed} in episode_results",
        )
        success = outcome.get("success")
        _require(isinstance(success, bool), f"{prefix}: success must be boolean")
        steps = outcome.get("steps")
        _require(
            _is_integer(steps) and steps >= 0,
            f"{prefix}: steps must be a non-negative integer",
        )
        outcomes_by_seed[outcome_seed] = {"success": success, "steps": steps}

    diagnostics_by_seed: dict[int, dict[str, Any]] = {}
    for index, diagnostic in enumerate(diagnostics):
        prefix = f"{path}: diagnostic record {index}"
        _require(isinstance(diagnostic, dict), f"{prefix} must be an object")
        diagnostic_seed = diagnostic.get("episode_seed")
        _require(
            _is_integer(diagnostic_seed),
            f"{prefix}: episode_seed must be an integer",
        )
        _require(
            diagnostic_seed not in diagnostics_by_seed,
            f"{path}: duplicate episode_seed {diagnostic_seed} in episode_diagnostics",
        )
        for field in (
            "first_reach_step",
            "target_radius_cm",
            "target_angle_degrees",
            "min_distance_cm",
            "max_held_steps",
            "hold_interruptions",
        ):
            _require(field in diagnostic, f"{prefix}: missing {field}")
        first_reach_step = diagnostic.get("first_reach_step")
        _require(
            first_reach_step is None
            or (_is_integer(first_reach_step) and first_reach_step >= 1),
            f"{prefix}: first_reach_step must be null or a positive integer",
        )
        radius = _number(
            diagnostic.get("target_radius_cm"),
            f"{prefix}: target_radius_cm",
        )
        angle = _number(
            diagnostic.get("target_angle_degrees"),
            f"{prefix}: target_angle_degrees",
        )
        _require(
            6.0 <= radius <= 20.0,
            f"{prefix}: target_radius_cm is outside the official [6,20] range",
        )
        _require(
            -180.0 <= angle <= 180.0,
            f"{prefix}: target_angle_degrees is outside the official [-180,180] range",
        )

        minimum_distance = _number(
            diagnostic.get("min_distance_cm"),
            f"{prefix}: min_distance_cm",
        )
        _require(
            minimum_distance >= 0.0,
            f"{prefix}: min_distance_cm must be non-negative",
        )
        maximum_held_steps = diagnostic.get("max_held_steps")
        _require(
            _is_integer(maximum_held_steps) and maximum_held_steps >= 0,
            f"{prefix}: max_held_steps must be a non-negative integer",
        )
        interruptions = diagnostic.get("hold_interruptions")
        _require(
            _is_integer(interruptions) and interruptions >= 0,
            f"{prefix}: hold_interruptions must be a non-negative integer",
        )
        diagnostics_by_seed[diagnostic_seed] = {
            "first_reach_step": first_reach_step,
            "first_reach": first_reach_step is not None,
            "min_distance_cm": minimum_distance,
            "max_held_steps": maximum_held_steps,
            "hold_interruptions": interruptions,
            "radius_cm": radius,
            "angle_degrees": angle,
        }
    _require(
        set(outcomes_by_seed) == set(diagnostics_by_seed),
        f"{path}: episode_results and episode_diagnostics have different episode_seed sets",
    )
    for seed, outcome in outcomes_by_seed.items():
        diagnostic = diagnostics_by_seed[seed]
        _require(
            not outcome["success"] or diagnostic["first_reach"],
            f"{path}: successful episode_seed {seed} has no first reach",
        )
        first_reach_step = diagnostic["first_reach_step"]
        _require(
            first_reach_step is None or first_reach_step <= outcome["steps"],
            f"{path}: first reach for episode_seed {seed} exceeds episode steps",
        )
        _require(
            diagnostic["max_held_steps"] <= outcome["steps"],
            f"{path}: maximum held steps for episode_seed {seed} exceeds episode steps",
        )
        _require(
            diagnostic["hold_interruptions"] <= outcome["steps"],
            f"{path}: hold interruptions for episode_seed {seed} exceed episode steps",
        )
    return label, {
        seed: {**outcomes_by_seed[seed], **diagnostics_by_seed[seed]}
        for seed in outcomes_by_seed
    }


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(records)
    successes = sum(record["success"] for record in records)
    first_reach_count = sum(record["first_reach"] for record in records)
    reached_successes = sum(
        record["success"] for record in records if record["first_reach"]
    )
    episodes_with_interruptions = sum(
        record["hold_interruptions"] > 0 for record in records
    )
    return {
        "episode_count": count,
        "successes": successes,
        "success_rate": _rate(successes, count),
        "first_reach_count": first_reach_count,
        "first_reach_rate": _rate(first_reach_count, count),
        "no_first_reach_count": count - first_reach_count,
        "mean_min_distance_cm": (
            sum(record["min_distance_cm"] for record in records) / count
            if count
            else None
        ),
        "mean_max_held_steps": (
            sum(record["max_held_steps"] for record in records) / count
            if count
            else None
        ),
        "episodes_with_hold_interruptions": episodes_with_interruptions,
        "total_interruptions": sum(
            record["hold_interruptions"] for record in records
        ),
        "reached_episode_success_rate": (
            _rate(reached_successes, first_reach_count)
            if first_reach_count
            else None
        ),
    }


def _in_bin(value: float, lower: float, upper: float, include_upper: bool) -> bool:
    return lower <= value <= upper if include_upper else lower <= value < upper


def _strata(
    records: list[dict[str, Any]],
    bins: tuple[tuple[str, float, float, bool], ...],
    coordinate: str,
) -> list[dict[str, Any]]:
    result = []
    assigned = 0
    for label, lower, upper, include_upper in bins:
        selected = [
            record
            for record in records
            if _in_bin(record[coordinate], lower, upper, include_upper)
        ]
        assigned += len(selected)
        result.append({"bin": label, "metrics": _metrics(selected)})
    _require(
        assigned == len(records),
        f"internal error: not every record was assigned to a {coordinate} bin",
    )
    return result


def _policy_result(label: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "label": label,
        "overall": _metrics(records),
        "radius_bins": _strata(records, RADIUS_BINS, "radius_cm"),
        "angle_bins": _strata(records, ANGLE_BINS, "angle_degrees"),
    }


def analyze(
    candidate_path: Path,
    candidate_label: str,
    reference_path: Path,
    reference_label: str,
) -> dict[str, Any]:
    candidate_label = _label(candidate_label, candidate_path, "candidate policy label")
    reference_label = _label(reference_label, reference_path, "reference policy label")
    candidate_label, candidate_records = _validate_and_join(
        candidate_path, candidate_label
    )
    reference_label, reference_records = _validate_and_join(
        reference_path, reference_label
    )
    _require(
        set(candidate_records) == set(reference_records),
        "candidate and reference artifacts have different episode_seed sets",
    )
    for seed in candidate_records:
        candidate_record = candidate_records[seed]
        reference_record = reference_records[seed]
        _require(
            math.isclose(
                candidate_record["radius_cm"],
                reference_record["radius_cm"],
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            and math.isclose(
                candidate_record["angle_degrees"],
                reference_record["angle_degrees"],
                rel_tol=0.0,
                abs_tol=1e-12,
            ),
            f"candidate and reference target geometry differs for episode_seed {seed}",
        )
    seeds = sorted(candidate_records)
    candidate = [candidate_records[seed] for seed in seeds]
    reference = [reference_records[seed] for seed in seeds]
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "research_evaluation_strata",
        "inputs": {
            "candidate": {"label": candidate_label},
            "reference": {"label": reference_label},
        },
        "policies": {
            "candidate": _policy_result(candidate_label, candidate),
            "reference": _policy_result(reference_label, reference),
        },
    }


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 5:
        raise ArtifactError(
            "expected exactly five arguments: candidate JSON, candidate label, "
            "reference JSON, reference label, output JSON"
        )
    candidate_path = Path(arguments[0])
    candidate_label = arguments[1]
    reference_path = Path(arguments[2])
    reference_label = arguments[3]
    output_path = Path(arguments[4])
    result = analyze(
        candidate_path,
        candidate_label,
        reference_path,
        reference_label,
    )
    try:
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
    except OSError as exc:
        raise ArtifactError(f"{output_path}: cannot write output JSON: {exc}") from exc
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ArtifactError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
