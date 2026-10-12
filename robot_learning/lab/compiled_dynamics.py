"""Characterize the compiled two-joint MuJoCo dynamics.

This is a laboratory measurement, not an alternate task environment. It
loads the protected robot XML, records the fields produced by MuJoCo's
compiler, and applies deterministic bounded commands at representative
postures. The output path is deliberately supplied by the caller.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import (
    FOREARM_LENGTH,
    TWO_JOINT_ARM_XML_PATH,
    UPPER_ARM_LENGTH,
)


FRAME_SKIP = 10
EXPECTED_TIMESTEP = 0.002
TOTAL_CONTROL_STEPS = 60
ACTIVE_STEP_COUNT = 12
ZERO_DECAY_ACTIVE_STEP_COUNT = 10
INNER_RADIUS = 0.08
OUTER_RADIUS = 0.18
POSTURE_ANGLE = 0.0


def _json_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _required_attribute(owner: Any, name: str, label: str) -> Any:
    if not hasattr(owner, name):
        raise RuntimeError(f"required compiled field is unavailable: {label}.{name}")
    return getattr(owner, name)


def _name(model: mujoco.MjModel, object_type: Any, object_id: int) -> str:
    result = mujoco.mj_id2name(model, object_type, object_id)
    if result is None:
        raise RuntimeError(f"MuJoCo did not provide a name for object id {object_id}")
    return result


def _object_id(model: mujoco.MjModel, object_type: Any, name: str) -> int:
    object_id = mujoco.mj_name2id(model, object_type, name)
    if object_id < 0:
        raise RuntimeError(f"required MuJoCo object is unavailable: {name}")
    return int(object_id)


def _actuator_label(
    model: mujoco.MjModel, actuator_id: int, actuator_trnid: np.ndarray
) -> str:
    """Name an actuator while allowing the XML's unnamed motors."""

    result = mujoco.mj_id2name(
        model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_id
    )
    if result is not None:
        return result

    label = f"actuator_{actuator_id}"
    transmitted_joint_id = int(actuator_trnid[actuator_id][0])
    if transmitted_joint_id >= 0:
        transmitted_joint_name = mujoco.mj_id2name(
            model, mujoco.mjtObj.mjOBJ_JOINT, transmitted_joint_id
        )
        if transmitted_joint_name is not None:
            label = f"{label}_joint_{transmitted_joint_name}"
    return label


def _compiled_fields(model: mujoco.MjModel) -> dict[str, Any]:
    body_mass = _required_attribute(model, "body_mass", "MjModel")
    body_inertia = _required_attribute(model, "body_inertia", "MjModel")
    body_ipos = _required_attribute(model, "body_ipos", "MjModel")
    jnt_damping = _required_attribute(model, "jnt_damping", "MjModel")
    jnt_armature = _required_attribute(model, "jnt_armature", "MjModel")
    actuator_ctrlrange = _required_attribute(model, "actuator_ctrlrange", "MjModel")
    actuator_gear = _required_attribute(model, "actuator_gear", "MjModel")
    actuator_trnid = _required_attribute(model, "actuator_trnid", "MjModel")
    option = model.opt
    option_fields = (
        "timestep",
        "integrator",
        "solver",
        "iterations",
        "tolerance",
        "ls_iterations",
        "noslip_iterations",
        "ccd_iterations",
        "sdf_iterations",
    )
    compiled_options = {
        field: _json_value(_required_attribute(option, field, "MjOption"))
        for field in option_fields
    }

    bodies = []
    for body_id in range(model.nbody):
        bodies.append(
            {
                "name": _name(model, mujoco.mjtObj.mjOBJ_BODY, body_id),
                "mass": _json_value(body_mass[body_id]),
                "inertia": _json_value(body_inertia[body_id]),
                "ipos": _json_value(body_ipos[body_id]),
            }
        )

    joints = []
    for joint_id in range(model.njnt):
        joints.append(
            {
                "name": _name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id),
                "damping": _json_value(jnt_damping[joint_id]),
                "armature": _json_value(jnt_armature[joint_id]),
            }
        )

    actuators = []
    for actuator_id in range(model.nu):
        actuators.append(
            {
                "name": _actuator_label(model, actuator_id, actuator_trnid),
                "ctrlrange": _json_value(actuator_ctrlrange[actuator_id]),
                "gear": _json_value(actuator_gear[actuator_id]),
                "trnid": _json_value(actuator_trnid[actuator_id]),
            }
        )

    return {
        "counts": {
            "nbody": int(model.nbody),
            "njnt": int(model.njnt),
            "nu": int(model.nu),
        },
        "bodies": bodies,
        "joints": joints,
        "actuators": actuators,
        "options": compiled_options,
    }


