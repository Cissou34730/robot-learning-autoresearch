"""Controlled measurements of the compiled two-joint MuJoCo plant.

This is a PI-owned laboratory instrument, rather than a task environment. It
uses fixed states and fixed motor commands so compiled dynamics and the 20 ms
zero-order-held interface can be inspected without a policy.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = 1
FRAME_SKIP = 10
CONTROL_INTERVAL_S = 0.020
SHOULDER_ELBOW_STATE = np.array([0.30, -0.45], dtype=np.float64)
FREE_DECAY_VELOCITY = np.array([0.55, -0.35], dtype=np.float64)
RESET_REPEATS = 3


def _finite_values(values: np.ndarray, field: str) -> list[float]:
    array = np.asarray(values, dtype=np.float64)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{field} contains a non-finite compiled or measured value")
    return [float(value) for value in array.reshape(-1)]


def _enum_metadata(value: Any) -> dict[str, Any]:
    integer = int(value)
    return {"value": integer, "name": getattr(value, "name", str(value))}


def _model_metadata(model: mujoco.MjModel) -> dict[str, Any]:
    option = model.opt
    control_interval_s = float(option.timestep * FRAME_SKIP)
    option_fields = {
        "timestep_s": float(option.timestep),
        "integrator": _enum_metadata(option.integrator),
        "solver": _enum_metadata(option.solver),
        "tolerance": float(option.tolerance),
        "ls_tolerance": float(option.ls_tolerance),
        "noslip_tolerance": float(option.noslip_tolerance),
        "mpr_tolerance": float(option.mpr_tolerance),
        "iterations": int(option.iterations),
        "ls_iterations": int(option.ls_iterations),
        "noslip_iterations": int(option.noslip_iterations),
        "mpr_iterations": int(option.mpr_iterations),
    }
    bodies = []
    for body_id in range(model.nbody):
        body = model.body(body_id)
        bodies.append(
            {
                "id": body_id,
                "name": body.name,
                "mass_kg": float(model.body_mass[body_id]),
                "inertia_diagonal_kg_m2": _finite_values(
                    model.body_inertia[body_id], "body_inertia"
                ),
            }
        )

    joints = []
    for joint_id in range(model.njnt):
        joint = model.joint(joint_id)
        joints.append(
            {
                "id": joint_id,
                "name": joint.name,
                "type": _enum_metadata(model.jnt_type[joint_id]),
                "damping_Nm_s": float(model.jnt_damping[joint_id]),
                "armature_kg_m2": float(model.jnt_armature[joint_id]),
                "range_rad": _finite_values(model.jnt_range[joint_id], "joint_range"),
                "limited": bool(model.jnt_limited[joint_id]),
            }
        )

    actuators = []
    for actuator_id in range(model.nu):
        actuator = model.actuator(actuator_id)
        actuators.append(
            {
                "id": actuator_id,
                "name": actuator.name,
                "gear": _finite_values(
                    model.actuator_gear[actuator_id], "actuator_gear"
                ),
                "control_range": _finite_values(
                    model.actuator_ctrlrange[actuator_id], "actuator_ctrlrange"
                ),
                "force_range": _finite_values(
                    model.actuator_forcerange[actuator_id], "actuator_forcerange"
                ),
                "control_limited": bool(model.actuator_ctrllimited[actuator_id]),
                "force_limited": bool(model.actuator_forcelimited[actuator_id]),
            }
        )

    return {
        "xml_path": str(TWO_JOINT_ARM_XML_PATH),
        "nq": int(model.nq),
        "nv": int(model.nv),
        "nu": int(model.nu),
        "nbody": int(model.nbody),
        "njnt": int(model.njnt),
        "ngeom": int(model.ngeom),
        "nconmax": int(model.nconmax),
        "frame_skip": FRAME_SKIP,
        "control_interval_s": control_interval_s,
        "compiled_option": option_fields,
        "bodies": bodies,
        "joints": joints,
        "actuators": actuators,
        "force_fields_recorded": [
            "actuator_force",
            "qfrc_actuator",
            "qfrc_bias",
            "qfrc_passive",
            "qfrc_constraint",
        ],
    }


def _reset_to_state(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    qpos: Sequence[float],
    qvel: Sequence[float],
) -> None:
    qpos_array = np.asarray(qpos, dtype=np.float64)
    qvel_array = np.asarray(qvel, dtype=np.float64)
    if qpos_array.shape != (model.nq,):
        raise ValueError(f"qpos state must have shape {(model.nq,)}")
    if qvel_array.shape != (model.nv,):
        raise ValueError(f"qvel state must have shape {(model.nv,)}")
    mujoco.mj_resetData(model, data)
    data.qpos[:] = qpos_array
    data.qvel[:] = qvel_array
    data.ctrl[:] = 0.0
    mujoco.mj_forward(model, data)


def _command_array(command: Sequence[float], model: mujoco.MjModel) -> np.ndarray:
    result = np.asarray(command, dtype=np.float64)
    if result.shape != (model.nu,):
        raise ValueError(f"control command must have shape {(model.nu,)}")
    if not np.all(np.isfinite(result)):
        raise ValueError("control command contains a non-finite value")
    if np.any(result < -1.0) or np.any(result > 1.0):
        raise ValueError("controlled experiment command is outside [-1, 1]")
    return result


def _trace_record(
    data: mujoco.MjData,
    sequence: str,
    interval_index: int,
    held_command: np.ndarray,
) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "interval_index": interval_index,
        "input_command": _finite_values(held_command, "input_command"),
        "substeps": FRAME_SKIP,
        "qpos_rad": _finite_values(data.qpos, "qpos"),
        "qvel_rad_s": _finite_values(data.qvel, "qvel"),
        "qacc_rad_s2": _finite_values(data.qacc, "qacc"),
        "actuator_force": _finite_values(data.actuator_force, "actuator_force"),
        "qfrc_actuator_Nm": _finite_values(data.qfrc_actuator, "qfrc_actuator"),
        "qfrc_bias_Nm": _finite_values(data.qfrc_bias, "qfrc_bias"),
        "qfrc_passive_Nm": _finite_values(data.qfrc_passive, "qfrc_passive"),
        "qfrc_constraint_Nm": _finite_values(
            data.qfrc_constraint, "qfrc_constraint"
        ),
        "end_effector_position_m": _finite_values(
            data.site("end_effector").xpos, "end_effector_position"
        ),
        "contact_count": int(data.ncon),
    }


def _run_held_sequence(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    sequence: str,
    qpos: Sequence[float],
    qvel: Sequence[float],
    commands: Sequence[Sequence[float]],
) -> dict[str, Any]:
    _reset_to_state(model, data, qpos, qvel)
    trace = [
        _trace_record(
            data,
            sequence,
            interval_index=0,
            held_command=np.zeros(model.nu, dtype=np.float64),
        )
    ]
    for interval_index, command in enumerate(commands, start=1):
        held_command = _command_array(command, model)
        data.ctrl[:] = held_command
        for _ in range(FRAME_SKIP):
            mujoco.mj_step(model, data)
        trace.append(
            _trace_record(data, sequence, interval_index, held_command)
        )
    return {
        "label": sequence,
        "initial_qpos_rad": _finite_values(np.asarray(qpos), "initial_qpos"),
        "initial_qvel_rad_s": _finite_values(np.asarray(qvel), "initial_qvel"),
        "trace": trace,
    }


def _contact_summary(sequence_result: dict[str, Any]) -> dict[str, Any]:
    counts = [int(record["contact_count"]) for record in sequence_result["trace"]]
    return {
        "sequence": sequence_result["label"],
        "samples": len(counts),
        "maximum_contact_count": max(counts),
        "nonzero_contact_samples": sum(count > 0 for count in counts),
    }


def _reset_measurement(
    model: mujoco.MjModel, data: mujoco.MjData
) -> dict[str, Any]:
    trace = []
    for repeat in range(RESET_REPEATS):
        _reset_to_state(model, data, np.zeros(model.nq), np.zeros(model.nv))
        trace.append(
            _trace_record(
                data,
                "repeated_reset",
                interval_index=repeat,
                held_command=np.zeros(model.nu, dtype=np.float64),
            )
        )
    return {
        "label": "repeated_reset",
        "repeats": RESET_REPEATS,
        "expected_qpos_rad": [0.0] * model.nq,
        "expected_qvel_rad_s": [0.0] * model.nv,
        "trace": trace,
    }


def run_measurement() -> dict[str, Any]:
    """Run the bounded, deterministic plant measurement in memory."""
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    metadata = _model_metadata(model)
    qpos = SHOULDER_ELBOW_STATE.copy()
    zero_velocity = np.zeros(model.nv, dtype=np.float64)

    positive = _run_held_sequence(
        model, data, "isolated_positive_torque_step", qpos, zero_velocity,
        [[0.75, 0.0]] * 4
    )
    negative = _run_held_sequence(
        model, data, "isolated_negative_torque_step", qpos, zero_velocity,
        [[-0.75, 0.0]] * 4
    )
    reversal = _run_held_sequence(
        model, data, "torque_reversal", qpos, zero_velocity,
        [[0.65, 0.0], [0.65, 0.0], [-0.65, 0.0], [-0.65, 0.0], [-0.65, 0.0]]
    )
    free_decay = _run_held_sequence(
        model, data, "free_decay", [0.35, -0.45], FREE_DECAY_VELOCITY,
        [[0.0, 0.0]] * 8
    )
    resets = _reset_measurement(model, data)
    sequences = [positive, negative, reversal, free_decay, resets]

    initial_states = []
    for sequence in sequences:
        state = np.asarray(sequence["initial_qpos_rad"], dtype=np.float64)
        margins = np.minimum(
            state - model.jnt_range[:, 0], model.jnt_range[:, 1] - state
        )
        initial_states.append(
            {
                "sequence": sequence["label"],
                "qpos_rad": _finite_values(state, "initial_state_qpos"),
                "minimum_joint_limit_margin_rad": float(np.min(margins)),
                "abs_sin_elbow": float(abs(np.sin(state[1]))),
                "non_singular_planar_elbow": bool(abs(np.sin(state[1])) > 1e-12),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "measurement": "compiled_dynamics_measurement",
        "units": {
            "time": "s",
            "control_interval": "s",
            "joint_position": "rad",
            "joint_velocity": "rad/s",
            "joint_acceleration": "rad/s^2",
            "mass": "kg",
            "inertia": "kg m^2",
            "torque": "N m",
            "end_effector_position": "m",
            "control": "normalized motor command",
            "contact_count": "count",
        },
        "model": metadata,
        "experiment_design": {
            "deterministic": True,
            "fixed_initial_states": initial_states,
            "control_hold": {
                "frame_skip": FRAME_SKIP,
                "integration_substeps_per_update": FRAME_SKIP,
                "control_interval_s": metadata["control_interval_s"],
                "policy_update": "one command assignment followed by ten mj_step calls",
            },
            "joint_limit_policy": "all non-reset experiment states have reported positive margins",
        },
        "sequences": sequences,
        "contact_summary": [_contact_summary(sequence) for sequence in sequences],
    }


def write_measurement(artifact_path: Path) -> None:
    resolved_artifact_path = (
        artifact_path
        if artifact_path.is_absolute()
        else REPOSITORY_ROOT / artifact_path
    ).resolve()
    resolved_artifact_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_artifact_path.write_text(
        json.dumps(run_measurement(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Measure compiled two-joint MuJoCo dynamics."
    )
    parser.add_argument("--artifact", required=True, type=Path)
    args = parser.parse_args(argv)
    write_measurement(args.artifact)


if __name__ == "__main__":
    main()
