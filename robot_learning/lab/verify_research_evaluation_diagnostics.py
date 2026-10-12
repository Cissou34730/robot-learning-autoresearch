"""Laboratory checks for scenario-owned branch evaluation diagnostics.

The checks use deterministic observations rather than a trained candidate or
an evaluation artifact.  They exercise the production summarizer so that a
missing or partial branch diagnostic cannot pass by merely producing the old
episode fields.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from robot_learning.scenario.evaluation import _summarize_branch_diagnostics


def _synthetic_observation(
    open_error: tuple[float, float], folded_error: tuple[float, float]
) -> np.ndarray:
    observation = np.zeros(11, dtype=np.float32)
    observation[7:9] = open_error
    observation[9:11] = folded_error
    return observation


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _require_summary(summary: dict[str, Any]) -> None:
    expected_keys = {
        "open_branch_occupancy_steps",
        "folded_branch_occupancy_steps",
        "open_branch_occupancy_fraction",
        "folded_branch_occupancy_fraction",
        "branch_switches",
        "branch_at_first_reach",
        "branch_at_max_held_run",
        "min_open_branch_error_norm",
        "min_folded_branch_error_norm",
    }
    _require(
        set(summary) == expected_keys,
        "branch summary must contain the complete diagnostic field set",
    )

    expected = {
        "open_branch_occupancy_steps": 3,
        "folded_branch_occupancy_steps": 2,
        "open_branch_occupancy_fraction": 0.6,
        "folded_branch_occupancy_fraction": 0.4,
        "branch_switches": 2,
        "branch_at_first_reach": "folded",
        "branch_at_max_held_run": "open",
        "min_open_branch_error_norm": 0.05,
        "min_folded_branch_error_norm": 0.1,
    }
    for key, expected_value in expected.items():
        observed_value = summary[key]
        if isinstance(expected_value, float):
            _require(
                bool(np.isclose(observed_value, expected_value)),
                f"{key}: expected {expected_value}, got {observed_value}",
            )
        else:
            _require(
                observed_value == expected_value,
                f"{key}: expected {expected_value}, got {observed_value}",
            )


def _run_behavioral_checks() -> dict[str, Any]:
    observations = [
        _synthetic_observation((1.0, 0.0), (3.0, 0.0)),
        _synthetic_observation((0.5, 0.0), (2.0, 0.0)),
        _synthetic_observation((2.0, 0.0), (0.25, 0.0)),
        _synthetic_observation((3.0, 0.0), (0.1, 0.0)),
        _synthetic_observation((0.05, 0.0), (2.0, 0.0)),
    ]
    summary = _summarize_branch_diagnostics(observations, [0, 0, 2, 0, 3])
    _require_summary(summary)

    tie_summary = _summarize_branch_diagnostics(
        [_synthetic_observation((0.25, 0.0), (0.25, 0.0))], [0]
    )
    _require(
        tie_summary["open_branch_occupancy_steps"] == 1
        and tie_summary["folded_branch_occupancy_steps"] == 0,
        "equal branch norms must use the documented open-branch tie rule",
    )

    rejected_shape: dict[str, str] = {}
    try:
        _summarize_branch_diagnostics([np.zeros(10, dtype=np.float32)], [0])
    except ValueError as exc:
        rejected_shape = {"error_type": type(exc).__name__, "message": str(exc)}
    _require(
        rejected_shape.get("error_type") == "ValueError"
        and "11" in rejected_shape.get("message", ""),
        "an incompatible observation shape must be rejected explicitly",
    )

    return {
        "observed": {
            "summary": summary,
            "tie_classification": tie_summary["open_branch_occupancy_steps"],
            "incompatible_shape_rejection": rejected_shape,
        },
        "expected": {
            "summary": {
                "open_branch_occupancy_steps": 3,
                "folded_branch_occupancy_steps": 2,
                "open_branch_occupancy_fraction": 0.6,
                "folded_branch_occupancy_fraction": 0.4,
                "branch_switches": 2,
                "branch_at_first_reach": "folded",
                "branch_at_max_held_run": "open",
                "min_open_branch_error_norm": 0.05,
                "min_folded_branch_error_norm": 0.1,
            },
            "tie_classification": "open",
            "incompatible_shape_rejection": "ValueError mentioning 11 elements",
        },
        "checked_scope": [
            "open/folded norm classification",
            "occupancy steps and fractions",
            "consecutive branch-switch counting",
            "first-reach branch attribution",
            "maximum-held-run branch attribution",
            "minimum open/folded error norms",
            "explicit rejection of a non-11-element observation",
        ],
    }


def _run_compatibility_check() -> dict[str, Any]:
    """Exercise the changed production helper with controlled inputs only."""
    result = _run_behavioral_checks()
    result["checked_scope"].append(
        "artifact-independent frozen observation compatibility path"
    )
    return result


def _write_artifact(output: Path, mode: str, result: dict[str, Any]) -> None:
    artifact = {
        "check": "research_evaluation_branch_diagnostics",
        "mode": mode,
        **result,
        "unchecked_scope": [
            "trained-policy behavior",
            "MuJoCo episode execution and target sampling",
            "scientific interpretation of branch-stratified outcomes",
        ],
    }
    output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=("behavioral", "compatibility"), default="behavioral"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    result = (
        _run_compatibility_check()
        if args.mode == "compatibility"
        else _run_behavioral_checks()
    )
    _write_artifact(args.output, args.mode, result)


if __name__ == "__main__":
    main()
