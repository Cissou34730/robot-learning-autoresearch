"""Measure compiled plant properties and local reach-and-hold control margin."""

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
CONTROL_STEPS = 100
SUCCESS_THRESHOLD = 0.01
TARGET_Z = 0.02


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _branch_configuration(radius: float, angle: float, elbow_sign: float) -> np.ndarray:
    cos_elbow = (
        radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow = elbow_sign * float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))
    shoulder = angle - np.arctan2(
        FOREARM_LENGTH * np.sin(elbow),
        UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
    )
    return np.array([_wrap_to_pi(float(shoulder)), elbow], dtype=np.float64)


def _set_state(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    qpos: np.ndarray,
    qvel: np.ndarray,
    target: np.ndarray,
) -> None:
    mujoco.mj_resetData(model, data)
    data.qpos[:] = qpos
    data.qvel[:] = qvel
    data.mocap_pos[0] = target
    data.ctrl[:] = 0.0
    mujoco.mj_forward(model, data)


def _geom_name(model: mujoco.MjModel, geom_id: int) -> str:
    name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, geom_id)
    return name or f"geom_{geom_id}"


def _contacts(model: mujoco.MjModel, data: mujoco.MjData) -> list[dict]:
    return [
        {
            "geom1": _geom_name(model, int(data.contact[index].geom[0])),
            "geom2": _geom_name(model, int(data.contact[index].geom[1])),
            "distance_m": float(data.contact[index].dist),
        }
        for index in range(data.ncon)
    ]


def _rollout(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    *,
    qtarget: np.ndarray,
    qpos: np.ndarray,
    qvel: np.ndarray,
    target: np.ndarray,
    controller: str,
) -> dict:
    _set_state(model, data, qpos, qvel, target)
    initial_distance = float(
        np.linalg.norm(data.site("end_effector").xpos - target)
    )
    distances = []
    held_steps = 0
    max_held_steps = 0
    interruptions = 0
    was_inside = False
    for _ in range(CONTROL_STEPS):
        if controller == "zero":
            action = np.zeros(2, dtype=np.float64)
        else:
            position_error = np.array(
                [_wrap_to_pi(float(qpos_i - target_i)) for qpos_i, target_i in zip(data.qpos, qtarget)]
            )
            effort = -1.0 * position_error - 0.2 * data.qvel
            action = np.clip(effort / 5.0, -1.0, 1.0)
        data.ctrl[:] = action
        for _ in range(FRAME_SKIP):
            mujoco.mj_step(model, data)
        distance = float(np.linalg.norm(data.site("end_effector").xpos - target))
        distances.append(distance)
        if distance <= SUCCESS_THRESHOLD:
            held_steps += 1
            max_held_steps = max(max_held_steps, held_steps)
            was_inside = True
        else:
            if was_inside:
                interruptions += 1
            held_steps = 0
            was_inside = False
    return {
        "controller": controller,
        "initial_distance_m": initial_distance,
        "minimum_distance_m": float(min(distances)),
        "maximum_distance_m": float(max(distances)),
        "final_distance_m": float(distances[-1]),
        "in_tolerance_steps": int(sum(distance <= SUCCESS_THRESHOLD for distance in distances)),
        "max_consecutive_tolerance_steps": int(max_held_steps),
        "hold_interruptions": int(interruptions),
        "completed_hold": bool(max_held_steps >= CONTROL_STEPS),
    }


def _compiled_properties(model: mujoco.MjModel) -> dict:
    geom_properties = []
    for geom_id in range(model.ngeom):
        geom_properties.append(
            {
                "name": _geom_name(model, geom_id),
                "contype": int(model.geom_contype[geom_id]),
                "conaffinity": int(model.geom_conaffinity[geom_id]),
            }
        )
    return {
        "timestep_s": float(model.opt.timestep),
        "integrator": int(model.opt.integrator),
        "solver": int(model.opt.solver),
        "body_masses_kg": [
            float(mass) for mass in model.body_mass
        ],
        "dof_damping": [float(value) for value in model.dof_damping],
        "dof_armature": [float(value) for value in model.dof_armature],
        "actuator_gear": model.actuator_gear[:, 0].astype(float).tolist(),
        "actuator_ctrlrange": model.actuator_ctrlrange.astype(float).tolist(),
        "geoms": geom_properties,
    }


