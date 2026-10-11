"""Laboratory check for observational evaluation diagnostics.

This module is intentionally independent of the research evaluator.  It
replays the same seeded resets and clipped actions in matched diagnostic and
normal environments, then checks task equivalence and the internal sampling
invariant.  It writes a JSON result and raises on a failed check.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from robot_learning.scenario.environment import TwoJointArmReachEnv


def _assert_equal(left: Any, right: Any, path: str) -> None:
    if isinstance(left, dict) or isinstance(right, dict):
        if not isinstance(left, dict) or not isinstance(right, dict):
            raise AssertionError(f"{path}: task values have different types")
        if set(left) != set(right):
            raise AssertionError(f"{path}: task keys differ")
        for key in left:
            _assert_equal(left[key], right[key], f"{path}.{key}")
        return
    if isinstance(left, np.ndarray) or isinstance(right, np.ndarray):
        if not isinstance(left, np.ndarray) or not isinstance(right, np.ndarray):
            raise AssertionError(f"{path}: task values have different types")
        if left.shape != right.shape or not np.array_equal(left, right):
            raise AssertionError(f"{path}: task arrays differ")
        return
    if isinstance(left, (float, np.floating)) or isinstance(
        right, (float, np.floating)
    ):
        if not np.isclose(left, right, rtol=0.0, atol=1e-12):
            raise AssertionError(f"{path}: task scalars differ")
        return
    if left != right:
        raise AssertionError(f"{path}: task values differ")


def _run_check() -> dict[str, Any]:
    # A short horizon guarantees a transition to truncation while retaining
    # enough repeated updates to check the per-control-step trace grouping.
    normal = TwoJointArmReachEnv(max_episode_steps=6)
    diagnostic = TwoJointArmReachEnv(max_episode_steps=6, diagnostic_mode=True)
    if normal.diagnostic_mode:
        raise AssertionError("diagnostic mode is not disabled by default")
    action_sequence = [
        np.array([0.25, -0.4], dtype=np.float32),
        np.array([2.0, -2.0], dtype=np.float32),
        np.array([-0.75, 0.15], dtype=np.float32),
        np.array([0.0, 0.0], dtype=np.float32),
        np.array([1.0, 1.0], dtype=np.float32),
        np.array([-1.0, 0.5], dtype=np.float32),
    ]
    seeds = (7, 23, 101)
    task_fields = (
        "distance",
        "is_success",
        "held_steps",
        "reward_components",
    )
    required_trace_fields = {
        "control_step",
        "internal_step",
        "distance",
        "qvel",
        "contact_count",
        "action_magnitude",
    }
    episodes_checked = 0
    control_steps_checked = 0
    internal_samples_checked = 0
    reset_trace_lengths: list[int] = []

    for seed in seeds:
        normal_obs, normal_reset_info = normal.reset(seed=seed)
        diagnostic_obs, diagnostic_reset_info = diagnostic.reset(seed=seed)
        _assert_equal(normal_obs, diagnostic_obs, "reset.observation")
        _assert_equal(normal_reset_info, diagnostic_reset_info, "reset.info")
        _assert_equal(
            normal.data.mocap_pos.copy(),
            diagnostic.data.mocap_pos.copy(),
            "reset.target",
        )
        if normal.diagnostic_trace:
            raise AssertionError("normal mode unexpectedly recorded diagnostics")
        if diagnostic.diagnostic_trace:
            raise AssertionError("diagnostic trace was not cleared on reset")
        reset_trace_lengths.append(len(diagnostic.diagnostic_trace))

        steps = 0
        terminated = truncated = False
        for action in action_sequence:
            normal_result = normal.step(action)
            diagnostic_result = diagnostic.step(action)
            for index, (normal_value, diagnostic_value) in enumerate(
                zip(normal_result[:4], diagnostic_result[:4])
            ):
                _assert_equal(
                    normal_value,
                    diagnostic_value,
                    f"episode{episodes_checked}.step{steps + 1}.result{index}",
                )
            _assert_equal(
                normal_result[4],
                diagnostic_result[4],
                f"episode{episodes_checked}.step{steps + 1}.info",
            )
            if set(normal_result[4]) != set(task_fields):
                raise AssertionError("unexpected change to environment task fields")
            if any(
                normal_result[4][field] != diagnostic_result[4][field]
                for field in task_fields
            ):
                raise AssertionError("diagnostic mode changed a task field")
            steps += 1
            terminated, truncated = normal_result[2], normal_result[3]
            if terminated or truncated:
                break

        if not truncated or terminated or steps != len(action_sequence):
            raise AssertionError("matched transition did not reach the test truncation")
        expected_samples = steps * diagnostic.frame_skip
        trace = diagnostic.diagnostic_trace
        if len(trace) != expected_samples:
            raise AssertionError(
                f"expected {expected_samples} internal samples, got {len(trace)}"
            )
        for index, sample in enumerate(trace):
            if not required_trace_fields <= set(sample):
                raise AssertionError("internal sample is missing a required field")
            expected_control_step = index // diagnostic.frame_skip + 1
            expected_internal_step = index % diagnostic.frame_skip + 1
            if sample["control_step"] != expected_control_step:
                raise AssertionError("internal samples have incorrect control grouping")
            if sample["internal_step"] != expected_internal_step:
                raise AssertionError("internal samples have incorrect local order")
            if (
                not np.isfinite(sample["distance"])
                or sample["distance"] < 0.0
                or np.asarray(sample["qvel"]).shape != (2,)
                or not np.all(np.isfinite(sample["qvel"]))
                or sample["contact_count"] < 0
                or not np.isfinite(sample["action_magnitude"])
            ):
                raise AssertionError("internal sample contains an invalid measurement")

        episodes_checked += 1
        control_steps_checked += steps
        internal_samples_checked += len(trace)

        # A new matched reset must discard the prior episode's trace.
        normal.reset(seed=seed + 1000)
        diagnostic.reset(seed=seed + 1000)
        if diagnostic.diagnostic_trace:
            raise AssertionError("diagnostic trace was not reset between episodes")
        reset_trace_lengths.append(len(diagnostic.diagnostic_trace))

    return {
        "episodes_checked": episodes_checked,
        "control_steps_checked": control_steps_checked,
        "internal_samples_checked": internal_samples_checked,
        "frame_skip_observed": diagnostic.frame_skip,
        "reset_trace_lengths": reset_trace_lengths,
        "task_fields_compared": list(task_fields),
        "trace_fields_checked": sorted(required_trace_fields),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    artifact: dict[str, Any] = {
        "check": "matched normal/diagnostic environment replay",
        "checked_scope": [
            "seeded reset equivalence",
            "repeated clipped-action transitions",
            "diagnostic trace cardinality and ordering",
            "diagnostic trace reset behavior",
        ],
        "unchecked_scope": [
            "full evaluation-panel aggregation",
            "policy quality or scientific validity",
            "protected evaluator semantics",
        ],
        "expected": {
            "diagnostic_mode_default": False,
            "internal_samples_per_control_step": 10,
            "normal_trace_length": 0,
            "trace_cleared_on_reset": True,
            "task_behavior_match": True,
        },
    }
    try:
        observed = _run_check()
    except Exception as error:
        artifact.update(
            {
                "passed": False,
                "observed": {"error": str(error)},
            }
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
        raise
    artifact.update(
        {
            "passed": True,
            "observed": observed,
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
