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


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _branch_distances(target_position: np.ndarray, joint_position: np.ndarray) -> tuple[float, float]:
    target_x, target_y = target_position[:2]
    cos_elbow = (
        target_x**2
        + target_y**2
        - UPPER_ARM_LENGTH**2
        - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))

    def shoulder_for_elbow(elbow: float) -> float:
        return float(
            np.arctan2(target_y, target_x)
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )

    configurations = (
        (shoulder_for_elbow(elbow_open), elbow_open),
        (shoulder_for_elbow(-elbow_open), -elbow_open),
    )
    return tuple(
        float(
            np.hypot(
                _wrap_to_pi(configuration[0] - joint_position[0]),
                _wrap_to_pi(configuration[1] - joint_position[1]),
            )
        )
        for configuration in configurations
    )


def _branch_label(target_position: np.ndarray, joint_position: np.ndarray) -> str:
    open_distance, folded_distance = _branch_distances(
        target_position, joint_position
    )
    return "open" if open_distance <= folded_distance else "folded"


def _endpoint_speed(joint_position: np.ndarray, joint_velocity: np.ndarray) -> float:
    shoulder, elbow = joint_position[:2]
    jacobian = np.array(
        [
            [
                -UPPER_ARM_LENGTH * np.sin(shoulder)
                - FOREARM_LENGTH * np.sin(shoulder + elbow),
                -FOREARM_LENGTH * np.sin(shoulder + elbow),
            ],
            [
                UPPER_ARM_LENGTH * np.cos(shoulder)
                + FOREARM_LENGTH * np.cos(shoulder + elbow),
                FOREARM_LENGTH * np.cos(shoulder + elbow),
            ],
        ]
    )
    return float(np.linalg.norm(jacobian @ joint_velocity[:2]))


def _jacobian_determinant_abs(joint_position: np.ndarray) -> float:
    return float(
        abs(UPPER_ARM_LENGTH * FOREARM_LENGTH * np.sin(joint_position[1]))
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
        initial_branch = _branch_label(target_position, env.data.qpos)
        previous_branch = initial_branch
        branch_switches = 0
        branch_counts = {"open": 0, "folded": 0}
        entry_branch: str | None = None
        final_branch = initial_branch
        entry_endpoint_speed: float | None = None
        entry_joint_speed: float | None = None
        entry_jacobian_determinant_abs: float | None = None
        max_endpoint_speed = 0.0
        min_jacobian_determinant_abs = float("inf")
        hold_endpoint_speed_sum = 0.0
        hold_endpoint_speed_count = 0
        max_hold_endpoint_speed = 0.0
        min_hold_jacobian_determinant_abs = float("inf")
        saturation_steps = 0
        action_delta_sum = 0.0
        action_delta_count = 0
        previous_applied_action: np.ndarray | None = None
        while not (terminated or truncated):
            action = runtime.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            current_branch = _branch_label(target_position, env.data.qpos)
            final_branch = current_branch
            branch_counts[current_branch] += 1
            if current_branch != previous_branch:
                branch_switches += 1
            previous_branch = current_branch
            endpoint_speed = _endpoint_speed(env.data.qpos, env.data.qvel)
            joint_speed = float(np.linalg.norm(env.data.qvel[:2]))
            jacobian_determinant_abs = _jacobian_determinant_abs(env.data.qpos)
            max_endpoint_speed = max(max_endpoint_speed, endpoint_speed)
            min_jacobian_determinant_abs = min(
                min_jacobian_determinant_abs, jacobian_determinant_abs
            )
            applied_action = np.asarray(env.data.ctrl, dtype=np.float64).copy()
            if previous_applied_action is not None:
                action_delta_sum += float(
                    np.linalg.norm(applied_action - previous_applied_action)
                )
                action_delta_count += 1
            previous_applied_action = applied_action
            if np.any(np.abs(applied_action) >= 1.0 - 1e-6):
                saturation_steps += 1
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    entry_branch = current_branch
                    entry_endpoint_speed = endpoint_speed
                    entry_joint_speed = joint_speed
                    entry_jacobian_determinant_abs = jacobian_determinant_abs
                hold_endpoint_speed_sum += endpoint_speed
                hold_endpoint_speed_count += 1
                max_hold_endpoint_speed = max(max_hold_endpoint_speed, endpoint_speed)
                min_hold_jacobian_determinant_abs = min(
                    min_hold_jacobian_determinant_abs, jacobian_determinant_abs
                )
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
                "initial_branch": initial_branch,
                "entry_branch": entry_branch,
                "final_branch": final_branch,
                "branch_switches": branch_switches,
                "branch_counts": branch_counts,
                "entry_endpoint_speed_m_per_s": entry_endpoint_speed,
                "entry_joint_speed_rad_per_s": entry_joint_speed,
                "entry_jacobian_determinant_abs_m2": entry_jacobian_determinant_abs,
                "max_endpoint_speed_m_per_s": max_endpoint_speed,
                "min_jacobian_determinant_abs_m2": min_jacobian_determinant_abs,
                "mean_hold_endpoint_speed_m_per_s": (
                    hold_endpoint_speed_sum / hold_endpoint_speed_count
                    if hold_endpoint_speed_count
                    else None
                ),
                "max_hold_endpoint_speed_m_per_s": (
                    max_hold_endpoint_speed if hold_endpoint_speed_count else None
                ),
                "min_hold_jacobian_determinant_abs_m2": (
                    min_hold_jacobian_determinant_abs
                    if hold_endpoint_speed_count
                    else None
                ),
                "saturation_steps": saturation_steps,
                "mean_action_delta": (
                    action_delta_sum / action_delta_count
                    if action_delta_count
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
            "units": {
                "distance": "cm",
                "time": "control_steps",
                "endpoint_speed": "m_per_s",
                "joint_speed": "rad_per_s",
                "jacobian_determinant": "m2",
                "action_delta": "normalized_control_units",
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
