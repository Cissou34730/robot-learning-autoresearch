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


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _branch_errors(qpos: np.ndarray, target_position: np.ndarray) -> tuple[float, float]:
    target_x, target_y = target_position[:2]
    target_angle = float(np.arctan2(target_y, target_x))
    cos_elbow = (
        target_x**2
        + target_y**2
        - UPPER_ARM_LENGTH**2
        - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))

    def shoulder_for_elbow(elbow: float) -> float:
        return target_angle - float(
            np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )

    elbow_folded = -elbow_open
    shoulder_open = shoulder_for_elbow(elbow_open)
    shoulder_folded = shoulder_for_elbow(elbow_folded)
    open_error = np.hypot(
        _wrap_to_pi(shoulder_open - float(qpos[0])),
        _wrap_to_pi(elbow_open - float(qpos[1])),
    )
    folded_error = np.hypot(
        _wrap_to_pi(shoulder_folded - float(qpos[0])),
        _wrap_to_pi(elbow_folded - float(qpos[1])),
    )
    return float(open_error), float(folded_error)


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
        first_reach_qpos: list[float] | None = None
        first_reach_qvel: list[float] | None = None
        first_reach_action: list[float] | None = None
        first_reach_branch: str | None = None
        branch_switches = 0
        previous_branch: str | None = None
        max_abs_qvel = np.zeros(2, dtype=np.float64)
        max_abs_action = np.zeros(2, dtype=np.float64)
        max_abs_qvel_during_hold = np.zeros(2, dtype=np.float64)
        final_qpos = np.zeros(2, dtype=np.float64)
        final_qvel = np.zeros(2, dtype=np.float64)
        final_action = np.zeros(2, dtype=np.float64)
        while not (terminated or truncated):
            action = runtime.predict(obs)
            action_array = np.asarray(action, dtype=np.float64).reshape(2)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            qpos = np.asarray(env.data.qpos[:2], dtype=np.float64).copy()
            qvel = np.asarray(env.data.qvel[:2], dtype=np.float64).copy()
            open_error, folded_error = _branch_errors(qpos, target_position)
            branch = "open" if open_error <= folded_error else "folded"
            if previous_branch is not None and branch != previous_branch:
                branch_switches += 1
            previous_branch = branch
            max_abs_qvel = np.maximum(max_abs_qvel, np.abs(qvel))
            max_abs_action = np.maximum(max_abs_action, np.abs(action_array))
            if held_steps > 0:
                max_abs_qvel_during_hold = np.maximum(
                    max_abs_qvel_during_hold, np.abs(qvel)
                )
            final_qpos = qpos
            final_qvel = qvel
            final_action = action_array
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    first_reach_qpos = qpos.tolist()
                    first_reach_qvel = qvel.tolist()
                    first_reach_action = action_array.tolist()
                    first_reach_branch = branch
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
                "first_reach_qpos": first_reach_qpos,
                "first_reach_qvel": first_reach_qvel,
                "first_reach_action": first_reach_action,
                "first_reach_branch": first_reach_branch,
                "branch_switches": branch_switches,
                "max_abs_qvel": max_abs_qvel.tolist(),
                "max_abs_action": max_abs_action.tolist(),
                "max_abs_qvel_during_hold": max_abs_qvel_during_hold.tolist(),
                "final_qpos": final_qpos.tolist(),
                "final_qvel": final_qvel.tolist(),
                "final_action": final_action.tolist(),
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
