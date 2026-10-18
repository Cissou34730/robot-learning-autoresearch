"""Paired analysis of completed non-official reach-and-hold evaluations.

The report summarizes artifact-recorded, post-control-block observations. In
particular, a null ``first_reach_step`` means that no sampled in-tolerance
observation was recorded; it does not establish continuous-time non-reach.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPORT_SCHEMA_VERSION = 1
GEOMETRY_ABS_TOLERANCE = 1e-9
RADIUS_MIN_CM = 6.0
RADIUS_SPLIT_CM = 14.0
RADIUS_MAX_CM = 20.0

RADIUS_GROUPS = (
    ("radius_cm_lt_14", "<14 cm"),
    ("radius_cm_gte_14", ">=14 cm"),
)
ANGLE_GROUPS = (
    ("angle_quadrant_i", "I"),
    ("angle_quadrant_ii", "II"),
    ("angle_quadrant_iii", "III"),
    ("angle_quadrant_iv", "IV"),
)


class AnalysisError(ValueError):
    """Raised when an input artifact cannot support a valid paired report."""


@dataclass(frozen=True)
class Episode:
    episode_id: int
    episode_seed: int
    success: bool
    steps: int
    target_radius_cm: float
    target_angle_degrees: float
    radius_group: str
    angle_group: str
    first_reach_step: int | None
    max_held_steps: int
    in_tolerance_steps: int
    hold_interruptions: int


@dataclass(frozen=True)
class Panel:
    role: str
    path: Path
    label: str
    model_identifier: str
    schema_version: int
    evaluation_semantics: str
    semantics_source_operation: str
    seed: int
    declared_episodes: int
    episodes: dict[int, Episode]


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AnalysisError(f"JSON object contains duplicate key {key!r}")
        result[key] = value
    return result


def _reject_nonstandard_number(token: str) -> None:
    raise AnalysisError(f"JSON contains non-standard numeric constant {token}")


def _read_json(path: Path, role: str) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as stream:
            value = json.load(
                stream,
                object_pairs_hook=_reject_duplicate_keys,
                parse_constant=_reject_nonstandard_number,
            )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AnalysisError(f"cannot read {role} JSON artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AnalysisError(f"{role} artifact root must be a JSON object")
    return value


def _required(mapping: dict[str, Any], key: str, context: str) -> Any:
    if key not in mapping:
        raise AnalysisError(f"{context} is missing required field {key!r}")
    return mapping[key]


def _integer(value: Any, context: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AnalysisError(f"{context} must be an integer")
    if minimum is not None and value < minimum:
        raise AnalysisError(f"{context} must be at least {minimum}")
    return value


def _number(value: Any, context: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AnalysisError(f"{context} must be a number")
    try:
        converted = float(value)
    except OverflowError as exc:
        raise AnalysisError(f"{context} is outside the supported numeric range") from exc
    if not math.isfinite(converted):
        raise AnalysisError(f"{context} must be finite")
    if minimum is not None and converted < minimum:
        raise AnalysisError(f"{context} must be at least {minimum}")
    return converted


def _record_list(value: Any, context: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise AnalysisError(f"{context} must be a list")
    records: list[dict[str, Any]] = []
    for index, record in enumerate(value):
        if not isinstance(record, dict):
            raise AnalysisError(f"{context}[{index}] must be an object")
        records.append(record)
    return records


def _wrapped_angle(angle_degrees: float) -> float:
    if (
        angle_degrees < -180.0 - GEOMETRY_ABS_TOLERANCE
        or angle_degrees > 180.0 + GEOMETRY_ABS_TOLERANCE
    ):
        raise AnalysisError(
            f"target angle {angle_degrees} is outside the recorded [-180, 180] range"
        )
    bounded = min(180.0, max(-180.0, angle_degrees))
    return (bounded + 180.0) % 360.0 - 180.0


def _snap_to_boundary(value: float, boundaries: tuple[float, ...]) -> float:
    for boundary in boundaries:
        if abs(value - boundary) <= GEOMETRY_ABS_TOLERANCE:
            return boundary
    return value


def _radius_group(radius_cm: float) -> str:
    if (
        radius_cm < RADIUS_MIN_CM - GEOMETRY_ABS_TOLERANCE
        or radius_cm > RADIUS_MAX_CM + GEOMETRY_ABS_TOLERANCE
    ):
        raise AnalysisError(
            f"target radius {radius_cm} cm is outside the task's 6–20 cm range"
        )
    bounded = min(RADIUS_MAX_CM, max(RADIUS_MIN_CM, radius_cm))
    assigned = _snap_to_boundary(
        bounded, (RADIUS_MIN_CM, RADIUS_SPLIT_CM, RADIUS_MAX_CM)
    )
    if assigned < RADIUS_SPLIT_CM:
        return "radius_cm_lt_14"
    return "radius_cm_gte_14"


def _angle_group(angle_degrees: float) -> str:
    wrapped = _wrapped_angle(angle_degrees)
    assigned = _snap_to_boundary(wrapped, (-180.0, -90.0, 0.0, 90.0))
    if 0.0 <= assigned < 90.0:
        return "angle_quadrant_i"
    if 90.0 <= assigned < 180.0:
        return "angle_quadrant_ii"
    if -180.0 <= assigned < -90.0:
        return "angle_quadrant_iii"
    return "angle_quadrant_iv"


def _index_records(
    records: list[dict[str, Any]],
    context: str,
    *,
    expected_count: int,
    panel_seed: int,
) -> dict[int, dict[str, Any]]:
    indexed: dict[int, dict[str, Any]] = {}
    for index, record in enumerate(records):
        record_context = f"{context}[{index}]"
        episode_id = _integer(
            _required(record, "episode", record_context),
            f"{record_context}.episode",
            minimum=0,
        )
        if episode_id in indexed:
            raise AnalysisError(
                f"{context} contains duplicate episode ID {episode_id}"
            )
        episode_seed = _integer(
            _required(record, "episode_seed", record_context),
            f"{record_context}.episode_seed",
            minimum=0,
        )
        if episode_seed != panel_seed + episode_id:
            raise AnalysisError(
                f"{record_context}.episode_seed is {episode_seed}, expected "
                f"{panel_seed + episode_id} from the panel seed and episode ID"
            )
        indexed[episode_id] = record

    expected_ids = set(range(expected_count))
    actual_ids = set(indexed)
    if actual_ids != expected_ids:
        missing = sorted(expected_ids - actual_ids)
        unexpected = sorted(actual_ids - expected_ids)
        raise AnalysisError(
            f"{context} does not contain the complete episode ID range "
            f"0..{expected_count - 1}; missing={missing}, unexpected={unexpected}"
        )
    return indexed


def _load_panel(
    path: Path,
    role: str,
    *,
    evaluation_semantics: str,
    semantics_source_operation: str,
) -> Panel:
    artifact = _read_json(path, role)
    context = f"{role} artifact"

    if _required(artifact, "official_benchmark", context) is not False:
        raise AnalysisError(f"{context} must be a non-official research evaluation")

    schema_version = _integer(
        _required(artifact, "schema_version", context),
        f"{context}.schema_version",
        minimum=1,
    )
    model_identifier = _required(artifact, "model", context)
    if not isinstance(model_identifier, str) or not model_identifier.strip():
        raise AnalysisError(f"{context}.model must be a non-empty string")
    label = artifact.get("label", role)
    if not isinstance(label, str) or not label.strip():
        raise AnalysisError(f"{context}.label must be a non-empty string when present")

    panel_seed = _integer(
        _required(artifact, "seed", context), f"{context}.seed", minimum=0
    )
    declared_episodes = _integer(
        _required(artifact, "episodes", context),
        f"{context}.episodes",
        minimum=1,
    )

    outcome_records = _record_list(
        _required(artifact, "episode_results", context),
        f"{context}.episode_results",
    )
    if len(outcome_records) != declared_episodes:
        raise AnalysisError(
            f"{context}.episode_results has {len(outcome_records)} rows, "
            f"but episodes declares {declared_episodes}"
        )
    outcomes = _index_records(
        outcome_records,
        f"{context}.episode_results",
        expected_count=declared_episodes,
        panel_seed=panel_seed,
    )

    research_evidence = _required(artifact, "research_evidence", context)
    if not isinstance(research_evidence, dict):
        raise AnalysisError(f"{context}.research_evidence must be an object")
    units = _required(research_evidence, "units", f"{context}.research_evidence")
    if not isinstance(units, dict):
        raise AnalysisError(f"{context}.research_evidence.units must be an object")
    if units.get("distance") != "cm" or units.get("time") != "control_steps":
        raise AnalysisError(
            f"{context}.research_evidence.units must specify distance='cm' "
            "and time='control_steps'"
        )
    diagnostic_records = _record_list(
        _required(
            research_evidence,
            "episode_diagnostics",
            f"{context}.research_evidence",
        ),
        f"{context}.research_evidence.episode_diagnostics",
    )
    if len(diagnostic_records) != declared_episodes:
        raise AnalysisError(
            f"{context}.research_evidence.episode_diagnostics has "
            f"{len(diagnostic_records)} rows, but episodes declares "
            f"{declared_episodes}"
        )
    diagnostics = _index_records(
        diagnostic_records,
        f"{context}.research_evidence.episode_diagnostics",
        expected_count=declared_episodes,
        panel_seed=panel_seed,
    )

    episodes: dict[int, Episode] = {}
    for episode_id in range(declared_episodes):
        outcome = outcomes[episode_id]
        diagnostic = diagnostics[episode_id]
        episode_context = f"{context} episode {episode_id}"
        outcome_seed = _integer(
            _required(outcome, "episode_seed", episode_context),
            f"{episode_context}.episode_seed",
            minimum=0,
        )
        diagnostic_seed = _integer(
            _required(diagnostic, "episode_seed", episode_context),
            f"{episode_context}.diagnostic episode_seed",
            minimum=0,
        )
        if outcome_seed != diagnostic_seed:
            raise AnalysisError(
                f"{episode_context} outcome and diagnostic seeds differ"
            )

        success = _required(outcome, "success", episode_context)
        if not isinstance(success, bool):
            raise AnalysisError(f"{episode_context}.success must be a boolean")
        _number(
            _required(outcome, "reward_total", episode_context),
            f"{episode_context}.reward_total",
        )
        steps = _integer(
            _required(outcome, "steps", episode_context),
            f"{episode_context}.steps",
            minimum=1,
        )
        terminated = _required(outcome, "terminated", episode_context)
        truncated = _required(outcome, "truncated", episode_context)
        if not isinstance(terminated, bool):
            raise AnalysisError(f"{episode_context}.terminated must be a boolean")
        if not isinstance(truncated, bool):
            raise AnalysisError(f"{episode_context}.truncated must be a boolean")
        if not (terminated or truncated):
            raise AnalysisError(
                f"{episode_context} is incomplete: neither terminated nor truncated"
            )
        if success != terminated:
            raise AnalysisError(
                f"{episode_context}.success disagrees with terminated; "
                "the research evaluator records success from is_success, "
                "which matches environment termination"
            )

        radius_cm = _number(
            _required(diagnostic, "target_radius_cm", episode_context),
            f"{episode_context}.target_radius_cm",
            minimum=0.0,
        )
        angle_degrees = _number(
            _required(diagnostic, "target_angle_degrees", episode_context),
            f"{episode_context}.target_angle_degrees",
        )
        _number(
            _required(diagnostic, "min_distance_cm", episode_context),
            f"{episode_context}.min_distance_cm",
            minimum=0.0,
        )
        _number(
            _required(diagnostic, "final_distance_cm", episode_context),
            f"{episode_context}.final_distance_cm",
            minimum=0.0,
        )
        first_reach_value = _required(
            diagnostic, "first_reach_step", episode_context
        )
        first_reach_step = (
            None
            if first_reach_value is None
            else _integer(
                first_reach_value,
                f"{episode_context}.first_reach_step",
                minimum=1,
            )
        )
        max_held_steps = _integer(
            _required(diagnostic, "max_held_steps", episode_context),
            f"{episode_context}.max_held_steps",
            minimum=0,
        )
        in_tolerance_steps = _integer(
            _required(diagnostic, "in_tolerance_steps", episode_context),
            f"{episode_context}.in_tolerance_steps",
            minimum=0,
        )
        hold_interruptions = _integer(
            _required(diagnostic, "hold_interruptions", episode_context),
            f"{episode_context}.hold_interruptions",
            minimum=0,
        )
        if first_reach_step is not None and first_reach_step > steps:
            raise AnalysisError(
                f"{episode_context}.first_reach_step exceeds episode steps"
            )
        if in_tolerance_steps > steps or max_held_steps > in_tolerance_steps:
            raise AnalysisError(
                f"{episode_context} has inconsistent in-tolerance step counts"
            )
        if (first_reach_step is None) != (in_tolerance_steps == 0):
            raise AnalysisError(
                f"{episode_context}.first_reach_step and in_tolerance_steps disagree"
            )
        if in_tolerance_steps == 0 and max_held_steps != 0:
            raise AnalysisError(
                f"{episode_context}.max_held_steps is nonzero without an "
                "in-tolerance observation"
            )
        if in_tolerance_steps > 0 and max_held_steps == 0:
            raise AnalysisError(
                f"{episode_context}.max_held_steps is zero despite an "
                "in-tolerance observation"
            )
        if hold_interruptions > in_tolerance_steps:
            raise AnalysisError(
                f"{episode_context}.hold_interruptions exceeds in-tolerance steps"
            )
        if success and first_reach_step is None:
            raise AnalysisError(
                f"{episode_context} is successful but has no sampled "
                "in-tolerance observation"
            )

        episodes[episode_id] = Episode(
            episode_id=episode_id,
            episode_seed=outcome_seed,
            success=success,
            steps=steps,
            target_radius_cm=radius_cm,
            target_angle_degrees=angle_degrees,
            radius_group=_radius_group(radius_cm),
            angle_group=_angle_group(angle_degrees),
            first_reach_step=first_reach_step,
            max_held_steps=max_held_steps,
            in_tolerance_steps=in_tolerance_steps,
            hold_interruptions=hold_interruptions,
        )

    return Panel(
        role=role,
        path=path,
        label=label,
        model_identifier=model_identifier,
        schema_version=schema_version,
        evaluation_semantics=evaluation_semantics,
        semantics_source_operation=semantics_source_operation,
        seed=panel_seed,
        declared_episodes=declared_episodes,
        episodes=episodes,
    )


def _circular_angle_difference(first: float, second: float) -> float:
    return abs((first - second + 180.0) % 360.0 - 180.0)


def _validate_pair(candidate: Panel, reference: Panel) -> None:
    if candidate.schema_version != reference.schema_version:
        raise AnalysisError("candidate and reference schema_version values differ")
    if candidate.evaluation_semantics != reference.evaluation_semantics:
        raise AnalysisError("candidate and reference evaluation-semantics IDs differ")
    if candidate.semantics_source_operation != reference.semantics_source_operation:
        raise AnalysisError("candidate and reference semantics source operations differ")
    if candidate.seed != reference.seed:
        raise AnalysisError("candidate and reference panel seeds differ")
    if candidate.declared_episodes != reference.declared_episodes:
        raise AnalysisError("candidate and reference episode counts differ")
    if set(candidate.episodes) != set(reference.episodes):
        raise AnalysisError("candidate and reference episode IDs differ")

    for episode_id in sorted(candidate.episodes):
        candidate_episode = candidate.episodes[episode_id]
        reference_episode = reference.episodes[episode_id]
        if candidate_episode.episode_seed != reference_episode.episode_seed:
            raise AnalysisError(
                f"episode {episode_id} candidate and reference seeds differ"
            )
        if not math.isclose(
            candidate_episode.target_radius_cm,
            reference_episode.target_radius_cm,
            rel_tol=0.0,
            abs_tol=GEOMETRY_ABS_TOLERANCE,
        ):
            raise AnalysisError(
                f"episode {episode_id} target radii differ by more than "
                f"{GEOMETRY_ABS_TOLERANCE} cm"
            )
        if (
            _circular_angle_difference(
                candidate_episode.target_angle_degrees,
                reference_episode.target_angle_degrees,
            )
            > GEOMETRY_ABS_TOLERANCE
        ):
            raise AnalysisError(
                f"episode {episode_id} target angles differ by more than "
                f"{GEOMETRY_ABS_TOLERANCE} degrees"
            )
        if candidate_episode.radius_group != reference_episode.radius_group:
            raise AnalysisError(
                f"episode {episode_id} candidate and reference radius strata differ"
            )
        if candidate_episode.angle_group != reference_episode.angle_group:
            raise AnalysisError(
                f"episode {episode_id} candidate and reference angle strata differ"
            )


def _summarize_episodes(episodes: list[Episode]) -> dict[str, Any]:
    reached_steps = [
        episode.first_reach_step
        for episode in episodes
        if episode.first_reach_step is not None
    ]
    return {
        "n": len(episodes),
        "successes": sum(episode.success for episode in episodes),
        "observed_success_percent": (
            100.0 * sum(episode.success for episode in episodes) / len(episodes)
            if episodes
            else None
        ),
        "episodes_without_sampled_in_tolerance_observation": sum(
            episode.first_reach_step is None for episode in episodes
        ),
        "failures_with_sampled_in_tolerance_observation": sum(
            (not episode.success) and episode.first_reach_step is not None
            for episode in episodes
        ),
        "mean_first_reach_step_among_reached": (
            statistics.fmean(reached_steps) if reached_steps else None
        ),
        "mean_max_held_steps": (
            statistics.fmean(episode.max_held_steps for episode in episodes)
            if episodes
            else None
        ),
        "episodes_with_any_hold_interruption": sum(
            episode.hold_interruptions > 0 for episode in episodes
        ),
        "total_interruptions": sum(
            episode.hold_interruptions for episode in episodes
        ),
    }


def _paired_counts(
    episode_ids: list[int], candidate: Panel, reference: Panel
) -> dict[str, int]:
    candidate_wins = 0
    reference_wins = 0
    ties = 0
    for episode_id in episode_ids:
        candidate_success = candidate.episodes[episode_id].success
        reference_success = reference.episodes[episode_id].success
        if candidate_success and not reference_success:
            candidate_wins += 1
        elif reference_success and not candidate_success:
            reference_wins += 1
        else:
            ties += 1
    return {
        "n": len(episode_ids),
        "candidate_wins": candidate_wins,
        "reference_wins": reference_wins,
        "ties": ties,
        "discordant_episodes": candidate_wins + reference_wins,
        "candidate_minus_reference_net_wins": candidate_wins - reference_wins,
    }


def _panel_metrics(panel: Panel) -> dict[str, Any]:
    all_episodes = list(panel.episodes.values())
    radius: dict[str, Any] = {}
    for group_name, _description in RADIUS_GROUPS:
        selected = [
            episode
            for episode in all_episodes
            if episode.radius_group == group_name
        ]
        radius[group_name] = _summarize_episodes(selected)

    angle: dict[str, Any] = {}
    for group_name, _quadrant in ANGLE_GROUPS:
        selected = [
            episode
            for episode in all_episodes
            if episode.angle_group == group_name
        ]
        angle[group_name] = _summarize_episodes(selected)
    return {
        "whole_panel": _summarize_episodes(all_episodes),
        "target_radius": radius,
        "target_angle_quadrant": angle,
    }


def _paired_metrics(candidate: Panel, reference: Panel) -> dict[str, Any]:
    episode_ids = sorted(candidate.episodes)
    radius: dict[str, Any] = {}
    for group_name, _description in RADIUS_GROUPS:
        selected_ids = [
            episode_id
            for episode_id in episode_ids
            if candidate.episodes[episode_id].radius_group == group_name
        ]
        radius[group_name] = _paired_counts(selected_ids, candidate, reference)

    angle: dict[str, Any] = {}
    for group_name, _quadrant in ANGLE_GROUPS:
        selected_ids = [
            episode_id
            for episode_id in episode_ids
            if candidate.episodes[episode_id].angle_group == group_name
        ]
        angle[group_name] = _paired_counts(selected_ids, candidate, reference)
    return {
        "whole_panel": _paired_counts(episode_ids, candidate, reference),
        "target_radius": radius,
        "target_angle_quadrant": angle,
    }


def _panel_provenance(panel: Panel) -> dict[str, Any]:
    return {
        "role": panel.role,
        "label": panel.label,
        "model_identifier": panel.model_identifier,
        "input_artifact": str(panel.path),
        "official_benchmark": False,
        "schema_version": panel.schema_version,
        "evaluation_semantics": panel.evaluation_semantics,
        "semantics_source_operation": panel.semantics_source_operation,
        "seed": panel.seed,
        "episodes": panel.declared_episodes,
        "episode_ids": sorted(panel.episodes),
    }


def build_report(candidate: Panel, reference: Panel) -> dict[str, Any]:
    _validate_pair(candidate, reference)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "provenance": {
            "status": "non_official_research_panel",
            "official_performance_claim": False,
            "candidate": _panel_provenance(candidate),
            "reference": _panel_provenance(reference),
            "evaluation_compatibility": {
                "schema_version_match": True,
                "caller_supplied_evaluation_semantics_identifiers_match": True,
                "basis": (
                    "matching schema_version and equal caller-supplied "
                    "evaluation-semantics identifiers"
                ),
            },
            "evaluation_semantics_provenance": {
                "identifier": candidate.evaluation_semantics,
                "source_operation": candidate.semantics_source_operation,
                "source": "caller-supplied operation metadata",
                "read_from_input_artifacts": False,
                "source_operation_binding_verified_by_module": False,
            },
            "strata_definitions": {
                "target_radius_cm": {
                    "radius_cm_lt_14": "[6, 14) cm",
                    "radius_cm_gte_14": "[14, 20] cm",
                },
                "target_angle_quadrant": {
                    "angle_quadrant_i": "[0, 90) degrees",
                    "angle_quadrant_ii": "[90, 180) degrees",
                    "angle_quadrant_iii": "[-180, -90) degrees",
                    "angle_quadrant_iv": "[-90, 0) degrees",
                },
                "angle_convention": "wrapped [-180, 180)",
            },
            "geometry_match_tolerance": {
                "target_radius_cm_absolute": GEOMETRY_ABS_TOLERANCE,
                "target_angle_degrees_absolute": GEOMETRY_ABS_TOLERANCE,
                "angular_comparison": "circular distance on wrapped [-180, 180)",
                "stratum_boundary_rule": (
                    "values within the geometry tolerance of a boundary are "
                    "assigned to that boundary; lower-inclusive strata apply"
                ),
            },
            "strata_interpretation": (
                "Observed development strata only; they do not define official "
                "task probability masses."
            ),
            "reach_interpretation": (
                "first_reach_step is the first post-control-block sample "
                "reporting held_steps > 0. A null value means no sampled "
                "in-tolerance observation, not proven physical non-reach."
            ),
            "hold_interpretation": (
                "Hold and interruption values are reported from the artifacts; "
                "they do not independently establish protected hold-check fidelity."
            ),
        },
        "outcomes": {
            "candidate": _panel_metrics(candidate),
            "reference": _panel_metrics(reference),
        },
        "paired_comparison": _paired_metrics(candidate, reference),
    }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    serialized = json.dumps(report, indent=2, sort_keys=True, allow_nan=False)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(serialized)
        stream.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analyze paired non-official reach-and-hold evaluation JSON."
    )
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--candidate-evaluation-semantics", required=True)
    parser.add_argument("--reference-evaluation-semantics", required=True)
    parser.add_argument("--semantics-source-operation", required=True)
    arguments = parser.parse_args(argv)

    try:
        candidate_semantics = arguments.candidate_evaluation_semantics
        reference_semantics = arguments.reference_evaluation_semantics
        semantics_source_operation = arguments.semantics_source_operation
        if not candidate_semantics.strip():
            raise AnalysisError(
                "--candidate-evaluation-semantics must be non-empty"
            )
        if not reference_semantics.strip():
            raise AnalysisError(
                "--reference-evaluation-semantics must be non-empty"
            )
        if candidate_semantics != reference_semantics:
            raise AnalysisError(
                "candidate and reference evaluation-semantics identifiers must match"
            )
        if not semantics_source_operation.strip():
            raise AnalysisError("--semantics-source-operation must be non-empty")

        candidate_path = arguments.candidate
        reference_path = arguments.reference
        output_path = arguments.output
        if output_path.resolve() in {
            candidate_path.resolve(),
            reference_path.resolve(),
        }:
            raise AnalysisError("output path must not overwrite an input artifact")
        candidate = _load_panel(
            candidate_path,
            "candidate",
            evaluation_semantics=candidate_semantics,
            semantics_source_operation=semantics_source_operation,
        )
        reference = _load_panel(
            reference_path,
            "reference",
            evaluation_semantics=reference_semantics,
            semantics_source_operation=semantics_source_operation,
        )
        report = build_report(candidate, reference)
        _write_report(output_path, report)
    except (AnalysisError, OSError) as exc:
        print(f"paired reach-and-hold analysis error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
