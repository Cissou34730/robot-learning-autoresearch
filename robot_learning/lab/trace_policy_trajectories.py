"""Trace policy trajectories without changing official evaluation semantics.

The artifact produced by this module is a diagnostic replay of the scenario
environment.  The control-boundary distance and hold state use the same
semantics as :class:`TwoJointArmReachEnv`; the 500-Hz values are explanatory
substep diagnostics only.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from contracts.policy_runtime import load_runtime
from robot_learning.scenario.environment import make_evaluation_env

SCHEMA_VERSION = 1


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a nonnegative integer")
    return parsed


def _json_list(values: np.ndarray) -> list[float]:
    return [float(value) for value in np.asarray(values, dtype=np.float64).reshape(-1)]


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _angular_difference_degrees(first: float, second: float) -> float:
    difference = (first - second + 180.0) % 360.0 - 180.0
    return abs(float(difference))


def _require_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"reference field {field!r} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"reference field {field!r} must be finite")
    return result


def _load_reference(
    reference_path: Path, *, episodes: int, seed: int
) -> list[dict[str, Any]]:
    try:
        with reference_path.open("r", encoding="utf-8") as handle:
            reference = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read reference JSON {reference_path}: {exc}") from exc

    if not isinstance(reference, dict):
        raise ValueError("reference artifact must contain a JSON object")
    reference_episodes = reference.get("episodes")
    if isinstance(reference_episodes, bool) or not isinstance(
        reference_episodes, int
    ):
        raise ValueError("reference.episodes must be an integer")
    if reference_episodes != episodes:
        raise ValueError(
            "reference episode count does not match --episodes: "
            f"{reference_episodes!r} != {episodes}"
        )
    reference_seed = reference.get("seed")
    if isinstance(reference_seed, bool) or not isinstance(reference_seed, int):
        raise ValueError("reference.seed must be an integer")
    if reference_seed != seed:
        raise ValueError(
            "reference seed does not match --seed: "
            f"{reference_seed!r} != {seed}"
        )

    evidence = reference.get("research_evidence")
    if not isinstance(evidence, dict):
        raise ValueError("reference.research_evidence must be an object")
    diagnostics = evidence.get("episode_diagnostics")
    if not isinstance(diagnostics, list) or len(diagnostics) != episodes:
        raise ValueError(
            "reference.research_evidence.episode_diagnostics must contain "
            f"exactly {episodes} entries"
        )

    validated: list[dict[str, Any]] = []
    for episode, diagnostic in enumerate(diagnostics):
        if not isinstance(diagnostic, dict):
            raise ValueError(f"reference diagnostic {episode} must be an object")
        diagnostic_episode = diagnostic.get("episode")
        if isinstance(diagnostic_episode, bool) or not isinstance(
            diagnostic_episode, int
        ):
            raise ValueError(
                f"reference diagnostic {episode}.episode must be an integer"
            )
        if diagnostic_episode != episode:
            raise ValueError(
                f"reference diagnostic {episode} has an invalid episode index"
            )
        diagnostic_seed = diagnostic.get("episode_seed")
        if isinstance(diagnostic_seed, bool) or not isinstance(diagnostic_seed, int):
            raise ValueError(
                f"reference diagnostic {episode}.episode_seed must be an integer"
            )
        if diagnostic_seed != seed + episode:
            raise ValueError(
                f"reference diagnostic {episode} has an invalid episode seed"
            )
        _require_number(
            diagnostic.get("target_radius_cm"),
            f"episode_diagnostics[{episode}].target_radius_cm",
        )
        _require_number(
            diagnostic.get("target_angle_degrees"),
            f"episode_diagnostics[{episode}].target_angle_degrees",
        )
        validated.append(diagnostic)
    return validated


def _analytical_ik(target: np.ndarray) -> dict[str, np.ndarray]:
    target_x = float(target[0])
    target_y = float(target[1])
    cosine = (
        target_x**2
        + target_y**2
        - UPPER_ARM_LENGTH**2
        - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    target_angle = float(np.arctan2(target_y, target_x))

    def shoulder_for_elbow(elbow: float) -> float:
        return target_angle - float(
            np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )

    open_solution = np.array(
        [shoulder_for_elbow(elbow_open), elbow_open], dtype=np.float64
    )
    folded_solution = np.array(
        [shoulder_for_elbow(-elbow_open), -elbow_open], dtype=np.float64
    )
    return {"open": open_solution, "folded": folded_solution}


def _branch_diagnostics(
    joint_positions: np.ndarray, solutions: dict[str, np.ndarray]
) -> dict[str, Any]:
    distances = {
        name: float(
            np.linalg.norm(
                [
                    _wrap_to_pi(float(solution[0] - joint_positions[0])),
                    _wrap_to_pi(float(solution[1] - joint_positions[1])),
                ]
            )
        )
        for name, solution in solutions.items()
    }
    ordered = sorted(distances.items(), key=lambda item: item[1])
    nearest_name, nearest_distance = ordered[0]
    branch_margin = float(ordered[1][1] - nearest_distance)
    return {
        "analytical_ik_solutions_radians": {
            name: _json_list(solution) for name, solution in solutions.items()
        },
        "wrapped_joint_space_distance_radians": distances,
        "nearest_branch": nearest_name,
        "nearest_branch_distance_radians": float(nearest_distance),
        "branch_margin_radians": branch_margin,
    }


def _validate_geometry(
    episode: int, target: np.ndarray, reference: dict[str, Any]
) -> dict[str, float]:
    radius_cm = float(np.hypot(target[0], target[1]) * 100.0)
    angle_degrees = float(np.degrees(np.arctan2(target[1], target[0])))
    reference_radius = _require_number(
        reference["target_radius_cm"],
        f"episode_diagnostics[{episode}].target_radius_cm",
    )
    reference_angle = _require_number(
        reference["target_angle_degrees"],
        f"episode_diagnostics[{episode}].target_angle_degrees",
    )
    if not math.isclose(radius_cm, reference_radius, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError(
            f"target radius mismatch for episode {episode}: "
            f"{radius_cm!r} != {reference_radius!r}"
        )
    if _angular_difference_degrees(angle_degrees, reference_angle) > 1e-9:
        raise ValueError(
            f"target angle mismatch for episode {episode}: "
            f"{angle_degrees!r} != {reference_angle!r}"
        )
    return {
        "radius_m": float(radius_cm / 100.0),
        "radius_cm": radius_cm,
        "angle_radians": float(np.radians(angle_degrees)),
        "angle_degrees": angle_degrees,
    }


def _trace_episode(
    env: Any,
    runtime: Any,
    *,
    episode: int,
    episode_seed: int,
    panel_size: int,
    reference_diagnostic: dict[str, Any],
) -> dict[str, Any]:
    obs, _ = env.reset(seed=episode_seed)
    # Keep the reset ordering identical to the research evaluator.
    runtime.reset()

    target = np.asarray(env.data.mocap_pos[0], dtype=np.float64).copy()
    target_geometry = _validate_geometry(episode, target, reference_diagnostic)
    solutions = _analytical_ik(target)

    control_steps: list[dict[str, Any]] = []
    first_reach_step: int | None = None
    max_held_steps = 0
    in_tolerance_steps = 0
    hold_interruptions = 0
    was_in_tolerance = False
    branch_switches = 0
    previous_branch: str | None = None
    terminated = False
    truncated = False

    while not (terminated or truncated):
        pre_positions = np.asarray(env.data.qpos[:2], dtype=np.float64).copy()
        pre_velocities = np.asarray(env.data.qvel[:2], dtype=np.float64).copy()
        policy_prediction = np.asarray(runtime.predict(obs), dtype=np.float64)
        policy_output = policy_prediction.reshape(-1)
        if policy_output.size != env.action_space.shape[0]:
            raise ValueError(
                "policy output has the wrong number of joints: "
                f"{policy_output.size} != {env.action_space.shape[0]}"
            )

        transformed_action = np.asarray(
            env.policy_io.action(policy_prediction), dtype=np.float64
        ).reshape(-1)
        applied_action = np.clip(
            transformed_action,
            np.asarray(env.action_space.low, dtype=np.float64),
            np.asarray(env.action_space.high, dtype=np.float64),
        )
        if applied_action.size != env.action_space.shape[0]:
            raise ValueError(
                "transformed policy action has the wrong number of joints: "
                f"{applied_action.size} != {env.action_space.shape[0]}"
            )

        substep_distances: list[float] = []
        substep_max_velocity_by_joint = np.zeros(2, dtype=np.float64)
        substep_max_displacement_by_joint = np.zeros(2, dtype=np.float64)
        env.data.ctrl[:] = applied_action
        for _ in range(env.frame_skip):
            mujoco.mj_step(env.model, env.data)
            substep_distances.append(float(env._distance_to_target()))
            substep_max_velocity_by_joint = np.maximum(
                substep_max_velocity_by_joint,
                np.abs(np.asarray(env.data.qvel[:2], dtype=np.float64)),
            )
            substep_max_displacement_by_joint = np.maximum(
                substep_max_displacement_by_joint,
                np.abs(
                    np.asarray(env.data.qpos[:2], dtype=np.float64)
                    - pre_positions
                ),
            )

        post_positions = np.asarray(env.data.qpos[:2], dtype=np.float64).copy()
        post_velocities = np.asarray(env.data.qvel[:2], dtype=np.float64).copy()
        boundary_distance = float(substep_distances[-1])

        previous_held_steps = env._held_steps
        if boundary_distance <= env.success_threshold:
            env._held_steps += 1
            env._outside_after_hold = False
        else:
            if previous_held_steps > 0:
                env._outside_after_hold = True
            env._held_steps = 0

        env._previous_distance = boundary_distance
        env._step_count += 1
        terminated = env._held_steps >= env.hold_steps_required
        truncated = env._step_count >= env.max_episode_steps

        held_steps = int(env._held_steps)
        if held_steps > 0:
            in_tolerance_steps += 1
            first_tolerance_entry = first_reach_step is None
            if first_tolerance_entry:
                first_reach_step = env._step_count
        else:
            first_tolerance_entry = False
            if was_in_tolerance:
                hold_interruptions += 1
        was_in_tolerance = held_steps > 0
        max_held_steps = max(max_held_steps, held_steps)

        branches = _branch_diagnostics(post_positions, solutions)
        current_branch = str(branches["nearest_branch"])
        if previous_branch is not None and current_branch != previous_branch:
            branch_switches += 1
        previous_branch = current_branch

        control_steps.append(
            {
                "control_step": int(env._step_count),
                "pre_action_joint_positions_radians": _json_list(pre_positions),
                "pre_action_joint_velocities_radians_per_second": _json_list(
                    pre_velocities
                ),
                "pre_action_joint_velocities_absolute_radians_per_second": _json_list(
                    np.abs(pre_velocities)
                ),
                "policy_output_action": _json_list(policy_output),
                "policy_output_action_absolute": _json_list(np.abs(policy_output)),
                "policy_output_action_max_absolute": float(np.max(np.abs(policy_output))),
                "policy_output_action_l2": float(np.linalg.norm(policy_output)),
                "transformed_action": _json_list(transformed_action),
                "applied_clipped_action": _json_list(applied_action),
                "applied_clipped_action_absolute": _json_list(np.abs(applied_action)),
                "applied_clipped_action_max_absolute": float(
                    np.max(np.abs(applied_action))
                ),
                "applied_clipped_action_l2": float(np.linalg.norm(applied_action)),
                "post_action_joint_positions_radians": _json_list(post_positions),
                "post_action_joint_velocities_radians_per_second": _json_list(
                    post_velocities
                ),
                "post_action_joint_velocities_absolute_radians_per_second": _json_list(
                    np.abs(post_velocities)
                ),
                "endpoint_distance_at_control_boundary_m": boundary_distance,
                "held_steps": held_steps,
                "first_tolerance_entry": first_tolerance_entry,
                "substep_count": int(env.frame_skip),
                "substep_frequency_hz": float(1.0 / env.model.opt.timestep),
                "substep_endpoint_distance_min_m": float(min(substep_distances)),
                "substep_endpoint_distance_max_m": float(max(substep_distances)),
                "substep_max_absolute_joint_velocity_radians_per_second": float(
                    np.max(substep_max_velocity_by_joint)
                ),
                "substep_max_absolute_joint_velocity_by_joint_radians_per_second": _json_list(
                    substep_max_velocity_by_joint
                ),
                "substep_max_absolute_joint_displacement_from_pre_action_radians": float(
                    np.max(substep_max_displacement_by_joint)
                ),
                "substep_max_absolute_joint_displacement_by_joint_radians": _json_list(
                    substep_max_displacement_by_joint
                ),
                "substep_outside_success_threshold_count": int(
                    sum(distance > env.success_threshold for distance in substep_distances)
                ),
                **branches,
            }
        )
        obs = env._observation()

    if first_reach_step is None:
        failure_phase = "no_reach"
        post_reach_steps = 0
    else:
        failure_phase = "success" if terminated else "reached_but_not_held"
        post_reach_steps = int(env._step_count - first_reach_step + 1)

    return {
        "episode": episode,
        "episode_seed": episode_seed,
        "target": {
            **target_geometry,
            "z_m": float(target[2]),
        },
        "panel_size": panel_size,
        "reference_target": {
            "radius_cm": float(reference_diagnostic["target_radius_cm"]),
            "angle_degrees": float(reference_diagnostic["target_angle_degrees"]),
            "panel_size": panel_size,
        },
        "success": bool(terminated),
        "terminated": bool(terminated),
        "truncated": bool(truncated),
        "steps": int(env._step_count),
        "first_reach_step": first_reach_step,
        "first_reach_control_step": first_reach_step,
        "max_held_steps": max_held_steps,
        "in_tolerance_steps": in_tolerance_steps,
        "hold_interruptions": hold_interruptions,
        "failure_phase": failure_phase,
        "branch_switches": branch_switches,
        "post_reach_steps": post_reach_steps,
        "control_steps": control_steps,
    }


def trace_policy_trajectories(
    model_path: Path,
    reference_path: Path,
    *,
    episodes: int,
    seed: int,
    output_path: Path,
) -> dict[str, Any]:
    """Replay a saved runtime and write a complete diagnostic trajectory."""
    if episodes < 1:
        raise ValueError("--episodes must be a positive integer")
    if seed < 0:
        raise ValueError("--seed must be a nonnegative integer")

    reference_diagnostics = _load_reference(
        reference_path, episodes=episodes, seed=seed
    )
    runtime = load_runtime(model_path)
    env = make_evaluation_env(policy_runtime=runtime)

    episode_traces = [
        _trace_episode(
            env,
            runtime,
            episode=episode,
            episode_seed=seed + episode,
            panel_size=episodes,
            reference_diagnostic=reference_diagnostics[episode],
        )
        for episode in range(episodes)
    ]

    successes = sum(bool(episode["success"]) for episode in episode_traces)
    no_reach_failures = sum(
        episode["failure_phase"] == "no_reach" for episode in episode_traces
    )
    reached_but_not_held_failures = sum(
        episode["failure_phase"] == "reached_but_not_held"
        for episode in episode_traces
    )
    artifact: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "model": str(model_path),
        "seed": seed,
        "episodes": episodes,
        "official_benchmark": False,
        "metadata": {
            "frame_skip": int(env.frame_skip),
            "simulator_timestep_s": float(env.model.opt.timestep),
            "control_period_s": float(env.model.opt.timestep * env.frame_skip),
            "control_frequency_hz": float(
                1.0 / (env.model.opt.timestep * env.frame_skip)
            ),
            "substep_frequency_hz": float(1.0 / env.model.opt.timestep),
            "success_threshold_m": float(env.success_threshold),
            "hold_steps_required": int(env.hold_steps_required),
            "diagnostic_notice": (
                "This is a policy trajectory diagnostic, not official assessment "
                "or causal proof. Boundary distance and hold state are authoritative; "
                "substep extrema are diagnostic only."
            ),
        },
        "units": {
            "distance": "metres",
            "target_radius_reference": "centimetres",
            "angle": "radians",
            "target_angle_reference": "degrees",
            "joint_position": "radians",
            "joint_velocity": "radians_per_second",
            "action": "policy/runtime control units",
            "time": "seconds",
        },
        "summary": {
            "successes": successes,
            "no_reach_failures": no_reach_failures,
            "reached_but_not_held_failures": reached_but_not_held_failures,
            "total_hold_interruptions": sum(
                int(episode["hold_interruptions"]) for episode in episode_traces
            ),
            "branch_switches": sum(
                int(episode["branch_switches"]) for episode in episode_traces
            ),
            "post_reach_steps": sum(
                int(episode["post_reach_steps"]) for episode in episode_traces
            ),
        },
        "episodes_trace": episode_traces,
    }

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(artifact, handle, indent=2, allow_nan=False)
            handle.write("\n")
    except (OSError, TypeError, ValueError) as exc:
        raise RuntimeError(f"cannot write trajectory artifact {output_path}: {exc}") from exc
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay a policy and write a detailed trajectory diagnostic."
    )
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--episodes", type=_positive_int, required=True)
    parser.add_argument("--seed", type=_nonnegative_int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    trace_policy_trajectories(
        args.model,
        args.reference,
        episodes=args.episodes,
        seed=args.seed,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
