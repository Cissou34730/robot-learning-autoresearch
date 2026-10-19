"""Measure local command authority of the compiled two-joint arm.

This is a direct bounded motor-command diagnostic, not a policy evaluation.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import (
    FOREARM_LENGTH,
    TWO_JOINT_ARM_XML_PATH,
    UPPER_ARM_LENGTH,
)
from contracts.task_spec import (
    FRAME_SKIP,
    HOLD_SECONDS,
    MAX_EPISODE_STEPS,
    TARGET_RADIUS_RANGE,
)

_JOINT_NAMES = ("shoulder", "elbow")
_LINK_NAMES = ("upper_arm", "forearm")
_SITE_NAME = "end_effector"
_IK_BRANCHES = (("elbow_positive", 1.0), ("elbow_negative", -1.0))
_PULSE_CONTROLS = (
    (1.0, 0.0),
    (-1.0, 0.0),
    (0.0, 1.0),
    (0.0, -1.0),
)
_LIMIT_TOLERANCE_RAD = 1e-10
_KINEMATIC_TOLERANCE_M = 1e-9
_CONTROL_TOLERANCE = 1e-12
_INTERVAL_COUNT_TOLERANCE = 1e-12


def _named_id(
    model: mujoco.MjModel, object_type: mujoco.mjtObj, name: str
) -> int:
    object_id = int(mujoco.mj_name2id(model, object_type, name))
    if object_id < 0:
        raise RuntimeError(f"Compiled model is missing required named object {name!r}")
    return object_id


def _require_expected_model_dimensions(model: mujoco.MjModel) -> None:
    dimensions = (int(model.nq), int(model.nv), int(model.nu))
    if dimensions != (2, 2, 2):
        raise RuntimeError(
            "The compiled two-joint-arm model must have nq=2, nv=2, and nu=2; "
            f"found nq={dimensions[0]}, nv={dimensions[1]}, nu={dimensions[2]}."
        )


def _finite_float_list(values: Any) -> list[float]:
    return [float(value) for value in np.asarray(values).reshape(-1)]


def _resolve_joint_metadata(
    model: mujoco.MjModel,
) -> list[dict[str, Any]]:
    metadata: list[dict[str, Any]] = []
    for name in _JOINT_NAMES:
        joint_id = _named_id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if not bool(model.jnt_limited[joint_id]):
            raise RuntimeError(
                f"Expected compiled limits for joint {name!r}, but the joint "
                "is not marked limited."
            )
        dof_address = int(model.jnt_dofadr[joint_id])
        qpos_address = int(model.jnt_qposadr[joint_id])
        limits = _finite_float_list(model.jnt_range[joint_id])
        metadata.append(
            {
                "name": name,
                "joint_id": joint_id,
                "qpos_address": qpos_address,
                "dof_address": dof_address,
                "damping_Nm_s_per_rad": float(model.dof_damping[dof_address]),
                "armature_kg_m2": float(model.dof_armature[dof_address]),
                "compiled_limited": True,
                "compiled_range_rad": limits,
            }
        )
    for address, joint in enumerate(metadata):
        if (
            joint["qpos_address"] != address
            or joint["dof_address"] != address
        ):
            raise RuntimeError(
                "The compiled arm joint ordering does not match the expected "
                "shoulder/elbow generalized-coordinate ordering."
            )
    return metadata


def _check_configuration_limits(
    qpos: np.ndarray, joint_metadata: list[dict[str, Any]], description: str
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for value, joint in zip(qpos, joint_metadata, strict=True):
        lower, upper = joint["compiled_range_rad"]
        within_limits = (
            lower - _LIMIT_TOLERANCE_RAD
            <= float(value)
            <= upper + _LIMIT_TOLERANCE_RAD
        )
        if not within_limits:
            raise RuntimeError(
                f"Expected configuration {description!r} is unavailable: "
                f"{joint['name']}={float(value):.17g} rad is outside the compiled "
                f"range [{lower:.17g}, {upper:.17g}] rad."
            )
        checks.append(
            {
                "joint": joint["name"],
                "qpos_rad": float(value),
                "compiled_range_rad": [lower, upper],
                "within_compiled_limits": True,
            }
        )
    return checks


def _expected_ik_configurations(
    joint_metadata: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    upper_length = float(UPPER_ARM_LENGTH)
    forearm_length = float(FOREARM_LENGTH)
    minimum_radius = abs(upper_length - forearm_length)
    maximum_radius = upper_length + forearm_length
    minimum_target_radius, maximum_target_radius = TARGET_RADIUS_RANGE
    radii = (
        float(minimum_target_radius),
        float((minimum_target_radius + maximum_target_radius) / 2.0),
        float(maximum_target_radius),
    )
    configurations: list[dict[str, Any]] = []

    for radius in radii:
        if radius < minimum_radius - _KINEMATIC_TOLERANCE_M or (
            radius > maximum_radius + _KINEMATIC_TOLERANCE_M
        ):
            raise RuntimeError(
                "Expected IK branches are unavailable: target radius "
                f"{radius:.17g} m is outside the two-link reachable interval "
                f"[{minimum_radius:.17g}, {maximum_radius:.17g}] m."
            )

        cos_elbow = (
            radius * radius
            - upper_length * upper_length
            - forearm_length * forearm_length
        ) / (2.0 * upper_length * forearm_length)
        if cos_elbow < -1.0 - _KINEMATIC_TOLERANCE_M or (
            cos_elbow > 1.0 + _KINEMATIC_TOLERANCE_M
        ):
            raise RuntimeError(
                "Expected IK branches are unavailable: the elbow cosine "
                f"{cos_elbow:.17g} for radius {radius:.17g} m is infeasible."
            )
        elbow_magnitude = math.acos(max(-1.0, min(1.0, cos_elbow)))

        for branch_name, branch_sign in _IK_BRANCHES:
            elbow = branch_sign * elbow_magnitude
            shoulder = -math.atan2(
                forearm_length * math.sin(elbow),
                upper_length + forearm_length * math.cos(elbow),
            )
            qpos = np.asarray((shoulder, elbow), dtype=np.float64)
            description = f"{radius:.17g} m / {branch_name}"
            limit_checks = _check_configuration_limits(
                qpos, joint_metadata, description
            )
            configurations.append(
                {
                    "name": f"target_{radius:.2f}m_{branch_name}",
                    "configuration_source": "planar two-link inverse kinematics",
                    "target": {
                        "radius_m": radius,
                        "bearing_rad": 0.0,
                        "position_xy_m": [radius, 0.0],
                    },
                    "elbow_branch": branch_name,
                    "qpos_rad": _finite_float_list(qpos),
                    "joint_limit_validation": limit_checks,
                }
            )

    return configurations


def _compiled_model_report(
    model: mujoco.MjModel,
    joint_metadata: list[dict[str, Any]],
    body_ids: dict[str, int],
    actuator_ids: list[int],
) -> dict[str, Any]:
    links = []
    for name in _LINK_NAMES:
        body_id = body_ids[name]
        links.append(
            {
                "name": name,
                "mass_kg": float(model.body_mass[body_id]),
                "principal_inertias_kg_m2": _finite_float_list(
                    model.body_inertia[body_id]
                ),
                "principal_inertia_frame": (
                    "compiled body inertial frame; values are the three principal "
                    "moments of inertia"
                ),
            }
        )

    actuators = []
    for actuator_id in actuator_ids:
        joint_id = int(model.actuator_trnid[actuator_id, 0])
        joint_name = next(
            (
                name
                for name in _JOINT_NAMES
                if int(
                    mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
                )
                == joint_id
            ),
            None,
        )
        if joint_name is None:
            raise RuntimeError(
                f"Actuator {actuator_id} does not transmit to an expected arm joint."
            )
        actuator_name = mujoco.mj_id2name(
            model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_id
        )
        gear = _finite_float_list(model.actuator_gear[actuator_id])
        actuators.append(
            {
                "name": actuator_name or f"motor_for_{joint_name}",
                "actuator_id": actuator_id,
                "joint": joint_name,
                "gear_vector": gear,
                "joint_axis_gear": float(gear[0]),
                "control_range": _finite_float_list(
                    model.actuator_ctrlrange[actuator_id]
                ),
                "control_limited": bool(model.actuator_ctrllimited[actuator_id]),
                "control_units": "MuJoCo motor control (dimensionless in this XML)",
            }
        )

    return {
        "xml_path": "contracts/robots/two_joint_arm.xml",
        "timestep_seconds": float(model.opt.timestep),
        "links": links,
        "joints": [
            {
                key: value
                for key, value in joint.items()
                if key not in ("joint_id", "qpos_address", "dof_address")
            }
            for joint in joint_metadata
        ],
        "actuators": actuators,
    }


def _set_posture(
    model: mujoco.MjModel, data: mujoco.MjData, qpos: list[float]
) -> None:
    mujoco.mj_resetData(model, data)
    data.qpos[:] = qpos
    data.qvel[:] = 0.0
    data.ctrl[:] = 0.0


def _actuator_ids_by_joint(model: mujoco.MjModel) -> list[int]:
    actuator_ids: list[int] = []
    for joint_name in _JOINT_NAMES:
        joint_id = _named_id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
        matching_ids = [
            actuator_id
            for actuator_id in range(model.nu)
            if int(model.actuator_trnid[actuator_id, 0]) == joint_id
        ]
        if len(matching_ids) != 1:
            raise RuntimeError(
                f"Expected exactly one compiled motor actuator for joint "
                f"{joint_name!r}; found {len(matching_ids)}."
            )
        actuator_ids.append(matching_ids[0])
    return actuator_ids


def _initial_dynamics(
    model: mujoco.MjModel, data: mujoco.MjData
) -> dict[str, list[float]]:
    mujoco.mj_forward(model, data)
    return {
        "qacc_rad_s2": _finite_float_list(data.qacc),
        "qfrc_actuator_Nm": _finite_float_list(data.qfrc_actuator),
    }


def _capture_pose_properties(
    model: mujoco.MjModel, data: mujoco.MjData, site_id: int
) -> dict[str, Any]:
    mass_matrix = np.zeros((model.nv, model.nv), dtype=np.float64, order="C")
    mujoco.mj_fullM(model, data, mass_matrix)
    jacobian_position = np.zeros((3, model.nv), dtype=np.float64, order="C")
    mujoco.mj_jacSite(model, data, jacobian_position, None, site_id)
    return {
        "generalized_mass_matrix": mass_matrix.tolist(),
        "mass_matrix_units": (
            "SI-consistent generalized inertia; rotational joint coordinates are radians"
        ),
        "end_effector_translational_jacobian": jacobian_position.tolist(),
        "jacobian_units": "m/rad for these rotational joint coordinates",
    }


def _sample_state(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    site_id: int,
    time_seconds: float,
    initial_endpoint: np.ndarray,
    applied_control: tuple[float, float],
) -> dict[str, Any]:
    endpoint = np.asarray(data.site(_SITE_NAME).xpos, dtype=np.float64).copy()
    jacobian_position = np.zeros((3, model.nv), dtype=np.float64, order="C")
    mujoco.mj_jacSite(model, data, jacobian_position, None, site_id)
    endpoint_velocity = jacobian_position @ np.asarray(data.qvel, dtype=np.float64)
    return {
        "time_seconds": float(time_seconds),
        "qpos_rad": _finite_float_list(data.qpos),
        "qvel_rad_s": _finite_float_list(data.qvel),
        "end_effector_position_m": _finite_float_list(endpoint),
        "end_effector_speed_m_s": float(np.linalg.norm(endpoint_velocity)),
        "distance_from_initial_endpoint_m": float(
            np.linalg.norm(endpoint - initial_endpoint)
        ),
        "applied_control": [float(value) for value in applied_control],
    }


def _advance_control_interval(
    model: mujoco.MjModel, data: mujoco.MjData, control: tuple[float, float]
) -> None:
    data.ctrl[:] = control
    for _ in range(FRAME_SKIP):
        mujoco.mj_step(model, data)


def _run_pulse_trial(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    site_id: int,
    qpos: list[float],
    pulse_control: tuple[float, float],
    control_interval_seconds: float,
    passive_intervals: int,
) -> dict[str, Any]:
    _set_posture(model, data, qpos)
    data.ctrl[:] = pulse_control
    initial_commanded_dynamics = _initial_dynamics(model, data)
    initial_endpoint = np.asarray(data.site(_SITE_NAME).xpos, dtype=np.float64).copy()
    samples = [
        _sample_state(
            model,
            data,
            site_id,
            0.0,
            initial_endpoint,
            pulse_control,
        )
    ]

    _advance_control_interval(model, data, pulse_control)
    zero_control = (0.0, 0.0)
    data.ctrl[:] = zero_control
    mujoco.mj_forward(model, data)
    samples.append(
        _sample_state(
            model,
            data,
            site_id,
            control_interval_seconds,
            initial_endpoint,
            zero_control,
        )
    )

    for passive_index in range(1, passive_intervals + 1):
        _advance_control_interval(model, data, zero_control)
        mujoco.mj_forward(model, data)
        samples.append(
            _sample_state(
                model,
                data,
                site_id,
                (1 + passive_index) * control_interval_seconds,
                initial_endpoint,
                zero_control,
            )
        )

    return {
        "pulse_control": [float(value) for value in pulse_control],
        "pulse_duration_seconds": control_interval_seconds,
        "zero_control_followup_seconds": 1.0,
        "initial_dynamics_under_pulse": initial_commanded_dynamics,
        "samples": samples,
    }


def _measure(model: mujoco.MjModel) -> dict[str, Any]:
    _require_expected_model_dimensions(model)
    data = mujoco.MjData(model)
    joint_metadata = _resolve_joint_metadata(model)
    body_ids = {
        name: _named_id(model, mujoco.mjtObj.mjOBJ_BODY, name)
        for name in _LINK_NAMES
    }
    actuator_ids = _actuator_ids_by_joint(model)
    site_id = _named_id(model, mujoco.mjtObj.mjOBJ_SITE, _SITE_NAME)

    control_interval_seconds = float(model.opt.timestep) * FRAME_SKIP
    passive_intervals_float = 1.0 / control_interval_seconds
    passive_intervals = round(passive_intervals_float)
    if (
        passive_intervals <= 0
        or abs(passive_intervals_float - passive_intervals)
        > _INTERVAL_COUNT_TOLERANCE
    ):
        raise RuntimeError(
            "The compiled timestep and official frame skip do not divide the "
            "1.0-second passive interval into whole control intervals."
        )

    for pulse in _PULSE_CONTROLS:
        for actuator_id, control in zip(actuator_ids, pulse, strict=True):
            control_lower, control_upper = (
                float(value)
                for value in model.actuator_ctrlrange[actuator_id]
            )
            if not (
                control_lower - _CONTROL_TOLERANCE
                <= control
                <= control_upper + _CONTROL_TOLERANCE
            ):
                raise RuntimeError(
                    f"Requested pulse control {control:g} is outside actuator "
                    f"{actuator_id}'s compiled control range "
                    f"[{control_lower:g}, {control_upper:g}]."
                )

    reset_qpos = [0.0, 0.0]
    reset_limit_validation = _check_configuration_limits(
        np.asarray(reset_qpos, dtype=np.float64), joint_metadata, "reset"
    )
    configurations = [
        {
            "name": "reset",
            "configuration_source": "official zero-angle, zero-velocity reset",
            "target": None,
            "elbow_branch": None,
            "qpos_rad": reset_qpos,
            "joint_limit_validation": reset_limit_validation,
        },
        *_expected_ik_configurations(joint_metadata),
    ]

    posture_records = []
    for configuration in configurations:
        qpos = configuration["qpos_rad"]
        _set_posture(model, data, qpos)
        baseline_dynamics = _initial_dynamics(model, data)
        pose_properties = _capture_pose_properties(model, data, site_id)
        initial_endpoint = np.asarray(
            data.site(_SITE_NAME).xpos, dtype=np.float64
        ).copy()
        actual_radius = float(np.linalg.norm(initial_endpoint[:2]))
        target = configuration["target"]
        if target is not None and abs(actual_radius - target["radius_m"]) > (
            _KINEMATIC_TOLERANCE_M
        ):
            raise RuntimeError(
                f"Expected IK branch {configuration['name']!r} does not compile "
                f"to its target radius: got {actual_radius:.17g} m, expected "
                f"{target['radius_m']:.17g} m."
            )

        posture_records.append(
            {
                **configuration,
                "initial_end_effector_position_m": _finite_float_list(initial_endpoint),
                "compiled_end_effector_radius_m": actual_radius,
                **pose_properties,
                "initial_zero_control_dynamics": baseline_dynamics,
                "trials": [
                    _run_pulse_trial(
                        model,
                        data,
                        site_id,
                        qpos,
                        pulse,
                        control_interval_seconds,
                        passive_intervals,
                    )
                    for pulse in _PULSE_CONTROLS
                ],
            }
        )

    return {
        "measurement": "two_joint_arm_local_command_authority",
        "model": _compiled_model_report(
            model, joint_metadata, body_ids, actuator_ids
        ),
        "protocol": {
            "purpose": (
                "Direct physical-command diagnostic of compiled local dynamics; "
                "not a policy evaluation."
            ),
            "control_interval_seconds": control_interval_seconds,
            "physics_substeps_per_control_interval": FRAME_SKIP,
            "official_hold_seconds": HOLD_SECONDS,
            "official_hold_control_steps": round(
                HOLD_SECONDS / control_interval_seconds
            ),
            "official_episode_horizon_seconds": (
                MAX_EPISODE_STEPS * control_interval_seconds
            ),
            "official_episode_control_steps": MAX_EPISODE_STEPS,
            "pulse_protocol": (
                "Each trial is reset to the named posture with zero velocity. "
                "One bounded control vector is applied for one control interval, "
                "then [0, 0] is applied for exactly 1.0 s."
            ),
            "sample_protocol": (
                "Samples occur at t=0 and every control boundary through the "
                "end of the 1.0 s zero-control follow-up. applied_control is the "
                "control set for the interval beginning at that sample; therefore "
                "the t=0 sample carries the pulse and subsequent samples carry zero."
            ),
            "initial_dynamics_protocol": (
                "initial_zero_control_dynamics is evaluated at the posture with "
                "zero velocity and zero control. Each trial also records "
                "initial_dynamics_under_pulse at t=0 after applying the pulse "
                "and computing forward dynamics."
            ),
            "pulse_controls": [
                [float(value) for value in pulse] for pulse in _PULSE_CONTROLS
            ],
            "pulse_control_bounds_source": (
                "compiled actuator control ranges; requested vectors are checked "
                "against those ranges before measurement"
            ),
            "units": {
                "time": "s",
                "qpos": "rad",
                "qvel": "rad/s",
                "qacc": "rad/s^2",
                "generalized_actuator_force": "N m",
                "end_effector_position": "m",
                "end_effector_speed": "m/s",
                "distance_from_initial_endpoint": "m",
                "motor_control": "dimensionless",
                "mass": "kg",
                "principal_inertia": "kg m^2",
                "joint_damping": "N m s/rad",
                "joint_armature": "kg m^2",
            },
            "interpretation_boundary": (
                "The measurements do not evaluate a policy, target-reaching or "
                "hold success, closed-loop path feasibility, all target bearings, "
                "or protected substep semantics."
            ),
        },
        "postures": posture_records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Measure local bounded-command dynamics of the compiled two-joint arm."
        )
    )
    parser.add_argument(
        "output_path",
        type=Path,
        help="required destination path for the JSON measurement artifact",
    )
    arguments = parser.parse_args()

    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    artifact = _measure(model)
    arguments.output_path.parent.mkdir(parents=True, exist_ok=True)
    with arguments.output_path.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(artifact, output, indent=2, sort_keys=True, allow_nan=False)
        output.write("\n")


if __name__ == "__main__":
    main()
