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
RESEARCH_EVALUATION_SUMMARY_VERSION = 4


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _ik_branches(target_position: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    target_x, target_y = target_position[:2]
    cosine = (
        target_x**2
        + target_y**2
        - UPPER_ARM_LENGTH**2
        - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cosine, -1.0, 1.0)))

    def solution(elbow: float) -> np.ndarray:
        shoulder = np.arctan2(target_y, target_x) - np.arctan2(
            FOREARM_LENGTH * np.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
        )
        return np.array([shoulder, elbow], dtype=np.float64)

    return solution(elbow_open), solution(-elbow_open)


def _nearest_branch(qpos: np.ndarray, branches: tuple[np.ndarray, np.ndarray]) -> int:
    errors = [
        sum(_wrap_to_pi(float(actual - expected)) ** 2 for actual, expected in zip(qpos, branch))
        for branch in branches
    ]
    return 1 if errors[0] <= errors[1] else -1


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
        first_entry_distance_cm: float | None = None
        first_entry_joint_velocity_rad_s: float | None = None
        first_entry_end_effector_velocity_cm_s: float | None = None
        branch_sign_at_first_entry: int | None = None
        branch_sign_at_final: int | None = None
        branch_switches = 0
        previous_branch_sign: int | None = None
        max_abs_action = 0.0
        saturated_action_steps = 0
        previous_end_effector = env.data.site("end_effector").xpos.copy()
        branches = _ik_branches(target_position)
        control_dt = env.model.opt.timestep * env.frame_skip
        while not (terminated or truncated):
            action = runtime.predict(obs)
            action = np.asarray(action, dtype=np.float64)
            max_abs_action = max(max_abs_action, float(np.max(np.abs(action))))
            if np.any(np.abs(action) >= 1.0 - 1e-6):
                saturated_action_steps += 1
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            end_effector_position = env.data.site("end_effector").xpos.copy()
            end_effector_velocity_cm_s = (
                100.0
                * float(np.linalg.norm(end_effector_position - previous_end_effector))
                / control_dt
            )
            previous_end_effector = end_effector_position
            branch_sign = _nearest_branch(env.data.qpos[:2], branches)
            if (
                previous_branch_sign is not None
                and branch_sign != previous_branch_sign
            ):
                branch_switches += 1
            previous_branch_sign = branch_sign
            branch_sign_at_final = branch_sign
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    first_entry_distance_cm = distance_cm
                    first_entry_joint_velocity_rad_s = float(
                        np.linalg.norm(env.data.qvel[:2])
                    )
                    first_entry_end_effector_velocity_cm_s = end_effector_velocity_cm_s
                    branch_sign_at_first_entry = branch_sign
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
                "first_entry_distance_cm": first_entry_distance_cm,
                "first_entry_joint_velocity_rad_s": first_entry_joint_velocity_rad_s,
                "first_entry_end_effector_velocity_cm_s": first_entry_end_effector_velocity_cm_s,
                "max_held_steps": max_held_steps,
                "in_tolerance_steps": in_tolerance_steps,
                "hold_interruptions": hold_interruptions,
                "branch_sign_at_first_entry": branch_sign_at_first_entry,
                "branch_sign_at_final": branch_sign_at_final,
                "branch_switches": branch_switches,
                "max_abs_action": max_abs_action,
                "saturated_action_steps": saturated_action_steps,
                "saturated_action_fraction": saturated_action_steps / steps,
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
