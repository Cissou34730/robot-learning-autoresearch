"""Deterministic compiled-physics and matched-response measurement.

This module deliberately measures the official XML directly rather than
constructing the visible Gymnasium environment.  It records raw simulator
state alongside derived kinematic metadata so that policy and model
limitations can be separated after the artifact is inspected.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import (
    FOREARM_LENGTH,
    MAX_REACH,
    TWO_JOINT_ARM_XML_PATH,
    UPPER_ARM_LENGTH,
)
from contracts.task_spec import (
    FRAME_SKIP,
    HOLD_SECONDS,
    SUCCESS_THRESHOLD,
    TARGET_RADIUS_RANGE,
)


SCHEMA_VERSION = "physics-baseline-1"
IK_RADII = (0.06, 0.10, 0.14, 0.18, 0.20)
IK_BEARINGS = (-math.pi, -math.pi / 2.0, 0.0, math.pi / 2.0)
RESPONSE_ACTIONS = (
    (1.0, 0.0),
    (-1.0, 0.0),
    (0.0, 1.0),
    (0.0, -1.0),
    (0.0, 0.0),
)
RESPONSE_SUBSTEPS = 10


def _as_json(value: Any) -> Any:
    """Convert MuJoCo/numpy values and non-finite floats to JSON-safe values."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, dict):
        return {str(key): _as_json(item) for key, item in value.items()}
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.ndarray, list, tuple)):
        return [_as_json(item) for item in value]
    if hasattr(value, "name"):
        return str(value.name)
    try:
        return _as_json(float(value))
    except (TypeError, ValueError):
        return str(value)


def _array(value: Any) -> Any:
    """Copy an optional MuJoCo array, preserving unavailable values as null."""
    if value is None:
        return None
    array = np.asarray(value).copy()
    return _as_json(array.item() if array.ndim == 0 else array)


def _optional_attribute(owner: Any, name: str) -> Any:
    try:
        return _array(getattr(owner, name))
    except (AttributeError, TypeError, ValueError):
        return None


def _enum_value(value: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"value": _as_json(value)}
    name = getattr(value, "name", None)
    if name is not None:
        result["name"] = str(name)
    return result


def _object_name(model: mujoco.MjModel, object_type: Any, index: int) -> str | None:
    try:
        name = mujoco.mj_id2name(model, object_type, index)
    except (RuntimeError, TypeError, ValueError):
        return None
    return None if name is None else str(name)


def _contact_records(model: mujoco.MjModel, data: mujoco.MjData) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for contact_id in range(int(data.ncon)):
        contact = data.contact[contact_id]
        force = np.zeros(6, dtype=np.float64)
        try:
            mujoco.mj_contactForce(model, data, contact_id, force)
            force_value: Any = force
            force_norm: Any = np.linalg.norm(force[:3])
            wrench_norm: Any = np.linalg.norm(force)
        except (RuntimeError, TypeError, ValueError):
            force_value = None
            force_norm = None
            wrench_norm = None
        records.append(
            {
                "id": contact_id,
                "geom1_id": int(contact.geom1),
                "geom2_id": int(contact.geom2),
                "geom1_name": _object_name(
                    model, mujoco.mjtObj.mjOBJ_GEOM, int(contact.geom1)
                ),
                "geom2_name": _object_name(
                    model, mujoco.mjtObj.mjOBJ_GEOM, int(contact.geom2)
                ),
                "distance": float(contact.dist),
                "force_contact_frame": force_value,
                "force_norm": force_norm,
                "wrench_norm": wrench_norm,
            }
        )
    return records


def _contact_summary(model: mujoco.MjModel, data: mujoco.MjData) -> dict[str, Any]:
    contacts = _contact_records(model, data)
    force_norms = [
        float(contact["force_norm"])
        for contact in contacts
        if contact["force_norm"] is not None
    ]
    return {
        "total_contacts": int(data.ncon),
        "contacts": contacts,
        "max_contact_force_norm": max(force_norms, default=None),
    }


