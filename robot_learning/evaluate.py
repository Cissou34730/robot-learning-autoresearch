import argparse
import json
import math
from collections.abc import Callable
from pathlib import Path

import numpy as np

from robot_learning.benchmark.final_benchmark import (
    evaluate_final_model,
)
from robot_learning.benchmark.metrics import (
    episode_hold_progress,
    milestone_steps,
    summarize_hold_progress,
)
from robot_learning.benchmark.spec import (
    EVALUATION_EPISODES,
    EVALUATION_SEED,
    HOLD_SECONDS,
)
from robot_learning.environments.reach_env import TwoJointArmReachEnv
from robot_learning.training.algorithms import load_policy
from robot_learning.training.normalization import load_observation_normalizer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a trained robot policy")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--algorithm", default=None)
    parser.add_argument("--episodes", type=int, default=EVALUATION_EPISODES)
    parser.add_argument("--seed", type=int, default=EVALUATION_SEED)
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--progress-json", type=Path, default=None)
    parser.add_argument("--official-benchmark", action="store_true")
    return parser.parse_args()


def evaluate_model(
    model_path: Path,
    episodes: int = EVALUATION_EPISODES,
    seed: int = EVALUATION_SEED,
    algorithm: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
    official_benchmark: bool = False,
) -> dict:
    if official_benchmark:
        return evaluate_final_model(model_path, algorithm=algorithm, progress_callback=progress_callback)
    model = load_policy(model_path, algorithm)
    env = TwoJointArmReachEnv()
    normalize_obs = load_observation_normalizer(model_path)

    successes = 0
    episode_progress: list[dict] = []
    final_distances: list[float] = []
    episode_results: list[dict] = []
    control_dt = env.model.opt.timestep * env.frame_skip
    required_hold_steps = milestone_steps(HOLD_SECONDS, control_dt)
    for episode in range(episodes):
        obs, _ = env.reset(seed=seed + episode)
        target_x, target_y = (float(value) for value in env.data.mocap_pos[0][:2])
        target_radius_cm = 100 * math.hypot(target_x, target_y)
        target_angle_degrees = math.degrees(math.atan2(target_y, target_x))
        distances: list[float] = []
        done = False
        while not done:
            normalized_obs = normalize_obs(obs) if normalize_obs is not None else obs
            action, _ = model.predict(normalized_obs, deterministic=True)
            obs, _, terminated, truncated, info = env.step(action)
            distances.append(float(info["distance"]))
            done = terminated or truncated
        progress = episode_hold_progress(
            distances, required_hold_steps, env.success_threshold
        )
        successes += progress["success"]
        episode_progress.append(progress)
        final_distances.append(distances[-1])
        episode_result = {
            "episode": episode,
            "episode_seed": seed + episode,
            "success": bool(progress["success"]),
            "target_radius_cm": target_radius_cm,
            "target_angle_degrees": target_angle_degrees,
            "longest_consecutive_steps": progress["longest_consecutive_steps"],
            "best_window_inside_steps": progress["best_window_inside_steps"],
            "best_window_excess_cm": progress["best_window_excess_cm"],
            "final_distance_cm": 100 * distances[-1],
        }
        if not progress["success"]:
            episode_result["distance_trace_cm"] = [
                100 * distance for distance in distances
            ]
        episode_results.append(episode_result)
        if progress_callback is not None:
            progress_callback(episode + 1, episodes)

    return {
        "schema_version": 3,
        "model": str(model_path),
        "episodes": episodes,
        "seed": seed,
        "official_benchmark": official_benchmark,
        "success_percent": 100 * successes / episodes,
        "failed_episode_progress": summarize_hold_progress(
            episode_progress, required_hold_steps
        ),
        "episode_results": episode_results,
        "final_distance_cm": {
            "mean": float(np.mean(final_distances) * 100),
            "median": float(np.median(final_distances) * 100),
            "worst": float(np.max(final_distances) * 100),
        },
    }


def write_progress(path: Path, completed: int, total: int) -> bool:
    """Write best-effort telemetry without risking the evaluation itself."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"completed": completed, "total": total}) + "\n",
            encoding="utf-8",
        )
    except OSError:
        # Progress is only a heartbeat. The final evaluation result remains the
        # authoritative output and must not fail because Windows briefly locks
        # this file while the parent process reads it.
        return False
    return True


def main() -> None:
    args = parse_args()

    def report_progress(completed: int, total: int) -> None:
        if args.progress_json is None:
            return
        write_progress(args.progress_json, completed, total)

    result = evaluate_model(
        args.model,
        episodes=args.episodes,
        seed=args.seed,
        algorithm=args.algorithm,
        progress_callback=report_progress,
        official_benchmark=args.official_benchmark,
    )
    output = json.dumps(result, indent=2)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
