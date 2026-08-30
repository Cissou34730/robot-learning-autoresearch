"""Scenario-owned research evaluation.

This module runs a model over the deterministic evaluation panel it is asked
for, records the observable signals this scenario chooses to expose, and
mechanically aggregates them. It draws no scientific conclusion: interpreting
the numbers is the researcher's job.

Which signals are captured is ordinary research code. Adding, removing or
replacing them requires no change to the generic AutoResearch core.
"""

import math
from collections.abc import Callable
from pathlib import Path

import numpy as np

from robot_learning.benchmark.final_contract import FINAL_SUCCESS_PERCENT
from robot_learning.scenario.environment import make_training_env
from robot_learning.training.algorithms import load_policy
from robot_learning.training.normalization import load_observation_normalizer

# Bumped when the meaning of a scenario evaluation summary changes.
RESEARCH_EVALUATION_SUMMARY_VERSION = 2

# Per-step `info` keys this scenario currently observes during evaluation.
OBSERVED_STEP_SIGNALS = ("distance", "held_steps")


def _series_statistics(values: list[float]) -> dict:
    series = np.asarray(values, dtype=float)
    return {
        "count": int(series.size),
        "mean": float(series.mean()),
        "std": float(series.std()),
        "min": float(series.min()),
        "max": float(series.max()),
        "final": float(series[-1]),
    }


def _distribution(values: list[float]) -> dict:
    series = np.asarray(values, dtype=float)
    return {
        "mean": float(series.mean()),
        "std": float(series.std()),
        "min": float(series.min()),
        "max": float(series.max()),
    }


def _action_statistics(actions: list[np.ndarray]) -> dict:
    recorded = np.asarray(actions, dtype=float)
    return {
        f"action_{dimension}": _distribution(list(column))
        for dimension, column in enumerate(recorded.T)
    }


def _aggregate_episodes(episode_results: list[dict]) -> dict:
    def over_episodes(read: Callable[[dict], float]) -> dict:
        return _distribution([read(episode) for episode in episode_results])

    def names_of(section: str) -> list[str]:
        return sorted(
            {name for episode in episode_results for name in episode[section]}
        )

    return {
        "steps": over_episodes(lambda episode: episode["steps"]),
        "reward_total": over_episodes(lambda episode: episode["reward_total"]),
        "reward_components": {
            name: over_episodes(
                lambda episode, name=name: episode["reward_components"].get(name, 0.0)
            )
            for name in names_of("reward_components")
        },
        "metrics": {
            name: {
                statistic: over_episodes(
                    lambda episode, name=name, statistic=statistic: episode["metrics"][
                        name
                    ][statistic]
                )
                for statistic in ("mean", "std", "min", "max", "final")
            }
            for name in names_of("metrics")
        },
        "actions": {
            name: {
                statistic: over_episodes(
                    lambda episode, name=name, statistic=statistic: episode["actions"][
                        name
                    ][statistic]
                )
                for statistic in ("mean", "std", "min", "max")
            }
            for name in names_of("actions")
        },
    }


def evaluate_research_model(
    model_path: Path,
    *,
    episodes: int,
    seed: int,
    algorithm: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict:
    """Measure one model over the requested deterministic evaluation panel."""
    if episodes < 1:
        raise ValueError("an evaluation panel requires at least one episode")
    model = load_policy(model_path, algorithm)
    env = make_training_env()
    normalize_obs = load_observation_normalizer(model_path)

    episode_results: list[dict] = []
    for episode in range(episodes):
        obs, _ = env.reset(seed=seed + episode)
        target_x, target_y = (float(value) for value in env.data.mocap_pos[0][:2])
        series: dict[str, list[float]] = {name: [] for name in OBSERVED_STEP_SIGNALS}
        actions: list[np.ndarray] = []
        reward_components: dict[str, float] = {}
        reward_total = 0.0
        steps = 0
        terminated = False
        truncated = False
        while not (terminated or truncated):
            normalized_obs = normalize_obs(obs) if normalize_obs is not None else obs
            action, _ = model.predict(normalized_obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            actions.append(np.ravel(np.asarray(action, dtype=float)))
            for name in OBSERVED_STEP_SIGNALS:
                series[name].append(float(info[name]))
            for name, value in info.get("reward_components", {}).items():
                reward_components[name] = reward_components.get(name, 0.0) + float(
                    value
                )

        episode_results.append(
            {
                "episode": episode,
                "episode_seed": seed + episode,
                "success": bool(terminated),
                "steps": steps,
                "terminated": bool(terminated),
                "truncated": bool(truncated),
                "target_radius_cm": 100 * math.hypot(target_x, target_y),
                "target_angle_degrees": math.degrees(math.atan2(target_y, target_x)),
                "reward_total": reward_total,
                "reward_components": reward_components,
                "metrics": {
                    name: _series_statistics(values) for name, values in series.items()
                },
                "actions": _action_statistics(actions),
            }
        )
        if progress_callback is not None:
            progress_callback(episode + 1, episodes)

    successes = sum(episode["success"] for episode in episode_results)
    return {
        "schema_version": 4,
        "model": str(model_path),
        "episodes": episodes,
        "seed": seed,
        "official_benchmark": False,
        "success_percent": 100 * successes / episodes,
        "aggregate_metrics": _aggregate_episodes(episode_results),
        "episode_results": episode_results,
    }


def summarize_research_evaluations(
    evaluations: list[dict],
    summary_version: int = RESEARCH_EVALUATION_SUMMARY_VERSION,
) -> dict:
    """Consolidate several completed evaluation panels for the same model.

    Only the primary task outcome is pooled here; the detailed measurements stay
    in each evaluation artifact and are not duplicated into this summary.
    """
    if not evaluations:
        raise ValueError("an evaluation summary requires at least one evaluation")
    total_episodes = sum(int(item["episodes"]) for item in evaluations)
    total_successes = sum(
        float(item["success_percent"]) * int(item["episodes"]) / 100
        for item in evaluations
    )
    seed_success = {
        str(item["seed"]): float(item["success_percent"]) for item in evaluations
    }
    pooled_success = 100 * total_successes / total_episodes
    return {
        "schema_version": 2,
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
    }
