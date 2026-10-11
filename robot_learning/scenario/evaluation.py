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
from robot_learning.scenario.environment import make_evaluation_env

# Bumped when the meaning of a scenario evaluation summary changes.
RESEARCH_EVALUATION_SUMMARY_VERSION = 4
Q2_BRANCH_DEADBAND_RADIANS = 1e-3


def classify_elbow_branch(q2: float) -> str:
    """Classify the signed relative elbow angle using a small zero deadband."""
    if abs(q2) <= Q2_BRANCH_DEADBAND_RADIANS:
        return "near_singular"
    return "open" if q2 > 0.0 else "folded"


def _summarize_internal_diagnostics(
    env, boundary_distances: list[float]
) -> dict[str, float | int]:
    """Summarize the opt-in internal samples without exporting the trace."""
    trace = env.diagnostic_trace
    distances = np.asarray([sample["distance"] for sample in trace], dtype=np.float64)
    qvel_norms = np.asarray(
        [np.linalg.norm(sample["qvel"]) for sample in trace], dtype=np.float64
    )
    action_magnitudes = np.asarray(
        [sample["action_magnitude"] for sample in trace], dtype=np.float64
    )
    contact_counts = np.asarray(
        [sample["contact_count"] for sample in trace], dtype=np.int64
    )

    outside_tolerance = distances > env.success_threshold
    # "Near tolerance" is the explicit 0--2 cm band for the default 1 cm
    # success threshold, rather than an additional task criterion.
    near_tolerance = distances <= 2.0 * env.success_threshold
    boundary_excursions = 0
    for step, boundary_distance in enumerate(boundary_distances, start=1):
        step_samples = [
            sample for sample in trace if sample["control_step"] == step
        ]
        if (
            boundary_distance <= env.success_threshold
            and any(
                sample["distance"] > env.success_threshold
                for sample in step_samples
            )
        ):
            boundary_excursions += 1

    return {
        "max_internal_distance_cm": float(np.max(distances) * 100.0),
        "internal_samples_outside_tolerance": int(np.count_nonzero(outside_tolerance)),
        "boundary_in_tolerance_internal_excursions": boundary_excursions,
        "max_qvel_norm": float(np.max(qvel_norms)),
        "near_tolerance_qvel_norm": float(
            np.max(qvel_norms[near_tolerance])
            if np.any(near_tolerance)
            else 0.0
        ),
        "near_tolerance_action_magnitude": float(
            np.max(action_magnitudes[near_tolerance])
            if np.any(near_tolerance)
            else 0.0
        ),
        "max_contact_count": int(np.max(contact_counts)),
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
        first_reach_q2: float | None = None
        first_reach_branch: str | None = None
        max_held_steps = 0
        in_tolerance_steps = 0
        hold_interruptions = 0
        was_in_tolerance = False
        boundary_distances: list[float] = []
        while not (terminated or truncated):
            action = runtime.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            boundary_distances.append(float(info["distance"]))
            held_steps = int(info.get("held_steps", 0))
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            max_held_steps = max(max_held_steps, held_steps)
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    first_reach_q2 = float(env.data.qpos[1])
                    first_reach_branch = classify_elbow_branch(first_reach_q2)
            elif was_in_tolerance:
                hold_interruptions += 1
            was_in_tolerance = held_steps > 0
            if "is_success" in info:
                success = bool(info["is_success"])

        final_q2 = float(env.data.qpos[1])
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
                "first_reach_q2": first_reach_q2,
                "first_reach_branch": first_reach_branch,
                "final_q2": final_q2,
                "final_branch": classify_elbow_branch(final_q2),
                "max_held_steps": max_held_steps,
                "in_tolerance_steps": in_tolerance_steps,
                "hold_interruptions": hold_interruptions,
                **_summarize_internal_diagnostics(env, boundary_distances),
            }
        )
        if progress_callback is not None:
            progress_callback(episode + 1, episodes)

    successes = sum(episode["success"] for episode in episode_results)
    return {
        "schema_version": 7,
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
                "q2": "radians",
                "time": "control_steps",
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
