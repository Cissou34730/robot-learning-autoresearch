"""Time-resolved mechanism measurement for the retained T2 policy.

This instrument deliberately uses the saved policy runtime rather than the
current scenario implementation for policy I/O.  The environment remains the
source of task semantics and compiled MuJoCo state; this module only records
the state transitions and diagnostics needed to distinguish reach, branch, and
post-reach regulation failures.
"""

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
EXPECTED_FAILURE_SEEDS = [
    4201,
    4208,
    4225,
    4226,
    4228,
    4243,
    4244,
    4246,
    4307,
    4316,
]
EXPECTED_CONTROL_SEEDS = [
    4211,
    4214,
    4236,
    4264,
    4286,
    4297,
    4337,
    4347,
    4349,
    4355,
]
HOLD_STEPS_REQUIRED = 100
BRANCH_NEAR_TOLERANCE_RAD = 0.10
JOINT_LIMIT_TOLERANCE_RAD = 1e-10


def _finite_array(values: Any, field: str, shape: tuple[int, ...] | None = None) -> list[float]:
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


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


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
    if not near:
        occupancy = "ambiguous"
    else:
        occupancy = min(near, key=lambda name: solutions[name]["error_rad"])
    solutions["occupancy"] = occupancy
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
    qpos: np.ndarray, qvel: np.ndarray, endpoint: np.ndarray, endpoint_velocity: np.ndarray
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
    if jacobian_position.shape != (3, model.nv):
        raise ValueError("replay endpoint Jacobian has an unexpected shape")
    if not np.all(np.isfinite(jacobian_position)):
        raise ValueError("replay endpoint Jacobian contains a non-finite value")
    reference_endpoint_velocity = jacobian_position @ qvel_after
    if reference_endpoint_velocity.shape != (3,):
        raise ValueError("replay endpoint velocity has an unexpected shape")
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


def _validate_rollout_outcome(
    seed: int,
    role: str,
    success: bool,
    allow_unexpected_outcomes: bool,
) -> bool:
    expected_success = role == "control"
    if not allow_unexpected_outcomes and success != expected_success:
        raise RuntimeError(
            f"seed {seed} with role {role} had unexpected outcome success={success}"
        )
    return success