def _ik_posture(radius: float, branch: str) -> dict[str, Any]:
    cosine = (
        radius * radius
        - UPPER_ARM_LENGTH * UPPER_ARM_LENGTH
        - FOREARM_LENGTH * FOREARM_LENGTH
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_magnitude = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    elbow = elbow_magnitude if branch == "open" else -elbow_magnitude
    shoulder = POSTURE_ANGLE - float(
        np.arctan2(
            FOREARM_LENGTH * np.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
        )
    )
    return {
        "name": f"{'inner' if radius == INNER_RADIUS else 'outer'}_{branch}",
        "kind": "ik_posture",
        "branch": branch,
        "representative_radius_m": radius,
        "target_angle_rad": POSTURE_ANGLE,
        "q": [shoulder, elbow],
    }


def _postures() -> list[dict[str, Any]]:
    return [
        {
            "name": "reset_singular",
            "kind": "reset_singular",
            "branch": None,
            "representative_radius_m": UPPER_ARM_LENGTH + FOREARM_LENGTH,
            "target_angle_rad": POSTURE_ANGLE,
            "q": [0.0, 0.0],
        },
        _ik_posture(INNER_RADIUS, "open"),
        _ik_posture(INNER_RADIUS, "folded"),
        _ik_posture(OUTER_RADIUS, "open"),
        _ik_posture(OUTER_RADIUS, "folded"),
    ]


def _set_posture(
    model: mujoco.MjModel, data: mujoco.MjData, posture: dict[str, Any]
) -> None:
    mujoco.mj_resetData(model, data)
    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    shoulder_id = _object_id(model, mujoco.mjtObj.mjOBJ_JOINT, "shoulder")
    elbow_id = _object_id(model, mujoco.mjtObj.mjOBJ_JOINT, "elbow")
    data.qpos[model.jnt_qposadr[shoulder_id]] = posture["q"][0]
    data.qpos[model.jnt_qposadr[elbow_id]] = posture["q"][1]
    data.ctrl[:] = 0.0
    mujoco.mj_forward(model, data)


def _state(
    model: mujoco.MjModel, data: mujoco.MjData, site_id: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    shoulder_id = _object_id(model, mujoco.mjtObj.mjOBJ_JOINT, "shoulder")
    elbow_id = _object_id(model, mujoco.mjtObj.mjOBJ_JOINT, "elbow")
    q_addresses = [model.jnt_qposadr[shoulder_id], model.jnt_qposadr[elbow_id]]
    qdot_addresses = [model.jnt_dofadr[shoulder_id], model.jnt_dofadr[elbow_id]]
    q = np.asarray([data.qpos[address] for address in q_addresses], dtype=float)
    qdot = np.asarray([data.qvel[address] for address in qdot_addresses], dtype=float)
    position = np.asarray(data.site_xpos[site_id], dtype=float).copy()
    velocity = np.asarray(data.site_xvelp[site_id], dtype=float).copy()
    return q, qdot, position, velocity


def _run_experiment(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    site_id: int,
    posture: dict[str, Any],
    name: str,
    active_command: list[float],
    active_steps: int,
) -> dict[str, Any]:
    _set_posture(model, data, posture)
    initial_q, initial_qdot, initial_position, initial_velocity = _state(
        model, data, site_id
    )
    radial_unit = initial_position[:2] / np.linalg.norm(initial_position[:2])
    tangential_unit = np.asarray([-radial_unit[1], radial_unit[0]])
    control_dt = float(model.opt.timestep) * FRAME_SKIP
    trace = []
    peak_qdot = 0.0
    peak_speed = 0.0

    for step_index in range(1, TOTAL_CONTROL_STEPS + 1):
        command = active_command if step_index <= active_steps else [0.0, 0.0]
        data.ctrl[:] = np.asarray(command, dtype=float)
        for _ in range(FRAME_SKIP):
            mujoco.mj_step(model, data)
        q, qdot, position, velocity = _state(model, data, site_id)
        displacement = position - initial_position
        radial_displacement = float(np.dot(displacement[:2], radial_unit))
        tangential_displacement = float(
            np.dot(displacement[:2], tangential_unit)
        )
        qdot_norm = float(np.linalg.norm(qdot))
        speed = float(np.linalg.norm(velocity))
        peak_qdot = max(peak_qdot, qdot_norm)
        peak_speed = max(peak_speed, speed)
        trace.append(
            {
                "control_step": step_index,
                "time_s": step_index * control_dt,
                "phase": "active" if step_index <= active_steps else "zero",
                "q": q.tolist(),
                "qdot": qdot.tolist(),
                "end_effector_position": position.tolist(),
                "end_effector_velocity": velocity.tolist(),
                "commanded_controls": [float(value) for value in command],
                "distance_from_initial_position_m": float(
                    np.linalg.norm(displacement)
                ),
                "displacement_m": displacement.tolist(),
                "displacement_norm_m": float(np.linalg.norm(displacement)),
                "radial_displacement_m": radial_displacement,
                "tangential_displacement_m": tangential_displacement,
                "q_displacement_norm_rad": float(np.linalg.norm(q - initial_q)),
                "qdot_norm_rad_s": qdot_norm,
                "end_effector_speed_m_s": speed,
            }
        )

    zero_trace = trace[active_steps:]
    active_trace = trace[:active_steps]
    return {
        "name": name,
        "posture": posture["name"],
        "active_command": active_command,
        "active_control_steps": active_steps,
        "total_control_steps": TOTAL_CONTROL_STEPS,
        "initial_state": {
            "q": initial_q.tolist(),
            "qdot": initial_qdot.tolist(),
            "end_effector_position": initial_position.tolist(),
            "end_effector_velocity": initial_velocity.tolist(),
        },
        "summary": {
            "peak_qdot_norm_rad_s": peak_qdot,
            "peak_end_effector_speed_m_s": peak_speed,
            "active_end_displacement_norm_m": active_trace[-1][
                "displacement_norm_m"
            ],
            "maximum_displacement_norm_m": max(
                item["displacement_norm_m"] for item in trace
            ),
            "maximum_inward_radial_displacement_m": max(
                0.0, max(-item["radial_displacement_m"] for item in trace)
            ),
            "maximum_absolute_tangential_displacement_m": max(
                abs(item["tangential_displacement_m"]) for item in trace
            ),
            "zero_phase_start_qdot_norm_rad_s": zero_trace[0]["qdot_norm_rad_s"],
            "zero_phase_end_qdot_norm_rad_s": zero_trace[-1]["qdot_norm_rad_s"],
            "zero_phase_start_speed_m_s": zero_trace[0][
                "end_effector_speed_m_s"
            ],
            "zero_phase_end_speed_m_s": zero_trace[-1][
                "end_effector_speed_m_s"
            ],
        },
        "trace": trace,
    }


def characterize() -> dict[str, Any]:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    site_id = _object_id(model, mujoco.mjtObj.mjOBJ_SITE, "end_effector")
    postures = _postures()
    experiment_specs = (
        ("saturated_shoulder_step", [1.0, 0.0], ACTIVE_STEP_COUNT),
        ("saturated_elbow_step", [0.0, 1.0], ACTIVE_STEP_COUNT),
        ("saturated_bilateral_step", [1.0, 1.0], ACTIVE_STEP_COUNT),
        ("zero_command_decay", [1.0, 0.0], ZERO_DECAY_ACTIVE_STEP_COUNT),
    )
    experiments = [
        _run_experiment(model, data, site_id, posture, name, command, active_steps)
        for posture in postures
        for name, command, active_steps in experiment_specs
    ]
    control_dt = float(model.opt.timestep) * FRAME_SKIP
    return {
        "schema": "robot_learning.lab.compiled_dynamics.v1",
        "tool": "compiled_dynamics",
        "description": (
            "Deterministic bounded motor step responses of the protected "
            "two-joint MuJoCo model."
        ),
        "source_xml": str(TWO_JOINT_ARM_XML_PATH),
        "measurement_contract": {
            "compiled_timestep_s": float(model.opt.timestep),
            "expected_xml_timestep_s": EXPECTED_TIMESTEP,
            "frame_skip": FRAME_SKIP,
            "control_interval_s": control_dt,
            "control_rate_hz": 1.0 / control_dt,
            "controls_bound": [-1.0, 1.0],
            "total_control_steps_per_trace": TOTAL_CONTROL_STEPS,
            "posture_angle_rad": POSTURE_ANGLE,
        },
        "compiled_model": _compiled_fields(model),
        "postures": postures,
        "experiments": experiments,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write a compiled MuJoCo dynamics characterization artifact."
    )
    parser.add_argument("output", type=Path, help="caller-supplied JSON output path")
    args = parser.parse_args()
    artifact = characterize()
    args.output.write_text(
        json.dumps(artifact, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
