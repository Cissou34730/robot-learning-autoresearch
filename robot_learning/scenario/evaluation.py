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
        min_distance_cm = float("inf")
        final_distance_cm = float("nan")
        first_reach_step: int | None = None
        max_held_steps = 0
        in_tolerance_steps = 0
        hold_interruptions = 0
        was_in_tolerance = False
        continuous_success = False
        continuous_violation_intervals = 0
        first_entry_joint_speed = None
        first_entry_end_effector_speed = None
        first_entry_max_end_effector_speed = None
        branch_sign_at_first_entry = None
        branch_sign_at_final = None
        branch_switches = 0
        previous_branch_sign = None
        max_abs_action = 0.0
        max_action_delta = 0.0
        saturated_action_steps = 0
        max_joint_speed = 0.0
        max_end_effector_speed = 0.0
        max_substep_distance_cm = 0.0
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
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    first_entry_joint_speed = float(info["joint_speed"])
                    first_entry_end_effector_speed = float(
                        info["end_effector_speed"]
                    )
                    first_entry_max_end_effector_speed = float(
                        info["max_end_effector_speed"]
                    )
                    branch_sign_at_first_entry = int(info["branch_sign"])
            elif was_in_tolerance:
                hold_interruptions += 1
            was_in_tolerance = held_steps > 0
            branch_sign = int(info["branch_sign"])
            if branch_sign != 0:
                if previous_branch_sign not in (None, 0, branch_sign):
                    branch_switches += 1
                previous_branch_sign = branch_sign
                branch_sign_at_final = branch_sign
            continuous_success = bool(info["continuous_success"])
            if bool(info["substep_outside_tolerance"]):
                continuous_violation_intervals += 1
            max_abs_action = max(max_abs_action, float(info["max_abs_action"]))
            max_action_delta = max(max_action_delta, float(info["max_action_delta"]))
            saturated_action_steps += int(info["action_saturated"])
            max_joint_speed = max(max_joint_speed, float(info["max_joint_speed"]))
            max_end_effector_speed = max(
                max_end_effector_speed, float(info["max_end_effector_speed"])
            )
            max_substep_distance_cm = max(
                max_substep_distance_cm,
                100.0 * float(info["substep_max_distance"]),
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
                "final_distance_cm": final_distance_cm,
                "first_reach_step": first_reach_step,
                "max_held_steps": max_held_steps,
                "in_tolerance_steps": in_tolerance_steps,
                "hold_interruptions": hold_interruptions,
                "continuous_success": continuous_success,
                "continuous_violation_intervals": continuous_violation_intervals,
                "first_entry_joint_speed": first_entry_joint_speed,
                "first_entry_end_effector_speed": first_entry_end_effector_speed,
                "first_entry_max_end_effector_speed": first_entry_max_end_effector_speed,
                "branch_sign_at_first_entry": branch_sign_at_first_entry,
                "branch_sign_at_final": branch_sign_at_final,
                "branch_switches": branch_switches,
                "max_abs_action": max_abs_action,
                "max_action_delta": max_action_delta,
                "saturated_action_steps": saturated_action_steps,
                "saturated_action_fraction": saturated_action_steps / steps,
                "max_joint_speed": max_joint_speed,
                "max_end_effector_speed": max_end_effector_speed,
                "max_substep_distance_cm": max_substep_distance_cm,
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
