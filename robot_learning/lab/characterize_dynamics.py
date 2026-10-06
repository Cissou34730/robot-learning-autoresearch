"""Measure compiled dynamics and bounded-torque response of the arm."""

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH

FRAME_SKIP = 10
PULSE_INTERVALS = 20
BRAKE_INTERVALS = 50


def _reset(model: mujoco.MjModel, data: mujoco.MjData, qpos: list[float]) -> None:
    mujoco.mj_resetData(model, data)
    data.qpos[:] = qpos
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)


def _json_array(values: np.ndarray) -> list:
    return np.asarray(values, dtype=float).tolist()


def _step_interval(
    model: mujoco.MjModel, data: mujoco.MjData, control: list[float]
) -> None:
    data.ctrl[:] = control
    for _ in range(FRAME_SKIP):
        mujoco.mj_step(model, data)


def _probe_impulses(model: mujoco.MjModel, data: mujoco.MjData) -> list[dict]:
    probes = []
    for qpos in ([0.0, 0.0], [0.6, -1.0], [-1.0, 1.4]):
        for control in ([1.0, 0.0], [0.0, 1.0], [1.0, 1.0]):
            _reset(model, data, list(qpos))
            data.ctrl[:] = control
            mujoco.mj_forward(model, data)
            initial_acceleration = data.qacc.copy()
            mujoco.mj_step(model, data)
            one_step_velocity = data.qvel.copy()
            _reset(model, data, list(qpos))
            _step_interval(model, data, list(control))
            probes.append(
                {
                    "initial_qpos_rad": list(qpos),
                    "control": list(control),
                    "initial_qacc_rad_s2": _json_array(initial_acceleration),
                    "qvel_after_one_sim_step_rad_s": _json_array(one_step_velocity),
                    "qvel_after_control_interval_rad_s": _json_array(data.qvel),
                }
            )
    return probes


def _pulse_response(model: mujoco.MjModel, data: mujoco.MjData) -> dict:
    _reset(model, data, [0.0, 0.0])
    velocity_trace = []
    for phase, control, intervals in (
        ("accelerate", [1.0, 1.0], PULSE_INTERVALS),
        ("brake", [-1.0, -1.0], BRAKE_INTERVALS),
    ):
        for interval in range(intervals):
            _step_interval(model, data, control)
            velocity_trace.append(
                {
                    "phase": phase,
                    "interval": interval + 1,
                    "qvel_rad_s": _json_array(data.qvel),
                    "qvel_norm_rad_s": float(np.linalg.norm(data.qvel)),
                }
            )

    acceleration_trace = velocity_trace[:PULSE_INTERVALS]
    peak_velocity = np.max(
        np.asarray([entry["qvel_rad_s"] for entry in acceleration_trace]), axis=0
    )
    brake_velocity = np.asarray(
        [entry["qvel_rad_s"] for entry in velocity_trace[PULSE_INTERVALS:]]
    )
    crossing_intervals = []
    for joint, peak in enumerate(peak_velocity):
        threshold = 0.1 * abs(float(peak))
        crossings = np.flatnonzero(np.abs(brake_velocity[:, joint]) <= threshold)
        crossing_intervals.append(
            None if crossings.size == 0 else int(crossings[0] + 1)
        )

    return {
        "initial_qpos_rad": [0.0, 0.0],
        "accelerating_control": [1.0, 1.0],
        "braking_control": [-1.0, -1.0],
        "pulse_intervals": PULSE_INTERVALS,
        "brake_intervals": BRAKE_INTERVALS,
        "peak_qvel_rad_s": _json_array(peak_velocity),
        "brake_crossing_intervals_to_10_percent": crossing_intervals,
        "control_interval_seconds": FRAME_SKIP * float(model.opt.timestep),
        "trace": velocity_trace,
    }


def characterize() -> dict:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    joint_names = ["shoulder", "elbow"]
    actuator_names = ["shoulder", "elbow"]
    return {
        "schema_version": 1,
        "measurement": "compiled_dynamics_and_bounded_torque_response",
        "model": {
            "timestep_seconds": float(model.opt.timestep),
            "nq": int(model.nq),
            "nv": int(model.nv),
            "nu": int(model.nu),
            "body_mass_kg": _json_array(model.body_mass),
            "body_inertia_kg_m2": _json_array(model.body_inertia),
            "joint_armature": _json_array(model.dof_armature),
            "joint_damping": _json_array(model.dof_damping),
            "actuator_gear": _json_array(model.actuator_gear[:, 0]),
            "actuator_ctrlrange": _json_array(model.actuator_ctrlrange),
            "joint_names": joint_names,
            "actuator_names": actuator_names,
        },
        "control_interval": {
            "simulator_steps": FRAME_SKIP,
            "seconds": FRAME_SKIP * float(model.opt.timestep),
            "nominal_control_range": [-1.0, 1.0],
        },
        "impulse_probes": _probe_impulses(model, data),
        "pulse_response": _pulse_response(model, data),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(
        json.dumps(characterize(), indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
