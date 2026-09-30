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
HIGH_EXIT_SPEED_CM_PER_SECOND = 5.0
ACTION_SATURATION_THRESHOLD = 0.95
RADIUS_BINS_CM = ((6.0, 10.0), (10.0, 14.0), (14.0, 18.0), (18.0, 20.0))
ANGLE_SECTORS = 8


def _summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "max": None}
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": len(values),
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "max": float(np.max(array)),
    }


def _radius_bin(radius_cm: float) -> str:
    for lower, upper in RADIUS_BINS_CM:
        if lower <= radius_cm < upper or (
            radius_cm == upper and upper == RADIUS_BINS_CM[-1][1]
        ):
            return f"{lower:g}-{upper:g}cm"
    raise ValueError(f"radius outside evaluation bins: {radius_cm}")


def _angle_sector(angle_degrees: float) -> str:
    sector = int(np.floor((angle_degrees + 180.0) / 45.0)) % ANGLE_SECTORS
    lower = -180 + sector * 45
    upper = lower + 45
    return f"{lower}to{upper}deg"


def _geometry_summary(diagnostics: list[dict]) -> dict[str, dict]:
    strata: dict[str, list[dict]] = {}
    for item in diagnostics:
        radius_key = str(item["target_radius_bin"])
        angle_key = str(item["target_angle_sector"])
        strata.setdefault(f"radius:{radius_key}", []).append(item)
        strata.setdefault(f"angle:{angle_key}", []).append(item)

    result: dict[str, dict] = {}
    for stratum, items in strata.items():
        entries = [item for item in items if item["first_reach_step"] is not None]
        successful = sum(bool(item["success"]) for item in items)
        result[stratum] = {
            "episodes": len(items),
            "successes": successful,
            "success_percent": 100.0 * successful / len(items),
            "entry_percent": 100.0 * len(entries) / len(items),
            "first_entry_step": _summary(
                [float(item["first_reach_step"]) for item in entries]
            ),
            "entry_speed_cm_per_second": _summary(
                [float(item["entry_speed_cm_per_second"]) for item in entries]
            ),
            "longest_hold_steps": _summary(
                [float(item["max_held_steps"]) for item in items]
            ),
            "hold_interruptions": sum(
                int(item["hold_interruptions"]) for item in items
            ),
        }
    return result


def _failure_phase(item: dict) -> str:
    if item["success"]:
        return "success"
    if item["first_reach_step"] is None:
        return "no_entry"
    if item["hold_interruptions"] > 0:
        return "hold_interrupted"
    return "entry_without_hold"


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
        control_dt_seconds = float(env.model.opt.timestep * env.frame_skip)
        previous_position = np.asarray(
            env.data.site("end_effector").xpos, dtype=np.float64
        ).copy()
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
        previous_held_steps = 0
        entry_speed_cm_per_second: float | None = None
        entry_joint_speed_rad_per_second: float | None = None
        interruption_events: list[dict] = []
        while not (terminated or truncated):
            action = runtime.predict(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            current_position = np.asarray(
                env.data.site("end_effector").xpos, dtype=np.float64
            ).copy()
            cartesian_speed_cm_per_second = (
                100.0
                * float(np.linalg.norm(current_position - previous_position))
                / control_dt_seconds
            )
            joint_speed_rad_per_second = float(
                np.linalg.norm(np.asarray(env.data.qvel, dtype=np.float64))
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
                    entry_speed_cm_per_second = cartesian_speed_cm_per_second
                    entry_joint_speed_rad_per_second = joint_speed_rad_per_second
            elif was_in_tolerance:
                hold_interruptions += 1
                action_magnitude = float(np.max(np.abs(np.asarray(action))))
                interruption_events.append(
                    {
                        "step": steps,
                        "distance_cm": distance_cm,
                        "cartesian_speed_cm_per_second": cartesian_speed_cm_per_second,
                        "joint_speed_rad_per_second": joint_speed_rad_per_second,
                        "action_max_abs": action_magnitude,
                        "previous_held_steps": previous_held_steps,
                        "signatures": [
                            (
                                "high_exit_speed"
                                if cartesian_speed_cm_per_second
                                >= HIGH_EXIT_SPEED_CM_PER_SECOND
                                else "low_exit_speed"
                            ),
                            *(
                                ["saturated_action"]
                                if action_magnitude >= ACTION_SATURATION_THRESHOLD
                                else []
                            ),
                        ],
                    }
                )
            was_in_tolerance = held_steps > 0
            previous_held_steps = held_steps
            previous_position = current_position
            if "is_success" in info:
                success = bool(info["is_success"])

        target_radius_cm = float(
            np.hypot(target_position[0], target_position[1]) * 100.0
        )
        target_angle_degrees = float(
            np.degrees(np.arctan2(target_position[1], target_position[0]))
        )
        diagnostic = {
            "episode": episode,
            "episode_seed": seed + episode,
            "success": success,
            "target_radius_cm": target_radius_cm,
            "target_radius_bin": _radius_bin(target_radius_cm),
            "target_angle_degrees": target_angle_degrees,
            "target_angle_sector": _angle_sector(target_angle_degrees),
            "min_distance_cm": min_distance_cm,
            "final_distance_cm": final_distance_cm,
            "first_reach_step": first_reach_step,
            "entry_speed_cm_per_second": entry_speed_cm_per_second,
            "entry_joint_speed_rad_per_second": entry_joint_speed_rad_per_second,
            "max_held_steps": max_held_steps,
            "in_tolerance_steps": in_tolerance_steps,
            "hold_interruptions": hold_interruptions,
            "interruption_events": interruption_events,
        }
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
        episode_diagnostics.append(diagnostic)
        if progress_callback is not None:
            progress_callback(episode + 1, episodes)

    successes = sum(episode["success"] for episode in episode_results)
    failure_phases: dict[str, int] = {}
    interruption_signatures: dict[str, int] = {}
    for diagnostic in episode_diagnostics:
        phase = _failure_phase(diagnostic)
        failure_phases[phase] = failure_phases.get(phase, 0) + 1
        for event in diagnostic["interruption_events"]:
            for signature in event["signatures"]:
                interruption_signatures[signature] = (
                    interruption_signatures.get(signature, 0) + 1
                )
    entries = [
        item for item in episode_diagnostics if item["first_reach_step"] is not None
    ]
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
            "aggregate": {
                "failure_phases": failure_phases,
                "interruption_signatures": interruption_signatures,
                "entry_percent": 100.0 * len(entries) / episodes,
                "first_entry_step": _summary(
                    [float(item["first_reach_step"]) for item in entries]
                ),
                "entry_speed_cm_per_second": _summary(
                    [float(item["entry_speed_cm_per_second"]) for item in entries]
                ),
                "entry_joint_speed_rad_per_second": _summary(
                    [
                        float(item["entry_joint_speed_rad_per_second"])
                        for item in entries
                    ]
                ),
                "longest_hold_steps": _summary(
                    [float(item["max_held_steps"]) for item in episode_diagnostics]
                ),
                "geometry_strata": _geometry_summary(episode_diagnostics),
            },
            "measurement_definitions": {
                "distance": "cm",
                "time": "control_steps",
                "control_dt_seconds": control_dt_seconds,
                "entry_speed": "finite difference of end-effector position at control boundaries",
                "high_exit_speed_cm_per_second": HIGH_EXIT_SPEED_CM_PER_SECOND,
                "action_saturation_threshold": ACTION_SATURATION_THRESHOLD,
                "radius_bins_cm": RADIUS_BINS_CM,
                "angle_sectors": ANGLE_SECTORS,
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
