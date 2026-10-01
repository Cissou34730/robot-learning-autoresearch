"""Measure whether fixed low-level feedback can complete the official task."""

from __future__ import annotations

import argparse
import json
from itertools import pairwise
from pathlib import Path

import numpy as np

from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.environment import TwoJointArmReachEnv

JOINT_LIMIT = np.deg2rad(170.0)
RADIUS_EDGES_CM = (6.0, 10.0, 14.0, 18.0, 20.0)


def _wrap(angle: np.ndarray) -> np.ndarray:
    return (angle + np.pi) % (2.0 * np.pi) - np.pi


def _ik_branches(target_x: float, target_y: float) -> dict[str, np.ndarray]:
    radius_squared = target_x**2 + target_y**2
    cosine = (
        radius_squared - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    target_angle = float(np.arctan2(target_y, target_x))
    branches: dict[str, np.ndarray] = {}
    for name, elbow in (("open", elbow_open), ("folded", -elbow_open)):
        shoulder = target_angle - np.arctan2(
            FOREARM_LENGTH * np.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
        )
        branches[name] = np.asarray([shoulder, elbow], dtype=np.float64)
    return branches


def _select_branch(branches: dict[str, np.ndarray], strategy: str) -> np.ndarray:
    if strategy in branches:
        return branches[strategy]
    feasible = [
        (float(np.linalg.norm(configuration)), configuration)
        for configuration in branches.values()
        if np.all(np.abs(configuration) <= JOINT_LIMIT)
    ]
    if feasible:
        return min(feasible, key=lambda item: item[0])[1]
    return min(
        branches.values(),
        key=lambda configuration: float(
            np.sum(np.maximum(np.abs(configuration) - JOINT_LIMIT, 0.0))
        ),
    )


def _variant_specs() -> list[dict]:
    return [
        {
            "name": f"{branch}_pd_{kp:g}_{kd:g}",
            "branch": branch,
            "kp": kp,
            "kd": kd,
        }
        for branch in ("nearest", "open", "folded")
        for kp, kd in ((0.2, 0.05), (0.3, 0.08), (0.4, 0.1))
    ]


def _summarize(rows: list[dict]) -> dict:
    successes = sum(bool(row["success"]) for row in rows)
    no_entry = sum(row["first_entry_step"] is None for row in rows)
    bins = []
    for lower, upper in pairwise(RADIUS_EDGES_CM):
        in_bin = [
            row
            for row in rows
            if lower <= row["target_radius_cm"] < upper
            or (
                upper == RADIUS_EDGES_CM[-1]
                and lower <= row["target_radius_cm"] <= upper
            )
        ]
        bins.append(
            {
                "bin_cm": f"{lower:g}-{upper:g}",
                "episodes": len(in_bin),
                "successes": sum(bool(row["success"]) for row in in_bin),
                "no_entry": sum(
                    row["first_entry_step"] is None for row in in_bin
                ),
            }
        )
    return {
        "episodes": len(rows),
        "successes": successes,
        "success_percent": 100.0 * successes / len(rows),
        "no_entry": no_entry,
        "post_entry_failures": sum(
            not row["success"] and row["first_entry_step"] is not None
            for row in rows
        ),
        "mean_first_entry_step": (
            float(np.mean([row["first_entry_step"] for row in rows if row["first_entry_step"] is not None]))
            if no_entry < len(rows)
            else None
        ),
        "mean_hold_exits": float(np.mean([row["hold_exits"] for row in rows])),
        "episodes_with_action_saturation_percent": (
            100.0
            * sum(row["saturated_action_steps"] > 0 for row in rows)
            / len(rows)
        ),
        "radius_bins": bins,
    }


def _run_variant(
    spec: dict,
    *,
    episodes: int,
    seed: int,
) -> dict:
    env = TwoJointArmReachEnv()
    rows = []
    for episode in range(episodes):
        env.reset(seed=seed + episode)
        target = np.asarray(env.data.mocap_pos[0], dtype=np.float64)
        target_radius_cm = 100.0 * float(np.hypot(target[0], target[1]))
        branches = _ik_branches(float(target[0]), float(target[1]))
        desired = _select_branch(branches, spec["branch"])
        first_entry_step = None
        hold_exits = 0
        previous_held_steps = 0
        max_abs_action = 0.0
        saturated_action_steps = 0
        steps = 0
        success = False
        terminated = False
        truncated = False
        while not (terminated or truncated):
            error = _wrap(
                desired - np.asarray(env.data.qpos[:2], dtype=np.float64)
            )
            action = np.clip(
                spec["kp"] * error
                - spec["kd"] * np.asarray(env.data.qvel[:2], dtype=np.float64),
                -1.0,
                1.0,
            )
            max_abs_action = max(max_abs_action, float(np.max(np.abs(action))))
            if np.any(np.abs(action) >= 1.0 - 1e-6):
                saturated_action_steps += 1
            _, _, terminated, truncated, info = env.step(action)
            steps += 1
            held_steps = int(info["held_steps"])
            if held_steps > 0 and first_entry_step is None:
                first_entry_step = steps
            if held_steps == 0 and previous_held_steps > 0:
                hold_exits += 1
            previous_held_steps = held_steps
            success = bool(info["is_success"])
        rows.append(
            {
                "episode": episode,
                "episode_seed": seed + episode,
                "target_radius_cm": target_radius_cm,
                "success": success,
                "steps": steps,
                "first_entry_step": first_entry_step,
                "hold_exits": hold_exits,
                "max_abs_action": max_abs_action,
                "saturated_action_steps": saturated_action_steps,
            }
        )
    return {
        "name": spec["name"],
        "branch": spec["branch"],
        "kp": spec["kp"],
        "kd": spec["kd"],
        "summary": _summarize(rows),
        "episode_diagnostics": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--episodes", type=int, default=160)
    parser.add_argument("--seed", type=int, default=4200)
    args = parser.parse_args()
    if args.episodes < 1 or args.seed < 0:
        raise ValueError("episodes must be positive and seed must be non-negative")

    result = {
        "schema_version": 1,
        "measurement": "fixed_ik_joint_pd_authority_probe",
        "episodes": args.episodes,
        "seed": args.seed,
        "task_semantics": {
            "target_radius_cm": [6.0, 20.0],
            "max_episode_steps": 500,
            "success_threshold_cm": 1.0,
            "hold_steps_required": 100,
        },
        "variants": [
            _run_variant(spec, episodes=args.episodes, seed=args.seed)
            for spec in _variant_specs()
        ],
    }
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
