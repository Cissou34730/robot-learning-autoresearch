"""Compare radius-band diagnostics from two completed research evaluations.

This is a post-processing analysis only.  It reads evaluation JSON artifacts,
joins the task outcomes to the researcher-owned episode diagnostics by episode,
and writes a compact JSON report.  It never constructs an environment or
loads a candidate policy.

The ``--compatibility`` mode is an artifact-independent production-path check
for the Runner's module invocation.  It uses a small in-memory fixture and
exercises argument normalization, episode joining, metric calculation, delta
calculation, and JSON publication without claiming to validate a real
evaluation artifact.  Real analysis additionally requires the accepted
Runner binding identities through ``--*-operation-id`` and
``--*-artifact-index``.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any, Iterable


INNER_RADIUS_LIMIT_CM = 14.0


def _normalise_argv(argv: Iterable[str] | str | None) -> list[str]:
    """Accept ordinary argv tokens and Runner's single-string argv form."""
    if argv is None:
        values = list(sys.argv[1:])
    elif isinstance(argv, str):
        values = [argv]
    else:
        values = list(argv)

    if len(values) == 1 and any(
        option in values[0]
        for option in (
            "--candidate",
            "--reference",
            "--candidate-operation-id",
            "--candidate-artifact-index",
            "--reference-operation-id",
            "--reference-artifact-index",
            "--artifact",
            "--compatibility",
        )
    ):
        # ``posix=True`` treats Windows backslashes as escapes.  The Runner
        # can supply canonical Windows paths in its single-string form, so
        # retain those backslashes while removing ordinary shell quotes.
        tokens = shlex.split(values[0], posix=False)
        return [
            token[1:-1]
            if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'"
            else token
            for token in tokens
        ]
    return values


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare full-radius research-evaluation diagnostics."
    )
    parser.add_argument("--candidate")
    parser.add_argument("--reference")
    parser.add_argument(
        "--candidate-operation-id",
        help="operation identity for the bound candidate artifact",
    )
    parser.add_argument(
        "--candidate-artifact-index",
        type=_nonnegative_int,
        help="artifact index for the bound candidate artifact",
    )
    parser.add_argument(
        "--reference-operation-id",
        help="operation identity for the bound reference artifact",
    )
    parser.add_argument(
        "--reference-artifact-index",
        type=_nonnegative_int,
        help="artifact index for the bound reference artifact",
    )
    parser.add_argument("--artifact")
    parser.add_argument(
        "--compatibility",
        action="store_true",
        help="run the artifact-independent module compatibility check",
    )
    return parser


def _nonnegative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def _require_mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be a JSON object")
    return value


def _rows_by_episode(rows: Any, context: str) -> dict[Any, dict[str, Any]]:
    if not isinstance(rows, list):
        raise ValueError(f"{context} must be a JSON array")
    indexed: dict[Any, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        row = _require_mapping(row, f"{context}[{index}]")
        if "episode" not in row:
            raise ValueError(f"{context}[{index}] is missing episode")
        episode = row["episode"]
        try:
            hash(episode)
        except TypeError as exc:
            raise ValueError(f"{context}[{index}].episode must be scalar") from exc
        if episode in indexed:
            raise ValueError(f"{context} contains duplicate episode {episode!r}")
        indexed[episode] = row
    return indexed


def _evaluation_rows(evaluation: Any, label: str) -> list[dict[str, Any]]:
    evaluation = _require_mapping(evaluation, label)
    results = _rows_by_episode(evaluation.get("episode_results"), f"{label}.episode_results")
    evidence = _require_mapping(
        evaluation.get("research_evidence"), f"{label}.research_evidence"
    )
    diagnostics = _rows_by_episode(
        evidence.get("episode_diagnostics"),
        f"{label}.research_evidence.episode_diagnostics",
    )
    if set(results) != set(diagnostics):
        missing_diagnostics = sorted(set(results) - set(diagnostics), key=repr)
        missing_results = sorted(set(diagnostics) - set(results), key=repr)
        raise ValueError(
            f"{label} episode join mismatch: "
            f"missing diagnostics={missing_diagnostics!r}, "
            f"missing results={missing_results!r}"
        )
    # Preserve the episode-result order while still joining by episode rather
    # than relying on the two arrays having the same physical ordering.
    return [
        {"result": result, "diagnostic": diagnostics[episode]}
        for episode, result in results.items()
    ]


def _episode_seed_panel(
    rows: list[dict[str, Any]], label: str
) -> set[int]:
    """Validate the seed identity on both sides of one artifact's episode join."""
    seeds: set[int] = set()
    for index, joined in enumerate(rows):
        result = joined["result"]
        diagnostic = joined["diagnostic"]
        if "episode_seed" not in result:
            raise ValueError(
                f"{label} episode join row {index} is missing "
                "episode_results.episode_seed"
            )
        if "episode_seed" not in diagnostic:
            raise ValueError(
                f"{label} episode join row {index} is missing "
                "episode_diagnostics.episode_seed"
            )
        result_seed = result["episode_seed"]
        diagnostic_seed = diagnostic["episode_seed"]
        if (
            isinstance(result_seed, bool)
            or not isinstance(result_seed, int)
            or isinstance(diagnostic_seed, bool)
            or not isinstance(diagnostic_seed, int)
        ):
            raise ValueError(
                f"{label} episode join row {index} has a non-integer episode_seed"
            )
        if result_seed != diagnostic_seed:
            raise ValueError(
                f"{label} episode {result.get('episode')!r} has mismatched "
                f"episode_seed values: outcome={result_seed!r}, "
                f"diagnostic={diagnostic_seed!r}"
            )
        if result_seed in seeds:
            raise ValueError(
                f"{label} has duplicate episode_seed {result_seed!r}"
            )
        seeds.add(result_seed)
    return seeds


def _matching_episode_seed_panel(
    candidate_rows: list[dict[str, Any]],
    reference_rows: list[dict[str, Any]],
) -> None:
    candidate_seeds = _episode_seed_panel(candidate_rows, "candidate")
    reference_seeds = _episode_seed_panel(reference_rows, "reference")
    if candidate_seeds != reference_seeds:
        missing_from_reference = sorted(candidate_seeds - reference_seeds)
        missing_from_candidate = sorted(reference_seeds - candidate_seeds)
        raise ValueError(
            "candidate and reference episode_seed panels do not match one-to-one: "
            f"missing from reference={missing_from_reference!r}, "
            f"missing from candidate={missing_from_candidate!r}"
        )


def _as_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"{field} must be finite")
    return number