def _site_state(
    model: mujoco.MjModel, data: mujoco.MjData, site_id: int
) -> tuple[Any, Any]:
    position = np.asarray(data.site_xpos[site_id]).copy()
    velocity = None
    try:
        object_velocity = np.zeros(6, dtype=np.float64)
        mujoco.mj_objectVelocity(
            model,
            data,
            mujoco.mjtObj.mjOBJ_SITE,
            site_id,
            object_velocity,
            0,
        )
        # mj_objectVelocity returns rotational then linear velocity.  The
        # zero local-frame flag requests the world-frame result.
        velocity = object_velocity[3:].copy()
    except (RuntimeError, TypeError, ValueError):
        pass
    return position, velocity


def _target_position(
    radius: float, bearing: float, site_height: float
) -> np.ndarray:
    return np.array(
        [radius * math.cos(bearing), radius * math.sin(bearing), site_height],
        dtype=np.float64,
    )


def _forward_kinematics(q: np.ndarray) -> np.ndarray:
    shoulder, elbow = q
    return np.array(
        [
            UPPER_ARM_LENGTH * math.cos(shoulder)
            + FOREARM_LENGTH * math.cos(shoulder + elbow),
            UPPER_ARM_LENGTH * math.sin(shoulder)
            + FOREARM_LENGTH * math.sin(shoulder + elbow),
        ],
        dtype=np.float64,
    )


def _wrap_to_pi(angle: float) -> float:
    return float((angle + math.pi) % (2.0 * math.pi) - math.pi)


def _jacobian_metadata(
    model: mujoco.MjModel, data: mujoco.MjData, site_id: int
) -> dict[str, Any]:
    jacp = np.zeros((3, int(model.nv)), dtype=np.float64)
    jacr = np.zeros((3, int(model.nv)), dtype=np.float64)
    mujoco.mj_jacSite(model, data, jacp, jacr, site_id)
    planar = jacp[:2, :2]
    singular_values = np.linalg.svd(planar, compute_uv=False)
    smallest = float(singular_values[-1]) if singular_values.size else None
    largest = float(singular_values[0]) if singular_values.size else None
    condition = (
        largest / smallest
        if smallest is not None and largest is not None and smallest > 0.0
        else None
    )
    return {
        "planar_jacobian": planar,
        "position_jacobian": jacp,
        "singular_values": singular_values,
        "rank": int(np.linalg.matrix_rank(planar)),
        "condition_number": condition,
        "determinant": np.linalg.det(planar),
    }


