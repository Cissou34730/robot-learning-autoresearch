"""Evaluate the M3 reflection controller on the held-out development panel."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from robot_learning.policy_runtime import load_runtime
from robot_learning.scenario.environment import make_evaluation_env

MAX_EPISODE_STEPS = 500
CONTROL_DT_SECONDS = 0.02


def _reflection_observation(observation: np.ndarray) -> np.ndarray:
    reflected = np.asarray(observation, dtype=np.float32).copy()
    reflected[:4] *= -1.0
    reflected[4:7] *= np.array([1.0, -1.0, 1.0], dtype=np.float32)
    reflected[7:11] = -observation[[9, 10, 7, 8]]
    return reflected


def _run_episode(runtime, env, *, seed: int, wrapped: bool) -> dict:
    env.reset(seed=seed)
    runtime.reset()
    target = np.asarray(env.data.mocap_pos[0], dtype=np.float64)
    reflection_sign = -1.0 if target[1] < 0.0 else 1.0
    observation = env._observation()
    reward_total = 0.0
    first_reach_step = None
    max_held_steps = 0
    in_tolerance_steps = 0
    hold_interruptions = 0
    was_in_tolerance = False
    min_distance_cm = float("inf")
    final_distance_cm = float("nan")
    peak_endpoint_speed_cm_s = 0.0
    peak_action_abs = 0.0
    pre_reach_peak_action_abs = 0.0
    post_reach_peak_action_abs = 0.0
    previous_endpoint = env._end_effector_position()
    terminated = False
    truncated = False

    for step in range(1, MAX_EPISODE_STEPS + 1):
        policy_observation = (
            _reflection_observation(observation)
            if wrapped and reflection_sign < 0.0
            else observation
        )
        policy_action = np.asarray(
            runtime.predict(policy_observation), dtype=np.float64
        )
        action = (
            reflection_sign * policy_action
            if wrapped and reflection_sign < 0.0
            else policy_action
        )
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
        final_distance_cm = distance_cm
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
        if terminated or truncated:
            break

    if first_reach_step is None:
        outcome_class = "never_reached"
    elif not terminated:
        outcome_class = "reached_but_hold_broken"
    else:
        outcome_class = "success"
    return {
        "seed": seed,
        "wrapped": wrapped,
        "target_radius_cm": float(np.hypot(target[0], target[1]) * 100.0),
        "target_angle_degrees": float(np.degrees(np.arctan2(target[1], target[0]))),
        "success": bool(terminated),
        "outcome_class": outcome_class,
        "steps": step,
        "reward_total": reward_total,
        "min_distance_cm": min_distance_cm,
        "final_distance_cm": final_distance_cm,
        "first_reach_step": first_reach_step,
        "max_held_steps": max_held_steps,
        "in_tolerance_steps": in_tolerance_steps,
        "hold_interruptions": hold_interruptions,
        "peak_endpoint_speed_cm_s": peak_endpoint_speed_cm_s,
        "peak_action_abs": peak_action_abs,
        "pre_reach_peak_action_abs": pre_reach_peak_action_abs,
        "post_reach_peak_action_abs": post_reach_peak_action_abs,
    }


def run(model_path: Path, artifact_path: Path, seed: int, episodes: int) -> None:
    runtime = load_runtime(model_path)
    env = make_evaluation_env(policy_runtime=runtime)
    results = []
    for episode_seed in range(seed, seed + episodes):
        results.append(
            _run_episode(runtime, env, seed=episode_seed, wrapped=False)
        )
        results.append(
            _run_episode(runtime, env, seed=episode_seed, wrapped=True)
        )

    def summarize(items: list[dict]) -> dict:
        return {
            "episodes": len(items),
            "successes": sum(item["success"] for item in items),
            "success_percent": 100.0
            * sum(item["success"] for item in items)
            / len(items),
            "never_reached": sum(
                item["outcome_class"] == "never_reached" for item in items
            ),
            "reached_but_hold_broken": sum(
                item["outcome_class"] == "reached_but_hold_broken"
                for item in items
            ),
        }

    baseline = [item for item in results if not item["wrapped"]]
    wrapped = [item for item in results if item["wrapped"]]
    artifact = {
        "schema_version": 1,
        "measurement": "reflection_wrapped_heldout",
        "model": str(model_path),
        "seed": seed,
        "episodes_per_controller": episodes,
        "control_dt_seconds": CONTROL_DT_SECONDS,
        "max_episode_steps": MAX_EPISODE_STEPS,
        "summary": {
            "baseline": summarize(baseline),
            "wrapped": summarize(wrapped),
            "negative_baseline": summarize(
                [item for item in baseline if item["target_angle_degrees"] < 0.0]
            ),
            "negative_wrapped": summarize(
                [item for item in wrapped if item["target_angle_degrees"] < 0.0]
            ),
        },
        "episodes": results,
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=4200)
    parser.add_argument("--episodes", type=int, default=160)
    args = parser.parse_args()
    run(args.model, args.artifact, args.seed, args.episodes)


if __name__ == "__main__":
    main()