def _episode_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    successes = 0
    no_entry = 0
    entered_but_incomplete = 0
    failed_with_hold_interruptions = 0
    hold_interruptions_among_failures = 0
    bands: dict[str, list[dict[str, Any]]] = {"inner": [], "outer": []}

    for joined in rows:
        result = joined["result"]
        diagnostic = joined["diagnostic"]
        if not isinstance(result.get("success"), bool):
            raise ValueError("episode_results.success must be boolean")
        if "first_reach_step" not in diagnostic:
            raise ValueError("episode_diagnostics is missing first_reach_step")
        if "target_radius_cm" not in diagnostic:
            raise ValueError("episode_diagnostics is missing target_radius_cm")
        if "hold_interruptions" not in diagnostic:
            raise ValueError("episode_diagnostics is missing hold_interruptions")

        success = result["success"]
        first_reach_step = diagnostic["first_reach_step"]
        radius_cm = _as_number(
            diagnostic["target_radius_cm"], "episode_diagnostics.target_radius_cm"
        )
        interruptions = _as_number(
            diagnostic["hold_interruptions"],
            "episode_diagnostics.hold_interruptions",
        )
        if interruptions < 0 or not interruptions.is_integer():
            raise ValueError(
                "episode_diagnostics.hold_interruptions must be a non-negative integer"
            )
        if first_reach_step is None:
            no_entry += 1
        elif not success:
            entered_but_incomplete += 1
        if success:
            successes += 1
        elif interruptions:
            failed_with_hold_interruptions += 1
            hold_interruptions_among_failures += int(interruptions)

        band = "inner" if radius_cm < INNER_RADIUS_LIMIT_CM else "outer"
        bands[band].append(joined)

    def counts(subset: list[dict[str, Any]]) -> dict[str, Any]:
        subset_total = len(subset)
        subset_successes = sum(
            bool(joined["result"]["success"]) for joined in subset
        )
        subset_no_entry = sum(
            joined["diagnostic"]["first_reach_step"] is None for joined in subset
        )
        subset_entered_incomplete = sum(
            joined["diagnostic"]["first_reach_step"] is not None
            and not joined["result"]["success"]
            for joined in subset
        )
        subset_failed_interruptions = sum(
            not joined["result"]["success"]
            and bool(joined["diagnostic"]["hold_interruptions"])
            for joined in subset
        )
        subset_interruptions = sum(
            int(joined["diagnostic"]["hold_interruptions"])
            for joined in subset
            if not joined["result"]["success"]
        )
        return _metric_record(
            total=subset_total,
            successes=subset_successes,
            no_entry=subset_no_entry,
            entered_but_incomplete=subset_entered_incomplete,
            failed_with_hold_interruptions=subset_failed_interruptions,
            hold_interruptions_among_failures=subset_interruptions,
        )

    overall = _metric_record(
        total=total,
        successes=successes,
        no_entry=no_entry,
        entered_but_incomplete=entered_but_incomplete,
        failed_with_hold_interruptions=failed_with_hold_interruptions,
        hold_interruptions_among_failures=hold_interruptions_among_failures,
    )
    return {
        "overall": overall,
        "bands": {name: counts(items) for name, items in bands.items()},
    }


