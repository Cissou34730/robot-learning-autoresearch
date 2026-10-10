"""Measure compiled MuJoCo properties and bounded sampled-data responses."""

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


FRAME_SKIP = 10
DRIVE_FRAMES = 25
COAST_FRAMES = 100


def _name(model: mujoco.MjModel, object_type: int, index: int) -> str:
    value = mujoco.mj_id2name(model, object_type, index)
    return value if value is not None else str(index)


def _reset(model: mujoco.MjModel, data: mujoco.MjData) -> None:
    mujoco.mj_resetData(model, data)
    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)


def _response(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    action: np.ndarray,
) -> dict:
    _reset(model, data)
    qpos_trace: list[list[float]] = []
    qvel_trace: list[list[float]] = []
    acceleration_trace: list[list[float]] = []
    for frame in range(DRIVE_FRAMES + COAST_FRAMES):
        data.ctrl[:] = action if frame < DRIVE_FRAMES else 0.0
        previous_qvel = data.qvel.copy()
        for _ in range(FRAME_SKIP):
            mujoco.mj_step(model, data)
        qpos_trace.append(data.qpos.copy().tolist())
        qvel_trace.append(data.qvel.copy().tolist())
        acceleration_trace.append(
            ((data.qvel - previous_qvel) / (model.opt.timestep * FRAME_SKIP)).tolist()
        )

    qpos = np.asarray(qpos_trace)
    qvel = np.asarray(qvel_trace)
    acceleration = np.asarray(acceleration_trace)
    coast_qvel = qvel[DRIVE_FRAMES:]
    settling_indices = np.flatnonzero(np.all(np.abs(coast_qvel) <= 0.01, axis=1))
    return {
        "action": action.tolist(),
        "drive_frames": DRIVE_FRAMES,
        "coast_frames": COAST_FRAMES,
        "peak_abs_velocity": float(np.max(np.abs(qvel))),
        "peak_abs_acceleration": float(np.max(np.abs(acceleration))),
        "drive_end_qpos": qpos[DRIVE_FRAMES - 1].tolist(),
        "peak_abs_qpos": np.max(np.abs(qpos), axis=0).tolist(),
        "coast_end_qpos": qpos[-1].tolist(),
        "coast_end_velocity": qvel[-1].tolist(),
        "settling_frame_after_drive": (
            int(settling_indices[0]) if settling_indices.size else None
        ),
    }


def _branch_probes(model: mujoco.MjModel, data: mujoco.MjData) -> list[dict]:
    probes: list[dict] = []
    for radius in (0.06, 0.13, 0.20):
        for angle in (0.0, np.pi / 2.0):
            cosine = (
                radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
            ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
            elbow_magnitude = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
            for branch in (-1, 1):
                q2 = branch * elbow_magnitude
                q1 = angle - np.arctan2(
                    FOREARM_LENGTH * np.sin(q2),
                    UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(q2),
                )
                _reset(model, data)
                data.qpos[:] = (q1, q2)
                mujoco.mj_forward(model, data)
                probes.append(
                    {
                        "radius_m": radius,
                        "angle_radians": angle,
                        "branch": "elbow_folded" if branch < 0 else "elbow_open",
                        "qpos": [float(q1), float(q2)],
                        "site_position": data.site("end_effector").xpos.tolist(),
                        "contact_count": int(data.ncon),
                        "joint_limit_flags": model.jnt_limited[:2].astype(bool).tolist(),
                    }
                )
    return probes


def measure() -> dict:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    return {
        "schema_version": 1,
        "measurement": "compiled_dynamics",
        "source_xml": str(TWO_JOINT_ARM_XML_PATH),
        "compiled_model": {
            "timestep_seconds": float(model.opt.timestep),
            "frame_skip": FRAME_SKIP,
            "control_interval_seconds": float(model.opt.timestep * FRAME_SKIP),
            "body_masses": {
                _name(model, mujoco.mjtObj.mjOBJ_BODY, index): float(model.body_mass[index])
                for index in range(model.nbody)
            },
            "body_inertias": {
                _name(model, mujoco.mjtObj.mjOBJ_BODY, index): model.body_inertia[
                    index
                ].tolist()
                for index in range(model.nbody)
            },
            "joints": [
                {
                    "name": _name(model, mujoco.mjtObj.mjOBJ_JOINT, index),
                    "limited": bool(model.jnt_limited[index]),
                    "range_radians": model.jnt_range[index].tolist(),
                    "damping": float(model.dof_damping[index]),
                    "armature": float(model.dof_armature[index]),
                }
                for index in range(model.njnt)
            ],
            "actuators": [
                {
                    "name": _name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, index),
                    "gear": model.actuator_gear[index].tolist(),
                    "ctrlrange": model.actuator_ctrlrange[index].tolist(),
                }
                for index in range(model.nu)
            ],
        },
        "step_responses": [
            _response(model, data, action)
            for action in (
                np.array((1.0, 0.0)),
                np.array((-1.0, 0.0)),
                np.array((0.0, 1.0)),
                np.array((0.0, -1.0)),
                np.array((1.0, 1.0)),
                np.array((1.0, -1.0)),
            )
        ],
        "branch_probes": _branch_probes(model, data),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(json.dumps(measure(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
