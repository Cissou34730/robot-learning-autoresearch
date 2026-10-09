"""Characterize compiled arm dynamics and kinematic feasibility."""

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


def _array(values: np.ndarray) -> list:
    return np.asarray(values).tolist()


def _name(model: mujoco.MjModel, object_type: int, index: int) -> str:
    return mujoco.mj_id2name(model, object_type, index) or str(index)


def _reset(model: mujoco.MjModel, data: mujoco.MjData, qpos: list[float]) -> None:
    mujoco.mj_resetData(model, data)
    data.qpos[:2] = qpos
    data.qvel[:2] = 0.0
    mujoco.mj_forward(model, data)


def _snapshot(model: mujoco.MjModel, data: mujoco.MjData) -> dict:
    return {
        "qpos_rad": _array(data.qpos[:2]),
        "qvel_rad_per_s": _array(data.qvel[:2]),
        "qacc_rad_per_s2": _array(data.qacc[:2]),
        "qfrc_actuator": _array(data.qfrc_actuator[:2]),
        "end_effector_m": _array(data.site("end_effector").xpos),
    }


def _probe_response(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    posture_name: str,
    qpos: list[float],
    action: list[float],
    *,
    intervals: int = 25,
) -> dict:
    _reset(model, data, qpos)
    data.ctrl[:] = action
    mujoco.mj_forward(model, data)
    applied_force = _array(data.qfrc_actuator[:2])
    initial_state = _snapshot(model, data)
    trace: list[dict] = []

    for interval in range(intervals):
        if interval == 1:
            data.ctrl[:] = 0.0
        first_substep_acceleration: list[float] | None = None
        max_abs_velocity = np.zeros(2, dtype=np.float64)
        for _ in range(10):
            mujoco.mj_step(model, data)
            if first_substep_acceleration is None:
                first_substep_acceleration = _array(data.qacc[:2])
            max_abs_velocity = np.maximum(max_abs_velocity, np.abs(data.qvel[:2]))
        trace.append(
            {
                "control_interval": interval,
                "qpos_rad": _array(data.qpos[:2]),
                "qvel_rad_per_s": _array(data.qvel[:2]),
                "max_abs_qvel_rad_per_s": _array(max_abs_velocity),
                "qacc_first_substep_rad_per_s2": first_substep_acceleration,
                "end_effector_m": _array(data.site("end_effector").xpos),
            }
        )

    return {
        "posture": posture_name,
        "initial_qpos_rad": qpos,
        "action": action,
        "applied_generalized_force": applied_force,
        "initial_state": initial_state,
        "trace": trace,
    }


def _ik_feasibility() -> dict:
    joint_limit = np.deg2rad(170.0)
    radii = np.linspace(0.06, 0.20, 8)
    angles = np.linspace(-np.pi, np.pi, 73)[:-1]
    rows: list[dict] = []
    feasible_counts = {"positive_elbow": 0, "negative_elbow": 0}
    minimum_margin = {"positive_elbow": float("inf"), "negative_elbow": float("inf")}

    for radius in radii:
        elbow_cosine = (
            radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
        ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
        elbow_open = float(np.arccos(np.clip(elbow_cosine, -1.0, 1.0)))
        for angle in angles:
            candidates = []
            for branch, elbow in (
                ("positive_elbow", elbow_open),
                ("negative_elbow", -elbow_open),
            ):
                shoulder = float(
                    angle
                    - np.arctan2(
                        FOREARM_LENGTH * np.sin(elbow),
                        UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
                    )
                )
                shoulder = float((shoulder + np.pi) % (2.0 * np.pi) - np.pi)
                margin = float(
                    min(
                        joint_limit - abs(shoulder),
                        joint_limit - abs(elbow),
                    )
                )
                feasible = margin >= 0.0
                key = branch
                if feasible:
                    feasible_counts[key] += 1
                minimum_margin[key] = min(minimum_margin[key], margin)
                candidates.append(
                    {
                        "branch": branch,
                        "qpos_rad": [shoulder, elbow],
                        "limit_margin_rad": margin,
                        "feasible": feasible,
                    }
                )
            rows.append(
                {
                    "radius_m": float(radius),
                    "target_angle_rad": float(angle),
                    "solutions": candidates,
                }
            )

    return {
        "grid_shape": {"radii": len(radii), "angles": len(angles)},
        "joint_limit_rad": joint_limit,
        "feasible_solution_counts": feasible_counts,
        "minimum_limit_margin_rad": minimum_margin,
        "solutions": rows,
    }


def characterize(artifact: Path) -> None:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    postures = {
        "extended": [0.0, 0.0],
        "positive_open": [0.0, float(np.deg2rad(90.0))],
        "negative_open": [0.0, float(np.deg2rad(-90.0))],
        "positive_folded": [0.0, float(np.deg2rad(140.0))],
        "negative_folded": [0.0, float(np.deg2rad(-140.0))],
    }
    actions = ([1.0, 0.0], [-1.0, 0.0], [0.0, 1.0], [0.0, -1.0])
    responses = [
        _probe_response(model, data, posture, qpos, action)
        for posture, qpos in postures.items()
        for action in actions
    ]

    body_fields = []
    for body_id in range(model.nbody):
        body_fields.append(
            {
                "name": _name(model, mujoco.mjtObj.mjOBJ_BODY, body_id),
                "mass_kg": float(model.body_mass[body_id]),
                "inertia_kg_m2": _array(model.body_inertia[body_id]),
                "center_of_mass_m": _array(model.body_ipos[body_id]),
            }
        )

    payload = {
        "schema_version": 1,
        "measurement": "compiled_arm_dynamics_and_kinematic_feasibility",
        "model": {
            "xml_path": str(TWO_JOINT_ARM_XML_PATH),
            "timestep_s": float(model.opt.timestep),
            "integrator": int(model.opt.integrator),
            "solver": int(model.opt.solver),
            "nbody": int(model.nbody),
            "njnt": int(model.njnt),
            "nv": int(model.nv),
            "nu": int(model.nu),
            "bodies": body_fields,
            "dof_damping": _array(model.dof_damping[:2]),
            "dof_armature": _array(model.dof_armature[:2]),
            "joint_names": [
                _name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id)
                for joint_id in range(model.njnt)
            ],
            "joint_ranges_rad": _array(model.jnt_range[:2]),
            "joint_limited": _array(model.jnt_limited[:2]),
            "actuator_gear": _array(model.actuator_gear[:2]),
            "actuator_ctrlrange": _array(model.actuator_ctrlrange[:2]),
            "actuator_ctrllimited": _array(model.actuator_ctrllimited[:2]),
            "actuator_forcerange": _array(model.actuator_forcerange[:2]),
            "actuator_forcelimited": _array(model.actuator_forcelimited[:2]),
        },
        "probe_design": {
            "action_pulse_intervals": 1,
            "zero_action_intervals_after_pulse": 24,
            "substeps_per_control_interval": 10,
            "control_interval_s": float(model.opt.timestep * 10),
            "postures_qpos_rad": postures,
            "actions": actions,
        },
        "action_response": responses,
        "ik_feasibility": _ik_feasibility(),
        "units": {
            "mass": "kg",
            "inertia": "kg m^2",
            "position": "m",
            "velocity": "rad/s",
            "acceleration": "rad/s^2",
            "force": "N m",
            "angle": "rad",
            "time": "s",
        },
    }
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    characterize(args.artifact)


if __name__ == "__main__":
    main()
