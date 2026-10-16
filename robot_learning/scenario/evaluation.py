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
# Bumped when the per-evaluation artifact schema changes.
RESEARCH_EVALUATION_SCHEMA_VERSION = 6


def _finite_float(value, *, field: str) -> float:
    number = float(value)
    if not np.isfinite(number):
        raise ValueError(
            f"{field} must be finite for research evaluation serialization"
        )
    return number


def _finite_array(value, *, field: str) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64).copy()
    if not np.all(np.isfinite(array)):
        raise ValueError(
            f"{field} must be finite for research evaluation serialization"
        )
    return array


def _failed_episode_step(
    env,
    trace_data,
    *,
    site_id: int,
    step: int,
    held_steps: int,
) -> dict:
    """Capture one factual post-step state without changing the environment."""
    # mj_step integrates qpos/qvel before all derived kinematics are current.
    # Forward a copy so the trace is state-consistent without changing the
    # environment data that will drive the next policy step.
    mujoco.mj_copyData(trace_data, env.model, env.data)
    mujoco.mj_forward(env.model, trace_data)

    qpos = _finite_array(trace_data.qpos, field="qpos")
    qvel = _finite_array(trace_data.qvel, field="qvel")
    end_effector_position = _finite_array(
        trace_data.site("end_effector").xpos, field="end_effector_position"
    )
    target_position = _finite_array(trace_data.mocap_pos[0], field="target_position")
    applied_action = _finite_array(trace_data.ctrl, field="action")

    jacobian_position = np.empty((3, env.model.nv), dtype=np.float64)
    mujoco.mj_jacSite(
        env.model,
        trace_data,
        jacobian_position,
        None,
        site_id,
    )
    jacobian_position = _finite_array(
        jacobian_position, field="end_effector_position_jacobian"
    )
    if jacobian_position.shape != (3, 2):
        raise ValueError(
            "the two-joint arm requires a 3x2 end-effector position Jacobian"
        )
    end_effector_velocity = _finite_array(
        jacobian_position @ qvel, field="end_effector_velocity"
    )
    jacobian_determinant = _finite_float(
        np.linalg.det(jacobian_position[:2, :2]),
        field="jacobian_determinant",
    )

    return {
        "step": int(step),
        "action": applied_action.tolist(),
        "qpos": qpos.tolist(),
        "qvel": qvel.tolist(),
        "end_effector_position": end_effector_position.tolist(),
        "end_effector_velocity": end_effector_velocity.tolist(),
        "distance_cm": _finite_float(
            100.0 * np.linalg.norm(end_effector_position - target_position),
            field="distance_cm",
        ),
        "held_steps": int(held_steps),
        "jacobian_determinant": jacobian_determinant,
        "ncon": int(trace_data.ncon),
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
    if site_id < 0:
        raise ValueError("the evaluation model has no end-effector site")
    trace_data = mujoco.MjData(env.model)

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
            elif was_in_tolerance:
                hold_interruptions += 1
            was_in_tolerance = held_steps > 0
            if "is_success" in info:
                success = bool(info["is_success"])
            trajectory.append(
                _failed_episode_step(
                    env,
                    trace_data,
                    site_id=site_id,
                    step=steps - 1,
                    held_steps=held_steps,
                )
            )

        episode_results.append(
            {
                "episode": episode,
                "episode_seed": seed + episode,
                # Scenario task outcome, not Gymnasium termination.
                "success": success,
                "reward_total": _finite_float(reward_total, field="reward_total"),
                "steps": steps,
                "terminated": bool(terminated),
                "truncated": bool(truncated),
            }
        )
        episode_diagnostics.append(
            {
                "episode": episode,
                "episode_seed": seed + episode,
                "target_radius_cm": _finite_float(
                    np.hypot(target_position[0], target_position[1]) * 100.0,
                    field="target_radius_cm",
                ),
                "target_angle_degrees": _finite_float(
                    np.degrees(np.arctan2(target_position[1], target_position[0])),
                    field="target_angle_degrees",
                ),
                "min_distance_cm": _finite_float(
                    min_distance_cm, field="min_distance_cm"
                ),
                "final_distance_cm": _finite_float(
                    final_distance_cm, field="final_distance_cm"
                ),
                "first_reach_step": first_reach_step,
                "max_held_steps": max_held_steps,
                "in_tolerance_steps": in_tolerance_steps,
                "hold_interruptions": hold_interruptions,
            }
        )
        if not success:
            episode_diagnostics[-1]["trajectory"] = trajectory
        if progress_callback is not None:
            progress_callback(episode + 1, episodes)

    successes = sum(episode["success"] for episode in episode_results)
    return {
        "schema_version": RESEARCH_EVALUATION_SCHEMA_VERSION,
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
                "trajectory": {
                    "step": "zero-based outer control step",
                    "action": "MuJoCo actuator control units",
                    "qpos": "radians",
                    "qvel": "radians per second",
                    "end_effector_position": "meters",
                    "end_effector_velocity": "meters per second",
                    "distance_cm": "cm",
                    "held_steps": "control steps",
                    "jacobian_determinant": "square meters per square radians",
                    "ncon": "contact count",
                },
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
