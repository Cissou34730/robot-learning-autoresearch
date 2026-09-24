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

from robot_learning.paired_evidence import episode_outcomes
from robot_learning.policy_runtime import load_runtime
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
        previous_end_effector = env.data.site("end_effector").xpos.copy()
        control_dt = env.model.opt.timestep * env.frame_skip
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
        peak_joint_speed_rad_s = 0.0
        peak_cartesian_speed_cm_s = 0.0
        peak_action_abs = 0.0
        saturated_action_steps = 0
        minimum_ik_branch_error_rad = float("inf")
        first_reach_branch: str | None = None
        first_reach_branch_error_rad: float | None = None
        final_closest_ik_branch: str | None = None
        final_ik_branch_error_rad: float | None = None
        while not (terminated or truncated):
            action = runtime.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            joint_speed_rad_s = float(np.max(np.abs(env.data.qvel[:2])))
            peak_joint_speed_rad_s = max(peak_joint_speed_rad_s, joint_speed_rad_s)
            end_effector = env.data.site("end_effector").xpos.copy()
            cartesian_speed_cm_s = (
                100.0 * float(np.linalg.norm(end_effector - previous_end_effector))
                / control_dt
            )
            peak_cartesian_speed_cm_s = max(
                peak_cartesian_speed_cm_s, cartesian_speed_cm_s
            )
            previous_end_effector = end_effector
            applied_action_abs = np.abs(np.asarray(env.data.ctrl[:2], dtype=np.float64))
            peak_action_abs = max(peak_action_abs, float(np.max(applied_action_abs)))
            if np.any(applied_action_abs >= 1.0 - 1e-6):
                saturated_action_steps += 1
            branch_errors = {
                "elbow_positive": float(np.linalg.norm(obs[7:9])),
                "elbow_negative": float(np.linalg.norm(obs[9:11])),
            }
            closest_branch = min(branch_errors, key=branch_errors.get)
            closest_branch_error_rad = branch_errors[closest_branch]
            minimum_ik_branch_error_rad = min(
                minimum_ik_branch_error_rad, closest_branch_error_rad
            )
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    first_reach_branch = closest_branch
                    first_reach_branch_error_rad = closest_branch_error_rad
            elif was_in_tolerance:
                hold_interruptions += 1
            was_in_tolerance = held_steps > 0
            final_closest_ik_branch = closest_branch
            final_ik_branch_error_rad = closest_branch_error_rad
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
                "peak_joint_speed_rad_s": peak_joint_speed_rad_s,
                "peak_cartesian_speed_cm_s": peak_cartesian_speed_cm_s,
                "peak_action_abs": peak_action_abs,
                "saturated_action_steps": saturated_action_steps,
                "minimum_ik_branch_error_rad": minimum_ik_branch_error_rad,
                "first_reach_branch": first_reach_branch,
                "first_reach_branch_error_rad": first_reach_branch_error_rad,
                "final_closest_ik_branch": final_closest_ik_branch,
                "final_ik_branch_error_rad": final_ik_branch_error_rad,
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
