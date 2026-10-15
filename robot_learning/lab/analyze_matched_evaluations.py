"""Diagnostic analysis for two matched research-evaluation artifacts.

This module summarizes reach, hold, success, and paired-status differences
across target geometry.  It is diagnostic analysis only: it is not an official
assessment and the stratified summaries do not establish a causal mechanism.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any


_HOLD_STEPS = 100
_RADIUS_BINS = (
    ("[6,10) cm", 6.0, 10.0, False),
    ("[10,14) cm", 10.0, 14.0, False),
    ("[14,18) cm", 14.0, 18.0, False),
    ("[18,20] cm", 18.0, 20.0, True),
)
_ANGLE_SECTORS = (
    ("[-180,-90) degrees", -180.0, -90.0, False),
    ("[-90,0) degrees", -90.0, 0.0, False),
    ("[0,90) degrees", 0.0, 90.0, False),
    ("[90,180] degrees", 90.0, 180.0, True),
)
_TRANSITION_KEYS = (
    "reference_success_to_candidate_success",
    "reference_success_to_candidate_failure",
    "reference_failure_to_candidate_success",
    "reference_failure_to_candidate_failure",
)


class AnalysisError(ValueError):
    """An input artifact does not satisfy the evaluation artifact contract."""


def _mapping(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AnalysisError(f"{location} must be a JSON object")
    return value


def _sequence(value: Any, location: str) -> list[Any]:
    if not isinstance(value, list):
        raise AnalysisError(f"{location} must be a JSON array")
    return value


def _string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise AnalysisError(f"{location} must be a non-empty string")
    return value


def _integer(value: Any, location: str, *, nonnegative: bool = False) -> int:
    if type(value) is not int:
        raise AnalysisError(f"{location} must be an integer")
    if nonnegative and value < 0:
        raise AnalysisError(f"{location} must be non-negative")
    return value


def _number(value: Any, location: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AnalysisError(f"{location} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise AnalysisError(f"{location} must be finite")
    return converted


def _boolean(value: Any, location: str) -> bool:
    if type(value) is not bool:
        raise AnalysisError(f"{location} must be a boolean")
    return value


def _read_json(path: Path, role: str) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AnalysisError(f"cannot read {role} input {path}: {exc}") from exc
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AnalysisError(f"{role} input {path} is not valid JSON: {exc}") from exc
    return _mapping(value, f"{role} input")


def _parse_evaluation(payload: dict[str, Any], role: str) -> dict[str, Any]:
    model = _string(payload.get("model"), f"{role}.model")
    seed = _integer(payload.get("seed"), f"{role}.seed", nonnegative=True)
    episodes = _integer(payload.get("episodes"), f"{role}.episodes")
    if episodes < 1:
        raise AnalysisError(f"{role}.episodes must be positive")

    result_rows = _sequence(payload.get("episode_results"), f"{role}.episode_results")
    evidence = _mapping(
        payload.get("research_evidence"), f"{role}.research_evidence"
    )
    diagnostic_rows = _sequence(
        evidence.get("episode_diagnostics"),
        f"{role}.research_evidence.episode_diagnostics",
    )
    if len(result_rows) != episodes or len(diagnostic_rows) != episodes:
        raise AnalysisError(
            f"{role} episode count metadata ({episodes}) does not match "
            f"episode_results ({len(result_rows)}) and diagnostics "
            f"({len(diagnostic_rows)})"
        )

    results_by_seed: dict[int, dict[str, Any]] = {}
    for index, raw_row in enumerate(result_rows):
        row = _mapping(raw_row, f"{role}.episode_results[{index}]")
        episode = _integer(row.get("episode"), f"{role}.episode_results[{index}].episode")
        episode_seed = _integer(
            row.get("episode_seed"),
            f"{role}.episode_results[{index}].episode_seed",
            nonnegative=True,
        )
        expected_episode = episode_seed - seed
        if episode != expected_episode:
            raise AnalysisError(
                f"{role}.episode_results[{index}].episode must equal "
                f"episode_seed - seed ({expected_episode})"
            )
        success = _boolean(
            row.get("success"), f"{role}.episode_results[{index}].success"
        )
        if episode_seed in results_by_seed:
            raise AnalysisError(f"{role} has duplicate episode_seed {episode_seed}")
        results_by_seed[episode_seed] = {
            "episode": episode,
            "success": success,
        }

    diagnostics_by_seed: dict[int, dict[str, Any]] = {}
    for index, raw_row in enumerate(diagnostic_rows):
        row = _mapping(
            raw_row,
            f"{role}.research_evidence.episode_diagnostics[{index}]",
        )
        episode = _integer(
            row.get("episode"),
            f"{role}.research_evidence.episode_diagnostics[{index}].episode",
        )
        episode_seed = _integer(
            row.get("episode_seed"),
            f"{role}.research_evidence.episode_diagnostics[{index}].episode_seed",
            nonnegative=True,
        )
        expected_episode = episode_seed - seed
        if episode != expected_episode:
            raise AnalysisError(
                f"{role}.research_evidence.episode_diagnostics[{index}].episode "
                f"must equal episode_seed - seed ({expected_episode})"
            )
        radius = _number(
            row.get("target_radius_cm"),
            f"{role}.research_evidence.episode_diagnostics[{index}].target_radius_cm",
        )
        angle = _number(
            row.get("target_angle_degrees"),
            f"{role}.research_evidence.episode_diagnostics[{index}].target_angle_degrees",
        )
        first_reach = row.get("first_reach_step")
        if first_reach is not None:
            first_reach = _integer(
                first_reach,
                f"{role}.research_evidence.episode_diagnostics[{index}].first_reach_step",
                nonnegative=True,
            )
            if first_reach < 1:
                raise AnalysisError(
                    f"{role}.research_evidence.episode_diagnostics[{index}]."
                    "first_reach_step must be at least 1 when non-null"
                )
        max_held = _integer(
            row.get("max_held_steps"),
            f"{role}.research_evidence.episode_diagnostics[{index}].max_held_steps",
            nonnegative=True,
        )
        hold_interruptions = _integer(
            row.get("hold_interruptions"),
            f"{role}.research_evidence.episode_diagnostics[{index}].hold_interruptions",
            nonnegative=True,
        )
        if episode_seed in diagnostics_by_seed:
            raise AnalysisError(f"{role} has duplicate diagnostic episode_seed {episode_seed}")
        diagnostics_by_seed[episode_seed] = {
            "episode": episode,
            "radius": radius,
            "angle": angle,
            "first_reach_step": first_reach,
            "max_held_steps": max_held,
            "hold_interruptions": hold_interruptions,
        }

    if set(results_by_seed) != set(diagnostics_by_seed):
        missing_diagnostics = sorted(set(results_by_seed) - set(diagnostics_by_seed))
        missing_results = sorted(set(diagnostics_by_seed) - set(results_by_seed))
        raise AnalysisError(
            f"{role} episode seed mismatch between episode_results and diagnostics: "
            f"missing_diagnostics={missing_diagnostics}, "
            f"missing_results={missing_results}"
        )

    expected_seeds = set(range(seed, seed + episodes))
    if set(results_by_seed) != expected_seeds:
        raise AnalysisError(
            f"{role} episode seeds do not match the declared consecutive panel "
            f"[{seed}, {seed + episodes})"
        )

    rows: list[dict[str, Any]] = []
    for episode_seed in sorted(results_by_seed):
        result = results_by_seed[episode_seed]
        diagnostic = diagnostics_by_seed[episode_seed]
        if result["episode"] != diagnostic["episode"]:
            raise AnalysisError(
                f"{role} episode identifier mismatch for episode_seed {episode_seed}"
            )
        radius = diagnostic["radius"]
        angle = diagnostic["angle"]
        if not 6.0 <= radius <= 20.0:
            raise AnalysisError(
                f"{role} target_radius_cm for episode_seed {episode_seed} "
                f"is outside the supported [6,20] cm range"
            )
        if not -180.0 <= angle <= 180.0:
            raise AnalysisError(
                f"{role} target_angle_degrees for episode_seed {episode_seed} "
                f"is outside the supported [-180,180] degree range"
            )
        rows.append(
            {
                "episode_seed": episode_seed,
                "success": result["success"],
                "radius": radius,
                "angle": angle,
                "first_reach_step": diagnostic["first_reach_step"],
                "max_held_steps": diagnostic["max_held_steps"],
                "hold_interruptions": diagnostic["hold_interruptions"],
            }
        )

    return {
        "metadata": {"model": model, "seed": seed, "episodes": episodes},
        "rows": rows,
    }


def _metric_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    episodes = len(rows)
    successes = sum(row["success"] for row in rows)
    reached = [row for row in rows if row["first_reach_step"] is not None]
    reached_failures = [
        row for row in reached if not row["success"]
    ]
    first_reach_steps = [row["first_reach_step"] for row in reached]
    return {
        "episodes": episodes,
        "successes": successes,
        "success_percent": 100.0 * successes / episodes if episodes else 0.0,
        "reached_episodes": len(reached),
        "no_reach_failures": sum(
            not row["success"] for row in rows if row["first_reach_step"] is None
        ),
        "reached_but_not_success_failures": len(reached_failures),
        "hold_failures": sum(
            row["max_held_steps"] < _HOLD_STEPS for row in reached_failures
        ),
        "hold_interruptions": sum(row["hold_interruptions"] for row in rows),
        "mean_first_reach_step": (
            sum(first_reach_steps) / len(first_reach_steps)
            if first_reach_steps
            else None
        ),
    }


def _transitions(
    reference_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
) -> dict[str, int]:
    candidate_by_seed = {
        row["episode_seed"]: row for row in candidate_rows
    }
    counts = {key: 0 for key in _TRANSITION_KEYS}
    for reference in reference_rows:
        candidate = candidate_by_seed[reference["episode_seed"]]
        if reference["success"] and candidate["success"]:
            key = "reference_success_to_candidate_success"
        elif reference["success"]:
            key = "reference_success_to_candidate_failure"
        elif candidate["success"]:
            key = "reference_failure_to_candidate_success"
        else:
            key = "reference_failure_to_candidate_failure"
        counts[key] += 1
    return counts


def _in_interval(
    value: float, lower: float, upper: float, upper_inclusive: bool
) -> bool:
    return lower <= value <= upper if upper_inclusive else lower <= value < upper


def _stratified_section(
    reference_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    definitions: tuple[tuple[str, float, float, bool], ...],
    coordinate: str,
    *,
    section_key: str,
) -> list[dict[str, Any]]:
    sections = []
    for label, lower, upper, upper_inclusive in definitions:
        reference_subset = [
            row
            for row in reference_rows
            if _in_interval(row[coordinate], lower, upper, upper_inclusive)
        ]
        candidate_subset = [
            row
            for row in candidate_rows
            if _in_interval(row[coordinate], lower, upper, upper_inclusive)
        ]
        sections.append(
            {
                section_key: label,
                "lower": lower,
                "upper": upper,
                "upper_inclusive": upper_inclusive,
                "reference": _metric_summary(reference_subset),
                "candidate": _metric_summary(candidate_subset),
                "paired_transitions": _transitions(
                    reference_subset, candidate_subset
                ),
            }
        )
    return sections


def analyze(reference: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Validate and analyze two completed, matched research evaluations."""
    parsed_reference = _parse_evaluation(reference, "reference")
    parsed_candidate = _parse_evaluation(candidate, "candidate")
    reference_rows = parsed_reference["rows"]
    candidate_rows = parsed_candidate["rows"]

    reference_by_seed = {
        row["episode_seed"]: row for row in reference_rows
    }
    candidate_by_seed = {
        row["episode_seed"]: row for row in candidate_rows
    }
    if set(reference_by_seed) != set(candidate_by_seed):
        raise AnalysisError(
            "reference and candidate episode seeds do not match: "
            f"reference_only={sorted(set(reference_by_seed) - set(candidate_by_seed))}, "
            f"candidate_only={sorted(set(candidate_by_seed) - set(reference_by_seed))}"
        )
    for episode_seed in sorted(reference_by_seed):
        reference_row = reference_by_seed[episode_seed]
        candidate_row = candidate_by_seed[episode_seed]
        if (
            reference_row["radius"] != candidate_row["radius"]
            or reference_row["angle"] != candidate_row["angle"]
        ):
            raise AnalysisError(
                "reference and candidate target geometry does not match for "
                f"episode_seed {episode_seed}"
            )

    return {
        "schema_version": 1,
        "analysis_type": "matched_evaluation_diagnostics",
        "diagnostic_notice": (
            "Diagnostic comparison only; not an official assessment or causal proof."
        ),
        "inputs": {
            "reference": parsed_reference["metadata"],
            "candidate": parsed_candidate["metadata"],
        },
        "overall": {
            "reference": _metric_summary(reference_rows),
            "candidate": _metric_summary(candidate_rows),
            "paired_transitions": _transitions(reference_rows, candidate_rows),
        },
        "radius_bins": _stratified_section(
            reference_rows,
            candidate_rows,
            _RADIUS_BINS,
            "radius",
            section_key="bin",
        ),
        "angle_sectors": _stratified_section(
            reference_rows,
            candidate_rows,
            _ANGLE_SECTORS,
            "angle",
            section_key="sector",
        ),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze two matched research-evaluation JSON artifacts."
    )
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def _same_underlying_file(first: Path, second: Path) -> bool:
    """Return whether two existing paths identify the same file."""
    try:
        return os.path.samefile(first, second)
    except FileNotFoundError:
        # This is the normal case when the output is a new path.  The fallback
        # still catches an equivalent spelling or symlink to an input.
        return first.resolve(strict=False) == second.resolve(strict=False)
    except OSError as exc:
        raise AnalysisError(
            f"cannot verify whether output {first} aliases input {second}: {exc}"
        ) from exc


def main(argv: list[str] | None = None) -> int:
    """Run the command-line analysis without modifying either input artifact."""
    args = _build_parser().parse_args(argv)
    try:
        if _same_underlying_file(args.reference, args.candidate):
            raise AnalysisError("reference and candidate must be different files")
        for input_path in (args.reference, args.candidate):
            if _same_underlying_file(args.output, input_path):
                raise AnalysisError(
                    f"output must not overwrite input artifact {input_path}"
                )
        result = analyze(
            _read_json(args.reference, "reference"),
            _read_json(args.candidate, "candidate"),
        )
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (AnalysisError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
