"""Focused, artifact-independent checks for research evaluation diagnostics.

The normal mode exercises the production environment's internal trace and the
numeric diagnostic helpers.  ``--compatibility`` exercises the same
``make_evaluation_env`` production path used by evaluation without loading a
model or requiring a saved artifact.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from contracts.task_spec import FRAME_SKIP, SUCCESS_THRESHOLD
from robot_learning.scenario.environment import make_evaluation_env
from robot_learning.scenario.evaluation import (
    _accumulate_hold_window_diagnostics,
    _build_episode_diagnostics,
    _empty_hold_window_diagnostics,
    minimum_joint_limit_margin,
    nearest_target_ik_branch,
    target_ik_branch_diagnostics,
)


def _assert_close(actual: float, expected: float, *, label: str) -> None:
    if not np.isclose(actual, expected):
        raise AssertionError(f"{label}: expected {expected}, got {actual}")


def _controlled_numeric_checks() -> dict:
    joint_ranges = np.asarray([[-np.pi, np.pi], [-2.0, 2.0]], dtype=np.float64)
    target = np.asarray([0.12, 0.0, 0.3], dtype=np.float64)
    branches = target_ik_branch_diagnostics(target, joint_ranges)
    if set(branches) != {"open", "folded"}:
        raise AssertionError("both target IK branch labels must be present")
    if any(branch is None for branch in branches.values()):
        raise AssertionError("the controlled reachable target must have two branches")

    margin = minimum_joint_limit_margin(
        np.asarray([0.5, -0.25], dtype=np.float64), joint_ranges
    )
    _assert_close(margin, min(np.pi - 0.5, 2.0 - 0.25), label="joint margin")
    nearest = nearest_target_ik_branch(
        branches, np.asarray(branches["open"]["joint_angles_rad"], dtype=np.float64)
    )
    if nearest is None or nearest["branch"] != "open":
        raise AssertionError("the exact open solution must be the nearest branch")
    _assert_close(
        nearest["configuration_distance_rad"], 0.0, label="nearest branch distance"
    )

    no_entry = _build_episode_diagnostics(
        episode=0,
        episode_seed=17,
        target_position=target,
        target_ik_branches=branches,
        min_distance_cm=12.0,
        final_distance_cm=13.0,
        first_reach_step=None,
        max_held_steps=0,
        in_tolerance_steps=0,
        hold_interruptions=0,
        min_joint_limit_margin_rad=0.75,
        max_joint_speed_norm_rad_per_s=1.5,
        max_absolute_action=0.4,
        max_internal_substep_distance_cm=13.0,
        max_internal_substep_distance_above_threshold_cm=13.0,
        internal_substeps_above_threshold=FRAME_SKIP,
        hold_window_control_steps=0,
        hold_window_max_joint_speed_norm_rad_per_s=None,
        hold_window_max_absolute_action=None,
        hold_window_max_internal_substep_distance_cm=None,
        hold_window_max_internal_substep_distance_above_threshold_cm=None,
        hold_window_internal_substeps_above_threshold=0,
        nearest_branch_at_first_entry=None,
    )
    if no_entry["nearest_target_ik_branch_at_first_entry"] is not None:
        raise AssertionError("missing first entry must produce an explicit null")
    if no_entry["internal_substeps_above_threshold"] != FRAME_SKIP:
        raise AssertionError("substep count must remain an integer diagnostic")
    if no_entry["max_internal_substep_distance_above_threshold_cm"] != 13.0:
        raise AssertionError("the maximum above-threshold distance was not retained")
    for field in (
        "hold_window_max_joint_speed_norm_rad_per_s",
        "hold_window_max_absolute_action",
        "hold_window_max_internal_substep_distance_cm",
        "hold_window_max_internal_substep_distance_above_threshold_cm",
    ):
        if no_entry[field] is not None:
            raise AssertionError(f"no-entry {field} must be null")
    if no_entry["hold_window_control_steps"] != 0:
        raise AssertionError("no-entry hold-window steps must be zero")
    if no_entry["hold_window_internal_substeps_above_threshold"] != 0:
        raise AssertionError("no-entry hold-window substep count must be zero")

    hold_window = _empty_hold_window_diagnostics()
    _accumulate_hold_window_diagnostics(
        hold_window,
        previous_held_steps=0,
        held_steps=0,
        joint_speed_norm_rad_per_s=9.0,
        absolute_action=0.9,
        substep_distances=np.asarray([0.03], dtype=np.float64),
    )
    if any(
        hold_window[field] is not None
        for field in (
            "hold_window_max_joint_speed_norm_rad_per_s",
            "hold_window_max_absolute_action",
            "hold_window_max_internal_substep_distance_cm",
            "hold_window_max_internal_substep_distance_above_threshold_cm",
        )
    ):
        raise AssertionError("no-entry accumulation must leave maxima null")
    if (
        hold_window["hold_window_control_steps"] != 0
        or hold_window["hold_window_internal_substeps_above_threshold"] != 0
    ):
        raise AssertionError("no-entry accumulation must leave counts at zero")
    _accumulate_hold_window_diagnostics(
        hold_window,
        previous_held_steps=0,
        held_steps=1,
        joint_speed_norm_rad_per_s=1.5,
        absolute_action=0.2,
        substep_distances=np.asarray([0.005, 0.012], dtype=np.float64),
    )
    _accumulate_hold_window_diagnostics(
        hold_window,
        previous_held_steps=1,
        held_steps=2,
        joint_speed_norm_rad_per_s=2.0,
        absolute_action=0.4,
        substep_distances=np.asarray([0.02], dtype=np.float64),
    )
    _accumulate_hold_window_diagnostics(
        hold_window,
        previous_held_steps=2,
        held_steps=0,
        joint_speed_norm_rad_per_s=3.0,
        absolute_action=0.6,
        substep_distances=np.asarray([0.03], dtype=np.float64),
    )
    if hold_window["hold_window_control_steps"] != 3:
        raise AssertionError("hold entry, continuation, and exit must be included")
    _assert_close(
        hold_window["hold_window_max_joint_speed_norm_rad_per_s"],
        3.0,
        label="hold-window maximum speed",
    )
    _assert_close(
        hold_window["hold_window_max_absolute_action"],
        0.6,
        label="hold-window maximum action",
    )
    _assert_close(
        hold_window["hold_window_max_internal_substep_distance_cm"],
        3.0,
        label="hold-window maximum substep distance",
    )
    _assert_close(
        hold_window["hold_window_max_internal_substep_distance_above_threshold_cm"],
        3.0,
        label="hold-window maximum above-threshold distance",
    )
    if hold_window["hold_window_internal_substeps_above_threshold"] != 3:
        raise AssertionError("hold-window above-threshold substeps were not counted")
    return {
        "branches_checked": sorted(branches),
        "nearest_branch": nearest["branch"],
        "null_first_entry_checked": True,
        "no_entry_hold_window_null_zero_checked": True,
        "hold_window_boundary_steps_checked": 3,
        "threshold_m": SUCCESS_THRESHOLD,
    }


def _environment_trace_check() -> dict:
    env = make_evaluation_env()
    try:
        env.reset(seed=123)
        env.step(np.zeros(env.action_space.shape, dtype=np.float32))
        trace = list(env.last_substep_distances)
        if len(trace) != FRAME_SKIP:
            raise AssertionError(
                f"expected {FRAME_SKIP} substep distances, got {len(trace)}"
            )
        if not all(np.isfinite(trace)):
            raise AssertionError("substep distances must be finite")
        return {
            "frame_skip": FRAME_SKIP,
            "trace_entries": len(trace),
            "info_path": "environment.step -> last_substep_distances",
        }
    finally:
        env.close()


def _compatibility_check() -> dict:
    """Check the evaluator-compatible production path without an artifact."""
    env = make_evaluation_env()
    try:
        observation, _ = env.reset(seed=321)
        if observation.shape != env.observation_space.shape:
            raise AssertionError("production evaluation observation shape changed")
        observation, reward, terminated, truncated, info = env.step(
            np.zeros(env.action_space.shape, dtype=np.float32)
        )
        if observation.shape != env.observation_space.shape:
            raise AssertionError("production evaluation step shape changed")
        if not np.isfinite(reward) or terminated or truncated:
            raise AssertionError("single compatibility step changed unexpectedly")
        if "distance" not in info or len(env.last_substep_distances) != FRAME_SKIP:
            raise AssertionError("production evaluation diagnostics are not reachable")
        return {
            "production_path": "make_evaluation_env -> reset -> step",
            "substep_trace_entries": len(env.last_substep_distances),
            "distance_info_present": True,
        }
    finally:
        env.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--compatibility", action="store_true")
    args = parser.parse_args()

    if args.compatibility:
        checks = {"compatibility": _compatibility_check()}
    else:
        checks = {
            "environment_trace": _environment_trace_check(),
            "controlled_numeric": _controlled_numeric_checks(),
        }
    args.artifact.write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
