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

import numpy as np

from benchmark.paired_evidence import episode_outcomes
from contracts.policy_runtime import load_runtime
from robot_learning.scenario.environment import make_evaluation_env

# Bumped when the meaning of a scenario evaluation summary changes.
RESEARCH_EVALUATION_SUMMARY_VERSION = 4


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
        min_distance_cm: float | None = None
        final_distance_cm = float("nan")
        first_reach_step: int | None = None
        reached_branch: str | None = None
        max_held_steps = 0
        in_tolerance_steps = 0
        hold_interruptions = 0
        interruption_steps: list[int] = []
        hold_margins_cm: list[float] = []
        action_norms: list[float] = []
        action_abs_values: list[float] = []
        joint_speed_values: list[float] = []
        joint_velocity_abs_values: list[float] = []
        hold_action_abs_values: list[float] = []
        hold_joint_velocity_abs_values: list[float] = []
        was_in_tolerance = False
        while not (terminated or truncated):
            action = runtime.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            action_array = np.asarray(action, dtype=np.float64).reshape(-1)
            joint_velocity = np.asarray(env.data.qvel[:2], dtype=np.float64)
            action_abs = float(np.max(np.abs(action_array)))
            action_norm = float(np.linalg.norm(action_array))
            joint_speed = float(np.linalg.norm(joint_velocity))
            joint_velocity_abs = float(np.max(np.abs(joint_velocity)))
            action_norms.append(action_norm)
            action_abs_values.append(action_abs)
            joint_speed_values.append(joint_speed)
            joint_velocity_abs_values.append(joint_velocity_abs)
            if min_distance_cm is None or distance_cm < min_distance_cm:
                min_distance_cm = distance_cm
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            if held_steps > 0:
                in_tolerance_steps += 1
                hold_margins_cm.append(1.0 - distance_cm)
                hold_action_abs_values.append(action_abs)
                hold_joint_velocity_abs_values.append(joint_velocity_abs)
                if first_reach_step is None:
                    first_reach_step = steps
                    open_residual = float(np.linalg.norm(obs[7:9]))
                    folded_residual = float(np.linalg.norm(obs[9:11]))
                    reached_branch = (
                        "open" if open_residual <= folded_residual else "folded"
                    )
            elif was_in_tolerance:
                hold_interruptions += 1
                interruption_steps.append(steps)
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
                "time_to_entry_steps": first_reach_step,
                "reached_branch": reached_branch,
                "max_held_steps": max_held_steps,
                "in_tolerance_steps": in_tolerance_steps,
                "hold_interruptions": hold_interruptions,
                "interruption_steps": interruption_steps,
                "minimum_hold_margin_cm": (
                    min(hold_margins_cm) if hold_margins_cm else None
                ),
                "max_action_abs": max(action_abs_values),
                "mean_action_norm": float(np.mean(action_norms)),
                "max_joint_velocity_abs_rad_per_s": max(joint_velocity_abs_values),
                "mean_joint_speed_rad_per_s": float(np.mean(joint_speed_values)),
                "max_hold_action_abs": (
                    max(hold_action_abs_values) if hold_action_abs_values else None
                ),
                "max_hold_joint_velocity_abs_rad_per_s": (
                    max(hold_joint_velocity_abs_values)
                    if hold_joint_velocity_abs_values
                    else None
                ),
            }
        )
        if progress_callback is not None:
            progress_callback(episode + 1, episodes)

    successes = sum(episode["success"] for episode in episode_results)
    return {
        "schema_version": 6,
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
            "units": {"distance": "cm", "time": "control_steps"},
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
