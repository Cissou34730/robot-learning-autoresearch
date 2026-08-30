"""Scenario-owned research evaluation.

This module runs a model over the deterministic evaluation panel it is asked
for and records the minimal factual outcome of every episode. It draws no
scientific conclusion and preselects no behavioral metric.

Anything else the current research question needs goes into `research_evidence`,
an opaque channel owned by the researcher. Filling, replacing or emptying it is
ordinary research code and requires no change to the generic AutoResearch core,
which never interprets its contents.
"""

from collections.abc import Callable
from pathlib import Path

from robot_learning.scenario.environment import make_training_env
from robot_learning.training.algorithms import load_policy
from robot_learning.training.normalization import load_observation_normalizer

# Bumped when the meaning of a scenario evaluation summary changes.
RESEARCH_EVALUATION_SUMMARY_VERSION = 3


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
        reward_total = 0.0
        steps = 0
        success = False
        terminated = False
        truncated = False
        while not (terminated or truncated):
            normalized_obs = normalize_obs(obs) if normalize_obs is not None else obs
            action, _ = model.predict(normalized_obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            if "is_success" in info:
                success = bool(info["is_success"])

        episode_results.append(
            {
                "episode": episode,
                "episode_seed": seed + episode,
                # Scenario task outcome, not Gymnasium termination.
                "success": success,
                "reward_total": reward_total,
                "steps": steps,
                "terminated": bool(terminated),
                "truncated": bool(truncated),
            }
        )
        if progress_callback is not None:
            progress_callback(episode + 1, episodes)

    successes = sum(episode["success"] for episode in episode_results)
    return {
        "schema_version": 5,
        "model": str(model_path),
        "episodes": episodes,
        "seed": seed,
        "official_benchmark": False,
        "success_percent": 100 * successes / episodes,
        "episode_results": episode_results,
        # Researcher-owned evidence for the current question. Empty until this
        # module is instrumented; the generic core never reads inside it.
        "research_evidence": {},
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
        "schema_version": 3,
        "evaluation_summary_version": summary_version,
        "episodes": total_episodes,
        "seed_count": len(evaluations),
        "seed_success_percent": seed_success,
        "worst_seed_success_percent": min(seed_success.values()),
        "pooled_success_percent": pooled_success,
        "success_percent": pooled_success,
    }
