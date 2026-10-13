"""Executable checks for evaluation diagnostics.

This is a laboratory regression check, not a policy evaluation.  It uses
known kinematic targets, controlled traces, and a short controlled evaluator
run to test the diagnostic plumbing without requiring a saved model.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from robot_learning.scenario import evaluation
from robot_learning.scenario.environment import TwoJointArmReachEnv


def _assert_finite_json(value: Any, path: str = "artifact") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_finite_json(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_finite_json(item, f"{path}[{index}]")
    elif isinstance(value, float) and not np.isfinite(value):
        raise AssertionError(f"non-finite JSON value at {path}")


def _check_branch_classifications(model) -> dict[str, dict[str, Any]]:
    targets = {
        "both": np.array([0.15, 0.0, 0.02], dtype=np.float64),
        "open_only": np.array(
            [0.218 * np.cos(np.deg2rad(175.0)), 0.218 * np.sin(np.deg2rad(175.0)), 0.02],
            dtype=np.float64,
        ),
        "folded_only": np.array(
            [0.218 * np.cos(np.deg2rad(-175.0)), 0.218 * np.sin(np.deg2rad(-175.0)), 0.02],
            dtype=np.float64,
        ),
        "none": np.array([0.23, 0.0, 0.02], dtype=np.float64),
    }
    expected = {
        "both": (True, True),
        "open_only": (True, False),
        "folded_only": (False, True),
        "none": (False, False),
    }
    observed: dict[str, dict[str, Any]] = {}
    for expected_union, target in targets.items():
        result = evaluation.classify_target_ik_branches(model, target)
        expected_open, expected_folded = expected[expected_union]
        actual = (
            bool(result["open_legal"]),
            bool(result["folded_legal"]),
            str(result["union"]),
        )
        wanted = (expected_open, expected_folded, expected_union)
        if actual != wanted:
            raise AssertionError(
                f"IK classification mismatch for {expected_union}: "
                f"observed={actual}, expected={wanted}"
            )
        observed[expected_union] = dict(result)
    return observed


def _check_control_summaries() -> dict[str, dict[str, Any]]:
    quiet = evaluation.summarize_applied_controls(
        [np.zeros(2), np.zeros(2)],
        [np.zeros(2), np.zeros(2)],
    )
    active = evaluation.summarize_applied_controls(
        [np.array([1.0, -1.0]), np.array([0.5, 0.0])],
        [np.array([0.3, -0.4]), np.array([1.0, -2.0])],
    )
    if quiet["applied_action_saturation_steps"] != 0:
        raise AssertionError("zero controls were reported as saturated")
    if active["applied_action_saturation_steps"] != 1:
        raise AssertionError("saturation summary did not count the controlled step")
    if not (
        active["applied_action_magnitude_max"]
        > quiet["applied_action_magnitude_max"]
    ):
        raise AssertionError("action magnitude summary did not change")
    if not (
        active["joint_velocity_magnitude_max"]
        > quiet["joint_velocity_magnitude_max"]
    ):
        raise AssertionError("joint velocity summary did not change")
    return {"quiet": quiet, "active": active}


def _compatibility_run() -> dict[str, Any]:
    """Exercise the evaluator with a real environment and controlled runtime."""

    environment = TwoJointArmReachEnv(max_episode_steps=2)

    class ControlledRuntime:
        observation_space = environment.observation_space
        io = environment.policy_io

        def __init__(self) -> None:
            self.calls = 0

        def reset(self) -> None:
            self.calls = 0

        def predict(self, observation: np.ndarray) -> np.ndarray:
            del observation
            self.calls += 1
            return np.array([2.0, -2.0]) if self.calls == 1 else np.zeros(2)

    runtime = ControlledRuntime()
    original_load_runtime = evaluation.load_runtime
    original_make_environment = evaluation.make_evaluation_env
    evaluation.load_runtime = lambda model_path, algorithm: runtime
    evaluation.make_evaluation_env = lambda policy_runtime: environment
    try:
        result = evaluation.evaluate_research_model(
            Path("controlled-runtime"),
            episodes=2,
            seed=17,
        )
    finally:
        evaluation.load_runtime = original_load_runtime
        evaluation.make_evaluation_env = original_make_environment

    diagnostics = result["research_evidence"]["episode_diagnostics"]
    if len(diagnostics) != 2:
        raise AssertionError("controlled evaluator did not preserve episode resets")
    for item in diagnostics:
        required_fields = {
            "ik_open_legal",
            "ik_folded_legal",
            "ik_branch_classification",
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
        }
        if not required_fields.issubset(item):
            raise AssertionError("controlled evaluator omitted diagnostic fields")
        _assert_finite_json(item, "episode_diagnostics")
        if item["applied_action_saturation_steps"] != 1:
            raise AssertionError("evaluator did not record post-clipped saturation")
        if not np.isclose(
            item["applied_action_magnitude_max"], np.sqrt(2.0)
        ):
            raise AssertionError("evaluator recorded the pre-clipped action")
        if item["control_steps_recorded"] != 2:
            raise AssertionError("evaluator recorded the wrong number of steps")
        if item["ik_branch_classification"] not in {
            "both",
            "open_only",
            "folded_only",
            "none",
        }:
            raise AssertionError("evaluator emitted an invalid IK classification")
    return {
        "episode_count": len(diagnostics),
        "diagnostics": diagnostics,
        "checked": {
            "repeated_resets": True,
            "post_clipped_controls": True,
            "velocity_summary": True,
            "geometry_fields": True,
        },
    }


def run_check(*, compatibility: bool) -> dict[str, Any]:
    if compatibility:
        observed = _compatibility_run()
        checked_scope = [
            "TwoJointArmReachEnv reset and step transitions",
            "evaluate_research_model controlled runtime path",
            "post-clipped action saturation and velocity diagnostics",
            "JSON-native episode diagnostic fields",
        ]
    else:
        environment = TwoJointArmReachEnv(max_episode_steps=2)
        environment.reset(seed=3)
        branches = _check_branch_classifications(environment.model)
        summaries = _check_control_summaries()
        environment.reset(seed=4)
        environment.step(np.array([2.0, -2.0]))
        applied_control = np.array(environment.data.ctrl, dtype=np.float64)
        if not np.array_equal(applied_control, np.array([1.0, -1.0])):
            raise AssertionError("environment did not expose post-clipped controls")
        if not np.all(np.isfinite(environment.data.qvel)):
            raise AssertionError("environment produced non-finite joint velocity")
        observed = {
            "branch_classifications": branches,
            "controlled_summaries": summaries,
            "applied_control_after_clipping": applied_control.tolist(),
            "joint_velocity_after_step": environment.data.qvel.tolist(),
        }
        checked_scope = [
            "compiled joint-limit IK branch union classifications",
            "controlled action magnitude and saturation summaries",
            "controlled joint velocity summaries",
            "repeated environment reset and post-clipped control state",
        ]

    artifact = {
        "schema": "evaluation_diagnostics_check_v1",
        "compatibility_mode": compatibility,
        "observed": observed,
        "expected": {
            "branch_union_labels": ["both", "open_only", "folded_only", "none"],
            "saturated_controls_are_at_unit_bounds": True,
            "diagnostic_values_are_finite": True,
        },
        "checked_scope": checked_scope,
        "unchecked_scope": [
            "saved policy runtime loading and model-specific behavior",
            "full evaluation-panel success or scientific validity",
            "within-frame-skip trajectories and physical causation",
        ],
    }
    _assert_finite_json(artifact)
    return artifact


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="JSON artifact path")
    parser.add_argument(
        "--compatibility",
        action="store_true",
        help="run the artifact-independent production-path compatibility check",
    )
    args = parser.parse_args(argv)
    artifact = run_check(compatibility=args.compatibility)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
