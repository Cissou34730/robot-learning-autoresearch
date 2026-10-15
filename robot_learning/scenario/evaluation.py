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
        final_distance_cm: float | None = None
        first_reach_step: int | None = None
        max_held_steps = 0
        in_tolerance_steps = 0
        hold_interruptions = 0
        was_in_tolerance = False
        actual_action_trace: list[list[float]] = []
        action_saturated_per_joint_trace: list[list[bool]] = []
        action_saturated_trace: list[bool] = []
        action_clipped_per_joint_trace: list[list[bool]] = []
        action_clipped_trace: list[bool] = []
        joint_velocity_trace: list[list[float]] = []
        endpoint_position_trace: list[list[float]] = []
        endpoint_linear_velocity_trace: list[list[float]] = []
        ik_branch_residuals_trace: list[dict[str, list[float]]] = []
        ik_branch_residual_norms_trace: list[dict[str, float]] = []
        selected_ik_branch_trace: list[str] = []
        joint_limit_margin_trace: list[float] = []
        while not (terminated or truncated):
            action = runtime.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            min_distance_cm = (
                distance_cm
                if min_distance_cm is None
                else min(min_distance_cm, distance_cm)
            )
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
            actual_action_trace.append(list(info["actual_action"]))
            action_saturated_per_joint_trace.append(
                list(info["action_saturated_per_joint"])
            )
            action_saturated_trace.append(bool(info["action_saturated"]))
            action_clipped_per_joint_trace.append(
                list(info["action_clipped_per_joint"])
            )
            action_clipped_trace.append(bool(info["action_clipped"]))
            joint_velocity_trace.append(list(info["joint_velocity_rad_per_s"]))
            endpoint_position_trace.append(list(info["end_effector_position_m"]))
            endpoint_linear_velocity_trace.append(
                list(info["end_effector_linear_velocity_m_per_s"])
            )
            ik_branch_residuals_trace.append(
                {
                    branch: list(residuals)
                    for branch, residuals in info["ik_branch_residuals_rad"].items()
                }
            )
            ik_branch_residual_norms_trace.append(
                {
                    branch: float(norm)
                    for branch, norm in info["ik_branch_residual_norms_rad"].items()
                }
            )
            selected_ik_branch_trace.append(str(info["selected_ik_branch"]))
            joint_limit_margin_trace.append(float(info["joint_limit_margin_rad"]))

        terminal_reason = "success" if success else "horizon_truncation"

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
                "terminal_reason": terminal_reason,
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
                "terminal_reason": terminal_reason,
                "minimum_joint_limit_margin_rad": min(joint_limit_margin_trace),
                "actual_action_trace": actual_action_trace,
                "action_saturated_per_joint_trace": action_saturated_per_joint_trace,
                "action_saturated_trace": action_saturated_trace,
                "action_clipped_per_joint_trace": action_clipped_per_joint_trace,
                "action_clipped_trace": action_clipped_trace,
                "joint_velocity_trace_rad_per_s": joint_velocity_trace,
                "endpoint_position_trace_m": endpoint_position_trace,
                "endpoint_linear_velocity_trace_m_per_s": (
                    endpoint_linear_velocity_trace
                ),
                "ik_branch_residuals_rad_trace": ik_branch_residuals_trace,
                "ik_branch_residual_norms_rad_trace": (
                    ik_branch_residual_norms_trace
                ),
                "selected_ik_branch_trace": selected_ik_branch_trace,
                "joint_limit_margin_trace_rad": joint_limit_margin_trace,
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
            "units": {
                "distance": "cm",
                "target_radius": "cm",
                "target_angle": "degrees",
                "time": "control_steps",
                "action": "dimensionless",
                "joint_velocity": "rad/s",
                "endpoint_position": "m",
                "endpoint_linear_velocity": "m/s",
                "ik_branch_residual": "rad",
                "joint_limit_margin": "rad",
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
