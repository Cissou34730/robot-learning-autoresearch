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


def _angle_bin(angle_degrees: float, bin_count: int = 8) -> str:
    width = 360.0 / bin_count
    index = int(np.floor((angle_degrees + 180.0) / width)) % bin_count
    start = -180.0 + index * width
    end = start + width
    return f"{start:g}..{end:g}"


def _radius_bin(radius_cm: float) -> str:
    if radius_cm < 10.0:
        return "6..10"
    if radius_cm < 14.0:
        return "10..14"
    if radius_cm < 18.0:
        return "14..18"
    return "18..20"


def _stratified_success(
    diagnostics: list[dict],
    *,
    key: str,
) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, list[dict]] = {}
    for item in diagnostics:
        grouped.setdefault(str(item[key]), []).append(item)
    return {
        group: {
            "episodes": len(items),
            "successes": sum(bool(item["success"]) for item in items),
            "success_percent": 100.0
            * sum(bool(item["success"]) for item in items)
            / len(items),
        }
        for group, items in sorted(grouped.items())
    }


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
    control_dt = env.model.opt.timestep * env.frame_skip

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
        distance_trace_cm: list[float] = []
        end_effector_speed_cm_s: list[float] = []
        joint_limit_margin_degrees: list[float] = []
        action_trace: list[list[float]] = []
        while not (terminated or truncated):
            action = runtime.predict(obs)
            previous_position = env._end_effector_position()
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            current_position = env._end_effector_position()
            end_effector_speed_cm_s.append(
                100.0
                * float(np.linalg.norm(current_position - previous_position))
                / control_dt
            )
            distance_trace_cm.append(distance_cm)
            action_array = np.asarray(action, dtype=np.float64).reshape(-1)
            action_trace.append(action_array.tolist())
            joint_ranges = np.asarray(env.model.jnt_range[:2], dtype=np.float64)
            joint_margin = np.minimum(
                env.data.qpos[:2] - joint_ranges[:, 0],
                joint_ranges[:, 1] - env.data.qpos[:2],
            )
            joint_limit_margin_degrees.append(
                float(np.degrees(np.min(joint_margin)))
            )
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

        first_entry_index = next(
            (
                index
                for index, distance in enumerate(distance_trace_cm)
                if distance <= 1.0
            ),
            None,
        )
        post_entry_distances = (
            []
            if first_entry_index is None
            else distance_trace_cm[first_entry_index : first_entry_index + 21]
        )
        post_entry_max_distance_cm = (
            None
            if not post_entry_distances
            else max(post_entry_distances)
        )
        post_entry_overshoot_cm = (
            None
            if post_entry_max_distance_cm is None
            else max(0.0, post_entry_max_distance_cm - 1.0)
        )
        action_array = np.asarray(action_trace, dtype=np.float64)
        action_deltas = (
            np.diff(action_array, axis=0)
            if len(action_array) > 1
            else np.empty((0, 2), dtype=np.float64)
        )
        saturated_actions = np.abs(action_array) >= 0.999
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
                "distance_trace_cm": distance_trace_cm,
                "end_effector_speed_cm_s": end_effector_speed_cm_s,
                "joint_limit_margin_degrees": joint_limit_margin_degrees,
                "action_trace": action_trace,
                "first_entry_speed_cm_s": (
                    None
                    if first_entry_index is None
                    else end_effector_speed_cm_s[first_entry_index]
                ),
                "post_entry_max_distance_cm": post_entry_max_distance_cm,
                "post_entry_overshoot_cm": post_entry_overshoot_cm,
                "residual_end_effector_speed_cm_s": (
                    end_effector_speed_cm_s[-1]
                ),
                "minimum_joint_limit_margin_degrees": min(
                    joint_limit_margin_degrees
                ),
                "action_saturation_count": int(np.sum(saturated_actions)),
                "action_saturation_fraction": float(
                    np.mean(saturated_actions)
                ),
                "action_change_count": int(
                    np.sum(np.linalg.norm(action_deltas, axis=1) > 1e-6)
                ),
                "mean_action_change": (
                    0.0
                    if len(action_deltas) == 0
                    else float(np.mean(np.linalg.norm(action_deltas, axis=1)))
                ),
                "maximum_action_change": (
                    0.0
                    if len(action_deltas) == 0
                    else float(np.max(np.linalg.norm(action_deltas, axis=1)))
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
            "stratified_success": {
                "radius_cm": _stratified_success(
                    [
                        {
                            **item,
                            "radius_bin": _radius_bin(item["target_radius_cm"]),
                        }
                        for item in episode_diagnostics
                    ],
                    key="radius_bin",
                ),
                "angle_degrees": _stratified_success(
                    [
                        {
                            **item,
                            "angle_bin": _angle_bin(
                                item["target_angle_degrees"]
                            ),
                        }
                        for item in episode_diagnostics
                    ],
                    key="angle_bin",
                ),
            },
            "units": {
                "distance": "cm",
                "speed": "cm_per_s",
                "joint_limit_margin": "degrees",
                "time": "control_steps",
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
