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


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def classify_target_ik_branches(
    model, target_position: np.ndarray
) -> dict[str, bool | str]:
    """Classify legal open/folded IK branches using the compiled joint limits."""
    target = np.asarray(target_position, dtype=np.float64)
    if target.ndim != 1 or target.shape[0] < 2 or not np.all(
        np.isfinite(target[:2])
    ):
        raise ValueError("target_position must contain finite planar coordinates")

    x, y = float(target[0]), float(target[1])
    radius = float(np.hypot(x, y))
    cosine = (
        radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    legal_branches = {}
    shoulder_lower, shoulder_upper = np.asarray(
        model.jnt_range[0], dtype=np.float64
    )
    elbow_lower, elbow_upper = np.asarray(model.jnt_range[1], dtype=np.float64)
    bearing = float(np.arctan2(y, x))

    for branch_name, elbow_sign in (("open", 1.0), ("folded", -1.0)):
        legal = False
        if abs(cosine) <= 1.0 + 1e-12:
            elbow = elbow_sign * float(np.arccos(np.clip(cosine, -1.0, 1.0)))
            shoulder = bearing - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
            shoulder = _wrap_to_pi(float(shoulder))
            legal = (
                shoulder_lower - 1e-12 <= shoulder <= shoulder_upper + 1e-12
                and elbow_lower - 1e-12 <= elbow <= elbow_upper + 1e-12
            )
        legal_branches[branch_name] = bool(legal)

    open_legal = bool(legal_branches["open"])
    folded_legal = bool(legal_branches["folded"])
    if open_legal and folded_legal:
        union = "both"
    elif open_legal:
        union = "open_only"
    elif folded_legal:
        union = "folded_only"
    else:
        union = "none"
    return {
        "open_legal": open_legal,
        "folded_legal": folded_legal,
        "union": union,
    }


def summarize_applied_controls(
    applied_actions: list[np.ndarray], joint_velocities: list[np.ndarray]
) -> dict[str, float | int]:
    """Summarize post-clipped controls and post-step joint velocities."""
    actions = np.asarray(applied_actions, dtype=np.float64)
    velocities = np.asarray(joint_velocities, dtype=np.float64)
    if actions.ndim != 2 or velocities.ndim != 2 or len(actions) == 0:
        raise ValueError("control and velocity traces must be non-empty matrices")
    if actions.shape[0] != velocities.shape[0]:
        raise ValueError("control and velocity traces must have equal lengths")
    if not np.all(np.isfinite(actions)) or not np.all(np.isfinite(velocities)):
        raise ValueError("control and velocity traces must be finite")

    action_magnitudes = np.linalg.norm(actions, axis=1)
    velocity_magnitudes = np.linalg.norm(velocities, axis=1)
    saturated_elements = np.isclose(np.abs(actions), 1.0, atol=1e-12)
    saturated_steps = np.any(saturated_elements, axis=1)
    step_count = len(actions)
    element_count = actions.size
    return {
        "applied_action_magnitude_mean": float(np.mean(action_magnitudes)),
        "applied_action_magnitude_max": float(np.max(action_magnitudes)),
        "applied_action_saturation_steps": int(np.sum(saturated_steps)),
        "applied_action_saturation_fraction": float(
            np.mean(saturated_steps)
        ),
        "applied_action_saturation_elements": int(np.sum(saturated_elements)),
        "applied_action_saturation_element_fraction": float(
            np.sum(saturated_elements) / element_count
        ),
        "joint_velocity_magnitude_mean": float(np.mean(velocity_magnitudes)),
        "joint_velocity_magnitude_max": float(np.max(velocity_magnitudes)),
        "joint_velocity_magnitude_final": float(velocity_magnitudes[-1]),
        "joint_velocity_max_abs": float(np.max(np.abs(velocities))),
        "control_steps_recorded": int(step_count),
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
        applied_actions: list[np.ndarray] = []
        joint_velocities: list[np.ndarray] = []
        while not (terminated or truncated):
            action = runtime.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            applied_actions.append(np.array(env.data.ctrl, dtype=np.float64, copy=True))
            joint_velocities.append(
                np.array(env.data.qvel, dtype=np.float64, copy=True)
            )
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

        ik_classification = classify_target_ik_branches(env.model, target_position)
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
                "ik_open_legal": bool(ik_classification["open_legal"]),
                "ik_folded_legal": bool(ik_classification["folded_legal"]),
                "ik_branch_classification": str(ik_classification["union"]),
                "min_distance_cm": min_distance_cm,
                "final_distance_cm": final_distance_cm,
                "first_reach_step": first_reach_step,
                "max_held_steps": max_held_steps,
                "in_tolerance_steps": in_tolerance_steps,
                "hold_interruptions": hold_interruptions,
                **summarize_applied_controls(applied_actions, joint_velocities),
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
            "units": {
                "distance": "cm",
                "time": "control_steps",
                "action": "normalized_control",
                "joint_velocity": "rad_per_second",
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
