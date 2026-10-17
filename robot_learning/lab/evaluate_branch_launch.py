"""Run a matched, non-official branch-aware launch comparison.

The intervention in this module is a research candidate only.  It is applied
by the research evaluator, not by the saved policy runtime or any official
evaluator, and this artifact makes no causal or official-performance claim.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from robot_learning.lab.analyze_evaluation import analyze_evaluation
from robot_learning.scenario.evaluation import evaluate_research_model


OBSERVATION_SIZE = 11
ACTION_SIZE = 2
LAUNCH_CONTROL_STEPS = 20

INTERVENTION_PARAMETERS = {
    "observation_size": OBSERVATION_SIZE,
    "action_size": ACTION_SIZE,
    "branch_selection": {
        "open_observation_slice": [7, 9],
        "folded_observation_slice": [9, 11],
        "error_metric": "Euclidean norm of the two-dimensional joint-error pair",
        "tie_break": "open",
    },
    "residual": {
        "formula": (
            "tanh(0.75 * branch_joint_error - 0.05 * joint_velocity)"
        ),
        "branch_error_gain": 0.75,
        "velocity_gain": -0.05,
        "branch_joint_error_source": {
            "open": "observation[7:9]",
            "folded": "observation[9:11]",
        },
        "joint_velocity_source": "observation[2:4]",
        "bounded_by": "tanh",
    },
    "launch_window": {
        "first_visible_control_step": 1,
        "last_visible_control_step": LAUNCH_CONTROL_STEPS,
        "after_last_step": "return the deterministic policy action unchanged",
    },
    "action_mix": {
        "policy_weight": 0.80,
        "residual_weight": 0.20,
        "formula": "clip(0.80 * policy_action + 0.20 * residual, -1, 1)",
        "clip_lower": -1.0,
        "clip_upper": 1.0,
    },
    "branch_lock": "selected at reset and fixed for the episode",
}


def _validated_vector(
    value: Any, *, name: str, expected_size: int
) -> np.ndarray:
    try:
        vector = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as error:
        raise RuntimeError(
            f"branch launch intervention received an invalid {name}; "
            f"expected a finite one-dimensional vector with {expected_size} "
            "elements"
        ) from error
    if vector.ndim != 1 or vector.size != expected_size:
        raise RuntimeError(
            f"branch launch intervention received an invalid {name}; "
            f"expected a finite one-dimensional vector with {expected_size} "
            "elements"
        )
    if not np.all(np.isfinite(vector)):
        raise RuntimeError(
            f"branch launch intervention received non-finite values in {name}"
        )
    return vector.copy()


class BranchLaunchIntervention:
    """Lock the closer reset IK branch and blend its early residual."""

    def __init__(self) -> None:
        self.selected_branch_counts = {"open": 0, "folded": 0}
        self._selected_branch: str | None = None

    def reset(self, observation: np.ndarray, info: dict[str, Any]) -> None:
        if not isinstance(info, dict):
            raise RuntimeError(
                "branch launch intervention received malformed reset info; "
                "expected a dictionary"
            )
        observation = _validated_vector(
            observation,
            name="reset observation",
            expected_size=OBSERVATION_SIZE,
        )
        open_error = float(np.linalg.norm(observation[7:9]))
        folded_error = float(np.linalg.norm(observation[9:11]))
        # <= makes the open branch deterministic on an exact tie.
        self._selected_branch = (
            "open" if open_error <= folded_error else "folded"
        )
        self.selected_branch_counts[self._selected_branch] += 1

    def intervene(
        self,
        action: np.ndarray,
        observation: np.ndarray,
        control_step: int,
    ) -> np.ndarray:
        policy_action = _validated_vector(
            action, name="policy action", expected_size=ACTION_SIZE
        )
        observation = _validated_vector(
            observation,
            name="current observation",
            expected_size=OBSERVATION_SIZE,
        )
        if (
            isinstance(control_step, bool)
            or not isinstance(control_step, (int, np.integer))
            or control_step < 1
        ):
            raise RuntimeError(
                "branch launch intervention received an invalid control step; "
                "expected a positive one-based integer"
            )
        if self._selected_branch is None:
            raise RuntimeError(
                "branch launch intervention was used before episode reset"
            )

        if control_step <= LAUNCH_CONTROL_STEPS:
            branch_error = (
                observation[7:9]
                if self._selected_branch == "open"
                else observation[9:11]
            )
            joint_velocity = observation[2:4]
            residual = np.tanh(
                0.75 * branch_error - 0.05 * joint_velocity
            )
            return np.clip(
                0.80 * policy_action + 0.20 * residual,
                -1.0,
                1.0,
            )
        return policy_action


def _episode_rows(
    evaluation: dict[str, Any], field: str, label: str
) -> list[dict[str, Any]]:
    rows = evaluation.get(field)
    if not isinstance(rows, list):
        raise RuntimeError(
            f"{label} research evaluation has no list-valued {field}"
        )
    return rows


def _check_matched_panel(
    baseline: dict[str, Any], candidate: dict[str, Any]
) -> list[dict[str, Any]]:
    if baseline.get("episodes") != candidate.get("episodes"):
        raise RuntimeError(
            "baseline and candidate evaluation panels have different episode "
            "counts"
        )
    if baseline.get("seed") != candidate.get("seed"):
        raise RuntimeError(
            "baseline and candidate evaluation panels have different seeds"
        )

    baseline_results = _episode_rows(
        baseline, "episode_results", "baseline"
    )
    candidate_results = _episode_rows(
        candidate, "episode_results", "candidate"
    )
    baseline_diagnostics = _episode_rows(
        baseline["research_evidence"],
        "episode_diagnostics",
        "baseline research evidence",
    )
    candidate_diagnostics = _episode_rows(
        candidate["research_evidence"],
        "episode_diagnostics",
        "candidate research evidence",
    )
    if not (
        len(baseline_results)
        == len(candidate_results)
        == len(baseline_diagnostics)
        == len(candidate_diagnostics)
        == baseline.get("episodes")
    ):
        raise RuntimeError(
            "baseline and candidate evaluation panels have inconsistent "
            "episode rows"
        )

    paired: list[dict[str, Any]] = []
    for index, (
        baseline_result,
        candidate_result,
        baseline_diagnostic,
        candidate_diagnostic,
    ) in enumerate(
        zip(
            baseline_results,
            candidate_results,
            baseline_diagnostics,
            candidate_diagnostics,
            strict=True,
        )
    ):
        for field in ("episode", "episode_seed"):
            if baseline_result.get(field) != candidate_result.get(field):
                raise RuntimeError(
                    f"baseline and candidate {field} values differ at "
                    f"episode row {index}"
                )
            if baseline_diagnostic.get(field) != candidate_diagnostic.get(
                field
            ):
                raise RuntimeError(
                    f"baseline and candidate diagnostic {field} values differ "
                    f"at episode row {index}"
                )
            if baseline_result.get(field) != baseline_diagnostic.get(field):
                raise RuntimeError(
                    f"baseline result and diagnostic {field} values differ "
                    f"at episode row {index}"
                )
            if candidate_result.get(field) != candidate_diagnostic.get(field):
                raise RuntimeError(
                    f"candidate result and diagnostic {field} values differ "
                    f"at episode row {index}"
                )
        for field in ("target_radius_cm", "target_angle_degrees"):
            baseline_value = baseline_diagnostic.get(field)
            candidate_value = candidate_diagnostic.get(field)
            if (
                not isinstance(baseline_value, (int, float))
                or isinstance(baseline_value, bool)
                or not isinstance(candidate_value, (int, float))
                or isinstance(candidate_value, bool)
                or not math.isfinite(float(baseline_value))
                or not math.isfinite(float(candidate_value))
                or float(baseline_value) != float(candidate_value)
            ):
                raise RuntimeError(
                    "baseline and candidate target radius/angle panels do "
                    f"not match for {field} at episode row {index}"
                )

        baseline_success = baseline_result.get("success")
        candidate_success = candidate_result.get("success")
        if not isinstance(baseline_success, bool) or not isinstance(
            candidate_success, bool
        ):
            raise RuntimeError(
                f"baseline/candidate success is malformed at episode row "
                f"{index}"
            )
        paired.append(
            {
                "episode": baseline_result["episode"],
                "episode_seed": baseline_result["episode_seed"],
                "target_radius_cm": float(
                    baseline_diagnostic["target_radius_cm"]
                ),
                "target_angle_degrees": float(
                    baseline_diagnostic["target_angle_degrees"]
                ),
                "baseline_success": baseline_success,
                "candidate_success": candidate_success,
                "candidate_minus_baseline_success": int(candidate_success)
                - int(baseline_success),
            }
        )
    return paired


def _paired_summary(paired: list[dict[str, Any]]) -> dict[str, int]:
    improved = sum(
        1
        for row in paired
        if not row["baseline_success"] and row["candidate_success"]
    )
    regressed = sum(
        1
        for row in paired
        if row["baseline_success"] and not row["candidate_success"]
    )
    unchanged = len(paired) - improved - regressed
    return {
        "episodes": len(paired),
        "baseline_successes": sum(row["baseline_success"] for row in paired),
        "candidate_successes": sum(
            row["candidate_success"] for row in paired
        ),
        "improved_episode_count": improved,
        "regressed_episode_count": regressed,
        "unchanged_episode_count": unchanged,
        "candidate_minus_baseline_success_count": improved - regressed,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a non-official branch-aware launch comparison"
    )
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--episodes", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--algorithm", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    intervention = BranchLaunchIntervention()
    baseline = evaluate_research_model(
        args.model,
        episodes=args.episodes,
        seed=args.seed,
        algorithm=args.algorithm,
    )
    candidate = evaluate_research_model(
        args.model,
        episodes=args.episodes,
        seed=args.seed,
        algorithm=args.algorithm,
        action_intervention=intervention,
    )
    paired = _check_matched_panel(baseline, candidate)
    artifact = {
        "artifact_type": "non_official_research_comparison",
        "inquiry": "I3",
        "official_assessment": False,
        "causal_claim": False,
        "official_performance_claim": False,
        "interpretation": (
            "Matched mechanism/candidate comparison only; this artifact is "
            "not an official assessment and does not establish causality."
        ),
        "model": str(args.model),
        "episodes": args.episodes,
        "seed": args.seed,
        "algorithm": args.algorithm,
        "intervention": {
            "name": "branch_aware_launch_residual",
            "parameters": INTERVENTION_PARAMETERS,
            "selected_branch_counts": intervention.selected_branch_counts,
        },
        "baseline": {
            "evaluation": baseline,
            "analysis": analyze_evaluation(
                baseline, f"{args.model} [unchanged baseline]"
            ),
        },
        "candidate": {
            "evaluation": candidate,
            "analysis": analyze_evaluation(
                candidate, f"{args.model} [branch launch candidate]"
            ),
        },
        "paired_outcome_comparison": {
            "panel_match": {
                "episode_seed": True,
                "target_radius_cm": True,
                "target_angle_degrees": True,
            },
            "summary": _paired_summary(paired),
            "episodes": paired,
        },
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(artifact, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
