"""Matched baseline and reflection-equivariant policy diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from robot_learning.policy_runtime import load_runtime
from robot_learning.scenario.environment import TwoJointArmReachEnv

TARGET_RADII_CM = (8.0, 12.0, 16.0, 19.0)
TARGET_ANGLE_MAGNITUDES_DEGREES = (120.0, 130.0, 140.0, 150.0)
MAX_EPISODE_STEPS = 500
CONTROL_DT_SECONDS = 0.02


def _reflection_observation(observation: np.ndarray) -> np.ndarray:
    """Reflect physical state and swap the two inverse-kinematic branches."""
    observation = np.asarray(observation, dtype=np.float32)
    if observation.shape != (11,):
        raise ValueError(f"expected an 11-value observation, got {observation.shape}")
    reflected = observation.copy()
    reflected[:4] *= -1.0
    reflected[4:7] *= np.array([1.0, -1.0, 1.0], dtype=np.float32)
    reflected[7:11] = -observation[[9, 10, 7, 8]]
    return reflected


def _reflection_action(action: np.ndarray) -> np.ndarray:
    return -np.asarray(action, dtype=np.float64)


def _target_position(radius_cm: float, angle_degrees: float, z: float) -> np.ndarray:
    angle = np.deg2rad(angle_degrees)
    radius_m = radius_cm / 100.0
    return np.array(
        [radius_m * np.cos(angle), radius_m * np.sin(angle), z],
        dtype=np.float64,
    )


def _mean_norm(values: list[np.ndarray]) -> float:
    if not values:
        return 0.0
    return float(np.mean([np.linalg.norm(value) for value in values]))


def _run_episode(
    runtime,
    env: TwoJointArmReachEnv,
    *,
    radius_cm: float,
    angle_degrees: float,
    seed: int,
    controller: str,
) -> dict:
    if controller not in {"baseline", "reflection_equivariant"}:
        raise ValueError(f"unsupported controller: {controller}")

    env.reset(seed=seed)
    target = _target_position(
        radius_cm,
        angle_degrees,
        float(env._end_effector_position()[2]),
    )
    env.data.mocap_pos[0] = target
    mujoco.mj_forward(env.model, env.data)
    env._previous_distance = env._distance_to_target()
    runtime.reset()
    observation = env._observation()
    initial_observation = observation.copy()
    initial_policy_observation = (
        _reflection_observation(observation)
        if controller == "reflection_equivariant"
        else observation.copy()
    )
    initial_action = None
    initial_policy_action = None
    previous_endpoint = env._end_effector_position()
    trajectory: list[dict] = []
    first_reach_step = None
    max_held_steps = 0
    in_tolerance_steps = 0
    hold_interruptions = 0
    was_in_tolerance = False
    min_distance_cm = float("inf")
    peak_endpoint_speed_cm_s = 0.0
    peak_action_abs = 0.0
    pre_reach_peak_action_abs = 0.0
    post_reach_peak_action_abs = 0.0
    terminated = False
    truncated = False
    reward_total = 0.0

    for step in range(1, MAX_EPISODE_STEPS + 1):
        policy_observation = (
            _reflection_observation(observation)
            if controller == "reflection_equivariant"
            else observation
        )
        policy_action = np.asarray(
            runtime.predict(policy_observation), dtype=np.float64
        )
        action = (
            _reflection_action(policy_action)
            if controller == "reflection_equivariant"
            else policy_action
        )
        action = np.clip(action, env.action_space.low, env.action_space.high)
        if initial_action is None:
            initial_action = action.copy()
            initial_policy_action = policy_action.copy()
        observation, reward, terminated, truncated, info = env.step(action)
        reward_total += float(reward)
        distance_cm = 100.0 * float(info["distance"])
        held_steps = int(info["held_steps"])
        endpoint = env._end_effector_position()
        endpoint_speed_cm_s = (
            100.0
            * float(np.linalg.norm(endpoint - previous_endpoint))
            / CONTROL_DT_SECONDS
        )
        previous_endpoint = endpoint.copy()
        min_distance_cm = min(min_distance_cm, distance_cm)
        peak_endpoint_speed_cm_s = max(
            peak_endpoint_speed_cm_s, endpoint_speed_cm_s
        )
        action_abs = float(np.max(np.abs(action)))
        peak_action_abs = max(peak_action_abs, action_abs)
        if held_steps > 0:
            in_tolerance_steps += 1
            if first_reach_step is None:
                first_reach_step = step
            post_reach_peak_action_abs = max(post_reach_peak_action_abs, action_abs)
        else:
            if was_in_tolerance:
                hold_interruptions += 1
            if first_reach_step is None:
                pre_reach_peak_action_abs = max(pre_reach_peak_action_abs, action_abs)
        max_held_steps = max(max_held_steps, held_steps)
        was_in_tolerance = held_steps > 0
        trajectory.append(
            {
                "step": step,
                "action": action.astype(float).tolist(),
                "policy_action": policy_action.astype(float).tolist(),
                "policy_observation": policy_observation.astype(float).tolist(),
                "qpos": env.data.qpos.astype(float).tolist(),
                "qvel": env.data.qvel.astype(float).tolist(),
                "distance_cm": distance_cm,
                "endpoint_speed_cm_s": endpoint_speed_cm_s,
                "held_steps": held_steps,
                "branch_residuals": observation[7:11].astype(float).tolist(),
            }
        )
        if terminated or truncated:
            break

    if first_reach_step is None:
        outcome_class = "never_reached"
    elif not terminated:
        outcome_class = "reached_but_hold_broken"
    else:
        outcome_class = "success"
    return {
        "controller": controller,
        "radius_cm": radius_cm,
        "angle_degrees": angle_degrees,
        "seed": seed,
        "success": bool(terminated),
        "outcome_class": outcome_class,
        "steps": len(trajectory),
        "reward_total": reward_total,
        "first_reach_step": first_reach_step,
        "max_held_steps": max_held_steps,
        "in_tolerance_steps": in_tolerance_steps,
        "hold_interruptions": hold_interruptions,
        "min_distance_cm": min_distance_cm,
        "final_distance_cm": trajectory[-1]["distance_cm"],
        "peak_endpoint_speed_cm_s": peak_endpoint_speed_cm_s,
        "peak_action_abs": peak_action_abs,
        "pre_reach_peak_action_abs": pre_reach_peak_action_abs,
        "post_reach_peak_action_abs": post_reach_peak_action_abs,
        "initial_observation": initial_observation.astype(float).tolist(),
        "initial_policy_observation": initial_policy_observation.astype(float).tolist(),
        "initial_action": initial_action.astype(float).tolist(),
        "initial_policy_action": initial_policy_action.astype(float).tolist(),
        "trajectory": trajectory,
    }


def _trajectory_pair_errors(
    negative: dict, positive: dict, *, reflect_negative: bool
) -> dict:
    negative_trajectory = negative["trajectory"]
    positive_trajectory = positive["trajectory"]
    shared_steps = min(len(negative_trajectory), len(positive_trajectory))
    action_errors = []
    joint_errors = []
    distance_errors = []
    for index in range(shared_steps):
        negative_step = negative_trajectory[index]
        positive_step = positive_trajectory[index]
        negative_action = np.asarray(negative_step["action"])
        negative_qpos = np.asarray(negative_step["qpos"])
        if reflect_negative:
            negative_action = -negative_action
            negative_qpos = -negative_qpos
        action_errors.append(negative_action + np.asarray(positive_step["action"]))
        joint_errors.append(negative_qpos + np.asarray(positive_step["qpos"]))
        distance_errors.append(
            abs(
                float(negative_step["distance_cm"])
                - float(positive_step["distance_cm"])
            )
        )
    return {
        "trajectory_action_reflection_error": _mean_norm(action_errors),
        "trajectory_joint_reflection_error": _mean_norm(joint_errors),
        "trajectory_distance_difference_cm": (
            float(np.mean(distance_errors)) if distance_errors else 0.0
        ),
        "shared_trajectory_steps": shared_steps,
    }


def _pair_diagnostics(
    negative: dict, positive: dict, canonical_negative: dict
) -> dict:
    negative_observation = np.asarray(negative["initial_observation"])
    positive_observation = np.asarray(positive["initial_observation"])
    canonical_observation = np.asarray(
        canonical_negative["initial_policy_observation"]
    )
    baseline_initial_action_error = np.asarray(negative["initial_action"]) + np.asarray(
        positive["initial_action"]
    )
    canonical_initial_action_error = np.asarray(
        canonical_negative["initial_action"]
    ) + np.asarray(positive["initial_action"])
    baseline_errors = _trajectory_pair_errors(
        negative, positive, reflect_negative=False
    )
    canonical_errors = _trajectory_pair_errors(
        canonical_negative, positive, reflect_negative=True
    )
    return {
        "radius_cm": negative["radius_cm"],
        "angle_magnitude_degrees": abs(negative["angle_degrees"]),
        "negative_episode_seed": negative["seed"],
        "positive_episode_seed": positive["seed"],
        "canonical_negative_episode_seed": canonical_negative["seed"],
        "negative_success": negative["success"],
        "positive_success": positive["success"],
        "canonical_negative_success": canonical_negative["success"],
        "negative_outcome_class": negative["outcome_class"],
        "positive_outcome_class": positive["outcome_class"],
        "canonical_negative_outcome_class": canonical_negative["outcome_class"],
        "negative_first_reach_step": negative["first_reach_step"],
        "positive_first_reach_step": positive["first_reach_step"],
        "canonical_negative_first_reach_step": canonical_negative[
            "first_reach_step"
        ],
        "negative_max_held_steps": negative["max_held_steps"],
        "positive_max_held_steps": positive["max_held_steps"],
        "canonical_negative_max_held_steps": canonical_negative["max_held_steps"],
        "initial_observation_reflection_error": float(
            np.linalg.norm(negative_observation - _reflection_observation(positive_observation))
        ),
        "canonical_initial_observation_reflection_error": float(
            np.linalg.norm(canonical_observation - positive_observation)
        ),
        "initial_action_reflection_error": float(
            np.linalg.norm(baseline_initial_action_error)
        ),
        "canonical_initial_action_reflection_error": float(
            np.linalg.norm(canonical_initial_action_error)
        ),
        "baseline": baseline_errors,
        "reflection_equivariant": canonical_errors,
    }


def run(model_path: Path, artifact_path: Path, seed: int) -> None:
    runtime = load_runtime(model_path)
    env = TwoJointArmReachEnv(
        max_episode_steps=MAX_EPISODE_STEPS,
        policy_runtime=runtime,
    )
    episodes = []
    pairs = []
    for pair_index, (radius_cm, angle_magnitude) in enumerate(
        (radius, magnitude)
        for radius in TARGET_RADII_CM
        for magnitude in TARGET_ANGLE_MAGNITUDES_DEGREES
    ):
        pair_seed = seed + pair_index
        negative = _run_episode(
            runtime,
            env,
            radius_cm=radius_cm,
            angle_degrees=-angle_magnitude,
            seed=pair_seed,
            controller="baseline",
        )
        positive = _run_episode(
            runtime,
            env,
            radius_cm=radius_cm,
            angle_degrees=angle_magnitude,
            seed=pair_seed,
            controller="baseline",
        )
        canonical_negative = _run_episode(
            runtime,
            env,
            radius_cm=radius_cm,
            angle_degrees=-angle_magnitude,
            seed=pair_seed,
            controller="reflection_equivariant",
        )
        episodes.extend((negative, positive, canonical_negative))
        pairs.append(_pair_diagnostics(negative, positive, canonical_negative))

    negative_episodes = [
        item
        for item in episodes
        if item["angle_degrees"] < 0 and item["controller"] == "baseline"
    ]
    positive_episodes = [
        item
        for item in episodes
        if item["angle_degrees"] > 0
    ]
    canonical_negative_episodes = [
        item
        for item in episodes
        if item["controller"] == "reflection_equivariant"
    ]
    result = {
        "schema_version": 1,
        "measurement": "representation_control_comparison",
        "model": str(model_path),
        "seed": seed,
        "panel": {
            "radii_cm": list(TARGET_RADII_CM),
            "angle_magnitudes_degrees": list(TARGET_ANGLE_MAGNITUDES_DEGREES),
            "episodes_per_condition": len(negative_episodes),
            "total_episodes": len(episodes),
            "control_dt_seconds": CONTROL_DT_SECONDS,
            "max_episode_steps": MAX_EPISODE_STEPS,
            "conditions": [
                "baseline_negative",
                "baseline_positive",
                "reflection_equivariant_negative",
            ],
        },
        "summary": {
            "baseline_negative_successes": sum(
                item["success"] for item in negative_episodes
            ),
            "baseline_positive_successes": sum(
                item["success"] for item in positive_episodes
            ),
            "reflection_equivariant_negative_successes": sum(
                item["success"] for item in canonical_negative_episodes
            ),
            "baseline_negative_never_reached": sum(
                item["outcome_class"] == "never_reached"
                for item in negative_episodes
            ),
            "reflection_equivariant_negative_never_reached": sum(
                item["outcome_class"] == "never_reached"
                for item in canonical_negative_episodes
            ),
            "baseline_negative_reached_but_hold_broken": sum(
                item["outcome_class"] == "reached_but_hold_broken"
                for item in negative_episodes
            ),
            "reflection_equivariant_negative_reached_but_hold_broken": sum(
                item["outcome_class"] == "reached_but_hold_broken"
                for item in canonical_negative_episodes
            ),
        },
        "matched_pairs": pairs,
        "episodes": episodes,
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(result, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=9200)
    args = parser.parse_args()
    run(args.model, args.artifact, args.seed)


if __name__ == "__main__":
    main()
