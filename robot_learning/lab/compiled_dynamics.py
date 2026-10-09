"""Measure the compiled arm dynamics relevant to reach-and-hold control."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH

FRAME_SKIP = 10
PULSE_INTERVALS = 10
RECOVERY_INTERVALS = 30
REVERSAL_INTERVALS = 15
POSTURE_SET = (
    np.array([0.0, 0.0], dtype=np.float64),
    np.array([0.8, -0.8], dtype=np.float64),
    np.array([-0.8, 0.8], dtype=np.float64),
)


def _array(values: np.ndarray) -> list:
    return np.asarray(values).tolist()


def _joint_names(model: mujoco.MjModel) -> list[str]:
    return [model.joint(index).name for index in range(model.njnt)]


def _body_names(model: mujoco.MjModel) -> list[str]:
    return [model.body(index).name for index in range(model.nbody)]


def _new_data(model: mujoco.MjModel, qpos: np.ndarray) -> mujoco.MjData:
    data = mujoco.MjData(model)
    data.qpos[:] = qpos
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)
    return data


def _run_controls(
    model: mujoco.MjModel,
    qpos: np.ndarray,
    controls: list[np.ndarray],
) -> dict:
    data = _new_data(model, qpos)
    control_dt = model.opt.timestep * FRAME_SKIP
    positions = [_array(data.qpos)]
    velocities = [_array(data.qvel)]
    accelerations: list[list[float]] = []
    for control in controls:
        data.ctrl[:] = control
        start_velocity = data.qvel.copy()
        for _ in range(FRAME_SKIP):
            mujoco.mj_step(model, data)
        positions.append(_array(data.qpos))
        velocities.append(_array(data.qvel))
        accelerations.append(_array((data.qvel - start_velocity) / control_dt))

    velocity_array = np.asarray(velocities, dtype=np.float64)
    acceleration_array = np.asarray(accelerations, dtype=np.float64)
    return {
        "control_dt_seconds": float(control_dt),
        "positions": positions,
        "velocities": velocities,
        "interval_accelerations": accelerations,
        "peak_abs_velocity": _array(np.max(np.abs(velocity_array), axis=0)),
        "peak_abs_acceleration": _array(np.max(np.abs(acceleration_array), axis=0)),
        "final_position": positions[-1],
        "final_velocity": velocities[-1],
    }


def _pulse_response(model: mujoco.MjModel, posture: np.ndarray, joint: int) -> dict:
    pulse = np.zeros(2, dtype=np.float64)
    pulse[joint] = 1.0
    controls = [pulse.copy() for _ in range(PULSE_INTERVALS)]
    controls.extend(
        np.zeros(2, dtype=np.float64) for _ in range(RECOVERY_INTERVALS)
    )
    result = _run_controls(model, posture, controls)
    result.update(
        {
            "type": "unit_pulse_and_coast",
            "initial_position": _array(posture),
            "excited_joint": joint,
            "pulse_intervals": PULSE_INTERVALS,
            "recovery_intervals": RECOVERY_INTERVALS,
        }
    )
    return result


def _reversal_response(model: mujoco.MjModel, posture: np.ndarray, joint: int) -> dict:
    positive = np.zeros(2, dtype=np.float64)
    positive[joint] = 1.0
    negative = -positive
    controls = [positive.copy() for _ in range(REVERSAL_INTERVALS)]
    controls.extend(negative.copy() for _ in range(REVERSAL_INTERVALS))
    result = _run_controls(model, posture, controls)
    velocities = np.asarray(result["velocities"], dtype=np.float64)[:, joint]
    reversal_index: int | None = None
    for index in range(REVERSAL_INTERVALS + 1, len(velocities)):
        if velocities[index] <= 0.0:
            reversal_index = index - REVERSAL_INTERVALS
            break
    result.update(
        {
            "type": "command_reversal",
            "initial_position": _array(posture),
            "excited_joint": joint,
            "positive_intervals": REVERSAL_INTERVALS,
            "negative_intervals": REVERSAL_INTERVALS,
            "reversal_intervals_after_command_switch": reversal_index,
        }
    )
    return result


def _limit_probe(model: mujoco.MjModel, joint: int, upper: bool) -> dict:
    qpos = np.zeros(2, dtype=np.float64)
    limit = float(model.jnt_range[joint, 1 if upper else 0])
    qpos[joint] = limit - (np.deg2rad(1.0) if upper else -np.deg2rad(1.0))
    control = np.zeros(2, dtype=np.float64)
    control[joint] = 1.0 if upper else -1.0
    result = _run_controls(
        model,
        qpos,
        [control.copy() for _ in range(RECOVERY_INTERVALS)],
    )
    data = _new_data(model, qpos)
    constraint_forces: list[list[float]] = []
    for _ in range(RECOVERY_INTERVALS):
        data.ctrl[:] = control
        for _ in range(FRAME_SKIP):
            mujoco.mj_step(model, data)
        constraint_forces.append(_array(data.qfrc_constraint))
    result.update(
        {
            "type": "joint_limit_probe",
            "joint": joint,
            "side": "upper" if upper else "lower",
            "declared_limit_radians": limit,
            "initial_position": _array(qpos),
            "constraint_forces": constraint_forces,
            "max_abs_constraint_force": _array(
                np.max(np.abs(np.asarray(constraint_forces)), axis=0)
            ),
        }
    )
    return result


def measure() -> dict:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    model_summary = {
        "timestep_seconds": float(model.opt.timestep),
        "frame_skip": FRAME_SKIP,
        "control_period_seconds": float(model.opt.timestep * FRAME_SKIP),
        "nq": int(model.nq),
        "nv": int(model.nv),
        "nu": int(model.nu),
        "joint_names": _joint_names(model),
        "joint_ranges_radians": _array(model.jnt_range),
        "joint_limited": _array(model.jnt_limited),
        "dof_damping": _array(model.dof_damping),
        "dof_armature": _array(model.dof_armature),
        "body_names": _body_names(model),
        "body_masses": _array(model.body_mass),
        "body_inertias": _array(model.body_inertia),
        "actuator_gear": _array(model.actuator_gear),
        "actuator_ctrlrange": _array(model.actuator_ctrlrange),
        "actuator_ctrl_limited": _array(model.actuator_ctrllimited),
        "actuator_gain_parameters": _array(model.actuator_gainprm),
        "actuator_bias_parameters": _array(model.actuator_biasprm),
    }

    responses = []
    for posture in POSTURE_SET:
        for joint in range(2):
            responses.append(_pulse_response(model, posture, joint))
            responses.append(_reversal_response(model, posture, joint))

    limit_probes = [
        _limit_probe(model, joint, upper)
        for joint in range(2)
        for upper in (False, True)
    ]
    return {
        "schema_version": 1,
        "measurement": "compiled_dynamics_and_limits",
        "model_source": str(TWO_JOINT_ARM_XML_PATH),
        "compiled_model": model_summary,
        "responses": responses,
        "limit_probes": limit_probes,
        "interpretation_scope": {
            "supports": [
                "compiled inertial and actuator parameter inspection",
                "action-to-acceleration authority",
                "braking and reversal timing",
                "joint-limit reaction detection",
            ],
            "does_not_support": [
                "learned-policy performance",
                "official task success",
                "target-distribution coverage",
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    artifact = measure()
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
