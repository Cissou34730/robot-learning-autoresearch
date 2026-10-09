"""Measure learned-policy failure geometry and joint-space dynamics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from contracts.policy_runtime import load_runtime
from contracts.robots.two_joint_arm import (
    FOREARM_LENGTH,
    UPPER_ARM_LENGTH,
)
from contracts.task_spec import TARGET_RADIUS_RANGE
from robot_learning.scenario.environment import make_evaluation_env

JOINT_LIMIT_RAD = float(np.deg2rad(170.0))
HOLD_STEPS_REQUIRED = 100


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _ik_solutions(target: np.ndarray) -> list[dict]:
    target_x, target_y = float(target[0]), float(target[1])
    target_angle = float(np.arctan2(target_y, target_x))
    radius_squared = target_x**2 + target_y**2
    elbow_open = float(
        np.arccos(
            np.clip(
                (radius_squared - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2)
                / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH),
                -1.0,
                1.0,
            )
        )
    )
    solutions = []
    for branch, elbow in (
        ("positive_elbow", elbow_open),
        ("negative_elbow", -elbow_open),
    ):
        shoulder = float(
            target_angle
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )
        shoulder = _wrap_to_pi(shoulder)
        solutions.append(
            {
                "branch": branch,
                "qpos_rad": [shoulder, elbow],
                "limit_margin_rad": min(
                    JOINT_LIMIT_RAD - abs(shoulder),
                    JOINT_LIMIT_RAD - abs(elbow),
                ),
            }
        )
    return solutions


def _branch_diagnostics(qpos: np.ndarray, target: np.ndarray) -> dict:
    candidates = []
    for solution in _ik_solutions(target):
        solution_qpos = np.asarray(solution["qpos_rad"], dtype=np.float64)
        error = np.asarray(
            [
                _wrap_to_pi(float(qpos[0] - solution_qpos[0])),
                _wrap_to_pi(float(qpos[1] - solution_qpos[1])),
            ]
        )
        candidates.append(
            {
                **solution,
                "joint_error_norm_rad": float(np.linalg.norm(error)),
            }
        )
    nearest = min(candidates, key=lambda item: item["joint_error_norm_rad"])
    return {
        "nearest_branch": nearest["branch"],
        "nearest_branch_error_norm_rad": nearest["joint_error_norm_rad"],
        "nearest_branch_limit_margin_rad": nearest["limit_margin_rad"],
        "solutions": candidates,
    }


def _state_diagnostics(data, target: np.ndarray) -> dict:
    qpos = np.asarray(data.qpos[:2], dtype=np.float64)
    qvel = np.asarray(data.qvel[:2], dtype=np.float64)
    return {
        "qpos_rad": qpos.tolist(),
        "qvel_rad_per_s": qvel.tolist(),
        "qvel_norm_rad_per_s": float(np.linalg.norm(qvel)),
        "actual_joint_limit_margin_rad": float(
            np.min(JOINT_LIMIT_RAD - np.abs(qpos))
        ),
        "ik": _branch_diagnostics(qpos, target),
    }


def diagnose(model: Path, artifact: Path, episodes: int, seed: int) -> None:
    runtime = load_runtime(model)
    env = make_evaluation_env(policy_runtime=runtime)
    diagnostics = []

    for episode in range(episodes):
        observation, _ = env.reset(seed=seed + episode)
        runtime.reset()
        target = np.asarray(env.data.mocap_pos[0], dtype=np.float64)
        target_xy = target[:2]
        target_radius_cm = float(np.linalg.norm(target_xy) * 100.0)
        target_angle_degrees = float(np.degrees(np.arctan2(target_xy[1], target_xy[0])))
        first_reach = None
        first_reach_state = None
        max_held_steps = 0
        hold_interruptions = 0
        was_in_tolerance = False
        min_distance_cm = float("inf")
        final_distance_cm = float("nan")
        success = False
        terminated = False
        truncated = False

        for step in range(1, 501):
            action = runtime.predict(observation)
            observation, _, terminated, truncated, info = env.step(action)
            distance_cm = float(info["distance"]) * 100.0
            held_steps = int(info.get("held_steps", 0))
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            if held_steps > 0 and first_reach is None:
                first_reach = step
                first_reach_state = _state_diagnostics(env.data, target_xy)
            elif held_steps == 0 and was_in_tolerance:
                hold_interruptions += 1
            was_in_tolerance = held_steps > 0
            success = bool(info.get("is_success", False))
            if terminated or truncated:
                break

        terminal_state = _state_diagnostics(env.data, target_xy)
        diagnostics.append(
            {
                "episode": episode,
                "episode_seed": seed + episode,
                "success": success,
                "target_radius_cm": target_radius_cm,
                "target_angle_degrees": target_angle_degrees,
                "first_reach_step": first_reach,
                "max_held_steps": max_held_steps,
                "hold_interruptions": hold_interruptions,
                "min_distance_cm": min_distance_cm,
                "final_distance_cm": final_distance_cm,
                "first_reach_state": first_reach_state,
                "terminal_state": terminal_state,
                "terminated": bool(terminated),
                "truncated": bool(truncated),
            }
        )

    failures = [item for item in diagnostics if not item["success"]]
    payload = {
        "schema_version": 1,
        "measurement": "learned_policy_failure_geometry_and_joint_dynamics",
        "model": str(model),
        "episodes": episodes,
        "seed": seed,
        "target_radius_range_m": list(TARGET_RADIUS_RANGE),
        "hold_steps_required": HOLD_STEPS_REQUIRED,
        "episode_diagnostics": diagnostics,
        "summary": {
            "successes": sum(item["success"] for item in diagnostics),
            "failures": len(failures),
            "failures_without_first_reach": sum(
                item["first_reach_step"] is None for item in failures
            ),
            "failures_after_first_reach": sum(
                item["first_reach_step"] is not None for item in failures
            ),
            "failure_hold_interruptions": sum(
                item["hold_interruptions"] for item in failures
            ),
        },
        "units": {
            "distance": "cm",
            "angle": "degrees",
            "joint_position": "rad",
            "joint_velocity": "rad/s",
            "time": "control_steps",
        },
    }
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--episodes", type=int, default=160)
    parser.add_argument("--seed", type=int, default=4200)
    args = parser.parse_args()
    diagnose(args.model, args.artifact, args.episodes, args.seed)


if __name__ == "__main__":
    main()
