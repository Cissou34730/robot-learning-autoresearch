"""Scenario-owned research evaluation.

Everything about what is measured and what the numbers mean belongs here. The
generic CLI and runner only move the returned dictionary around.
"""

import math
from collections.abc import Callable
from pathlib import Path

import numpy as np

from robot_learning.benchmark.final_contract import FINAL_SUCCESS_PERCENT
from robot_learning.benchmark.metrics import (
    episode_hold_progress,
    milestone_steps,
    summarize_hold_progress,
)
from robot_learning.benchmark.spec import HOLD_SECONDS
from robot_learning.scenario.environment import make_training_env
from robot_learning.training.algorithms import load_policy
from robot_learning.training.normalization import load_observation_normalizer

# Bumped when the meaning of a scenario evaluation summary changes.
RESEARCH_EVALUATION_SUMMARY_VERSION = 1


def evaluate_research_model(
    model_path: Path,
    *,
    episodes: int,
    seed: int,
    algorithm: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict:
    model = load_policy(model_path, algorithm)
    env = make_training_env()
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
        "official_benchmark": False,
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


def summarize_research_evaluations(
    evaluations: list[dict],
    summary_version: int = RESEARCH_EVALUATION_SUMMARY_VERSION,
) -> dict:
    """Pool several scenario evaluations into the compact summary the runner stores.

    The runner treats the result as opaque apart from episode counts, seeds and
    success percentages; every hold/tolerance field below is scenario semantics.
    """
    if not evaluations:
        raise ValueError("an evaluation summary requires at least one evaluation")
    total_episodes = sum(int(item["episodes"]) for item in evaluations)
    total_successes = sum(
        float(item["success_percent"]) * int(item["episodes"]) / 100
        for item in evaluations
    )
    total_failures = sum(
        int(item["failed_episode_progress"]["failed_episodes"]) for item in evaluations
    )
    required = int(evaluations[0]["failed_episode_progress"]["required_steps"])

    def failure_weighted_mean(field: str, perfect: float) -> float:
        if not total_failures:
            return perfect
        return (
            sum(
                float(item["failed_episode_progress"][field])
                * int(item["failed_episode_progress"]["failed_episodes"])
                for item in evaluations
            )
            / total_failures
        )

    seed_success = {
        str(item["seed"]): float(item["success_percent"]) for item in evaluations
    }
    failed_diagnostics = [
        {key: value for key, value in episode.items() if key != "distance_trace_cm"}
        for evaluation in evaluations
        for episode in evaluation.get("episode_results", [])
        if not episode["success"]
    ]
    failed_diagnostics.sort(
        key=lambda item: (
            item["longest_consecutive_steps"],
            item["best_window_inside_steps"],
            -item["best_window_excess_cm"],
        )
    )
    pooled_success = 100 * total_successes / total_episodes
    return {
        "schema_version": 1,
        "evaluation_summary_version": summary_version,
        "episodes": total_episodes,
        "seed_count": len(evaluations),
        "seed_success_percent": seed_success,
        # Historical field name; the threshold is the scenario success contract.
        "seeds_passing_98_percent": sum(
            success >= FINAL_SUCCESS_PERCENT for success in seed_success.values()
        ),
        "worst_seed_success_percent": min(seed_success.values()),
        "pooled_success_percent": pooled_success,
        "success_percent": pooled_success,
        "failed_episode_progress": {
            "failed_episodes": total_failures,
            "longest_consecutive_steps_mean": failure_weighted_mean(
                "longest_consecutive_steps_mean", float(required)
            ),
            "best_window_inside_steps_mean": failure_weighted_mean(
                "best_window_inside_steps_mean", float(required)
            ),
            "best_window_excess_cm_mean": failure_weighted_mean(
                "best_window_excess_cm_mean", 0.0
            ),
            "required_steps": required,
        },
        "failure_diagnostics": failed_diagnostics,
    }
