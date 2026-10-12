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
RESEARCH_EVALUATION_SUMMARY_VERSION = 5


def _joint_state(model, data) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return the two compiled joint positions, velocities and ranges."""
    if int(model.njnt) < 2:
        raise ValueError("the two-joint diagnostic requires two compiled joints")
    qpos = np.asarray(
        [data.qpos[int(model.jnt_qposadr[index])] for index in range(2)],
        dtype=np.float64,
    )
    qvel = np.asarray(
        [data.qvel[int(model.jnt_dofadr[index])] for index in range(2)],
        dtype=np.float64,
    )
    ranges = np.asarray(model.jnt_range[:2], dtype=np.float64)
    if ranges.shape != (2, 2) or not np.all(np.isfinite(ranges)):
        raise ValueError("compiled joint ranges are unavailable")
    return qpos, qvel, ranges


def _compiled_joint_ranges(model) -> np.ndarray:
    """Return the two scalar joint ranges compiled by MuJoCo."""
    if int(model.njnt) < 2:
        raise ValueError("the two-joint diagnostic requires two compiled joints")
    ranges = np.asarray(model.jnt_range[:2], dtype=np.float64)
    if ranges.shape != (2, 2) or not np.all(np.isfinite(ranges)):
        raise ValueError("compiled joint ranges are unavailable")
    return ranges


def _angle_candidates(angle: float, lower: float, upper: float) -> list[float]:
    """Represent an angle with a value inside a compiled joint range."""
    turns = range(
        int(np.floor((lower - angle) / (2.0 * np.pi))) - 1,
        int(np.ceil((upper - angle) / (2.0 * np.pi))) + 2,
    )
    return [
        float(angle + (2.0 * np.pi * turn))
        for turn in turns
        if lower <= angle + (2.0 * np.pi * turn) <= upper
    ]


def analytic_ik_branch_context(
    target_position: np.ndarray,
    model,
    observed_qpos: np.ndarray | None = None,
) -> dict:
    """Describe analytic open/folded IK branches using compiled limits.

    The labels are explicit: ``open`` has a non-negative elbow angle and
    ``folded`` has a non-positive elbow angle.  The target solutions are
    analytic planar solutions; the observed-state portion reports the nearest
    feasible solution, or ``None``/``ambiguous`` when that distinction is not
    available.
    """
    ranges = _compiled_joint_ranges(model)
    target = np.asarray(target_position, dtype=np.float64).reshape(-1)
    result = {
        "label_definition": {
            "open": "analytic elbow angle >= 0 rad",
            "folded": "analytic elbow angle <= 0 rad",
        },
        "feasible_branches": [],
        "solutions": {},
        "nearest_branch": None,
        "nearest_distances_rad": {},
        "ambiguous": False,
    }
    if target.size < 2 or not np.all(np.isfinite(target[:2])):
        return result

    target_x, target_y = target[:2]
    radius_squared = float(target_x**2 + target_y**2)
    cosine = (
        radius_squared
        - UPPER_ARM_LENGTH**2
        - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    if cosine < -1.0 - 1e-10 or cosine > 1.0 + 1e-10:
        return result
    elbow_magnitude = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    target_angle = float(np.arctan2(target_y, target_x))

    branch_candidates: dict[str, tuple[float, float]] = {}
    for label, elbow in (
        ("open", elbow_magnitude),
        ("folded", -elbow_magnitude),
    ):
        shoulder = float(
            target_angle
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )
        shoulder_values = _angle_candidates(
            shoulder, float(ranges[0, 0]), float(ranges[0, 1])
        )
        elbow_values = _angle_candidates(
            elbow, float(ranges[1, 0]), float(ranges[1, 1])
        )
        feasible = bool(shoulder_values and elbow_values)
        solution = {
            "shoulder_rad": float(shoulder_values[0] if shoulder_values else shoulder),
            "elbow_rad": float(elbow_values[0] if elbow_values else elbow),
            "feasible": feasible,
        }
        result["solutions"][label] = solution
        if feasible:
            result["feasible_branches"].append(label)
            branch_candidates[label] = (
                solution["shoulder_rad"],
                solution["elbow_rad"],
            )

    if observed_qpos is None or not branch_candidates:
        return result
    observed = np.asarray(observed_qpos, dtype=np.float64).reshape(-1)
    if observed.size < 2 or not np.all(np.isfinite(observed[:2])):
        return result
    distances = {
        label: float(
            np.linalg.norm(
                np.arctan2(
                    np.sin(np.asarray(candidate) - observed[:2]),
                    np.cos(np.asarray(candidate) - observed[:2]),
                )
            )
        )
        for label, candidate in branch_candidates.items()
    }
    result["nearest_distances_rad"] = distances
    nearest_distance = min(distances.values())
    nearest = [
        label
        for label, distance in distances.items()
        if abs(distance - nearest_distance) <= 1e-9
    ]
    if len(nearest) == 1:
        result["nearest_branch"] = nearest[0]
    else:
        result["nearest_branch"] = "ambiguous"
        result["ambiguous"] = True
    return result


def initialize_episode_diagnostics(
    model,
    data,
    target_position: np.ndarray,
    control_interval_seconds: float,
) -> dict:
    """Create observational state for one episode at its reset boundary."""
    if control_interval_seconds <= 0.0:
        raise ValueError("the control interval must be positive")
    return {
        "previous_end_effector_position": np.asarray(
            data.site("end_effector").xpos, dtype=np.float64
        ).copy(),
        "target_position": np.asarray(target_position, dtype=np.float64).copy(),
        "control_interval_seconds": float(control_interval_seconds),
        "max_joint_speed_norm": 0.0,
        "max_cartesian_speed": 0.0,
        "min_joint_limit_margin": float("inf"),
        "first_entry": None,
        "final_boundary": None,
        "target_branch_context": analytic_ik_branch_context(
            target_position, model
        ),
    }


def update_episode_diagnostics(
    state: dict,
    model,
    data,
    *,
    in_tolerance: bool,
) -> None:
    """Record one post-step control-boundary state without changing it."""
    qpos, qvel, ranges = _joint_state(model, data)
    end_effector_position = np.asarray(
        data.site("end_effector").xpos, dtype=np.float64
    ).copy()
    cartesian_speed = float(
        np.linalg.norm(
            end_effector_position - state["previous_end_effector_position"]
        )
        / state["control_interval_seconds"]
    )
    joint_speed = float(np.linalg.norm(qvel))
    joint_limit_margin = float(
        np.min(np.minimum(qpos - ranges[:, 0], ranges[:, 1] - qpos))
    )
    boundary = {
        "joint_speed_norm": joint_speed,
        "cartesian_speed": cartesian_speed,
        "joint_limit_margin": joint_limit_margin,
        "branch_context": analytic_ik_branch_context(
            state["target_position"], model, observed_qpos=qpos
        ),
    }
    state["previous_end_effector_position"] = end_effector_position
    state["max_joint_speed_norm"] = max(state["max_joint_speed_norm"], joint_speed)
    state["max_cartesian_speed"] = max(
        state["max_cartesian_speed"], cartesian_speed
    )
    state["min_joint_limit_margin"] = min(
        state["min_joint_limit_margin"], joint_limit_margin
    )
    if in_tolerance and state["first_entry"] is None:
        state["first_entry"] = boundary
    state["final_boundary"] = boundary


def finalize_episode_diagnostics(state: dict) -> dict:
    """Convert diagnostic state into JSON-compatible episode evidence."""
    first_entry = state["first_entry"]
    final_boundary = state["final_boundary"]

    def value(boundary: dict | None, key: str) -> float | None:
        return None if boundary is None else float(boundary[key])

    def branch(boundary: dict | None) -> dict | None:
        return None if boundary is None else boundary["branch_context"]

    return {
        "max_joint_speed_norm_rad_per_s": float(state["max_joint_speed_norm"]),
        "first_entry_joint_speed_norm_rad_per_s": value(
            first_entry, "joint_speed_norm"
        ),
        "final_joint_speed_norm_rad_per_s": value(
            final_boundary, "joint_speed_norm"
        ),
        "max_cartesian_speed_m_per_s": float(state["max_cartesian_speed"]),
        "first_entry_cartesian_speed_m_per_s": value(
            first_entry, "cartesian_speed"
        ),
        "final_cartesian_speed_m_per_s": value(
            final_boundary, "cartesian_speed"
        ),
        "min_joint_limit_margin_rad": float(state["min_joint_limit_margin"]),
        "first_entry_joint_limit_margin_rad": value(
            first_entry, "joint_limit_margin"
        ),
        "final_joint_limit_margin_rad": value(
            final_boundary, "joint_limit_margin"
        ),
        "ik_branch_context": {
            "target": state["target_branch_context"],
            "first_entry": branch(first_entry),
            "final_boundary": branch(final_boundary),
        },
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
        diagnostic_state = initialize_episode_diagnostics(
            env.model,
            env.data,
            target_position,
            env.model.opt.timestep * env.frame_skip,
        )
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
            update_episode_diagnostics(
                diagnostic_state,
                env.model,
                env.data,
                in_tolerance=held_steps > 0,
            )
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
                **finalize_episode_diagnostics(diagnostic_state),
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
                "control_interval": "s",
                "joint_speed": "rad/s",
                "cartesian_speed": "m/s",
                "joint_limit_margin": "rad",
                "ik_branch_angles": "rad",
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
