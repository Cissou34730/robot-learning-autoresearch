"""Measure learned-policy failure trajectories and inverse-kinematics branches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from contracts.policy_runtime import load_runtime
from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.environment import make_evaluation_env

JOINT_LIMIT = np.deg2rad(170.0)
ANGLE_SECTOR_COUNT = 8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--episodes", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    return parser.parse_args()


def wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def target_configurations(target_position: np.ndarray) -> dict[str, tuple[float, float]]:
    target_x = float(target_position[0])
    target_y = float(target_position[1])
    radius = float(np.hypot(target_x, target_y))
    angle = float(np.arctan2(target_y, target_x))
    cosine = (
        radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    configurations = {}
    for branch, elbow in (("open", elbow_open), ("folded", -elbow_open)):
        shoulder = float(
            angle
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )
        configurations[branch] = (shoulder, elbow)
    return configurations


def configuration_distance(
    qpos: np.ndarray, configuration: tuple[float, float]
) -> float:
    return float(
        np.linalg.norm(
            [
                wrap_to_pi(float(qpos[0]) - configuration[0]),
                wrap_to_pi(float(qpos[1]) - configuration[1]),
            ]
        )
    )


def nearest_branch(
    qpos: np.ndarray, configurations: dict[str, tuple[float, float]]
) -> tuple[str, dict[str, float]]:
    distances = {
        branch: configuration_distance(qpos, configuration)
        for branch, configuration in configurations.items()
    }
    branch = min(distances, key=distances.get)
    return branch, distances


def radius_bin(radius_cm: float) -> str:
    edges = (6.0, 10.0, 14.0, 18.0, 20.0)
    for lower, upper in zip(edges, edges[1:], strict=True):
        if radius_cm < upper or upper == edges[-1]:
            return f"{lower:.0f}-{upper:.0f}cm"
    raise AssertionError("radius is outside the official range")


def angle_sector(angle_degrees: float) -> str:
    normalized = (angle_degrees + 180.0) % 360.0
    index = min(int(normalized // (360.0 / ANGLE_SECTOR_COUNT)), 7)
    lower = -180.0 + index * 45.0
    upper = lower + 45.0
    return f"{lower:.0f}..{upper:.0f}deg"


def increment_nested_count(
    counts: dict[str, dict[str, int]], key: str, branch: str
) -> None:
    counts.setdefault(key, {"open": 0, "folded": 0})
    counts[key][branch] += 1


def run_probe(model_path: Path, episodes: int, seed: int) -> dict:
    if episodes < 1:
        raise ValueError("episodes must be positive")
    runtime = load_runtime(model_path)
    env = make_evaluation_env(policy_runtime=runtime)
    episode_results: list[dict] = []
    episode_diagnostics: list[dict] = []
    failure_traces: list[dict] = []
    failure_classes = {
        "no_tolerance_entry": 0,
        "late_tolerance_entry": 0,
        "early_entry_interrupted": 0,
    }
    failure_radius_bins: dict[str, int] = {}
    failure_angle_sectors: dict[str, int] = {}
    failure_branch_at_entry = {"open": 0, "folded": 0, "none": 0}
    failure_branch_at_closest = {"open": 0, "folded": 0}
    branch_counts = {"open": 0, "folded": 0}
    branch_counts_by_radius: dict[str, dict[str, int]] = {}
    branch_counts_by_angle: dict[str, dict[str, int]] = {}

    for episode in range(episodes):
        episode_seed = seed + episode
        obs, _ = env.reset(seed=episode_seed)
        runtime.reset()
        target_position = np.asarray(env.data.mocap_pos[0], dtype=np.float64)
        configurations = target_configurations(target_position)
        target_radius_cm = float(np.hypot(target_position[0], target_position[1]) * 100.0)
        target_angle_degrees = float(
            np.degrees(np.arctan2(target_position[1], target_position[0]))
        )
        feasible_branches = [
            branch
            for branch, configuration in configurations.items()
            if abs(configuration[0]) <= JOINT_LIMIT and abs(configuration[1]) <= JOINT_LIMIT
        ]

        reward_total = 0.0
        steps = 0
        success = False
        terminated = False
        truncated = False
        min_distance_cm = float("inf")
        final_distance_cm = float("nan")
        first_reach_step: int | None = None
        max_held_steps = 0
        in_tolerance_steps = 0
        hold_interruptions = 0
        was_in_tolerance = False
        first_entry_branch: str | None = None
        closest_branch = "open"
        closest_branch_distance = float("inf")
        previous_branch: str | None = None
        branch_switch_count = 0
        branch_counts_episode = {"open": 0, "folded": 0}
        trace: list[dict] = []

        while not (terminated or truncated):
            action = runtime.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            qpos = np.asarray(env.data.qpos[:2], dtype=np.float64).copy()
            qvel = np.asarray(env.data.qvel[:2], dtype=np.float64).copy()
            branch, branch_distances = nearest_branch(qpos, configurations)
            branch_counts[branch] += 1
            branch_counts_episode[branch] += 1
            increment_nested_count(
                branch_counts_by_radius, radius_bin(target_radius_cm), branch
            )
            increment_nested_count(
                branch_counts_by_angle, angle_sector(target_angle_degrees), branch
            )
            if previous_branch is not None and branch != previous_branch:
                branch_switch_count += 1
            previous_branch = branch
            if branch_distances[branch] < closest_branch_distance:
                closest_branch = branch
                closest_branch_distance = branch_distances[branch]

            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    first_entry_branch = branch
            elif was_in_tolerance:
                hold_interruptions += 1
            was_in_tolerance = held_steps > 0
            if "is_success" in info:
                success = bool(info["is_success"])

            if not success:
                trace.append(
                    {
                        "step": steps,
                        "qpos": qpos.tolist(),
                        "qvel": qvel.tolist(),
                        "distance_cm": distance_cm,
                        "held_steps": held_steps,
                        "nearest_branch": branch,
                        "branch_distance_rad": branch_distances[branch],
                    }
                )

        episode_results.append(
            {
                "episode": episode,
                "episode_seed": episode_seed,
                "success": success,
                "reward_total": reward_total,
                "steps": steps,
                "terminated": bool(terminated),
                "truncated": bool(truncated),
            }
        )
        diagnostic = {
            "episode": episode,
            "episode_seed": episode_seed,
            "target_radius_cm": target_radius_cm,
            "target_angle_degrees": target_angle_degrees,
            "radius_bin": radius_bin(target_radius_cm),
            "angle_sector": angle_sector(target_angle_degrees),
            "feasible_branches": feasible_branches,
            "first_reach_step": first_reach_step,
            "first_entry_branch": first_entry_branch,
            "closest_branch": closest_branch,
            "closest_branch_distance_rad": closest_branch_distance,
            "min_distance_cm": min_distance_cm,
            "final_distance_cm": final_distance_cm,
            "max_held_steps": max_held_steps,
            "in_tolerance_steps": in_tolerance_steps,
            "hold_interruptions": hold_interruptions,
            "branch_switch_count": branch_switch_count,
            "branch_step_counts": branch_counts_episode,
        }
        episode_diagnostics.append(diagnostic)

        if not success:
            if first_reach_step is None:
                failure_class = "no_tolerance_entry"
                failure_branch_at_entry["none"] += 1
            elif first_reach_step >= 100:
                failure_class = "late_tolerance_entry"
                failure_branch_at_entry[first_entry_branch] += 1
            else:
                failure_class = "early_entry_interrupted"
                failure_branch_at_entry[first_entry_branch] += 1
            failure_classes[failure_class] += 1
            failure_radius_bins[radius_bin(target_radius_cm)] = (
                failure_radius_bins.get(radius_bin(target_radius_cm), 0) + 1
            )
            failure_angle_sectors[angle_sector(target_angle_degrees)] = (
                failure_angle_sectors.get(angle_sector(target_angle_degrees), 0) + 1
            )
            failure_branch_at_closest[closest_branch] += 1
            failure_traces.append(
                {
                    "episode": episode,
                    "episode_seed": episode_seed,
                    "failure_class": failure_class,
                    "diagnostic": diagnostic,
                    "trajectory": trace,
                }
            )

    successes = sum(result["success"] for result in episode_results)
    return {
        "schema_version": 1,
        "measurement": "learned_policy_branch_and_failure_trace",
        "model": str(model_path),
        "episodes": episodes,
        "seed": seed,
        "successes": successes,
        "success_percent": 100.0 * successes / episodes,
        "episode_results": episode_results,
        "failure_summary": {
            "failure_count": episodes - successes,
            "failure_classes": failure_classes,
            "radius_bins": failure_radius_bins,
            "angle_sectors": failure_angle_sectors,
            "branch_at_first_entry": failure_branch_at_entry,
            "branch_at_closest_approach": failure_branch_at_closest,
        },
        "branch_summary": {
            "all_episode_steps": branch_counts,
            "by_radius_bin": branch_counts_by_radius,
            "by_angle_sector": branch_counts_by_angle,
        },
        "episode_diagnostics": episode_diagnostics,
        "failure_traces": failure_traces,
    }


def main() -> None:
    args = parse_args()
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact = run_probe(args.model, args.episodes, args.seed)
    args.artifact.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
