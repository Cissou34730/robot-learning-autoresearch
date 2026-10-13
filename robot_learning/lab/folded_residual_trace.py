"""Production-path, ten-substep traces for the folded-branch residual inquiry."""

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.policy_runtime import load_runtime
from robot_learning.scenario.environment import make_evaluation_env
from robot_learning.scenario.evaluation import classify_target_ik_branches
from robot_learning.training.reward import reach_reward


SCHEMA_VERSION = 1


def _finite_array(value, *, name: str) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} contains a non-finite value")
    return array


def _finite_list(value, *, name: str) -> list[float]:
    return _finite_array(value, name=name).tolist()


def _finite_float(value, *, name: str) -> float:
    result = float(value)
    if not np.isfinite(result):
        raise ValueError(f"{name} is non-finite")
    return result


def _target_geometry(target: np.ndarray, classification: dict) -> dict:
    target = _finite_array(target, name="target")
    return {
        "target_position_m": _finite_list(target, name="target"),
        "target_radius_m": _finite_float(np.hypot(target[0], target[1]), name="target radius"),
        "target_angle_degrees": _finite_float(
            np.degrees(np.arctan2(target[1], target[0])),
            name="target angle",
        ),
        "ik_open_legal": bool(classification["open_legal"]),
        "ik_folded_legal": bool(classification["folded_legal"]),
        "ik_branch_classification": str(classification["union"]),
    }


def _actuator_forces(data) -> tuple[bool, list[float] | None]:
    forces = getattr(data, "qfrc_actuator", None)
    if forces is None:
        return False, None
    values = _finite_array(forces, name="qfrc_actuator")
    return True, values.tolist()


def _diagnostic_step(
    env,
    commanded_action,
    *,
    control_step: int,
    first_reach_step: int | None,
) -> tuple[dict, np.ndarray, float, bool, bool, int | None]:
    """Mirror ``TwoJointArmReachEnv.step`` while retaining every mj_step."""
    commanded = _finite_array(commanded_action, name="commanded action")
    transformed = _finite_array(
        env.policy_io.action(commanded_action), name="transformed action"
    )
    applied = np.clip(
        transformed,
        np.asarray(env.action_space.low, dtype=np.float64),
        np.asarray(env.action_space.high, dtype=np.float64),
    )
    applied = _finite_array(applied, name="applied action")
    lower = np.asarray(env.action_space.low, dtype=np.float64)
    upper = np.asarray(env.action_space.high, dtype=np.float64)
    saturated = np.isclose(applied, lower, atol=1e-12) | np.isclose(
        applied, upper, atol=1e-12
    )
    env.data.ctrl[:] = applied

    target = np.asarray(env.data.mocap_pos[0], dtype=np.float64).copy()
    pre_action_qpos = _finite_list(env.data.qpos, name="pre-action qpos")
    pre_action_qvel = _finite_list(env.data.qvel, name="pre-action qvel")
    pre_action_distance = _finite_float(
        env._previous_distance, name="pre-action distance"
    )
    substeps: list[dict] = []
    for internal_substep in range(env.frame_skip):
        mujoco.mj_step(env.model, env.data)
        end_effector = _finite_array(
            env._end_effector_position(), name="end-effector position"
        )
        error = _finite_array(end_effector - target, name="Cartesian error")
        distance = _finite_float(np.linalg.norm(error), name="substep distance")
        actuator_available, actuator_force = _actuator_forces(env.data)
        substeps.append(
            {
                "internal_substep": internal_substep,
                "qpos": _finite_list(env.data.qpos, name="qpos"),
                "qvel": _finite_list(env.data.qvel, name="qvel"),
                "qacc": _finite_list(env.data.qacc, name="qacc"),
                "cartesian_end_effector_minus_target_m": error.tolist(),
                "distance_m": distance,
                "actuator_force_torque_available": actuator_available,
                "qfrc_actuator": actuator_force,
            }
        )

    endpoint_distance = _finite_float(
        env._distance_to_target(), name="endpoint distance"
    )
    endpoint_in_tolerance = endpoint_distance <= env.success_threshold
    previous_held_steps = int(env._held_steps)
    endpoint_interrupted = previous_held_steps > 0 and not endpoint_in_tolerance
    if endpoint_in_tolerance:
        env._held_steps += 1
        env._outside_after_hold = False
    else:
        if previous_held_steps > 0:
            env._outside_after_hold = True
        env._held_steps = 0

    reward = reach_reward(
        pre_action_distance,
        endpoint_distance,
        env.success_threshold,
        applied,
        held_steps=env._held_steps,
        previous_held_steps=previous_held_steps,
        hold_steps_required=env.hold_steps_required,
        penalize_outside=env._outside_after_hold,
        joint_velocities=env.data.qvel[:2].copy(),
    )
    reward_total = _finite_float(reward.total, name="reward")
    env._previous_distance = endpoint_distance
    env._step_count += 1
    terminated = env._held_steps >= env.hold_steps_required
    truncated = env._step_count >= env.max_episode_steps
    if endpoint_in_tolerance and first_reach_step is None:
        first_reach_step = control_step + 1

    any_substep_outside = any(
        item["distance_m"] > env.success_threshold for item in substeps
    )
    frame = {
        "control_step": control_step,
        "pre_action_state": {
            "qpos": pre_action_qpos,
            "qvel": pre_action_qvel,
            "distance_m": pre_action_distance,
        },
        "commanded_policy_action": commanded.tolist(),
        "transformed_action": transformed.tolist(),
        "applied_clipped_action": applied.tolist(),
        "saturated_elements": saturated.astype(bool).tolist(),
        "saturation_flag": bool(np.any(saturated)),
        "substeps": substeps,
        "any_substep_outside_tolerance": any_substep_outside,
        "hidden_excursion_returned_inside": bool(
            any_substep_outside and endpoint_in_tolerance
        ),
        "endpoint_distance_m": endpoint_distance,
        "endpoint_official_distance_m": endpoint_distance,
        "endpoint_in_tolerance": endpoint_in_tolerance,
        "endpoint_outside_tolerance": bool(not endpoint_in_tolerance),
        "held_steps": int(env._held_steps),
        "endpoint_hold_interrupted": endpoint_interrupted,
        "first_reach_step": first_reach_step,
        "reward": reward_total,
        "terminated": bool(terminated),
        "truncated": bool(truncated),
    }
    return (
        frame,
        env._observation(),
        reward_total,
        bool(terminated),
        bool(truncated),
        first_reach_step,
    )


