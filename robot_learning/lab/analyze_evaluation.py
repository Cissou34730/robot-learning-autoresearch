"""Compare two completed research-evaluation artifacts.

The evaluator owns episode semantics.  This module only validates its recorded
rows and produces deterministic, geometry-stratified summaries from them.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


COMPARISON_SCHEMA_VERSION = 1
EVALUATION_SCHEMA_VERSION = 5
ANGLE_BIN_DEFINITIONS = (
    (-180.0, -135.0, True, False),
    (-135.0, -90.0, True, False),
    (-90.0, -45.0, True, False),
    (-45.0, 0.0, True, False),
    (0.0, 45.0, True, False),
    (45.0, 90.0, True, False),
    (90.0, 135.0, True, False),
    (135.0, 180.0, True, False),
)
RADIUS_BIN_DEFINITIONS = (
    ("inner", 0.0, 14.0, True, False),
    ("outer", 14.0, None, True, True),
)

_OUTCOME_FIELDS = (
    "episode",
    "episode_seed",
    "success",
    "reward_total",
    "steps",
    "terminated",
    "truncated",
)
_DIAGNOSTIC_FIELDS = (
    "episode",
    "episode_seed",
    "target_radius_cm",
    "target_angle_degrees",
    "min_distance_cm",
    "final_distance_cm",
    "first_reach_step",
    "max_held_steps",
    "in_tolerance_steps",
    "hold_interruptions",
)
_METRIC_FIELDS = (
    "episode_count",
    "successes",
    "success_percent",
    "no_entry_count",
    "post_entry_failure_count",
    "truncated_count",
    "mean_first_reach_step",
    "mean_min_distance_cm",
    "mean_final_distance_cm",
    "mean_max_held_steps",
    "total_in_tolerance_steps",
    "total_hold_interruptions",
)


def _error(source: str, message: str) -> ValueError:
    return ValueError(f"{source}: {message}")


def _require_object(value: Any, source: str, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _error(source, f"{location} must be an object")
    return value


def _require_array(value: Any, source: str, location: str) -> list[Any]:
    if not isinstance(value, list):
        raise _error(source, f"{location} must be an array")
    if not value:
        raise _error(source, f"{location} must not be empty")
    return value


def _require_int(value: Any, source: str, location: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _error(source, f"{location} must be an integer")
    if value < minimum:
        raise _error(source, f"{location} must be at least {minimum}")
    return value


def _require_bool(value: Any, source: str, location: str) -> bool:
    if not isinstance(value, bool):
        raise _error(source, f"{location} must be a boolean")
    return value


def _require_number(
    value: Any, source: str, location: str, *, minimum: float | None = None
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _error(source, f"{location} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise _error(source, f"{location} must be a finite number")
    if minimum is not None and number < minimum:
        raise _error(source, f"{location} must be at least {minimum}")
    return number


def _require_optional_step(value: Any, source: str, location: str) -> int | None:
    if value is None:
        return None
    return _require_int(value, source, location)


def _validate_fields(
    row: dict[str, Any], fields: tuple[str, ...], source: str, location: str
) -> None:
    missing = [field for field in fields if field not in row]
    if missing:
        raise _error(source, f"{location} is missing fields: {', '.join(missing)}")


def _validate_evaluation(
    artifact: Any, source: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    document = _require_object(artifact, source, "artifact")
    if document.get("schema_version") != EVALUATION_SCHEMA_VERSION:
        raise _error(
            source,
            f"schema_version must be {EVALUATION_SCHEMA_VERSION}",
        )

    outcomes = _require_array(document.get("episode_results"), source, "episode_results")
    evidence = _require_object(
        document.get("research_evidence"), source, "research_evidence"
    )
    diagnostics = _require_array(
        evidence.get("episode_diagnostics"),
        source,
        "research_evidence.episode_diagnostics",
    )
    if len(outcomes) != len(diagnostics):
        raise _error(
            source,
            "episode_results and research_evidence.episode_diagnostics must have "
            "the same nonzero length",
        )

    validated_outcomes: list[dict[str, Any]] = []
    validated_diagnostics: list[dict[str, Any]] = []
    outcome_seeds: set[int] = set()
    diagnostic_seeds: set[int] = set()

    for index, row_value in enumerate(outcomes):
        location = f"episode_results[{index}]"
        row = _require_object(row_value, source, location)
        _validate_fields(row, _OUTCOME_FIELDS, source, location)
        episode_seed = _require_int(row["episode_seed"], source, f"{location}.episode_seed")
        if episode_seed in outcome_seeds:
            raise _error(source, f"duplicate episode_seed {episode_seed} in episode_results")
        outcome_seeds.add(episode_seed)
        _require_int(row["episode"], source, f"{location}.episode")
        _require_bool(row["success"], source, f"{location}.success")
        _require_number(row["reward_total"], source, f"{location}.reward_total")
        _require_int(row["steps"], source, f"{location}.steps")
        _require_bool(row["terminated"], source, f"{location}.terminated")
        _require_bool(row["truncated"], source, f"{location}.truncated")
        validated_outcomes.append(row)

    for index, row_value in enumerate(diagnostics):
        location = f"research_evidence.episode_diagnostics[{index}]"
        row = _require_object(row_value, source, location)
        _validate_fields(row, _DIAGNOSTIC_FIELDS, source, location)
        episode_seed = _require_int(row["episode_seed"], source, f"{location}.episode_seed")
        if episode_seed in diagnostic_seeds:
            raise _error(
                source, f"duplicate episode_seed {episode_seed} in episode_diagnostics"
            )
        diagnostic_seeds.add(episode_seed)
        _require_int(row["episode"], source, f"{location}.episode")
        _require_number(
            row["target_radius_cm"], source, f"{location}.target_radius_cm", minimum=0.0
        )
        angle = _require_number(
            row["target_angle_degrees"],
            source,
            f"{location}.target_angle_degrees",
        )
        if angle < -180.0 or angle > 180.0:
            raise _error(
                source,
                f"{location}.target_angle_degrees must be in [-180, 180]",
            )
        _require_number(row["min_distance_cm"], source, f"{location}.min_distance_cm")
        _require_number(row["final_distance_cm"], source, f"{location}.final_distance_cm")
        _require_optional_step(
            row["first_reach_step"], source, f"{location}.first_reach_step"
        )
        _require_int(row["max_held_steps"], source, f"{location}.max_held_steps")
        _require_int(row["in_tolerance_steps"], source, f"{location}.in_tolerance_steps")
        _require_int(row["hold_interruptions"], source, f"{location}.hold_interruptions")
        validated_diagnostics.append(row)

    if outcome_seeds != diagnostic_seeds:
        only_outcomes = sorted(outcome_seeds - diagnostic_seeds)
        only_diagnostics = sorted(diagnostic_seeds - outcome_seeds)
        raise _error(
            source,
            "episode_seed values do not match between episode_results and "
            f"episode_diagnostics (outcomes_only={only_outcomes}, "
            f"diagnostics_only={only_diagnostics})",
        )

    return validated_outcomes, validated_diagnostics, document


def _read_evaluation(path: Path, label: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            artifact = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise _error(label, f"could not read JSON artifact {path}: {exc}") from exc
    return _validate_evaluation(artifact, label)


def _model_metadata(document: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ("model", "model_name", "fingerprint", "model_fingerprint"):
        if key in document:
            value = document[key]
            if not isinstance(value, str):
                raise ValueError(f"artifact field {key} must be a string when present")
            metadata[key] = value
    return metadata


def _join_rows(
    outcomes: list[dict[str, Any]], diagnostics: list[dict[str, Any]]
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    outcomes_by_seed = {row["episode_seed"]: row for row in outcomes}
    diagnostics_by_seed = {row["episode_seed"]: row for row in diagnostics}
    return [
        (outcomes_by_seed[seed], diagnostics_by_seed[seed])
        for seed in sorted(outcomes_by_seed)
    ]


def _angle_bin(angle: float) -> int:
    if angle == 180.0:
        return len(ANGLE_BIN_DEFINITIONS) - 1
    for index, (_, upper, _, _) in enumerate(ANGLE_BIN_DEFINITIONS):
        if angle < upper:
            return index
    raise ValueError(f"angle {angle} did not fit an angle bin")


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _summarize(
    rows: list[tuple[dict[str, Any], dict[str, Any]]],
) -> dict[str, int | float | None]:
    successes = sum(1 for outcome, _ in rows if outcome["success"])
    no_entry = [
        (outcome, diagnostic)
        for outcome, diagnostic in rows
        if diagnostic["first_reach_step"] is None or diagnostic["max_held_steps"] == 0
    ]
    post_entry_failures = [
        (outcome, diagnostic)
        for outcome, diagnostic in rows
        if not outcome["success"]
        and diagnostic["first_reach_step"] is not None
        and diagnostic["max_held_steps"] > 0
    ]
    first_reach_steps = [
        float(diagnostic["first_reach_step"])
        for _, diagnostic in rows
        if diagnostic["first_reach_step"] is not None
    ]
    return {
        "episode_count": len(rows),
        "successes": successes,
        "success_percent": 100.0 * successes / len(rows) if rows else None,
        "no_entry_count": len(no_entry),
        "post_entry_failure_count": len(post_entry_failures),
        "truncated_count": sum(1 for outcome, _ in rows if outcome["truncated"]),
        "mean_first_reach_step": _mean(first_reach_steps),
        "mean_min_distance_cm": _mean(
            [float(diagnostic["min_distance_cm"]) for _, diagnostic in rows]
        ),
        "mean_final_distance_cm": _mean(
            [float(diagnostic["final_distance_cm"]) for _, diagnostic in rows]
        ),
        "mean_max_held_steps": _mean(
            [float(diagnostic["max_held_steps"]) for _, diagnostic in rows]
        ),
        "total_in_tolerance_steps": sum(
            diagnostic["in_tolerance_steps"] for _, diagnostic in rows
        ),
        "total_hold_interruptions": sum(
            diagnostic["hold_interruptions"] for _, diagnostic in rows
        ),
    }


def _difference(
    candidate: dict[str, int | float | None],
    reference: dict[str, int | float | None],
) -> dict[str, int | float | None]:
    delta: dict[str, int | float | None] = {}
    for field in _METRIC_FIELDS:
        candidate_value = candidate[field]
        reference_value = reference[field]
        if candidate_value is None or reference_value is None:
            delta[field] = None
        else:
            delta[field] = candidate_value - reference_value
    return delta


def _bin_definitions() -> dict[str, Any]:
    return {
        "radius_cm": [
            {
                "name": name,
                "lower": lower,
                "upper": upper,
                "lower_inclusive": lower_inclusive,
                "upper_inclusive": upper_inclusive,
            }
            for name, lower, upper, lower_inclusive, upper_inclusive in RADIUS_BIN_DEFINITIONS
        ],
        "angle_degrees": [
            {
                "name": f"[{int(lower)},{int(upper)}"
                + ")",
                "lower": lower,
                "upper": upper,
                "lower_inclusive": lower_inclusive,
                "upper_inclusive": upper_inclusive,
                **(
                    {"upper_endpoint_assignment": "180 degrees is assigned here"}
                    if upper == 180.0
                    else {}
                ),
            }
            for lower, upper, lower_inclusive, upper_inclusive in ANGLE_BIN_DEFINITIONS
        ],
    }


def compare_evaluations(
    candidate_path: str | Path,
    reference_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """Create a comparison artifact and return the document that was written."""
    candidate_path = Path(candidate_path)
    reference_path = Path(reference_path)
    output_path = Path(output_path)
    if output_path.resolve() in {candidate_path.resolve(), reference_path.resolve()}:
        raise ValueError("output_path must not overwrite either input artifact")

    candidate_outcomes, candidate_diagnostics, candidate_document = _read_evaluation(
        candidate_path, "candidate"
    )
    reference_outcomes, reference_diagnostics, reference_document = _read_evaluation(
        reference_path, "reference"
    )
    candidate_rows = _join_rows(candidate_outcomes, candidate_diagnostics)
    reference_rows = _join_rows(reference_outcomes, reference_diagnostics)
    candidate_seeds = [outcome["episode_seed"] for outcome, _ in candidate_rows]
    reference_seeds = [outcome["episode_seed"] for outcome, _ in reference_rows]
    if candidate_seeds != reference_seeds:
        raise ValueError(
            "candidate and reference must use the same episode panel; "
            f"candidate_seeds={candidate_seeds}, reference_seeds={reference_seeds}"
        )
    for (candidate_outcome, candidate_diagnostic), (
        _,
        reference_diagnostic,
    ) in zip(candidate_rows, reference_rows):
        seed = candidate_outcome["episode_seed"]
        candidate_geometry = (
            candidate_diagnostic["target_radius_cm"],
            candidate_diagnostic["target_angle_degrees"],
        )
        reference_geometry = (
            reference_diagnostic["target_radius_cm"],
            reference_diagnostic["target_angle_degrees"],
        )
        if candidate_geometry != reference_geometry:
            raise ValueError(
                "candidate and reference target geometry must match for every "
                f"episode_seed; seed {seed} has candidate "
                f"(radius_cm={candidate_geometry[0]}, "
                f"angle_degrees={candidate_geometry[1]}) versus reference "
                f"(radius_cm={reference_geometry[0]}, "
                f"angle_degrees={reference_geometry[1]})"
            )

    strata_rows: dict[str, dict[str, list[tuple[dict[str, Any], dict[str, Any]]]]] = {
        "radius": {"inner": [], "outer": []},
        "angle": {
            f"[{int(lower)},{int(upper)}"
            + ")": []
            for lower, upper, _, _ in ANGLE_BIN_DEFINITIONS
        },
    }

    def assign_rows(
        rows: list[tuple[dict[str, Any], dict[str, Any]]]
    ) -> dict[str, dict[str, list[tuple[dict[str, Any], dict[str, Any]]]]]:
        assigned = {
            "radius": {"inner": [], "outer": []},
            "angle": {name: [] for name in strata_rows["angle"]},
        }
        for outcome, diagnostic in rows:
            radius = float(diagnostic["target_radius_cm"])
            assigned["radius"]["inner" if radius < 14.0 else "outer"].append(
                (outcome, diagnostic)
            )
            angle_index = _angle_bin(float(diagnostic["target_angle_degrees"]))
            lower, upper, _, _ = ANGLE_BIN_DEFINITIONS[angle_index]
            name = f"[{int(lower)},{int(upper)})"
            assigned["angle"][name].append((outcome, diagnostic))
        return assigned

    candidate_strata = assign_rows(candidate_rows)
    reference_strata = assign_rows(reference_rows)

    candidate_summary: dict[str, Any] = {"overall": _summarize(candidate_rows)}
    reference_summary: dict[str, Any] = {"overall": _summarize(reference_rows)}
    delta_summary: dict[str, Any] = {"overall": {}}
    for group in ("radius", "angle"):
        candidate_summary[group] = {}
        reference_summary[group] = {}
        delta_summary[group] = {}
        for name in strata_rows[group]:
            candidate_summary[group][name] = _summarize(candidate_strata[group][name])
            reference_summary[group][name] = _summarize(reference_strata[group][name])
            delta_summary[group][name] = _difference(
                candidate_summary[group][name], reference_summary[group][name]
            )
    delta_summary["overall"] = _difference(
        candidate_summary["overall"], reference_summary["overall"]
    )

    result: dict[str, Any] = {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "artifact_type": "research_evaluation_comparison",
        "inputs": {
            "candidate": _model_metadata(candidate_document),
            "reference": _model_metadata(reference_document),
        },
        "shared_episode_panel": {
            "episode_count": len(candidate_seeds),
            "seed_range": {
                "start": min(candidate_seeds),
                "end": max(candidate_seeds),
            },
            "episode_seeds": candidate_seeds,
        },
        "bin_definitions": _bin_definitions(),
        "candidate": candidate_summary,
        "reference": reference_summary,
        "deltas": {"candidate_minus_reference": delta_summary},
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return result


def analyze_evaluations(
    candidate_path: str | Path,
    reference_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """Backward-compatible descriptive alias for :func:`compare_evaluations`."""
    return compare_evaluations(candidate_path, reference_path, output_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare candidate and reference research-evaluation artifacts."
    )
    parser.add_argument("candidate", type=Path)
    parser.add_argument("reference", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    compare_evaluations(args.candidate, args.reference, args.output)


if __name__ == "__main__":
    main()
