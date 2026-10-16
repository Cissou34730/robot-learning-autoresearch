"""Measure compiled MuJoCo dynamics for the two-joint arm.

This module is intentionally a measurement entry point rather than an
alternative environment.  The simulation is advanced through the exact
``TwoJointArmReachEnv`` instance used by the scenario, while the task state is
not used as a measurement outcome.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

import robot_learning.scenario.environment as scenario_environment


SETTLING_INTERVALS = 25
RESET_SEED = 0
POSTURES: tuple[tuple[str, tuple[float, float]], ...] = (
    ("fully_extended", (0.0, 0.0)),
    ("near_folded", (0.0, math.radians(160.0))),
    ("intermediate", (math.radians(30.0), math.radians(-60.0))),
    ("rotated", (math.radians(90.0), math.radians(45.0))),
)


def _finite_float(value: Any, label: str) -> float:
    converted = float(value)
    if not math.isfinite(converted):
        raise RuntimeError(f"required measurement {label} is non-finite")
    return converted


def _finite_vector(values: Any, label: str) -> list[float]:
    array = np.asarray(values, dtype=np.float64).reshape(-1)
    return [_finite_float(value, f"{label}[{index}]") for index, value in enumerate(array)]


def _optional_vector(values: Any, label: str) -> list[float] | None:
    if values is None:
        return None
    return _finite_vector(values, label)


def _object_name(model: mujoco.MjModel, object_type: Any, index: int) -> str:
    name = mujoco.mj_id2name(model, object_type, index)
    return str(name) if name is not None else f"unnamed_{index}"


def _model_quantities(
    model: mujoco.MjModel, frame_skip: int
) -> dict[str, Any]:
    timestep_s = _finite_float(model.opt.timestep, "model.opt.timestep")
    quantities: dict[str, Any] = {
        "timestep_s": timestep_s,
        "frame_skip": int(frame_skip),
        "control_interval_s": _finite_float(
            timestep_s * frame_skip, "control interval"
        ),
        "joint_ranges": [],
        "bodies": [],
        "dofs": [],
        "actuators": [],
    }

    for joint_id in range(model.njnt):
        quantities["joint_ranges"].append(
            {
                "joint_id": joint_id,
                "name": _object_name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id),
                "range_rad": _finite_vector(
                    model.jnt_range[joint_id], f"joint range {joint_id}"
                ),
            }
        )

    for body_id in range(model.nbody):
        quantities["bodies"].append(
            {
                "body_id": body_id,
                "name": _object_name(model, mujoco.mjtObj.mjOBJ_BODY, body_id),
                "mass_kg": _finite_float(
                    model.body_mass[body_id], f"body mass {body_id}"
                ),
                "inertia_kg_m2": _finite_vector(
                    model.body_inertia[body_id], f"body inertia {body_id}"
                ),
            }
        )

    for dof_id in range(model.nv):
        joint_id = int(np.asarray(model.dof_jntid)[dof_id])
        quantities["dofs"].append(
            {
                "dof_id": dof_id,
                "joint_id": joint_id,
                "joint_name": _object_name(
                    model, mujoco.mjtObj.mjOBJ_JOINT, joint_id
                ),
                "damping": _finite_float(
                    model.dof_damping[dof_id], f"DOF damping {dof_id}"
                ),
                "armature": _finite_float(
                    model.dof_armature[dof_id], f"DOF armature {dof_id}"
                ),
            }
        )

    for actuator_id in range(model.nu):
        quantities["actuators"].append(
            {
                "actuator_id": actuator_id,
                "name": _object_name(
                    model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_id
                ),
                "gear": _finite_vector(
                    model.actuator_gear[actuator_id],
                    f"actuator gear {actuator_id}",
                ),
                "control_range": _finite_vector(
                    model.actuator_ctrlrange[actuator_id],
                    f"actuator control range {actuator_id}",
                ),
                "force_range": _finite_vector(
                    model.actuator_forcerange[actuator_id],
                    f"actuator force range {actuator_id}",
                ),
            }
        )
    return quantities


def _actuator_for_joints(model: mujoco.MjModel) -> dict[int, int]:
    actuator_to_joint = np.asarray(model.actuator_trnid, dtype=np.int64)
    if actuator_to_joint.ndim != 2 or actuator_to_joint.shape[1] < 1:
        raise RuntimeError("compiled model has no usable actuator-to-joint mapping")

    mapping: dict[int, int] = {}
    for actuator_id in range(model.nu):
        joint_id = int(actuator_to_joint[actuator_id, 0])
        if joint_id < 0:
            continue
        if joint_id in mapping:
            raise RuntimeError(
                f"multiple actuators found for joint {joint_id}; measurement is ambiguous"
            )
        mapping[joint_id] = actuator_id
    return mapping


def _reset_to_posture(
    env: scenario_environment.TwoJointArmReachEnv,
    qpos_addresses: np.ndarray,
    posture: tuple[float, float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    env.reset(seed=RESET_SEED)
    env.data.qpos[:] = 0.0
    env.data.qvel[:] = 0.0
    env.data.ctrl[:] = 0.0
    env.data.qpos[qpos_addresses] = np.asarray(posture, dtype=np.float64)
    mujoco.mj_forward(env.model, env.data)

    endpoint = _finite_vector(
        env.data.site("end_effector").xpos, "initial endpoint position"
    )
    qpos = _finite_vector(env.data.qpos, "initial qpos")
    qvel = _finite_vector(env.data.qvel, "initial qvel")
    return (
        np.asarray(endpoint, dtype=np.float64),
        np.asarray(qpos, dtype=np.float64),
        np.asarray(qvel, dtype=np.float64),
    )


def _run_pulse(
    env: scenario_environment.TwoJointArmReachEnv,
    *,
    posture_name: str,
    posture: tuple[float, float],
    joint_id: int,
    joint_name: str,
    actuator_id: int,
    sign: int,
    qpos_addresses: np.ndarray,
    control_interval_s: float,
) -> dict[str, Any]:
    initial_endpoint, initial_qpos, initial_qvel = _reset_to_posture(
        env, qpos_addresses, posture
    )
    initial_force = _optional_vector(
        getattr(env.data, "qfrc_actuator", None),
        "initial actuator generalized force",
    )

    action = np.zeros(env.action_space.shape, dtype=np.float64)
    action[actuator_id] = float(sign)
    records: list[dict[str, Any]] = []
    previous_endpoint = initial_endpoint

    for interval_index in range(1, SETTLING_INTERVALS + 2):
        phase = "pulse" if interval_index == 1 else "settling"
        interval_action = action if interval_index == 1 else np.zeros_like(action)
        env.step(interval_action)

        endpoint = np.asarray(
            _finite_vector(
                env.data.site("end_effector").xpos,
                f"{posture_name} endpoint position interval {interval_index}",
            ),
            dtype=np.float64,
        )
        endpoint_velocity = (endpoint - previous_endpoint) / control_interval_s
        record: dict[str, Any] = {
            "control_interval": interval_index,
            "time_s": _finite_float(
                interval_index * control_interval_s,
                f"{posture_name} interval time",
            ),
            "phase": phase,
            "action": _finite_vector(
                interval_action, f"{posture_name} action interval {interval_index}"
            ),
            "control": _finite_vector(
                env.data.ctrl, f"{posture_name} control interval {interval_index}"
            ),
            "qpos": _finite_vector(
                env.data.qpos, f"{posture_name} qpos interval {interval_index}"
            ),
            "qvel": _finite_vector(
                env.data.qvel, f"{posture_name} qvel interval {interval_index}"
            ),
            "endpoint_position_m": _finite_vector(
                endpoint, f"{posture_name} endpoint position interval {interval_index}"
            ),
            "endpoint_velocity_m_per_s": _finite_vector(
                endpoint_velocity,
                f"{posture_name} endpoint velocity interval {interval_index}",
            ),
        }
        records.append(record)
        previous_endpoint = endpoint

        if interval_index == 1:
            post_pulse_force = _optional_vector(
                getattr(env.data, "qfrc_actuator", None),
                "post-pulse actuator generalized force",
            )

    return {
        "posture": {
            "name": posture_name,
            "qpos_rad": _finite_vector(posture, f"{posture_name} posture"),
        },
        "joint": {
            "joint_id": joint_id,
            "joint_name": joint_name,
            "actuator_id": actuator_id,
            "action_index": actuator_id,
            "pulse_sign": sign,
            "pulse_action": float(sign),
        },
        "initial_state": {
            "qpos": _finite_vector(initial_qpos, f"{posture_name} initial qpos"),
            "qvel": _finite_vector(initial_qvel, f"{posture_name} initial qvel"),
            "endpoint_position_m": _finite_vector(
                initial_endpoint, f"{posture_name} initial endpoint position"
            ),
            "actuator_generalized_force": initial_force,
        },
        "post_pulse_actuator_generalized_force": post_pulse_force,
        "intervals": records,
    }


def measure() -> dict[str, Any]:
    env = scenario_environment.TwoJointArmReachEnv()
    model = env.model
    frame_skip = int(env.frame_skip)
    if frame_skip <= 0:
        raise RuntimeError("environment frame_skip must be positive")
    if model.nq != 2 or model.nv != 2:
        raise RuntimeError(
            f"expected two joint coordinates, compiled model has nq={model.nq}, nv={model.nv}"
        )
    if model.nu != env.action_space.shape[0]:
        raise RuntimeError(
            "environment action dimension does not match compiled actuator count"
        )

    qpos_addresses = np.asarray(model.jnt_qposadr, dtype=np.int64)
    if qpos_addresses.shape != (model.njnt,):
        raise RuntimeError("compiled joint qpos addresses are not usable")
    if model.njnt != 2:
        raise RuntimeError(f"expected two joints, compiled model has {model.njnt}")

    joint_ranges = np.asarray(model.jnt_range, dtype=np.float64)
    for posture_name, posture in POSTURES:
        posture_array = np.asarray(posture, dtype=np.float64)
        if posture_array.shape != (model.njnt,):
            raise RuntimeError(f"{posture_name} does not specify every joint")
        if np.any(posture_array < joint_ranges[:, 0]) or np.any(
            posture_array > joint_ranges[:, 1]
        ):
            raise RuntimeError(f"{posture_name} is outside the compiled joint limits")

    model_quantities = _model_quantities(model, frame_skip)
    control_interval_s = model_quantities["control_interval_s"]
    actuator_by_joint = _actuator_for_joints(model)
    joint_names = [
        _object_name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id)
        for joint_id in range(model.njnt)
    ]
    if set(actuator_by_joint) != set(range(model.njnt)):
        raise RuntimeError("not every compiled joint has exactly one actuator")

    experiments: list[dict[str, Any]] = []
    for posture_name, posture in POSTURES:
        for joint_id, joint_name in enumerate(joint_names):
            actuator_id = actuator_by_joint[joint_id]
            for sign in (-1, 1):
                experiments.append(
                    _run_pulse(
                        env,
                        posture_name=posture_name,
                        posture=posture,
                        joint_id=joint_id,
                        joint_name=joint_name,
                        actuator_id=actuator_id,
                        sign=sign,
                        qpos_addresses=qpos_addresses,
                        control_interval_s=control_interval_s,
                    )
                )

    return {
        "schema": "compiled_dynamics_measurement.v1",
        "runtime": {
            "environment_class": (
                f"{type(env).__module__}.{type(env).__qualname__}"
            ),
            "environment_module": scenario_environment.__name__,
            "environment_source": str(
                Path(scenario_environment.__file__).resolve()
            ),
            "model_source": str(
                Path(scenario_environment.TWO_JOINT_ARM_XML_PATH).resolve()
            ),
            "mujoco_api": "native mujoco",
            "mujoco_version": getattr(mujoco, "__version__", None),
        },
        "units": {
            "time": "s",
            "joint_position": "rad",
            "joint_velocity": "rad/s",
            "endpoint_position": "m",
            "endpoint_velocity": "m/s",
            "mass": "kg",
            "inertia": "kg m^2",
            "damping": "N m s/rad",
            "armature": "kg m^2",
            "generalized_force": "N m for hinge DOFs",
            "action": "dimensionless environment action in [-1, 1]",
            "control": "dimensionless actuator control",
        },
        "measurement": {
            "pulse_duration_s": control_interval_s,
            "pulse_control_intervals": 1,
            "settling_intervals": SETTLING_INTERVALS,
            "settling_duration_s": _finite_float(
                SETTLING_INTERVALS * control_interval_s,
                "settling duration",
            ),
            "posture_count": len(POSTURES),
            "joint_count": model.njnt,
            "pulse_signs": [-1, 1],
            "reset_seed": RESET_SEED,
        },
        "compiled_model": model_quantities,
        "experiments": experiments,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure the compiled two-joint arm dynamics."
    )
    parser.add_argument(
        "--output",
        required=True,
        help="path for the single JSON measurement artifact",
    )
    args = parser.parse_args(argv)
    if not args.output.strip() or args.output == "-":
        parser.error("--output must be a concrete file path")
    return args


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    output_path = Path(args.output)
    if output_path.exists() and output_path.is_dir():
        raise ValueError(f"measurement output is a directory: {output_path}")
    if not output_path.parent.exists():
        raise FileNotFoundError(
            f"measurement output directory does not exist: {output_path.parent}"
        )

    artifact = measure()
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(artifact, handle, indent=2, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
