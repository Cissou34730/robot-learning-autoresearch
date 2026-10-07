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
from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.environment import make_evaluation_env
from robot_learning.lab.initial_physics import JOINT_LIMIT, inverse_kinematics

# Bumped when the meaning of a scenario evaluation summary changes.
RESEARCH_EVALUATION_SUMMARY_VERSION = 5


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
        first_entry_diagnostics: dict | None = None
        peak_joint_speed = 0.0
        peak_endpoint_speed = 0.0
        peak_action_abs = 0.0
        hold_peak_joint_speed = 0.0
        hold_peak_endpoint_speed = 0.0
        hold_peak_action_abs = 0.0
        interruption_diagnostics: list[dict] = []
        while not (terminated or truncated):
            action = runtime.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            qpos = np.asarray(env.data.qpos[:2], dtype=np.float64)
            qvel = np.asarray(env.data.qvel[:2], dtype=np.float64)
            forearm_angle = qpos[0] + qpos[1]
            endpoint_jacobian = np.array(
                [
                    [
                        -UPPER_ARM_LENGTH * np.sin(qpos[0])
                        - FOREARM_LENGTH * np.sin(forearm_angle),
                        -FOREARM_LENGTH * np.sin(forearm_angle),
                    ],
                    [
                        UPPER_ARM_LENGTH * np.cos(qpos[0])
                        + FOREARM_LENGTH * np.cos(forearm_angle),
                        FOREARM_LENGTH * np.cos(forearm_angle),
                    ],
                ]
            )
            endpoint_velocity = endpoint_jacobian @ qvel
            actual_action = np.asarray(env.data.ctrl[:2], dtype=np.float64)
            joint_speed = float(np.linalg.norm(qvel))
            endpoint_speed = float(np.linalg.norm(endpoint_velocity))
            action_abs = float(np.max(np.abs(actual_action)))
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            peak_joint_speed = max(peak_joint_speed, joint_speed)
            peak_endpoint_speed = max(peak_endpoint_speed, endpoint_speed)
            peak_action_abs = max(peak_action_abs, action_abs)
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    first_entry_diagnostics = {
                        "step": steps,
                        "joint_velocity": qvel.tolist(),
                        "joint_speed": joint_speed,
                        "endpoint_velocity": endpoint_velocity.tolist(),
                        "endpoint_speed": endpoint_speed,
                        "action": actual_action.tolist(),
                        "action_abs_max": action_abs,
                    }
                hold_peak_joint_speed = max(hold_peak_joint_speed, joint_speed)
                hold_peak_endpoint_speed = max(
                    hold_peak_endpoint_speed, endpoint_speed
                )
                hold_peak_action_abs = max(hold_peak_action_abs, action_abs)
            elif was_in_tolerance:
                hold_interruptions += 1
                interruption_diagnostics.append(
                    {
                        "step": steps,
                        "distance_cm": distance_cm,
                        "joint_velocity": qvel.tolist(),
                        "joint_speed": joint_speed,
                        "endpoint_velocity": endpoint_velocity.tolist(),
                        "endpoint_speed": endpoint_speed,
                        "action": actual_action.tolist(),
                        "action_abs_max": action_abs,
                    }
                )
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
        branch_metrics = []
        target_radius = float(np.hypot(target_position[0], target_position[1]))
        target_angle = float(np.arctan2(target_position[1], target_position[0]))
        for branch_name, elbow_sign in (("open", 1.0), ("folded", -1.0)):
            branch_q = inverse_kinematics(target_radius, target_angle, elbow_sign)
            margin_degrees = float(
                np.degrees(JOINT_LIMIT - np.max(np.abs(branch_q)))
            )
            branch_metrics.append(
                {
                    "name": branch_name,
                    "joint_limit_margin_degrees": margin_degrees,
                    "valid": margin_degrees >= 0.0,
                }
            )
        best_branch = max(
            branch_metrics, key=lambda branch: branch["joint_limit_margin_degrees"]
        )
        episode_diagnostics.append(
            {
                "episode": episode,
                "episode_seed": seed + episode,
                "target_radius_cm": target_radius * 100.0,
                "target_angle_degrees": np.degrees(target_angle),
                "branches": branch_metrics,
                "best_branch": best_branch["name"],
                "best_joint_limit_margin_degrees": best_branch[
                    "joint_limit_margin_degrees"
                ],
                "min_distance_cm": min_distance_cm,
                "final_distance_cm": final_distance_cm,
                "first_reach_step": first_reach_step,
                "max_held_steps": max_held_steps,
                "in_tolerance_steps": in_tolerance_steps,
                "hold_interruptions": hold_interruptions,
                "termination_cause": (
                    "success"
                    if success
                    else "hold_not_completed"
                    if first_reach_step is not None
                    else "maneuver_timeout"
                ),
                "first_entry_diagnostics": first_entry_diagnostics,
                "peak_joint_speed": peak_joint_speed,
                "peak_endpoint_speed": peak_endpoint_speed,
                "peak_action_abs_max": peak_action_abs,
                "hold_peak_joint_speed": hold_peak_joint_speed,
                "hold_peak_endpoint_speed": hold_peak_endpoint_speed,
                "hold_peak_action_abs": hold_peak_action_abs,
                "interruption_diagnostics": interruption_diagnostics,
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
            "units": {
                "distance": "cm",
                "time": "control_steps",
                "joint_velocity": "radians_per_second",
                "endpoint_velocity": "meters_per_second",
                "action": "normalized_control",
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
