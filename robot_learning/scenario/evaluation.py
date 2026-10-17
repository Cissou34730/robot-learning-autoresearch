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
from robot_learning.scenario.environment import (
    ELBOW_BRANCH_LABELS,
    make_evaluation_env,
)

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
        obs, reset_info = env.reset(seed=seed + episode)
        runtime.reset()
        target_position = np.asarray(env.data.mocap_pos[0], dtype=np.float64)
        initial_elbow_branch = str(reset_info["elbow_branch"])
        if initial_elbow_branch not in ELBOW_BRANCH_LABELS:
            raise RuntimeError(
                f"Unknown initial elbow branch label from scenario "
                f"environment: {initial_elbow_branch!r}"
            )
        initial_elbow_qpos_rad = float(reset_info["elbow_qpos_rad"])
        reward_total = 0.0
        steps = 0
        success = False
        terminated = False
        truncated = False
        min_distance_cm = float("inf")
        final_distance_cm = float("nan")
        first_reach_step: int | None = None
        first_reach_endpoint_speed_mps: float | None = None
        max_endpoint_speed_mps: float | None = None
        final_endpoint_speed_mps: float | None = None
        max_held_steps = 0
        in_tolerance_steps = 0
        hold_interruptions = 0
        was_in_tolerance = False
        branch_occupancy_counts = dict.fromkeys(ELBOW_BRANCH_LABELS, 0)
        final_elbow_branch: str | None = None
        final_elbow_qpos_rad: float | None = None
        action_saturation_count = 0
        action_saturation_count_per_joint: np.ndarray | None = None
        while not (terminated or truncated):
            action = runtime.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            endpoint_speed_mps = float(info["endpoint_speed_mps"])
            if not np.isfinite(endpoint_speed_mps):
                raise RuntimeError(
                    "Research evaluation received a non-finite endpoint speed "
                    "from the scenario environment"
                )
            if max_endpoint_speed_mps is None:
                max_endpoint_speed_mps = endpoint_speed_mps
            else:
                max_endpoint_speed_mps = max(
                    max_endpoint_speed_mps, endpoint_speed_mps
                )
            final_endpoint_speed_mps = endpoint_speed_mps
            if action_saturation_count_per_joint is None:
                action_saturated = np.asarray(
                    info["action_saturated"], dtype=bool
                )
                if action_saturated.ndim != 1:
                    raise RuntimeError(
                        "Scenario action saturation instrumentation must be "
                        "a one-dimensional per-joint array"
                    )
                action_saturation_count_per_joint = np.zeros(
                    action_saturated.shape, dtype=np.int64
                )
            action_saturated = np.asarray(info["action_saturated"], dtype=bool)
            if action_saturated.shape != action_saturation_count_per_joint.shape:
                raise RuntimeError(
                    "Scenario action saturation instrumentation changed "
                    "joint shape during an episode"
                )
            action_saturation_count_per_joint += action_saturated
            action_saturation_count += int(np.count_nonzero(action_saturated))
            elbow_branch = str(info["elbow_branch"])
            if elbow_branch not in branch_occupancy_counts:
                raise RuntimeError(
                    f"Unknown elbow branch label from scenario environment: "
                    f"{elbow_branch!r}"
                )
            branch_occupancy_counts[elbow_branch] += 1
            final_elbow_branch = elbow_branch
            final_elbow_qpos_rad = float(info["elbow_qpos_rad"])
            max_held_steps = max(max_held_steps, held_steps)
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    first_reach_endpoint_speed_mps = endpoint_speed_mps
            elif was_in_tolerance:
                hold_interruptions += 1
            was_in_tolerance = held_steps > 0
            if "is_success" in info:
                success = bool(info["is_success"])

        if (
            max_endpoint_speed_mps is None
            or final_endpoint_speed_mps is None
            or final_elbow_branch is None
            or final_elbow_qpos_rad is None
            or action_saturation_count_per_joint is None
        ):
            raise RuntimeError(
                "Research evaluation completed an episode without the "
                "required scenario diagnostics"
            )
        action_saturation_fraction_per_joint = (
            action_saturation_count_per_joint / steps
        )
        action_saturation_fraction = action_saturation_count / (
            steps * action_saturation_count_per_joint.size
        )
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
                "initial_elbow_qpos_rad": initial_elbow_qpos_rad,
                "initial_elbow_branch": initial_elbow_branch,
                "min_distance_cm": min_distance_cm,
                "final_distance_cm": final_distance_cm,
                "first_reach_step": first_reach_step,
                "first_reach_endpoint_speed_mps": first_reach_endpoint_speed_mps,
                "max_endpoint_speed_mps": max_endpoint_speed_mps,
                "final_endpoint_speed_mps": final_endpoint_speed_mps,
                "max_held_steps": max_held_steps,
                "in_tolerance_steps": in_tolerance_steps,
                "hold_interruptions": hold_interruptions,
                "final_elbow_qpos_rad": final_elbow_qpos_rad,
                "final_elbow_branch": final_elbow_branch,
                "elbow_branch_occupancy_counts": branch_occupancy_counts,
                "action_saturation_count": action_saturation_count,
                "action_saturation_fraction": float(action_saturation_fraction),
                "action_saturation_count_per_joint": (
                    action_saturation_count_per_joint.tolist()
                ),
                "action_saturation_fraction_per_joint": (
                    action_saturation_fraction_per_joint.tolist()
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
            "units": {
                "distance": "cm",
                "time": "control_steps",
                "endpoint_speed": "m_per_s",
                "elbow_qpos": "rad",
                "action_saturation_fraction": "proportion",
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
