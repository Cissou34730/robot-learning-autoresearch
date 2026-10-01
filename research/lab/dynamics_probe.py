"""Measure reach, braking, and hold feasibility across the official geometry."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.environment import TwoJointArmReachEnv

CONTROL_TORQUE_LIMIT = 5.0
JOINT_LIMIT = math.radians(170.0)
RADII = (0.06, 0.10, 0.14, 0.18, 0.20)
ANGLE_COUNT = 12
GAIN_SCHEDULES = (
    {"name": "soft", "kp": 2.0, "kd": 0.25},
    {"name": "balanced", "kp": 5.0, "kd": 0.75},
    {"name": "firm", "kp": 10.0, "kd": 1.5},
)


def wrap_to_pi(value: float) -> float:
    return float((value + math.pi) % (2.0 * math.pi) - math.pi)


def ik_solutions(x: float, y: float) -> list[tuple[str, np.ndarray]]:
    radius_squared = x * x + y * y
    cosine = (
        radius_squared - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_magnitude = math.acos(float(np.clip(cosine, -1.0, 1.0)))
    angle = math.atan2(y, x)
    solutions: list[tuple[str, np.ndarray]] = []
    for branch, elbow in (
        ("open", elbow_magnitude),
        ("folded", -elbow_magnitude),
    ):
        shoulder = angle - math.atan2(
            FOREARM_LENGTH * math.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * math.cos(elbow),
        )
        target = np.array([wrap_to_pi(shoulder), elbow], dtype=np.float64)
        if np.all(np.abs(target) <= JOINT_LIMIT):
            solutions.append((branch, target))
    return solutions


def target_position(radius: float, angle: float, z: float) -> np.ndarray:
    return np.array([radius * math.cos(angle), radius * math.sin(angle), z])


def run_trial(
    env: TwoJointArmReachEnv,
    target: np.ndarray,
    desired_q: np.ndarray,
    gains: dict[str, float],
    seed: int,
) -> dict:
    env.reset(seed=seed)
    env.data.mocap_pos[0] = target
    import mujoco

    mujoco.mj_forward(env.model, env.data)
    env._previous_distance = env._distance_to_target()
    max_speed = 0.0
    max_abs_action = 0.0
    saturated_steps = 0
    first_reach_step: int | None = None
    max_held_steps = 0
    success = False
    final_distance = None
    for step in range(1, env.max_episode_steps + 1):
        error = desired_q - env.data.qpos[:2]
        error[0] = wrap_to_pi(float(error[0]))
        torque = gains["kp"] * error - gains["kd"] * env.data.qvel[:2]
        action = np.clip(torque / CONTROL_TORQUE_LIMIT, -1.0, 1.0)
        if np.any(np.abs(action) >= 1.0 - 1e-12):
            saturated_steps += 1
        max_abs_action = max(max_abs_action, float(np.max(np.abs(action))))
        _, _, terminated, truncated, info = env.step(action)
        max_speed = max(max_speed, float(np.linalg.norm(env.data.qvel[:2])))
        held_steps = int(info["held_steps"])
        max_held_steps = max(max_held_steps, held_steps)
        if held_steps > 0 and first_reach_step is None:
            first_reach_step = step
        final_distance = float(info["distance"])
        if bool(info["is_success"]):
            success = True
            break
        if truncated or terminated:
            break
    return {
        "success": success,
        "steps": step,
        "first_reach_step": first_reach_step,
        "max_held_steps": max_held_steps,
        "final_distance_cm": 100.0 * (final_distance or 0.0),
        "max_joint_speed_rad_s": max_speed,
        "max_abs_action": max_abs_action,
        "saturated_fraction": saturated_steps / step,
    }


def summarize_trials(trials: list[dict]) -> dict:
    successful = [trial for trial in trials if trial["success"]]
    return {
        "trials": len(trials),
        "successful_trials": len(successful),
        "success_rate_percent": 100.0 * len(successful) / len(trials)
        if trials
        else 0.0,
        "median_first_reach_step": (
            float(np.median([trial["first_reach_step"] for trial in successful]))
            if successful
            else None
        ),
        "median_max_held_steps": float(
            np.median([trial["max_held_steps"] for trial in trials])
        )
        if trials
        else None,
        "median_saturated_fraction": float(
            np.median([trial["saturated_fraction"] for trial in trials])
        )
        if trials
        else None,
    }


def run_probe() -> dict:
    env = TwoJointArmReachEnv(
        target_radius_range=(RADII[0], RADII[-1]),
        max_episode_steps=500,
    )
    angles = tuple(2.0 * math.pi * index / ANGLE_COUNT for index in range(ANGLE_COUNT))
    targets: list[dict] = []
    all_trials: list[dict] = []
    branch_trials: dict[str, list[dict]] = {"open": [], "folded": []}
    gain_trials: dict[str, list[dict]] = {
        schedule["name"]: [] for schedule in GAIN_SCHEDULES
    }
    target_index = 0
    for radius in RADII:
        for angle in angles:
            target_index += 1
            target = target_position(radius, angle, 0.02)
            branches = ik_solutions(float(target[0]), float(target[1]))
            target_record = {
                "target_index": target_index,
                "radius_cm": radius * 100.0,
                "angle_degrees": math.degrees(angle),
                "feasible_branches": [branch for branch, _ in branches],
                "trials": [],
            }
            for branch, desired_q in branches:
                for gain_index, gains in enumerate(GAIN_SCHEDULES):
                    trial = run_trial(
                        env,
                        target,
                        desired_q,
                        gains,
                        seed=10_000 + target_index * 10 + gain_index,
                    )
                    trial = {
                        "branch": branch,
                        "gain_schedule": gains["name"],
                        **trial,
                    }
                    target_record["trials"].append(trial)
                    all_trials.append(trial)
                    branch_trials[branch].append(trial)
                    gain_trials[gains["name"]].append(trial)
            targets.append(target_record)
    env.close()

    target_successes = sum(
        any(trial["success"] for trial in target["trials"]) for target in targets
    )
    return {
        "schema_version": 1,
        "probe": {
            "radii_cm": [radius * 100.0 for radius in RADII],
            "angle_count": ANGLE_COUNT,
            "gain_schedules": list(GAIN_SCHEDULES),
            "control_torque_limit": CONTROL_TORQUE_LIMIT,
            "hold_steps_required": 100,
            "max_episode_steps": 500,
        },
        "kinematic_summary": {
            "targets": len(targets),
            "targets_with_a_feasible_branch": sum(
                bool(target["feasible_branches"]) for target in targets
            ),
            "targets_with_both_feasible_branches": sum(
                len(target["feasible_branches"]) == 2 for target in targets
            ),
            "targets_with_a_successful_bounded_pd_trial": target_successes,
        },
        "all_trials": summarize_trials(all_trials),
        "by_branch": {
            branch: summarize_trials(trials)
            for branch, trials in branch_trials.items()
        },
        "by_gain_schedule": {
            name: summarize_trials(trials) for name, trials in gain_trials.items()
        },
        "by_radius_cm": {
            str(radius * 100.0): summarize_trials(
                [
                    trial
                    for target in targets
                    if target["radius_cm"] == radius * 100.0
                    for trial in target["trials"]
                ]
            )
            for radius in RADII
        },
        "targets": targets,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(run_probe(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
