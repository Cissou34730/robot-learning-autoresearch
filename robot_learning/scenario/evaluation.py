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

from benchmark.paired_evidence import episode_outcomes
from contracts.policy_runtime import load_runtime
from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.environment import make_evaluation_env

# Bumped when the meaning of a scenario evaluation summary changes.
RESEARCH_EVALUATION_SUMMARY_VERSION = 4


_IK_BRANCHES = ("open", "folded")
_JOINT_NAMES = ("shoulder", "elbow")
_ANGLE_TOLERANCE = 1e-9


def _compiled_joint_ids(model) -> tuple[int, int]:
    """Return the compiled ids for the two task joints."""
    ids = tuple(
        mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        for name in _JOINT_NAMES
    )
    if any(joint_id < 0 for joint_id in ids):
        raise RuntimeError("the compiled model is missing a task joint")
    return ids


def _angle_in_compiled_range(angle: float, lower: float, upper: float) -> float:
    """Choose the representation of an angle nearest its analytical value."""
    candidates = [angle + (2.0 * np.pi * turns) for turns in range(-2, 3)]
    in_range = [
        candidate
        for candidate in candidates
        if lower - _ANGLE_TOLERANCE <= candidate <= upper + _ANGLE_TOLERANCE
    ]
    if in_range:
        return float(min(in_range, key=lambda candidate: abs(candidate - angle)))
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _geometry_diagnostics(model, target_position: np.ndarray) -> dict:
    """Describe analytical IK branches against the compiled joint ranges."""
    target_x = float(target_position[0])
    target_y = float(target_position[1])
    radius = float(np.hypot(target_x, target_y))
    target_angle = float(np.arctan2(target_y, target_x))
    cosine = (
        radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    joint_ids = _compiled_joint_ids(model)
    joint_ranges = [
        (float(model.jnt_range[joint_id][0]), float(model.jnt_range[joint_id][1]))
        for joint_id in joint_ids
    ]

    branches: dict[str, dict] = {}
    has_kinematic_solution = -1.0 - _ANGLE_TOLERANCE <= cosine <= 1.0 + _ANGLE_TOLERANCE
    if has_kinematic_solution:
        elbow_magnitude = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
        for branch, sign in (("open", 1.0), ("folded", -1.0)):
            elbow = sign * elbow_magnitude
            shoulder = target_angle - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
            joint_angles = [
                _angle_in_compiled_range(shoulder, *joint_ranges[0]),
                _angle_in_compiled_range(elbow, *joint_ranges[1]),
            ]
            feasible = all(
                lower - _ANGLE_TOLERANCE <= angle <= upper + _ANGLE_TOLERANCE
                for angle, (lower, upper) in zip(joint_angles, joint_ranges)
            )
            margin = (
                min(
                    min(angle - lower, upper - angle)
                    for angle, (lower, upper) in zip(joint_angles, joint_ranges)
                )
                if feasible
                else None
            )
            branches[branch] = {
                "joint_angles_rad": [float(angle) for angle in joint_angles],
                "feasible": bool(feasible),
                "range_margin_rad": None if margin is None else float(margin),
            }
    else:
        for branch in _IK_BRANCHES:
            branches[branch] = {
                "joint_angles_rad": None,
                "feasible": False,
                "range_margin_rad": None,
            }

    feasible_branches = [
        branch for branch in _IK_BRANCHES if branches[branch]["feasible"]
    ]
    if len(feasible_branches) == 2:
        range_stratum = "both_branches_feasible"
    elif feasible_branches:
        range_stratum = f"{feasible_branches[0]}_only"
    elif has_kinematic_solution:
        range_stratum = "range_infeasible"
    else:
        range_stratum = "kinematically_infeasible"

    return {
        "target_radius_m": radius,
        "target_angle_rad": target_angle,
        "branch_feasibility": {
            branch: bool(branches[branch]["feasible"]) for branch in _IK_BRANCHES
        },
        "branches": branches,
        "range_stratum": range_stratum,
    }


def _trajectory_branch_label(
    geometry: dict, measured_qpos: np.ndarray, model
) -> str:
    """Assign the nearest feasible analytical branch deterministically."""
    candidates: list[tuple[float, str]] = []
    joint_ids = _compiled_joint_ids(model)
    measured = np.asarray(
        [
            measured_qpos[int(model.jnt_qposadr[joint_id])]
            for joint_id in joint_ids
        ],
        dtype=np.float64,
    )
    for branch in _IK_BRANCHES:
        if not geometry["branches"][branch]["feasible"]:
            continue
        branch_angles = np.asarray(
            geometry["branches"][branch]["joint_angles_rad"], dtype=np.float64
        )
        angular_error = (measured - branch_angles + np.pi) % (2.0 * np.pi) - np.pi
        candidates.append((float(np.linalg.norm(angular_error)), branch))
    if not candidates:
        return "unavailable"
    # _IK_BRANCHES is ordered open then folded, making exact ties reproducible.
    return min(candidates, key=lambda item: (item[0], _IK_BRANCHES.index(item[1])))[1]


def _endpoint_speed_m_per_s(env) -> float:
    site_id = mujoco.mj_name2id(env.model, mujoco.mjtObj.mjOBJ_SITE, "end_effector")
    velocity = np.zeros(6, dtype=np.float64)
    mujoco.mj_objectVelocity(
        env.model, env.data, mujoco.mjtObj.mjOBJ_SITE, site_id, velocity, 0
    )
    # MuJoCo returns object velocity in rotational, then linear order.
    return float(np.linalg.norm(velocity[3:6]))


def _joint_speed_rad_per_s(env) -> float:
    joint_ids = _compiled_joint_ids(env.model)
    velocities = np.asarray(
        [
            env.data.qvel[int(env.model.jnt_dofadr[joint_id])]
            for joint_id in joint_ids
        ],
        dtype=np.float64,
    )
    return float(np.linalg.norm(velocities))


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
        peak_distance_cm = 0.0
        peak_endpoint_speed_m_per_s = 0.0
        final_endpoint_speed_m_per_s = float("nan")
        peak_joint_speed_rad_per_s = 0.0
        final_joint_speed_rad_per_s = float("nan")
        action_saturation_steps = 0
        per_joint_action_saturation_steps = np.zeros(2, dtype=np.int64)
        geometry = _geometry_diagnostics(env.model, target_position)
        trajectory_branch_counts = {branch: 0 for branch in _IK_BRANCHES}
        while not (terminated or truncated):
            action = runtime.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            peak_distance_cm = max(peak_distance_cm, distance_cm)
            max_held_steps = max(max_held_steps, held_steps)
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
            elif was_in_tolerance:
                hold_interruptions += 1
            was_in_tolerance = held_steps > 0
            action_array = np.asarray(action, dtype=np.float64).reshape(-1)
            saturation = np.abs(action_array) >= 1.0 - _ANGLE_TOLERANCE
            if np.any(saturation):
                action_saturation_steps += 1
            per_joint_action_saturation_steps += saturation[:2]
            final_endpoint_speed_m_per_s = _endpoint_speed_m_per_s(env)
            final_joint_speed_rad_per_s = _joint_speed_rad_per_s(env)
            peak_endpoint_speed_m_per_s = max(
                peak_endpoint_speed_m_per_s, final_endpoint_speed_m_per_s
            )
            peak_joint_speed_rad_per_s = max(
                peak_joint_speed_rad_per_s, final_joint_speed_rad_per_s
            )
            branch_label = _trajectory_branch_label(
                geometry, env.data.qpos, env.model
            )
            if branch_label in trajectory_branch_counts:
                trajectory_branch_counts[branch_label] += 1
            if "is_success" in info:
                success = bool(info["is_success"])

        trajectory_branch_label = _trajectory_branch_label(
            geometry, env.data.qpos, env.model
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
                "target_radius_m": geometry["target_radius_m"],
                "target_angle_rad": geometry["target_angle_rad"],
                "min_distance_cm": min_distance_cm,
                "peak_distance_cm": peak_distance_cm,
                "final_distance_cm": final_distance_cm,
                "first_reach_step": first_reach_step,
                "max_held_steps": max_held_steps,
                "max_uninterrupted_hold_steps": max_held_steps,
                "in_tolerance_steps": in_tolerance_steps,
                "hold_interruptions": hold_interruptions,
                "hold_interruption_count": hold_interruptions,
                "endpoint_velocity": {
                    "peak_m_per_s": peak_endpoint_speed_m_per_s,
                    "final_m_per_s": final_endpoint_speed_m_per_s,
                },
                "joint_velocity": {
                    "peak_rad_per_s": peak_joint_speed_rad_per_s,
                    "final_rad_per_s": final_joint_speed_rad_per_s,
                },
                "endpoint_speed_peak_m_per_s": peak_endpoint_speed_m_per_s,
                "endpoint_speed_final_m_per_s": final_endpoint_speed_m_per_s,
                "joint_speed_peak_rad_per_s": peak_joint_speed_rad_per_s,
                "joint_speed_final_rad_per_s": final_joint_speed_rad_per_s,
                "endpoint_velocity_m_per_s": {
                    "peak": peak_endpoint_speed_m_per_s,
                    "final": final_endpoint_speed_m_per_s,
                },
                "joint_velocity_rad_per_s": {
                    "peak": peak_joint_speed_rad_per_s,
                    "final": final_joint_speed_rad_per_s,
                },
                "action_saturation": {
                    "any": bool(action_saturation_steps),
                    "steps": action_saturation_steps,
                    "fraction": (
                        action_saturation_steps / steps if steps else 0.0
                    ),
                    "per_joint_steps": [
                        int(value) for value in per_joint_action_saturation_steps
                    ],
                    "units": "normalized_control_at_absolute_bound",
                },
                "action_saturated": bool(action_saturation_steps),
                "branch_feasibility": geometry["branch_feasibility"],
                "range_stratum": geometry["range_stratum"],
                "geometry_strata": {
                    "range": geometry["range_stratum"],
                    "trajectory_branch": trajectory_branch_label,
                },
                "trajectory_branch_label": trajectory_branch_label,
                "trajectory_branch_counts": trajectory_branch_counts,
                "ik_branches": geometry["branches"],
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
                "target_radius": "cm",
                "target_angle": "degrees",
                "time": "control_steps",
                "endpoint_velocity": "m_per_s",
                "joint_velocity": "rad_per_s",
                "joint_angles": "rad",
                "range_margin": "rad",
                "action": "normalized_control",
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
