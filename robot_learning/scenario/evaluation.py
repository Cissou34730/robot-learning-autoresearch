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
        control_dt = env.model.opt.timestep * env.frame_skip
        previous_end_effector = np.asarray(
            env.data.site("end_effector").xpos, dtype=np.float64
        ).copy()
        max_endpoint_speed = 0.0
        max_endpoint_speed_during_hold = 0.0
        max_joint_speed = 0.0
        max_joint_speed_during_hold = 0.0
        max_abs_applied_control = 0.0
        saturated_control_steps = 0
        min_joint_limit_margin = float("inf")
        first_reach_endpoint_speed: float | None = None
        first_reach_joint_speed: float | None = None
        first_reach_joint_limit_margin: float | None = None
        while not (terminated or truncated):
            action = runtime.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            end_effector_position = np.asarray(
                env.data.site("end_effector").xpos, dtype=np.float64
            )
            endpoint_speed = float(
                np.linalg.norm(
                    (end_effector_position - previous_end_effector) / control_dt
                )
            )
            previous_end_effector = end_effector_position.copy()
            joint_speed = float(np.linalg.norm(env.data.qvel))
            joint_limit_margin = float(
                np.min(
                    np.minimum(
                        env.data.qpos - env.model.jnt_range[:, 0],
                        env.model.jnt_range[:, 1] - env.data.qpos,
                    )
                )
            )
            applied_control = np.asarray(env.data.ctrl, dtype=np.float64)
            max_abs_applied_control = max(
                max_abs_applied_control, float(np.max(np.abs(applied_control)))
            )
            if np.any(np.abs(applied_control) >= 0.999):
                saturated_control_steps += 1
            max_endpoint_speed = max(max_endpoint_speed, endpoint_speed)
            max_joint_speed = max(max_joint_speed, joint_speed)
            min_joint_limit_margin = min(min_joint_limit_margin, joint_limit_margin)
            if held_steps > 0:
                max_endpoint_speed_during_hold = max(
                    max_endpoint_speed_during_hold, endpoint_speed
                )
                max_joint_speed_during_hold = max(
                    max_joint_speed_during_hold, joint_speed
                )
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    first_reach_endpoint_speed = endpoint_speed
                    first_reach_joint_speed = joint_speed
                    first_reach_joint_limit_margin = joint_limit_margin
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
                "max_endpoint_speed_m_per_s": max_endpoint_speed,
                "max_endpoint_speed_during_hold_m_per_s": (
                    max_endpoint_speed_during_hold
                ),
                "first_reach_endpoint_speed_m_per_s": first_reach_endpoint_speed,
                "max_joint_speed_rad_per_s": max_joint_speed,
                "max_joint_speed_during_hold_rad_per_s": (
                    max_joint_speed_during_hold
                ),
                "first_reach_joint_speed_rad_per_s": first_reach_joint_speed,
                "max_abs_applied_control": max_abs_applied_control,
                "saturated_control_steps": saturated_control_steps,
                "min_joint_limit_margin_rad": min_joint_limit_margin,
                "first_reach_joint_limit_margin_rad": (
                    first_reach_joint_limit_margin
                ),
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
