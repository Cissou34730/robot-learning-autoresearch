"""Measure same-interface model-based control capability."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from contracts.task_spec import TARGET_RADIUS_RANGE
from robot_learning.scenario.environment import make_evaluation_env
from robot_learning.scenario.model_based_control import computed_torque_action

JOINT_LIMIT_RAD = float(np.deg2rad(170.0))
HOLD_STEPS_REQUIRED = 100
GAIN_SWEEP = ((25.0, 8.0), (50.0, 14.0), (100.0, 20.0), (150.0, 25.0))


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _ik_solutions(target_xy: np.ndarray) -> list[dict]:
    radius_squared = float(np.dot(target_xy, target_xy))
    target_angle = float(np.arctan2(target_xy[1], target_xy[0]))
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
        shoulder = _wrap_to_pi(
            target_angle
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )
        margin = min(
            JOINT_LIMIT_RAD - abs(shoulder),
            JOINT_LIMIT_RAD - abs(elbow),
        )
        solutions.append(
            {
                "branch": branch,
                "qpos_rad": np.array([shoulder, elbow], dtype=np.float64),
                "limit_margin_rad": float(margin),
            }
        )
    return solutions


def _select_solution(target_xy: np.ndarray) -> dict:
    feasible = [
        solution
        for solution in _ik_solutions(target_xy)
        if solution["limit_margin_rad"] >= 0.0
    ]
    if not feasible:
        raise RuntimeError("official target has no feasible analytic IK branch")
    return max(feasible, key=lambda solution: solution["limit_margin_rad"])


def _computed_torque_action(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    target_qpos: np.ndarray,
    kp: float,
    kd: float,
) -> np.ndarray:
    return computed_torque_action(model, data, target_qpos, kp=kp, kd=kd)


def _run_controller(
    *,
    kp: float,
    kd: float,
    episodes: int,
    seed: int,
) -> dict:
    env = make_evaluation_env()
    episode_diagnostics = []
    for episode in range(episodes):
        env.reset(seed=seed + episode)
        target_xy = np.asarray(env.data.mocap_pos[0][:2], dtype=np.float64)
        solution = _select_solution(target_xy)
        target_qpos = solution["qpos_rad"]
        first_reach_step = None
        max_held_steps = 0
        hold_interruptions = 0
        was_in_tolerance = False
        min_distance_cm = float("inf")
        final_distance_cm = float("nan")
        max_qvel_norm = 0.0
        max_action_abs = 0.0
        success = False
        terminated = False
        truncated = False
        steps = 0

        while not (terminated or truncated):
            action = _computed_torque_action(
                env.model, env.data, target_qpos, kp, kd
            )
            max_action_abs = max(max_action_abs, float(np.max(np.abs(action))))
            _, _, terminated, truncated, info = env.step(action)
            steps += 1
            distance_cm = float(info["distance"]) * 100.0
            held_steps = int(info["held_steps"])
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            max_qvel_norm = max(
                max_qvel_norm,
                float(np.linalg.norm(env.data.qvel[:2])),
            )
            if held_steps > 0 and first_reach_step is None:
                first_reach_step = steps
            elif held_steps == 0 and was_in_tolerance:
                hold_interruptions += 1
            was_in_tolerance = held_steps > 0
            success = bool(info["is_success"])

        episode_diagnostics.append(
            {
                "episode": episode,
                "episode_seed": seed + episode,
                "success": success,
                "target_radius_cm": float(np.linalg.norm(target_xy) * 100.0),
                "target_angle_degrees": float(
                    np.degrees(np.arctan2(target_xy[1], target_xy[0]))
                ),
                "selected_branch": solution["branch"],
                "selected_branch_limit_margin_rad": solution["limit_margin_rad"],
                "first_reach_step": first_reach_step,
                "max_held_steps": max_held_steps,
                "hold_interruptions": hold_interruptions,
                "min_distance_cm": min_distance_cm,
                "final_distance_cm": final_distance_cm,
                "max_qvel_norm_rad_per_s": max_qvel_norm,
                "max_action_abs": max_action_abs,
            }
        )

    failures = [item for item in episode_diagnostics if not item["success"]]
    inner_band = [
        item for item in episode_diagnostics if item["target_radius_cm"] < 14.0
    ]
    return {
        "kp": kp,
        "kd": kd,
        "episodes": episodes,
        "seed": seed,
        "successes": sum(item["success"] for item in episode_diagnostics),
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
        "inner_band_episodes": len(inner_band),
        "inner_band_successes": sum(item["success"] for item in inner_band),
        "episode_diagnostics": episode_diagnostics,
    }


def measure(artifact: Path, episodes: int, seed: int) -> None:
    results = [
        _run_controller(kp=kp, kd=kd, episodes=episodes, seed=seed)
        for kp, kd in GAIN_SWEEP
    ]
    payload = {
        "schema_version": 1,
        "measurement": "same_interface_model_based_control_capability",
        "target_radius_range_m": list(TARGET_RADIUS_RANGE),
        "hold_steps_required": HOLD_STEPS_REQUIRED,
        "controller": "analytic_IK_branch_selection_and_MuJoCo_computed_torque_PD",
        "gain_sweep": [{"kp": kp, "kd": kd} for kp, kd in GAIN_SWEEP],
        "results": results,
        "units": {
            "distance": "cm",
            "angle": "degrees",
            "joint_velocity": "rad/s",
            "time": "control_steps",
        },
    }
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--episodes", type=int, default=160)
    parser.add_argument("--seed", type=int, default=4200)
    args = parser.parse_args()
    measure(args.artifact, args.episodes, args.seed)


if __name__ == "__main__":
    main()
