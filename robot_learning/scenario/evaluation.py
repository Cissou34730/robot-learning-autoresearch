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


def build_step_diagnostic(
    model,
    data,
    *,
    control_step: int,
    distance_cm: float,
    held_steps: int,
    action,
    in_tolerance: bool | None = None,
) -> dict:
    """Return JSON-compatible kinematic diagnostics at a post-step boundary.

    The site Jacobian is computed from the current MuJoCo state rather than
    from a site-velocity convenience field.  A non-full-rank planar Jacobian
    has an infinite condition number; otherwise the condition number is the
    ratio of its largest to smallest singular value.  The zero elbow
    convention is ``open`` (the non-negative-q2 branch).
    """
    qpos = np.asarray(data.qpos, dtype=np.float64)
    qvel = np.asarray(data.qvel, dtype=np.float64)
    jacobian_position = np.zeros((3, model.nv), dtype=np.float64)
    jacobian_rotation = np.zeros((3, model.nv), dtype=np.float64)
    site_id = mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_SITE, "end_effector"
    )
    if site_id < 0:
        raise ValueError("the evaluation model has no end-effector site")
    mujoco.mj_jacSite(
        model, data, jacobian_position, jacobian_rotation, site_id
    )
    planar_jacobian = jacobian_position[:2, :]
    singular_values = np.linalg.svd(planar_jacobian, compute_uv=False)
    rank_tolerance = (
        np.finfo(np.float64).eps
        * max(planar_jacobian.shape)
        * (float(singular_values[0]) if singular_values.size else 0.0)
    )
    rank_lost = (
        not np.all(np.isfinite(singular_values))
        or not singular_values.size
        or float(singular_values[-1]) <= rank_tolerance
    )
    condition_number = (
        float("inf")
        if rank_lost
        else float(singular_values[0] / singular_values[-1])
    )

    # The official model has two hinge joints whose qpos/qvel coordinates are
    # the first two generalized coordinates.  Keep both per-joint margins and
    # their limiting value for direct interpretation.
    joint_positions = qpos[:2]
    joint_ranges = np.asarray(model.jnt_range[:2], dtype=np.float64)
    joint_limit_margins = np.minimum(
        joint_positions - joint_ranges[:, 0],
        joint_ranges[:, 1] - joint_positions,
    )
    if in_tolerance is None:
        in_tolerance = held_steps > 0

    planar_velocity_cm_s = planar_jacobian @ qvel * 100.0
    return {
        "control_step": int(control_step),
        "distance_cm": float(distance_cm),
        "held_steps": int(held_steps),
        "in_tolerance": bool(in_tolerance),
        "qpos_rad": [float(value) for value in joint_positions],
        "qvel_rad": [float(value) for value in qvel[:2]],
        "planar_ee_velocity_cm_s": [
            float(value) for value in planar_velocity_cm_s
        ],
        "action": [
            float(value) for value in np.asarray(action, dtype=np.float64).reshape(-1)
        ],
        "jacobian_singular_values": [
            float(value) for value in singular_values
        ],
        "jacobian_condition_number": condition_number,
        "joint_limit_margins_rad": [
            float(value) for value in joint_limit_margins
        ],
        "joint_limit_margin_rad": float(np.min(joint_limit_margins)),
        "elbow_branch": "open" if joint_positions[1] >= 0.0 else "folded",
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
        trajectory: list[dict] = []
        velocity_at_first_reach_cm_s: float | None = None
        maximum_sampled_velocity_cm_s = 0.0
        while not (terminated or truncated):
            action = runtime.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            in_tolerance = distance_cm <= 100.0 * env.success_threshold
            step_diagnostic = build_step_diagnostic(
                env.model,
                env.data,
                control_step=steps,
                distance_cm=distance_cm,
                held_steps=held_steps,
                action=env.data.ctrl.copy(),
                in_tolerance=in_tolerance,
            )
            trajectory.append(step_diagnostic)
            sampled_velocity_cm_s = float(
                np.linalg.norm(step_diagnostic["planar_ee_velocity_cm_s"])
            )
            maximum_sampled_velocity_cm_s = max(
                maximum_sampled_velocity_cm_s, sampled_velocity_cm_s
            )
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    velocity_at_first_reach_cm_s = sampled_velocity_cm_s
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
                "trajectory": trajectory,
                "velocity_at_first_reach_cm_s": velocity_at_first_reach_cm_s,
                "maximum_sampled_velocity_cm_s": maximum_sampled_velocity_cm_s,
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
            "diagnostic_conventions": {
                "elbow_branch": "open for q2 >= 0 radians, folded for q2 < 0",
                "jacobian_condition_number": (
                    "largest/smallest singular value; inf when planar rank is lost"
                ),
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
