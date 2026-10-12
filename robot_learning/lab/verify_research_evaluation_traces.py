"""Defect-sensitive laboratory checks for synchronized evaluation traces.

These checks use the production environment with controlled actions and a
controlled target.  They do not load a candidate or interpret a research
artifact.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import mujoco
import numpy as np

from robot_learning.scenario.environment import TwoJointArmReachEnv


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _snapshot_keys(snapshot: dict[str, Any]) -> None:
    expected = {
        "qpos",
        "qvel",
        "ctrl",
        "endpoint_distance",
        "contact_count",
        "contact_geom_pairs",
        "joint_limit_distance",
        "joint_limit_proximity",
        "joint_limit_active",
    }
    _require(
        set(snapshot) == expected,
        "each substep must expose the complete physical diagnostic snapshot",
    )


def _check_trace_shape(info: dict[str, Any], frame_skip: int) -> None:
    _require(
        len(info["substep_trace"]) == frame_skip,
        "one snapshot is required per mj_step",
    )
    _require(len(info["qpos"]) == 2, "post-control qpos must contain both joints")
    _require(len(info["qvel"]) == 2, "post-control qvel must contain both joints")
    _require(len(info["ctrl"]) == 2, "post-control ctrl must contain both actuators")
    _require(
        len(info["joint_limit_distance"]) == 2,
        "limit distances must be per-joint",
    )
    _require(
        len(info["joint_limit_proximity"]) == 2,
        "limit proximity must be per-joint",
    )
    _require(
        len(info["joint_limit_active"]) == 2,
        "active limits must be per-joint",
    )
    for snapshot in info["substep_trace"]:
        _snapshot_keys(snapshot)
        _require(len(snapshot["qpos"]) == 2, "substep qpos must contain both joints")
        _require(len(snapshot["qvel"]) == 2, "substep qvel must contain both joints")
        _require(len(snapshot["ctrl"]) == 2, "substep ctrl must contain both actuators")


def _put_target_at_endpoint(env: TwoJointArmReachEnv) -> None:
    endpoint = env.data.site("end_effector").xpos.copy()
    env.data.mocap_pos[0] = endpoint
    mujoco.mj_forward(env.model, env.data)


def _run_behavioral_checks() -> dict[str, Any]:
    frame_skip = 3
    env = TwoJointArmReachEnv(
        frame_skip=frame_skip,
        hold_seconds=0.04,
        max_episode_steps=20,
    )
    env.reset(seed=123)

    raw_action = np.array([2.0, -2.0], dtype=np.float64)
    _, _, _, _, saturated_info = env.step(raw_action)
    expected_clipped = np.clip(raw_action, -1.0, 1.0)
    _require(
        saturated_info["post_policy_action"] == raw_action.tolist(),
        "post-policy physical command must be recorded before clipping",
    )
    _require(
        saturated_info["clipped_action"] == expected_clipped.tolist(),
        "clipped command must match the independent [-1, 1] reference",
    )
    _require(
        saturated_info["joint_saturation"] == [True, True]
        and saturated_info["action_saturated"],
        "per-joint and aggregate saturation must identify both clipped joints",
    )
    _check_trace_shape(saturated_info, frame_skip)

    env.reset(seed=123)
    _require(
        env._last_substep_trace == [], "reset must clear the prior substep trace"
    )
    _put_target_at_endpoint(env)
    _, _, _, _, reached_info = env.step(np.zeros(2, dtype=np.float64))
    _require(
        reached_info["held_steps"] == 1,
        "controlled endpoint target must enter hold",
    )
    _require(reached_info["first_reach"], "the first tolerance entry must be marked")
    _check_trace_shape(reached_info, frame_skip)

    env.data.mocap_pos[0] = [-0.20, 0.0, float(env.data.mocap_pos[0, 2])]
    mujoco.mj_forward(env.model, env.data)
    _, _, _, _, interrupted_info = env.step(np.zeros(2, dtype=np.float64))
    _require(
        interrupted_info["held_steps"] == 0
        and interrupted_info["hold_interrupted"],
        "leaving the controlled tolerance target must interrupt the hold",
    )
    _require(
        interrupted_info["first_reach"] is False,
        "a later reacquisition is not the episode's first reach",
    )
    _check_trace_shape(interrupted_info, frame_skip)

    malformed_rejection: dict[str, str] = {}
    try:
        env.step(np.zeros((1, 2), dtype=np.float64))
    except ValueError as exc:
        malformed_rejection = {
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
    _require(
        malformed_rejection.get("error_type") == "ValueError",
        "malformed action shapes must be rejected explicitly",
    )

    return {
        "observed": {
            "raw_action": saturated_info["post_policy_action"],
            "clipped_action": saturated_info["clipped_action"],
            "joint_saturation": saturated_info["joint_saturation"],
            "frame_skip": frame_skip,
            "saturated_substep_count": len(saturated_info["substep_trace"]),
            "reached_hold": reached_info["held_steps"],
            "interrupted_hold": interrupted_info["held_steps"],
            "contact_count": interrupted_info["contact_count"],
            "joint_limit_active": interrupted_info["joint_limit_active"],
            "malformed_action_rejection": malformed_rejection,
        },
        "expected": {
            "raw_action": [2.0, -2.0],
            "clipped_action": [1.0, -1.0],
            "joint_saturation": [True, True],
            "one_substep_snapshot_per_frame_skip": frame_skip,
            "reached_hold": 1,
            "interrupted_hold": 0,
            "malformed_action_rejection": "ValueError",
        },
        "checked_scope": [
            "raw post-policy versus clipped command",
            "per-joint and aggregate saturation",
            "repeated post-mj_step snapshots",
            "post-control qpos and qvel shapes",
            "contact count and geom-pair fields",
            "joint-limit distance, proximity, and active fields",
            "reset clearing of the prior trace",
            "first reach and deliberately induced hold interruption",
            "explicit malformed action-shape rejection",
        ],
    }


def _run_compatibility_check() -> dict[str, Any]:
    """Exercise the changed production path without a candidate or artifact."""
    env = TwoJointArmReachEnv(frame_skip=2, max_episode_steps=4)
    observation, reset_info = env.reset(seed=7)
    _require(
        observation.shape == (11,), "production reset observation must remain 11D"
    )
    _require(reset_info == {}, "reset info must remain backward-compatible")
    _, reward, terminated, truncated, info = env.step(np.zeros(2, dtype=np.float64))
    _require(np.isfinite(reward), "compatibility step reward must be finite")
    _require(not terminated and not truncated, "compatibility step should not terminate")
    _check_trace_shape(info, 2)
    _require(
        info["post_policy_action"] == [0.0, 0.0]
        and info["clipped_action"] == [0.0, 0.0],
        "identity policy mapping must reach the changed diagnostic path",
    )
    return {
        "observed": {
            "observation_shape": list(observation.shape),
            "reward_finite": bool(np.isfinite(reward)),
            "substep_count": len(info["substep_trace"]),
            "diagnostic_fields": sorted(info),
        },
        "expected": {
            "observation_shape": [11],
            "reward_finite": True,
            "substep_count": 2,
            "production_path_exercised": True,
        },
        "checked_scope": [
            "artifact-independent environment reset and step",
            "unchanged observation shape and reset info",
            "finite reward and unchanged termination path",
            "post-policy/clipped action fields",
            "frame-skip trace and physical diagnostic fields",
        ],
    }


def _write_artifact(output: Path, mode: str, result: dict[str, Any]) -> None:
    artifact = {
        "check": "research_evaluation_traces",
        "mode": mode,
        **result,
        "unchecked_scope": [
            "learned-policy runtime output over a research panel",
            "evaluation artifact schema consumed by external readers",
            "scientific interpretation of contact, limit, or branch correlations",
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
