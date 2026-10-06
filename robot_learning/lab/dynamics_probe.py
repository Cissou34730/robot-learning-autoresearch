"""Measure compiled arm dynamics and short-horizon bounded-command response."""

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

FRAME_SKIP = 10
CONTROL_INTERVALS = 10
RADII_METERS = (0.06, 0.13, 0.20)
COMMANDS = (
    ("shoulder_positive", (1.0, 0.0)),
    ("shoulder_negative", (-1.0, 0.0)),
    ("elbow_positive", (0.0, 1.0)),
    ("elbow_negative", (0.0, -1.0)),
)


def inverse_kinematics(radius: float, elbow_sign: float) -> np.ndarray:
    cosine = (
        radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow = elbow_sign * float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    shoulder = -float(
        np.arctan2(
            FOREARM_LENGTH * np.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
        )
    )
    return np.array([shoulder, elbow], dtype=np.float64)


def forward_position(qpos: np.ndarray) -> np.ndarray:
    angle = qpos[0] + qpos[1]
    return np.array(
        [
            UPPER_ARM_LENGTH * np.cos(qpos[0])
            + FOREARM_LENGTH * np.cos(angle),
            UPPER_ARM_LENGTH * np.sin(qpos[0])
            + FOREARM_LENGTH * np.sin(angle),
            0.02,
        ],
        dtype=np.float64,
    )


def jacobian_singular_values(qpos: np.ndarray) -> list[float]:
    q1, q2 = qpos
    q12 = q1 + q2
    jacobian = np.array(
        [
            [
                -UPPER_ARM_LENGTH * np.sin(q1) - FOREARM_LENGTH * np.sin(q12),
                -FOREARM_LENGTH * np.sin(q12),
            ],
            [
                UPPER_ARM_LENGTH * np.cos(q1) + FOREARM_LENGTH * np.cos(q12),
                FOREARM_LENGTH * np.cos(q12),
            ],
        ]
    )
    return np.linalg.svd(jacobian, compute_uv=False).tolist()


def reset_state(model: mujoco.MjModel, data: mujoco.MjData, qpos: np.ndarray) -> None:
    mujoco.mj_resetData(model, data)
    data.qpos[:] = qpos
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)


def pulse_response(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    qpos: np.ndarray,
    command: tuple[float, float],
) -> dict:
    reset_state(model, data, qpos)
    initial_position = data.site("end_effector").xpos.copy()
    max_speed = 0.0
    max_displacement = 0.0
    speed_after_pulse = None
    displacement_after_pulse = None

    for interval in range(CONTROL_INTERVALS):
        data.ctrl[:] = command if interval == 0 else -np.asarray(command)
        for _ in range(FRAME_SKIP):
            mujoco.mj_step(model, data)
            max_speed = max(max_speed, float(np.linalg.norm(data.qvel)))
            displacement = float(
                np.linalg.norm(data.site("end_effector").xpos - initial_position)
            )
            max_displacement = max(max_displacement, displacement)
        if interval == 0:
            speed_after_pulse = float(np.linalg.norm(data.qvel))
            displacement_after_pulse = float(
                np.linalg.norm(data.site("end_effector").xpos - initial_position)
            )

    return {
        "command": list(command),
        "pulse_control_steps": 1,
        "brake_control_steps": CONTROL_INTERVALS - 1,
        "speed_after_pulse_rad_s": speed_after_pulse,
        "displacement_after_pulse_cm": 100.0 * displacement_after_pulse,
        "peak_joint_speed_rad_s": max_speed,
        "peak_end_effector_displacement_cm": 100.0 * max_displacement,
        "final_joint_speed_rad_s": float(np.linalg.norm(data.qvel)),
    }


def measure(output: Path) -> None:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    configurations = []

    for radius in RADII_METERS:
        for branch, elbow_sign in (("open", 1.0), ("folded", -1.0)):
            qpos = inverse_kinematics(radius, elbow_sign)
            limit_margins = np.pi * 170.0 / 180.0 - np.abs(qpos)
            configurations.append(
                {
                    "radius_cm": radius * 100.0,
                    "branch": branch,
                    "qpos_rad": qpos.tolist(),
                    "joint_limit_margin_deg": np.degrees(limit_margins).tolist(),
                    "jacobian_singular_values_m": jacobian_singular_values(qpos),
                    "pulse_responses": [
                        pulse_response(model, data, qpos, command)
                        for _, command in COMMANDS
                    ],
                }
            )

    result = {
        "schema_version": 1,
        "measurement": "compiled_dynamics_and_bounded_command_response",
        "model": {
            "timestep_s": float(model.opt.timestep),
            "frame_skip": FRAME_SKIP,
            "actuator_gear": model.actuator_gear[:, 0].tolist(),
            "body_mass_kg": model.body_mass.tolist(),
            "body_inertia_kg_m2": model.body_inertia.tolist(),
            "joint_damping": model.dof_damping.tolist(),
            "joint_armature": model.dof_armature.tolist(),
        },
        "control_interval_s": model.opt.timestep * FRAME_SKIP,
        "configurations": configurations,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    measure(args.output)


if __name__ == "__main__":
    main()
