"""Scenario-owned research evaluation.

This module runs a model over the deterministic evaluation panel it is asked
for and records factual task outcomes plus researcher-selected mechanism
telemetry for every episode. It draws no scientific conclusion and preselects
no policy ranking.

Anything else the current research question needs goes into `research_evidence`,
an opaque channel owned by the researcher. Filling, replacing or emptying it is
ordinary research code and requires no change to the generic AutoResearch core,
which never interprets its contents.
"""

from collections.abc import Callable
from pathlib import Path

import numpy as np

from robot_learning.paired_evidence import episode_outcomes
from robot_learning.policy_runtime import load_runtime
from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.environment import make_evaluation_env

# Bumped when the meaning of a scenario evaluation summary changes.
RESEARCH_EVALUATION_SUMMARY_VERSION = 5


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _target_branches(target_position: np.ndarray) -> np.ndarray:
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

    return np.asarray(
        [
            [shoulder_for_elbow(elbow_open), elbow_open],
            [shoulder_for_elbow(-elbow_open), -elbow_open],
        ],
        dtype=np.float64,
    )


def _kinematic_telemetry(
    qpos: np.ndarray, qvel: np.ndarray, branches: np.ndarray
) -> tuple[float, float, np.ndarray, str, float]:
    shoulder, elbow = (float(value) for value in qpos[:2])
    total_shoulder_angle = shoulder + elbow
    jacobian = np.asarray(
        [
            [
                -UPPER_ARM_LENGTH * np.sin(shoulder)
                - FOREARM_LENGTH * np.sin(total_shoulder_angle),
                -FOREARM_LENGTH * np.sin(total_shoulder_angle),
            ],
            [
                UPPER_ARM_LENGTH * np.cos(shoulder)
                + FOREARM_LENGTH * np.cos(total_shoulder_angle),
                FOREARM_LENGTH * np.cos(total_shoulder_angle),
            ],
        ],
        dtype=np.float64,
    )
    endpoint_speed_cm_s = float(
        np.linalg.norm(jacobian @ np.asarray(qvel[:2], dtype=np.float64)) * 100.0
    )
    jacobian_abs_det = float(abs(np.linalg.det(jacobian)))
    branch_errors = np.asarray(
        [
            [
                _wrap_to_pi(float(branch[0]) - shoulder),
                _wrap_to_pi(float(branch[1]) - elbow),
            ]
            for branch in branches
        ],
        dtype=np.float64,
    )
    branch_distances = np.linalg.norm(branch_errors, axis=1)
    nearest_branch_index = int(np.argmin(branch_distances))
    nearest_branch = ("open", "folded")[nearest_branch_index]
    branch_margin_rad = float(abs(branch_distances[0] - branch_distances[1]))
    return (
        endpoint_speed_cm_s,
        jacobian_abs_det,
        branch_errors,
        nearest_branch,
        branch_margin_rad,
    )


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
        target_branches = _target_branches(target_position)
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
        entry_endpoint_speed_cm_s: float | None = None
        entry_jacobian_abs_det: float | None = None
        entry_open_branch_error_rad: float | None = None
        entry_folded_branch_error_rad: float | None = None
        entry_branch: str | None = None
        entry_branch_margin_rad: float | None = None
        min_jacobian_abs_det = float("inf")
        max_endpoint_speed_cm_s = 0.0
        max_hold_endpoint_speed_cm_s = 0.0
        action_saturation_steps = 0
        action_deltas: list[float] = []
        previous_action: np.ndarray | None = None
        previous_branch: str | None = None
        branch_switches = 0
        while not (terminated or truncated):
            action = runtime.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            applied_action = np.asarray(env.data.ctrl, dtype=np.float64).copy()
            (
                endpoint_speed_cm_s,
                jacobian_abs_det,
                branch_errors,
                nearest_branch,
                branch_margin_rad,
            ) = _kinematic_telemetry(
                np.asarray(env.data.qpos, dtype=np.float64),
                np.asarray(env.data.qvel, dtype=np.float64),
                target_branches,
            )
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            min_jacobian_abs_det = min(min_jacobian_abs_det, jacobian_abs_det)
            max_endpoint_speed_cm_s = max(max_endpoint_speed_cm_s, endpoint_speed_cm_s)
            if held_steps > 0:
                max_hold_endpoint_speed_cm_s = max(
                    max_hold_endpoint_speed_cm_s, endpoint_speed_cm_s
                )
            if abs(applied_action).max() >= 1.0 - 1e-6:
                action_saturation_steps += 1
            if previous_action is not None:
                action_deltas.append(
                    float(np.linalg.norm(applied_action - previous_action))
                )
            previous_action = applied_action
            if previous_branch is not None and nearest_branch != previous_branch:
                branch_switches += 1
            previous_branch = nearest_branch
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    entry_endpoint_speed_cm_s = endpoint_speed_cm_s
                    entry_jacobian_abs_det = jacobian_abs_det
                    entry_open_branch_error_rad = float(np.linalg.norm(branch_errors[0]))
                    entry_folded_branch_error_rad = float(
                        np.linalg.norm(branch_errors[1])
                    )
                    entry_branch = nearest_branch
                    entry_branch_margin_rad = branch_margin_rad
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
                "entry_endpoint_speed_cm_s": entry_endpoint_speed_cm_s,
                "entry_jacobian_abs_det": entry_jacobian_abs_det,
                "entry_open_branch_error_rad": entry_open_branch_error_rad,
                "entry_folded_branch_error_rad": entry_folded_branch_error_rad,
                "entry_branch": entry_branch,
                "entry_branch_margin_rad": entry_branch_margin_rad,
                "branch_switches": branch_switches,
                "min_jacobian_abs_det": min_jacobian_abs_det,
                "max_endpoint_speed_cm_s": max_endpoint_speed_cm_s,
                "max_hold_endpoint_speed_cm_s": max_hold_endpoint_speed_cm_s,
                "action_saturation_steps": action_saturation_steps,
                "mean_action_delta_norm": (
                    float(np.mean(action_deltas)) if action_deltas else None
                ),
                "max_action_delta_norm": (
                    float(max(action_deltas)) if action_deltas else None
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
            "units": {
                "distance": "cm",
                "time": "control_steps",
                "endpoint_speed": "cm/s",
                "jacobian_abs_det": "m^2",
                "branch_error": "rad",
                "action": "normalized",
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