def _metric_record(
    *,
    total: int,
    successes: int,
    no_entry: int,
    entered_but_incomplete: int,
    failed_with_hold_interruptions: int,
    hold_interruptions_among_failures: int,
) -> dict[str, Any]:
    return {
        "total": total,
        "successes": successes,
        "success_percent": 100.0 * successes / total if total else None,
        "no_entry": no_entry,
        "entered_but_incomplete": entered_but_incomplete,
        # Under the evaluation contract, success is the complete uninterrupted
        # hold, so this explicit field is equal to successes by definition.
        "complete_hold_successes": successes,
        "failed_with_hold_interruptions": failed_with_hold_interruptions,
        "hold_interruptions_among_failures": hold_interruptions_among_failures,
    }


def _metric_delta(candidate: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    delta: dict[str, Any] = {}
    for key in candidate:
        candidate_value = candidate[key]
        reference_value = reference[key]
        if candidate_value is None or reference_value is None:
            delta[key] = None
        else:
            delta[key] = candidate_value - reference_value
    return delta


def _paired_deltas(
    candidate: dict[str, Any], reference: dict[str, Any]
) -> dict[str, Any]:
    return {
        "overall": _metric_delta(candidate["overall"], reference["overall"]),
        "bands": {
            band: _metric_delta(
                candidate["bands"][band], reference["bands"][band]
            )
            for band in ("inner", "outer")
        },
    }


def _source_identity(
    path: Path,
    operation_id: str,
    artifact_index: int,
) -> dict[str, Any]:
    """Record the identities supplied by the accepted Runner input binding."""
    if not isinstance(operation_id, str) or not operation_id:
        raise ValueError("source operation_id must be a non-empty string")
    if (
        isinstance(artifact_index, bool)
        or not isinstance(artifact_index, int)
        or artifact_index < 0
    ):
        raise ValueError("source artifact_index must be a non-negative integer")
    return {
        "path": str(path),
        "operation_id": operation_id,
        "artifact_index": artifact_index,
    }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except OSError as exc:
        raise ValueError(f"could not read JSON artifact {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON artifact {path}: {exc}") from exc
    return _require_mapping(value, f"artifact {path}")


def analyze(
    candidate_path: Path,
    reference_path: Path,
    *,
    candidate_operation_id: str,
    candidate_artifact_index: int,
    reference_operation_id: str,
    reference_artifact_index: int,
) -> dict[str, Any]:
    """Build the comparison report from two completed evaluation artifacts."""
    candidate_evaluation = _load_json(candidate_path)
    reference_evaluation = _load_json(reference_path)
    candidate_rows = _evaluation_rows(candidate_evaluation, "candidate")
    reference_rows = _evaluation_rows(reference_evaluation, "reference")
    _matching_episode_seed_panel(candidate_rows, reference_rows)
    candidate_metrics = _episode_metrics(candidate_rows)
    reference_metrics = _episode_metrics(reference_rows)
    return {
        "schema_version": 1,
        "analysis": "full_radius_comparison",
        "radius_bands_cm": {
            "inner": "<14",
            "outer": ">=14",
        },
        "candidate": {
            "source": _source_identity(
                candidate_path,
                candidate_operation_id,
                candidate_artifact_index,
            ),
            "metrics": candidate_metrics,
        },
        "reference": {
            "source": _source_identity(
                reference_path,
                reference_operation_id,
                reference_artifact_index,
            ),
            "metrics": reference_metrics,
        },
        "paired_deltas": _paired_deltas(candidate_metrics, reference_metrics),
    }


def _compatibility_fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a deterministic fixture for the module's compatibility mode."""
    candidate = {
        "episode_results": [
            {"episode": 0, "episode_seed": 5200, "success": True},
            {"episode": 1, "episode_seed": 5201, "success": False},
            {"episode": 2, "episode_seed": 5202, "success": False},
        ],
        "research_evidence": {
            "episode_diagnostics": [
                {"episode": 0, "episode_seed": 5200, "target_radius_cm": 13.9, "first_reach_step": 4, "hold_interruptions": 0},
                {"episode": 1, "episode_seed": 5201, "target_radius_cm": 14.0, "first_reach_step": None, "hold_interruptions": 0},
                {"episode": 2, "episode_seed": 5202, "target_radius_cm": 18.0, "first_reach_step": 7, "hold_interruptions": 2},
            ]
        },
    }
    reference = {
        "episode_results": [
            {"episode": 0, "episode_seed": 5200, "success": False},
            {"episode": 1, "episode_seed": 5201, "success": True},
            {"episode": 2, "episode_seed": 5202, "success": False},
        ],
        "research_evidence": {
            "episode_diagnostics": [
                {"episode": 0, "episode_seed": 5200, "target_radius_cm": 13.9, "first_reach_step": None, "hold_interruptions": 0},
                {"episode": 1, "episode_seed": 5201, "target_radius_cm": 14.0, "first_reach_step": 5, "hold_interruptions": 0},
                {"episode": 2, "episode_seed": 5202, "target_radius_cm": 18.0, "first_reach_step": 6, "hold_interruptions": 1},
            ]
        },
    }
    return candidate, reference


def _compatibility_report() -> dict[str, Any]:
    candidate, reference = _compatibility_fixture()
    candidate_rows = _evaluation_rows(candidate, "fixture_candidate")
    reference_rows = _evaluation_rows(reference, "fixture_reference")
    _matching_episode_seed_panel(candidate_rows, reference_rows)
    candidate_metrics = _episode_metrics(candidate_rows)
    reference_metrics = _episode_metrics(reference_rows)
    expected_candidate_inner = candidate_metrics["bands"]["inner"]
    expected_candidate_outer = candidate_metrics["bands"]["outer"]
    checks = {
        "single_string_argv_normalization": _normalise_argv(
            "--compatibility --artifact compatibility.json"
        )
        == ["--compatibility", "--artifact", "compatibility.json"],
        "ordinary_argv_normalization": _normalise_argv(
            ["--compatibility", "--artifact", "compatibility.json"]
        )
        == ["--compatibility", "--artifact", "compatibility.json"],
        "episode_join_and_radius_boundary": (
            expected_candidate_inner["total"] == 1
            and expected_candidate_outer["total"] == 2
            and expected_candidate_outer["no_entry"] == 1
        ),
        "complete_hold_and_interruption_metrics": (
            candidate_metrics["overall"]["complete_hold_successes"] == 1
            and candidate_metrics["bands"]["outer"]["entered_but_incomplete"] == 1
            and candidate_metrics["overall"]["hold_interruptions_among_failures"] == 2
        ),
        "paired_delta_calculation": (
            _paired_deltas(candidate_metrics, reference_metrics)["overall"]["successes"]
            == 0
        ),
        "paired_panel_verification": (
            set(
                row["result"]["episode_seed"]
                for row in candidate_rows
            )
            == {5200, 5201, 5202}
        ),
    }
    mismatched_rows = reference_rows[:-1]
    try:
        _matching_episode_seed_panel(candidate_rows, mismatched_rows)
    except ValueError as exc:
        checks["mismatched_panel_rejected"] = (
            "episode_seed panels do not match one-to-one" in str(exc)
        )
    else:
        checks["mismatched_panel_rejected"] = False
    checks["provenance_serialization"] = _source_identity(
        Path("candidate.json"), "M5", 0
    ) == {
        "path": "candidate.json",
        "operation_id": "M5",
        "artifact_index": 0,
    }
    if not all(checks.values()):
        raise RuntimeError(f"compatibility checks failed: {checks}")
    return {
        "schema_version": 1,
        "analysis": "full_radius_comparison",
        "mode": "compatibility",
        "artifact_independent": True,
        "checks": checks,
        "note": (
            "Synthetic in-memory fixture only; this does not validate a real "
            "evaluation artifact or Runner artifact identity."
        ),
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def main(argv: Iterable[str] | str | None = None) -> int:
    args = _parser().parse_args(_normalise_argv(argv))
    if not args.artifact:
        raise SystemExit("--artifact is required")
    output_path = Path(args.artifact)
    if args.compatibility:
        _write_json(output_path, _compatibility_report())
        return 0
    required_real_args = {
        "--candidate": args.candidate,
        "--reference": args.reference,
        "--candidate-operation-id": args.candidate_operation_id,
        "--candidate-artifact-index": args.candidate_artifact_index,
        "--reference-operation-id": args.reference_operation_id,
        "--reference-artifact-index": args.reference_artifact_index,
    }
    missing = [name for name, value in required_real_args.items() if value is None]
    if missing:
        raise SystemExit(
            "real analysis requires bound provenance arguments: "
            + ", ".join(missing)
        )
    report = analyze(
        Path(args.candidate),
        Path(args.reference),
        candidate_operation_id=args.candidate_operation_id,
        candidate_artifact_index=args.candidate_artifact_index,
        reference_operation_id=args.reference_operation_id,
        reference_artifact_index=args.reference_artifact_index,
    )
    _write_json(output_path, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
