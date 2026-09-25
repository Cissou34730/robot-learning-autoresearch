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
        previous_endpoint = np.asarray(
            env.data.site("end_effector").xpos, dtype=np.float64
        ).copy()
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
        entry_endpoint_speed_cm_s: float | None = None
        entry_jacobian_abs_det: float | None = None
        entry_open_branch_error_rad: float | None = None
        entry_folded_branch_error_rad: float | None = None
        min_jacobian_abs_det = float("inf")
        max_endpoint_speed_cm_s = 0.0
        max_hold_endpoint_speed_cm_s = 0.0
        action_saturation_steps = 0
        while not (terminated or truncated):
            action = runtime.predict(obs)
            applied_action = np.clip(
                np.asarray(action, dtype=np.float64),
                env.action_space.low,
                env.action_space.high,
            )
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            endpoint = np.asarray(
                env.data.site("end_effector").xpos, dtype=np.float64
            )
            endpoint_speed_cm_s = (
                100.0 * float(np.linalg.norm(endpoint - previous_endpoint)) / control_dt
            )
            previous_endpoint = endpoint.copy()
            jacobian_position = np.zeros((3, env.model.nv), dtype=np.float64)
            jacobian_rotation = np.zeros((3, env.model.nv), dtype=np.float64)
            mujoco.mj_jacSite(
                env.model,
                env.data,
                jacobian_position,
                jacobian_rotation,
                env.model.site("end_effector").id,
            )
            jacobian_abs_det = abs(
                float(np.linalg.det(jacobian_position[:2, :2]))
            )
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            min_jacobian_abs_det = min(min_jacobian_abs_det, jacobian_abs_det)
            max_endpoint_speed_cm_s = max(max_endpoint_speed_cm_s, endpoint_speed_cm_s)
            if held_steps > 0:
                max_hold_endpoint_speed_cm_s = max(
                    max_hold_endpoint_speed_cm_s, endpoint_speed_cm_s
                )
            if np.any(np.abs(applied_action) >= 1.0 - 1e-6):
                action_saturation_steps += 1
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    entry_endpoint_speed_cm_s = endpoint_speed_cm_s
                    entry_jacobian_abs_det = jacobian_abs_det
                    entry_open_branch_error_rad = float(np.linalg.norm(obs[7:9]))
                    entry_folded_branch_error_rad = float(np.linalg.norm(obs[9:11]))
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
                "entry_endpoint_speed_cm_s": entry_endpoint_speed_cm_s,
                "entry_jacobian_abs_det": entry_jacobian_abs_det,
                "entry_open_branch_error_rad": entry_open_branch_error_rad,
                "entry_folded_branch_error_rad": entry_folded_branch_error_rad,
                "min_jacobian_abs_det": min_jacobian_abs_det,
                "max_endpoint_speed_cm_s": max_endpoint_speed_cm_s,
                "max_hold_endpoint_speed_cm_s": max_hold_endpoint_speed_cm_s,
                "action_saturation_steps": action_saturation_steps,
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
                "time": "control_steps",
                "speed": "cm_per_second",
                "jacobian_determinant": "meter_squared_per_radian_squared",
                "angle": "radians",
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
