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

# Bumped when the meaning of a scenario evaluation summary changes.
RESEARCH_EVALUATION_SUMMARY_VERSION = 5


def _jacobian_diagnostics(env) -> dict:
    """Return planar end-effector Jacobian quantities at the current state."""
    jacobian_position = np.zeros((3, env.model.nv), dtype=np.float64)
    jacobian_rotation = np.zeros((3, env.model.nv), dtype=np.float64)
    site_id = mujoco.mj_name2id(
        env.model, mujoco.mjtObj.mjOBJ_SITE, "end_effector"
    )
    mujoco.mj_jacSite(
        env.model, env.data, jacobian_position, jacobian_rotation, site_id
    )
    planar_jacobian = jacobian_position[:2, :2]
    singular_values = np.linalg.svd(planar_jacobian, compute_uv=False)
    minimum_singular_value = float(singular_values[-1])
    condition = (
        None
        if minimum_singular_value <= 1e-12
        else float(singular_values[0] / minimum_singular_value)
    )
    return {
        "jacobian_planar": planar_jacobian.tolist(),
        "jacobian_min_singular_value": minimum_singular_value,
        "jacobian_condition": condition,
    }


def _trajectory_state(
    env,
    observation: np.ndarray,
    *,
    action: np.ndarray | None,
    distance_cm: float,
    held_steps: int,
    path_length_cm: float,
    step: int,
) -> dict:
    """Capture the post-control state used to distinguish failure mechanisms."""
    jacobian = _jacobian_diagnostics(env)
    joint_positions = np.asarray(env.data.qpos[:2], dtype=np.float64)
    joint_velocities = np.asarray(env.data.qvel[:2], dtype=np.float64)
    effector_position = np.asarray(
        env.data.site("end_effector").xpos[:2], dtype=np.float64
    )
    effector_velocity = np.asarray(
        np.asarray(jacobian["jacobian_planar"]) @ joint_velocities,
        dtype=np.float64,
    )
    branch_residuals = np.asarray(observation[7:11], dtype=np.float64)
    branch_norms = np.array(
        [
            np.linalg.norm(branch_residuals[:2]),
            np.linalg.norm(branch_residuals[2:]),
        ]
    )
    closest_branch = "open" if branch_norms[0] < branch_norms[1] else "folded"
    if np.isclose(branch_norms[0], branch_norms[1]):
        closest_branch = "ambiguous"
    applied_action = None if action is None else np.asarray(action, dtype=np.float64)
    return {
        "step": step,
        "joint_positions_radians": joint_positions.tolist(),
        "joint_velocities_radians_per_second": joint_velocities.tolist(),
        "action": None if applied_action is None else applied_action.tolist(),
        "action_saturated": (
            None
            if applied_action is None
            else [bool(abs(value) >= 1.0 - 1e-6) for value in applied_action]
        ),
        "effector_position_meters": effector_position.tolist(),
        "effector_speed_cm_per_second": float(
            np.linalg.norm(effector_velocity) * 100.0
        ),
        "joint_speed_radians_per_second": float(np.linalg.norm(joint_velocities)),
        "distance_cm": distance_cm,
        "held_steps": held_steps,
        "path_length_cm": path_length_cm,
        "ik_branch_residuals_radians": branch_residuals.tolist(),
        "closest_ik_branch": closest_branch,
        "ik_branch_residual_margin_radians": float(
            abs(branch_norms[0] - branch_norms[1])
        ),
        **jacobian,
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
        hold_exit_steps: list[int] = []
        entry_speed_cm_per_second: float | None = None
        max_effector_speed_cm_per_second = 0.0
        max_joint_speed_radians_per_second = 0.0
        saturated_control_steps = 0
        saturated_action_components = 0
        path_length_cm = 0.0
        previous_effector_position = np.asarray(
            env.data.site("end_effector").xpos[:2], dtype=np.float64
        ).copy()
        initial_state = _trajectory_state(
            env,
            obs,
            action=None,
            distance_cm=100.0
            * float(np.linalg.norm(previous_effector_position - target_position[:2])),
            held_steps=0,
            path_length_cm=0.0,
            step=0,
        )
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
                    entry_speed_cm_per_second = None
            elif was_in_tolerance:
                hold_interruptions += 1
                hold_exit_steps.append(steps)
            was_in_tolerance = held_steps > 0
            if "is_success" in info:
                success = bool(info["is_success"])
            current_effector_position = np.asarray(
                env.data.site("end_effector").xpos[:2], dtype=np.float64
            )
            path_length_cm += float(
                np.linalg.norm(current_effector_position - previous_effector_position)
                * 100.0
            )
            previous_effector_position = current_effector_position.copy()
            applied_action = np.asarray(env.data.ctrl, dtype=np.float64).copy()
            state = _trajectory_state(
                env,
                obs,
                action=applied_action,
                distance_cm=distance_cm,
                held_steps=held_steps,
                path_length_cm=path_length_cm,
                step=steps,
            )
            trajectory.append(state)
            effector_speed = float(state["effector_speed_cm_per_second"])
            joint_speed = float(state["joint_speed_radians_per_second"])
            max_effector_speed_cm_per_second = max(
                max_effector_speed_cm_per_second, effector_speed
            )
            max_joint_speed_radians_per_second = max(
                max_joint_speed_radians_per_second, joint_speed
            )
            saturated_components = sum(state["action_saturated"])
            saturated_action_components += saturated_components
            if saturated_components:
                saturated_control_steps += 1
            if held_steps > 0 and entry_speed_cm_per_second is None:
                entry_speed_cm_per_second = effector_speed

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
                "hold_exit_steps": hold_exit_steps,
                "entry_speed_cm_per_second": entry_speed_cm_per_second,
                "max_effector_speed_cm_per_second": max_effector_speed_cm_per_second,
                "max_joint_speed_radians_per_second": (
                    max_joint_speed_radians_per_second
                ),
                "saturated_control_steps": saturated_control_steps,
                "saturated_action_components": saturated_action_components,
                "path_length_cm": path_length_cm,
                "initial_state": initial_state,
                "trajectory": trajectory,
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
                "effector_speed": "cm_per_second",
                "joint_position": "radians",
                "joint_velocity": "radians_per_second",
                "jacobian": "meters_per_radian",
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
        "schema_version": 5,
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
