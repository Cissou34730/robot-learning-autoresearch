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
from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from contracts.policy_runtime import load_runtime
from robot_learning.scenario.environment import make_evaluation_env

# Bumped when the meaning of a scenario evaluation summary changes.
RESEARCH_EVALUATION_SUMMARY_VERSION = 4


def _wrap_to_pi(angle: np.ndarray) -> np.ndarray:
    return (angle + np.pi) % (2.0 * np.pi) - np.pi


def _planar_jacobians(qpos: np.ndarray) -> np.ndarray:
    """Return the contract forward-kinematic Jacobian for each qpos sample."""
    shoulder = qpos[:, 0]
    total = shoulder + qpos[:, 1]
    return np.stack(
        [
            np.stack(
                [
                    -UPPER_ARM_LENGTH * np.sin(shoulder)
                    - FOREARM_LENGTH * np.sin(total),
                    -FOREARM_LENGTH * np.sin(total),
                ],
                axis=1,
            ),
            np.stack(
                [
                    UPPER_ARM_LENGTH * np.cos(shoulder)
                    + FOREARM_LENGTH * np.cos(total),
                    FOREARM_LENGTH * np.cos(total),
                ],
                axis=1,
            ),
        ],
        axis=1,
    )


def _branch_configurations(target_position: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    target_x, target_y = target_position[:2]
    elbow_open = float(
        np.arccos(
            np.clip(
                (
                    target_x**2
                    + target_y**2
                    - UPPER_ARM_LENGTH**2
                    - FOREARM_LENGTH**2
                )
                / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH),
                -1.0,
                1.0,
            )
        )
    )
    target_angle = float(np.arctan2(target_y, target_x))

    def shoulder_for_elbow(elbow: float) -> float:
        return target_angle - float(
            np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )

    return (
        np.asarray([shoulder_for_elbow(elbow_open), elbow_open]),
        np.asarray([shoulder_for_elbow(-elbow_open), -elbow_open]),
    )


