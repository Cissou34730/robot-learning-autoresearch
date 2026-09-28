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
from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.environment import make_evaluation_env

# Bumped when the meaning of a scenario evaluation summary changes.
RESEARCH_EVALUATION_SUMMARY_VERSION = 4
JOINT_LIMIT_RADIANS = np.deg2rad(170.0)


def _endpoint_speed(qpos: np.ndarray, qvel: np.ndarray) -> float:
    angle = float(qpos[0] + qpos[1])
    shoulder_velocity = float(qvel[0])
    elbow_velocity = float(qvel[0] + qvel[1])
    velocity = np.array(
        [
            -UPPER_ARM_LENGTH * np.sin(float(qpos[0])) * shoulder_velocity
            - FOREARM_LENGTH * np.sin(angle) * elbow_velocity,
            UPPER_ARM_LENGTH * np.cos(float(qpos[0])) * shoulder_velocity
            + FOREARM_LENGTH * np.cos(angle) * elbow_velocity,
        ]
    )
    return float(np.linalg.norm(velocity))


def _jacobian_condition(qpos: np.ndarray) -> float:
    angle = float(qpos[0] + qpos[1])
    jacobian = np.array(
        [
            [
                -UPPER_ARM_LENGTH * np.sin(float(qpos[0]))
                - FOREARM_LENGTH * np.sin(angle),
                -FOREARM_LENGTH * np.sin(angle),
            ],
            [
                UPPER_ARM_LENGTH * np.cos(float(qpos[0]))
                + FOREARM_LENGTH * np.cos(angle),
                FOREARM_LENGTH * np.cos(angle),
            ],
        ]
    )
    return float(np.linalg.cond(jacobian))


def _nearest_ik_branch(observation: np.ndarray) -> str:
    open_error = float(np.linalg.norm(observation[7:9]))
    folded_error = float(np.linalg.norm(observation[9:11]))
    return "open" if open_error <= folded_error else "folded"


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
        previous_branch: str | None = None
        branch_switches = 0
        hold_endpoint_speeds: list[float] = []
        hold_joint_speeds: list[float] = []
        first_entry_branch: str | None = None
        first_entry_joint_positions: list[float] | None = None
        first_entry_joint_limit_margin_degrees: float | None = None
        first_entry_jacobian_condition: float | None = None
        first_entry_endpoint_speed_mps: float | None = None
        min_joint_limit_margin_degrees = float("inf")
        max_jacobian_condition = 0.0
        while not (terminated or truncated):
            action = runtime.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            qpos = np.asarray(env.data.qpos[:2], dtype=np.float64)
            qvel = np.asarray(env.data.qvel[:2], dtype=np.float64)
            endpoint_speed_mps = _endpoint_speed(qpos, qvel)
            joint_limit_margin_degrees = float(
                np.degrees(JOINT_LIMIT_RADIANS - np.max(np.abs(qpos)))
            )
            jacobian_condition = _jacobian_condition(qpos)
            branch = _nearest_ik_branch(obs)
            if previous_branch is not None and branch != previous_branch:
                branch_switches += 1
            previous_branch = branch
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            min_joint_limit_margin_degrees = min(
                min_joint_limit_margin_degrees, joint_limit_margin_degrees
            )
            max_jacobian_condition = max(max_jacobian_condition, jacobian_condition)
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    first_entry_branch = branch
                    first_entry_joint_positions = qpos.tolist()
                    first_entry_joint_limit_margin_degrees = (
                        joint_limit_margin_degrees
                    )
                    first_entry_jacobian_condition = jacobian_condition
                    first_entry_endpoint_speed_mps = endpoint_speed_mps
                hold_endpoint_speeds.append(endpoint_speed_mps)
                hold_joint_speeds.append(float(np.linalg.norm(qvel)))
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
                "first_entry_branch": first_entry_branch,
                "final_branch": previous_branch,
                "branch_switches": branch_switches,
                "first_entry_joint_positions_rad": first_entry_joint_positions,
                "final_joint_positions_rad": qpos.tolist(),
                "min_joint_limit_margin_degrees": min_joint_limit_margin_degrees,
                "first_entry_joint_limit_margin_degrees": (
                    first_entry_joint_limit_margin_degrees
                ),
                "first_entry_jacobian_condition": first_entry_jacobian_condition,
                "max_jacobian_condition": max_jacobian_condition,
                "first_entry_endpoint_speed_mps": first_entry_endpoint_speed_mps,
                "max_hold_endpoint_speed_mps": max(hold_endpoint_speeds, default=0.0),
                "mean_hold_endpoint_speed_mps": (
                    float(np.mean(hold_endpoint_speeds))
                    if hold_endpoint_speeds
                    else None
                ),
                "max_hold_joint_speed_rad_s": max(hold_joint_speeds, default=0.0),
                "mean_hold_joint_speed_rad_s": (
                    float(np.mean(hold_joint_speeds))
                    if hold_joint_speeds
                    else None
                ),
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
