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
from robot_learning.scenario.environment import make_evaluation_env

# Bumped when the meaning of a scenario evaluation summary changes.
RESEARCH_EVALUATION_SUMMARY_VERSION = 4


def _float_list(values: np.ndarray) -> list[float]:
    return [float(value) for value in values]


def _site_velocity(
    model: mujoco.MjModel, data: mujoco.MjData, site_id: int
) -> np.ndarray:
    spatial_velocity = np.zeros(6, dtype=np.float64)
    mujoco.mj_objectVelocity(
        model,
        data,
        mujoco.mjtObj.mjOBJ_SITE,
        site_id,
        spatial_velocity,
        0,
    )
    return spatial_velocity[3:].copy()


def _branch_residuals(target_position: np.ndarray, qpos: np.ndarray) -> dict:
    target_x = float(target_position[0])
    target_y = float(target_position[1])
    cos_elbow = (
        target_x**2 + target_y**2 - 0.12**2 - 0.10**2
    ) / (2.0 * 0.12 * 0.10)
    elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))
    target_angle = float(np.arctan2(target_y, target_x))

    def wrap_to_pi(angle: float) -> float:
        return float((angle + np.pi) % (2.0 * np.pi) - np.pi)

    def residuals(elbow: float) -> list[float]:
        shoulder = target_angle - float(
            np.arctan2(0.10 * np.sin(elbow), 0.12 + 0.10 * np.cos(elbow))
        )
        return [
            wrap_to_pi(float(qpos[0]) - shoulder),
            wrap_to_pi(float(qpos[1]) - elbow),
        ]

    open_residuals = residuals(elbow_open)
    folded_residuals = residuals(-elbow_open)
    norms = {
        "open": float(np.linalg.norm(open_residuals)),
        "folded": float(np.linalg.norm(folded_residuals)),
    }
    return {
        "open_rad": open_residuals,
        "folded_rad": folded_residuals,
        "norms_rad": norms,
        "best_branch": min(norms, key=norms.get),
        "best_norm_rad": min(norms.values()),
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
    site_id = env.model.site("end_effector").id

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
        first_reach_action: list[float] | None = None
        first_reach_qvel: list[float] | None = None
        first_reach_end_effector_velocity: list[float] | None = None
        final_action = np.zeros(2, dtype=np.float64)
        max_abs_action = 0.0
        max_end_effector_speed = 0.0
        while not (terminated or truncated):
            action = runtime.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            applied_action = np.asarray(env.data.ctrl, dtype=np.float64).copy()
            qvel = np.asarray(env.data.qvel[:2], dtype=np.float64).copy()
            end_effector_velocity = _site_velocity(env.model, env.data, site_id)
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            final_action = applied_action
            max_abs_action = max(max_abs_action, float(np.max(np.abs(applied_action))))
            max_end_effector_speed = max(
                max_end_effector_speed,
                float(np.linalg.norm(end_effector_velocity)),
            )
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    first_reach_action = _float_list(applied_action)
                    first_reach_qvel = _float_list(qvel)
                    first_reach_end_effector_velocity = _float_list(
                        end_effector_velocity
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
                "failure_class": (
                    "success"
                    if success
                    else (
                        "non_reach"
                        if first_reach_step is None
                        else (
                            "hold_interruption"
                            if hold_interruptions > 0
                            else "incomplete_hold"
                        )
                    )
                ),
                "final_qpos_rad": _float_list(np.asarray(env.data.qpos[:2])),
                "final_qvel_rad_s": _float_list(np.asarray(env.data.qvel[:2])),
                "final_action": _float_list(final_action),
                "first_reach_action": first_reach_action,
                "first_reach_qvel_rad_s": first_reach_qvel,
                "first_reach_end_effector_velocity_m_s": first_reach_end_effector_velocity,
                "final_end_effector_velocity_m_s": _float_list(
                    _site_velocity(env.model, env.data, site_id)
                ),
                "max_abs_action": max_abs_action,
                "max_end_effector_speed_m_s": max_end_effector_speed,
                "final_branch_residuals": _branch_residuals(
                    target_position, np.asarray(env.data.qpos[:2])
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
