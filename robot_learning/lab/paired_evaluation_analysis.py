"""Paired, episode-level analysis of two research evaluation artifacts.

The evaluator records one outcome row and one diagnostic row for each episode.
This module validates those two channels before combining them, so that paired
comparisons cannot silently align different episodes or reinterpret a missing
diagnostic as a zero.

Normal use:

    python -m robot_learning.lab.paired_evaluation_analysis \
        --outer-only outer.json --full-radius full.json --output result.json

The ``--check`` mode is a small, artifact-independent laboratory verification
of the same loading and analysis paths.  It is intended for the existing
``python_module`` instrument; it does not certify scientific validity.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import tempfile
from pathlib import Path
from typing import Any


RADIUS_BINS = (
    (0.06, 0.10, False, "[0.06,0.10)"),
    (0.10, 0.14, False, "[0.10,0.14)"),
    (0.14, 0.18, False, "[0.14,0.18)"),
    (0.18, 0.20, True, "[0.18,0.20]"),
)
BRANCH_STRATA = ("both", "open_only", "folded_only", "none")
SUCCESS_HOLD_STEPS = 100

UNCHECKED_SCOPE = [
    "Endpoint diagnostics do not establish within-frame-skip continuous stability.",
    "This is an artifact-level comparison rather than causal exposure proof.",
    "A 160-episode panel is not the protected 200-episode assessment.",
]

_RESULT_FIELDS = (
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
    "ik_open_legal",
    "ik_folded_legal",
    "ik_branch_classification",
    "min_distance_cm",
    "final_distance_cm",
    "first_reach_step",
    "max_held_steps",
    "in_tolerance_steps",
    "hold_interruptions",
    "applied_action_magnitude_mean",
    "applied_action_magnitude_max",
    "applied_action_saturation_steps",
    "applied_action_saturation_fraction",
    "applied_action_saturation_elements",
    "applied_action_saturation_element_fraction",
    "joint_velocity_magnitude_mean",
    "joint_velocity_magnitude_max",
    "joint_velocity_magnitude_final",
    "joint_velocity_max_abs",
    "control_steps_recorded",
)


def _reject_nonfinite_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is not permitted: {value}")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            document = json.load(handle, parse_constant=_reject_nonfinite_constant)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise ValueError(f"{path} must contain a JSON object")
    _assert_finite_json(document, str(path))
    return document


def _assert_finite_json(value: Any, location: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite numeric value at {location}")
    if isinstance(value, dict):
        for key, child in value.items():
            _assert_finite_json(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_finite_json(child, f"{location}[{index}]")


def _require_fields(value: dict[str, Any], fields: tuple[str, ...], context: str) -> None:
    missing = [field for field in fields if field not in value]
    if missing:
        raise ValueError(f"{context} is missing required fields: {', '.join(missing)}")


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_integer(value: Any, context: str, *, minimum: int | None = None) -> int:
    if not _is_integer(value):
        raise ValueError(f"{context} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{context} must be at least {minimum}")
    return int(value)


def _require_number(value: Any, context: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{context} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{context} must be finite")
    if minimum is not None and number < minimum:
        raise ValueError(f"{context} must be at least {minimum}")
    return number


def _radius_bin(radius_cm: float) -> str:
    radius_m = radius_cm / 100.0
    for lower, upper, upper_inclusive, label in RADIUS_BINS:
        if lower <= radius_m < upper or (
            upper_inclusive and lower <= radius_m <= upper
        ):
            return label
    raise ValueError(
        f"target_radius_cm={radius_cm} is outside the fixed [0.06,0.20] radius range"
    )


def _branch_from_flags(open_legal: bool, folded_legal: bool) -> str:
    if open_legal and folded_legal:
        return "both"
    if open_legal:
        return "open_only"
    if folded_legal:
        return "folded_only"
    return "none"


def _validate_result_row(row: Any, index: int) -> dict[str, Any]:
    context = f"episode_results[{index}]"
    if not isinstance(row, dict):
        raise ValueError(f"{context} must be an object")
    _require_fields(row, _RESULT_FIELDS, context)
    _require_integer(row["episode"], f"{context}.episode", minimum=0)
    _require_integer(row["episode_seed"], f"{context}.episode_seed", minimum=0)
    if not isinstance(row["success"], bool):
        raise ValueError(f"{context}.success must be boolean")
    _require_number(row["reward_total"], f"{context}.reward_total")
    _require_integer(row["steps"], f"{context}.steps", minimum=1)
    if not isinstance(row["terminated"], bool) or not isinstance(
        row["truncated"], bool
    ):
        raise ValueError(f"{context}.terminated and truncated must be boolean")
    return row


def _validate_diagnostic_row(row: Any, index: int) -> dict[str, Any]:
    context = f"episode_diagnostics[{index}]"
    if not isinstance(row, dict):
        raise ValueError(f"{context} must be an object")
    _require_fields(row, _DIAGNOSTIC_FIELDS, context)
    _require_integer(row["episode"], f"{context}.episode", minimum=0)
    _require_integer(row["episode_seed"], f"{context}.episode_seed", minimum=0)

    radius_cm = _require_number(
        row["target_radius_cm"], f"{context}.target_radius_cm", minimum=0.0
    )
    _require_number(row["target_angle_degrees"], f"{context}.target_angle_degrees")
    if not isinstance(row["ik_open_legal"], bool) or not isinstance(
        row["ik_folded_legal"], bool
    ):
        raise ValueError(f"{context}.ik_open_legal and ik_folded_legal must be boolean")
    branch = row["ik_branch_classification"]
    if branch not in BRANCH_STRATA:
        raise ValueError(f"{context}.ik_branch_classification is invalid: {branch!r}")
    expected_branch = _branch_from_flags(
        row["ik_open_legal"], row["ik_folded_legal"]
    )
    if branch != expected_branch:
        raise ValueError(
            f"{context}.ik_branch_classification disagrees with legal-branch flags"
        )
    _radius_bin(radius_cm)

    _require_number(row["min_distance_cm"], f"{context}.min_distance_cm", minimum=0.0)
    _require_number(row["final_distance_cm"], f"{context}.final_distance_cm", minimum=0.0)
    first_reach_step = row["first_reach_step"]
    if first_reach_step is not None:
        _require_integer(first_reach_step, f"{context}.first_reach_step", minimum=1)
    max_held_steps = _require_integer(
        row["max_held_steps"], f"{context}.max_held_steps", minimum=0
    )
    in_tolerance_steps = _require_integer(
        row["in_tolerance_steps"], f"{context}.in_tolerance_steps", minimum=0
    )
    hold_interruptions = _require_integer(
        row["hold_interruptions"], f"{context}.hold_interruptions", minimum=0
    )
    for field in (
        "applied_action_saturation_steps",
        "applied_action_saturation_elements",
        "control_steps_recorded",
    ):
        _require_integer(row[field], f"{context}.{field}", minimum=0)
    for field in (
        "applied_action_magnitude_mean",
        "applied_action_magnitude_max",
        "applied_action_saturation_fraction",
        "applied_action_saturation_element_fraction",
        "joint_velocity_magnitude_mean",
        "joint_velocity_magnitude_max",
        "joint_velocity_magnitude_final",
        "joint_velocity_max_abs",
    ):
        _require_number(row[field], f"{context}.{field}", minimum=0.0)
    for field in (
        "applied_action_saturation_fraction",
        "applied_action_saturation_element_fraction",
    ):
        if not 0.0 <= float(row[field]) <= 1.0:
            raise ValueError(f"{context}.{field} must be in [0, 1]")

    if first_reach_step is None and (max_held_steps != 0 or in_tolerance_steps != 0):
        raise ValueError(
            f"{context} has no first reach but reports in-tolerance activity"
        )
    if first_reach_step is not None and max_held_steps == 0:
        raise ValueError(f"{context} has a first reach but no held steps")
    return row


def _validate_artifact(document: dict[str, Any], label: str) -> list[dict[str, Any]]:
    context = f"{label} research_evaluation artifact"
    _require_fields(
        document,
        (
            "schema_version",
            "model",
            "episodes",
            "seed",
            "success_percent",
            "episode_results",
            "research_evidence",
        ),
        context,
    )
    _require_integer(document["schema_version"], f"{context}.schema_version", minimum=1)
    if not isinstance(document["model"], str) or not document["model"]:
        raise ValueError(f"{context}.model must be a non-empty string")
    episodes = _require_integer(document["episodes"], f"{context}.episodes", minimum=1)
    seed = _require_integer(document["seed"], f"{context}.seed", minimum=0)
    success_percent = _require_number(
        document["success_percent"], f"{context}.success_percent", minimum=0.0
    )
    if success_percent > 100.0:
        raise ValueError(f"{context}.success_percent must not exceed 100")
    results = document["episode_results"]
    evidence = document["research_evidence"]
    if not isinstance(results, list):
        raise ValueError(f"{context}.episode_results must be an array")
    if not isinstance(evidence, dict):
        raise ValueError(f"{context}.research_evidence must be an object")
    _require_fields(evidence, ("episode_diagnostics",), f"{context}.research_evidence")
    diagnostics = evidence["episode_diagnostics"]
    if not isinstance(diagnostics, list):
        raise ValueError(f"{context}.research_evidence.episode_diagnostics must be an array")
    if len(results) != episodes or len(diagnostics) != episodes:
        raise ValueError(f"{context} episode count does not match both episode arrays")

    validated_results = [_validate_result_row(row, index) for index, row in enumerate(results)]
    validated_diagnostics = [
        _validate_diagnostic_row(row, index)
        for index, row in enumerate(diagnostics)
    ]
    result_by_episode: dict[int, dict[str, Any]] = {}
    diagnostic_by_episode: dict[int, dict[str, Any]] = {}
    for row in validated_results:
        episode = int(row["episode"])
        if episode in result_by_episode:
            raise ValueError(f"{context} has duplicate result episode {episode}")
        result_by_episode[episode] = row
    for row in validated_diagnostics:
        episode = int(row["episode"])
        if episode in diagnostic_by_episode:
            raise ValueError(f"{context} has duplicate diagnostic episode {episode}")
        diagnostic_by_episode[episode] = row
    expected_episodes = set(range(episodes))
    if set(result_by_episode) != expected_episodes or set(diagnostic_by_episode) != expected_episodes:
        raise ValueError(f"{context} episode identifiers must be exactly 0 through {episodes - 1}")

    joined: list[dict[str, Any]] = []
    for episode in range(episodes):
        result = result_by_episode[episode]
        diagnostic = diagnostic_by_episode[episode]
        if result["episode_seed"] != diagnostic["episode_seed"]:
            raise ValueError(f"{context} has mismatched result/diagnostic seed at episode {episode}")
        if result["steps"] != diagnostic["control_steps_recorded"]:
            raise ValueError(f"{context} has mismatched result/diagnostic steps at episode {episode}")
        if result["success"] != (diagnostic["max_held_steps"] >= SUCCESS_HOLD_STEPS):
            raise ValueError(
                f"{context} has success inconsistent with held-step diagnostics at episode {episode}"
            )
        if diagnostic["first_reach_step"] is not None and diagnostic["first_reach_step"] > result["steps"]:
            raise ValueError(f"{context} first reach is after episode end at episode {episode}")
        joined.append({"episode": episode, "result": result, "diagnostic": diagnostic})

    expected_seed_sequence = [seed + episode for episode in range(episodes)]
    actual_seed_sequence = [int(item["result"]["episode_seed"]) for item in joined]
    if actual_seed_sequence != expected_seed_sequence:
        raise ValueError(f"{context} episode seeds are not consecutive from the artifact seed")
    expected_success_percent = 100.0 * sum(
        bool(item["result"]["success"]) for item in joined
    ) / episodes
    if not math.isclose(
        success_percent, expected_success_percent, rel_tol=0.0, abs_tol=1e-9
    ):
        raise ValueError(f"{context}.success_percent disagrees with episode outcomes")
    return joined


def _check_shared_panel(
    outer: list[dict[str, Any]], full: list[dict[str, Any]]
) -> None:
    if len(outer) != len(full):
        raise ValueError("paired artifacts must have the same episode count")
    for outer_item, full_item in zip(outer, full):
        if outer_item["episode"] != full_item["episode"]:
            raise ValueError("paired artifacts do not share episode identifiers")
        outer_result = outer_item["result"]
        full_result = full_item["result"]
        if outer_result["episode_seed"] != full_result["episode_seed"]:
            raise ValueError(
                f"paired artifacts have mismatched episode seeds at episode {outer_item['episode']}"
            )
        outer_diag = outer_item["diagnostic"]
        full_diag = full_item["diagnostic"]
        if outer_diag["ik_branch_classification"] != full_diag["ik_branch_classification"]:
            raise ValueError(
                f"paired artifacts have mismatched branch strata at episode {outer_item['episode']}"
            )
        outer_bin = _radius_bin(float(outer_diag["target_radius_cm"]))
        full_bin = _radius_bin(float(full_diag["target_radius_cm"]))
        if outer_bin != full_bin or not math.isclose(
            float(outer_diag["target_radius_cm"]),
            float(full_diag["target_radius_cm"]),
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError(
                f"paired artifacts have mismatched target radii at episode {outer_item['episode']}"
            )


def _mean(values: list[float]) -> float | None:
    return None if not values else float(sum(values) / len(values))


def _aggregate(items: list[dict[str, Any]]) -> dict[str, Any]:
    successes = sum(bool(item["result"]["success"]) for item in items)
    return {
        "episode_count": len(items),
        "successes": successes,
        "success_rate": float(successes / len(items)) if items else None,
        "mean_max_held_steps": _mean(
            [float(item["diagnostic"]["max_held_steps"]) for item in items]
        ),
        "max_held_steps": (
            max(
                (int(item["diagnostic"]["max_held_steps"]) for item in items),
                default=None,
            )
        ),
        "interrupted_episode_count": sum(
            int(item["diagnostic"]["hold_interruptions"]) > 0 for item in items
        ),
        "never_reached_count": sum(
            item["diagnostic"]["first_reach_step"] is None for item in items
        ),
        "mean_minimum_distance_cm": _mean(
            [float(item["diagnostic"]["min_distance_cm"]) for item in items]
        ),
        "mean_final_distance_cm": _mean(
            [float(item["diagnostic"]["final_distance_cm"]) for item in items]
        ),
        "mean_action_saturation_fraction": _mean(
            [
                float(item["diagnostic"]["applied_action_saturation_fraction"])
                for item in items
            ]
        ),
        "mean_joint_velocity_max": _mean(
            [
                float(item["diagnostic"]["joint_velocity_magnitude_max"])
                for item in items
            ]
        ),
        "max_joint_velocity_max": max(
            (
                float(item["diagnostic"]["joint_velocity_magnitude_max"])
                for item in items
            ),
            default=None,
        ),
    }


def _candidate_aggregate(items: list[dict[str, Any]], label: str) -> dict[str, Any]:
    # Keeping the candidate label at the call site makes the two sides of every
    # paired table explicit instead of relying on positional interpretation.
    result = _aggregate(items)
    result["candidate"] = label
    return result


def _failure_mode_counts(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    predicates = {
        "never_reached": lambda item: item["diagnostic"]["first_reach_step"] is None,
        "reached_but_never_completed": lambda item: (
            item["diagnostic"]["first_reach_step"] is not None
            and not item["result"]["success"]
        ),
        "interrupted_hold": lambda item: (
            item["diagnostic"]["hold_interruptions"] > 0
            and not item["result"]["success"]
        ),
    }
    output: dict[str, dict[str, Any]] = {}
    for name, predicate in predicates.items():
        count = sum(predicate(item) for item in items)
        output[name] = {
            "count": count,
            "rate": float(count / len(items)) if items else None,
        }
    return output


def _paired_discordance(
    outer: list[dict[str, Any]], full: list[dict[str, Any]]
) -> dict[str, int]:
    pairs = [
        (bool(outer_item["result"]["success"]), bool(full_item["result"]["success"]))
        for outer_item, full_item in zip(outer, full)
    ]
    return {
        "outer_only_success": sum(outer_success and not full_success for outer_success, full_success in pairs),
        "full_radius_only_success": sum(not outer_success and full_success for outer_success, full_success in pairs),
        "both_success": sum(outer_success and full_success for outer_success, full_success in pairs),
        "both_failure": sum(not outer_success and not full_success for outer_success, full_success in pairs),
    }


def analyze_documents(
    outer_document: dict[str, Any], full_document: dict[str, Any]
) -> dict[str, Any]:
    """Validate and analyze two completed research-evaluation documents."""
    outer = _validate_artifact(outer_document, "outer_only")
    full = _validate_artifact(full_document, "full_radius")
    _check_shared_panel(outer, full)

    radius_bins: list[dict[str, Any]] = []
    for lower, upper, upper_inclusive, label in RADIUS_BINS:
        outer_items = [
            item
            for item in outer
            if _radius_bin(float(item["diagnostic"]["target_radius_cm"])) == label
        ]
        full_items = [
            item
            for item in full
            if _radius_bin(float(item["diagnostic"]["target_radius_cm"])) == label
        ]
        radius_bins.append(
            {
                "label": label,
                "lower_radius_m": lower,
                "upper_radius_m": upper,
                "upper_inclusive": upper_inclusive,
                "outer_only": _candidate_aggregate(outer_items, "outer_only"),
                "full_radius": _candidate_aggregate(full_items, "full_radius"),
            }
        )

    branch_strata: dict[str, Any] = {}
    for branch in BRANCH_STRATA:
        outer_items = [
            item
            for item in outer
            if item["diagnostic"]["ik_branch_classification"] == branch
        ]
        full_items = [
            item
            for item in full
            if item["diagnostic"]["ik_branch_classification"] == branch
        ]
        branch_strata[branch] = {
            "episode_count": len(outer_items),
            "outer_only": _candidate_aggregate(outer_items, "outer_only"),
            "full_radius": _candidate_aggregate(full_items, "full_radius"),
        }

    outer_failure_modes = _failure_mode_counts(outer)
    full_failure_modes = _failure_mode_counts(full)
    failure_mode_paired_differences = {}
    for mode in outer_failure_modes:
        failure_mode_paired_differences[mode] = {
            "count_outer_only_minus_full_radius": (
                outer_failure_modes[mode]["count"] - full_failure_modes[mode]["count"]
            ),
            "rate_outer_only_minus_full_radius": (
                outer_failure_modes[mode]["rate"] - full_failure_modes[mode]["rate"]
                if outer_failure_modes[mode]["rate"] is not None
                and full_failure_modes[mode]["rate"] is not None
                else None
            ),
        }

    return {
        "analysis": "paired_research_evaluation",
        "analysis_version": 1,
        "episode_count": len(outer),
        "candidates": {
            "outer_only": _candidate_aggregate(outer, "outer_only"),
            "full_radius": _candidate_aggregate(full, "full_radius"),
        },
        "paired_discordance_counts": _paired_discordance(outer, full),
        "radius_bins": radius_bins,
        "branch_strata": branch_strata,
        "failure_modes": {
            "outer_only": outer_failure_modes,
            "full_radius": full_failure_modes,
        },
        "failure_mode_paired_differences": failure_mode_paired_differences,
        "unchecked_scope": list(UNCHECKED_SCOPE),
    }


def analyze_paths(outer_path: Path, full_path: Path) -> dict[str, Any]:
    result = analyze_documents(_load_json(outer_path), _load_json(full_path))
    result["input_artifacts"] = {
        "outer_only": str(outer_path),
        "full_radius": str(full_path),
    }
    return result


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def _fixture_artifact(
    successes: list[bool],
    radii_cm: list[float],
    branches: list[str],
    first_reaches: list[int | None],
    held_steps: list[int],
    interruptions: list[int],
) -> dict[str, Any]:
    results = []
    diagnostics = []
    for episode, (
        success,
        radius_cm,
        branch,
        first_reach,
        held,
        interruption,
    ) in enumerate(
        zip(
            successes,
            radii_cm,
            branches,
            first_reaches,
            held_steps,
            interruptions,
        )
    ):
        legal_flags = {
            "both": (True, True),
            "open_only": (True, False),
            "folded_only": (False, True),
            "none": (False, False),
        }[branch]
        steps = 120
        results.append(
            {
                "episode": episode,
                "episode_seed": 100 + episode,
                "success": success,
                "reward_total": float(episode),
                "steps": steps,
                "terminated": success,
                "truncated": not success,
            }
        )
        diagnostics.append(
            {
                "episode": episode,
                "episode_seed": 100 + episode,
                "target_radius_cm": radius_cm,
                "target_angle_degrees": float(episode * 20),
                "ik_open_legal": legal_flags[0],
                "ik_folded_legal": legal_flags[1],
                "ik_branch_classification": branch,
                "min_distance_cm": 0.5 + episode,
                "final_distance_cm": 0.6 + episode,
                "first_reach_step": first_reach,
                "max_held_steps": held,
                "in_tolerance_steps": 0 if first_reach is None else held,
                "hold_interruptions": interruption,
                "applied_action_magnitude_mean": 0.2,
                "applied_action_magnitude_max": 0.8,
                "applied_action_saturation_steps": 2,
                "applied_action_saturation_fraction": 0.1,
                "applied_action_saturation_elements": 4,
                "applied_action_saturation_element_fraction": 0.05,
                "joint_velocity_magnitude_mean": 0.3,
                "joint_velocity_magnitude_max": 0.4 + episode,
                "joint_velocity_magnitude_final": 0.1,
                "joint_velocity_max_abs": 0.35 + episode,
                "control_steps_recorded": steps,
            }
        )
    return {
        "schema_version": 5,
        "model": "controlled-fixture",
        "episodes": len(results),
        "seed": 100,
        "success_percent": 100.0 * sum(successes) / len(results),
        "episode_results": results,
        "research_evidence": {
            "episode_diagnostics": diagnostics,
            "units": {
                "distance": "cm",
                "time": "control_steps",
                "action": "normalized_control",
                "joint_velocity": "rad_per_second",
            },
        },
    }


def _run_check(output_path: Path) -> None:
    outer_fixture = _fixture_artifact(
        [True, False, False, True],
        [6.0, 10.0, 14.0, 20.0],
        ["both", "open_only", "folded_only", "none"],
        [10, None, 20, 5],
        [100, 0, 30, 100],
        [1, 0, 0, 0],
    )
    full_fixture = _fixture_artifact(
        [False, True, False, True],
        [6.0, 10.0, 14.0, 20.0],
        ["both", "open_only", "folded_only", "none"],
        [10, 8, 20, 5],
        [50, 100, 30, 100],
        [1, 0, 0, 0],
    )
    with tempfile.TemporaryDirectory(prefix="paired-evaluation-check-") as directory:
        outer_path = Path(directory) / "outer.json"
        full_path = Path(directory) / "full.json"
        _write_json(outer_path, outer_fixture)
        _write_json(full_path, full_fixture)
        observed = analyze_paths(outer_path, full_path)

    expected_discordance = {
        "outer_only_success": 1,
        "full_radius_only_success": 1,
        "both_success": 1,
        "both_failure": 1,
    }
    if observed["episode_count"] != 4:
        raise AssertionError("the controlled panel did not retain all four episodes")
    if observed["paired_discordance_counts"] != expected_discordance:
        raise AssertionError(
            f"paired discordance mismatch: {observed['paired_discordance_counts']!r}"
        )
    expected_candidate_summaries = {
        "outer_only": {
            "successes": 2,
            "success_rate": 0.5,
            "mean_max_held_steps": 57.5,
            "max_held_steps": 100,
            "interrupted_episode_count": 1,
            "never_reached_count": 1,
        },
        "full_radius": {
            "successes": 2,
            "success_rate": 0.5,
            "mean_max_held_steps": 70.0,
            "max_held_steps": 100,
            "interrupted_episode_count": 1,
            "never_reached_count": 0,
        },
    }
    for candidate, expected in expected_candidate_summaries.items():
        for field, expected_value in expected.items():
            if observed["candidates"][candidate][field] != expected_value:
                raise AssertionError(
                    f"{candidate} summary mismatch for {field}: "
                    f"{observed['candidates'][candidate][field]!r}"
                )
    expected_outer_counts = [1, 0, 0, 1]
    expected_full_counts = [0, 1, 0, 1]
    for index, radius_bin in enumerate(observed["radius_bins"]):
        if radius_bin["outer_only"]["episode_count"] != 1:
            raise AssertionError("each controlled radius boundary must occupy one bin")
        if radius_bin["outer_only"]["successes"] != expected_outer_counts[index]:
            raise AssertionError("outer-only radius-stratified success mismatch")
        if radius_bin["full_radius"]["successes"] != expected_full_counts[index]:
            raise AssertionError("full-radius radius-stratified success mismatch")
    expected_branch_successes = {
        "both": (1, 0),
        "open_only": (0, 1),
        "folded_only": (0, 0),
        "none": (1, 1),
    }
    for branch, (outer_successes, full_successes) in expected_branch_successes.items():
        if observed["branch_strata"][branch]["outer_only"]["successes"] != outer_successes:
            raise AssertionError(f"outer-only branch result mismatch for {branch}")
        if observed["branch_strata"][branch]["full_radius"]["successes"] != full_successes:
            raise AssertionError(f"full-radius branch result mismatch for {branch}")
    expected_outer_failure_counts = (1, 1, 0)
    expected_full_failure_counts = (0, 2, 1)
    modes = ("never_reached", "reached_but_never_completed", "interrupted_hold")
    for mode, outer_count, full_count in zip(
        modes, expected_outer_failure_counts, expected_full_failure_counts
    ):
        if observed["failure_modes"]["outer_only"][mode]["count"] != outer_count:
            raise AssertionError(f"outer-only failure-mode mismatch for {mode}")
        if observed["failure_modes"]["full_radius"][mode]["count"] != full_count:
            raise AssertionError(f"full-radius failure-mode mismatch for {mode}")
        if (
            observed["failure_mode_paired_differences"][mode][
                "count_outer_only_minus_full_radius"
            ]
            != outer_count - full_count
        ):
            raise AssertionError(f"paired failure-mode difference mismatch for {mode}")

    negative_cases: dict[str, bool] = {}
    mismatched_seed = copy.deepcopy(full_fixture)
    mismatched_seed["episode_results"][0]["episode_seed"] = 999
    try:
        analyze_documents(outer_fixture, mismatched_seed)
    except ValueError:
        negative_cases["mismatched_join_seed_rejected"] = True
    else:
        negative_cases["mismatched_join_seed_rejected"] = False

    invalid_branch = copy.deepcopy(full_fixture)
    invalid_branch["research_evidence"]["episode_diagnostics"][0][
        "ik_branch_classification"
    ] = "invalid"
    try:
        analyze_documents(outer_fixture, invalid_branch)
    except ValueError:
        negative_cases["invalid_branch_rejected"] = True
    else:
        negative_cases["invalid_branch_rejected"] = False
    if not all(negative_cases.values()):
        raise AssertionError(f"validation negative cases were not rejected: {negative_cases}")

    artifact = {
        "check": "paired_evaluation_analysis",
        "status": "passed",
        "observed": {
            "episode_count": observed["episode_count"],
            "paired_discordance_counts": observed["paired_discordance_counts"],
            "candidate_summaries": {
                candidate: {
                    field: values[field]
                    for field in expected_candidate_summaries[candidate]
                }
                for candidate, values in observed["candidates"].items()
            },
            "radius_bin_successes": [
                {
                    "label": item["label"],
                    "outer_only": item["outer_only"]["successes"],
                    "full_radius": item["full_radius"]["successes"],
                }
                for item in observed["radius_bins"]
            ],
            "branch_successes": {
                branch: {
                    "outer_only": item["outer_only"]["successes"],
                    "full_radius": item["full_radius"]["successes"],
                }
                for branch, item in observed["branch_strata"].items()
            },
            "failure_mode_counts": {
                candidate: {
                    mode: values["count"] for mode, values in modes_by_candidate.items()
                }
                for candidate, modes_by_candidate in observed["failure_modes"].items()
            },
            "negative_cases": negative_cases,
        },
        "expected": {
            "episode_count": 4,
            "paired_discordance_counts": expected_discordance,
            "candidate_summaries": expected_candidate_summaries,
            "radius_bin_outer_successes": expected_outer_counts,
            "radius_bin_full_successes": expected_full_counts,
            "branch_successes": expected_branch_successes,
            "outer_failure_mode_counts": dict(zip(modes, expected_outer_failure_counts)),
            "full_failure_mode_counts": dict(zip(modes, expected_full_failure_counts)),
            "negative_cases": {
                "mismatched_join_seed_rejected": True,
                "invalid_branch_rejected": True,
            },
        },
        "checked_scope": [
            "JSON loading and paired episode-seed validation",
            "radius-bin boundary assignment including 0.06, 0.10, 0.14, and 0.20 m",
            "branch-stratum success counts",
            "failure-mode predicates and paired count differences",
            "rejection of mismatched joins and invalid branch categories",
        ],
        "unchecked_scope": list(UNCHECKED_SCOPE),
    }
    _write_json(output_path, artifact)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outer-only", type=Path)
    parser.add_argument("--full-radius", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--check",
        type=Path,
        help="write the artifact-independent laboratory verification artifact",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.check is not None:
        if any(value is not None for value in (args.outer_only, args.full_radius, args.output)):
            raise SystemExit("--check cannot be combined with analysis input arguments")
        _run_check(args.check)
        return
    if args.outer_only is None or args.full_radius is None or args.output is None:
        raise SystemExit("--outer-only, --full-radius, and --output are required")
    _write_json(args.output, analyze_paths(args.outer_only, args.full_radius))


if __name__ == "__main__":
    main()
