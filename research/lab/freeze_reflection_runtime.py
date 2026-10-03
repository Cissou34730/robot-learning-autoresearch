"""Freeze the validated M3 reflection wrapper around an existing policy."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np

from robot_learning.policy_runtime import (
    load_runtime,
    save_runtime,
    validate_runtime_files,
)
from robot_learning.scenario.environment import make_evaluation_env
from robot_learning.scenario.policy_io import make_policy_io
from robot_learning.training.algorithms import load_policy
from robot_learning.training.normalization import load_observation_normalizer

CONTROL_DT_SECONDS = 0.02
MAX_EPISODE_STEPS = 500
INFERENCE_FILES = ("model.zip", "artifact.json", "vecnormalize.pkl")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _complete_artifact(path: Path) -> None:
    for filename in (*INFERENCE_FILES, "policy_runtime.pkl"):
        if not (path / filename).is_file():
            raise ValueError(f"frozen artifact is missing {path / filename}")


def _freeze(source: Path, destination: Path) -> None:
    source = source.resolve()
    destination = destination.resolve()
    _complete_artifact(source)
    source_metadata = json.loads(
        (source / "artifact.json").read_text(encoding="utf-8")
    )
    expected_source_hash = _sha256(source / "model.zip")

    if destination.exists():
        _complete_artifact(destination)
        metadata = json.loads(
            (destination / "artifact.json").read_text(encoding="utf-8")
        )
        if (
            metadata.get("frozen_wrapper") != "m3_reflection"
            or metadata.get("source_model_sha256") != expected_source_hash
        ):
            raise ValueError(f"existing destination is not the requested artifact: {destination}")
        validate_runtime_files(destination / "model.zip")
        return

    staging = destination.with_name(f".{destination.name}.tmp")
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(source, staging)
    metadata = {
        **source_metadata,
        "frozen_wrapper": "m3_reflection",
        "source_artifact": str(source),
        "source_model_sha256": expected_source_hash,
    }
    (staging / "artifact.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    model_path = staging / "model.zip"
    stats_path = staging / "vecnormalize.pkl"
    save_runtime(
        model_path,
        policy_io=make_policy_io(),
        loader=load_policy,
        normalizer=load_observation_normalizer(model_path),
        stats_path=stats_path,
    )
    _complete_artifact(staging)
    validate_runtime_files(model_path)
    staging.replace(destination)


def _run_episode(runtime, env, *, seed: int) -> dict:
    observation, _ = env.reset(seed=seed)
    runtime.reset()
    target = np.asarray(env.data.mocap_pos[0], dtype=np.float64)
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
        action = np.asarray(runtime.predict(observation), dtype=np.float64)
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


def _summarize(items: list[dict]) -> dict:
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
            item["outcome_class"] == "reached_but_hold_broken" for item in items
        ),
    }


def run(
    source: Path,
    destination: Path,
    artifact_path: Path,
    seed: int,
    episodes: int,
) -> None:
    _freeze(source, destination)
    model_path = destination / "model.zip"
    runtime = load_runtime(model_path)
    env = make_evaluation_env(policy_runtime=runtime)
    results = [
        _run_episode(runtime, env, seed=episode_seed)
        for episode_seed in range(seed, seed + episodes)
    ]
    negative = [item for item in results if item["target_angle_degrees"] < 0.0]
    artifact = {
        "schema_version": 1,
        "measurement": "frozen_reflection_runtime_heldout",
        "source_artifact": str(source),
        "frozen_artifact": str(destination),
        "frozen_model_sha256": _sha256(model_path),
        "frozen_runtime_sha256": _sha256(destination / "policy_runtime.pkl"),
        "frozen_wrapper": "m3_reflection",
        "seed": seed,
        "episodes": episodes,
        "control_dt_seconds": CONTROL_DT_SECONDS,
        "max_episode_steps": MAX_EPISODE_STEPS,
        "summary": _summarize(results),
        "negative_angle_summary": _summarize(negative),
        "episodes_diagnostics": results,
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=4200)
    parser.add_argument("--episodes", type=int, default=160)
    args = parser.parse_args()
    run(args.source, args.destination, args.artifact, args.seed, args.episodes)


if __name__ == "__main__":
    main()