def _model_facts(model: mujoco.MjModel, data: mujoco.MjData) -> dict[str, Any]:
    opt = model.opt
    option_names = (
        "timestep",
        "gravity",
        "wind",
        "magnetic",
        "density",
        "viscosity",
        "impratio",
        "tolerance",
        "ls_tolerance",
        "noslip_tolerance",
        "mpr_tolerance",
        "iterations",
        "ls_iterations",
        "noslip_iterations",
        "ccd_iterations",
        "sdf_iterations",
        "integrator",
        "cone",
        "jacobian",
        "solver",
    )
    options: dict[str, Any] = {}
    for name in option_names:
        try:
            value = getattr(opt, name)
        except AttributeError:
            options[name] = None
        else:
            options[name] = (
                _enum_value(value)
                if name in {"integrator", "cone", "jacobian", "solver"}
                else _array(value)
            )

    bodies = []
    for body_id in range(int(model.nbody)):
        bodies.append(
            {
                "id": body_id,
                "name": _object_name(model, mujoco.mjtObj.mjOBJ_BODY, body_id),
                "mass": model.body_mass[body_id],
                "inertia": model.body_inertia[body_id],
                "inertial_position": model.body_ipos[body_id],
                "inertial_quaternion": model.body_iquat[body_id],
            }
        )

    joints = []
    for joint_id in range(int(model.njnt)):
        dof_id = int(model.jnt_dofadr[joint_id])
        joints.append(
            {
                "id": joint_id,
                "name": _object_name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id),
                "type": _as_json(model.jnt_type[joint_id]),
                "qpos_address": int(model.jnt_qposadr[joint_id]),
                "dof_address": dof_id,
                "range": model.jnt_range[joint_id],
                "limited": model.jnt_limited[joint_id],
                "damping": model.dof_damping[dof_id],
                "armature": model.dof_armature[dof_id],
            }
        )

    actuators = []
    for actuator_id in range(int(model.nu)):
        record: dict[str, Any] = {
            "id": actuator_id,
            "name": _object_name(
                model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_id
            ),
        }
        for field in (
            "actuator_trnid",
            "actuator_ctrllimited",
            "actuator_ctrlrange",
            "actuator_forcelimited",
            "actuator_forcerange",
            "actuator_gear",
            "actuator_actlimited",
            "actuator_actrange",
        ):
            value = _optional_attribute(model, field)
            if value is not None:
                record[field.removeprefix("actuator_")] = value[actuator_id]
            else:
                record[field.removeprefix("actuator_")] = None
        actuators.append(record)

    geoms = []
    for geom_id in range(int(model.ngeom)):
        geoms.append(
            {
                "id": geom_id,
                "name": _object_name(model, mujoco.mjtObj.mjOBJ_GEOM, geom_id),
                "type": _as_json(model.geom_type[geom_id]),
                "body_id": int(model.geom_bodyid[geom_id]),
                "contype": model.geom_contype[geom_id],
                "conaffinity": model.geom_conaffinity[geom_id],
                "condim": model.geom_condim[geom_id],
                "margin": model.geom_margin[geom_id],
                "gap": model.geom_gap[geom_id],
            }
        )

    mujoco.mj_resetData(model, data)
    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)
    mass_matrix = np.zeros((int(model.nv), int(model.nv)), dtype=np.float64)
    mujoco.mj_fullM(model, data, mass_matrix)

    return {
        "xml_path": str(TWO_JOINT_ARM_XML_PATH),
        "dimensions": {
            "nq": model.nq,
            "nv": model.nv,
            "nu": model.nu,
            "ngeom": model.ngeom,
            "nbody": model.nbody,
            "njnt": model.njnt,
            "nsite": model.nsite,
            "nconmax": _optional_attribute(model, "nconmax"),
        },
        "timing": {
            "physics_timestep": opt.timestep,
            "control_interval_seconds": float(opt.timestep) * FRAME_SKIP,
            "physics_substeps_per_visible_control_interval": FRAME_SKIP,
        },
        "options": options,
        "bodies": bodies,
        "joints": joints,
        "actuators": actuators,
        "geoms": geoms,
        "mass_matrix_at_q_zero": mass_matrix,
        "compiled_initial_contact_summary": _contact_summary(model, data),
    }


