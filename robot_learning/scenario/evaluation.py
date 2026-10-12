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
_RESEARCH_EVALUATION_SCHEMA_VERSION = 7
_OBSERVATION_SIZE = 11
_OPEN_BRANCH_ERROR_SLICE = slice(7, 9)
_FOLDED_BRANCH_ERROR_SLICE = slice(9, 11)


def _extract_branch_error_norms(
    observation: np.ndarray, *, context: str = "observation"
) -> tuple[float, float]:
    """Read the frozen open/folded IK errors from one policy observation.

    The observation contract is deliberately checked here rather than padded or
    truncated.  Evaluation artifacts must not claim branch diagnostics when a
    runtime supplies a different representation.
    """
    try:
        observation_array = np.asarray(observation, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{context} is not a numeric {_OBSERVATION_SIZE}-element observation"
        ) from exc
    if observation_array.shape != (_OBSERVATION_SIZE,):
        raise ValueError(
            f"{context} must have shape ({_OBSERVATION_SIZE},), "
            f"got {observation_array.shape}"
        )
    branch_errors = observation_array[7:11]
    if not np.all(np.isfinite(branch_errors)):
        raise ValueError(f"{context} has non-finite branch-error entries")
    open_norm = float(np.linalg.norm(observation_array[_OPEN_BRANCH_ERROR_SLICE]))
    folded_norm = float(
        np.linalg.norm(observation_array[_FOLDED_BRANCH_ERROR_SLICE])
    )
    return open_norm, folded_norm


def _summarize_branch_diagnostics(
    post_step_observations: list[np.ndarray], held_steps: list[int]
) -> dict:
    """Summarize branch attribution for the post-step states of one episode.

    Each post-step state is assigned to the branch with the smaller Euclidean
    norm of its two IK-error entries.  Equal norms are assigned to ``open``.
    Occupancy and switches use consecutive post-step states only; the reset
    observation is not a control state.  First reach is the first state whose
    environment-reported ``held_steps`` is positive.  Maximum-held attribution
    uses the first state that strictly exceeds the previous maximum, so ties
    are deterministic.
    """
    if len(post_step_observations) != len(held_steps):
        raise ValueError(
            "branch diagnostics require one held-step value per post-step "
            "observation"
        )
    if not post_step_observations:
        raise ValueError("branch diagnostics require at least one post-step state")

    branch_labels: list[str] = []
    open_norms: list[float] = []
    folded_norms: list[float] = []
    for step_index, observation in enumerate(post_step_observations, start=1):
        open_norm, folded_norm = _extract_branch_error_norms(
            observation, context=f"post-step observation {step_index}"
        )
        open_norms.append(open_norm)
        folded_norms.append(folded_norm)
        branch_labels.append("open" if open_norm <= folded_norm else "folded")

    open_occupancy_steps = branch_labels.count("open")
    folded_occupancy_steps = branch_labels.count("folded")
    branch_switches = sum(
        previous != current
        for previous, current in zip(branch_labels, branch_labels[1:])
    )

    branch_at_first_reach: str | None = None
    max_held_steps = 0
    branch_at_max_held_run: str | None = None
    for branch, held in zip(branch_labels, held_steps):
        held_value = int(held)
        if held_value > 0 and branch_at_first_reach is None:
            branch_at_first_reach = branch
        if held_value > max_held_steps:
            max_held_steps = held_value
            branch_at_max_held_run = branch

    total_steps = len(branch_labels)
    return {
        "open_branch_occupancy_steps": open_occupancy_steps,
        "folded_branch_occupancy_steps": folded_occupancy_steps,
        "open_branch_occupancy_fraction": open_occupancy_steps / total_steps,
        "folded_branch_occupancy_fraction": folded_occupancy_steps / total_steps,
        "branch_switches": branch_switches,
        "branch_at_first_reach": branch_at_first_reach,
        "branch_at_max_held_run": branch_at_max_held_run,
        "min_open_branch_error_norm": min(open_norms),
        "min_folded_branch_error_norm": min(folded_norms),
    }


def _coerce_policy_output(action: object) -> np.ndarray:
    """Require the runtime to return exactly one two-joint action."""
    try:
        action_array = np.asarray(action, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "runtime policy output must be a numeric two-element vector"
        ) from exc
    if action_array.shape != (2,):
        raise ValueError(
            f"runtime policy output must have shape (2,), got {action_array.shape}"
        )
    if not np.all(np.isfinite(action_array)):
        raise ValueError("runtime policy output contains non-finite values")
    return action_array.copy()


