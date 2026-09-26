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
from robot_learning.scenario.observations import reach_observation

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
    env = make_evaluation_env(
        policy_runtime=runtime, capture_step_diagnostics=True
    )

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
        min_distance_step: int | None = None
        min_substep_distance_cm = float("inf")
        min_substep_distance_step: int | None = None
        internal_tolerance_hits = 0
        first_internal_tolerance_step: int | None = None
        max_internal_distance_cm = 0.0
        max_internal_distance_after_entry_cm = 0.0
        max_tip_speed_cm_s = 0.0
        max_tip_speed_after_entry_cm_s = 0.0
        max_action_abs = 0.0
        entry_tip_speed_cm_s: float | None = None
        entry_joint_speed_rad_s: float | None = None
        entry_elbow_angle_rad: float | None = None
        entry_open_ik_branch_error_rad: float | None = None
        entry_folded_ik_branch_error_rad: float | None = None
        entry_nearest_ik_branch_error_rad: float | None = None
        while not (terminated or truncated):
            action = runtime.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            step_diagnostics = env.last_step_diagnostics
            if step_diagnostics is None:
                raise RuntimeError("evaluation diagnostics were not captured")
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            min_substep_distance = float(step_diagnostics["min_substep_distance"])
            max_substep_distance = float(step_diagnostics["max_substep_distance"])
            max_substep_tip_speed = float(step_diagnostics["max_substep_tip_speed"])
            if 100.0 * min_substep_distance < min_substep_distance_cm:
                min_substep_distance_cm = 100.0 * min_substep_distance
                min_substep_distance_step = steps
            if bool(step_diagnostics["internal_tolerance_hit"]):
                internal_tolerance_hits += 1
                if first_internal_tolerance_step is None:
                    first_internal_tolerance_step = steps
            max_internal_distance_cm = max(
                max_internal_distance_cm, 100.0 * max_substep_distance
            )
            max_tip_speed_cm_s = max(
                max_tip_speed_cm_s, 100.0 * max_substep_tip_speed
            )
            max_action_abs = max(
                max_action_abs,
                float(np.max(np.abs(step_diagnostics["applied_action"]))),
            )
            if distance_cm < min_distance_cm:
                min_distance_cm = distance_cm
                min_distance_step = steps
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    raw_observation = reach_observation(env.data)
                    entry_tip_speed_cm_s = 100.0 * float(
                        step_diagnostics["final_tip_speed"]
                    )
                    entry_joint_speed_rad_s = float(
                        np.linalg.norm(raw_observation[2:4])
                    )
                    entry_elbow_angle_rad = float(raw_observation[3])
                    entry_open_ik_branch_error_rad = float(
                        np.linalg.norm(raw_observation[7:9])
                    )
                    entry_folded_ik_branch_error_rad = float(
                        np.linalg.norm(raw_observation[9:11])
                    )
                    entry_nearest_ik_branch_error_rad = min(
                        entry_open_ik_branch_error_rad,
                        entry_folded_ik_branch_error_rad,
                    )
            elif was_in_tolerance:
                hold_interruptions += 1
            was_in_tolerance = held_steps > 0
            if first_reach_step is not None:
                max_internal_distance_after_entry_cm = max(
                    max_internal_distance_after_entry_cm,
                    100.0 * max_substep_distance,
                )
                max_tip_speed_after_entry_cm_s = max(
                    max_tip_speed_after_entry_cm_s,
                    100.0 * max_substep_tip_speed,
                )
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
                "min_distance_step": min_distance_step,
                "min_substep_distance_cm": min_substep_distance_cm,
                "min_substep_distance_step": min_substep_distance_step,
                "final_distance_cm": final_distance_cm,
                "first_reach_step": first_reach_step,
                "first_internal_tolerance_step": first_internal_tolerance_step,
                "internal_tolerance_hits": internal_tolerance_hits,
                "internal_tolerance_without_sampled_entry": (
                    first_reach_step is None and internal_tolerance_hits > 0
                ),
                "max_internal_distance_cm": max_internal_distance_cm,
                "max_internal_distance_after_entry_cm": (
                    max_internal_distance_after_entry_cm
                    if first_reach_step is not None
                    else None
                ),
                "max_tip_speed_cm_s": max_tip_speed_cm_s,
                "max_tip_speed_after_entry_cm_s": (
                    max_tip_speed_after_entry_cm_s
                    if first_reach_step is not None
                    else None
                ),
                "max_action_abs": max_action_abs,
                "entry_tip_speed_cm_s": entry_tip_speed_cm_s,
                "entry_joint_speed_rad_s": entry_joint_speed_rad_s,
                "entry_elbow_angle_rad": entry_elbow_angle_rad,
                "entry_open_ik_branch_error_rad": entry_open_ik_branch_error_rad,
                "entry_folded_ik_branch_error_rad": (
                    entry_folded_ik_branch_error_rad
                ),
                "entry_nearest_ik_branch_error_rad": (
                    entry_nearest_ik_branch_error_rad
                ),
                "max_held_steps": max_held_steps,
                "in_tolerance_steps": in_tolerance_steps,
                "hold_interruptions": hold_interruptions,
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
