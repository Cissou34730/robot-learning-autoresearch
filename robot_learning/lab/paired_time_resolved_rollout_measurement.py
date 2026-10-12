"""Paired time-resolved rollout measurement for the T7/T4 comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

import mujoco
import numpy as np

from contracts.policy_runtime import load_runtime
from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from contracts.task_spec import FRAME_SKIP, MAX_EPISODE_STEPS, SUCCESS_THRESHOLD
from robot_learning.scenario.environment import make_evaluation_env


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = 1
HOLD_STEPS_REQUIRED = 100
BRANCH_NEAR_TOLERANCE_RAD = 0.10
JOINT_LIMIT_TOLERANCE_RAD = 1e-10


def _finite_array(
    values: Any, field: str, shape: tuple[int, ...] | None = None
) -> list[float]:
    array = np.asarray(values, dtype=np.float64)
    if shape is not None and array.shape != shape:
        raise ValueError(f"{field} has shape {array.shape}, expected {shape}")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{field} contains a non-finite value")
    return [float(value) for value in array.reshape(-1)]


def _finite_scalar(value: Any, field: str) -> float:
    result = float(value)
    if not np.isfinite(result):
        raise ValueError(f"{field} contains a non-finite value")
    return result


def _parse_seeds(values: Sequence[str], field: str) -> list[int]:
    tokens: list[str] = []
    for value in values:
        tokens.extend(value.replace(",", " ").split())
    if not tokens:
        raise ValueError(f"{field} must contain at least one integer seed")
    seeds: list[int] = []
    for token in tokens:
        try:
            seed = int(token, 10)
        except ValueError as exc:
            raise ValueError(f"{field} contains malformed seed {token!r}") from exc
        if seed < 0 or str(seed) != token.lstrip("+"):
            raise ValueError(f"{field} contains malformed seed {token!r}")
        seeds.append(seed)
    if len(set(seeds)) != len(seeds):
        raise ValueError(f"{field} contains duplicate seeds")
    return seeds


def _resolve_repository_path(path: Path) -> Path:
    return (path if path.is_absolute() else REPOSITORY_ROOT / path).resolve()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _bounded_ik(
    target_position: np.ndarray, model: mujoco.MjModel, qpos: np.ndarray
) -> dict[str, Any]:
    x, y = float(target_position[0]), float(target_position[1])
    radius_squared = x * x + y * y
    cosine = (
        radius_squared - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    if cosine < -1.0 - 1e-10 or cosine > 1.0 + 1e-10:
        raise ValueError(f"target is outside the analytic IK domain: cosine={cosine}")
    elbow_open = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    solutions: dict[str, Any] = {}
    for name, elbow in (("open", elbow_open), ("folded", -elbow_open)):
        shoulder = np.arctan2(y, x) - np.arctan2(
            FOREARM_LENGTH * np.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
        )
        solution = np.array([_wrap_to_pi(shoulder), elbow], dtype=np.float64)
        limits = model.jnt_range[:2]
        feasible = bool(
            np.all(solution >= limits[:, 0] - JOINT_LIMIT_TOLERANCE_RAD)
            and np.all(solution <= limits[:, 1] + JOINT_LIMIT_TOLERANCE_RAD)
        )
        error = float(
            np.linalg.norm(
                np.array(
                    [_wrap_to_pi(qpos[0] - solution[0]), qpos[1] - solution[1]]
                )
            )
        )
        solutions[name] = {
            "qpos_rad": _finite_array(solution, f"{name}_ik_solution", (2,)),
            "feasible": feasible,
            "error_rad": _finite_scalar(error, f"{name}_ik_error"),
        }
    near = [
        name
        for name, branch in solutions.items()
        if branch["feasible"] and branch["error_rad"] <= BRANCH_NEAR_TOLERANCE_RAD
    ]
    solutions["occupancy"] = (
        "ambiguous"
        if not near
        else min(near, key=lambda name: solutions[name]["error_rad"])
    )
    return solutions


def _contact_record(data: mujoco.MjData) -> dict[str, Any]:
    events = []
    for contact_index in range(int(data.ncon)):
        contact = data.contact[contact_index]
        events.append(
            {
                "geom1": int(contact.geom1),
                "geom2": int(contact.geom2),
                "distance_m": _finite_scalar(contact.dist, "contact_distance"),
            }
        )
    return {"count": int(data.ncon), "events": events}


def _target_metadata(target: np.ndarray) -> dict[str, Any]:
    radius = float(np.hypot(target[0], target[1]))
    return {
        "position_m": _finite_array(target, "target_position", (3,)),
        "radius_m": _finite_scalar(radius, "target_radius"),
        "radius_cm": _finite_scalar(100.0 * radius, "target_radius_cm"),
        "angle_degrees": _finite_scalar(
            np.degrees(np.arctan2(target[1], target[0])), "target_angle"
        ),
    }


def _dynamics_record(
    qpos: np.ndarray,
    qvel: np.ndarray,
    endpoint: np.ndarray,
    endpoint_velocity: np.ndarray,
) -> dict[str, Any]:
    planar_radius = float(np.hypot(endpoint[0], endpoint[1]))
    if planar_radius <= 1e-15:
        radial_velocity = None
        tangential_velocity = None
    else:
        radial_unit = endpoint[:2] / planar_radius
        tangential_unit = np.array([-radial_unit[1], radial_unit[0]])
        radial_velocity = _finite_scalar(
            np.dot(endpoint_velocity[:2], radial_unit), "radial_endpoint_velocity"
        )
        tangential_velocity = _finite_scalar(
            np.dot(endpoint_velocity[:2], tangential_unit),
            "tangential_endpoint_velocity",
        )
    return {
        "elbow_angle_rad": _finite_scalar(qpos[1], "elbow_angle"),
        "sin_elbow": _finite_scalar(np.sin(qpos[1]), "sin_elbow"),
        "joint_velocity_norm_rad_s": _finite_scalar(
            np.linalg.norm(qvel), "joint_velocity_norm"
        ),
        "endpoint_velocity_norm_m_s": _finite_scalar(
            np.linalg.norm(endpoint_velocity), "endpoint_velocity_norm"
        ),
        "radial_endpoint_velocity_m_s": radial_velocity,
        "tangential_endpoint_velocity_m_s": tangential_velocity,
    }


def _kinematic_reference(
    model: mujoco.MjModel,
    replay_data: mujoco.MjData,
    site_id: int,
    qpos_after: np.ndarray,
    qvel_after: np.ndarray,
    observed_endpoint: np.ndarray,
    observed_endpoint_velocity: np.ndarray,
) -> dict[str, Any]:
    replay_data.qpos[:] = qpos_after
    replay_data.qvel[:] = qvel_after
    mujoco.mj_forward(model, replay_data)
    reference_endpoint = np.asarray(
        replay_data.site("end_effector").xpos, dtype=np.float64
    ).copy()
    jacobian_position = np.empty((3, model.nv), dtype=np.float64)
    jacobian_rotation = np.empty((3, model.nv), dtype=np.float64)
    mujoco.mj_jacSite(
        model,
        replay_data,
        jacobian_position,
        jacobian_rotation,
        site_id,
    )
    if not np.all(np.isfinite(jacobian_position)):
        raise ValueError("replay endpoint Jacobian contains a non-finite value")
    reference_endpoint_velocity = jacobian_position @ qvel_after
    return {
        "endpoint_position_m": _finite_array(
            reference_endpoint, "kinematic_reference_endpoint_position", (3,)
        ),
        "endpoint_velocity_m_s": _finite_array(
            reference_endpoint_velocity,
            "kinematic_reference_endpoint_velocity",
            (3,),
        ),
        "position_error_m": _finite_scalar(
            np.linalg.norm(observed_endpoint - reference_endpoint),
            "kinematic_reference_position_error",
        ),
        "velocity_error_m_s": _finite_scalar(
            np.linalg.norm(observed_endpoint_velocity - reference_endpoint_velocity),
            "kinematic_reference_velocity_error",
        ),
    }


def _rollout(
    env: Any,
    runtime: Any,
    model: mujoco.MjModel,
    seed: int,
    max_steps: int,
) -> dict[str, Any]:
    observation, _ = env.reset(seed=seed)
    runtime.reset()
    if observation.shape != runtime.observation_space.shape:
        raise ValueError("reset observation does not match saved runtime")
    if env.data.qpos.shape != (2,) or env.data.qvel.shape != (2,):
        raise ValueError("the compiled task must have two position and velocity DOFs")
    initial_qpos = np.asarray(env.data.qpos, dtype=np.float64).copy()
    initial_qvel = np.asarray(env.data.qvel, dtype=np.float64).copy()
    if not np.array_equal(initial_qpos, np.zeros(2)) or not np.array_equal(
        initial_qvel, np.zeros(2)
    ):
        raise ValueError("reset did not produce the required zero state")

    replay_data = mujoco.MjData(model)
    site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "end_effector")
    if site_id < 0:
        raise ValueError("compiled model has no end_effector site")
    target = np.asarray(env.data.mocap_pos[0], dtype=np.float64).copy()
    target_info = _target_metadata(target)
    trace: list[dict[str, Any]] = []
    previous_held_steps = 0
    cumulative_interruptions = 0
    terminated = False
    truncated = False
    reward_total = 0.0
    final_info: dict[str, Any] = {}

    for control_step in range(1, max_steps + 1):
        qpos_before = np.asarray(env.data.qpos, dtype=np.float64).copy()
        qvel_before = np.asarray(env.data.qvel, dtype=np.float64).copy()
        action = np.asarray(runtime.predict(observation), dtype=np.float64)
        if action.shape != env.action_space.shape:
            raise ValueError("policy action has an unexpected shape")
        if not np.all(np.isfinite(action)):
            raise ValueError("policy action contains a non-finite value")
        observation, reward, terminated, truncated, info = env.step(action)
        final_info = info
        qpos_after = np.asarray(env.data.qpos, dtype=np.float64).copy()
        qvel_after = np.asarray(env.data.qvel, dtype=np.float64).copy()
        endpoint = np.asarray(env.data.site("end_effector").xpos, dtype=np.float64).copy()
        site_velocity = np.empty(6, dtype=np.float64)
        mujoco.mj_objectVelocity(
            model, env.data, mujoco.mjtObj.mjOBJ_SITE, site_id, site_velocity, 0
        )
        if not np.all(np.isfinite(site_velocity)):
            raise ValueError("site velocity contains a non-finite value")
        endpoint_velocity = site_velocity[3:6].copy()
        kinematic_reference = _kinematic_reference(
            model,
            replay_data,
            site_id,
            qpos_after,
            qvel_after,
            endpoint,
            endpoint_velocity,
        )
        applied_control = np.asarray(env.data.ctrl, dtype=np.float64).copy()
        if applied_control.shape != (2,) or not np.all(np.isfinite(applied_control)):
            raise ValueError("applied control is not a finite two-vector")
        distance = _finite_scalar(info["distance"], "environment distance")
        in_tolerance = bool(distance <= SUCCESS_THRESHOLD)
        held_steps = int(info["held_steps"])
        expected_held_steps = previous_held_steps + 1 if in_tolerance else 0
        if held_steps != expected_held_steps:
            raise ValueError("environment hold counter disagrees with its transition rule")
        interruption = bool(previous_held_steps > 0 and not in_tolerance)
        if interruption:
            cumulative_interruptions += 1
        transition = (
            "entered"
            if in_tolerance and previous_held_steps == 0
            else "continued"
            if in_tolerance
            else "interrupted"
            if interruption
            else "outside"
        )
        trace.append(
            {
                "control_step": control_step,
                "qpos_before_rad": _finite_array(qpos_before, "qpos_before", (2,)),
                "qvel_before_rad_s": _finite_array(qvel_before, "qvel_before", (2,)),
                "qpos_after_rad": _finite_array(qpos_after, "qpos_after", (2,)),
                "qvel_after_rad_s": _finite_array(qvel_after, "qvel_after", (2,)),
                "endpoint_position_m": _finite_array(endpoint, "endpoint_position", (3,)),
                "endpoint_velocity_m_s": _finite_array(
                    endpoint_velocity, "endpoint_velocity", (3,)
                ),
                "target_position_m": _finite_array(target, "target_position", (3,)),
                "distance_m": distance,
                "distance_cm": _finite_scalar(100.0 * distance, "distance_cm"),
                "kinematic_reference": kinematic_reference,
                "policy_action": _finite_array(action, "policy_action", (2,)),
                "applied_clipped_control": _finite_array(
                    applied_control, "applied_control", (2,)
                ),
                "actuator_force": _finite_array(
                    env.data.actuator_force, "actuator_force", (2,)
                ),
                "joint_actuator_torque_Nm": _finite_array(
                    env.data.qfrc_actuator, "joint_actuator_torque", (2,)
                ),
                "previous_held_steps": previous_held_steps,
                "held_steps": held_steps,
                "in_tolerance": in_tolerance,
                "hold_counter_transition": transition,
                "interruption": interruption,
                "cumulative_interruptions": cumulative_interruptions,
                "terminated": bool(terminated),
                "truncated": bool(truncated),
                "contact": _contact_record(env.data),
                "ik": _bounded_ik(target, model, qpos_after),
                "dynamics": _dynamics_record(
                    qpos_after, qvel_after, endpoint, endpoint_velocity
                ),
            }
        )
        reward_total += _finite_scalar(reward, "reward")
        previous_held_steps = held_steps
        if terminated or truncated:
            break
    if not (terminated or truncated):
        raise ValueError(f"seed {seed} exceeded the requested maximum control steps")

    success = bool(final_info.get("is_success", False))
    first_reach_step = next(
        (record["control_step"] for record in trace if record["in_tolerance"]), None
    )
    max_held_steps = max(record["held_steps"] for record in trace)
    contact_counts = [record["contact"]["count"] for record in trace]
    return {
        "seed": seed,
        "target": target_info,
        "initial_state": {
            "qpos_rad": _finite_array(initial_qpos, "initial_qpos", (2,)),
            "qvel_rad_s": _finite_array(initial_qvel, "initial_qvel", (2,)),
        },
        "trace": trace,
        "outcome": {
            "success": success,
            "reward_total": _finite_scalar(reward_total, "reward_total"),
            "steps": len(trace),
            "terminated": bool(terminated),
            "truncated": bool(truncated),
            "first_reach_step": first_reach_step,
            "max_held_steps": max_held_steps,
            "hold_interruptions": cumulative_interruptions,
        },
        "contact_summary": {
            "samples": len(trace),
            "maximum_contact_count": max(contact_counts),
            "nonzero_contact_samples": sum(count > 0 for count in contact_counts),
        },
    }


def _candidate_record(label: str, model_path: Path, seeds: Sequence[int], max_steps: int) -> dict[str, Any]:
    runtime_path = model_path.parent / "policy_runtime.pkl"
    if not model_path.is_file():
        raise FileNotFoundError(f"missing saved model: {model_path}")
    if not runtime_path.is_file():
        raise FileNotFoundError(f"missing saved policy runtime: {runtime_path}")
    runtime = load_runtime(model_path)
    env = make_evaluation_env(policy_runtime=runtime)
    if env.frame_skip != FRAME_SKIP or env.max_episode_steps != MAX_EPISODE_STEPS:
        raise ValueError("evaluation environment does not use the fixed task timing")
    if env.hold_steps_required != HOLD_STEPS_REQUIRED:
        raise ValueError("evaluation environment does not use the 100-step hold")
    rollouts = [
        _rollout(env, runtime, env.model, seed, max_steps) for seed in seeds
    ]
    successes = sum(bool(rollout["outcome"]["success"]) for rollout in rollouts)
    return {
        "candidate_id": label,
        "model": {
            "path": str(model_path),
            "sha256": _sha256(model_path),
        },
        "runtime": {
            "path": str(runtime_path),
            "sha256": _sha256(runtime_path),
            "loaded_with": "contracts.policy_runtime.load_runtime",
        },
        "rollouts": rollouts,
        "outcome_summary": {
            "episodes": len(rollouts),
            "successes": successes,
            "failures": len(rollouts) - successes,
            "success_values_preserved": True,
        },
    }


def run_measurement(
    t7_model: Path,
    t4_model: Path,
    seeds: Sequence[int],
    max_steps: int,
) -> dict[str, Any]:
    if not seeds:
        raise ValueError("seeds must contain at least one seed")
    if len(set(seeds)) != len(seeds):
        raise ValueError("seeds must not contain duplicates")
    if max_steps != MAX_EPISODE_STEPS:
        raise ValueError("max_steps must be the exact 500-step evaluation horizon")
    t7_path = _resolve_repository_path(t7_model)
    t4_path = _resolve_repository_path(t4_model)
    if t7_path == t4_path:
        raise ValueError("T7 and T4 model paths must be distinct")
    candidates = [
        _candidate_record("t7", t7_path, seeds, max_steps),
        _candidate_record("t4", t4_path, seeds, max_steps),
    ]
    t7_by_seed = {rollout["seed"]: rollout for rollout in candidates[0]["rollouts"]}
    t4_by_seed = {rollout["seed"]: rollout for rollout in candidates[1]["rollouts"]}
    target_pairs = []
    for seed in seeds:
        t7_target = t7_by_seed[seed]["target"]["position_m"]
        t4_target = t4_by_seed[seed]["target"]["position_m"]
        if t7_target != t4_target:
            raise ValueError(f"target geometry differs between candidates at seed {seed}")
        target_pairs.append(
            {"seed": seed, "t7_target_position_m": t7_target, "t4_target_position_m": t4_target, "exact_match": True}
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "measurement": "paired_time_resolved_rollout_mechanism_discrimination",
        "units": {
            "joint_position": "rad",
            "joint_velocity": "rad/s",
            "endpoint_position": "m",
            "endpoint_velocity": "m/s",
            "distance": "m",
            "distance_display": "cm",
            "angle": "degrees",
            "torque": "N m",
            "control": "normalized actuator command",
            "time": "control steps; ten simulator substeps per control step",
        },
        "evaluation_semantics": {
            "reset_each_episode_with_seed": True,
            "runtime_reset_each_episode": True,
            "candidate_environments_are_independent": True,
            "deterministic_prediction": True,
            "frame_skip": FRAME_SKIP,
            "simulator_substeps_per_action": FRAME_SKIP,
            "control_interval_s": 0.020,
            "hold_steps_required": HOLD_STEPS_REQUIRED,
            "success_threshold_m": SUCCESS_THRESHOLD,
            "max_control_steps": MAX_EPISODE_STEPS,
            "environment_factory": "make_evaluation_env(policy_runtime=runtime)",
            "outcomes_are_actual_environment_outcomes": True,
        },
        "measurement_semantics": {
            "live_environment_fields": [
                "endpoint_position_m",
                "endpoint_velocity_m_s",
                "distance_m",
                "in_tolerance",
                "previous_held_steps",
                "held_steps",
                "hold_counter_transition",
                "interruption",
            ],
            "live_environment_source": (
                "Endpoint and velocity are sampled from the live MuJoCo data after "
                "env.step; distance and hold fields are read from the live environment "
                "transition and its info record."
            ),
            "kinematic_reference": {
                "source": (
                    "Separate MuJoCo replay loaded from qpos_after_rad and "
                    "qvel_after_rad_s, followed by mj_forward and mj_jacSite."
                ),
                "role": (
                    "Independent forward-kinematic reference; it does not replace "
                    "live environment endpoint, distance, or hold fields."
                ),
            },
            "outcomes": "No candidate role or success expectation is imposed.",
        },
        "requested_probe_seeds": list(seeds),
        "reset_evidence": {
            "each_candidate_and_seed_reset_independently": True,
            "initial_qpos_rad": [0.0, 0.0],
            "initial_qvel_rad_s": [0.0, 0.0],
            "runtime_reset_before_each_rollout": True,
            "trace_contains_before_and_after_each_update": True,
        },
        "candidates": candidates,
        "target_pairing": {
            "exact_match_all_seeds": True,
            "by_seed": target_pairs,
        },
    }


def write_measurement(
    t7_model: Path,
    t4_model: Path,
    seeds: Sequence[int],
    max_steps: int,
    artifact_path: Path,
) -> None:
    result = run_measurement(t7_model, t4_model, seeds, max_steps)
    destination = _resolve_repository_path(artifact_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Record paired time-resolved T7 and T4 rollout mechanisms."
    )
    parser.add_argument("--t7-model", required=True, type=Path)
    parser.add_argument("--t4-model", required=True, type=Path)
    parser.add_argument("--seeds", required=True, nargs="+")
    parser.add_argument("--max-steps", required=True, type=int)
    parser.add_argument("--artifact", required=True, type=Path)
    args = parser.parse_args(argv)
    write_measurement(
        args.t7_model,
        args.t4_model,
        _parse_seeds(args.seeds, "seeds"),
        args.max_steps,
        args.artifact,
    )


if __name__ == "__main__":
    main()
