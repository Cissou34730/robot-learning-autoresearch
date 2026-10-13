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
from contracts.task_spec import SUCCESS_THRESHOLD
from robot_learning.scenario.environment import make_evaluation_env

# Bumped when the meaning of a scenario evaluation summary changes.
RESEARCH_EVALUATION_SUMMARY_VERSION = 4


def _finite_float(value: float | int | np.floating) -> float | None:
    result = float(value)
    return result if np.isfinite(result) else None


def _joint_limit_margins(
    joint_angles: np.ndarray, joint_ranges: np.ndarray
) -> np.ndarray | None:
    angles = np.asarray(joint_angles, dtype=np.float64)
    ranges = np.asarray(joint_ranges, dtype=np.float64)
    if angles.shape != (2,) or ranges.shape != (2, 2):
        raise ValueError("two joint angles and two joint ranges are required")
    if not np.all(np.isfinite(angles)) or not np.all(np.isfinite(ranges)):
        return None
    margins = np.minimum(angles - ranges[:, 0], ranges[:, 1] - angles)
    return margins if np.all(np.isfinite(margins)) else None


def target_ik_branch_diagnostics(
    target_position: np.ndarray, joint_ranges: np.ndarray
) -> dict[str, dict | None]:
    """Return the planar target IK branches and their limit margins.

    Angles and margins are radians.  A branch is ``None`` when the target is
    not a finite, reachable planar target.
    """
    target = np.asarray(target_position, dtype=np.float64)
    ranges = np.asarray(joint_ranges, dtype=np.float64)
    if target.ndim != 1 or target.shape[0] < 2 or ranges.shape != (2, 2):
        raise ValueError("a planar target and two joint ranges are required")
    target_x, target_y = target[:2]
    if not np.all(np.isfinite(target[:2])) or not np.all(np.isfinite(ranges)):
        return {"open": None, "folded": None}

    cos_elbow = (
        target_x**2
        + target_y**2
        - UPPER_ARM_LENGTH**2
        - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    if not np.isfinite(cos_elbow) or cos_elbow < -1.0 or cos_elbow > 1.0:
        return {"open": None, "folded": None}

    elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))
    target_angle = float(np.arctan2(target_y, target_x))
    branches: dict[str, dict | None] = {}
    for name, elbow in (("open", elbow_open), ("folded", -elbow_open)):
        shoulder = target_angle - float(
            np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )
        angles = np.asarray([shoulder, elbow], dtype=np.float64)
        margins = _joint_limit_margins(angles, ranges)
        if margins is None:
            branches[name] = None
            continue
        branches[name] = {
            "joint_angles_rad": [float(angle) for angle in angles],
            "joint_limit_margins_rad": [float(margin) for margin in margins],
            "minimum_joint_limit_margin_rad": float(np.min(margins)),
        }
    return branches


def minimum_joint_limit_margin(
    joint_angles: np.ndarray, joint_ranges: np.ndarray
) -> float | None:
    """Return the nearest joint limit in radians, or ``None`` for bad input."""
    margins = _joint_limit_margins(joint_angles, joint_ranges)
    if margins is None:
        return None
    return _finite_float(np.min(margins))


def nearest_target_ik_branch(
    branches: dict[str, dict | None], actual_configuration: np.ndarray
) -> dict | None:
    """Identify the target branch nearest an actual two-joint configuration."""
    actual = np.asarray(actual_configuration, dtype=np.float64)
    if actual.shape != (2,) or not np.all(np.isfinite(actual)):
        return None
    candidates: list[tuple[float, str]] = []
    for name in ("open", "folded"):
        branch = branches.get(name)
        if branch is None:
            continue
        angles = np.asarray(branch["joint_angles_rad"], dtype=np.float64)
        if angles.shape != (2,) or not np.all(np.isfinite(angles)):
            continue
        wrapped_delta = (angles - actual + np.pi) % (2.0 * np.pi) - np.pi
        distance = float(np.linalg.norm(wrapped_delta))
        if np.isfinite(distance):
            candidates.append((distance, name))
    if not candidates:
        return None
    distance, name = min(candidates)
    return {
        "branch": name,
        "configuration_distance_rad": distance,
    }


