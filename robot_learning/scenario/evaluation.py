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
from itertools import pairwise
from pathlib import Path

import numpy as np

from robot_learning.paired_evidence import episode_outcomes
from robot_learning.policy_runtime import load_runtime
from robot_learning.scenario.environment import make_evaluation_env

# Bumped when the meaning of a scenario evaluation summary changes.
RESEARCH_EVALUATION_SUMMARY_VERSION = 4


def _mean(values: list[float]) -> float | None:
    return None if not values else float(np.mean(values))


def _group_summary(
    diagnostics: list[dict], key: str, lower: float, upper: float, is_last: bool
) -> dict:
    rows = [
        row
        for row in diagnostics
        if (
            lower <= row[key] <= upper
            if is_last
            else lower <= row[key] < upper
        )
    ]
    entered = [
        row["first_reach_step"]
        for row in rows
        if row["first_reach_step"] is not None
    ]
    successes = sum(bool(row["success"]) for row in rows)
    return {
        "lower_bound": lower,
        "upper_bound": upper,
        "episodes": len(rows),
        "successes": successes,
        "success_percent": 100.0 * successes / len(rows) if rows else None,
        "mean_time_to_first_entry_step": _mean(entered),
        "mean_longest_in_band_run_steps": _mean(
            [float(row["max_held_steps"]) for row in rows]
        ),
        "mean_hold_exits": _mean(
            [float(row["hold_interruptions"]) for row in rows]
        ),
        "episodes_with_action_saturation_percent": (
            100.0
            * sum(row["saturated_action_steps"] > 0 for row in rows)
            / len(rows)
            if rows
            else None
        ),
    }


def _stratified_summary(diagnostics: list[dict]) -> dict:
    radius_edges = (6.0, 10.0, 14.0, 18.0, 20.0)
    angle_edges = (-180.0, -135.0, -90.0, -45.0, 0.0, 45.0, 90.0, 135.0, 180.0)
    return {
        "radius_cm": [
            {
                "bin": f"{lower:g}-{upper:g}",
                **_group_summary(
                    diagnostics,
                    "target_radius_cm",
                    lower,
                    upper,
                    index == len(radius_edges) - 2,
                ),
            }
            for index, (lower, upper) in enumerate(pairwise(radius_edges))
        ],
        "angle_degrees": [
            {
                "bin": f"{lower:g}-{upper:g}",
                **_group_summary(
                    diagnostics,
                    "target_angle_degrees",
                    lower,
                    upper,
                    index == len(angle_edges) - 2,
                ),
            }
            for index, (lower, upper) in enumerate(pairwise(angle_edges))
        ],
    }


def evaluate_research_model(
    model_path: Path,
    *,
    episodes: int,
    seed: int,
    algorithm: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict:
    """Measure a deterministic panel with episode seeds starting at ``seed``."""
    if episodes < 1:
        raise ValueError("an evaluation panel requires at least one episode")
    runtime = load_runtime(model_path, algorithm)
    env = make_evaluation_env(policy_runtime=runtime)

    episode_results: list[dict] = []
    episode_diagnostics: list[dict] = []
    for episode in range(episodes):
        obs, _ = env.reset(seed=seed + episode)
        runtime.reset()
        target_position = np.asarray(env.data.mocap_pos[0], dtype=np.float64)
        reward_total = 0.0
        steps = 0
        success = False
        terminated = False
        truncated = False
        min_distance_cm = float("inf")
        final_distance_cm = float("nan")
        first_reach_step: int | None = None
        max_held_steps = 0
        in_tolerance_steps = 0
        hold_interruptions = 0
        was_in_tolerance = False
        saturated_action_steps = 0
        max_abs_action = 0.0
        while not (terminated or truncated):
            action = runtime.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            applied_action = np.asarray(info["applied_action"], dtype=np.float64)
            saturated_action = bool(np.any(np.abs(applied_action) >= 1.0 - 1e-6))
            if saturated_action:
                saturated_action_steps += 1
            max_abs_action = max(max_abs_action, float(np.max(np.abs(applied_action))))
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
            elif was_in_tolerance:
                hold_interruptions += 1
            was_in_tolerance = held_steps > 0
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
        episode_diagnostics.append(
            {
                "episode": episode,
                "episode_seed": seed + episode,
                "target_radius_cm": float(
                    np.hypot(target_position[0], target_position[1]) * 100.0
                ),
                "target_angle_degrees": float(
                    np.degrees(np.arctan2(target_position[1], target_position[0]))
                ),
                "min_distance_cm": min_distance_cm,
                "final_distance_cm": final_distance_cm,
                "first_reach_step": first_reach_step,
                "max_held_steps": max_held_steps,
                "in_tolerance_steps": in_tolerance_steps,
                "hold_interruptions": hold_interruptions,
                "saturated_action_steps": saturated_action_steps,
                "max_abs_action": max_abs_action,
                "success": success,
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
        # Researcher-owned evidence for distinguishing reach failures from hold
        # failures and checking whether performance varies by target geometry.
        "research_evidence": {
            "episode_diagnostics": episode_diagnostics,
            "stratified_summary": _stratified_summary(episode_diagnostics),
            "units": {
                "distance": "cm",
                "time": "control_steps",
                "action": "normalized_motor_command",
            },
        },
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
    outcomes = episode_outcomes(evaluations)
    total_episodes = len(outcomes)
    total_successes = sum(outcomes.values())
    episode_executions = sum(int(item["episodes"]) for item in evaluations)
    seed_success = {
        str(item["seed"]): float(item["success_percent"]) for item in evaluations
    }
    pooled_success = 100 * total_successes / total_episodes
    return {
        "schema_version": 4,
        "evaluation_summary_version": summary_version,
        "episodes": total_episodes,
        "episode_executions": episode_executions,
        "repeated_episodes": episode_executions - total_episodes,
        "seed_count": len(evaluations),
        "seed_success_percent": seed_success,
        "worst_seed_success_percent": min(seed_success.values()),
        "pooled_success_percent": pooled_success,
        "success_percent": pooled_success,
    }
