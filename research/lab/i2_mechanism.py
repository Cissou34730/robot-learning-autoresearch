"""Targeted behavioral diagnostics for inquiry I2.

The diagnostic uses symmetric target pairs and a radius grid to measure
negative-bearing asymmetry, branch-limit proximity, and complete hold outcomes
without changing the policy or task semantics.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from robot_learning.policy_runtime import load_runtime
from robot_learning.scenario.environment import make_evaluation_env

CONTROL_LIMIT_DEGREES = 170.0
HOLD_WINDOW_STEPS = 10
HOLD_REQUIRED_STEPS = 100
MAX_STEPS = 500
RADIUS_GRID_METERS = (0.06, 0.10, 0.14, 0.16, 0.18, 0.20)
ANGLE_GRID_DEGREES = tuple(range(-165, 180, 15))


def _wrap_degrees(angle: float) -> float:
    return float((angle + 180.0) % 360.0 - 180.0)


def _ik_branches(radius: float, angle_degrees: float) -> dict[str, dict[str, float]]:
    angle = np.radians(angle_degrees)
    elbow = float(
        np.arccos(
            np.clip(
                (radius**2 - 0.12**2 - 0.10**2) / (2.0 * 0.12 * 0.10),
                -1.0,
                1.0,
            )
        )
    )
    branches = {}
    for name, q2 in (("open", elbow), ("folded", -elbow)):
        q1 = float(
            angle
            - np.arctan2(0.10 * np.sin(q2), 0.12 + 0.10 * np.cos(q2))
        )
        q1 = float(np.arctan2(np.sin(q1), np.cos(q1)))
        q1_degrees = _wrap_degrees(np.degrees(q1))
        q2_degrees = float(np.degrees(q2))
        margin = min(
            CONTROL_LIMIT_DEGREES - abs(q1_degrees),
            CONTROL_LIMIT_DEGREES - abs(q2_degrees),
        )
        branches[name] = {
            "shoulder_degrees": q1_degrees,
            "elbow_degrees": q2_degrees,
            "joint_limit_margin_degrees": margin,
            "feasible": bool(margin >= 0.0),
        }
    return branches


def _initial_branch_features(observation: np.ndarray) -> dict[str, float | str]:
    open_error = float(np.linalg.norm(observation[7:9]))
    folded_error = float(np.linalg.norm(observation[9:11]))
    return {
        "open_error_norm": open_error,
        "folded_error_norm": folded_error,
        "nearest_branch": "open" if open_error <= folded_error else "folded",
    }


def _target_observation(env, radius: float, angle_degrees: float) -> np.ndarray:
    target_z = float(env.data.site("end_effector").xpos[2])
    angle = np.radians(angle_degrees)
    env.data.mocap_pos[0] = [
        radius * np.cos(angle),
        radius * np.sin(angle),
        target_z,
    ]
    mujoco.mj_forward(env.model, env.data)
    env._previous_distance = env._distance_to_target()
    return env._observation()


def _run_episode(runtime, env, radius: float, angle_degrees: float) -> dict:
    env.reset(seed=0)
    runtime.reset()
    observation = _target_observation(env, radius, angle_degrees)
    initial_features = _initial_branch_features(observation)
    initial_action = np.asarray(runtime.predict(observation), dtype=np.float64)
    actions = [initial_action]
    first_reach_step = None
    settling_step = None
    longest_hold = 0
    current_hold = 0
    interruptions = 0
    was_inside = False
    min_distance_cm = float("inf")
    final_distance_cm = float("nan")
    success = False
    steps = 1
    terminated = False
    truncated = False
    while not (terminated or truncated):
        if steps == 1:
            action = initial_action
        else:
            action = runtime.predict(observation)
            actions.append(np.asarray(action, dtype=np.float64))
        observation, _, terminated, truncated, info = env.step(action)
        distance_cm = 100.0 * float(info["distance"])
        held_steps = int(info.get("held_steps", 0))
        min_distance_cm = min(min_distance_cm, distance_cm)
        final_distance_cm = distance_cm
        if held_steps > 0:
            current_hold += 1
            longest_hold = max(longest_hold, current_hold)
            if first_reach_step is None:
                first_reach_step = steps
            if settling_step is None and current_hold >= HOLD_WINDOW_STEPS:
                settling_step = steps - HOLD_WINDOW_STEPS + 1
        else:
            if was_inside:
                interruptions += 1
            current_hold = 0
        was_inside = held_steps > 0
        success = bool(info.get("is_success", False))
        steps += 1
    actions_array = np.asarray(actions, dtype=np.float64)
    branches = _ik_branches(radius, angle_degrees)
    return {
        "radius_cm": radius * 100.0,
        "angle_degrees": angle_degrees,
        "success": success,
        "first_entry_step": first_reach_step,
        "settling_step": settling_step,
        "longest_uninterrupted_hold_steps": longest_hold,
        "hold_interruptions": interruptions,
        "min_distance_cm": min_distance_cm,
        "timeout_distance_cm": final_distance_cm if truncated else None,
        "initial_action": initial_action.tolist(),
        "mean_abs_action_first_10": np.mean(
            np.abs(actions_array[:10]), axis=0
        ).tolist(),
        "initial_branch_features": initial_features,
        "ik_branches": branches,
    }


def _summarize(records: list[dict]) -> dict:
    def group(items: list[dict]) -> dict:
        successes = sum(bool(item["success"]) for item in items)
        return {
            "episodes": len(items),
            "successes": successes,
            "success_percent": 100.0 * successes / len(items) if items else None,
            "approach_failures": sum(
                item["first_entry_step"] is None for item in items
            ),
            "settling_failures": sum(
                item["first_entry_step"] is not None
                and item["settling_step"] is None
                for item in items
            ),
            "post_settling_hold_failures": sum(
                item["settling_step"] is not None and not item["success"]
                for item in items
            ),
            "mean_longest_hold_steps": (
                float(np.mean([item["longest_uninterrupted_hold_steps"] for item in items]))
                if items
                else None
            ),
        }

    negative = [item for item in records if -180.0 <= item["angle_degrees"] < -90.0]
    mirrored = [item for item in records if 90.0 < item["angle_degrees"] <= 180.0]
    supported = [item for item in records if item["radius_cm"] >= 14.0]
    unsupported = [item for item in records if item["radius_cm"] < 14.0]
    return {
        "all": group(records),
        "negative_bearing_sector": group(negative),
        "mirrored_positive_sector": group(mirrored),
        "training_supported_radius": group(supported),
        "training_unsupported_radius": group(unsupported),
    }


def _paired_mirror_summary(records: list[dict]) -> dict:
    pairs = []
    for radius in RADIUS_GRID_METERS:
        radius_cm = radius * 100.0
        for angle in (105.0, 120.0, 135.0, 150.0, 165.0):
            negative = next(
                (
                    item
                    for item in records
                    if round(item["radius_cm"], 5) == round(radius_cm, 5)
                    and round(item["angle_degrees"], 5) == -angle
                ),
                None,
            )
            positive = next(
                (
                    item
                    for item in records
                    if round(item["radius_cm"], 5) == round(radius_cm, 5)
                    and round(item["angle_degrees"], 5) == angle
                ),
                None,
            )
            if negative is None or positive is None:
                continue
            negative_action = np.asarray(negative["initial_action"])
            positive_action = np.asarray(positive["initial_action"])
            pairs.append(
                {
                    "radius_cm": radius_cm,
                    "absolute_angle_degrees": angle,
                    "negative_success": negative["success"],
                    "positive_success": positive["success"],
                    "success_disagreement": (
                        negative["success"] != positive["success"]
                    ),
                    "initial_mirror_action_error": float(
                        np.linalg.norm(negative_action + positive_action)
                    ),
                    "negative_nearest_branch": negative["initial_branch_features"][
                        "nearest_branch"
                    ],
                    "negative_nearest_branch_feasible": negative["ik_branches"][
                        negative["initial_branch_features"]["nearest_branch"]
                    ]["feasible"],
                }
            )
    disagreements = [pair for pair in pairs if pair["success_disagreement"]]
    return {
        "pairs": pairs,
        "pair_count": len(pairs),
        "success_disagreements": len(disagreements),
        "mean_initial_mirror_action_error": (
            float(np.mean([pair["initial_mirror_action_error"] for pair in pairs]))
            if pairs
            else None
        ),
        "mean_error_disagreement_pairs": (
            float(
                np.mean(
                    [pair["initial_mirror_action_error"] for pair in disagreements]
                )
            )
            if disagreements
            else None
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    runtime = load_runtime(args.model)
    env = make_evaluation_env(policy_runtime=runtime)
    records = [
        _run_episode(runtime, env, radius, angle)
        for radius in RADIUS_GRID_METERS
        for angle in ANGLE_GRID_DEGREES
    ]
    artifact = {
        "schema_version": 1,
        "diagnostic": "I2 symmetric bearing and radius grid",
        "model": str(args.model),
        "grid": {
            "radii_cm": [radius * 100.0 for radius in RADIUS_GRID_METERS],
            "angles_degrees": list(ANGLE_GRID_DEGREES),
            "training_radius_boundary_cm": 14.0,
        },
        "measurement_definition": {
            "negative_bearing_approach_settling": (
                "Report approach failures, settling failures, and longest "
                "uninterrupted holds separately in -180 to -90 degrees, with "
                "mirrored positive-bearing pairs at the same radius."
            ),
            "complete_hold": (
                "Count success only when the environment reaches 100 consecutive "
                "in-tolerance control samples; report post-settling hold failures "
                "separately."
            ),
            "official_distribution_check": (
                "Pair this grid with a fresh research_evaluation panel over the "
                "complete 0.06-0.20 m and -180 to 180 degree distribution before "
                "assigning a candidate role."
            ),
        },
        "summary": _summarize(records),
        "paired_mirror_summary": _paired_mirror_summary(records),
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
