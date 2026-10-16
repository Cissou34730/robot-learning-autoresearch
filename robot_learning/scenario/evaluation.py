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
RESEARCH_EVALUATION_SCHEMA_VERSION = 6
RADIUS_BIN_EDGES_CM = (6.0, 10.0, 14.0, 18.0, 20.0)


def _radius_bin_label(radius_cm: float) -> str:
    if radius_cm < RADIUS_BIN_EDGES_CM[0] or radius_cm > RADIUS_BIN_EDGES_CM[-1]:
        raise ValueError(f"target radius is outside official range: {radius_cm}")
    for lower, upper in zip(RADIUS_BIN_EDGES_CM[:-1], RADIUS_BIN_EDGES_CM[1:]):
        if radius_cm < upper:
            return f"{lower:g}-{upper:g} cm"
    return f"{RADIUS_BIN_EDGES_CM[-2]:g}-{RADIUS_BIN_EDGES_CM[-1]:g} cm"


def _empty_stratified_group() -> dict:
    return {
        "episodes": 0,
        "successes": 0,
        "success_percent": 0.0,
        "episode_indices": [],
    }


def _add_to_stratified_group(
    group: dict, success: bool, episode_index: int
) -> None:
    group["episodes"] += 1
    group["successes"] += int(success)
    group["success_percent"] = 100 * group["successes"] / group["episodes"]
    group["episode_indices"].append(episode_index)


def _stratified_diagnostics(
    episode_diagnostics: list[dict], episode_results: list[dict]
) -> dict:
    radius_bins = {
        _radius_bin_label(lower): _empty_stratified_group()
        for lower in RADIUS_BIN_EDGES_CM[:-1]
    }
    branch_groups = {
        branch: _empty_stratified_group() for branch in ("open", "folded")
    }
    for episode_index, (diagnostic, result) in enumerate(
        zip(episode_diagnostics, episode_results)
    ):
        success = bool(result["success"])
        radius_group = radius_bins[
            _radius_bin_label(diagnostic["target_radius_cm"])
        ]
        _add_to_stratified_group(radius_group, success, episode_index)
        observed_branches = set(diagnostic["branch_labels"])
        for branch in observed_branches:
            _add_to_stratified_group(
                branch_groups[branch], success, episode_index
            )
    return {
        "radius_bin_edges_cm": list(RADIUS_BIN_EDGES_CM),
        "radius_bins": radius_bins,
        # An episode that switches branches is intentionally counted in each
        # branch it visibly occupies; branch counts therefore need not sum to
        # the panel size. The indices provide compact access to the complete
        # per-episode diagnostics without choosing unrequested summary
        # statistics for those measures.
        "branches": branch_groups,
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
        final_endpoint_velocity: list[float] = []
        final_endpoint_velocity_magnitude = float("nan")
        max_endpoint_velocity_magnitude = 0.0
        final_action_magnitude = float("nan")
        max_action_magnitude = 0.0
        saturated_action_steps = 0
        final_joint_limit_margins: list[float] = []
        min_joint_limit_margin = float("inf")
        branch_labels: list[str] = []
        branch_switch_count = 0
        previous_branch_label: str | None = None
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
            endpoint_velocity = np.asarray(
                info["endpoint_linear_velocity"], dtype=np.float64
            )
            final_endpoint_velocity = endpoint_velocity.copy().tolist()
            endpoint_velocity_magnitude = float(np.linalg.norm(endpoint_velocity))
            final_endpoint_velocity_magnitude = endpoint_velocity_magnitude
            max_endpoint_velocity_magnitude = max(
                max_endpoint_velocity_magnitude, endpoint_velocity_magnitude
            )
            applied_action = np.asarray(info["applied_action"], dtype=np.float64)
            action_magnitude = float(np.linalg.norm(applied_action))
            final_action_magnitude = action_magnitude
            max_action_magnitude = max(max_action_magnitude, action_magnitude)
            if np.any(np.abs(applied_action) >= 1.0):
                saturated_action_steps += 1
            final_joint_limit_margins = [
                float(margin)
                for margin in info["joint_limit_margins"]
            ]
            min_joint_limit_margin = min(
                min_joint_limit_margin,
                min(final_joint_limit_margins),
            )
            elbow_position = float(info["joint_positions"][1])
            branch_label = "open" if elbow_position >= 0.0 else "folded"
            branch_labels.append(branch_label)
            if (
                previous_branch_label is not None
                and branch_label != previous_branch_label
            ):
                branch_switch_count += 1
            previous_branch_label = branch_label
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
                "final_endpoint_velocity": final_endpoint_velocity,
                "final_endpoint_velocity_magnitude": final_endpoint_velocity_magnitude,
                "max_endpoint_velocity_magnitude": max_endpoint_velocity_magnitude,
                "final_action_magnitude": final_action_magnitude,
                "max_action_magnitude": max_action_magnitude,
                "saturated_action_steps": saturated_action_steps,
                "final_joint_limit_margins": final_joint_limit_margins,
                "min_joint_limit_margin": min_joint_limit_margin,
                "branch_labels": branch_labels,
                "branch_switch_count": branch_switch_count,
            }
        )
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
            "stratified_diagnostics": _stratified_diagnostics(
                episode_diagnostics, episode_results
            ),
            "units": {
                "distance": "cm",
                "time": "control_steps",
                "endpoint_velocity": "m/s",
                "action": "normalized actuator command",
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
