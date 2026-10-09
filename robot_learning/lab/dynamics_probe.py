"""Measure compiled arm dynamics and bounded control response."""

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH


FRAME_SKIP = 10
DRIVE_CONTROL_STEPS = 10
BRAKE_CONTROL_STEPS = 10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    return parser.parse_args()


def reset_state(model: mujoco.MjModel, data: mujoco.MjData, qpos: np.ndarray) -> None:
    mujoco.mj_resetData(model, data)
    data.qpos[:] = qpos
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)


def run_trial(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    start_qpos: np.ndarray,
    drive_action: np.ndarray,
) -> dict:
    reset_state(model, data, start_qpos)
    data.ctrl[:] = drive_action
    mujoco.mj_forward(model, data)
    initial_qacc = data.qacc.copy()
    response: list[dict] = []
    for phase, action, count in (
        ("drive", drive_action, DRIVE_CONTROL_STEPS),
        ("brake", -drive_action, BRAKE_CONTROL_STEPS),
    ):
        data.ctrl[:] = action
        for control_step in range(count):
            for _ in range(FRAME_SKIP):
                mujoco.mj_step(model, data)
            response.append(
                {
                    "phase": phase,
                    "control_step": control_step + 1,
                    "qpos": data.qpos.copy().tolist(),
                    "qvel": data.qvel.copy().tolist(),
                    "qacc": data.qacc.copy().tolist(),
                }
            )

    drive_rows = response[:DRIVE_CONTROL_STEPS]
    brake_rows = response[DRIVE_CONTROL_STEPS:]
    drive_speeds = np.asarray([row["qvel"] for row in drive_rows], dtype=np.float64)
    brake_speeds = np.asarray([row["qvel"] for row in brake_rows], dtype=np.float64)
    return {
        "start_qpos": start_qpos.tolist(),
        "drive_action": drive_action.tolist(),
        "brake_action": (-drive_action).tolist(),
        "initial_qacc": initial_qacc.tolist(),
        "peak_abs_joint_speed_drive": np.max(np.abs(drive_speeds), axis=0).tolist(),
        "speed_after_drive": drive_speeds[-1].tolist(),
        "speed_after_brake": brake_speeds[-1].tolist(),
        "response": response,
    }


def collect_measurement() -> dict:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    start_states = np.asarray(
        [[0.0, 0.0], [0.0, 1.0], [0.0, -1.0], [np.pi / 2.0, 0.0]],
        dtype=np.float64,
    )
    actions = np.asarray(
        [[1.0, 0.0], [-1.0, 0.0], [0.0, 1.0], [0.0, -1.0], [1.0, 1.0], [1.0, -1.0]],
        dtype=np.float64,
    )
    trials = [
        run_trial(model, data, start_qpos, action)
        for start_qpos in start_states
        for action in actions
    ]
    return {
        "schema_version": 1,
        "experiment": "compiled_dynamics_and_control_response",
        "measurement_semantics": {
            "integration_timestep_seconds": float(model.opt.timestep),
            "control_interval_steps": FRAME_SKIP,
            "control_interval_seconds": float(model.opt.timestep * FRAME_SKIP),
            "drive_control_steps": DRIVE_CONTROL_STEPS,
            "brake_control_steps": BRAKE_CONTROL_STEPS,
        },
        "compiled_model": {
            "nq": int(model.nq),
            "nv": int(model.nv),
            "nu": int(model.nu),
            "body_mass": model.body_mass.tolist(),
            "body_inertia": model.body_inertia.tolist(),
            "dof_armature": model.dof_armature.tolist(),
            "dof_damping": model.dof_damping.tolist(),
            "actuator_gear": model.actuator_gear.tolist(),
            "actuator_ctrlrange": model.actuator_ctrlrange.tolist(),
            "joint_range": model.jnt_range.tolist(),
        },
        "trials": trials,
    }


def main() -> None:
    args = parse_args()
    artifact = collect_measurement()
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(json.dumps(artifact, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
