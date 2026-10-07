"""Characterize the compiled arm dynamics at the policy control rate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import TWO_JOINT_ARM_XML_PATH
from contracts.task_spec import FRAME_SKIP


TARGET_RADII = (0.06, 0.13, 0.20)
BRANCH_SIGNS = (-1, 1)
CONTROL_STEPS = 150
IMPULSE_STEPS = 1
ACTIVE_STEP_STEPS = 25
VELOCITY_SETTLING_THRESHOLD = 0.02


def inverse_kinematics(radius: float, branch_sign: int) -> np.ndarray:
    cosine = (radius**2 - 0.12**2 - 0.10**2) / (2.0 * 0.12 * 0.10)
    q2 = branch_sign * np.arccos(np.clip(cosine, -1.0, 1.0))
    q1 = -np.arctan2(0.10 * np.sin(q2), 0.12 + 0.10 * np.cos(q2))
    return np.array([q1, q2], dtype=np.float64)


def full_mass_matrix(model: mujoco.MjModel, data: mujoco.MjData) -> np.ndarray:
    matrix = np.zeros((model.nv, model.nv), dtype=np.float64)
    mujoco.mj_fullM(model, matrix, data.qM)
    return matrix


def set_configuration(
    model: mujoco.MjModel, data: mujoco.MjData, qpos: np.ndarray
) -> None:
    mujoco.mj_resetData(model, data)
    data.qpos[:2] = qpos
    data.qvel[:2] = 0.0
    mujoco.mj_forward(model, data)


def actuator_response(
    model: mujoco.MjModel, data: mujoco.MjData, control: np.ndarray
) -> dict:
    data.ctrl[:] = control
    mujoco.mj_forward(model, data)
    return {
        "control": control.tolist(),
        "actuator_joint_torque": data.qfrc_actuator[:2].tolist(),
        "joint_acceleration": data.qacc[:2].tolist(),
    }


def step_response(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    qpos: np.ndarray,
    axis: int,
) -> dict:
    set_configuration(model, data, qpos)
    initial_position = data.qpos[:2].copy()
    peak_joint_speed = 0.0
    peak_end_effector_speed = 0.0
    peak_position_change = 0.0
    velocity_below_threshold_step: int | None = None
    samples: list[dict] = []

    for control_step in range(CONTROL_STEPS):
        control = np.zeros(2, dtype=np.float64)
        if control_step < ACTIVE_STEP_STEPS:
            control[axis] = 1.0
        for _ in range(FRAME_SKIP):
            data.ctrl[:] = control
            mujoco.mj_step(model, data)
            joint_speed = float(np.linalg.norm(data.qvel[:2]))
            end_effector_speed = float(np.linalg.norm(data.site_xvelp[0]))
            peak_joint_speed = max(peak_joint_speed, joint_speed)
            peak_end_effector_speed = max(peak_end_effector_speed, end_effector_speed)
            peak_position_change = max(
                peak_position_change,
                float(np.linalg.norm(data.qpos[:2] - initial_position)),
            )
        if (
            control_step >= ACTIVE_STEP_STEPS
            and velocity_below_threshold_step is None
            and float(np.linalg.norm(data.qvel[:2])) <= VELOCITY_SETTLING_THRESHOLD
        ):
            velocity_below_threshold_step = control_step + 1
        if control_step in (0, IMPULSE_STEPS - 1, ACTIVE_STEP_STEPS - 1, CONTROL_STEPS - 1):
            samples.append(
                {
                    "control_step": control_step + 1,
                    "joint_position": data.qpos[:2].tolist(),
                    "joint_velocity": data.qvel[:2].tolist(),
                    "end_effector_speed": float(np.linalg.norm(data.site_xvelp[0])),
                }
            )

    return {
        "axis": axis,
        "command": "positive_unit_control",
        "control_dt_seconds": model.opt.timestep * FRAME_SKIP,
        "active_control_steps": ACTIVE_STEP_STEPS,
        "total_control_steps": CONTROL_STEPS,
        "peak_joint_speed": peak_joint_speed,
        "peak_end_effector_speed": peak_end_effector_speed,
        "peak_joint_position_change": peak_position_change,
        "velocity_below_threshold_step_after_release": velocity_below_threshold_step,
        "samples": samples,
    }


def impulse_response(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    qpos: np.ndarray,
    axis: int,
) -> dict:
    set_configuration(model, data, qpos)
    initial_position = data.qpos[:2].copy()
    initial_end_effector_position = data.site_xpos[0].copy()
    peak_joint_speed = 0.0
    max_joint_displacement = 0.0
    max_end_effector_displacement = 0.0

    for control_step in range(CONTROL_STEPS):
        control = np.zeros(2, dtype=np.float64)
        if control_step < IMPULSE_STEPS:
            control[axis] = 1.0
        for _ in range(FRAME_SKIP):
            data.ctrl[:] = control
            mujoco.mj_step(model, data)
            peak_joint_speed = max(peak_joint_speed, float(np.linalg.norm(data.qvel[:2])))
            max_end_effector_displacement = max(
                max_end_effector_displacement,
                float(np.linalg.norm(data.site_xpos[0] - initial_end_effector_position)),
            )
        joint_displacement = float(np.linalg.norm(data.qpos[:2] - initial_position))
        max_joint_displacement = max(max_joint_displacement, joint_displacement)

    return {
        "axis": axis,
        "command": "one_control_step_positive_unit_impulse",
        "control_dt_seconds": model.opt.timestep * FRAME_SKIP,
        "total_control_steps": CONTROL_STEPS,
        "peak_joint_speed": peak_joint_speed,
        "max_joint_displacement": max_joint_displacement,
        "max_end_effector_displacement": max_end_effector_displacement,
    }


def characterize(artifact_path: Path) -> None:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "end_effector")

    configurations: list[dict] = []
    for radius in TARGET_RADII:
        for branch_sign in BRANCH_SIGNS:
            qpos = inverse_kinematics(radius, branch_sign)
            set_configuration(model, data, qpos)
            actuator_responses = [
                actuator_response(model, data, control)
                for control in (
                    np.array([1.0, 0.0]),
                    np.array([0.0, 1.0]),
                )
            ]
            configurations.append(
                {
                    "target_radius_m": radius,
                    "branch_sign": branch_sign,
                    "joint_configuration_rad": qpos.tolist(),
                    "end_effector_position_m": data.site_xpos[site_id].tolist(),
                    "mass_matrix": full_mass_matrix(model, data).tolist(),
                    "actuator_responses": actuator_responses,
                    "step_responses": [
                        step_response(model, data, qpos, axis) for axis in range(2)
                    ],
                    "impulse_responses": [
                        impulse_response(model, data, qpos, axis) for axis in range(2)
                    ],
                }
            )

    artifact = {
        "schema_version": 1,
        "measurement": "compiled_dynamics_and_control_rate_response",
        "model": str(TWO_JOINT_ARM_XML_PATH),
        "control_dt_seconds": model.opt.timestep * FRAME_SKIP,
        "frame_skip": FRAME_SKIP,
        "compiled_model": {
            "nq": model.nq,
            "nv": model.nv,
            "nbody": model.nbody,
            "body_mass": model.body_mass.tolist(),
            "body_inertia": model.body_inertia.tolist(),
            "dof_damping": model.dof_damping.tolist(),
            "dof_armature": model.dof_armature.tolist(),
            "actuator_gear": model.actuator_gear.tolist(),
            "actuator_ctrlrange": model.actuator_ctrlrange.tolist(),
        },
        "configurations": configurations,
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    characterize(args.artifact)


if __name__ == "__main__":
    main()
