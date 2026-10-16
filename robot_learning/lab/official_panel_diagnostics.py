"""Compare two research-evaluation artifacts by target geometry and failure class.

The module deliberately only consumes the JSON written by
``evaluate_research_model``.  It does not rerun an evaluation or infer values
for fields that are absent from an artifact.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


RADIUS_BINS = (
    ("[6,10)", 6.0, 10.0),
    ("[10,14)", 10.0, 14.0),
    ("[14,18)", 14.0, 18.0),
    ("[18,20.000001)", 18.0, 20.000001),
)
ANGLE_BINS = (
    ("[-180,-90)", -180.0, -90.0),
    ("[-90,0)", -90.0, 0.0),
    ("[0,90)", 0.0, 90.0),
    ("[90,180.000001)", 90.0, 180.000001),
)

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
    "min_distance_cm",
    "final_distance_cm",
    "first_reach_step",
    "max_held_steps",
    "in_tolerance_steps",
    "hold_interruptions",
)


class ArtifactError(ValueError):
    """An input artifact does not satisfy the evaluation-artifact contract."""


def _context(label: str, field: str) -> str:
    return f"{label}: {field}"


def _require_mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ArtifactError(f"{where} must be a JSON object")
    return value


def _require_list(value: Any, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise ArtifactError(f"{where} must be a JSON array")
    return value


def _required(mapping: dict[str, Any], field: str, where: str) -> Any:
    if field not in mapping:
        raise ArtifactError(f"{where} is missing required field {field!r}")
    return mapping[field]


def _integer(value: Any, where: str, *, nonnegative: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ArtifactError(f"{where} must be an integer")
    if nonnegative and value < 0:
        raise ArtifactError(f"{where} must be non-negative")
    return value


def _number(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ArtifactError(f"{where} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ArtifactError(f"{where} must be finite")
    return result


def _boolean(value: Any, where: str) -> bool:
    if not isinstance(value, bool):
        raise ArtifactError(f"{where} must be a boolean")
    return value


def _nonempty_string(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise ArtifactError(f"{where} must be a non-empty string")
    return value


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant {value!r}")


def _load_artifact(path: Path, label: str) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            artifact = json.load(handle, parse_constant=_reject_json_constant)
    except FileNotFoundError as exc:
        raise ArtifactError(f"{label} input does not exist: {path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ArtifactError(f"{label} input cannot be read as JSON: {path}: {exc}") from exc

    data = _require_mapping(artifact, label)
    _integer(_required(data, "schema_version", label), _context(label, "schema_version"))
    _nonempty_string(_required(data, "model", label), _context(label, "model"))
    episodes = _integer(
        _required(data, "episodes", label),
        _context(label, "episodes"),
        nonnegative=False,
    )
    if episodes < 1:
        raise ArtifactError(f"{label}: episodes must be positive")
    seed = _integer(
        _required(data, "seed", label),
        _context(label, "seed"),
        nonnegative=True,
    )
    _boolean(_required(data, "official_benchmark", label), _context(label, "official_benchmark"))
    if data["official_benchmark"]:
        raise ArtifactError(f"{label}: official_benchmark must be false for a research artifact")

    results = _require_list(_required(data, "episode_results", label), f"{label}.episode_results")
    if len(results) != episodes:
        raise ArtifactError(
            f"{label}: episodes={episodes} but episode_results has length {len(results)}"
        )
    evidence = _require_mapping(
        _required(data, "research_evidence", label), f"{label}.research_evidence"
    )
    units = _require_mapping(
        _required(evidence, "units", f"{label}.research_evidence"),
        f"{label}.research_evidence.units",
    )
    if _required(units, "distance", f"{label}.research_evidence.units") != "cm":
        raise ArtifactError(f"{label}: diagnostic distance unit must be 'cm'")
    if _required(units, "time", f"{label}.research_evidence.units") != "control_steps":
        raise ArtifactError(f"{label}: diagnostic time unit must be 'control_steps'")
    diagnostics = _require_list(
        _required(evidence, "episode_diagnostics", f"{label}.research_evidence"),
        f"{label}.research_evidence.episode_diagnostics",
    )
    if len(diagnostics) != episodes:
        raise ArtifactError(
            f"{label}: episodes={episodes} but episode_diagnostics has length {len(diagnostics)}"
        )

    expected_ids = set(range(episodes))
    result_ids: set[int] = set()
    diagnostic_ids: set[int] = set()
    parsed_results: dict[int, dict[str, Any]] = {}
    parsed_diagnostics: dict[int, dict[str, Any]] = {}

    for index, raw_result in enumerate(results):
        result = _require_mapping(raw_result, f"{label}.episode_results[{index}]")
        for field in _RESULT_FIELDS:
            _required(result, field, f"{label}.episode_results[{index}]")
        episode_id = _integer(
            result["episode"],
            f"{label}.episode_results[{index}].episode",
            nonnegative=True,
        )
        if episode_id in result_ids:
            raise ArtifactError(f"{label}: duplicate episode ID {episode_id} in episode_results")
        result_ids.add(episode_id)
        _integer(
            result["episode_seed"],
            f"{label}.episode_results[{index}].episode_seed",
            nonnegative=True,
        )
        _boolean(result["success"], f"{label}.episode_results[{index}].success")
        _number(result["reward_total"], f"{label}.episode_results[{index}].reward_total")
        steps = _integer(
            result["steps"],
            f"{label}.episode_results[{index}].steps",
            nonnegative=True,
        )
        if steps < 1:
            raise ArtifactError(f"{label}.episode_results[{index}].steps must be positive")
        _boolean(result["terminated"], f"{label}.episode_results[{index}].terminated")
        _boolean(result["truncated"], f"{label}.episode_results[{index}].truncated")
        parsed_results[episode_id] = result

    for index, raw_diagnostic in enumerate(diagnostics):
        diagnostic = _require_mapping(raw_diagnostic, f"{label}.episode_diagnostics[{index}]")
        for field in _DIAGNOSTIC_FIELDS:
            _required(diagnostic, field, f"{label}.episode_diagnostics[{index}]")
        episode_id = _integer(
            diagnostic["episode"],
            f"{label}.episode_diagnostics[{index}].episode",
            nonnegative=True,
        )
        if episode_id in diagnostic_ids:
            raise ArtifactError(
                f"{label}: duplicate episode ID {episode_id} in episode_diagnostics"
            )
        diagnostic_ids.add(episode_id)
        _integer(
            diagnostic["episode_seed"],
            f"{label}.episode_diagnostics[{index}].episode_seed",
            nonnegative=True,
        )
        _number(
            diagnostic["target_radius_cm"],
            f"{label}.episode_diagnostics[{index}].target_radius_cm",
        )
        _number(
            diagnostic["target_angle_degrees"],
            f"{label}.episode_diagnostics[{index}].target_angle_degrees",
        )
        _number(
            diagnostic["min_distance_cm"],
            f"{label}.episode_diagnostics[{index}].min_distance_cm",
        )
        _number(
            diagnostic["final_distance_cm"],
            f"{label}.episode_diagnostics[{index}].final_distance_cm",
        )
        first_reach_step = diagnostic["first_reach_step"]
        if first_reach_step is not None:
            first_reach_step = _integer(
                first_reach_step,
                f"{label}.episode_diagnostics[{index}].first_reach_step",
                nonnegative=True,
            )
            if first_reach_step < 1:
                raise ArtifactError(
                    f"{label}.episode_diagnostics[{index}].first_reach_step must be positive"
                )
        max_held_steps = _integer(
            diagnostic["max_held_steps"],
            f"{label}.episode_diagnostics[{index}].max_held_steps",
            nonnegative=True,
        )
        if (first_reach_step is None) != (max_held_steps == 0):
            raise ArtifactError(
                f"{label}.episode_diagnostics[{index}] has inconsistent "
                "first_reach_step and max_held_steps"
            )
        for field in ("in_tolerance_steps", "hold_interruptions"):
            _integer(
                diagnostic[field],
                f"{label}.episode_diagnostics[{index}].{field}",
                nonnegative=True,
            )
        parsed_diagnostics[episode_id] = diagnostic

    if result_ids != expected_ids:
        raise ArtifactError(f"{label}: episode_results IDs must be exactly 0 through {episodes - 1}")
    if diagnostic_ids != expected_ids:
        raise ArtifactError(
            f"{label}: episode_diagnostics IDs must be exactly 0 through {episodes - 1}"
        )

    for episode_id in range(episodes):
        result = parsed_results[episode_id]
        diagnostic = parsed_diagnostics[episode_id]
        if result["episode_seed"] != diagnostic["episode_seed"]:
            raise ArtifactError(
                f"{label}: episode {episode_id} has inconsistent result and diagnostic seeds"
            )
        if result["episode_seed"] != seed + episode_id:
            raise ArtifactError(
                f"{label}: episode {episode_id} seed {result['episode_seed']} "
                f"does not follow artifact seed {seed}"
            )
        first_reach_step = diagnostic["first_reach_step"]
        if first_reach_step is not None and first_reach_step > result["steps"]:
            raise ArtifactError(
                f"{label}: episode {episode_id} first_reach_step exceeds episode steps"
            )
        if result["success"] and first_reach_step is None:
            raise ArtifactError(
                f"{label}: episode {episode_id} succeeds but first_reach_step is null"
            )

    successes = sum(bool(item["success"]) for item in parsed_results.values())
    recorded_percent = _number(_required(data, "success_percent", label), f"{label}.success_percent")
    expected_percent = 100.0 * successes / episodes
    if not math.isclose(recorded_percent, expected_percent, rel_tol=0.0, abs_tol=1e-9):
        raise ArtifactError(
            f"{label}: success_percent={recorded_percent} does not match "
            f"{expected_percent} from episode_results"
        )

    return {
        "model": data["model"],
        "seed": seed,
        "episodes": episodes,
        "results": parsed_results,
        "diagnostics": parsed_diagnostics,
    }


def _bin_for(value: float, bins: tuple[tuple[str, float, float], ...], where: str) -> str:
    for label, lower, upper in bins:
        if lower <= value < upper:
            return label
    raise ArtifactError(f"{where}={value} is outside the configured analysis bins")


def _empty_stratum(label: str) -> dict[str, Any]:
    return {
        "bin": label,
        "episodes": 0,
        "successes": 0,
        "success_percent": None,
        "never_reached": 0,
        "reached_but_failed_hold": 0,
        "mean_first_reach_step": None,
    }


def _strata(artifact: dict[str, Any], bins: tuple[tuple[str, float, float], ...], field: str) -> list[dict[str, Any]]:
    strata = {label: _empty_stratum(label) for label, _, _ in bins}
    first_reach_values: dict[str, list[int]] = {label: [] for label, _, _ in bins}
    for episode_id, result in artifact["results"].items():
        diagnostic = artifact["diagnostics"][episode_id]
        label = _bin_for(
            float(diagnostic[field]),
            bins,
            f"episode {episode_id} {field}",
        )
        row = strata[label]
        row["episodes"] += 1
        if result["success"]:
            row["successes"] += 1
        else:
            if diagnostic["first_reach_step"] is None:
                row["never_reached"] += 1
            else:
                row["reached_but_failed_hold"] += 1
        if diagnostic["first_reach_step"] is not None:
            first_reach_values[label].append(diagnostic["first_reach_step"])

    for label, _, _ in bins:
        row = strata[label]
        if row["episodes"]:
            row["success_percent"] = 100.0 * row["successes"] / row["episodes"]
        values = first_reach_values[label]
        if values:
            row["mean_first_reach_step"] = sum(values) / len(values)
    return [strata[label] for label, _, _ in bins]


def _candidate_report(artifact: dict[str, Any]) -> dict[str, Any]:
    episodes = artifact["episodes"]
    successes = sum(bool(item["success"]) for item in artifact["results"].values())
    never_reached = 0
    reached_but_failed_hold = 0
    for episode_id, result in artifact["results"].items():
        first_reach_step = artifact["diagnostics"][episode_id]["first_reach_step"]
        if not result["success"]:
            if first_reach_step is None:
                never_reached += 1
            else:
                reached_but_failed_hold += 1

    return {
        "model": artifact["model"],
        "seed": artifact["seed"],
        "overall": {
            "episodes": episodes,
            "successes": successes,
            "success_percent": 100.0 * successes / episodes,
        },
        "radius_bins": _strata(artifact, RADIUS_BINS, "target_radius_cm"),
        "angle_bins": _strata(artifact, ANGLE_BINS, "target_angle_degrees"),
        "failure_classes": {
            "never_reached": never_reached,
            "reached_but_failed_hold": reached_but_failed_hold,
        },
    }


def _paired_report(candidate_a: dict[str, Any], candidate_b: dict[str, Any]) -> list[dict[str, Any]]:
    if candidate_a["seed"] != candidate_b["seed"]:
        raise ArtifactError(
            f"paired artifacts must use the same seed ({candidate_a['seed']} != {candidate_b['seed']})"
        )
    if candidate_a["episodes"] != candidate_b["episodes"]:
        raise ArtifactError(
            "paired artifacts must have the same episode count "
            f"({candidate_a['episodes']} != {candidate_b['episodes']})"
        )

    rows = {label: _empty_stratum(label) for label, _, _ in RADIUS_BINS}
    for episode_id in range(candidate_a["episodes"]):
        result_a = candidate_a["results"][episode_id]
        result_b = candidate_b["results"][episode_id]
        diagnostic_a = candidate_a["diagnostics"][episode_id]
        diagnostic_b = candidate_b["diagnostics"][episode_id]
        if result_a["episode_seed"] != result_b["episode_seed"]:
            raise ArtifactError(f"paired episode {episode_id} has different episode seeds")
        for field in ("target_radius_cm", "target_angle_degrees"):
            if not math.isclose(
                diagnostic_a[field],
                diagnostic_b[field],
                rel_tol=0.0,
                abs_tol=1e-9,
            ):
                raise ArtifactError(f"paired episode {episode_id} has different {field} values")

        label = _bin_for(
            float(diagnostic_a["target_radius_cm"]),
            RADIUS_BINS,
            f"paired episode {episode_id} target_radius_cm",
        )
        row = rows[label]
        row["episodes"] += 1
        success_a = bool(result_a["success"])
        success_b = bool(result_b["success"])
        if success_a and not success_b:
            row["candidate_a_wins"] = row.get("candidate_a_wins", 0) + 1
        elif success_b and not success_a:
            row["candidate_b_wins"] = row.get("candidate_b_wins", 0) + 1
        else:
            row["ties"] = row.get("ties", 0) + 1

    report: list[dict[str, Any]] = []
    for label, _, _ in RADIUS_BINS:
        row = rows[label]
        candidate_a_wins = row.get("candidate_a_wins", 0)
        candidate_b_wins = row.get("candidate_b_wins", 0)
        report.append(
            {
                "bin": label,
                "episodes": row["episodes"],
                "candidate_a_wins": candidate_a_wins,
                "candidate_b_wins": candidate_b_wins,
                "ties": row.get("ties", 0),
                "discordant_episodes": candidate_a_wins + candidate_b_wins,
            }
        )
    return report


def build_report(candidate_a: dict[str, Any], candidate_b: dict[str, Any]) -> dict[str, Any]:
    """Build the deterministic comparison report from two validated artifacts."""
    return {
        "analysis_schema_version": 1,
        "candidate_a": _candidate_report(candidate_a),
        "candidate_b": _candidate_report(candidate_b),
        "paired_by_radius_bin": _paired_report(candidate_a, candidate_b),
    }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    parent = path.parent
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(
                report,
                handle,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    except (OSError, TypeError, ValueError) as exc:
        raise ArtifactError(f"output path cannot be written: {path}: {exc}") from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except OSError:
                pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare two research-evaluation artifacts by target geometry."
    )
    parser.add_argument("--candidate-a", required=True, type=Path)
    parser.add_argument("--candidate-b", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    candidate_a_path = args.candidate_a
    candidate_b_path = args.candidate_b
    output_path = args.output
    try:
        resolved_output = output_path.resolve()
        if resolved_output == candidate_a_path.resolve() or resolved_output == candidate_b_path.resolve():
            raise ArtifactError("output path must differ from both input artifact paths")
        candidate_a = _load_artifact(candidate_a_path, "candidate-a")
        candidate_b = _load_artifact(candidate_b_path, "candidate-b")
        report = build_report(candidate_a, candidate_b)
        _write_report(output_path, report)
    except (ArtifactError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
