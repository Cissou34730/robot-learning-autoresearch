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
from typing import Any, Protocol

import numpy as np

from benchmark.paired_evidence import episode_outcomes
from contracts.policy_runtime import load_runtime
from robot_learning.scenario.environment import (
    ELBOW_BRANCH_LABELS,
    make_evaluation_env,
)

# Bumped when the meaning of a scenario evaluation summary changes.
RESEARCH_EVALUATION_SUMMARY_VERSION = 4


class ActionIntervention(Protocol):
    """Optional research-only action transformation for a scenario evaluation."""

    def reset(self, observation: np.ndarray, info: dict[str, Any]) -> None:
        """Initialize intervention state from one environment reset."""

    def intervene(
        self,
        action: np.ndarray,
        observation: np.ndarray,
        control_step: int,
    ) -> np.ndarray:
        """Return the action to pass to the existing evaluation environment."""


def _finite_vector(
    value, *, name: str, expected_size: int | None = None
) -> np.ndarray:
    try:
        vector = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as error:
        expected = (
            f" with {expected_size} elements" if expected_size is not None else ""
        )
        raise RuntimeError(
            f"Research evaluation received an invalid {name}; expected a "
            f"one-dimensional vector{expected}"
        ) from error
    if vector.ndim != 1 or (
        expected_size is not None and vector.size != expected_size
    ):
        expected = (
            f" with {expected_size} elements" if expected_size is not None else ""
        )
        raise RuntimeError(
            f"Research evaluation received an invalid {name}; expected a "
            f"one-dimensional vector{expected}"
        )
    if not np.all(np.isfinite(vector)):
        raise RuntimeError(
            f"Research evaluation received non-finite values in {name}"
        )
    return vector.copy()


def _finite_scalar(value, *, name: str) -> float:
    scalar = float(value)
    if not np.isfinite(scalar):
        raise RuntimeError(
            f"Research evaluation received a non-finite {name}"
        )
    return scalar