def _branch_trace_fields(observation: np.ndarray) -> dict[str, object]:
    open_norm, folded_norm = _extract_branch_error_norms(
        observation, context="post-step observation"
    )
    observation_array = np.asarray(observation, dtype=np.float64)
    return {
        "branch_label": "open" if open_norm <= folded_norm else "folded",
        "open_branch_error": observation_array[7:9].tolist(),
        "folded_branch_error": observation_array[9:11].tolist(),
        "open_branch_error_norm": float(open_norm),
        "folded_branch_error_norm": float(folded_norm),
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
    episode_traces: list[dict] = []
    for episode in range(episodes):
        obs, _ = env.reset(seed=seed + episode)
        _extract_branch_error_norms(obs, context="reset observation")
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
        post_step_observations: list[np.ndarray] = []
        held_steps_history: list[int] = []
        control_trace: list[dict] = []
        while not (terminated or truncated):
            policy_output = _coerce_policy_output(runtime.predict(obs))
            obs, reward, terminated, truncated, info = env.step(policy_output)
            steps += 1
            reward_total += float(reward)
            distance_cm = 100.0 * float(info["distance"])
            held_steps = int(info.get("held_steps", 0))
            post_step_observations.append(obs)
            held_steps_history.append(held_steps)
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
            control_trace.append(
                {
                    "control_step": steps,
                    "policy_output": policy_output.tolist(),
                    "commanded_action": list(info["post_policy_action"]),
                    "clipped_action": list(info["clipped_action"]),
                    "joint_saturation": list(info["joint_saturation"]),
                    "action_saturated": bool(info["action_saturated"]),
                    "qpos": list(info["qpos"]),
                    "qvel": list(info["qvel"]),
                    "ctrl": list(info["ctrl"]),
                    "endpoint_distance_m": float(info["endpoint_distance"]),
                    "held_steps": held_steps,
                    "first_reach": bool(info["first_reach"]),
                    "hold_interrupted": bool(info["hold_interrupted"]),
                    **_branch_trace_fields(obs),
                    "contact_count": int(info["contact_count"]),
                    "contact_geom_pairs": [
                        list(pair) for pair in info["contact_geom_pairs"]
                    ],
                    "joint_limit_distance": list(info["joint_limit_distance"]),
                    "joint_limit_proximity": list(info["joint_limit_proximity"]),
                    "joint_limit_active": list(info["joint_limit_active"]),
                    "substep_trace": [
                        {
                            "qpos": list(substep["qpos"]),
                            "qvel": list(substep["qvel"]),
                            "ctrl": list(substep["ctrl"]),
                            "endpoint_distance_m": float(
                                substep["endpoint_distance"]
                            ),
                            "contact_count": int(substep["contact_count"]),
                            "contact_geom_pairs": [
                                list(pair) for pair in substep["contact_geom_pairs"]
                            ],
                            "joint_limit_distance": list(
                                substep["joint_limit_distance"]
                            ),
                            "joint_limit_proximity": list(
                                substep["joint_limit_proximity"]
                            ),
                            "joint_limit_active": list(
                                substep["joint_limit_active"]
                            ),
                        }
                        for substep in info["substep_trace"]
                    ],
                }
            )

        branch_diagnostics = _summarize_branch_diagnostics(
            post_step_observations, held_steps_history
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
                "min_distance_cm": min_distance_cm,
                "final_distance_cm": final_distance_cm,
                "first_reach_step": first_reach_step,
                "max_held_steps": max_held_steps,
                "in_tolerance_steps": in_tolerance_steps,
                "hold_interruptions": hold_interruptions,
                **branch_diagnostics,
            }
        )
        episode_traces.append(
            {
                "episode": episode,
                "episode_seed": seed + episode,
                "control_steps": control_trace,
            }
        )
        if progress_callback is not None:
            progress_callback(episode + 1, episodes)

    successes = sum(episode["success"] for episode in episode_results)
    return {
        "schema_version": _RESEARCH_EVALUATION_SCHEMA_VERSION,
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
            "episode_traces": episode_traces,
            "units": {
                "distance": "cm",
                "time": "control_steps",
                "branch_error_norm": "radians",
                "trace_endpoint_distance": "m",
                "qpos": "radians",
                "qvel": "radians_per_second",
                "ctrl": "actuator command units sent to MuJoCo",
                "joint_limit_distance": "radians",
                "action": "post-policy actuator command units before/after [-1, 1] clipping",
            },
            "trace_definitions": {
                "policy_output": (
                    "The finite two-element vector returned by the loaded runtime "
                    "before the environment policy-I/O mapping."
                ),
                "commanded_action": (
                    "The finite two-element physical command after policy-I/O "
                    "mapping and before environment clipping."
                ),
                "joint_saturation": (
                    "Per-joint true when commanded_action is outside the inclusive "
                    "environment action bounds; clipped_action is the value sent "
                    "to MuJoCo."
                ),
                "joint_limit_distance": (
                    "Minimum angular distance from each limited joint position to "
                    "its configured lower or upper range edge."
                ),
                "joint_limit_proximity": (
                    "Per-joint indicator true within one degree of a configured "
                    "range edge; it is diagnostic only and does not affect control."
                ),
                "joint_limit_active": (
                    "Per-joint indicator true when the joint position is at or "
                    "outside a configured range edge."
                ),
                "contact_geom_pairs": (
                    "MuJoCo contact geom integer pairs at the corresponding "
                    "control boundary or simulator substep."
                ),
                "substep_trace": (
                    "Ordered post-mj_step snapshots for every simulator step in "
                    "the control interval; no extra dynamics step is performed."
                ),
                "first_reach": (
                    "True only on the first post-control state in the episode "
                    "with held_steps greater than zero."
                ),
                "hold_interrupted": (
                    "True when a prior positive held_steps value is followed by "
                    "a post-control state outside the success tolerance."
                ),
            },
            "branch_diagnostic_definitions": {
                "observation_contract": (
                    "Frozen policy observation shape (11,): branch errors are "
                    "entries 7:9 for open and 9:11 for folded."
                ),
                "branch_classification": (
                    "Each post-step observation is assigned to the branch with "
                    "the smaller Euclidean two-entry error norm; equal norms "
                    "are assigned to open."
                ),
                "occupancy": (
                    "Occupancy counts classified post-step control states; "
                    "fractions divide those counts by episode control steps."
                ),
                "branch_switches": (
                    "Count changes between consecutive classified post-step "
                    "states; the reset observation is excluded."
                ),
                "branch_at_first_reach": (
                    "The branch at the first post-step state with held_steps "
                    "greater than zero, or null when never reached."
                ),
                "branch_at_max_held_run": (
                    "The branch at the first post-step state setting a new "
                    "maximum held_steps; ties keep the earlier attribution."
                ),
                "minimum_error_norms": (
                    "Minimum open and folded two-entry Euclidean error norms "
                    "over all post-step observations."
                ),
                "error_norm_units": "radians",
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
