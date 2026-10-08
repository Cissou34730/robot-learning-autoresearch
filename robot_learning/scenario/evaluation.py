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


JOINT_LIMIT_DEGREES = 170.0


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _target_branches(target_position: np.ndarray) -> dict[str, np.ndarray]:
    target_x, target_y = target_position[:2]
    radius_squared = target_x**2 + target_y**2
    cosine = (
        radius_squared - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    target_angle = float(np.arctan2(target_y, target_x))

    branches: dict[str, np.ndarray] = {}
    for name, elbow in (("elbow_positive", elbow_open), ("elbow_negative", -elbow_open)):
        shoulder = target_angle - np.arctan2(
            FOREARM_LENGTH * np.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
        )
        branches[name] = np.array([_wrap_to_pi(shoulder), elbow], dtype=np.float64)
    return branches


def _joint_limit_margin_degrees(qpos: np.ndarray) -> float:
    return float(JOINT_LIMIT_DEGREES - np.degrees(np.max(np.abs(qpos[:2]))))


def _branch_limit_margins(branches: dict[str, np.ndarray]) -> dict[str, float]:
    return {
        name: _joint_limit_margin_degrees(configuration)
        for name, configuration in branches.items()
    }


def _branch_distance(qpos: np.ndarray, configuration: np.ndarray) -> float:
    difference = np.array(
        [_wrap_to_pi(qpos[index] - configuration[index]) for index in range(2)]
    )
    return float(np.linalg.norm(difference))


def _end_effector_velocity(qpos: np.ndarray, qvel: np.ndarray) -> np.ndarray:
    shoulder, elbow = qpos[:2]
    return np.array(
        [
            -UPPER_ARM_LENGTH * np.sin(shoulder)
            - FOREARM_LENGTH * np.sin(shoulder + elbow),
            UPPER_ARM_LENGTH * np.cos(shoulder)
            + FOREARM_LENGTH * np.cos(shoulder + elbow),
        ]
    ) * qvel[0] + np.array(
        [
            -FOREARM_LENGTH * np.sin(shoulder + elbow),
            FOREARM_LENGTH * np.cos(shoulder + elbow),
        ]
    ) * qvel[1]


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
        target_branches = _target_branches(target_position)
        branch_limit_margins = _branch_limit_margins(target_branches)
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
        first_entry_qvel: list[float] | None = None
        first_entry_ee_velocity: list[float] | None = None
        first_entry_branch: str | None = None
        first_entry_joint_limit_margin_degrees: float | None = None
        first_entry_action: list[float] | None = None
        max_abs_qvel = 0.0
        max_ee_speed = 0.0
        minimum_joint_limit_margin_degrees = float("inf")
        minimum_action_margin = float("inf")
        action_saturation_steps = 0
        while not (terminated or truncated):
            action = np.asarray(runtime.predict(obs), dtype=np.float64)
            action = np.clip(action, -1.0, 1.0)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            qpos = np.asarray(env.data.qpos[:2], dtype=np.float64)
            qvel = np.asarray(env.data.qvel[:2], dtype=np.float64)
            ee_velocity = _end_effector_velocity(qpos, qvel)
            joint_limit_margin = _joint_limit_margin_degrees(qpos)
            action_margin = float(1.0 - np.max(np.abs(action)))
            minimum_joint_limit_margin_degrees = min(
                minimum_joint_limit_margin_degrees, joint_limit_margin
            )
            minimum_action_margin = min(minimum_action_margin, action_margin)
            max_abs_qvel = max(max_abs_qvel, float(np.max(np.abs(qvel))))
            max_ee_speed = max(max_ee_speed, float(np.linalg.norm(ee_velocity)))
            if np.any(np.abs(action) >= 1.0 - 1e-6):
                action_saturation_steps += 1
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    first_entry_qvel = qvel.tolist()
                    first_entry_ee_velocity = ee_velocity.tolist()
                    first_entry_branch = min(
                        target_branches,
                        key=lambda name: _branch_distance(qpos, target_branches[name]),
                    )
                    first_entry_joint_limit_margin_degrees = joint_limit_margin
                    first_entry_action = action.tolist()
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
                "first_entry_qvel_rad_s": first_entry_qvel,
                "first_entry_ee_velocity_m_s": first_entry_ee_velocity,
                "first_entry_ee_speed_m_s": (
                    None
                    if first_entry_ee_velocity is None
                    else float(np.linalg.norm(first_entry_ee_velocity))
                ),
                "first_entry_branch": first_entry_branch,
                "first_entry_joint_limit_margin_degrees": (
                    first_entry_joint_limit_margin_degrees
                ),
                "first_entry_action": first_entry_action,
                "branch_limit_margins_degrees": branch_limit_margins,
                "minimum_joint_limit_margin_degrees": (
                    minimum_joint_limit_margin_degrees
                ),
                "minimum_action_margin": minimum_action_margin,
                "action_saturation_steps": action_saturation_steps,
                "max_abs_qvel_rad_s": max_abs_qvel,
                "max_ee_speed_m_s": max_ee_speed,
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