def _ik_cases(
    model: mujoco.MjModel, data: mujoco.MjData, site_id: int
) -> tuple[list[dict[str, Any]], list[np.ndarray]]:
    mujoco.mj_resetData(model, data)
    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)
    site_height = float(data.site_xpos[site_id][2])
    joint_ranges = np.asarray(model.jnt_range[:2], dtype=np.float64)
    cases: list[dict[str, Any]] = []
    valid_qs: list[np.ndarray] = []

    for radius in IK_RADII:
        cosine = (
            radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
        ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
        elbow_magnitude = math.acos(float(np.clip(cosine, -1.0, 1.0)))
        for bearing in IK_BEARINGS:
            target = _target_position(radius, bearing, site_height)
            for branch_sign in (1, -1):
                elbow = branch_sign * elbow_magnitude
                shoulder = _wrap_to_pi(
                    bearing
                    - math.atan2(
                        FOREARM_LENGTH * math.sin(elbow),
                        UPPER_ARM_LENGTH + FOREARM_LENGTH * math.cos(elbow),
                    )
                )
                q = np.array([shoulder, elbow], dtype=np.float64)
                margins = np.minimum(q - joint_ranges[:, 0], joint_ranges[:, 1] - q)
                valid = bool(np.all(margins >= 0.0))
                data.qpos[:2] = q
                data.qvel[:2] = 0.0
                mujoco.mj_forward(model, data)
                site_position = np.asarray(data.site_xpos[site_id]).copy()
                fk_xy = _forward_kinematics(q)
                jacobian = _jacobian_metadata(model, data, site_id)
                case = {
                    "radius": radius,
                    "bearing": bearing,
                    "branch_sign": branch_sign,
                    "q": q,
                    "target_position": target,
                    "site_position": site_position,
                    "analytic_fk_xy": fk_xy,
                    "fk_residual": np.linalg.norm(
                        np.concatenate((fk_xy, [site_height])) - target
                    ),
                    "valid_joint_limits": valid,
                    "joint_limit_margins": margins,
                    "joint_limit_margin_minimum": np.min(margins),
                    "invalid_reason": None
                    if valid
                    else "one_or_more_joint_limits_exceeded",
                    "jacobian": jacobian,
                    "contact_observation": _contact_summary(model, data),
                }
                cases.append(case)
                if valid:
                    valid_qs.append(q.copy())
    return cases, valid_qs


def _trace_sample(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    site_id: int,
    target: np.ndarray,
    phase: str,
    substep: int,
) -> dict[str, Any]:
    # mj_step integrates qpos/qvel after its forward-dynamics calculations.
    # Preserve those interval-start dynamics values before refreshing the
    # derived endpoint state below.
    interval_qacc = np.asarray(data.qacc).copy()
    interval_actuator_force = _optional_attribute(data, "actuator_force")
    interval_generalized_force = _optional_attribute(data, "qfrc_actuator")
    interval_contacts = _contact_summary(model, data)
    endpoint_time = float(data.time)
    interval_start_time = endpoint_time - float(model.opt.timestep)

    # Refresh kinematics, velocities, acceleration, and contacts so the
    # endpoint quantities correspond to the post-integration qpos/qvel/time.
    mujoco.mj_forward(model, data)
    site_position, site_velocity = _site_state(model, data, site_id)
    endpoint_contacts = _contact_summary(model, data)
    endpoint_actuator_force = _optional_attribute(data, "actuator_force")
    endpoint_generalized_force = _optional_attribute(data, "qfrc_actuator")
    return {
        "phase": phase,
        "substep": substep,
        "time": endpoint_time,
        "interval_start_time": interval_start_time,
        "qpos": np.asarray(data.qpos).copy(),
        "qvel": np.asarray(data.qvel).copy(),
        "qacc": interval_qacc,
        "qacc_semantics": "interval_start_dynamics",
        "endpoint_qacc": np.asarray(data.qacc).copy(),
        "site_position": site_position,
        "site_velocity": site_velocity,
        "target_position": target,
        "target_distance": np.linalg.norm(site_position - target),
        "ctrl": np.asarray(data.ctrl).copy(),
        "actuator_force": interval_actuator_force,
        "generalized_actuator_force": interval_generalized_force,
        "force_semantics": "interval_start_dynamics",
        "endpoint_actuator_force": endpoint_actuator_force,
        "endpoint_generalized_actuator_force": endpoint_generalized_force,
        "contact_count": endpoint_contacts["total_contacts"],
        "max_contact_force_norm": endpoint_contacts["max_contact_force_norm"],
        "contacts": endpoint_contacts["contacts"],
        "interval_contact_count": interval_contacts["total_contacts"],
        "interval_max_contact_force_norm": interval_contacts[
            "max_contact_force_norm"
        ],
        "interval_contacts": interval_contacts["contacts"],
    }


def _trace_aggregate(
    trace: list[dict[str, Any]],
    action: np.ndarray,
    ctrlrange: np.ndarray | None,
    initial_qvel: np.ndarray,
    initial_distance: float,
    pulse_end_qvel: np.ndarray | None = None,
) -> dict[str, Any]:
    qvels = [np.asarray(item["qvel"], dtype=np.float64) for item in trace]
    qaccs = [np.asarray(item["qacc"], dtype=np.float64) for item in trace]
    distances = [float(item["target_distance"]) for item in trace]
    final_qvel = qvels[-1] if qvels else initial_qvel
    pulse_end_qvel = final_qvel if pulse_end_qvel is None else pulse_end_qvel
    saturation = False
    if ctrlrange is not None and ctrlrange.shape == (2, 2):
        lower = ctrlrange[:, 0]
        upper = ctrlrange[:, 1]
        saturation = bool(
            np.any(np.isclose(action, lower)) or np.any(np.isclose(action, upper))
        )
    speed_initial = float(np.linalg.norm(initial_qvel))
    speed_pulse_end = float(np.linalg.norm(pulse_end_qvel))
    speed_final = float(np.linalg.norm(final_qvel))
    return {
        "initial_qvel": initial_qvel,
        "final_qvel": final_qvel,
        "peak_speed": max(
            [speed_initial] + [float(np.linalg.norm(value)) for value in qvels]
        ),
        "peak_acceleration": max(
            [0.0] + [float(np.linalg.norm(value)) for value in qaccs]
        ),
        "initial_distance": initial_distance,
        "final_distance": distances[-1] if distances else initial_distance,
        "distance_change": (
            distances[-1] - initial_distance if distances else 0.0
        ),
        "pulse_end_speed": speed_pulse_end,
        "final_speed": speed_final,
        "braking_speed_reduction": speed_pulse_end - speed_final,
        "control_saturated": saturation,
        "any_contact": any(
            int(item["contact_count"]) > 0
            or int(item["interval_contact_count"]) > 0
            for item in trace
        ),
        "maximum_contact_force_norm": max(
            [
                float(force)
                for item in trace
                for force in (
                    item["max_contact_force_norm"],
                    item["interval_max_contact_force_norm"],
                )
                if force is not None
            ],
            default=None,
        ),
    }


def _response_case(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    site_id: int,
    q: np.ndarray,
    target: np.ndarray,
    action: tuple[float, float],
    ctrlrange: np.ndarray | None,
) -> dict[str, Any]:
    action_array = np.asarray(action, dtype=np.float64)
    mujoco.mj_resetData(model, data)
    data.qpos[: len(q)] = q
    data.qvel[:] = 0.0
    data.mocap_pos[0] = target
    mujoco.mj_forward(model, data)
    initial_site, _ = _site_state(model, data, site_id)
    initial_distance = float(np.linalg.norm(initial_site - target))
    initial_qvel = data.qvel.copy()
    data.ctrl[:] = action_array
    pulse_trace: list[dict[str, Any]] = []
    for substep in range(RESPONSE_SUBSTEPS):
        mujoco.mj_step(model, data)
        pulse_trace.append(
            _trace_sample(
                model, data, site_id, target, "pulse", substep + 1
            )
        )

    braking_trace: list[dict[str, Any]] = []
    braking_action = -action_array
    if np.any(np.abs(action_array) > 0.0):
        pulse_end_qvel = data.qvel.copy()
        data.ctrl[:] = braking_action
        for substep in range(RESPONSE_SUBSTEPS):
            mujoco.mj_step(model, data)
            braking_trace.append(
                _trace_sample(
                    model, data, site_id, target, "braking", substep + 1
                )
            )
    else:
        pulse_end_qvel = data.qvel.copy()

    full_trace = pulse_trace + braking_trace
    aggregate = _trace_aggregate(
        full_trace,
        action_array,
        ctrlrange,
        initial_qvel,
        initial_distance,
        pulse_end_qvel=pulse_end_qvel,
    )
    aggregate["pulse"] = _trace_aggregate(
        pulse_trace,
        action_array,
        ctrlrange,
        initial_qvel,
        initial_distance,
        pulse_end_qvel=pulse_end_qvel,
    )
    aggregate["braking"] = (
        _trace_aggregate(
            braking_trace,
            braking_action,
            ctrlrange,
            pulse_end_qvel,
            float(pulse_trace[-1]["target_distance"]),
        )
        if braking_trace
        else None
    )
    return {
        "initial_qpos": q,
        "target_position": target,
        "action": action_array,
        "opposite_action": braking_action,
        "pulse_substeps": RESPONSE_SUBSTEPS,
        "braking_substeps": len(braking_trace),
        "braking_performed": bool(braking_trace),
        "trace": full_trace,
        "aggregates": aggregate,
    }


def _response_cases(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    site_id: int,
    ik_cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ctrlrange_value = _optional_attribute(model, "actuator_ctrlrange")
    ctrlrange = (
        np.asarray(ctrlrange_value, dtype=np.float64)
        if ctrlrange_value is not None
        else None
    )
    mujoco.mj_resetData(model, data)
    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)
    zero_target = _target_position(0.14, 0.0, float(data.site_xpos[site_id][2]))
    configurations: list[dict[str, Any]] = [
        {
            "configuration": "q_zero",
            "q": np.zeros(2, dtype=np.float64),
            "target": zero_target,
            "radius": 0.14,
            "bearing": 0.0,
            "branch_sign": None,
        }
    ]
    for case in ik_cases:
        if case["valid_joint_limits"]:
            configurations.append(
                {
                    "configuration": "ik_branch",
                    "q": np.asarray(case["q"], dtype=np.float64),
                    "target": np.asarray(case["target_position"], dtype=np.float64),
                    "radius": case["radius"],
                    "bearing": case["bearing"],
                    "branch_sign": case["branch_sign"],
                }
            )

    responses: list[dict[str, Any]] = []
    for configuration in configurations:
        for action in RESPONSE_ACTIONS:
            record = _response_case(
                model,
                data,
                site_id,
                configuration["q"],
                configuration["target"],
                action,
                ctrlrange,
            )
            record.update(
                {
                    "configuration": configuration["configuration"],
                    "radius": configuration["radius"],
                    "bearing": configuration["bearing"],
                    "branch_sign": configuration["branch_sign"],
                }
            )
            responses.append(record)
    return responses


def measure() -> dict[str, Any]:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    site_id = mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_SITE, "end_effector"
    )
    if site_id < 0:
        raise RuntimeError("official XML does not contain end_effector site")

    ik_cases, _ = _ik_cases(model, data, site_id)
    facts = _model_facts(model, data)
    responses = _response_cases(model, data, site_id, ik_cases)
    return {
        "schema": "physics_baseline",
        "schema_version": SCHEMA_VERSION,
        "protocol": {
            "description": (
                "Deterministic MuJoCo compiled-model, analytic-kinematics, "
                "contact, and matched constant-action response measurement."
            ),
            "mujoco_api": "native mujoco 3.12.0",
            "physics_substeps_per_response_phase": RESPONSE_SUBSTEPS,
            "trace_alignment": (
                "qpos, qvel, site kinematics, distance, and contact fields "
                "are post-step endpoint values; qacc and force fields retain "
                "the interval-start dynamics values and are explicitly "
                "labeled, with endpoint dynamics also recorded."
            ),
            "braking_rule": (
                "The opposite action is applied for ten substeps after each "
                "nonzero pulse; zero action has no braking phase."
            ),
            "zero_posture_target": {
                "radius": 0.14,
                "bearing": 0.0,
                "description": "fixed official-range target for q=0 responses",
            },
        },
        "official_constants": {
            "target_radius_range": TARGET_RADIUS_RANGE,
            "ik_radii": IK_RADII,
            "ik_bearings": IK_BEARINGS,
            "frame_skip": FRAME_SKIP,
            "hold_seconds": HOLD_SECONDS,
            "success_threshold": SUCCESS_THRESHOLD,
            "upper_arm_length": UPPER_ARM_LENGTH,
            "forearm_length": FOREARM_LENGTH,
            "max_reach": MAX_REACH,
            "response_actions": RESPONSE_ACTIONS,
            "response_substeps": RESPONSE_SUBSTEPS,
        },
        "model_facts": facts,
        "geometry_cases": {
            "ik_branches": ik_cases,
            "representative_zero_posture": {
                "q": np.zeros(2, dtype=np.float64),
                "contact_observation": facts["compiled_initial_contact_summary"],
            },
        },
        "response_cases": responses,
    }


def _write_atomically(output: Path, payload: dict[str, Any]) -> None:
    output = output.expanduser()
    if output.exists() and output.is_dir():
        raise ValueError(f"output path is a directory: {output}")
    parent = output.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(_as_json(payload), handle, allow_nan=False, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, output)
    except Exception:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        _write_atomically(args.output, measure())
    except Exception as exc:
        print(f"physics baseline measurement failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
