"""Characterize compiled actuation and short-horizon joint response."""

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

RADIUS_CM = (6.0, 10.0, 14.0, 18.0, 20.0)
ANGLES_DEGREES = (-180.0, -90.0, 0.0, 90.0, 180.0)
SWEEP_ACTIONS = (
    (0.0, 0.0),
    (1.0, 0.0),
    (-1.0, 0.0),
    (0.0, 1.0),
    (0.0, -1.0),
    (1.0, 1.0),
    (-1.0, -1.0),
)
FRAME_SKIP = 10


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _ik_configuration(radius_m: float, angle_rad: float, elbow: float) -> np.ndarray:
    shoulder_offset = np.arctan2(
        FOREARM_LENGTH * np.sin(elbow),
        UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
    )
    shoulder = _wrap_to_pi(angle_rad - shoulder_offset)
    return np.asarray([shoulder, elbow], dtype=np.float64)


def _reset_configuration(
    model: mujoco.MjModel, data: mujoco.MjData, qpos: np.ndarray
) -> None:
    mujoco.mj_resetData(model, data)
    data.qpos[:2] = qpos
    data.qvel[:2] = 0.0
    mujoco.mj_forward(model, data)


def _model_snapshot(model: mujoco.MjModel) -> dict:
    return {
        "xml_path": str(TWO_JOINT_ARM_XML_PATH),
        "timestep_s": float(model.opt.timestep),
        "integrator": int(model.opt.integrator),
        "solver": int(model.opt.solver),
        "iterations": int(model.opt.iterations),
        "body_mass_kg": np.asarray(model.body_mass, dtype=np.float64).tolist(),
        "body_inertia_kg_m2": np.asarray(model.body_inertia, dtype=np.float64).tolist(),
        "dof_armature_kg_m2": np.asarray(model.dof_armature, dtype=np.float64).tolist(),
        "dof_damping": np.asarray(model.dof_damping, dtype=np.float64).tolist(),
        "actuator_ctrlrange": np.asarray(
            model.actuator_ctrlrange, dtype=np.float64
        ).tolist(),
        "actuator_gear": np.asarray(model.actuator_gear, dtype=np.float64).tolist(),
        "joint_range_rad": np.asarray(model.jnt_range, dtype=np.float64).tolist(),
    }


def characterize() -> dict:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    responses: list[dict] = []

    for radius_cm in RADIUS_CM:
        radius_m = radius_cm / 100.0
        elbow_magnitude = float(
            np.arccos(
                np.clip(
                    (
                        radius_m**2
                        - UPPER_ARM_LENGTH**2
                        - FOREARM_LENGTH**2
                    )
                    / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH),
                    -1.0,
                    1.0,
                )
            )
        )
        for angle_degrees in ANGLES_DEGREES:
            angle_rad = float(np.radians(angle_degrees))
            for branch, elbow in (
                ("open", elbow_magnitude),
                ("folded", -elbow_magnitude),
            ):
                qpos = _ik_configuration(radius_m, angle_rad, elbow)
                for action_values in SWEEP_ACTIONS:
                    action = np.asarray(action_values, dtype=np.float64)
                    _reset_configuration(model, data, qpos)
                    data.ctrl[:2] = action
                    mujoco.mj_forward(model, data)
                    initial_qacc = np.asarray(data.qacc[:2], dtype=np.float64).copy()
                    initial_actuator_force = np.asarray(
                        data.actuator_force[:2], dtype=np.float64
                    ).copy()
                    initial_actuator_torque = np.asarray(
                        data.qfrc_actuator[:2], dtype=np.float64
                    ).copy()
                    for _ in range(FRAME_SKIP):
                        mujoco.mj_step(model, data)
                    responses.append(
                        {
                            "radius_cm": radius_cm,
                            "angle_degrees": angle_degrees,
                            "branch": branch,
                            "qpos_rad": qpos.tolist(),
                            "action": action.tolist(),
                            "initial_qacc_rad_per_s2": initial_qacc.tolist(),
                            "initial_actuator_force": initial_actuator_force.tolist(),
                            "initial_actuator_torque": initial_actuator_torque.tolist(),
                            "qpos_delta_20ms_rad": (
                                np.asarray(data.qpos[:2], dtype=np.float64) - qpos
                            ).tolist(),
                            "qvel_after_20ms_rad_per_s": np.asarray(
                                data.qvel[:2], dtype=np.float64
                            ).tolist(),
                            "qacc_after_20ms_rad_per_s2": np.asarray(
                                data.qacc[:2], dtype=np.float64
                            ).tolist(),
                        }
                    )

    return {
        "schema_version": 1,
        "measurement": "compiled_actuation_response",
        "control_interval_s": float(model.opt.timestep * FRAME_SKIP),
        "model": _model_snapshot(model),
        "design": {
            "radii_cm": list(RADIUS_CM),
            "angles_degrees": list(ANGLES_DEGREES),
            "branches": ["open", "folded"],
            "actions": [list(action) for action in SWEEP_ACTIONS],
            "frame_skip": FRAME_SKIP,
        },
        "responses": responses,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    artifact = characterize()
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