def _aggregate_internal_diagnostics(
    *,
    env,
    target_position: np.ndarray,
    internal_distances: list[np.ndarray],
    internal_qpos: list[np.ndarray],
    internal_qvel: list[np.ndarray],
    internal_actions: list[np.ndarray],
) -> dict:
    distances_m = np.concatenate(internal_distances)
    qpos = np.concatenate(internal_qpos, axis=0)
    qvel = np.concatenate(internal_qvel, axis=0)
    actions = np.concatenate(internal_actions, axis=0)

    jacobians = _planar_jacobians(qpos)
    jacobian_determinants = np.linalg.det(jacobians)
    condition_numbers: list[float] = []
    cartesian_velocity_norms: list[float] = []
    for jacobian, velocity in zip(jacobians, qvel, strict=True):
        singular_values = np.linalg.svd(jacobian, compute_uv=False)
        if singular_values[-1] <= np.finfo(np.float64).eps:
            condition_numbers.append(float(np.finfo(np.float64).max))
        else:
            condition_numbers.append(
                float(singular_values[0] / singular_values[-1])
            )
        cartesian_velocity_norms.append(
            float(np.linalg.norm(jacobian @ velocity))
        )

    open_branch, folded_branch = _branch_configurations(target_position)
    open_residuals = np.linalg.norm(
        _wrap_to_pi(qpos - open_branch), axis=1
    )
    folded_residuals = np.linalg.norm(
        _wrap_to_pi(qpos - folded_branch), axis=1
    )
    elbow_signs = np.sign(qpos[:, 1]).astype(np.int8)
    negative_sign_samples = int(np.count_nonzero(elbow_signs < 0))
    zero_sign_samples = int(np.count_nonzero(elbow_signs == 0))
    positive_sign_samples = int(np.count_nonzero(elbow_signs > 0))
    if positive_sign_samples > negative_sign_samples:
        realized_elbow_sign = 1
    elif negative_sign_samples > positive_sign_samples:
        realized_elbow_sign = -1
    else:
        realized_elbow_sign = 0

    joint_ranges = np.asarray(env.model.jnt_range[: qpos.shape[1]], dtype=float)
    joint_limit_margins = np.minimum(
        qpos - joint_ranges[:, 0], joint_ranges[:, 1] - qpos
    )
    saturated_components = np.abs(actions) >= (1.0 - 1e-12)
    action_component_count = int(actions.size)

    return {
        "internal_step_samples": int(distances_m.size),
        "internal_step_min_distance_cm": float(np.min(distances_m) * 100.0),
        "internal_step_max_distance_cm": float(np.max(distances_m) * 100.0),
        "internal_out_of_tolerance_samples": int(
            np.count_nonzero(distances_m > env.success_threshold)
        ),
        "action_saturation_fraction": float(
            np.count_nonzero(saturated_components) / action_component_count
        ),
        "action_saturated_components": int(
            np.count_nonzero(saturated_components)
        ),
        "action_components_observed": action_component_count,
        "joint_velocity_max_rad_per_s": float(
            np.max(np.linalg.norm(qvel, axis=1))
        ),
        "joint_velocity_mean_rad_per_s": float(
            np.mean(np.linalg.norm(qvel, axis=1))
        ),
        "cartesian_velocity_max_m_per_s": float(
            np.max(cartesian_velocity_norms)
        ),
        "cartesian_velocity_mean_m_per_s": float(
            np.mean(cartesian_velocity_norms)
        ),
        "realized_elbow_sign": realized_elbow_sign,
        "realized_elbow_sign_final": int(elbow_signs[-1]),
        "realized_elbow_sign_samples": {
            "negative": negative_sign_samples,
            "zero": zero_sign_samples,
            "positive": positive_sign_samples,
        },
        "ik_open_branch_residual_min_rad": float(np.min(open_residuals)),
        "ik_open_branch_residual_mean_rad": float(np.mean(open_residuals)),
        "ik_open_branch_residual_final_rad": float(open_residuals[-1]),
        "ik_folded_branch_residual_min_rad": float(np.min(folded_residuals)),
        "ik_folded_branch_residual_mean_rad": float(np.mean(folded_residuals)),
        "ik_folded_branch_residual_final_rad": float(folded_residuals[-1]),
        "jacobian_determinant_min_m2": float(np.min(jacobian_determinants)),
        "jacobian_determinant_max_m2": float(np.max(jacobian_determinants)),
        "jacobian_determinant_min_abs_m2": float(
            np.min(np.abs(jacobian_determinants))
        ),
        "jacobian_condition_number_max": float(np.max(condition_numbers)),
        "jacobian_condition_number_mean": float(np.mean(condition_numbers)),
        "joint_limit_margin_min_rad": float(np.min(joint_limit_margins)),
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
    env = make_evaluation_env(
        policy_runtime=runtime, evaluation_diagnostics=True
    )

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
        internal_distances: list[np.ndarray] = []
        internal_qpos: list[np.ndarray] = []
        internal_qvel: list[np.ndarray] = []
        internal_actions: list[np.ndarray] = []
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
            diagnostics = info["evaluation_diagnostics"]
            internal_distances.append(
                np.asarray(diagnostics["internal_distance_m"], dtype=np.float64)
            )
            internal_qpos.append(
                np.asarray(diagnostics["internal_qpos_rad"], dtype=np.float64)
            )
            internal_qvel.append(
                np.asarray(
                    diagnostics["internal_qvel_rad_per_s"], dtype=np.float64
                )
            )
            internal_actions.append(
                np.asarray(
                    diagnostics["internal_applied_action"], dtype=np.float64
                )
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
        episode_diagnostic = {
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
            "max_held_run_control_steps": max_held_steps,
            "in_tolerance_steps": in_tolerance_steps,
            "hold_interruptions": hold_interruptions,
        }
        episode_diagnostic.update(
            _aggregate_internal_diagnostics(
                env=env,
                target_position=target_position,
                internal_distances=internal_distances,
                internal_qpos=internal_qpos,
                internal_qvel=internal_qvel,
                internal_actions=internal_actions,
            )
        )
        episode_diagnostics.append(episode_diagnostic)
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
                "target_angle": "degrees",
                "time": "control_steps",
                "internal_samples": "mujoco_steps",
                "qpos": "rad",
                "qvel": "rad_per_s",
                "action": "normalized_control",
                "joint_velocity": "rad_per_s",
                "cartesian_velocity": "m_per_s",
                "ik_branch_residual": "rad",
                "jacobian_determinant": "m2",
                "jacobian_condition_number": "dimensionless",
                "joint_limit_margin": "rad",
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