def _run_episode(runtime, env, *, episode: int, seed: int) -> tuple[dict, dict]:
    observation, _ = env.reset(seed=seed)
    runtime.reset()
    target = np.asarray(env.data.mocap_pos[0], dtype=np.float64).copy()
    classification = classify_target_ik_branches(env.model, target)
    geometry = _target_geometry(target, classification)
    frames: list[dict] = []
    reward_total = 0.0
    terminated = False
    truncated = False
    first_reach_step: int | None = None
    min_distance = float("inf")
    hidden_excursions = 0
    hold_interruptions = 0
    while not (terminated or truncated):
        commanded = runtime.predict(observation)
        (
            frame,
            observation,
            reward,
            terminated,
            truncated,
            first_reach_step,
        ) = _diagnostic_step(
            env,
            commanded,
            control_step=len(frames),
            first_reach_step=first_reach_step,
        )
        frames.append(frame)
        reward_total += reward
        min_distance = min(min_distance, frame["endpoint_distance_m"])
        hidden_excursions += int(frame["hidden_excursion_returned_inside"])
        hold_interruptions += int(frame["endpoint_hold_interrupted"])

    success = bool(terminated and frames[-1]["held_steps"] >= env.hold_steps_required)
    endpoint = frames[-1]
    result = {
        "episode": episode,
        "episode_seed": seed,
        "success": success,
        "reward_total": _finite_float(reward_total, name="episode reward"),
        "steps": len(frames),
        "terminated": bool(terminated),
        "truncated": bool(truncated),
    }
    diagnostic = {
        "episode": episode,
        "episode_seed": seed,
        **geometry,
        "min_endpoint_distance_m": _finite_float(
            min_distance, name="minimum endpoint distance"
        ),
        "final_endpoint_distance_m": endpoint["endpoint_official_distance_m"],
        "first_reach_step": first_reach_step,
        "max_held_steps": max(frame["held_steps"] for frame in frames),
        "in_tolerance_control_steps": sum(
            int(frame["endpoint_in_tolerance"]) for frame in frames
        ),
        "hold_interruptions": hold_interruptions,
        "hidden_excursion_returned_inside_control_steps": hidden_excursions,
    }
    trajectory = {
        "episode": episode,
        "episode_seed": seed,
        **geometry,
        "selection_reason": None,
        "control_frames": frames,
    }
    return {"result": result, "diagnostic": diagnostic}, trajectory


