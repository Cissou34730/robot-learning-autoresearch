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


def ik_branch_proximities(observation: np.ndarray) -> tuple[float, float]:
    """Return open and folded IK-feature distances from an observation."""
    values = np.asarray(observation, dtype=np.float64)
    if values.shape != (11,):
        raise ValueError(f"expected an 11-value observation, got {values.shape}")
    return (
        float(np.linalg.norm(values[7:9])),
        float(np.linalg.norm(values[9:11])),
    )


def selected_ik_branch(open_proximity: float, folded_proximity: float) -> str:
    """Select the closer IK branch, resolving a tie in favor of open."""
    return "open" if open_proximity <= folded_proximity else "folded"


def failure_attribution(success: bool, first_reach_step: int | None) -> str:
    """Classify an episode by first entry and uninterrupted task completion."""
    if success:
        return "success"
    if first_reach_step is None:
        return "approach_failure"
    return "hold_failure"


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
        min_open_branch_proximity = float("inf")
        min_folded_branch_proximity = float("inf")
        action_magnitude_total = 0.0
        action_magnitude_max = 0.0
        final_action_magnitude = 0.0
        saturated_steps = 0
        saturated_components = 0
        action_components = int(np.asarray(env.action_space.low).size)

        open_proximity, folded_proximity = ik_branch_proximities(obs)
        min_open_branch_proximity = min(min_open_branch_proximity, open_proximity)
        min_folded_branch_proximity = min(
            min_folded_branch_proximity, folded_proximity
        )
        while not (terminated or truncated):
            action = runtime.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            actual_action = np.asarray(env.data.ctrl, dtype=np.float64).copy()
            action_magnitude = float(np.linalg.norm(actual_action))
            action_magnitude_total += action_magnitude
            action_magnitude_max = max(action_magnitude_max, action_magnitude)
            final_action_magnitude = action_magnitude
            at_action_limit = np.logical_or(
                actual_action
                <= np.asarray(env.action_space.low, dtype=np.float64),
                actual_action
                >= np.asarray(env.action_space.high, dtype=np.float64),
            )
            saturated_components += int(np.count_nonzero(at_action_limit))
            if np.any(at_action_limit):
                saturated_steps += 1

            open_proximity, folded_proximity = ik_branch_proximities(obs)
            min_open_branch_proximity = min(
                min_open_branch_proximity, open_proximity
            )
            min_folded_branch_proximity = min(
                min_folded_branch_proximity, folded_proximity
            )
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            min_distance_cm = min(min_distance_cm, distance_cm)
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
        selected_branch = selected_ik_branch(
            min_open_branch_proximity, min_folded_branch_proximity
        )
        attribution = failure_attribution(success, first_reach_step)
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
                "failure_attribution": attribution,
                "min_open_branch_proximity": min_open_branch_proximity,
                "min_folded_branch_proximity": min_folded_branch_proximity,
                "selected_branch": selected_branch,
                "selected_branch_proximity": min(
                    min_open_branch_proximity, min_folded_branch_proximity
                ),
                "actual_action_magnitude_mean": (
                    action_magnitude_total / steps
                ),
                "actual_action_magnitude_max": action_magnitude_max,
                "actual_action_magnitude_final": final_action_magnitude,
                "action_saturation_steps": saturated_steps,
                "action_saturation_fraction": saturated_steps / steps,
                "action_saturated_components": saturated_components,
                "action_saturation_component_fraction": (
                    saturated_components / (steps * action_components)
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
                "branch_proximity": "joint_error_norm_radians",
                "action_magnitude": "control_l2_norm",
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
