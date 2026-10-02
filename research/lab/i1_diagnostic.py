"""Conditioned trajectory diagnostics for inquiry I1."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import mujoco
import numpy as np

from robot_learning.policy_runtime import load_runtime
from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.environment import make_evaluation_env


def _wrap(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _finite(value: float | np.floating) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def _planar_jacobian(q: np.ndarray) -> np.ndarray:
    q1, q2 = float(q[0]), float(q[1])
    q12 = q1 + q2
    return np.array(
        [
            [
                -UPPER_ARM_LENGTH * np.sin(q1)
                - FOREARM_LENGTH * np.sin(q12),
                -FOREARM_LENGTH * np.sin(q12),
            ],
            [
                UPPER_ARM_LENGTH * np.cos(q1)
                + FOREARM_LENGTH * np.cos(q12),
                FOREARM_LENGTH * np.cos(q12),
            ],
        ]
    )


def _jacobian_metrics(jacobian: np.ndarray) -> dict:
    singular_values = np.linalg.svd(jacobian, compute_uv=False)
    smallest = float(singular_values[-1])
    condition = (
        float(singular_values[0] / smallest) if smallest > np.finfo(float).eps else None
    )
    return {
        "singular_values": [float(value) for value in singular_values],
        "condition": _finite(condition) if condition is not None else None,
    }


def _ik_branches(target: np.ndarray) -> dict[str, np.ndarray]:
    x, y = float(target[0]), float(target[1])
    cos_elbow = (
        x**2 + y**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))
    branches = {}
    for name, elbow in (("open", elbow_open), ("folded", -elbow_open)):
        shoulder = float(
            np.arctan2(y, x)
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )
        branches[name] = np.array([_wrap(shoulder), elbow], dtype=np.float64)
    return branches


def _branch_metrics(q: np.ndarray, branches: dict[str, np.ndarray]) -> dict:
    errors = {
        name: np.array([_wrap(float(target[0] - q[0])), _wrap(float(target[1] - q[1]))])
        for name, target in branches.items()
    }
    distances = {
        name: float(np.linalg.norm(error)) for name, error in errors.items()
    }
    selected = min(distances, key=distances.get)
    return {
        "selected_branch": selected,
        "branch_distance_rad": distances,
        "branch_errors_rad": {
            name: [float(value) for value in error]
            for name, error in errors.items()
        },
    }


def _limit_margins(q: np.ndarray, joint_ranges: np.ndarray) -> list[float]:
    return [
        float(min(float(position - limits[0]), float(limits[1] - position)))
        for position, limits in zip(q, joint_ranges, strict=True)
    ]


def _state_metrics(
    env,
    target: np.ndarray,
    branches: dict[str, np.ndarray],
    observation: np.ndarray,
    action: np.ndarray,
    held_steps: int,
) -> dict:
    q = np.asarray(env.data.qpos[:2], dtype=np.float64).copy()
    qvel = np.asarray(env.data.qvel[:2], dtype=np.float64).copy()
    end_effector = np.asarray(env.data.site("end_effector").xpos, dtype=np.float64)
    distance_cm = 100.0 * float(np.linalg.norm(end_effector - target))
    actual_jacobian = np.zeros((3, env.model.nv), dtype=np.float64)
    actual_angular_jacobian = np.zeros((3, env.model.nv), dtype=np.float64)
    mujoco.mj_jacSite(
        env.model,
        env.data,
        actual_jacobian,
        actual_angular_jacobian,
        env.model.site("end_effector").id,
    )
    branch = _branch_metrics(q, branches)
    target_geometry = {
        name: _jacobian_metrics(_planar_jacobian(configuration))
        for name, configuration in branches.items()
    }
    return {
        "distance_cm": distance_cm,
        "held_steps": int(held_steps),
        "q_rad": [float(value) for value in q],
        "qvel_rad_per_second": [float(value) for value in qvel],
        "qvel_norm": float(np.linalg.norm(qvel)),
        "action": [float(value) for value in np.asarray(action)],
        "joint_limit_margin_rad": _limit_margins(
            q, np.asarray(env.model.jnt_range[:2], dtype=np.float64)
        ),
        "joint_limit_margin_degrees": [
            float(np.degrees(value))
            for value in _limit_margins(
                q, np.asarray(env.model.jnt_range[:2], dtype=np.float64)
            )
        ],
        "target_branch_q_rad": {
            name: [float(value) for value in configuration]
            for name, configuration in branches.items()
        },
        "target_branch_limit_margin_degrees": {
            name: [
                float(np.degrees(value))
                for value in _limit_margins(
                    configuration,
                    np.asarray(env.model.jnt_range[:2], dtype=np.float64),
                )
            ]
            for name, configuration in branches.items()
        },
        "jacobian": _jacobian_metrics(actual_jacobian[:2, :2]),
        "target_branch_jacobian": target_geometry,
        **branch,
        "observation_branch_errors_rad": [
            float(value) for value in np.asarray(observation[7:11])
        ],
    }


def _mean(values: list[float | int | None]) -> float | None:
    finite_values = [
        float(value)
        for value in values
        if value is not None and math.isfinite(float(value))
    ]
    return _finite(np.mean(finite_values)) if finite_values else None


def _state_summary(episodes: list[dict], state_name: str) -> dict:
    selected = [
        episode["states"][state_name]
        for episode in episodes
        if episode["states"].get(state_name) is not None
    ]
    branch_counts: dict[str, int] = {}
    for state in selected:
        branch = str(state["selected_branch"])
        branch_counts[branch] = branch_counts.get(branch, 0) + 1
    return {
        "episodes": len(selected),
        "selected_branch_counts": branch_counts,
        "mean_target_radius_cm": _mean(
            [episode["target_radius_cm"] for episode in episodes]
        ),
        "mean_target_angle_degrees": _mean(
            [episode["target_angle_degrees"] for episode in episodes]
        ),
        "mean_joint_limit_margin_degrees": [
            _mean([state["joint_limit_margin_degrees"][joint] for state in selected])
            for joint in range(2)
        ],
        "mean_jacobian_condition": _mean(
            [state["jacobian"]["condition"] for state in selected]
        ),
        "mean_qvel_norm": _mean([state["qvel_norm"] for state in selected]),
        "mean_distance_cm": _mean([state["distance_cm"] for state in selected]),
    }


def _episode_class(success: bool, first_entry: dict | None) -> str:
    if success:
        return "success"
    if first_entry is None:
        return "non_entry"
    return "interrupted_hold"


def _trace_candidate(model_path: Path, episodes: int, seed: int) -> dict:
    runtime = load_runtime(model_path)
    env = make_evaluation_env(policy_runtime=runtime)
    traced: list[dict] = []
    for episode_index in range(episodes):
        observation, _ = env.reset(seed=seed + episode_index)
        runtime.reset()
        target = np.asarray(env.data.mocap_pos[0], dtype=np.float64).copy()
        branches = _ik_branches(target)
        target_radius_cm = 100.0 * float(np.hypot(target[0], target[1]))
        target_angle_degrees = float(np.degrees(np.arctan2(target[1], target[0])))
        states: dict[str, dict | None] = {
            "first_entry": None,
            "minimum_distance": None,
            "first_interruption": None,
            "maximum_hold_run": None,
        }
        reward_total = 0.0
        step_count = 0
        success = False
        terminated = False
        truncated = False
        minimum_distance = float("inf")
        first_entry_step: int | None = None
        previous_held_steps = 0
        maximum_hold_run = 0
        post_entry_distances: list[float] = []
        hold_interruptions = 0
        while not (terminated or truncated):
            action = np.asarray(runtime.predict(observation), dtype=np.float64)
            observation, reward, terminated, truncated, info = env.step(action)
            step_count += 1
            reward_total += float(reward)
            held_steps = int(info["held_steps"])
            distance_cm = 100.0 * float(info["distance"])
            current_state = _state_metrics(
                env, target, branches, observation, action, held_steps
            )
            if distance_cm < minimum_distance:
                minimum_distance = distance_cm
                states["minimum_distance"] = current_state
            if held_steps > 0 and first_entry_step is None:
                first_entry_step = step_count
                states["first_entry"] = current_state
            if first_entry_step is not None:
                post_entry_distances.append(distance_cm)
            if held_steps > maximum_hold_run:
                maximum_hold_run = held_steps
                states["maximum_hold_run"] = current_state
            if previous_held_steps > 0 and held_steps == 0:
                hold_interruptions += 1
                if states["first_interruption"] is None:
                    states["first_interruption"] = current_state
            previous_held_steps = held_steps
            success = bool(info["is_success"])
        first_entry = states["first_entry"]
        traced.append(
            {
                "episode": episode_index,
                "episode_seed": seed + episode_index,
                "target_radius_cm": target_radius_cm,
                "target_angle_degrees": target_angle_degrees,
                "success": success,
                "failure_class": _episode_class(success, first_entry),
                "steps": step_count,
                "reward_total": reward_total,
                "first_reach_step": first_entry_step,
                "max_held_steps": maximum_hold_run,
                "hold_interruptions": hold_interruptions,
                "hold_distance_excursions_cm": {
                    "samples": len(post_entry_distances),
                    "maximum": _mean([max(post_entry_distances)])
                    if post_entry_distances
                    else None,
                    "mean": _mean(post_entry_distances),
                    "p95": _mean(
                        [np.percentile(post_entry_distances, 95)]
                    )
                    if post_entry_distances
                    else None,
                },
                "states": states,
            }
        )
    successes = sum(bool(episode["success"]) for episode in traced)
    grouped = {
        "success": [episode for episode in traced if episode["failure_class"] == "success"],
        "non_entry": [
            episode for episode in traced if episode["failure_class"] == "non_entry"
        ],
        "interrupted_hold": [
            episode
            for episode in traced
            if episode["failure_class"] == "interrupted_hold"
        ],
    }
    state_for_group = {
        "success": "first_entry",
        "non_entry": "minimum_distance",
        "interrupted_hold": "first_entry",
    }
    summaries = {
        group: _state_summary(episodes_in_group, state_for_group[group])
        for group, episodes_in_group in grouped.items()
    }
    return {
        "model": str(model_path),
        "episodes": episodes,
        "seed": seed,
        "successes": successes,
        "success_percent": 100.0 * successes / episodes,
        "group_summaries": summaries,
        "episodes_detail": traced,
    }


def _match_successes(result: dict) -> list[dict]:
    successes = [
        episode
        for episode in result["episodes_detail"]
        if episode["failure_class"] == "success"
    ]
    pairs = []
    for failure in result["episodes_detail"]:
        if failure["failure_class"] == "success":
            continue
        match = min(
            (candidate for candidate in successes if candidate["episode"] != failure["episode"]),
            key=lambda candidate: (
                ((candidate["target_angle_degrees"] - failure["target_angle_degrees"] + 180.0)
                 % 360.0 - 180.0)
                / 15.0
            )
            ** 2
            + ((candidate["target_radius_cm"] - failure["target_radius_cm"]) / 2.0)
            ** 2,
        )
        failure_state_name = (
            "minimum_distance"
            if failure["failure_class"] == "non_entry"
            else "first_entry"
        )
        failure_state = failure["states"][failure_state_name]
        success_state = match["states"]["first_entry"]
        pairs.append(
            {
                "failure_episode": failure["episode"],
                "failure_seed": failure["episode_seed"],
                "failure_class": failure["failure_class"],
                "matched_success_episode": match["episode"],
                "matched_success_seed": match["episode_seed"],
                "angle_difference_degrees": float(
                    (match["target_angle_degrees"] - failure["target_angle_degrees"] + 180.0)
                    % 360.0
                    - 180.0
                ),
                "radius_difference_cm": float(
                    match["target_radius_cm"] - failure["target_radius_cm"]
                ),
                "failure_selected_branch": failure_state["selected_branch"],
                "success_selected_branch": success_state["selected_branch"],
                "failure_jacobian_condition": failure_state["jacobian"]["condition"],
                "success_jacobian_condition": success_state["jacobian"]["condition"],
                "failure_joint_limit_margin_degrees": failure_state[
                    "joint_limit_margin_degrees"
                ],
                "success_joint_limit_margin_degrees": success_state[
                    "joint_limit_margin_degrees"
                ],
            }
        )
    return pairs


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="append", required=True)
    parser.add_argument("--episodes", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.episodes < 1 or args.seed < 0 or len(args.model) < 1:
        raise ValueError("episodes, seed, and model arguments are invalid")
    results = [
        _trace_candidate(Path(model), args.episodes, args.seed)
        for model in args.model
    ]
    for result in results:
        result["matched_success_pairs"] = _match_successes(result)
    outcome_agreement = None
    if len(results) >= 2:
        outcome_agreement = all(
            left["success"] == right["success"]
            for left, right in zip(
                results[0]["episodes_detail"],
                results[1]["episodes_detail"],
                strict=True,
            )
        )
    artifact = {
        "schema_version": 1,
        "measurement": "I1 branch and geometry conditioned trajectory diagnostic",
        "episodes": args.episodes,
        "seed": args.seed,
        "outcome_agreement_across_candidates": outcome_agreement,
        "candidates": results,
        "matching_method": {
            "successful_reference": "nearest successful episode by wrapped target angle and target radius",
            "angle_scale_degrees": 15.0,
            "radius_scale_cm": 2.0,
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
