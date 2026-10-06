"""Mechanistic startup measurements for the two-joint reach-and-hold task."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import (
    FOREARM_LENGTH,
    TWO_JOINT_ARM_XML_PATH,
    UPPER_ARM_LENGTH,
)

JOINT_LIMIT = np.deg2rad(170.0)
FRAME_SKIP = 10
RADII_M = (0.06, 0.13, 0.20)
ANGLES_DEG = (0.0, 90.0, 180.0)
CONTROL_ACTIONS = (
    (0.0, 0.0),
    (1.0, 0.0),
    (-1.0, 0.0),
    (0.0, 1.0),
    (0.0, -1.0),
)


def wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def inverse_kinematics(radius: float, angle: float, elbow_sign: float) -> tuple[float, float]:
    cosine = (
        radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow = elbow_sign * float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    shoulder = angle - np.arctan2(
        FOREARM_LENGTH * np.sin(elbow),
        UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
    )
    return wrap_to_pi(float(shoulder)), elbow


def planar_jacobian(q: tuple[float, float]) -> np.ndarray:
    shoulder, elbow = q
    distal = shoulder + elbow
    return np.array(
        [
            [
                -UPPER_ARM_LENGTH * np.sin(shoulder)
                - FOREARM_LENGTH * np.sin(distal),
                -FOREARM_LENGTH * np.sin(distal),
            ],
            [
                UPPER_ARM_LENGTH * np.cos(shoulder)
                + FOREARM_LENGTH * np.cos(distal),
                FOREARM_LENGTH * np.cos(distal),
            ],
        ],
        dtype=np.float64,
    )


def target_position(radius: float, angle_deg: float) -> np.ndarray:
    angle = np.deg2rad(angle_deg)
    return np.array(
        [radius * np.cos(angle), radius * np.sin(angle), 0.02],
        dtype=np.float64,
    )


def make_ik_records() -> list[dict]:
    records: list[dict] = []
    for radius in RADII_M:
        for angle_deg in ANGLES_DEG:
            angle = np.deg2rad(angle_deg)
            for branch, elbow_sign in (("open", 1.0), ("folded", -1.0)):
                q = inverse_kinematics(radius, angle, elbow_sign)
                jacobian = planar_jacobian(q)
                singular_values = np.linalg.svd(jacobian, compute_uv=False)
                valid = bool(np.all(np.abs(q) <= JOINT_LIMIT + 1e-12))
                records.append(
                    {
                        "radius_cm": radius * 100.0,
                        "angle_deg": angle_deg,
                        "branch": branch,
                        "q_deg": [float(np.rad2deg(value)) for value in q],
                        "valid": valid,
                        "joint_limit_margin_deg": float(
                            np.rad2deg(JOINT_LIMIT - max(np.abs(q)))
                        ),
                        "jacobian_singular_values": [
                            float(value) for value in singular_values
                        ],
                        "jacobian_condition_number": float(
                            singular_values[0] / singular_values[-1]
                        ),
                    }
                )
    return records


def load_mass_matrix(model: mujoco.MjModel, data: mujoco.MjData) -> np.ndarray:
    mass_matrix = np.zeros((model.nv, model.nv), dtype=np.float64)
    mujoco.mj_fullM(model, mass_matrix.ravel(), data.M)
    return mass_matrix


def run_response_trial(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    q: tuple[float, float],
    target: np.ndarray,
    action: tuple[float, float],
) -> dict:
    mujoco.mj_resetData(model, data)
    data.qpos[:] = q
    data.qvel[:] = 0.0
    data.mocap_pos[0] = target
    mujoco.mj_forward(model, data)
    mass_eigenvalues = np.linalg.eigvalsh(load_mass_matrix(model, data))

    distances = []
    qacc_norms = []
    qvel_norms = []
    actuator_torque_norms = []
    data.ctrl[:] = action
    for _ in range(FRAME_SKIP):
        mujoco.mj_step(model, data)
        distances.append(
            float(np.linalg.norm(data.site("end_effector").xpos - target))
        )
        qacc_norms.append(float(np.linalg.norm(data.qacc)))
        qvel_norms.append(float(np.linalg.norm(data.qvel)))
        actuator_torque_norms.append(float(np.linalg.norm(data.qfrc_actuator)))

    return {
        "action": list(action),
        "mass_eigenvalues": [float(value) for value in mass_eigenvalues],
        "max_distance_mm": 1000.0 * max(distances),
        "final_distance_mm": 1000.0 * distances[-1],
        "max_qacc": max(qacc_norms),
        "max_qvel": max(qvel_norms),
        "max_actuator_torque": max(actuator_torque_norms),
        "final_q_deg": [float(np.rad2deg(value)) for value in data.qpos],
    }


def make_response_records(
    model: mujoco.MjModel, data: mujoco.MjData
) -> list[dict]:
    records: list[dict] = []
    for radius in RADII_M:
        for angle_deg in ANGLES_DEG:
            target = target_position(radius, angle_deg)
            angle = np.deg2rad(angle_deg)
            for branch, elbow_sign in (("open", 1.0), ("folded", -1.0)):
                q = inverse_kinematics(radius, angle, elbow_sign)
                for action in CONTROL_ACTIONS:
                    trial = run_response_trial(model, data, q, target, action)
                    records.append(
                        {
                            "radius_cm": radius * 100.0,
                            "angle_deg": angle_deg,
                            "branch": branch,
                            "q_deg": [float(np.rad2deg(value)) for value in q],
                            **trial,
                        }
                    )
    return records


def build_artifact() -> dict:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    ik_records = make_ik_records()
    response_records = make_response_records(model, data)
    valid_records = [record for record in ik_records if record["valid"]]
    return {
        "schema_version": 1,
        "measurement": "startup_ik_and_dynamics",
        "model": {
            "timestep_s": float(model.opt.timestep),
            "frame_skip": FRAME_SKIP,
            "joint_limits_deg": [-170.0, 170.0],
            "control_range": [-1.0, 1.0],
            "motor_gear": [float(value) for value in model.actuator_gear[:, 0]],
        },
        "ik_sweep": {
            "radii_cm": [radius * 100.0 for radius in RADII_M],
            "angles_deg": list(ANGLES_DEG),
            "records": ik_records,
            "valid_branch_records": len(valid_records),
            "total_branch_records": len(ik_records),
        },
        "action_response": {
            "actions": [list(action) for action in CONTROL_ACTIONS],
            "records": response_records,
            "units": {
                "distance": "mm",
                "q": "degrees",
                "qacc": "rad/s^2",
                "qvel": "rad/s",
                "torque": "model torque units",
            },
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(build_artifact(), indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
