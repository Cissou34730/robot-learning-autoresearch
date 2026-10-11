"""Measure compiled MuJoCo dynamics and short-horizon actuator responses."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH


FRAME_SKIP = 10
REPRESENTATIVE_ELBOW_ANGLES = (0.0, -np.pi / 2, np.pi / 2, -2.4, 2.4)
IMPULSE_ACTIONS = (
    (1.0, 0.0),
    (-1.0, 0.0),
    (0.0, 1.0),
    (0.0, -1.0),
    (1.0, 1.0),
)


def _rounded(values: np.ndarray | list[float], digits: int = 10) -> list[float]:
    return [float(value) for value in np.round(np.asarray(values), digits)]


def _mass_matrix(model: mujoco.MjModel, data: mujoco.MjData) -> list[list[float]]:
    full_mass = np.zeros((model.nv, model.nv), dtype=np.float64)
    mujoco.mj_fullM(model, full_mass, data.qM)
    return np.round(full_mass, 10).tolist()


def _compile_summary(model: mujoco.MjModel, data: mujoco.MjData) -> dict:
    joint_ids = [model.joint("shoulder").id, model.joint("elbow").id]
    body_ids = [model.body("upper_arm").id, model.body("forearm").id]
    mass_matrices = []
    for elbow_angle in REPRESENTATIVE_ELBOW_ANGLES:
        data.qpos[:] = [0.0, elbow_angle]
        data.qvel[:] = 0.0
        mujoco.mj_forward(model, data)
        mass_matrices.append(
            {
                "q1_rad": 0.0,
                "q2_rad": float(elbow_angle),
                "mass_matrix": _mass_matrix(model, data),
            }
        )

    return {
        "timestep_s": float(model.opt.timestep),
        "frame_skip": FRAME_SKIP,
        "control_period_s": float(model.opt.timestep * FRAME_SKIP),
        "nq": int(model.nq),
        "nv": int(model.nv),
        "joint_names": ["shoulder", "elbow"],
        "joint_range_rad": np.asarray(model.jnt_range[joint_ids]).round(10).tolist(),
        "joint_limited": [bool(model.jnt_limited[joint_id]) for joint_id in joint_ids],
        "joint_damping": _rounded(model.dof_damping[:2]),
        "joint_armature": _rounded(model.dof_armature[:2]),
        "body_names": ["upper_arm", "forearm"],
        "body_mass_kg": _rounded(model.body_mass[body_ids]),
        "body_inertia_kg_m2": np.asarray(model.body_inertia[body_ids])
        .round(10)
        .tolist(),
        "actuator_ctrlrange": np.asarray(model.actuator_ctrlrange[:2])
        .round(10)
        .tolist(),
        "actuator_gear": np.asarray(model.actuator_gear[:2])
        .round(10)
        .tolist(),
        "mass_matrix_by_configuration": mass_matrices,
    }


def _response_trial(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    elbow_angle: float,
    action: tuple[float, float],
    recovery_control_steps: int,
) -> dict:
    data.qpos[:] = [0.0, elbow_angle]
    data.qvel[:] = 0.0
    data.ctrl[:] = 0.0
    mujoco.mj_forward(model, data)

    initial_site = data.site("end_effector").xpos.copy()
    trace: list[dict] = []
    previous_site = initial_site
    for control_step in range(recovery_control_steps + 1):
        applied_action = np.asarray(action if control_step == 0 else (0.0, 0.0))
        data.ctrl[:] = applied_action
        for _ in range(FRAME_SKIP):
            mujoco.mj_step(model, data)
        site_position = data.site("end_effector").xpos.copy()
        site_velocity = (site_position - previous_site) / (
            model.opt.timestep * FRAME_SKIP
        )
        previous_site = site_position
        trace.append(
            {
                "control_step": control_step + 1,
                "action": _rounded(applied_action),
                "qpos_rad": _rounded(data.qpos[:2]),
                "qvel_rad_s": _rounded(data.qvel[:2]),
                "site_position_m": _rounded(site_position),
                "site_velocity_m_s": _rounded(site_velocity),
            }
        )

    qvel = np.asarray([row["qvel_rad_s"] for row in trace])
    site_speed = np.linalg.norm(
        np.asarray([row["site_velocity_m_s"] for row in trace]), axis=1
    )
    return {
        "q1_rad": 0.0,
        "q2_rad": float(elbow_angle),
        "action": _rounded(action),
        "commanded_torque": _rounded(
            np.asarray(action) * model.actuator_gear[:2, 0]
        ),
        "saturated_action_components": [
            bool(abs(value) >= 1.0) for value in action
        ],
        "max_abs_qvel_rad_s": _rounded(np.max(np.abs(qvel), axis=0)),
        "max_site_speed_m_s": float(np.max(site_speed)),
        "final_qpos_rad": _rounded(data.qpos[:2]),
        "final_qvel_rad_s": _rounded(data.qvel[:2]),
        "trace": trace,
    }


def measure(artifact_path: Path, recovery_control_steps: int) -> None:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    responses = [
        _response_trial(
            model, data, elbow_angle, action, recovery_control_steps
        )
        for elbow_angle in REPRESENTATIVE_ELBOW_ANGLES
        for action in IMPULSE_ACTIONS
    ]
    artifact = {
        "schema_version": 1,
        "measurement": "compiled_dynamics",
        "robot_xml": str(TWO_JOINT_ARM_XML_PATH),
        "compiled_model": _compile_summary(model, data),
        "response_protocol": {
            "initial_qvel_rad_s": [0.0, 0.0],
            "impulse_control_periods": 1,
            "recovery_control_periods": recovery_control_steps,
            "action_space": "clipped to [-1, 1] before actuator application",
        },
        "responses": responses,
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--recovery-control-steps", type=int, default=20)
    args = parser.parse_args()
    if args.recovery_control_steps < 1:
        raise ValueError("--recovery-control-steps must be positive")
    measure(args.artifact, args.recovery_control_steps)


if __name__ == "__main__":
    main()
