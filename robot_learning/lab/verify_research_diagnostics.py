"""Executable checks for opt-in research evaluation diagnostics."""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from contracts.task_spec import (
    FRAME_SKIP,
    HOLD_SECONDS,
    MAX_EPISODE_STEPS,
    SUCCESS_THRESHOLD,
    TARGET_RADIUS_RANGE,
)
from robot_learning.scenario.environment import make_evaluation_env


DIAGNOSTIC_KEYS = {
    "internal_distance_m",
    "internal_qpos_rad",
    "internal_qvel_rad_per_s",
    "internal_applied_action",
}
CHECK_SEED = 26_1013


def _write_json(output: Path, payload: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _diagnostic_observation(
    env: Any, info: dict[str, Any], action: np.ndarray
) -> dict[str, Any]:
    if "evaluation_diagnostics" not in info:
        raise AssertionError("enabled evaluation diagnostics are missing")
    diagnostics = info["evaluation_diagnostics"]
    if set(diagnostics) != DIAGNOSTIC_KEYS:
        raise AssertionError("evaluation diagnostic keys changed or are incomplete")

    distances = np.asarray(diagnostics["internal_distance_m"])
    qpos = np.asarray(diagnostics["internal_qpos_rad"])
    qvel = np.asarray(diagnostics["internal_qvel_rad_per_s"])
    applied_action = np.asarray(diagnostics["internal_applied_action"])
    expected_action = np.repeat(
        np.clip(action, env.action_space.low, env.action_space.high)[None, :],
        env.frame_skip,
        axis=0,
    )
    shapes = {
        "distance": list(distances.shape),
        "qpos": list(qpos.shape),
        "qvel": list(qvel.shape),
        "applied_action": list(applied_action.shape),
    }
    expected_shapes = {
        "distance": [env.frame_skip],
        "qpos": [env.frame_skip, env.model.nq],
        "qvel": [env.frame_skip, env.model.nv],
        "applied_action": [env.frame_skip, env.action_space.shape[0]],
    }
    finite = all(
        bool(np.isfinite(values).all())
        for values in (distances, qpos, qvel, applied_action)
    )
    applied_action_matches = bool(np.array_equal(applied_action, expected_action))
    endpoint_matches = bool(
        np.isclose(distances[-1], float(info["distance"]))
        and np.array_equal(qpos[-1], env.data.qpos)
        and np.array_equal(qvel[-1], env.data.qvel)
    )
    if (
        shapes != expected_shapes
        or not finite
        or not applied_action_matches
        or not endpoint_matches
    ):
        raise AssertionError("evaluation diagnostic values or shapes are invalid")
    return {
        "keys": sorted(diagnostics),
        "shapes": shapes,
        "expected_shapes": expected_shapes,
        "finite": finite,
        "applied_action_matches_clipped_input": applied_action_matches,
        "last_internal_state_matches_transition": endpoint_matches,
    }


def _behavioral_check() -> dict[str, Any]:
    enabled = make_evaluation_env(evaluation_diagnostics=True)
    disabled = make_evaluation_env()
    actions = [
        np.zeros(2, dtype=np.float32),
        np.asarray([2.0, -2.0], dtype=np.float32),
        np.asarray([-0.35, 0.4], dtype=np.float32),
    ]
    transitions: list[dict[str, Any]] = []
    try:
        enabled_reset, enabled_reset_info = enabled.reset(seed=CHECK_SEED)
        disabled_reset, disabled_reset_info = disabled.reset(seed=CHECK_SEED)
        reset_match = bool(
            np.array_equal(enabled_reset, disabled_reset)
            and enabled_reset_info == disabled_reset_info == {}
        )
        if not reset_match:
            raise AssertionError("diagnostic opt-in changed reset semantics")

        for action in actions:
            enabled_obs, enabled_reward, enabled_terminated, enabled_truncated, enabled_info = (
                enabled.step(action)
            )
            disabled_obs, disabled_reward, disabled_terminated, disabled_truncated, disabled_info = (
                disabled.step(action)
            )
            diagnostic = _diagnostic_observation(enabled, enabled_info, action)
            disabled_absent = "evaluation_diagnostics" not in disabled_info
            core_match = bool(
                np.array_equal(enabled_obs, disabled_obs)
                and np.isclose(enabled_reward, disabled_reward)
                and enabled_terminated == disabled_terminated
                and enabled_truncated == disabled_truncated
                and np.isclose(enabled_info["distance"], disabled_info["distance"])
                and enabled_info["held_steps"] == disabled_info["held_steps"]
                and enabled_info["is_success"] == disabled_info["is_success"]
            )
            if not disabled_absent or not core_match:
                raise AssertionError(
                    "diagnostic opt-in changed a production transition"
                )
            transitions.append(
                {
                    "action": action.tolist(),
                    "diagnostic": diagnostic,
                    "disabled_diagnostics_absent": disabled_absent,
                    "core_transition_matches_disabled": core_match,
                    "step_count": int(enabled._step_count),
                    "termination_types": [
                        type(enabled_terminated).__name__,
                        type(enabled_truncated).__name__,
                    ],
                }
            )

        enabled_reset_after_step, enabled_reset_info_after_step = enabled.reset(
            seed=CHECK_SEED + 1
        )
        disabled_reset_after_step, disabled_reset_info_after_step = disabled.reset(
            seed=CHECK_SEED + 1
        )
        reset_transition = {
            "observations_match": bool(
                np.array_equal(enabled_reset_after_step, disabled_reset_after_step)
            ),
            "info_has_no_diagnostics": bool(
                "evaluation_diagnostics" not in enabled_reset_info_after_step
                and "evaluation_diagnostics" not in disabled_reset_info_after_step
            ),
            "step_count_after_reset": int(enabled._step_count),
            "held_steps_after_reset": int(enabled._held_steps),
        }
        if not (
            reset_transition["observations_match"]
            and reset_transition["info_has_no_diagnostics"]
            and reset_transition["step_count_after_reset"] == 0
            and reset_transition["held_steps_after_reset"] == 0
        ):
            raise AssertionError("reset transition semantics changed")

        expected_hold_steps = round(
            HOLD_SECONDS / (enabled.model.opt.timestep * FRAME_SKIP)
        )
        semantics = {
            "target_radius_range": tuple(
                float(value) for value in enabled.target_radius_range
            ),
            "frame_skip": int(enabled.frame_skip),
            "max_episode_steps": int(enabled.max_episode_steps),
            "success_threshold": float(enabled.success_threshold),
            "hold_steps_required": int(enabled.hold_steps_required),
            "expected_hold_steps": expected_hold_steps,
        }
        semantics_match = (
            semantics["target_radius_range"] == TARGET_RADIUS_RANGE
            and semantics["frame_skip"] == FRAME_SKIP
            and semantics["max_episode_steps"] == MAX_EPISODE_STEPS
            and semantics["success_threshold"] == SUCCESS_THRESHOLD
            and semantics["hold_steps_required"] == expected_hold_steps
        )
        if not semantics_match:
            raise AssertionError("evaluation task mechanics changed")
        return {
            "schema_version": 1,
            "mode": "behavioral_check",
            "status": "passed",
            "observed": {
                "reset_match_before_steps": reset_match,
                "transitions": transitions,
                "reset_transition": reset_transition,
                "task_semantics": semantics,
            },
            "expected": {
                "diagnostic_keys": sorted(DIAGNOSTIC_KEYS),
                "one_row_per_internal_step": True,
                "disabled_info_omits_diagnostics": True,
                "enabled_and_disabled_core_transitions_match": True,
                "reset_clears_step_and_hold_counters": True,
                "task_semantics_unchanged": True,
            },
            "checked_scope": [
                "evaluation environment construction with diagnostics enabled and disabled",
                "repeated controlled transitions including clipped-action input",
                "diagnostic key set, shapes, finiteness, and endpoint state correspondence",
                "absence of diagnostics when opt-in is disabled",
                "paired reset and transition semantics",
                "fixed evaluation target distribution, timing, threshold, and hold duration",
            ],
            "unchecked_scope": [
                "learned-policy evaluation and episode-level aggregate values",
                "long-horizon hold behavior and target-panel coverage",
                "scientific interpretation or validity of the recorded diagnostics",
            ],
        }
    finally:
        enabled.close()
        disabled.close()


def _compatibility_check() -> dict[str, Any]:
    env = make_evaluation_env(evaluation_diagnostics=True)
    try:
        observation, reset_info = env.reset(seed=CHECK_SEED)
        next_observation, reward, terminated, truncated, info = env.step(
            np.asarray([0.25, -0.5], dtype=np.float32)
        )
        diagnostic = _diagnostic_observation(
            env, info, np.asarray([0.25, -0.5], dtype=np.float32)
        )
        observed = {
            "reset_observation_finite": bool(np.isfinite(observation).all()),
            "reset_info": reset_info,
            "step_observation_finite": bool(np.isfinite(next_observation).all()),
            "reward_finite": bool(np.isfinite(reward)),
            "termination_types": [
                type(terminated).__name__,
                type(truncated).__name__,
            ],
            "diagnostic": diagnostic,
        }
        expected = {
            "reset_and_step_complete": True,
            "finite_observations_and_reward": True,
            "termination_types": ["bool", "bool"],
            "production_diagnostic_path": True,
        }
        passed = (
            observed["reset_observation_finite"]
            and observed["reset_info"] == {}
            and observed["step_observation_finite"]
            and observed["reward_finite"]
            and observed["termination_types"] == ["bool", "bool"]
        )
        if not passed:
            raise AssertionError("research diagnostics compatibility check failed")
        return {
            "schema_version": 1,
            "mode": "compatibility_check",
            "status": "passed",
            "observed": observed,
            "expected": expected,
            "checked_scope": [
                "evaluation factory construction with the opt-in flag",
                "one reset and one controlled production transition",
                "native diagnostic arrays and transition outputs",
            ],
            "unchecked_scope": [
                "paired disabled-environment transition equivalence",
                "repeated resets and long-horizon episode aggregation",
                "learned-policy behavior and scientific interpretation",
            ],
        }
    finally:
        env.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("check", "compatibility"), default="check")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = (
            _behavioral_check()
            if args.mode == "check"
            else _compatibility_check()
        )
    except Exception as error:
        _write_json(
            args.output,
            {
                "schema_version": 1,
                "mode": f"{args.mode}_check",
                "status": "failed",
                "error_type": type(error).__name__,
                "error": str(error),
                "unchecked_scope": [
                    "checks after the first failed production-path operation"
                ],
            },
        )
        raise
    _write_json(args.output, payload)


if __name__ == "__main__":
    main()