def _rollout(
    env,
    runtime,
    model: mujoco.MjModel,
    seed: int,
    role: str,
    max_steps: int,
    allow_unexpected_outcomes: bool,
) -> dict[str, Any]:
    observation, _ = env.reset(seed=seed)
    runtime.reset()
    if observation.shape != runtime.observation_space.shape:
        raise ValueError(
            f"observation shape {observation.shape} does not match runtime "
            f"{runtime.observation_space.shape}"
        )
    if env.data.qpos.shape != (2,) or env.data.qvel.shape != (2,):
        raise ValueError("the compiled task must have two position and velocity DOFs")
    initial_qpos = np.asarray(env.data.qpos, dtype=np.float64).copy()
    initial_qvel = np.asarray(env.data.qvel, dtype=np.float64).copy()
    if not np.array_equal(initial_qpos, np.zeros(2)) or not np.array_equal(
        initial_qvel, np.zeros(2)
    ):
        raise ValueError("reset did not produce the required zero state")
    replay_data = mujoco.MjData(model)
    target = np.asarray(env.data.mocap_pos[0], dtype=np.float64).copy()
    target_info = _target_metadata(target)
    trace: list[dict[str, Any]] = []
    previous_held_steps = 0
    cumulative_interruptions = 0
    terminated = False
    truncated = False
    reward_total = 0.0

    for control_step in range(1, max_steps + 1):
        qpos_before = np.asarray(env.data.qpos, dtype=np.float64).copy()
        qvel_before = np.asarray(env.data.qvel, dtype=np.float64).copy()
        action = np.asarray(runtime.predict(observation), dtype=np.float64)
        if action.shape != env.action_space.shape:
            raise ValueError(
                f"policy action shape {action.shape}, expected {env.action_space.shape}"
            )
        if not np.all(np.isfinite(action)):
            raise ValueError("policy action contains a non-finite value")
        observation, reward, terminated, truncated, info = env.step(action)
        if observation.shape != runtime.observation_space.shape:
            raise ValueError("post-step observation has an unexpected shape")
        qpos_after = np.asarray(env.data.qpos, dtype=np.float64).copy()
        qvel_after = np.asarray(env.data.qvel, dtype=np.float64).copy()
        endpoint = np.asarray(env.data.site("end_effector").xpos, dtype=np.float64).copy()
        site_id = mujoco.mj_name2id(
            model, mujoco.mjtObj.mjOBJ_SITE, "end_effector"
        )
        if site_id < 0:
            raise ValueError("compiled model has no end_effector site")
        site_velocity = np.empty(6, dtype=np.float64)
        mujoco.mj_objectVelocity(
            model,
            env.data,
            mujoco.mjtObj.mjOBJ_SITE,
            site_id,
            site_velocity,
            0,
        )
        if site_velocity.shape != (6,):
            raise ValueError(
                f"site velocity has shape {site_velocity.shape}, expected (6,)"
            )
        if not np.all(np.isfinite(site_velocity)):
            raise ValueError("site velocity contains a non-finite value")
        endpoint_velocity = site_velocity[3:6].copy()
        if endpoint_velocity.shape != (3,):
            raise ValueError(
                f"endpoint velocity has shape {endpoint_velocity.shape}, expected (3,)"
            )
        if not np.all(np.isfinite(endpoint_velocity)):
            raise ValueError("endpoint velocity contains a non-finite value")
        kinematic_reference = _kinematic_reference(
            model,
            replay_data,
            site_id,
            qpos_after,
            qvel_after,
            endpoint,
            endpoint_velocity,
        )
        if env.data.ctrl.shape != (2,):
            raise ValueError("compiled actuator control shape is not two")
        applied_control = np.asarray(env.data.ctrl, dtype=np.float64).copy()
        if not np.all(np.isfinite(applied_control)):
            raise ValueError("applied control contains a non-finite value")
        distance = float(np.linalg.norm(endpoint - target))
        in_tolerance = bool(distance <= SUCCESS_THRESHOLD)
        held_steps = int(info["held_steps"])
        expected_held_steps = (
            previous_held_steps + 1 if in_tolerance else 0
        )
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
        ik = _bounded_ik(target, model, qpos_after)
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
                "distance_m": _finite_scalar(distance, "distance"),
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
                "ik": ik,
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
    success = _validate_rollout_outcome(
        seed,
        role,
        bool(info.get("is_success", False)),
        allow_unexpected_outcomes,
    )
    expected_success = role == "control"
    first_reach_step = next(
        (record["control_step"] for record in trace if record["in_tolerance"]), None
    )
    max_held_steps = max(record["held_steps"] for record in trace)
    final = trace[-1]
    contact_counts = [record["contact"]["count"] for record in trace]
    return {
        "role": role,
        "seed": seed,
        "expected_success": expected_success,
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
        "mechanism_diagnostics": {
            "final_branch_errors_rad": {
                "open": final["ik"]["open"]["error_rad"],
                "folded": final["ik"]["folded"]["error_rad"],
            },
            "final_branch_occupancy": final["ik"]["occupancy"],
            "first_reach_step": first_reach_step,
            "max_held_steps": max_held_steps,
            "hold_interruptions": cumulative_interruptions,
        },
    }