def evaluate_research_model(
    model_path: Path,
    *,
    episodes: int,
    seed: int,
    algorithm: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
    action_intervention: ActionIntervention | None = None,
) -> dict:
    """Measure a deterministic panel with episode seeds starting at ``seed``."""
    if episodes < 1:
        raise ValueError("an evaluation panel requires at least one episode")
    runtime = load_runtime(model_path, algorithm)
    env = make_evaluation_env(policy_runtime=runtime)

    episode_results: list[dict] = []
    episode_diagnostics: list[dict] = []
    for episode in range(episodes):
        obs, reset_info = env.reset(seed=seed + episode)
        runtime.reset()
        if action_intervention is not None:
            action_intervention.reset(obs, reset_info)
        target_position = np.asarray(env.data.mocap_pos[0], dtype=np.float64)
        initial_elbow_branch = str(reset_info["elbow_branch"])
        if initial_elbow_branch not in ELBOW_BRANCH_LABELS:
            raise RuntimeError(
                f"Unknown initial elbow branch label from scenario "
                f"environment: {initial_elbow_branch!r}"
            )
        initial_elbow_qpos_rad = float(reset_info["elbow_qpos_rad"])
        reward_total = 0.0
        steps = 0
        success = False
        terminated = False
        truncated = False
        min_distance_cm = float("inf")
        final_distance_cm = float("nan")
        first_reach_step: int | None = None
        first_reach_endpoint_speed_mps: float | None = None
        max_endpoint_speed_mps: float | None = None
        final_endpoint_speed_mps: float | None = None
        max_held_steps = 0
        in_tolerance_steps = 0
        hold_interruptions = 0
        was_in_tolerance = False
        trajectory: list[dict] = []
        branch_occupancy_counts = dict.fromkeys(ELBOW_BRANCH_LABELS, 0)
        final_elbow_branch: str | None = None
        final_elbow_qpos_rad: float | None = None
        action_saturation_count = 0
        action_saturation_count_per_joint: np.ndarray | None = None
        while not (terminated or truncated):
            action = runtime.predict(obs)
            if action_intervention is not None:
                action = action_intervention.intervene(
                    action, obs, steps + 1
                )
                action = _finite_vector(
                    action, name="intervened action", expected_size=2
                )
            obs, reward, terminated, truncated, info = env.step(action)
            steps += 1
            reward_total += float(reward)
            end_effector_position_m = _finite_vector(
                info["end_effector_position_m"],
                name="end-effector position",
                expected_size=3,
            )
            target_relative_error_m = end_effector_position_m - target_position
            if not np.all(np.isfinite(target_relative_error_m)):
                raise RuntimeError(
                    "Research evaluation received non-finite target-relative "
                    "end-effector error"
                )
            task_distance_m = _finite_scalar(info["distance"], name="distance")
            distance_cm = 100.0 * task_distance_m
            trajectory_distance_m = _finite_scalar(
                np.linalg.norm(target_relative_error_m),
                name="trajectory distance",
            )
            held_steps = int(info.get("held_steps", 0))
            min_distance_cm = min(min_distance_cm, distance_cm)
            final_distance_cm = distance_cm
            endpoint_velocity_mps = _finite_vector(
                info["endpoint_velocity_mps"],
                name="endpoint velocity",
                expected_size=3,
            )
            endpoint_speed_mps = _finite_scalar(
                info["endpoint_speed_mps"], name="endpoint speed"
            )
            if max_endpoint_speed_mps is None:
                max_endpoint_speed_mps = endpoint_speed_mps
            else:
                max_endpoint_speed_mps = max(
                    max_endpoint_speed_mps, endpoint_speed_mps
                )
            final_endpoint_speed_mps = endpoint_speed_mps
            if action_saturation_count_per_joint is None:
                action_saturated = np.asarray(
                    info["action_saturated"], dtype=bool
                )
                if action_saturated.ndim != 1:
                    raise RuntimeError(
                        "Scenario action saturation instrumentation must be "
                        "a one-dimensional per-joint array"
                    )
                action_saturation_count_per_joint = np.zeros(
                    action_saturated.shape, dtype=np.int64
                )
            action_saturated = np.asarray(info["action_saturated"], dtype=bool)
            if action_saturated.shape != action_saturation_count_per_joint.shape:
                raise RuntimeError(
                    "Scenario action saturation instrumentation changed "
                    "joint shape during an episode"
                )
            applied_action = _finite_vector(
                info["applied_action"],
                name="applied action",
                expected_size=action_saturated.size,
            )
            action_saturation_count_per_joint += action_saturated
            action_saturation_count += int(np.count_nonzero(action_saturated))
            elbow_branch = str(info["elbow_branch"])
            if elbow_branch not in branch_occupancy_counts:
                raise RuntimeError(
                    f"Unknown elbow branch label from scenario environment: "
                    f"{elbow_branch!r}"
                )
            branch_occupancy_counts[elbow_branch] += 1
            final_elbow_branch = elbow_branch
            final_elbow_qpos_rad = float(info["elbow_qpos_rad"])
            max_held_steps = max(max_held_steps, held_steps)
            if held_steps > 0:
                in_tolerance_steps += 1
                if first_reach_step is None:
                    first_reach_step = steps
                    first_reach_endpoint_speed_mps = endpoint_speed_mps
            elif was_in_tolerance:
                hold_interruptions += 1
            was_in_tolerance = held_steps > 0
            joint_positions_rad = _finite_vector(
                env.data.qpos, name="joint positions", expected_size=2
            )
            joint_velocities_rad_per_s = _finite_vector(
                env.data.qvel, name="joint velocities", expected_size=2
            )
            trajectory.append(
                {
                    # Control steps are one-based, matching first_reach_step.
                    "control_step": steps,
                    "end_effector_position_m": end_effector_position_m.tolist(),
                    "target_relative_error_m": target_relative_error_m.tolist(),
                    "joint_positions_rad": joint_positions_rad.tolist(),
                    "joint_velocities_rad_per_s": (
                        joint_velocities_rad_per_s.tolist()
                    ),
                    "endpoint_velocity_mps": endpoint_velocity_mps.tolist(),
                    "endpoint_speed_mps": endpoint_speed_mps,
                    "distance_m": trajectory_distance_m,
                    "applied_action": applied_action.tolist(),
                    "action_saturated": action_saturated.tolist(),
                    "elbow_qpos_rad": float(final_elbow_qpos_rad),
                    "elbow_branch": elbow_branch,
                    "held_steps": held_steps,
                    "in_tolerance": bool(
                        trajectory_distance_m <= env.success_threshold
                    ),
                }
            )
            if "is_success" in info:
                success = bool(info["is_success"])

        if (
            max_endpoint_speed_mps is None
            or final_endpoint_speed_mps is None
            or final_elbow_branch is None
            or final_elbow_qpos_rad is None
            or action_saturation_count_per_joint is None
        ):
            raise RuntimeError(
                "Research evaluation completed an episode without the "
                "required scenario diagnostics"
            )
        action_saturation_fraction_per_joint = (
            action_saturation_count_per_joint / steps
        )
        action_saturation_fraction = action_saturation_count / (
            steps * action_saturation_count_per_joint.size
        )
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
                "initial_elbow_qpos_rad": initial_elbow_qpos_rad,
                "initial_elbow_branch": initial_elbow_branch,
                "min_distance_cm": min_distance_cm,
                "final_distance_cm": final_distance_cm,
                "first_reach_step": first_reach_step,
                "first_reach_endpoint_speed_mps": first_reach_endpoint_speed_mps,
                "max_endpoint_speed_mps": max_endpoint_speed_mps,
                "final_endpoint_speed_mps": final_endpoint_speed_mps,
                "max_held_steps": max_held_steps,
                "in_tolerance_steps": in_tolerance_steps,
                "hold_interruptions": hold_interruptions,
                "final_elbow_qpos_rad": final_elbow_qpos_rad,
                "final_elbow_branch": final_elbow_branch,
                "elbow_branch_occupancy_counts": branch_occupancy_counts,
                "action_saturation_count": action_saturation_count,
                "action_saturation_fraction": float(action_saturation_fraction),
                "action_saturation_count_per_joint": (
                    action_saturation_count_per_joint.tolist()
                ),
                "action_saturation_fraction_per_joint": (
                    action_saturation_fraction_per_joint.tolist()
                ),
                "trajectory": trajectory,
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
                "endpoint_speed": "m_per_s",
                "elbow_qpos": "rad",
                "action_saturation_fraction": "proportion",
            },
            "trajectory_schema": {
                "row_semantics": (
                    "One row per visible control step, sampled at the "
                    "post-control-boundary state. control_step is one-based "
                    "and rows continue through termination or truncation."
                ),
                "fields": {
                    "control_step": {
                        "units": "control_steps",
                        "semantics": "One-based visible control-step index.",
                    },
                    "end_effector_position_m": {
                        "units": "m",
                        "semantics": (
                            "World-frame end-effector position after the "
                            "control interval."
                        ),
                    },
                    "target_relative_error_m": {
                        "units": "m",
                        "semantics": (
                            "End-effector position minus the fixed target "
                            "position at the same boundary."
                        ),
                    },
                    "joint_positions_rad": {
                        "units": "rad",
                        "semantics": (
                            "Two joint positions at the post-control "
                            "boundary, ordered shoulder then elbow."
                        ),
                    },
                    "joint_velocities_rad_per_s": {
                        "units": "rad_per_s",
                        "semantics": (
                            "Two joint velocities at the post-control "
                            "boundary, ordered shoulder then elbow."
                        ),
                    },
                    "endpoint_velocity_mps": {
                        "units": "m_per_s",
                        "semantics": (
                            "World-frame end-effector linear velocity at "
                            "the post-control boundary."
                        ),
                    },
                    "endpoint_speed_mps": {
                        "units": "m_per_s",
                        "semantics": (
                            "Euclidean norm of endpoint_velocity_mps."
                        ),
                    },
                    "distance_m": {
                        "units": "m",
                        "semantics": (
                            "Three-dimensional Euclidean distance computed "
                            "from the post-control-boundary position and "
                            "target-relative error in this row."
                        ),
                    },
                    "applied_action": {
                        "units": "dimensionless_action",
                        "semantics": (
                            "Post-adapter action after environment clipping, "
                            "in the order applied to the two actuators."
                        ),
                    },
                    "action_saturated": {
                        "units": "boolean_per_joint",
                        "semantics": (
                            "Whether the corresponding applied action equals "
                            "an inclusive action bound."
                        ),
                    },
                    "elbow_qpos_rad": {
                        "units": "rad",
                        "semantics": "Relative elbow joint configuration.",
                    },
                    "elbow_branch": {
                        "units": "label",
                        "semantics": (
                            "Branch label derived from elbow_qpos_rad: open, "
                            "folded, or singular."
                        ),
                    },
                    "held_steps": {
                        "units": "control_steps",
                        "semantics": (
                            "Existing environment task hold counter reported "
                            "for this control step; zero after a task-level "
                            "interruption."
                        ),
                    },
                    "in_tolerance": {
                        "units": "boolean",
                        "semantics": (
                            "Whether this row's post-control-boundary "
                            "distance is within the success threshold; the "
                            "existing task counter remains in held_steps."
                        ),
                    },
                },
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
