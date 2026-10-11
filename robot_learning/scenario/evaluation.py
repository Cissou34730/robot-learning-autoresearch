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
from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.environment import make_evaluation_env

# Bumped when the meaning of a scenario evaluation summary changes.
RESEARCH_EVALUATION_SUMMARY_VERSION = 5


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _branch_errors(data) -> dict[str, float]:
    target_x = float(data.mocap_pos[0][0])
    target_y = float(data.mocap_pos[0][1])
    target_angle = float(np.arctan2(target_y, target_x))
    cos_elbow = (
        target_x**2
        + target_y**2
        - UPPER_ARM_LENGTH**2
        - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))
    errors = {}
    for branch, elbow in (("open", elbow_open), ("folded", -elbow_open)):
        shoulder = target_angle - np.arctan2(
            FOREARM_LENGTH * np.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
        )
        errors[f"{branch}_shoulder_rad"] = _wrap_to_pi(
            float(shoulder) - float(data.qpos[0])
        )
        errors[f"{branch}_elbow_rad"] = _wrap_to_pi(
            elbow - float(data.qpos[1])
        )
    return errors


def _branch_norms(errors: dict[str, float]) -> dict[str, float]:
    return {
        branch: float(
            np.linalg.norm(
                [
                    errors[f"{branch}_shoulder_rad"],
                    errors[f"{branch}_elbow_rad"],
                ]
            )
        )
        for branch in ("open", "folded")
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
        previous_site = np.asarray(
            env.data.site("end_effector").xpos, dtype=np.float64
        ).copy()
        previous_branch: str | None = None
        branch_switches = 0
        max_abs_qvel_rad_s = np.zeros(2, dtype=np.float64)
        max_end_effector_speed_m_s = 0.0
        saturated_control_steps = 0
        saturated_action_components = 0
        trajectory: list[dict] = []
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
            qpos = np.asarray(env.data.qpos[:2], dtype=np.float64).copy()
            qvel = np.asarray(env.data.qvel[:2], dtype=np.float64).copy()
            site_position = np.asarray(
                env.data.site("end_effector").xpos, dtype=np.float64
            )
            site_velocity = (site_position - previous_site) / (
                env.model.opt.timestep * env.frame_skip
            )
            previous_site = site_position
            branch_errors = _branch_errors(env.data)
            branch_norms = _branch_norms(branch_errors)
            closest_branch = min(branch_norms, key=branch_norms.get)
            if previous_branch is not None and closest_branch != previous_branch:
                branch_switches += 1
            previous_branch = closest_branch
            applied_action = np.asarray(env.data.ctrl[:2], dtype=np.float64).copy()
            saturated_components = [
                bool(abs(value) >= 1.0) for value in applied_action
            ]
            saturated_action_components += sum(saturated_components)
            saturated_control_steps += int(any(saturated_components))
            max_abs_qvel_rad_s = np.maximum(max_abs_qvel_rad_s, np.abs(qvel))
            end_effector_speed_m_s = float(np.linalg.norm(site_velocity))
            max_end_effector_speed_m_s = max(
                max_end_effector_speed_m_s, end_effector_speed_m_s
            )
            trajectory.append(
                {
                    "control_step": steps,
                    "qpos_rad": qpos.tolist(),
                    "qvel_rad_s": qvel.tolist(),
                    "action": applied_action.tolist(),
                    "saturated_action_components": saturated_components,
                    "branch_errors_rad": branch_errors,
                    "branch_error_norms_rad": branch_norms,
                    "closest_branch": closest_branch,
                    "distance_cm": distance_cm,
                    "end_effector_velocity_m_s": site_velocity.tolist(),
                    "end_effector_speed_m_s": end_effector_speed_m_s,
                    "held_steps": held_steps,
                }
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
                "branch_switches": branch_switches,
                "max_abs_qvel_rad_s": max_abs_qvel_rad_s.tolist(),
                "max_end_effector_speed_m_s": max_end_effector_speed_m_s,
                "saturated_control_steps": saturated_control_steps,
                "saturated_action_components": saturated_action_components,
                "trajectory": trajectory,
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
