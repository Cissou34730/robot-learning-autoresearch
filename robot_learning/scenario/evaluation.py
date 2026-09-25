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


def _jacobian_metrics(env) -> tuple[float, float | None]:
    jacobian_position = np.zeros((3, env.model.nv), dtype=np.float64)
    jacobian_rotation = np.zeros((3, env.model.nv), dtype=np.float64)
    mujoco.mj_jacSite(
        env.model,
        env.data,
        jacobian_position,
        jacobian_rotation,
        env.model.site("end_effector").id,
    )
    singular_values = np.linalg.svd(jacobian_position[:2, :2], compute_uv=False)
    minimum_singular_value = float(singular_values[-1])
    condition = (
        float(singular_values[0] / minimum_singular_value)
        if minimum_singular_value > 1e-12
        else None
    )
    return minimum_singular_value, condition


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
    control_limit = np.asarray(env.action_space.high, dtype=np.float64)

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
        max_abs_joint_velocity = 0.0
        max_abs_joint_acceleration = 0.0
        max_abs_control = 0.0
        max_abs_actuator_torque = 0.0
        control_saturated_steps = 0
        min_jacobian_singular_value = float("inf")
        max_jacobian_condition = 0.0
        jacobian_singular_steps = 0
        in_tolerance_max_abs_joint_velocity = 0.0
        in_tolerance_max_abs_joint_acceleration = 0.0
        in_tolerance_max_abs_control = 0.0
        in_tolerance_max_abs_actuator_torque = 0.0
        in_tolerance_control_saturated_steps = 0
        in_tolerance_min_jacobian_singular_value = float("inf")
        in_tolerance_max_jacobian_condition = 0.0
        in_tolerance_jacobian_singular_steps = 0
        entry_max_abs_joint_velocity: float | None = None
        entry_max_abs_control: float | None = None
        entry_min_jacobian_singular_value: float | None = None
        entry_jacobian_condition: float | None = None
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

            joint_velocity = np.abs(np.asarray(env.data.qvel[:2], dtype=np.float64))
            joint_acceleration = np.abs(
                np.asarray(env.data.qacc[:2], dtype=np.float64)
            )
            control = np.abs(np.asarray(env.data.ctrl[:2], dtype=np.float64))
            actuator_torque = np.abs(
                np.asarray(env.data.qfrc_actuator[:2], dtype=np.float64)
            )
            control_saturated = bool(
                np.any(control >= control_limit[:2] - 1e-6)
            )
            jacobian_minimum, jacobian_condition = _jacobian_metrics(env)
            max_abs_joint_velocity = max(
                max_abs_joint_velocity, float(np.max(joint_velocity))
            )
            max_abs_joint_acceleration = max(
                max_abs_joint_acceleration, float(np.max(joint_acceleration))
            )
            max_abs_control = max(max_abs_control, float(np.max(control)))
            max_abs_actuator_torque = max(
                max_abs_actuator_torque, float(np.max(actuator_torque))
            )
            control_saturated_steps += int(control_saturated)
            min_jacobian_singular_value = min(
                min_jacobian_singular_value, jacobian_minimum
            )
            if jacobian_condition is None:
                jacobian_singular_steps += 1
            else:
                max_jacobian_condition = max(
                    max_jacobian_condition, jacobian_condition
                )
            if held_steps > 0:
                in_tolerance_max_abs_joint_velocity = max(
                    in_tolerance_max_abs_joint_velocity,
                    float(np.max(joint_velocity)),
                )
                in_tolerance_max_abs_joint_acceleration = max(
                    in_tolerance_max_abs_joint_acceleration,
                    float(np.max(joint_acceleration)),
                )
                in_tolerance_max_abs_control = max(
                    in_tolerance_max_abs_control, float(np.max(control))
                )
                in_tolerance_max_abs_actuator_torque = max(
                    in_tolerance_max_abs_actuator_torque,
                    float(np.max(actuator_torque)),
                )
                in_tolerance_control_saturated_steps += int(control_saturated)
                in_tolerance_min_jacobian_singular_value = min(
                    in_tolerance_min_jacobian_singular_value, jacobian_minimum
                )
                if jacobian_condition is None:
                    in_tolerance_jacobian_singular_steps += 1
                else:
                    in_tolerance_max_jacobian_condition = max(
                        in_tolerance_max_jacobian_condition, jacobian_condition
                    )
                if first_reach_step == steps:
                    entry_max_abs_joint_velocity = float(np.max(joint_velocity))
                    entry_max_abs_control = float(np.max(control))
                    entry_min_jacobian_singular_value = jacobian_minimum
                    entry_jacobian_condition = jacobian_condition

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
                "max_abs_joint_velocity": max_abs_joint_velocity,
                "max_abs_joint_acceleration": max_abs_joint_acceleration,
                "max_abs_control": max_abs_control,
                "max_abs_actuator_torque": max_abs_actuator_torque,
                "control_saturated_steps": control_saturated_steps,
                "min_jacobian_singular_value": min_jacobian_singular_value,
                "max_jacobian_condition": (
                    max_jacobian_condition
                    if jacobian_singular_steps < steps
                    else None
                ),
                "jacobian_singular_steps": jacobian_singular_steps,
                "in_tolerance_max_abs_joint_velocity": (
                    in_tolerance_max_abs_joint_velocity
                    if in_tolerance_steps > 0
                    else None
                ),
                "in_tolerance_max_abs_joint_acceleration": (
                    in_tolerance_max_abs_joint_acceleration
                    if in_tolerance_steps > 0
                    else None
                ),
                "in_tolerance_max_abs_control": (
                    in_tolerance_max_abs_control
                    if in_tolerance_steps > 0
                    else None
                ),
                "in_tolerance_max_abs_actuator_torque": (
                    in_tolerance_max_abs_actuator_torque
                    if in_tolerance_steps > 0
                    else None
                ),
                "in_tolerance_control_saturated_steps": (
                    in_tolerance_control_saturated_steps
                    if in_tolerance_steps > 0
                    else None
                ),
                "in_tolerance_min_jacobian_singular_value": (
                    in_tolerance_min_jacobian_singular_value
                    if in_tolerance_steps > 0
                    else None
                ),
                "in_tolerance_max_jacobian_condition": (
                    in_tolerance_max_jacobian_condition
                    if in_tolerance_steps > 0
                    and in_tolerance_jacobian_singular_steps < in_tolerance_steps
                    else None
                ),
                "in_tolerance_jacobian_singular_steps": (
                    in_tolerance_jacobian_singular_steps
                    if in_tolerance_steps > 0
                    else None
                ),
                "entry_max_abs_joint_velocity": entry_max_abs_joint_velocity,
                "entry_max_abs_control": entry_max_abs_control,
                "entry_min_jacobian_singular_value": entry_min_jacobian_singular_value,
                "entry_jacobian_condition": entry_jacobian_condition,
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
