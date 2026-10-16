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


def _wrap_angle_difference(angle: float, reference: float) -> float:
    return float((angle - reference + np.pi) % (2.0 * np.pi) - np.pi)


def _analytic_ik_branch(target_position: np.ndarray, joint_position: np.ndarray) -> str:
    """Return the nearest feasible analytic IK branch for a joint state."""
    target_x = float(target_position[0])
    target_y = float(target_position[1])
    denominator = 2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH
    cos_elbow = (
        target_x**2
        + target_y**2
        - UPPER_ARM_LENGTH**2
        - FOREARM_LENGTH**2
    ) / denominator
    if not np.isfinite(cos_elbow) or cos_elbow < -1.0 or cos_elbow > 1.0:
        return "undetermined"

    elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))

    def shoulder_for_elbow(elbow: float) -> float:
        return float(
            np.arctan2(target_y, target_x)
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )

    open_solution = np.array(
        [shoulder_for_elbow(elbow_open), elbow_open], dtype=np.float64
    )
    folded_solution = np.array(
        [shoulder_for_elbow(-elbow_open), -elbow_open], dtype=np.float64
    )
    joint_position = np.asarray(joint_position, dtype=np.float64)
    if joint_position.shape != (2,) or not np.all(np.isfinite(joint_position)):
        return "undetermined"
    distances = np.array(
        [
            np.linalg.norm(
                [
                    _wrap_angle_difference(joint_position[0], open_solution[0]),
                    _wrap_angle_difference(joint_position[1], open_solution[1]),
                ]
            ),
            np.linalg.norm(
                [
                    _wrap_angle_difference(
                        joint_position[0], folded_solution[0]
                    ),
                    _wrap_angle_difference(
                        joint_position[1], folded_solution[1]
                    ),
                ]
            ),
        ],
        dtype=np.float64,
    )
    if not np.all(np.isfinite(distances)) or np.isclose(
        distances[0], distances[1], rtol=0.0, atol=1e-12
    ):
        return "undetermined"
    return "open" if distances[0] < distances[1] else "folded"


def _finite_float(value: float) -> float | None:
    value = float(value)
    return value if np.isfinite(value) else None


def _finite_vector(values: np.ndarray) -> list[float] | None:
    values = np.asarray(values, dtype=np.float64)
    if not np.all(np.isfinite(values)):
        return None
    return [float(value) for value in values]


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
        min_distance_cm: float | None = None
        final_distance_cm: float | None = None
        first_reach_step: int | None = None
        max_held_steps = 0
        in_tolerance_steps = 0
        hold_interruptions = 0
        was_in_tolerance = False
        first_entry_ik_branch: str | None = None
        first_entry_joint_velocity: list[float] | None = None
        first_entry_joint_velocity_norm: float | None = None
        max_joint_speed_norm: float | None = None
        max_action_abs: float | None = None
        saturated_control_steps = 0
        max_substep_target_distance_cm: float | None = None
        while not (terminated or truncated):
            action = runtime.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            distance_cm = _finite_float(100.0 * float(info["distance"]))
            held_steps = int(info.get("held_steps", 0))
            if distance_cm is not None and (
                min_distance_cm is None or distance_cm < min_distance_cm
            ):
                min_distance_cm = distance_cm
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            applied_action = np.asarray(env.data.ctrl, dtype=np.float64)
            action_abs = _finite_float(np.max(np.abs(applied_action)))
            if action_abs is not None and (
                max_action_abs is None or action_abs > max_action_abs
            ):
                max_action_abs = action_abs
            if np.any(
                (
                    applied_action
                    <= np.asarray(env.action_space.low, dtype=np.float64) + 1e-12
                )
                | (
                    applied_action
                    >= np.asarray(env.action_space.high, dtype=np.float64) - 1e-12
                )
            ):
                saturated_control_steps += 1
            joint_speed_norm = _finite_float(np.linalg.norm(env.data.qvel))
            if joint_speed_norm is not None and (
                max_joint_speed_norm is None
                or joint_speed_norm > max_joint_speed_norm
            ):
                max_joint_speed_norm = joint_speed_norm
            substep_distances = np.asarray(
                env.last_step_target_distances, dtype=np.float64
            )
            if substep_distances.size:
                finite_substep_distances = substep_distances[
                    np.isfinite(substep_distances)
                ]
                if finite_substep_distances.size:
                    step_max_substep_distance_cm = _finite_float(
                        100.0 * np.max(finite_substep_distances)
                    )
                    if step_max_substep_distance_cm is not None and (
                        max_substep_target_distance_cm is None
                        or step_max_substep_distance_cm
                        > max_substep_target_distance_cm
                    ):
                        max_substep_target_distance_cm = (
                            step_max_substep_distance_cm
                        )
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    first_entry_ik_branch = _analytic_ik_branch(
                        target_position, env.data.qpos
                    )
                    first_entry_joint_velocity = _finite_vector(env.data.qvel)
                    if first_entry_joint_velocity is not None:
                        first_entry_joint_velocity_norm = _finite_float(
                            np.linalg.norm(env.data.qvel)
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
                "first_entry_ik_branch": first_entry_ik_branch,
                "final_ik_branch": _analytic_ik_branch(
                    target_position, env.data.qpos
                ),
                "first_entry_joint_velocity": first_entry_joint_velocity,
                "first_entry_joint_velocity_norm": first_entry_joint_velocity_norm,
                "max_joint_speed_norm": max_joint_speed_norm,
                "max_action_abs": max_action_abs,
                "saturated_control_steps": saturated_control_steps,
                "max_substep_target_distance_cm": max_substep_target_distance_cm,
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
