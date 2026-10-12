"""Analyze the geometry-stratified facts in a research evaluation artifact.

The analysis deliberately consumes the evaluator's recorded outcome and
diagnostic rows without recomputing task outcomes or changing task semantics.
It is a laboratory report of the artifact, not an evaluator or a causal
analysis.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


COMPLETE_HOLD_STEPS = 100
_REQUIRED_RESULT_FIELDS = ("episode", "success")
_REQUIRED_DIAGNOSTIC_FIELDS = (
    "episode",
    "target_radius_cm",
    "target_angle_degrees",
    "first_reach_step",
    "max_held_steps",
    "hold_interruptions",
)


class ArtifactValidationError(ValueError):
    """Raised when an evaluation artifact cannot support this analysis."""


def _load_json(path: str | Path) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ArtifactValidationError(
            f"non-finite JSON number {value!r} is not allowed"
        )

    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            artifact = json.load(handle, parse_constant=reject_constant)
    except json.JSONDecodeError as exc:
        raise ArtifactValidationError(f"invalid JSON artifact: {exc}") from exc
    if not isinstance(artifact, dict):
        raise ArtifactValidationError("the evaluation artifact must be a JSON object")
    return artifact


def _require_fields(
    row: dict[str, Any], fields: tuple[str, ...], row_kind: str, row_index: int
) -> None:
    missing = [field for field in fields if field not in row]
    if missing:
        names = ", ".join(repr(field) for field in missing)
        raise ArtifactValidationError(
            f"{row_kind} row {row_index} is missing required field(s): {names}"
        )


def _integer(value: Any, field: str, row_kind: str, episode: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ArtifactValidationError(
            f"{row_kind} episode {episode!r} field {field!r} must be an integer"
        )
    return value


def _nonnegative_integer(
    value: Any, field: str, row_kind: str, episode: Any
) -> int:
    number = _integer(value, field, row_kind, episode)
    if number < 0:
        raise ArtifactValidationError(
            f"{row_kind} episode {episode!r} field {field!r} must be non-negative"
        )
    return number


def _number(value: Any, field: str, row_kind: str, episode: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ArtifactValidationError(
            f"{row_kind} episode {episode!r} field {field!r} must be numeric"
        )
    number = float(value)
    if not math.isfinite(number):
        raise ArtifactValidationError(
            f"{row_kind} episode {episode!r} field {field!r} must be finite"
        )
    return number


def _index_rows(
    rows: Any, row_kind: str, required_fields: tuple[str, ...]
) -> dict[int, dict[str, Any]]:
    if not isinstance(rows, list):
        raise ArtifactValidationError(f"{row_kind} must be a JSON array")
    indexed: dict[int, dict[str, Any]] = {}
    for row_index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ArtifactValidationError(
                f"{row_kind} row {row_index} must be a JSON object"
            )
        _require_fields(row, required_fields, row_kind, row_index)
        episode_value = row["episode"]
        episode = _nonnegative_integer(
            episode_value, "episode", row_kind, episode_value
        )
        if episode in indexed:
            raise ArtifactValidationError(
                f"duplicate episode ID {episode} in {row_kind}"
            )
        indexed[episode] = row
    return indexed


def _validate_artifact(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    if "episode_results" not in artifact:
        raise ArtifactValidationError("artifact is missing 'episode_results'")
    if "research_evidence" not in artifact:
        raise ArtifactValidationError("artifact is missing 'research_evidence'")
    evidence = artifact["research_evidence"]
    if not isinstance(evidence, dict):
        raise ArtifactValidationError("'research_evidence' must be a JSON object")
    if "episode_diagnostics" not in evidence:
        raise ArtifactValidationError(
            "research_evidence is missing 'episode_diagnostics'"
        )

    results = _index_rows(
        artifact["episode_results"], "episode_results", _REQUIRED_RESULT_FIELDS
    )
    diagnostics = _index_rows(
        evidence["episode_diagnostics"],
        "episode_diagnostics",
        _REQUIRED_DIAGNOSTIC_FIELDS,
    )
    if set(results) != set(diagnostics):
        only_results = sorted(set(results) - set(diagnostics))
        only_diagnostics = sorted(set(diagnostics) - set(results))
        raise ArtifactValidationError(
            "episode IDs do not match between episode_results and "
            f"episode_diagnostics (results_only={only_results}, "
            f"diagnostics_only={only_diagnostics})"
        )
    if not results:
        raise ArtifactValidationError("the evaluation panel contains no episodes")

    if "episodes" not in artifact:
        raise ArtifactValidationError("artifact is missing 'episodes'")
    declared_episodes = _nonnegative_integer(
        artifact["episodes"], "episodes", "artifact", "artifact"
    )
    if declared_episodes != len(results):
        raise ArtifactValidationError(
            f"artifact episodes={declared_episodes} does not match "
            f"the {len(results)} episode rows"
        )

    joined: list[dict[str, Any]] = []
    for episode in sorted(results):
        result = results[episode]
        diagnostic = diagnostics[episode]
        success = result["success"]
        if not isinstance(success, bool):
            raise ArtifactValidationError(
                f"episode_results episode {episode} field 'success' must be boolean"
            )

        radius = _number(
            diagnostic["target_radius_cm"],
            "target_radius_cm",
            "episode_diagnostics",
            episode,
        )
        if not 6.0 <= radius <= 20.0:
            raise ArtifactValidationError(
                f"episode_diagnostics episode {episode} target radius {radius} "
                "is outside the inclusive [6.0, 20.0] cm range"
            )
        angle = _number(
            diagnostic["target_angle_degrees"],
            "target_angle_degrees",
            "episode_diagnostics",
            episode,
        )
        if not -180.0 <= angle < 180.0:
            raise ArtifactValidationError(
                f"episode_diagnostics episode {episode} target angle {angle} "
                "is outside the half-open [-180.0, 180.0) degree range"
            )

        first_reach = diagnostic["first_reach_step"]
        if first_reach is not None:
            first_reach = _nonnegative_integer(
                first_reach,
                "first_reach_step",
                "episode_diagnostics",
                episode,
            )
        max_held = _nonnegative_integer(
            diagnostic["max_held_steps"],
            "max_held_steps",
            "episode_diagnostics",
            episode,
        )
        interruptions = _nonnegative_integer(
            diagnostic["hold_interruptions"],
            "hold_interruptions",
            "episode_diagnostics",
            episode,
        )
        reached = first_reach is not None
        complete_hold = max_held >= COMPLETE_HOLD_STEPS
        if reached != (max_held > 0):
            raise ArtifactValidationError(
                f"episode {episode} has inconsistent reach fields: "
                "first_reach_step and max_held_steps disagree"
            )
        if not reached and interruptions:
            raise ArtifactValidationError(
                f"episode {episode} reports hold interruptions before any reach"
            )
        if success != complete_hold:
            raise ArtifactValidationError(
                f"episode {episode} success={success} is inconsistent with "
                f"max_held_steps={max_held} and the {COMPLETE_HOLD_STEPS}-step "
                "complete-hold rule"
            )
        joined.append(
            {
                "episode": episode,
                "success": success,
                "target_radius_cm": radius,
                "target_angle_degrees": angle,
                "first_reach_step": first_reach,
                "max_held_steps": max_held,
                "hold_interruptions": interruptions,
                "reached": reached,
                "complete_hold": complete_hold,
            }
        )
    return joined


def _coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    radii = [row["target_radius_cm"] for row in rows]
    angles = [row["target_angle_degrees"] for row in rows]
    return {
        "radius_min_cm": min(radii),
        "radius_max_cm": max(radii),
        "radius_count": len(radii),
        "angle_min_degrees": min(angles),
        "angle_max_degrees": max(angles),
        "angle_count": len(angles),
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ArtifactValidationError("a radius band or angle sector is empty")
    episode_count = len(rows)
    successes = sum(row["success"] for row in rows)
    reached = [row for row in rows if row["reached"]]
    failures = [row for row in rows if not row["success"]]
    reached_first_steps = [
        row["first_reach_step"] for row in reached if row["first_reach_step"] is not None
    ]
    interruptions = [
        row for row in rows if row["hold_interruptions"] > 0
    ]
    return {
        "episode_count": episode_count,
        "successes": successes,
        "success_percent": 100.0 * successes / episode_count,
        "reach_count": len(reached),
        "reach_percent": 100.0 * len(reached) / episode_count,
        "mean_first_reach_step": (
            sum(reached_first_steps) / len(reached_first_steps)
            if reached_first_steps
            else None
        ),
        "mean_max_held_steps": sum(
            row["max_held_steps"] for row in rows
        ) / episode_count,
        "maximum_max_held_steps": max(row["max_held_steps"] for row in rows),
        "interruption_episode_count": len(interruptions),
        "total_interruptions": sum(
            row["hold_interruptions"] for row in rows
        ),
        "failures_before_any_reach": sum(
            not row["reached"] for row in failures
        ),
        "failures_after_reach_without_complete_hold": sum(
            row["reached"] and not row["complete_hold"] for row in failures
        ),
    }


def _stratum_report(
    name: str, rows: list[dict[str, Any]], boundary: str
) -> dict[str, Any]:
    if not rows:
        raise ArtifactValidationError(f"empty stratum {name!r}")
    report = {"name": name, "boundary": boundary, "coverage": _coverage(rows)}
    report.update(_summary(rows))
    return report


def _radius_band_rows(
    rows: list[dict[str, Any]], lower: float, upper: float, include_upper: bool
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if lower <= row["target_radius_cm"]
        and (
            row["target_radius_cm"] <= upper
            if include_upper
            else row["target_radius_cm"] < upper
        )
    ]


def _angle_sector_rows(
    rows: list[dict[str, Any]], lower: float, upper: float
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if lower <= row["target_angle_degrees"] < upper
    ]


def analyze_evaluation_stratification(
    input_path: str | Path, output_path: str | Path
) -> dict[str, Any]:
    """Validate, summarize, and write one evaluation artifact analysis."""
    artifact = _load_json(input_path)
    rows = _validate_artifact(artifact)

    radius_specs = (
        ("inner", 6.0, 14.0, False, "6.0 <= target_radius_cm < 14.0"),
        ("outer", 14.0, 20.0, True, "14.0 <= target_radius_cm <= 20.0"),
    )
    radius_bands = [
        _stratum_report(
            name,
            _radius_band_rows(rows, lower, upper, include_upper),
            boundary,
        )
        for name, lower, upper, include_upper, boundary in radius_specs
    ]

    sector_specs = (
        ("[-180,-90)", -180.0, -90.0),
        ("[-90,0)", -90.0, 0.0),
        ("[0,90)", 0.0, 90.0),
        ("[90,180)", 90.0, 180.0),
    )
    angle_sectors = [
        _stratum_report(
            name,
            _angle_sector_rows(rows, lower, upper),
            f"{lower:g} <= target_angle_degrees < {upper:g}",
        )
        for name, lower, upper in sector_specs
    ]

    successes = sum(row["success"] for row in rows)
    report = {
        "analysis_version": 1,
        "complete_hold_steps": COMPLETE_HOLD_STEPS,
        "total_episodes": len(rows),
        "total_successes": successes,
        "success_percent": 100.0 * successes / len(rows),
        "coverage": _coverage(rows),
        "radius_band_convention": (
            "inner: 6.0 <= target_radius_cm < 14.0; "
            "outer: 14.0 <= target_radius_cm <= 20.0"
        ),
        "angle_sector_convention": (
            "[-180,-90), [-90,0), [0,90), [90,180); "
            "-180 is included and 180 is excluded"
        ),
        "radius_bands": radius_bands,
        "angle_sectors": angle_sectors,
    }
    with Path(output_path).open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Analyze radius- and angle-stratified evaluation diagnostics."
    )
    parser.add_argument("input_json", type=Path)
    parser.add_argument("output_json", type=Path)
    args = parser.parse_args(argv)
    analyze_evaluation_stratification(args.input_json, args.output_json)


if __name__ == "__main__":
    main()
