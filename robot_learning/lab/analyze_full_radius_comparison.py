"""PI-owned analysis of a matched full-radius evaluation pair.

The evaluator writes one primary outcome record and one diagnostic record per
episode.  This module deliberately consumes those records as data: it does not
run a policy, alter an evaluation, or infer a new task definition.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean, median
from typing import Any


RADIUS_STRATA: tuple[tuple[str, float, float, bool], ...] = (
    ("[6,10)", 6.0, 10.0, False),
    ("[10,14)", 10.0, 14.0, False),
    ("[14,17)", 14.0, 17.0, False),
    ("[17,20]", 17.0, 20.0, True),
)

_REQUIRED_DIAGNOSTIC_FIELDS = (
    "target_radius_cm",
    "first_reach_step",
    "hold_interruptions",
    "target_ik_branches",
    "nearest_target_ik_branch_at_first_entry",
    "min_joint_limit_margin_rad",
    "max_joint_speed_norm_rad_per_s",
    "max_absolute_action",
    "max_internal_substep_distance_cm",
    "max_internal_substep_distance_above_threshold_cm",
    "internal_substeps_above_threshold",
)


def _fail(message: str) -> None:
    raise ValueError(message)


def _finite_number(value: Any, *, field: str, allow_none: bool = True) -> float | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{field} must be a finite number or null")
    result = float(value)
    if not math.isfinite(result):
        _fail(f"{field} must be finite")
    return result


def _nonnegative_integer(value: Any, *, field: str, allow_none: bool = False) -> int | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(f"{field} must be a non-negative integer")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON artifact {path}: {exc}") from exc
    if not isinstance(document, dict):
        _fail(f"JSON artifact {path} must contain an object")
    return document


def _validate_branch(branch: Any, *, field: str) -> None:
    if branch is None:
        return
    if not isinstance(branch, dict):
        _fail(f"{field} must be an object or null")
    angles = branch.get("joint_angles_rad")
    margins = branch.get("joint_limit_margins_rad")
    if not isinstance(angles, list) or len(angles) != 2:
        _fail(f"{field}.joint_angles_rad must contain two values")
    if not isinstance(margins, list) or len(margins) != 2:
        _fail(f"{field}.joint_limit_margins_rad must contain two values")
    for index, value in enumerate(angles):
        _finite_number(value, field=f"{field}.joint_angles_rad[{index}]", allow_none=False)
    for index, value in enumerate(margins):
        _finite_number(
            value, field=f"{field}.joint_limit_margins_rad[{index}]", allow_none=False
        )
    _finite_number(
        branch.get("minimum_joint_limit_margin_rad"),
        field=f"{field}.minimum_joint_limit_margin_rad",
        allow_none=False,
    )


def _validate_diagnostic(record: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(record, dict):
        _fail(f"{label} diagnostic must be an object")
    if "episode" not in record:
        _fail(f"{label} diagnostic is missing episode")
    _nonnegative_integer(record["episode"], field=f"{label}.episode")
    for field in _REQUIRED_DIAGNOSTIC_FIELDS:
        if field not in record:
            _fail(f"{label} diagnostic is missing {field}")

    radius = _finite_number(
        record["target_radius_cm"], field=f"{label}.target_radius_cm", allow_none=False
    )
    if radius < 6.0 or radius > 20.0:
        _fail(f"{label}.target_radius_cm must be within [6, 20]")
    _nonnegative_integer(
        record["first_reach_step"],
        field=f"{label}.first_reach_step",
        allow_none=True,
    )
    _nonnegative_integer(record["hold_interruptions"], field=f"{label}.hold_interruptions")
    branches = record["target_ik_branches"]
    if not isinstance(branches, dict):
        _fail(f"{label}.target_ik_branches must be an object")
    for branch_name in ("open", "folded"):
        if branch_name not in branches:
            _fail(f"{label}.target_ik_branches is missing {branch_name}")
        _validate_branch(
            branches[branch_name],
            field=f"{label}.target_ik_branches.{branch_name}",
        )

    nearest = record["nearest_target_ik_branch_at_first_entry"]
    if nearest is not None:
        if not isinstance(nearest, dict) or nearest.get("branch") not in ("open", "folded"):
            _fail(
                f"{label}.nearest_target_ik_branch_at_first_entry must be null "
                "or identify open/folded"
            )
        _finite_number(
            nearest.get("configuration_distance_rad"),
            field=f"{label}.nearest_target_ik_branch_at_first_entry."
            "configuration_distance_rad",
            allow_none=False,
        )

    for field in (
        "min_joint_limit_margin_rad",
        "max_joint_speed_norm_rad_per_s",
        "max_absolute_action",
        "max_internal_substep_distance_cm",
        "max_internal_substep_distance_above_threshold_cm",
    ):
        _finite_number(record[field], field=f"{label}.{field}")
    _nonnegative_integer(
        record["internal_substeps_above_threshold"],
        field=f"{label}.internal_substeps_above_threshold",
    )
    return record


def _validated_records(document: dict[str, Any], *, label: str) -> tuple[dict[int, dict], dict[int, dict]]:
    results = document.get("episode_results")
    if not isinstance(results, list) or not results:
        _fail(f"{label}.episode_results must be a non-empty list")
    diagnostics_parent = document.get("research_evidence")
    if not isinstance(diagnostics_parent, dict):
        _fail(f"{label}.research_evidence must be an object")
    diagnostics = diagnostics_parent.get("episode_diagnostics")
    if not isinstance(diagnostics, list) or not diagnostics:
        _fail(f"{label}.research_evidence.episode_diagnostics must be a non-empty list")
    if len(results) != len(diagnostics):
        _fail(f"{label} has different outcome and diagnostic counts")
    if "episodes" in document:
        _nonnegative_integer(document["episodes"], field=f"{label}.episodes")
        if document["episodes"] != len(results):
            _fail(f"{label}.episodes does not match episode_results")

    result_by_episode: dict[int, dict] = {}
    diagnostic_by_episode: dict[int, dict] = {}
    for index, result in enumerate(results):
        if not isinstance(result, dict):
            _fail(f"{label}.episode_results[{index}] must be an object")
        episode = result.get("episode")
        _nonnegative_integer(episode, field=f"{label}.episode_results[{index}].episode")
        if episode in result_by_episode:
            _fail(f"{label} contains duplicate episode {episode}")
        if not isinstance(result.get("success"), bool):
            _fail(f"{label}.episode_results[{index}].success must be boolean")
        if "episode_seed" not in result:
            _fail(f"{label}.episode_results[{index}] is missing episode_seed")
        _nonnegative_integer(
            result["episode_seed"],
            field=f"{label}.episode_results[{index}].episode_seed",
        )
        result_by_episode[episode] = result

    for index, diagnostic in enumerate(diagnostics):
        checked = _validate_diagnostic(diagnostic, label=f"{label}.episode_diagnostics[{index}]")
        episode = checked["episode"]
        if episode in diagnostic_by_episode:
            _fail(f"{label} contains duplicate diagnostic episode {episode}")
        diagnostic_by_episode[episode] = checked

    if set(result_by_episode) != set(diagnostic_by_episode):
        _fail(f"{label} episode_results and diagnostics do not have matching episode IDs")
    return result_by_episode, diagnostic_by_episode


def _summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "min": None, "max": None, "mean": None, "median": None}
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": mean(values),
        "median": median(values),
    }


def radius_stratum(radius_cm: float) -> str:
    """Return the requested half-open/inclusive radius stratum."""
    radius = _finite_number(radius_cm, field="radius_cm", allow_none=False)
    for name, lower, upper, inclusive_upper in RADIUS_STRATA:
        in_stratum = (
            lower <= radius <= upper
            if inclusive_upper
            else lower <= radius < upper
        )
        if in_stratum:
            return name
    _fail(f"radius_cm {radius} is outside [6, 20]")


def _stats_for_records(
    episodes: list[int], result_by_episode: dict[int, dict]
) -> dict[str, Any]:
    successes = sum(1 for episode in episodes if result_by_episode[episode]["success"])
    count = len(episodes)
    return {
        "episodes": count,
        "successes": successes,
        "success_percent": 100.0 * successes / count if count else None,
    }


def _source_metadata(document: dict[str, Any]) -> dict[str, Any]:
    """Retain source identity fields without inventing absent metadata."""
    metadata: dict[str, Any] = {}
    identity_keys = (
        "artifact_id",
        "artifact_identity",
        "artifact_filename",
        "artifact_name",
        "artifact_path",
        "artifact_sha256",
        "artifact_hash",
        "sha256",
        "fingerprint",
        "source_artifact",
        "source_artifact_id",
        "source",
        "evaluation_id",
        "operation_id",
        "model",
        "seed",
        "episodes",
    )
    for key in identity_keys:
        if key in document:
            metadata[key] = document[key]
    return metadata


def _evaluator_metadata(document: dict[str, Any]) -> dict[str, Any]:
    """Retain evaluator semantics/schema fields without inventing metadata."""
    metadata: dict[str, Any] = {}
    evaluator_keys = (
        "schema_version",
        "evaluation_summary_version",
        "official_benchmark",
        "evaluator",
        "evaluator_schema",
        "evaluator_semantics",
        "evaluation_semantics",
    )
    for key in evaluator_keys:
        if key in document:
            metadata[key] = document[key]
    evidence = document.get("research_evidence")
    if isinstance(evidence, dict) and "units" in evidence:
        metadata["units"] = evidence["units"]
    return metadata


def _check_pair(
    candidate_document: dict[str, Any], reference_document: dict[str, Any]
) -> tuple[dict[int, dict], dict[int, dict], dict[int, dict], dict[int, dict]]:
    candidate_results, candidate_diagnostics = _validated_records(
        candidate_document, label="candidate"
    )
    reference_results, reference_diagnostics = _validated_records(
        reference_document, label="reference"
    )
    if set(candidate_results) != set(reference_results):
        _fail("candidate and reference do not contain the same episode IDs")
    for episode in candidate_results:
        candidate_result = candidate_results[episode]
        reference_result = reference_results[episode]
        if candidate_result["episode_seed"] != reference_result["episode_seed"]:
            _fail(f"episode {episode} has mismatched episode seeds")
        candidate_radius = candidate_diagnostics[episode]["target_radius_cm"]
        reference_radius = reference_diagnostics[episode]["target_radius_cm"]
        if not math.isclose(candidate_radius, reference_radius, rel_tol=0.0, abs_tol=1e-9):
            _fail(f"episode {episode} has mismatched target radii")
    if "seed" in candidate_document:
        _nonnegative_integer(candidate_document["seed"], field="candidate.seed")
    if "seed" in reference_document:
        _nonnegative_integer(reference_document["seed"], field="reference.seed")
    if "seed" in candidate_document and "seed" in reference_document:
        if candidate_document["seed"] != reference_document["seed"]:
            _fail("candidate and reference have different panel seeds")
    return candidate_results, candidate_diagnostics, reference_results, reference_diagnostics


def _policy_diagnostics(
    result_by_episode: dict[int, dict],
    diagnostic_by_episode: dict[int, dict],
) -> dict[str, Any]:
    episodes = sorted(result_by_episode)
    no_entry = [
        episode
        for episode in episodes
        if not result_by_episode[episode]["success"]
        and diagnostic_by_episode[episode]["first_reach_step"] is None
    ]
    post_entry = [
        episode
        for episode in episodes
        if not result_by_episode[episode]["success"]
        and diagnostic_by_episode[episode]["first_reach_step"] is not None
    ]
    branch_counts = {"open": 0, "folded": 0, "null": 0}
    for episode in episodes:
        nearest = diagnostic_by_episode[episode]["nearest_target_ik_branch_at_first_entry"]
        if nearest is None:
            branch_counts["null"] += 1
        else:
            branch_counts[nearest["branch"]] += 1

    first_entries = sum(
        diagnostic_by_episode[episode]["first_reach_step"] is not None for episode in episodes
    )
    hold_interruptions = [
        diagnostic_by_episode[episode]["hold_interruptions"] for episode in episodes
    ]
    target_margins: dict[str, list[float]] = {"open": [], "folded": []}
    for episode in episodes:
        branches = diagnostic_by_episode[episode]["target_ik_branches"]
        for branch_name in target_margins:
            branch = branches[branch_name]
            if branch is not None:
                target_margins[branch_name].append(
                    float(branch["minimum_joint_limit_margin_rad"])
                )

    above_threshold = [
        diagnostic_by_episode[episode]["internal_substeps_above_threshold"]
        for episode in episodes
    ]
    return {
        "failures": {
            "no_entry_failures": len(no_entry),
            "post_entry_unsuccessful": len(post_entry),
            "hold_interruption_count": sum(hold_interruptions),
            "episodes_with_hold_interruptions": sum(value > 0 for value in hold_interruptions),
        },
        "first_entry": {
            "entries": first_entries,
            "episodes": len(episodes),
            "rate_percent": 100.0 * first_entries / len(episodes),
        },
        "branch_at_first_entry": branch_counts,
        "joint_limit_margin": {
            "target": {
                branch_name: _summary(values)
                for branch_name, values in target_margins.items()
            },
            "rollout": _summary(
                [
                    diagnostic_by_episode[episode]["min_joint_limit_margin_rad"]
                    for episode in episodes
                    if diagnostic_by_episode[episode]["min_joint_limit_margin_rad"] is not None
                ]
            ),
        },
        "joint_speed_and_action": {
            "max_joint_speed_norm_rad_per_s": _summary(
                [
                    diagnostic_by_episode[episode]["max_joint_speed_norm_rad_per_s"]
                    for episode in episodes
                    if diagnostic_by_episode[episode]["max_joint_speed_norm_rad_per_s"] is not None
                ]
            ),
            "max_absolute_action": _summary(
                [
                    diagnostic_by_episode[episode]["max_absolute_action"]
                    for episode in episodes
                    if diagnostic_by_episode[episode]["max_absolute_action"] is not None
                ]
            ),
        },
        "internal_substeps": {
            "max_distance_cm": _summary(
                [
                    diagnostic_by_episode[episode]["max_internal_substep_distance_cm"]
                    for episode in episodes
                    if diagnostic_by_episode[episode]["max_internal_substep_distance_cm"] is not None
                ]
            ),
            "max_distance_above_threshold_cm": _summary(
                [
                    diagnostic_by_episode[episode][
                        "max_internal_substep_distance_above_threshold_cm"
                    ]
                    for episode in episodes
                    if diagnostic_by_episode[episode][
                        "max_internal_substep_distance_above_threshold_cm"
                    ]
                    is not None
                ]
            ),
            "above_threshold_count": sum(above_threshold),
            "episodes_with_above_threshold": sum(value > 0 for value in above_threshold),
        },
    }


def analyze_documents(
    candidate_document: dict[str, Any], reference_document: dict[str, Any]
) -> dict[str, Any]:
    """Analyze two matched evaluator documents without touching the filesystem."""
    (
        candidate_results,
        candidate_diagnostics,
        reference_results,
        reference_diagnostics,
    ) = _check_pair(candidate_document, reference_document)
    episodes = sorted(candidate_results)
    candidate_successes = sum(candidate_results[episode]["success"] for episode in episodes)
    reference_successes = sum(reference_results[episode]["success"] for episode in episodes)
    candidate_wins = sum(
        candidate_results[episode]["success"] and not reference_results[episode]["success"]
        for episode in episodes
    )
    reference_wins = sum(
        reference_results[episode]["success"] and not candidate_results[episode]["success"]
        for episode in episodes
    )
    discordant = candidate_wins + reference_wins

    radius_strata: list[dict[str, Any]] = []
    for name, _, _, _ in RADIUS_STRATA:
        stratum_episodes = [
            episode
            for episode in episodes
            if radius_stratum(candidate_diagnostics[episode]["target_radius_cm"]) == name
        ]
        radius_strata.append(
            {
                "stratum": name,
                "candidate": _stats_for_records(stratum_episodes, candidate_results),
                "reference": _stats_for_records(stratum_episodes, reference_results),
            }
        )

    return {
        "schema_version": 1,
        "overall": {
            "candidate": _stats_for_records(episodes, candidate_results),
            "reference": _stats_for_records(episodes, reference_results),
            "paired_discordance": {
                "candidate_wins": candidate_wins,
                "reference_wins": reference_wins,
                "ties": len(episodes) - discordant,
                "discordant": discordant,
            },
        },
        "radius_strata": radius_strata,
        "candidate": _policy_diagnostics(candidate_results, candidate_diagnostics),
        "reference": _policy_diagnostics(reference_results, reference_diagnostics),
        "source_artifacts": {
            "candidate": _source_metadata(candidate_document),
            "reference": _source_metadata(reference_document),
        },
        "evaluator": {
            "candidate": _evaluator_metadata(candidate_document),
            "reference": _evaluator_metadata(reference_document),
        },
    }


def analyze_artifacts(
    candidate_artifact: str | Path,
    reference_artifact: str | Path,
    output_artifact: str | Path,
) -> dict[str, Any]:
    """Read two JSON artifacts, write the comparison, and return it."""
    result = analyze_documents(
        _load_json(Path(candidate_artifact)),
        _load_json(Path(reference_artifact)),
    )
    output_path = Path(output_artifact)
    try:
        output_path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise ValueError(f"cannot write comparison artifact {output_path}: {exc}") from exc
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate_artifact", type=Path)
    parser.add_argument("reference_artifact", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    analyze_artifacts(args.candidate_artifact, args.reference_artifact, args.output)


if __name__ == "__main__":
    main()
