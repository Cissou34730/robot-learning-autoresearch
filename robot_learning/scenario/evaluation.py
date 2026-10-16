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
ELBOW_NEAR_SINGULAR_THRESHOLD_RAD = 1e-3


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
    control_interval_seconds = float(env.model.opt.timestep * env.frame_skip)

    episode_results: list[dict] = []
    episode_diagnostics: list[dict] = []
    for episode in range(episodes):
        obs, _ = env.reset(seed=seed + episode)
        runtime.reset()
        target_position = np.asarray(env.data.mocap_pos[0], dtype=np.float64)
        target_radius_m = float(np.hypot(target_position[0], target_position[1]))
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
        entry_endpoint_speed_m_s: float | None = None
        entry_elbow_angle_rad: float | None = None
        realized_elbow_branch = "unreached"
        while not (terminated or truncated):
            action = runtime.predict(obs)
            endpoint_position_before = env.data.site("end_effector").xpos.copy()
            obs, reward, terminated, truncated, info = env.step(action)
            endpoint_position_after = env.data.site("end_effector").xpos.copy()
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            endpoint_speed_m_s = float(
                np.linalg.norm(endpoint_position_after - endpoint_position_before)
                / control_interval_seconds
            )
            held_steps = int(info.get("held_steps", 0))
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    entry_endpoint_speed_m_s = endpoint_speed_m_s
                    entry_elbow_angle_rad = float(env.data.qpos[1])
                    if (
                        abs(entry_elbow_angle_rad)
                        <= ELBOW_NEAR_SINGULAR_THRESHOLD_RAD
                    ):
                        realized_elbow_branch = "near_singular"
                    elif entry_elbow_angle_rad > 0.0:
                        realized_elbow_branch = "open"
                    else:
                        realized_elbow_branch = "folded"
            elif was_in_tolerance:
                hold_interruptions += 1
            was_in_tolerance = held_steps > 0
            if "is_success" in info:
                success = bool(info["is_success"])

        if success:
            failure_class = "success"
        elif first_reach_step is None:
            failure_class = "no_reach"
        elif hold_interruptions > 0:
            failure_class = "hold_interrupted"
        else:
            failure_class = "reached_without_complete_hold"

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
                "target_radius_cm": target_radius_m * 100.0,
                "target_radius_band": (
                    "inner_6_14_cm"
                    if target_radius_m < 0.14
                    else "outer_14_20_cm"
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
                "entry_endpoint_speed_m_s": entry_endpoint_speed_m_s,
                "entry_elbow_angle_rad": entry_elbow_angle_rad,
                "realized_elbow_branch": realized_elbow_branch,
                "failure_class": failure_class,
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
                "entry_endpoint_speed_m_s": "m/s",
                "entry_elbow_angle_rad": "rad",
                "realized_elbow_branch": (
                    "open for qpos[1] > "
                    f"{ELBOW_NEAR_SINGULAR_THRESHOLD_RAD} rad; "
                    "folded for qpos[1] < -"
                    f"{ELBOW_NEAR_SINGULAR_THRESHOLD_RAD} rad; "
                    "near_singular for absolute qpos[1] <= "
                    f"{ELBOW_NEAR_SINGULAR_THRESHOLD_RAD} rad; "
                    "unreached when no tolerance entry occurs"
                ),
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
