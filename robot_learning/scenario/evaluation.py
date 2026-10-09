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
import mujoco

from benchmark.paired_evidence import episode_outcomes
from contracts.policy_runtime import load_runtime
from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.environment import make_evaluation_env

# Bumped when the meaning of a scenario evaluation summary changes.
RESEARCH_EVALUATION_SUMMARY_VERSION = 4


def _wrap_to_pi(angle: np.ndarray | float) -> np.ndarray | float:
    return (np.asarray(angle) + np.pi) % (2.0 * np.pi) - np.pi


def _target_branches(target_position: np.ndarray) -> dict[str, np.ndarray]:
    target_x = float(target_position[0])
    target_y = float(target_position[1])
    cos_elbow = (
        target_x**2
        + target_y**2
        - UPPER_ARM_LENGTH**2
        - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))
    target_angle = float(np.arctan2(target_y, target_x))

    def shoulder_for_elbow(elbow: float) -> float:
        return target_angle - float(
            np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )

    return {
        "open": np.array([shoulder_for_elbow(elbow_open), elbow_open]),
        "folded": np.array(
            [shoulder_for_elbow(-elbow_open), -elbow_open]
        ),
    }


def _joint_limit_margin_degrees(env) -> float:
    joint_ranges = np.asarray(env.model.jnt_range[:2], dtype=np.float64)
    qpos = np.asarray(env.data.qpos[:2], dtype=np.float64)
    margins = np.minimum(qpos - joint_ranges[:, 0], joint_ranges[:, 1] - qpos)
    return float(np.degrees(np.min(margins)))


def _branch_state(env, target_branches: dict[str, np.ndarray]) -> tuple[str, bool]:
    qpos = np.asarray(env.data.qpos[:2], dtype=np.float64)
    errors = {
        name: float(np.linalg.norm(_wrap_to_pi(qpos - branch)))
        for name, branch in target_branches.items()
    }
    branch_name = min(errors, key=errors.get)
    joint_ranges = np.asarray(env.model.jnt_range[:2], dtype=np.float64)
    branch_config = target_branches[branch_name]
    valid = bool(
        np.all(branch_config >= joint_ranges[:, 0])
        and np.all(branch_config <= joint_ranges[:, 1])
    )
    return branch_name, valid


def _end_effector_speed_cm_s(env, site_id: int) -> float:
    velocity = np.empty(6, dtype=np.float64)
    mujoco.mj_objectVelocity(
        env.model,
        env.data,
        mujoco.mjtObj.mjOBJ_SITE,
        site_id,
        velocity,
        0,
    )
    return float(100.0 * np.linalg.norm(velocity[3:6]))


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
    end_effector_site_id = env.model.site("end_effector").id

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
        target_branches = _target_branches(target_position)
        branch_at_first_entry: str | None = None
        branch_valid_at_first_entry: bool | None = None
        branch_switches = 0
        previous_branch: str | None = None
        minimum_joint_limit_margin_degrees = float("inf")
        first_entry_speed_cm_s: float | None = None
        maximum_cartesian_speed_cm_s = 0.0
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
            branch_name, branch_valid = _branch_state(env, target_branches)
            if previous_branch is not None and branch_name != previous_branch:
                branch_switches += 1
            previous_branch = branch_name
            if held_steps > 0 and branch_at_first_entry is None:
                branch_at_first_entry = branch_name
                branch_valid_at_first_entry = branch_valid
                first_entry_speed_cm_s = _end_effector_speed_cm_s(
                    env, end_effector_site_id
                )
            minimum_joint_limit_margin_degrees = min(
                minimum_joint_limit_margin_degrees,
                _joint_limit_margin_degrees(env),
            )
            maximum_cartesian_speed_cm_s = max(
                maximum_cartesian_speed_cm_s,
                _end_effector_speed_cm_s(env, end_effector_site_id),
            )
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
                "branch_at_first_entry": branch_at_first_entry,
                "branch_valid_at_first_entry": branch_valid_at_first_entry,
                "branch_switches": branch_switches,
                "minimum_joint_limit_margin_degrees": (
                    minimum_joint_limit_margin_degrees
                ),
                "first_entry_speed_cm_s": first_entry_speed_cm_s,
                "maximum_cartesian_speed_cm_s": maximum_cartesian_speed_cm_s,
                "settling_steps": (
                    steps - first_reach_step
                    if success and first_reach_step is not None
                    else None
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
