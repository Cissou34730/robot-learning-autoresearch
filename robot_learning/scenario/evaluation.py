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

from robot_learning.paired_evidence import episode_outcomes
from robot_learning.policy_runtime import load_runtime
from robot_learning.scenario.environment import make_evaluation_env

# Bumped when the meaning of a scenario evaluation summary changes.
RESEARCH_EVALUATION_SUMMARY_VERSION = 4
RADIUS_BANDS_CM = (
    ("6-10cm", 6.0, 10.0),
    ("10-14cm", 10.0, 14.0),
    ("14-18cm", 14.0, 18.0),
    ("18-20cm", 18.0, 20.000001),
)


def _radius_band(radius_cm: float) -> str:
    for name, lower, upper in RADIUS_BANDS_CM:
        if lower <= radius_cm < upper:
            return name
    raise ValueError(f"radius {radius_cm} cm is outside the official bands")


def _radius_summary(
    radius_band: str, diagnostics: list[dict], results: list[dict]
) -> dict:
    selected = [
        (diagnostic, result)
        for diagnostic, result in zip(diagnostics, results, strict=True)
        if diagnostic["radius_band"] == radius_band
    ]
    if not selected:
        raise ValueError(f"no episodes found in radius band {radius_band}")
    band_diagnostics = [item[0] for item in selected]
    band_results = [item[1] for item in selected]
    first_reach_steps = [
        item["first_reach_step"]
        for item in band_diagnostics
        if item["first_reach_step"] is not None
    ]
    hold_onset_steps = [
        item["hold_onset_step"]
        for item in band_diagnostics
        if item["hold_onset_step"] is not None
    ]
    successes = sum(bool(item["success"]) for item in band_results)
    post_reach_failures = sum(
        item["failure_phase"] == "post_reach" for item in band_diagnostics
    )
    return {
        "episodes": len(selected),
        "successes": successes,
        "success_percent": 100.0 * successes / len(selected),
        "first_reach_count": len(first_reach_steps),
        "first_reach_rate_percent": 100.0 * len(first_reach_steps) / len(selected),
        "median_first_reach_step": (
            float(np.median(first_reach_steps)) if first_reach_steps else None
        ),
        "hold_onset_count": len(hold_onset_steps),
        "hold_onset_rate_percent": 100.0 * len(hold_onset_steps) / len(selected),
        "median_hold_onset_step": (
            float(np.median(hold_onset_steps)) if hold_onset_steps else None
        ),
        "median_max_hold_streak": float(
            np.median([item["max_held_steps"] for item in band_diagnostics])
        ),
        "pre_reach_failures": sum(
            item["failure_phase"] == "pre_reach" for item in band_diagnostics
        ),
        "post_reach_failures": post_reach_failures,
        "post_reach_failure_rate_percent": (
            100.0 * post_reach_failures / len(selected)
        ),
        "hold_interruptions": sum(
            item["hold_interruptions"] for item in band_diagnostics
        ),
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
        hold_onset_step: int | None = None
        first_post_reach_exit_step: int | None = None
        max_held_steps = 0
        in_tolerance_steps = 0
        hold_interruptions = 0
        was_in_tolerance = False
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
            if first_reach_step is None and distance_cm <= 100.0 * env.success_threshold:
                first_reach_step = steps
            if held_steps > 0:
                in_tolerance_steps += 1
                if hold_onset_step is None:
                    hold_onset_step = steps
            elif was_in_tolerance:
                hold_interruptions += 1
                if first_post_reach_exit_step is None:
                    first_post_reach_exit_step = steps
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
                "radius_band": _radius_band(
                    float(np.hypot(target_position[0], target_position[1]) * 100.0)
                ),
                "min_distance_cm": min_distance_cm,
                "final_distance_cm": final_distance_cm,
                "first_reach_step": first_reach_step,
                "hold_onset_step": hold_onset_step,
                "max_held_steps": max_held_steps,
                "in_tolerance_steps": in_tolerance_steps,
                "hold_interruptions": hold_interruptions,
                "first_post_reach_exit_step": first_post_reach_exit_step,
                "failure_phase": (
                    "success"
                    if success
                    else "pre_reach"
                    if first_reach_step is None
                    else "post_reach"
                ),
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
            "radius_stratified": {
                name: _radius_summary(name, episode_diagnostics, episode_results)
                for name, _, _ in RADIUS_BANDS_CM
            },
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