def collect_panel(
    model_path: Path,
    *,
    episodes: int = 160,
    seed: int = 4200,
    controls: int | None = None,
    algorithm: str | None = None,
) -> dict:
    """Collect the full outcome panel, retaining detailed frames after selection."""
    if episodes < 1:
        raise ValueError("episodes must be positive")
    if controls is not None and controls < 0:
        raise ValueError("controls must be non-negative")

    runtime = load_runtime(Path(model_path), algorithm)
    env = make_evaluation_env(policy_runtime=runtime)
    production_timing = {
        "frame_skip": int(env.frame_skip),
        "model_timestep_seconds": _finite_float(
            env.model.opt.timestep, name="model timestep"
        ),
        "control_interval_seconds": _finite_float(
            env.model.opt.timestep * env.frame_skip,
            name="control interval",
        ),
        "control_substeps_per_frame": int(env.frame_skip),
    }
    records: list[dict] = []
    trajectories: dict[int, dict] = {}
    try:
        for episode in range(episodes):
            record, trajectory = _run_episode(
                runtime, env, episode=episode, seed=seed + episode
            )
            records.append(record)
            trajectories[episode] = trajectory
    finally:
        close = getattr(env, "close", None)
        if close is not None:
            close()

    failed_folded = [
        item["result"]
        for item in records
        if not item["result"]["success"]
        and item["diagnostic"]["ik_branch_classification"] == "folded_only"
    ]
    successful_folded = [
        item["result"]
        for item in records
        if item["result"]["success"]
        and item["diagnostic"]["ik_branch_classification"] == "folded_only"
    ]
    requested_controls = len(failed_folded) if controls is None else controls
    selected_failed = failed_folded
    selected_controls = successful_folded[:requested_controls]
    selected_ids = {item["episode"] for item in selected_failed}
    selected_ids.update(item["episode"] for item in selected_controls)
    for item in selected_failed:
        trajectories[item["episode"]]["selection_reason"] = (
            "failed_folded_only"
        )
    for item in selected_controls:
        trajectories[item["episode"]]["selection_reason"] = (
            "successful_folded_only_control"
        )

    episode_results = [item["result"] for item in records]
    episode_diagnostics = [item["diagnostic"] for item in records]
    detailed_traces = [
        trajectories[episode]
        for episode in sorted(selected_ids)
    ]
    successes = sum(int(item["success"]) for item in episode_results)
    return {
        "schema": "folded_residual_trace",
        "schema_version": SCHEMA_VERSION,
        "model": str(model_path),
        "episodes": episodes,
        "seed": seed,
        "official_benchmark": False,
        "success_percent": 100.0 * successes / episodes,
        "production_timing": production_timing,
        "selection": {
            "rationale": (
                "all failed folded_only episodes plus the deterministic earliest "
                "successful folded_only controls"
            ),
            "failed_folded_only_count": len(failed_folded),
            "successful_folded_only_available": len(successful_folded),
            "successful_controls_requested": requested_controls,
            "selected_episode_count": len(detailed_traces),
        },
        "episode_results": episode_results,
        "episode_diagnostics": episode_diagnostics,
        "detailed_traces": detailed_traces,
        "units": {
            "position": "m",
            "distance": "m",
            "time": "seconds for timing, control_steps for episode indices",
            "joint_position": "rad",
            "joint_velocity": "rad_per_second",
            "joint_acceleration": "rad_per_second_squared",
            "qfrc_actuator": "generalized_force_or_torque",
            "action": "policy-normalized units after policy transform",
        },
        "unchecked_scope": [
            "No causal attribution from traces to policy quality is established.",
            "The diagnostic does not alter or certify the official benchmark.",
            "Only selected episodes contain internal-substep trajectories.",
        ],
    }


def write_panel(
    model_path: Path,
    *,
    episodes: int,
    seed: int,
    output: Path,
    controls: int | None = None,
    algorithm: str | None = None,
) -> None:
    panel = collect_panel(
        model_path,
        episodes=episodes,
        seed=seed,
        controls=controls,
        algorithm=algorithm,
    )
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(panel, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--episodes", type=int, default=160)
    parser.add_argument("--seed", type=int, default=4200)
    parser.add_argument("--controls", type=int, default=None)
    parser.add_argument("--algorithm", default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_panel(
        args.model,
        episodes=args.episodes,
        seed=args.seed,
        controls=args.controls,
        algorithm=args.algorithm,
        output=args.output,
    )


if __name__ == "__main__":
    main()
