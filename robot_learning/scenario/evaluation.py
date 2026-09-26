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
NEAR_TARGET_DISTANCE_CM = 5.0


def _physical_metrics(env) -> tuple[float, float, float, float]:
    jacobian = np.zeros((3, 2), dtype=np.float64)
    mujoco.mj_jacSite(
        env.model,
        env.data,
        jacobian,
        None,
        env.model.site("end_effector").id,
    )
    planar_jacobian = jacobian[:2, :]
    singular_values = np.linalg.svd(planar_jacobian, compute_uv=False)
    smallest_singular_value = float(singular_values[-1])
    jacobian_condition = float(
        singular_values[0] / max(smallest_singular_value, 1e-12)
    )
    endpoint_speed_cm_s = float(
        np.linalg.norm(planar_jacobian @ np.asarray(env.data.qvel[:2]))
        * 100.0
    )
    joint_speed = float(np.linalg.norm(env.data.qvel[:2]))
    return (
        smallest_singular_value,
        jacobian_condition,
        endpoint_speed_cm_s,
        joint_speed,
    )


def _branch_distances(env) -> tuple[float, float]:
    observation = reach_observation(env.data)
    return (
        float(np.linalg.norm(observation[7:9])),
        float(np.linalg.norm(observation[9:11])),
    )


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
        min_jacobian_singular_value = float("inf")
        max_jacobian_condition = 0.0
        max_endpoint_speed_cm_s = 0.0
        max_joint_speed = 0.0
        max_action_abs = 0.0
        saturated_steps = 0
        branch_switches = 0
        min_branch_margin = float("inf")
        previous_branch: int | None = None
        entry_endpoint_speed_cm_s: float | None = None
        entry_jacobian_condition: float | None = None
        entry_branch: int | None = None
        entry_branch_margin: float | None = None
        branch_switch_events: list[dict] = []
        near_target_steps = 0
        near_target_saturated_steps = 0
        min_near_target_jacobian_singular_value = float("inf")
        max_near_target_jacobian_condition = 0.0
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
            elif was_in_tolerance:
                hold_interruptions += 1
            was_in_tolerance = held_steps > 0
            if "is_success" in info:
                success = bool(info["is_success"])
            (
                jacobian_singular_value,
                jacobian_condition,
                endpoint_speed_cm_s,
                joint_speed,
            ) = _physical_metrics(env)
            min_jacobian_singular_value = min(
                min_jacobian_singular_value, jacobian_singular_value
            )
            max_jacobian_condition = max(
                max_jacobian_condition, jacobian_condition
            )
            max_endpoint_speed_cm_s = max(
                max_endpoint_speed_cm_s, endpoint_speed_cm_s
            )
            max_joint_speed = max(max_joint_speed, joint_speed)
            applied_action_abs = float(np.max(np.abs(env.data.ctrl)))
            max_action_abs = max(max_action_abs, applied_action_abs)
            if applied_action_abs >= 1.0 - 1e-8:
                saturated_steps += 1
            branch_distances = _branch_distances(env)
            branch = int(np.argmin(branch_distances))
            if previous_branch is not None and branch != previous_branch:
                branch_switches += 1
                branch_switch_events.append(
                    {
                        "step": steps,
                        "from_branch": previous_branch,
                        "to_branch": branch,
                        "distance_cm": distance_cm,
                        "branch_margin": abs(
                            branch_distances[0] - branch_distances[1]
                        ),
                        "jacobian_condition": jacobian_condition,
                        "endpoint_speed_cm_s": endpoint_speed_cm_s,
                        "action_abs": applied_action_abs,
                        "held_steps": held_steps,
                    }
                )
            previous_branch = branch
            min_branch_margin = min(
                min_branch_margin,
                abs(branch_distances[0] - branch_distances[1]),
            )
            if held_steps > 0 and first_reach_step == steps:
                entry_endpoint_speed_cm_s = endpoint_speed_cm_s
                entry_jacobian_condition = jacobian_condition
                entry_branch = branch
                entry_branch_margin = abs(
                    branch_distances[0] - branch_distances[1]
                )
            if distance_cm <= NEAR_TARGET_DISTANCE_CM:
                near_target_steps += 1
                near_target_saturated_steps += int(applied_action_abs >= 1.0 - 1e-8)
                min_near_target_jacobian_singular_value = min(
                    min_near_target_jacobian_singular_value,
                    jacobian_singular_value,
                )
                max_near_target_jacobian_condition = max(
                    max_near_target_jacobian_condition,
                    jacobian_condition,
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
                "min_distance_cm": min_distance_cm,
                "final_distance_cm": final_distance_cm,
                "first_reach_step": first_reach_step,
                "max_held_steps": max_held_steps,
                "in_tolerance_steps": in_tolerance_steps,
                "hold_interruptions": hold_interruptions,
                "min_jacobian_singular_value": min_jacobian_singular_value,
                "max_jacobian_condition": max_jacobian_condition,
                "max_endpoint_speed_cm_s": max_endpoint_speed_cm_s,
                "max_joint_speed": max_joint_speed,
                "max_action_abs": max_action_abs,
                "saturated_steps": saturated_steps,
                "branch_switches": branch_switches,
                "min_branch_margin": min_branch_margin,
                "entry_endpoint_speed_cm_s": entry_endpoint_speed_cm_s,
                "entry_jacobian_condition": entry_jacobian_condition,
                "entry_branch": entry_branch,
                "entry_branch_margin": entry_branch_margin,
                "branch_switch_events": branch_switch_events,
                "near_target_steps": near_target_steps,
                "near_target_saturated_steps": near_target_saturated_steps,
                "min_near_target_jacobian_singular_value": (
                    min_near_target_jacobian_singular_value
                    if np.isfinite(min_near_target_jacobian_singular_value)
                    else None
                ),
                "max_near_target_jacobian_condition": (
                    max_near_target_jacobian_condition
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