def _build_episode_diagnostics(
    *,
    episode: int,
    episode_seed: int,
    target_position: np.ndarray,
    target_ik_branches: dict[str, dict | None],
    min_distance_cm: float,
    final_distance_cm: float,
    first_reach_step: int | None,
    max_held_steps: int,
    in_tolerance_steps: int,
    hold_interruptions: int,
    min_joint_limit_margin_rad: float | None,
    max_joint_speed_norm_rad_per_s: float | None,
    max_absolute_action: float | None,
    max_internal_substep_distance_cm: float | None,
    max_internal_substep_distance_above_threshold_cm: float | None,
    internal_substeps_above_threshold: int,
    nearest_branch_at_first_entry: dict | None,
) -> dict:
    """Assemble one JSON-compatible diagnostic record from measured values."""
    return {
        "episode": episode,
        "episode_seed": episode_seed,
        "target_radius_cm": float(
            np.hypot(target_position[0], target_position[1]) * 100.0
        ),
        "target_angle_degrees": float(
            np.degrees(np.arctan2(target_position[1], target_position[0]))
        ),
        "target_ik_branches": target_ik_branches,
        "nearest_target_ik_branch_at_first_entry": nearest_branch_at_first_entry,
        "min_distance_cm": _finite_float(min_distance_cm),
        "final_distance_cm": _finite_float(final_distance_cm),
        "first_reach_step": first_reach_step,
        "max_held_steps": max_held_steps,
        "in_tolerance_steps": in_tolerance_steps,
        "hold_interruptions": hold_interruptions,
        "min_joint_limit_margin_rad": min_joint_limit_margin_rad,
        "max_joint_speed_norm_rad_per_s": max_joint_speed_norm_rad_per_s,
        "max_absolute_action": max_absolute_action,
        "max_internal_substep_distance_cm": max_internal_substep_distance_cm,
        "max_internal_substep_distance_above_threshold_cm": (
            max_internal_substep_distance_above_threshold_cm
        ),
        "internal_substeps_above_threshold": internal_substeps_above_threshold,
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
        joint_ranges = np.asarray(env.model.jnt_range[:2], dtype=np.float64)
        target_ik_branches = target_ik_branch_diagnostics(
            target_position, joint_ranges
        )
        min_joint_limit_margin_rad = minimum_joint_limit_margin(
            np.asarray(env.data.qpos[:2], dtype=np.float64), joint_ranges
        )
        max_joint_speed_norm_rad_per_s = _finite_float(
            np.linalg.norm(np.asarray(env.data.qvel[:2], dtype=np.float64))
        )
        max_absolute_action = 0.0
        max_internal_substep_distance_cm: float | None = None
        max_internal_substep_distance_above_threshold_cm: float | None = None
        internal_substeps_above_threshold = 0
        nearest_branch_at_first_entry: dict | None = None
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
            current_joint_limit_margin = minimum_joint_limit_margin(
                np.asarray(env.data.qpos[:2], dtype=np.float64), joint_ranges
            )
            if current_joint_limit_margin is not None:
                if min_joint_limit_margin_rad is None:
                    min_joint_limit_margin_rad = current_joint_limit_margin
                else:
                    min_joint_limit_margin_rad = min(
                        min_joint_limit_margin_rad, current_joint_limit_margin
                    )
            current_speed_norm = _finite_float(
                np.linalg.norm(np.asarray(env.data.qvel[:2], dtype=np.float64))
            )
            if current_speed_norm is not None:
                if max_joint_speed_norm_rad_per_s is None:
                    max_joint_speed_norm_rad_per_s = current_speed_norm
                else:
                    max_joint_speed_norm_rad_per_s = max(
                        max_joint_speed_norm_rad_per_s, current_speed_norm
                    )
            applied_action = np.asarray(env.last_action, dtype=np.float64)
            current_max_action = _finite_float(np.max(np.abs(applied_action)))
            if current_max_action is not None:
                max_absolute_action = max(max_absolute_action, current_max_action)
            substep_distances = np.asarray(
                env.last_substep_distances, dtype=np.float64
            )
            if substep_distances.size:
                finite_substeps = substep_distances[np.isfinite(substep_distances)]
                if finite_substeps.size:
                    current_max_substep_cm = float(np.max(finite_substeps) * 100.0)
                    if max_internal_substep_distance_cm is None:
                        max_internal_substep_distance_cm = current_max_substep_cm
                    else:
                        max_internal_substep_distance_cm = max(
                            max_internal_substep_distance_cm, current_max_substep_cm
                        )
                    above_threshold = finite_substeps[
                        finite_substeps > SUCCESS_THRESHOLD
                    ]
                    internal_substeps_above_threshold += int(above_threshold.size)
                    if above_threshold.size:
                        current_max_above_cm = float(np.max(above_threshold) * 100.0)
                        if (
                            max_internal_substep_distance_above_threshold_cm is None
                        ):
                            max_internal_substep_distance_above_threshold_cm = (
                                current_max_above_cm
                            )
                        else:
                            max_internal_substep_distance_above_threshold_cm = max(
                                max_internal_substep_distance_above_threshold_cm,
                                current_max_above_cm,
                            )
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    nearest_branch_at_first_entry = nearest_target_ik_branch(
                        target_ik_branches,
                        np.asarray(env.data.qpos[:2], dtype=np.float64),
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
            _build_episode_diagnostics(
                episode=episode,
                episode_seed=seed + episode,
                target_position=target_position,
                target_ik_branches=target_ik_branches,
                min_distance_cm=min_distance_cm,
                final_distance_cm=final_distance_cm,
                first_reach_step=first_reach_step,
                max_held_steps=max_held_steps,
                in_tolerance_steps=in_tolerance_steps,
                hold_interruptions=hold_interruptions,
                min_joint_limit_margin_rad=min_joint_limit_margin_rad,
                max_joint_speed_norm_rad_per_s=max_joint_speed_norm_rad_per_s,
                max_absolute_action=max_absolute_action,
                max_internal_substep_distance_cm=max_internal_substep_distance_cm,
                max_internal_substep_distance_above_threshold_cm=(
                    max_internal_substep_distance_above_threshold_cm
                ),
                internal_substeps_above_threshold=internal_substeps_above_threshold,
                nearest_branch_at_first_entry=nearest_branch_at_first_entry,
            )
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
            "units": {
                "distance": "cm",
                "time": "control_steps",
                "joint_angle": "rad",
                "joint_limit_margin": "rad",
                "joint_speed": "rad/s",
                "action": "normalized actuator command",
                "substep_distance_threshold": "1 cm",
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
