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
RESEARCH_EVALUATION_SUMMARY_VERSION = 4


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _branch_diagnostics(target_position: np.ndarray, qpos: np.ndarray) -> dict:
    target_x = float(target_position[0])
    target_y = float(target_position[1])
    cos_elbow = (
        target_x**2
        + target_y**2
        - UPPER_ARM_LENGTH**2
        - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))
    solutions = {}
    for name, elbow in (("open", elbow_open), ("folded", -elbow_open)):
        shoulder = float(
            np.arctan2(target_y, target_x)
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )
        residual = np.array(
            [
                _wrap_to_pi(shoulder - float(qpos[0])),
                _wrap_to_pi(elbow - float(qpos[1])),
            ]
        )
        solutions[name] = {
            "residual_norm_radians": float(np.linalg.norm(residual)),
            "shoulder_residual_radians": float(residual[0]),
            "elbow_residual_radians": float(residual[1]),
        }
    branch = min(
        solutions,
        key=lambda name: (solutions[name]["residual_norm_radians"], name != "open"),
    )
    return {
        "branch": branch,
        "open_residual_norm_radians": solutions["open"]["residual_norm_radians"],
        "folded_residual_norm_radians": solutions["folded"][
            "residual_norm_radians"
        ],
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
        site_id = env.model.site("end_effector").id
        site_jacobian = np.zeros((3, env.model.nv), dtype=np.float64)
        angular_jacobian = np.zeros((3, env.model.nv), dtype=np.float64)
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
        max_post_entry_distance_cm = float("nan")
        max_post_entry_excursion_cm = float("nan")
        max_post_entry_endpoint_speed_cm_s = float("nan")
        post_entry_out_of_band_steps = 0
        endpoint_speed_cm_s = float("nan")
        endpoint_speed_at_first_entry_cm_s: float | None = None
        branch_at_first_entry: str | None = None
        branch_at_end: str | None = None
        branch_switches = 0
        previous_branch: str | None = None
        minimum_joint_limit_margin_degrees = float("inf")
        joint_limit_margin_at_first_entry_degrees: float | None = None
        near_joint_limit_steps = 0
        saturated_action_steps = 0
        while not (terminated or truncated):
            action = runtime.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            mujoco.mj_jacSite(
                env.model,
                env.data,
                site_jacobian,
                angular_jacobian,
                site_id,
            )
            endpoint_speed_cm_s = 100.0 * float(
                np.linalg.norm(site_jacobian @ env.data.qvel)
            )
            qpos = np.asarray(env.data.qpos[:2], dtype=np.float64)
            branch = _branch_diagnostics(target_position, qpos)
            branch_name = str(branch["branch"])
            if previous_branch is not None and branch_name != previous_branch:
                branch_switches += 1
            previous_branch = branch_name
            branch_at_end = branch_name
            joint_ranges = np.asarray(env.model.jnt_range[:2], dtype=np.float64)
            joint_limit_margin_degrees = float(
                np.degrees(
                    np.min(
                        np.minimum(
                            qpos - joint_ranges[:, 0], joint_ranges[:, 1] - qpos
                        )
                    )
                )
            )
            minimum_joint_limit_margin_degrees = min(
                minimum_joint_limit_margin_degrees, joint_limit_margin_degrees
            )
            if joint_limit_margin_degrees <= 10.0:
                near_joint_limit_steps += 1
            if np.any(np.abs(np.asarray(env.data.ctrl[:2])) >= 0.999):
                saturated_action_steps += 1
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    endpoint_speed_at_first_entry_cm_s = endpoint_speed_cm_s
                    branch_at_first_entry = branch_name
                    joint_limit_margin_at_first_entry_degrees = (
                        joint_limit_margin_degrees
                    )
            elif was_in_tolerance:
                hold_interruptions += 1
            if first_reach_step is not None:
                if np.isnan(max_post_entry_distance_cm):
                    max_post_entry_distance_cm = distance_cm
                else:
                    max_post_entry_distance_cm = max(
                        distance_cm, max_post_entry_distance_cm
                    )
                if np.isnan(max_post_entry_excursion_cm):
                    max_post_entry_excursion_cm = max(distance_cm - 1.0, 0.0)
                else:
                    max_post_entry_excursion_cm = max(
                        distance_cm - 1.0, max_post_entry_excursion_cm
                    )
                if held_steps == 0:
                    post_entry_out_of_band_steps += 1
                if np.isnan(max_post_entry_endpoint_speed_cm_s):
                    max_post_entry_endpoint_speed_cm_s = endpoint_speed_cm_s
                else:
                    max_post_entry_endpoint_speed_cm_s = max(
                        endpoint_speed_cm_s, max_post_entry_endpoint_speed_cm_s
                    )
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
                "max_post_entry_distance_cm": max_post_entry_distance_cm,
                "max_post_entry_excursion_cm": max_post_entry_excursion_cm,
                "post_entry_out_of_band_steps": post_entry_out_of_band_steps,
                "endpoint_speed_at_first_entry_cm_s": endpoint_speed_at_first_entry_cm_s,
                "max_post_entry_endpoint_speed_cm_s": max_post_entry_endpoint_speed_cm_s,
                "final_endpoint_speed_cm_s": endpoint_speed_cm_s,
                "branch_at_first_entry": branch_at_first_entry,
                "branch_at_end": branch_at_end,
                "branch_switches": branch_switches,
                "minimum_joint_limit_margin_degrees": (
                    minimum_joint_limit_margin_degrees
                ),
                "joint_limit_margin_at_first_entry_degrees": (
                    joint_limit_margin_at_first_entry_degrees
                ),
                "near_joint_limit_steps": near_joint_limit_steps,
                "saturated_action_steps": saturated_action_steps,
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