def measure() -> dict:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    joint_ranges = model.jnt_range[:2].astype(float).tolist()
    radii = np.linspace(0.06, 0.20, 5)
    angles = np.linspace(-np.pi, np.pi, 24, endpoint=False)
    perturbations = {
        "position": (np.array([0.015, -0.015]), np.zeros(2)),
        "velocity": (np.zeros(2), np.array([0.25, -0.25])),
        "combined": (np.array([0.015, -0.015]), np.array([0.25, -0.25])),
    }
    branch_records = []
    rollout_records = []

    for radius in radii:
        for angle in angles:
            target = np.array(
                [radius * np.cos(angle), radius * np.sin(angle), TARGET_Z],
                dtype=np.float64,
            )
            for branch_name, elbow_sign in (("open", 1.0), ("folded", -1.0)):
                qtarget = _branch_configuration(float(radius), float(angle), elbow_sign)
                valid = bool(
                    np.all(qtarget >= model.jnt_range[:2, 0])
                    and np.all(qtarget <= model.jnt_range[:2, 1])
                )
                _set_state(model, data, qtarget, np.zeros(2), target)
                branch_records.append(
                    {
                        "radius_m": float(radius),
                        "angle_degrees": float(np.degrees(angle)),
                        "branch": branch_name,
                        "qtarget_radians": qtarget.tolist(),
                        "within_joint_limits": valid,
                        "contact_count": int(data.ncon),
                        "contacts": _contacts(model, data),
                    }
                )
                if not valid:
                    continue
                for perturbation_name, (qoffset, velocity) in perturbations.items():
                    for controller in ("zero", "local_pd"):
                        result = _rollout(
                            model,
                            data,
                            qtarget=qtarget,
                            qpos=qtarget + qoffset,
                            qvel=velocity,
                            target=target,
                            controller=controller,
                        )
                        rollout_records.append(
                            {
                                "radius_m": float(radius),
                                "angle_degrees": float(np.degrees(angle)),
                                "branch": branch_name,
                                "perturbation": perturbation_name,
                                "initial_qpos_offset_radians": qoffset.tolist(),
                                "initial_qvel_radians_s": velocity.tolist(),
                                **result,
                            }
                        )

    valid_branches = [record for record in branch_records if record["within_joint_limits"]]
    contact_records = [record for record in valid_branches if record["contact_count"] > 0]
    summary = {}
    for controller in ("zero", "local_pd"):
        records = [
            record for record in rollout_records if record["controller"] == controller
        ]
        summary[controller] = {
            "rollouts": len(records),
            "completed_holds": sum(record["completed_hold"] for record in records),
            "completion_rate": (
                sum(record["completed_hold"] for record in records) / len(records)
                if records
                else 0.0
            ),
            "mean_max_consecutive_tolerance_steps": (
                float(np.mean([record["max_consecutive_tolerance_steps"] for record in records]))
                if records
                else 0.0
            ),
            "mean_maximum_distance_m": (
                float(np.mean([record["maximum_distance_m"] for record in records]))
                if records
                else 0.0
            ),
        }

    return {
        "schema_version": 1,
        "measurement": "compiled_plant_and_local_hold_margin",
        "control_interval": {
            "frame_skip": FRAME_SKIP,
            "control_steps": CONTROL_STEPS,
            "success_threshold_m": SUCCESS_THRESHOLD,
        },
        "compiled_properties": _compiled_properties(model),
        "joint_ranges_radians": joint_ranges,
        "grid": {
            "radii_m": radii.tolist(),
            "angles_degrees": [float(np.degrees(angle)) for angle in angles],
        },
        "summary": {
            "branch_configurations": len(branch_records),
            "valid_branch_configurations": len(valid_branches),
            "contacting_valid_configurations": len(contact_records),
            "rollouts": len(rollout_records),
            "controllers": summary,
        },
        "branch_records": branch_records,
        "rollout_records": rollout_records,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(json.dumps(measure(), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
