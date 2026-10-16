"""Detailed, semantics-preserving traces for a frozen research evaluation.

The trace is deliberately a measurement of the saved runtime and the shared
scenario mechanics.  It does not replace the research evaluator or interpret
the resulting behavior.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from contracts.policy_runtime import load_runtime
from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from contracts.task_spec import (
    FRAME_SKIP,
    HOLD_SECONDS,
    MAX_EPISODE_STEPS,
    SUCCESS_THRESHOLD,
)
from robot_learning.scenario.environment import make_evaluation_env
from robot_learning.training.reward import reach_reward


SCHEMA_VERSION = 1
UINT32_MAX = 2**32 - 1
_IK_TIE_ATOL = 1e-12


def _class_name(value: Any) -> str:
    value_type = value if isinstance(value, type) else type(value)
    return f"{value_type.__module__}.{value_type.__qualname__}"


def _callable_name(value: Any) -> dict[str, str]:
    return {
        "module": str(getattr(value, "__module__", _class_name(value).rsplit(".", 1)[0])),
        "qualname": str(
            getattr(value, "__qualname__", _class_name(value).rsplit(".", 1)[-1])
        ),
    }


def _finite_float(value: Any) -> float | None:
    result = float(value)
    return result if np.isfinite(result) else None


def _state_summary(value: Any) -> dict[str, Any] | None:
    """Summarize recurrent state without retaining tensor or weight contents."""
    if value is None:
        return None

    if isinstance(value, dict):
        return {
            "type": _class_name(value),
            "shape": None,
            "dtype": None,
            "norm": None,
            "items": {
                str(key): _state_summary(value[key])
                for key in sorted(value, key=lambda item: str(item))
            },
        }

    if isinstance(value, (tuple, list)):
        numeric_values: list[float] = []
        for item in value:
            item_array = np.asarray(item)
            if np.issubdtype(item_array.dtype, np.number):
                numeric_values.extend(
                    float(number) for number in item_array.reshape(-1)
                )
        norm = None
        if numeric_values:
            norm = _finite_float(np.linalg.norm(np.asarray(numeric_values)))
        return {
            "type": _class_name(value),
            "shape": None,
            "dtype": None,
            "norm": norm,
            "items": [_state_summary(item) for item in value],
        }

    shape = getattr(value, "shape", None)
    dtype = getattr(value, "dtype", None)
    try:
        array = np.asarray(value)
        if shape is None:
            shape = array.shape
        if dtype is None:
            dtype = array.dtype
        norm = (
            _finite_float(np.linalg.norm(array))
            if np.issubdtype(array.dtype, np.number)
            else None
        )
    except (TypeError, ValueError):
        array = None
        norm = None

    return {
        "type": _class_name(value),
        "shape": None if shape is None else [int(item) for item in shape],
        "dtype": None if dtype is None else str(dtype),
        "norm": norm,
    }


def _json_value(value: Any) -> Any:
    """Convert scientific scalar/container values to strict JSON values."""
    if isinstance(value, np.ndarray):
        return [_json_value(item) for item in value.tolist()]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        finite = _finite_float(value)
        if finite is None:
            raise ValueError("non-finite value cannot be written to the trace")
        return finite
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, float):
        if not np.isfinite(value):
            raise ValueError("non-finite value cannot be written to the trace")
        return value
    if isinstance(value, Path):
        return str(value)
    return value


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _validate_inputs(episodes: int, seed: int) -> None:
    if isinstance(episodes, bool) or not isinstance(episodes, (int, np.integer)):
        raise ValueError("episodes must be a positive integer")
    if episodes < 1:
        raise ValueError("episodes must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
        raise ValueError(f"seed must be an integer in the uint32 range [0, {UINT32_MAX}]")
    if seed < 0 or seed > UINT32_MAX:
        raise ValueError(f"seed must be in the uint32 range [0, {UINT32_MAX}]")
    if seed + episodes - 1 > UINT32_MAX:
        raise ValueError("episode seeds must remain in the uint32 range")


def _space_metadata(space: Any) -> dict[str, Any]:
    shape = getattr(space, "shape", None)
    if shape is None:
        raise ValueError("policy space has no shape")
    return {
        "shape": [int(item) for item in shape],
        "dtype": str(getattr(space, "dtype", None)),
    }


def _validate_environment(runtime: Any, env: Any) -> dict[str, Any]:
    observation_shape = tuple(getattr(runtime.observation_space, "shape", ()) or ())
    action_shape = tuple(getattr(runtime.action_space, "shape", ()) or ())
    if observation_shape != (11,):
        raise ValueError(
            f"invalid policy observation dimensions: expected (11,), got {observation_shape}"
        )
    if action_shape != (2,):
        raise ValueError(
            f"invalid policy action dimensions: expected (2,), got {action_shape}"
        )

    model = env.model
    if (model.nq, model.nv, model.nu) != (2, 2, 2):
        raise ValueError(
            "invalid MuJoCo model dimensions: expected nq=nv=nu=2, "
            f"got nq={model.nq}, nv={model.nv}, nu={model.nu}"
        )
    if model.nmocap < 1:
        raise ValueError("invalid MuJoCo model: a target mocap body is required")
    if model.njnt < 2 or model.nq < 2:
        raise ValueError("invalid MuJoCo model: two joint coordinates are required")
    if tuple(model.jnt_qposadr[:2]) != (0, 1):
        raise ValueError("invalid MuJoCo model: joint coordinates are not qpos[0:2]")
    if not bool(np.all(model.jnt_limited[:2])):
        raise ValueError("invalid MuJoCo model: both arm joints must have limits")
    limits = np.asarray(model.jnt_range[:2], dtype=np.float64)
    if limits.shape != (2, 2) or not np.all(np.isfinite(limits)):
        raise ValueError("invalid MuJoCo model: joint limits are not finite")
    if not np.all(limits[:, 1] > limits[:, 0]):
        raise ValueError("invalid MuJoCo model: joint limits have no positive width")

    timestep = float(model.opt.timestep)
    if not np.isfinite(timestep) or timestep <= 0.0:
        raise ValueError("invalid MuJoCo model: integration timestep must be positive")
    if not np.isclose(timestep, 0.002, rtol=0.0, atol=1e-12):
        raise ValueError(
            f"invalid integration timestep: expected 0.002, got {timestep}"
        )
    if env.frame_skip != FRAME_SKIP:
        raise ValueError(
            f"invalid evaluation frame skip: expected {FRAME_SKIP}, got {env.frame_skip}"
        )
    if env.max_episode_steps != MAX_EPISODE_STEPS:
        raise ValueError(
            "invalid evaluation horizon: "
            f"expected {MAX_EPISODE_STEPS}, got {env.max_episode_steps}"
        )
    if not np.isclose(
        env.success_threshold, SUCCESS_THRESHOLD, rtol=0.0, atol=0.0
    ):
        raise ValueError(
            "invalid evaluation tolerance: "
            f"expected {SUCCESS_THRESHOLD}, got {env.success_threshold}"
        )
    expected_hold_steps = round(HOLD_SECONDS / (timestep * env.frame_skip))
    if env.hold_steps_required != expected_hold_steps:
        raise ValueError(
            "invalid evaluation hold duration: "
            f"expected {expected_hold_steps} steps, got {env.hold_steps_required}"
        )
    if model.nsite < 1:
        raise ValueError("invalid MuJoCo model: an end-effector site is required")
    try:
        env.data.site("end_effector")
    except (KeyError, ValueError):
        raise ValueError("invalid MuJoCo model: missing end_effector site") from None

    return {
        "observation_space": _space_metadata(runtime.observation_space),
        "action_space": _space_metadata(runtime.action_space),
        "joint_limits": limits,
        "integration_timestep": timestep,
        "control_timestep": timestep * env.frame_skip,
    }


def _joint_limit_metrics(joints: np.ndarray, limits: np.ndarray) -> dict[str, Any]:
    distances = np.minimum(joints - limits[:, 0], limits[:, 1] - joints)
    margins = distances / (limits[:, 1] - limits[:, 0])
    return {
        "joint_limit_distances": distances,
        "joint_limit_margins": margins,
        "joint_limit_feasible": bool(np.all(distances >= 0.0)),
        "normalized_min_joint_limit_margin": float(np.min(margins)),
    }


def _forward_kinematics(joints: np.ndarray, target_z: float) -> np.ndarray:
    shoulder, elbow = float(joints[0]), float(joints[1])
    return np.asarray(
        [
            UPPER_ARM_LENGTH * np.cos(shoulder)
            + FOREARM_LENGTH * np.cos(shoulder + elbow),
            UPPER_ARM_LENGTH * np.sin(shoulder)
            + FOREARM_LENGTH * np.sin(shoulder + elbow),
            target_z,
        ],
        dtype=np.float64,
    )


def _ik_metrics(
    target: np.ndarray, actual_joints: np.ndarray, limits: np.ndarray
) -> dict[str, Any]:
    target_x, target_y = float(target[0]), float(target[1])
    cosine = (
        target_x**2
        + target_y**2
        - UPPER_ARM_LENGTH**2
        - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cosine, -1.0, 1.0)))

    def shoulder_for_elbow(elbow: float) -> float:
        return float(
            np.arctan2(target_y, target_x)
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )

    branches = {
        "open": np.asarray(
            [shoulder_for_elbow(elbow_open), elbow_open], dtype=np.float64
        ),
        "folded": np.asarray(
            [shoulder_for_elbow(-elbow_open), -elbow_open], dtype=np.float64
        ),
    }
    branch_records: dict[str, dict[str, Any]] = {}
    errors: dict[str, float] = {}
    for name, joints in branches.items():
        error = np.asarray(
            [_wrap_to_pi(joints[0] - actual_joints[0]), _wrap_to_pi(joints[1] - actual_joints[1])],
            dtype=np.float64,
        )
        errors[name] = float(np.linalg.norm(error))
        limit_metrics = _joint_limit_metrics(joints, limits)
        fk = _forward_kinematics(joints, float(target[2]))
        branch_records[name] = {
            "joints": joints,
            "wrapped_joint_space_error": error,
            "wrapped_joint_space_error_norm": errors[name],
            "forward_kinematics": fk,
            "target_residual": float(np.linalg.norm(fk - target)),
            **limit_metrics,
        }

    if np.isclose(errors["open"], errors["folded"], rtol=0.0, atol=_IK_TIE_ATOL):
        selected_branch = "ambiguous_tie"
    else:
        selected_branch = "open" if errors["open"] < errors["folded"] else "folded"

    return {
        "ik_branches": branch_records,
        "selected_ik_branch": selected_branch,
        "planar_jacobian_determinant": abs(
            UPPER_ARM_LENGTH * FOREARM_LENGTH * np.sin(actual_joints[1])
        ),
        "planar_manipulability": abs(
            UPPER_ARM_LENGTH * FOREARM_LENGTH * np.sin(actual_joints[1])
        ),
    }


def _runtime_metadata(runtime: Any) -> dict[str, Any]:
    return {
        "runtime_class": _class_name(runtime),
        "loaded_policy_model_class": _class_name(runtime.model),
        "normalizer_class": (
            None if runtime.normalizer is None else _class_name(runtime.normalizer)
        ),
        "observation_space": _space_metadata(runtime.observation_space),
        "action_space": _space_metadata(runtime.action_space),
        "policy_io": {
            "observe": _callable_name(runtime.io.observe),
            "action": _callable_name(runtime.io.action),
            "reset": (
                None
                if runtime.io.reset is None
                else _callable_name(runtime.io.reset)
            ),
        },
    }


def _trace_control_frame(
    env: Any,
    raw_action: Any,
    *,
    target: np.ndarray,
    episode: int,
    control_step: int,
    held_before: int,
    limits: np.ndarray,
) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
    """Perform exactly one shared-environment control frame with substep samples."""
    mapped_action = np.asarray(env.policy_io.action(raw_action), dtype=np.float64)
    if mapped_action.shape != (2,):
        raise ValueError(
            f"invalid mapped action dimensions: expected (2,), got {mapped_action.shape}"
        )
    if not np.all(np.isfinite(mapped_action)):
        raise ValueError("policy I/O produced a non-finite action")
    applied_control = np.clip(
        mapped_action, env.action_space.low, env.action_space.high
    )
    env.data.ctrl[:] = applied_control

    frame_time_start = float(env.data.time)
    internal_samples: list[dict[str, Any]] = []
    for substep in range(env.frame_skip):
        mujoco.mj_step(env.model, env.data)
        end_effector = env.data.site("end_effector").xpos.copy()
        distance = float(np.linalg.norm(end_effector - target))
        internal_samples.append(
            {
                "substep_index": substep,
                "simulation_time": float(env.data.time),
                "distance_m": distance,
                "boundary_distance_m": float(env.success_threshold - distance),
                "outside_tolerance": bool(distance > env.success_threshold),
            }
        )

    distance = float(internal_samples[-1]["distance_m"])
    boundary_distance = float(env.success_threshold - distance)
    if distance <= env.success_threshold:
        held_after = held_before + 1
        env._outside_after_hold = False
    else:
        if held_before > 0:
            env._outside_after_hold = True
        held_after = 0

    reward = reach_reward(
        env._previous_distance,
        distance,
        env.success_threshold,
        applied_control,
        held_steps=held_after,
        previous_held_steps=held_before,
        hold_steps_required=env.hold_steps_required,
        penalize_outside=env._outside_after_hold,
    )
    env._previous_distance = distance
    env._held_steps = held_after
    env._step_count += 1
    terminated = held_after >= env.hold_steps_required
    truncated = env._step_count >= env.max_episode_steps

    entered = held_before == 0 and held_after > 0
    continued = held_before > 0 and held_after > 0
    interrupted = held_before > 0 and held_after == 0
    qpos = np.asarray(env.data.qpos[:2], dtype=np.float64).copy()
    qvel = np.asarray(env.data.qvel[:2], dtype=np.float64).copy()
    limit_metrics = _joint_limit_metrics(qpos, limits)
    ik = _ik_metrics(target, qpos, limits)
    internal_distances = np.asarray(
        [sample["distance_m"] for sample in internal_samples], dtype=np.float64
    )
    internal_boundaries = np.asarray(
        [sample["boundary_distance_m"] for sample in internal_samples],
        dtype=np.float64,
    )
    step_trace = {
        "episode": episode,
        "control_index": control_step - 1,
        "control_step": control_step,
        "simulation_time_start": frame_time_start,
        "simulation_time_end": float(env.data.time),
        "target_position_m": target,
        "target_radius_m": float(np.hypot(target[0], target[1])),
        "target_angle_radians": float(np.arctan2(target[1], target[0])),
        "target_angle_degrees": float(np.degrees(np.arctan2(target[1], target[0]))),
        "qpos": qpos,
        "qvel": qvel,
        "raw_policy_action": raw_action,
        "applied_clipped_physical_control": applied_control,
        "distance_m": distance,
        "boundary_distance_m": boundary_distance,
        "hold_age_before": held_before,
        "hold_age_after": held_after,
        "entered_hold": entered,
        "continued_hold": continued,
        "interrupted_hold": interrupted,
        "joint_limit_metrics": limit_metrics,
        **ik,
        "internal_samples": internal_samples,
        "internal_site_target_distances_m": internal_distances,
        "minimum_internal_site_target_distance_m": float(np.min(internal_distances)),
        "minimum_internal_boundary_distance_m": float(np.min(internal_boundaries)),
        "any_internal_sample_outside_tolerance": bool(
            np.any(internal_distances > env.success_threshold)
        ),
        "reward": float(reward.total),
        "terminated": bool(terminated),
        "truncated": bool(truncated),
    }
    return env._observation(), float(reward.total), terminated, truncated, step_trace


def build_artifact(
    model_path: Path,
    episodes: int,
    seed: int,
    algorithm: str | None = None,
) -> dict:
    """Replay a saved runtime and return a strict-JSON-compatible trace."""
    _validate_inputs(episodes, seed)
    runtime = load_runtime(Path(model_path), algorithm)
    env = make_evaluation_env(policy_runtime=runtime)
    environment_metadata = _validate_environment(runtime, env)
    runtime_metadata = _runtime_metadata(runtime)
    limits = environment_metadata["joint_limits"]
    protocol = {
        "control_timestep_seconds": environment_metadata["control_timestep"],
        "integration_timestep_seconds": environment_metadata["integration_timestep"],
        "frame_skip": int(env.frame_skip),
        "tolerance_m": float(env.success_threshold),
        "boundary_distance_definition": "tolerance_m minus site_target_distance_m",
        "required_hold_steps": int(env.hold_steps_required),
        "max_episode_steps": int(env.max_episode_steps),
        "trace_runtime": "frozen saved runtime",
    }

    episode_traces: list[dict[str, Any]] = []
    for episode in range(episodes):
        episode_seed = seed + episode
        observation, _ = env.reset(seed=episode_seed)
        runtime.reset()
        target = np.asarray(env.data.mocap_pos[0], dtype=np.float64).copy()
        target_radius = float(np.hypot(target[0], target[1]))
        target_angle = float(np.arctan2(target[1], target[0]))
        first_observation = np.asarray(observation)
        if first_observation.shape != (11,):
            raise ValueError(
                f"invalid observed dimensions at reset: expected (11,), "
                f"got {first_observation.shape}"
            )

        steps: list[dict[str, Any]] = []
        reward_total = 0.0
        terminated = False
        truncated = False
        first_entry_step: int | None = None
        max_held_steps = 0
        in_tolerance_frames = 0
        hold_interruptions = 0
        minimum_boundary_distance = float("inf")
        final_boundary_distance: float | None = None
        minimum_distance = float("inf")
        final_distance: float | None = None
        held_steps = 0

        episode_runtime = {
            **runtime_metadata,
            "state_after_reset": _state_summary(runtime.state),
            "episode_start_after_reset": bool(runtime.episode_start),
        }
        while not (terminated or truncated):
            state_before = _state_summary(runtime.state)
            episode_start_before = bool(runtime.episode_start)
            raw_action = runtime.predict(observation)
            state_after = _state_summary(runtime.state)
            episode_start_after = bool(runtime.episode_start)
            control_step = len(steps) + 1
            (
                observation,
                reward,
                terminated,
                truncated,
                step_trace,
            ) = _trace_control_frame(
                env,
                raw_action,
                target=target,
                episode=episode,
                control_step=control_step,
                held_before=held_steps,
                limits=limits,
            )
            step_trace["runtime"] = {
                **runtime_metadata,
                "state_before_prediction": state_before,
                "state_after_prediction": state_after,
                "episode_start_before_prediction": episode_start_before,
                "episode_start_after_prediction": episode_start_after,
            }
            steps.append(step_trace)
            reward_total += reward
            held_after = int(step_trace["hold_age_after"])
            if held_after > 0:
                in_tolerance_frames += 1
                if first_entry_step is None:
                    first_entry_step = control_step
            if step_trace["interrupted_hold"]:
                hold_interruptions += 1
            held_steps = held_after
            max_held_steps = max(max_held_steps, held_steps)
            minimum_boundary_distance = min(
                minimum_boundary_distance, float(step_trace["boundary_distance_m"])
            )
            final_boundary_distance = float(step_trace["boundary_distance_m"])
            minimum_distance = min(minimum_distance, float(step_trace["distance_m"]))
            final_distance = float(step_trace["distance_m"])

        success = bool(terminated and held_steps >= env.hold_steps_required)
        if success:
            failure_class = "success"
        elif first_entry_step is None:
            failure_class = "no_entry"
        else:
            failure_class = "post_entry_failure"
        episode_runtime["state_after_episode"] = _state_summary(runtime.state)
        episode_runtime["episode_start_after_episode"] = bool(runtime.episode_start)
        episode_traces.append(
            {
                "episode": episode,
                "episode_seed": episode_seed,
                "target_position_m": target,
                "target_radius_m": target_radius,
                "target_angle_radians": target_angle,
                "target_angle_degrees": float(np.degrees(target_angle)),
                "success": success,
                "terminated": bool(terminated),
                "truncated": bool(truncated),
                "steps": len(steps),
                "reward_total": reward_total,
                "first_entry_step": first_entry_step,
                "first_reach_step": first_entry_step,
                "max_held_steps": max_held_steps,
                "in_tolerance_control_frames": in_tolerance_frames,
                "in_tolerance_steps": in_tolerance_frames,
                "hold_interruptions": hold_interruptions,
                "minimum_boundary_distance_m": minimum_boundary_distance,
                "final_boundary_distance_m": final_boundary_distance,
                "minimum_distance_m": minimum_distance,
                "min_distance_cm": minimum_distance * 100.0,
                "final_distance_cm": (
                    None
                    if final_distance is None
                    else final_distance * 100.0
                ),
                "failure_class": failure_class,
                "runtime": episode_runtime,
                "steps_trace": steps,
            }
        )

    artifact = {
        "schema_version": SCHEMA_VERSION,
        "model": str(Path(model_path)),
        "algorithm": algorithm,
        "episodes": episodes,
        "seed": seed,
        "official_benchmark": False,
        "protocol": protocol,
        "runtime": runtime_metadata,
        "episode_traces": episode_traces,
    }
    artifact = _json_value(artifact)
    json.dumps(artifact, allow_nan=False, sort_keys=True, separators=(",", ":"))
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Trace a frozen saved policy under research evaluation semantics."
    )
    parser.add_argument("model_path", type=Path)
    parser.add_argument("output_path", type=Path)
    parser.add_argument("--episodes", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--algorithm", default=None)
    arguments = parser.parse_args()
    artifact = build_artifact(
        arguments.model_path,
        arguments.episodes,
        arguments.seed,
        arguments.algorithm,
    )
    arguments.output_path.parent.mkdir(parents=True, exist_ok=True)
    arguments.output_path.write_text(
        json.dumps(artifact, allow_nan=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
