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
from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.environment import make_evaluation_env

# Bumped when the meaning of a scenario evaluation summary changes.
RESEARCH_EVALUATION_SUMMARY_VERSION = 5
# Near-ties are reported as ambiguous rather than counted as branch switches.
BRANCH_AMBIGUITY_RAD = 0.05


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _branch_errors(target_position: np.ndarray, joint_positions: np.ndarray) -> np.ndarray:
    target_x = float(target_position[0])
    target_y = float(target_position[1])
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

    branches = (
        (shoulder_for_elbow(elbow_open), elbow_open),
        (shoulder_for_elbow(-elbow_open), -elbow_open),
    )
    return np.asarray(
        [
            np.linalg.norm(
                [
                    _wrap_to_pi(shoulder - float(joint_positions[0])),
                    _wrap_to_pi(elbow - float(joint_positions[1])),
                ]
            )
            for shoulder, elbow in branches
        ],
        dtype=np.float64,
    )


def _kinematic_snapshot(
    env,
    target_position: np.ndarray,
    site_id: int,
) -> dict:
    joint_positions = np.asarray(env.data.qpos[:2], dtype=np.float64).copy()
    joint_velocities = np.asarray(env.data.qvel[:2], dtype=np.float64).copy()
    jacobian_position = np.zeros((3, env.model.nv), dtype=np.float64)
    jacobian_rotation = np.zeros((3, env.model.nv), dtype=np.float64)
    mujoco.mj_jacSite(
        env.model,
        env.data,
        jacobian_position,
        jacobian_rotation,
        site_id,
    )
    singular_values = np.linalg.svd(
        jacobian_position[:2, :2], compute_uv=False
    )
    smallest_singular_value = float(singular_values[-1])
    condition = (
        float(singular_values[0] / smallest_singular_value)
        if smallest_singular_value > 1e-12
        else None
    )
    errors = _branch_errors(target_position, joint_positions)
    branch_index = int(np.argmin(errors))
    branch_margin = float(abs(errors[0] - errors[1]))
    branch = (
        "ambiguous"
        if branch_margin < BRANCH_AMBIGUITY_RAD
        else ("open" if branch_index == 0 else "folded")
    )
    return {
        "joint_positions_rad": joint_positions.tolist(),
        "joint_velocities_rad_s": joint_velocities.tolist(),
        "branch": branch,
        "branch_errors_rad": errors.tolist(),
        "branch_margin_rad": branch_margin,
        "jacobian_smallest_singular_value_m_per_rad": smallest_singular_value,
        "jacobian_condition": condition,
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
    site_id = mujoco.mj_name2id(
        env.model, mujoco.mjtObj.mjOBJ_SITE, "end_effector"
    )
    control_dt = float(env.model.opt.timestep * env.frame_skip)

    episode_results: list[dict] = []
    episode_diagnostics: list[dict] = []
    trajectory_diagnostics: list[dict] = []
    for episode in range(episodes):
        obs, _ = env.reset(seed=seed + episode)
        runtime.reset()
        target_position = np.asarray(env.data.mocap_pos[0], dtype=np.float64)
        initial_snapshot = _kinematic_snapshot(env, target_position, site_id)
        previous_end_effector = env.data.site("end_effector").xpos.copy()
        last_unambiguous_branch = (
            None
            if initial_snapshot["branch"] == "ambiguous"
            else initial_snapshot["branch"]
        )
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
        path_length_cm = 0.0
        max_cartesian_speed_cm_s = 0.0
        max_joint_speed_rad_s = float(
            np.max(np.abs(initial_snapshot["joint_velocities_rad_s"]))
        )
        max_action_abs = 0.0
        saturated_action_steps = 0
        min_jacobian_singular_value = float(
            initial_snapshot["jacobian_smallest_singular_value_m_per_rad"]
        )
        max_jacobian_condition = (
            initial_snapshot["jacobian_condition"] or 0.0
        )
        singular_jacobian_steps = int(
            initial_snapshot["jacobian_condition"] is None
        )
        branch_switches = 0
        ambiguous_branch_steps = int(initial_snapshot["branch"] == "ambiguous")
        entry_snapshot: dict | None = None
        entry_action: list[float] | None = None
        entry_cartesian_speed_cm_s: float | None = None
        final_snapshot = initial_snapshot
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
            applied_action = np.asarray(env.data.ctrl, dtype=np.float64).copy()
            max_action_abs = max(max_action_abs, float(np.max(np.abs(applied_action))))
            if np.any(np.isclose(np.abs(applied_action), 1.0, atol=1e-8)):
                saturated_action_steps += 1

            end_effector = env.data.site("end_effector").xpos.copy()
            displacement = float(np.linalg.norm(end_effector - previous_end_effector))
            cartesian_speed_cm_s = 100.0 * displacement / control_dt
            path_length_cm += 100.0 * displacement
            max_cartesian_speed_cm_s = max(
                max_cartesian_speed_cm_s, cartesian_speed_cm_s
            )
            previous_end_effector = end_effector

            snapshot = _kinematic_snapshot(env, target_position, site_id)
            final_snapshot = snapshot
            max_joint_speed_rad_s = max(
                max_joint_speed_rad_s,
                float(np.max(np.abs(snapshot["joint_velocities_rad_s"]))),
            )
            min_jacobian_singular_value = min(
                min_jacobian_singular_value,
                snapshot["jacobian_smallest_singular_value_m_per_rad"],
            )
            if snapshot["jacobian_condition"] is not None:
                max_jacobian_condition = max(
                    max_jacobian_condition, snapshot["jacobian_condition"]
                )
            else:
                singular_jacobian_steps += 1
            if snapshot["branch"] == "ambiguous":
                ambiguous_branch_steps += 1
            else:
                if (
                    last_unambiguous_branch is not None
                    and snapshot["branch"] != last_unambiguous_branch
                ):
                    branch_switches += 1
                last_unambiguous_branch = snapshot["branch"]
            if held_steps > 0 and entry_snapshot is None:
                entry_snapshot = snapshot
                entry_action = applied_action.tolist()
                entry_cartesian_speed_cm_s = cartesian_speed_cm_s

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
            }
        )
        trajectory_diagnostics.append(
            {
                "episode": episode,
                "episode_seed": seed + episode,
                "entry_joint_positions_rad": (
                    entry_snapshot["joint_positions_rad"]
                    if entry_snapshot is not None
                    else None
                ),
                "entry_joint_velocities_rad_s": (
                    entry_snapshot["joint_velocities_rad_s"]
                    if entry_snapshot is not None
                    else None
                ),
                "entry_branch": (
                    entry_snapshot["branch"] if entry_snapshot is not None else None
                ),
                "entry_branch_errors_rad": (
                    entry_snapshot["branch_errors_rad"]
                    if entry_snapshot is not None
                    else None
                ),
                "entry_jacobian_condition": (
                    entry_snapshot["jacobian_condition"]
                    if entry_snapshot is not None
                    else None
                ),
                "entry_jacobian_smallest_singular_value_m_per_rad": (
                    entry_snapshot["jacobian_smallest_singular_value_m_per_rad"]
                    if entry_snapshot is not None
                    else None
                ),
                "entry_action": entry_action,
                "entry_cartesian_speed_cm_s": entry_cartesian_speed_cm_s,
                "final_branch": final_snapshot["branch"],
                "final_jacobian_condition": final_snapshot["jacobian_condition"],
                "path_length_cm": path_length_cm,
                "max_cartesian_speed_cm_s": max_cartesian_speed_cm_s,
                "max_joint_speed_rad_s": max_joint_speed_rad_s,
                "max_action_abs": max_action_abs,
                "saturated_action_steps": saturated_action_steps,
                "min_jacobian_singular_value_m_per_rad": (
                    min_jacobian_singular_value
                ),
                "max_jacobian_condition": max_jacobian_condition,
                "singular_jacobian_steps": singular_jacobian_steps,
                "branch_switches": branch_switches,
                "ambiguous_branch_steps": ambiguous_branch_steps,
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
            "trajectory_diagnostics": trajectory_diagnostics,
            "units": {
                "distance": "cm",
                "time": "control_steps",
                "speed": "cm_per_s",
                "joint_position": "rad",
                "joint_velocity": "rad_per_s",
                "jacobian_singular_value": "m_per_rad",
            },
            "instrumentation_version": 1,
            "branch_ambiguity_threshold_rad": BRANCH_AMBIGUITY_RAD,
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
