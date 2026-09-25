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

import mujoco
import numpy as np

from robot_learning.paired_evidence import episode_outcomes
from robot_learning.policy_runtime import load_runtime
from robot_learning.scenario.environment import make_evaluation_env
from robot_learning.scenario.observations import reach_observation

# Bumped when the meaning of a scenario evaluation summary changes.
RESEARCH_EVALUATION_SUMMARY_VERSION = 4
RESEARCH_EVALUATION_SCHEMA_VERSION = 6


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
    site_id = env.model.site("end_effector").id
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
        action_sum = 0.0
        peak_abs_action = 0.0
        peak_action_delta = 0.0
        previous_action: np.ndarray | None = None
        peak_endpoint_speed = 0.0
        closest_endpoint_speed = float("nan")
        first_reach_endpoint_speed = float("nan")
        closest_joint_positions: list[float] | None = None
        closest_joint_velocities: list[float] | None = None
        closest_branch_residuals: list[float] | None = None
        while not (terminated or truncated):
            action = runtime.predict(obs)
            action_array = np.asarray(action, dtype=np.float64).reshape(-1)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            jacobian = np.zeros((3, 2), dtype=np.float64)
            mujoco.mj_jacSite(env.model, env.data, jacobian, None, site_id)
            endpoint_speed = float(np.linalg.norm(jacobian @ env.data.qvel))
            peak_endpoint_speed = max(peak_endpoint_speed, endpoint_speed)
            action_sum += float(np.sum(np.abs(action_array)))
            peak_abs_action = max(peak_abs_action, float(np.max(np.abs(action_array))))
            if previous_action is not None:
                peak_action_delta = max(
                    peak_action_delta,
                    float(np.max(np.abs(action_array - previous_action))),
                )
            previous_action = action_array.copy()
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    first_reach_endpoint_speed = endpoint_speed
            elif was_in_tolerance:
                hold_interruptions += 1
            was_in_tolerance = held_steps > 0
            if distance_cm <= min_distance_cm:
                closest_endpoint_speed = endpoint_speed
                closest_joint_positions = np.asarray(
                    env.data.qpos, dtype=np.float64
                ).tolist()
                closest_joint_velocities = np.asarray(
                    env.data.qvel, dtype=np.float64
                ).tolist()
                closest_branch_residuals = reach_observation(env.data)[7:].tolist()
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
                "peak_endpoint_speed_m_per_s": peak_endpoint_speed,
                "closest_endpoint_speed_m_per_s": closest_endpoint_speed,
                "first_reach_endpoint_speed_m_per_s": first_reach_endpoint_speed,
                "closest_joint_positions": closest_joint_positions,
                "closest_joint_velocities": closest_joint_velocities,
                "closest_branch_residuals_radians": closest_branch_residuals,
                "mean_absolute_action": action_sum / max(steps, 1),
                "peak_absolute_action": peak_abs_action,
                "peak_action_delta": peak_action_delta,
            }
        )
        if progress_callback is not None:
            progress_callback(episode + 1, episodes)

    successes = sum(episode["success"] for episode in episode_results)
    return {
        "schema_version": RESEARCH_EVALUATION_SCHEMA_VERSION,
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