def _runtime_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_measurement(
    model_path: Path,
    failure_seeds: Sequence[int],
    control_seeds: Sequence[int],
    max_steps: int,
    allow_unexpected_outcomes: bool = False,
) -> dict[str, Any]:
    if list(failure_seeds) != EXPECTED_FAILURE_SEEDS:
        raise ValueError("failure seeds must be the exact M9 failure seed list")
    if list(control_seeds) != EXPECTED_CONTROL_SEEDS:
        raise ValueError("control seeds must be the exact M9 control seed list")
    if max_steps != MAX_EPISODE_STEPS:
        raise ValueError("max_steps must be the exact 500-step evaluation horizon")
    model_path = Path(model_path).resolve()
    if not model_path.is_file():
        raise FileNotFoundError(f"missing saved model: {model_path}")
    runtime_path = model_path.parent / "policy_runtime.pkl"
    if not runtime_path.is_file():
        raise FileNotFoundError(f"missing saved policy runtime: {runtime_path}")
    runtime = load_runtime(model_path)
    env = make_evaluation_env(policy_runtime=runtime)
    if env.frame_skip != FRAME_SKIP or env.max_episode_steps != MAX_EPISODE_STEPS:
        raise ValueError("evaluation environment does not use the fixed task timing")
    if env.hold_steps_required != HOLD_STEPS_REQUIRED:
        raise ValueError("evaluation environment does not use the 100-step hold")
    model = env.model
    rollouts = []
    for role, seeds in (("failure", failure_seeds), ("control", control_seeds)):
        for seed in seeds:
            rollouts.append(
                _rollout(
                    env,
                    runtime,
                    model,
                    seed,
                    role,
                    max_steps,
                    allow_unexpected_outcomes,
                )
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "measurement": "time_resolved_rollout_mechanism_discrimination",
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
        "runtime": {
            "model_path": str(model_path),
            "runtime_path": str(runtime_path.resolve()),
            "model_sha256": _runtime_digest(model_path),
            "runtime_sha256": _runtime_digest(runtime_path),
            "runtime_loaded_with": "contracts.policy_runtime.load_runtime",
        },
        "evaluation_semantics": {
            "reset_each_episode_with_seed": True,
            "runtime_reset_each_episode": True,
            "deterministic_prediction": True,
            "frame_skip": FRAME_SKIP,
            "simulator_substeps_per_action": FRAME_SKIP,
            "hold_steps_required": HOLD_STEPS_REQUIRED,
            "success_threshold_m": SUCCESS_THRESHOLD,
            "max_control_steps": MAX_EPISODE_STEPS,
            "environment_factory": "make_evaluation_env(policy_runtime=runtime)",
        },
        "measurement_semantics": {
            "outcome_validation": {
                "allow_unexpected_outcomes": bool(allow_unexpected_outcomes),
                "historical_role_expectation_retained": True,
                "actual_success_source": "environment info['is_success']",
            },
            "environment_observed_fields": [
                "endpoint_position_m",
                "endpoint_velocity_m_s",
                "distance_m",
                "distance_cm",
                "in_tolerance",
                "previous_held_steps",
                "held_steps",
                "hold_counter_transition",
                "interruption",
                "cumulative_interruptions",
            ],
            "environment_observed_role": (
                "Endpoint, distance, and hold fields are sampled from the live "
                "environment after env.step and retain task semantics."
            ),
            "kinematic_reference": {
                "fields": [
                    "endpoint_position_m",
                    "endpoint_velocity_m_s",
                    "position_error_m",
                    "velocity_error_m_s",
                ],
                "source": (
                    "Separate MuJoCo replay loaded from qpos_after_rad and "
                    "qvel_after_rad_s, followed by mj_forward and mj_jacSite."
                ),
                "role": (
                    "Forward-consistent reference only; it does not replace "
                    "environment-observed endpoint, distance, or hold fields."
                ),
            },
        },
        "requested_rollouts": {
            "failure_seeds": list(failure_seeds),
            "control_seeds": list(control_seeds),
            "total": len(failure_seeds) + len(control_seeds),
        },
        "reset_evidence": {
            "each_rollout_reset_with_its_seed": True,
            "initial_qpos_rad": [0.0, 0.0],
            "initial_qvel_rad_s": [0.0, 0.0],
            "trace_contains_before_and_after_each_update": True,
        },
        "rollouts": rollouts,
    }


def write_measurement(
    model_path: Path,
    failure_seeds: Sequence[int],
    control_seeds: Sequence[int],
    max_steps: int,
    artifact_path: Path,
    allow_unexpected_outcomes: bool = False,
) -> None:
    result = run_measurement(
        model_path,
        failure_seeds,
        control_seeds,
        max_steps,
        allow_unexpected_outcomes,
    )
    destination = (
        artifact_path if artifact_path.is_absolute() else REPOSITORY_ROOT / artifact_path
    ).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Record time-resolved retained-policy rollout mechanisms."
    )
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--failure-seeds", required=True, nargs="+")
    parser.add_argument("--control-seeds", required=True, nargs="+")
    parser.add_argument("--max-steps", required=True, type=int)
    parser.add_argument(
        "--allow-unexpected-outcomes",
        action="store_true",
        help="record actual outcomes without enforcing historical role expectations",
    )
    parser.add_argument("--artifact", required=True, type=Path)
    args = parser.parse_args(argv)
    failure_seeds = _parse_seeds(args.failure_seeds, "failure seeds")
    control_seeds = _parse_seeds(args.control_seeds, "control seeds")
    write_measurement(
        args.model,
        failure_seeds,
        control_seeds,
        args.max_steps,
        args.artifact,
        args.allow_unexpected_outcomes,
    )


if __name__ == "__main__":
    main()
