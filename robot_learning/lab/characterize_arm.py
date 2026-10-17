"""Measure compiled two-joint-arm geometry and matched known-action responses.

This module is intentionally a measurement instrument rather than a controller:
it loads the contractual MuJoCo model, records compiled quantities, computes
analytical planar inverse-kinematic diagnostics, and records deterministic
unit-action responses.  It does not train or evaluate a policy.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import (
    FOREARM_LENGTH,
    TWO_JOINT_ARM_XML_PATH,
    UPPER_ARM_LENGTH,
)
from contracts.task_spec import FRAME_SKIP


SCHEMA_NAME = "two_joint_arm_characterization"
SCHEMA_VERSION = 1
PHYSICS_STEPS_PER_CONTROL_INTERVAL = FRAME_SKIP
EXPECTED_PHYSICS_TIMESTEP_S = 0.002
EXPECTED_CONTROL_INTERVAL_S = 0.020
GRID_RADII_M = (0.06, 0.14, 0.20)
GRID_ANGLE_COUNT = 8
REPRESENTATIVE_ANGLE_RAD = 0.0
TRAJECTORY_CONTROL_INTERVALS = 1 + 50
IMPULSE_CONTROL_INTERVALS = 1
RANK_TOLERANCE = 1e-12

JOINT_NAMES = ("shoulder", "elbow")
ACTUATOR_NAMES = ("shoulder", "elbow")
SITE_NAME = "end_effector"

_OPTION_FIELDS = (
    "timestep",
    "integrator",
    "cone",
    "jacobian",
    "solver",
    "iterations",
    "ls_iterations",
    "noslip_iterations",
    "sdf_initpoints",
    "sdf_iterations",
    "disableflags",
    "disableactuator",
    "enableflags",
    "fwdinv",
    "island",
    "impratio",
    "tolerance",
    "ls_tolerance",
    "noslip_tolerance",
    "ccd_tolerance",
    "gravity",
    "wind",
    "magnetic",
    "density",
    "viscosity",
    "o_margin",
    "o_solref",
    "o_solimp",
    "o_friction",
)


def _json_value(value: Any) -> Any:
    """Convert MuJoCo and NumPy values into strict-JSON-compatible values."""

    if isinstance(value, np.ndarray):
        return [_json_value(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return _json_value(value.item())
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return str(value)


def _finite_float(value: float, *, label: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise RuntimeError(f"non-finite {label}: {result!r}")
    return result


def _finite_list(values: Iterable[float], *, label: str) -> list[float]:
    return [_finite_float(value, label=label) for value in values]


def _wrap_to_pi(angle: float) -> float:
    wrapped = (float(angle) + math.pi) % (2.0 * math.pi) - math.pi
    # Keep +pi available for callers that explicitly supplied it only through
    # the numerical tolerance at a joint limit; -pi is the canonical value.
    return wrapped


def _planar_fk(q: np.ndarray) -> np.ndarray:
    shoulder, elbow = (float(q[0]), float(q[1]))
    forearm_angle = shoulder + elbow
    return np.array(
        [
            UPPER_ARM_LENGTH * math.cos(shoulder)
            + FOREARM_LENGTH * math.cos(forearm_angle),
            UPPER_ARM_LENGTH * math.sin(shoulder)
            + FOREARM_LENGTH * math.sin(forearm_angle),
        ],
        dtype=np.float64,
    )


def _planar_jacobian(q: np.ndarray) -> np.ndarray:
    shoulder, elbow = (float(q[0]), float(q[1]))
    forearm_angle = shoulder + elbow
    return np.array(
        [
            [
                -UPPER_ARM_LENGTH * math.sin(shoulder)
                - FOREARM_LENGTH * math.sin(forearm_angle),
                -FOREARM_LENGTH * math.sin(forearm_angle),
            ],
            [
                UPPER_ARM_LENGTH * math.cos(shoulder)
                + FOREARM_LENGTH * math.cos(forearm_angle),
                FOREARM_LENGTH * math.cos(forearm_angle),
            ],
        ],
        dtype=np.float64,
    )


def _jacobian_diagnostics(jacobian: np.ndarray) -> dict[str, Any]:
    singular_values = np.linalg.svd(jacobian, compute_uv=False)
    scale = float(singular_values[0]) if singular_values.size else 0.0
    rank = int(np.count_nonzero(singular_values > RANK_TOLERANCE * scale))
    condition_number: float | None
    if singular_values.size == 0 or singular_values[-1] <= RANK_TOLERANCE * scale:
        condition_number = None
    else:
        condition_number = _finite_float(
            singular_values[0] / singular_values[-1],
            label="Jacobian condition number",
        )
    return {
        "matrix_m_per_rad": [
            _finite_list(row, label="Jacobian entry") for row in jacobian
        ],
        "determinant_m2_per_rad2": _finite_float(
            np.linalg.det(jacobian), label="Jacobian determinant"
        ),
        "singular_values_m_per_rad": _finite_list(
            singular_values, label="Jacobian singular value"
        ),
        "rank": rank,
        "rank_tolerance_relative": RANK_TOLERANCE,
        "condition_number": condition_number,
    }


def _joint_limit_entry(
    q: np.ndarray, joint_ranges: np.ndarray
) -> tuple[bool, list[bool]]:
    checks = [
        bool(
            float(joint_ranges[index, 0]) - RANK_TOLERANCE
            <= float(q[index])
            <= float(joint_ranges[index, 1]) + RANK_TOLERANCE
        )
        for index in range(2)
    ]
    return all(checks), checks


def _ik_solution(
    radius_m: float,
    angle_rad: float,
    elbow_sign: int,
    joint_ranges: np.ndarray,
) -> dict[str, Any]:
    target = np.array(
        [radius_m * math.cos(angle_rad), radius_m * math.sin(angle_rad)],
        dtype=np.float64,
    )
    cosine = (
        radius_m * radius_m
        - UPPER_ARM_LENGTH * UPPER_ARM_LENGTH
        - FOREARM_LENGTH * FOREARM_LENGTH
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    if cosine < -1.0 - 1e-12 or cosine > 1.0 + 1e-12:
        raise ValueError(
            f"radius {radius_m} m has no planar IK solution "
            f"(cosine={cosine})"
        )
    cosine = float(np.clip(cosine, -1.0, 1.0))
    elbow = float(elbow_sign * math.acos(cosine))
    shoulder = _wrap_to_pi(
        angle_rad
        - math.atan2(
            FOREARM_LENGTH * math.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * math.cos(elbow),
        )
    )
    q = np.array([shoulder, elbow], dtype=np.float64)
    fk = _planar_fk(q)
    jacobian = _planar_jacobian(q)
    all_feasible, per_joint = _joint_limit_entry(q, joint_ranges)
    diagnostics = _jacobian_diagnostics(jacobian)
    branch_name = "positive_elbow" if elbow_sign > 0 else "negative_elbow"
    return {
        "branch": branch_name,
        "target_xy_m": _finite_list(target, label="IK target"),
        "q_rad": _finite_list(q, label="IK joint angle"),
        "joint_limit_feasible": all_feasible,
        "joint_limit_feasible_by_joint": dict(
            zip(JOINT_NAMES, per_joint, strict=True)
        ),
        "fk_xy_m": _finite_list(fk, label="IK FK position"),
        "fk_residual_m": _finite_float(
            np.linalg.norm(fk - target), label="IK FK residual"
        ),
        "jacobian": diagnostics,
    }


def _name(model: mujoco.MjModel, object_type: Any, index: int) -> str:
    value = mujoco.mj_id2name(model, object_type, int(index))
    return str(value) if value is not None else f"unnamed_{index}"


def _find_ids(model: mujoco.MjModel) -> tuple[list[int], list[int], int]:
    joint_ids = [
        mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        for name in JOINT_NAMES
    ]
    actuator_ids = [
        mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, name)
        for name in ACTUATOR_NAMES
    ]
    site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, SITE_NAME)
    if any(index < 0 for index in (*joint_ids, *actuator_ids)) or site_id < 0:
        raise RuntimeError(
            "the compiled XML is missing a contractual joint, actuator, or site"
        )
    return joint_ids, actuator_ids, site_id


def _validate_model(
    model: mujoco.MjModel,
    joint_ids: list[int],
    actuator_ids: list[int],
) -> tuple[np.ndarray, np.ndarray]:
    if (model.nq, model.nv, model.nu) != (2, 2, 2):
        raise RuntimeError(
            "characterization requires the two-joint model dimensions "
            f"(nq,nv,nu)=(2,2,2), got {(model.nq, model.nv, model.nu)}"
        )
    if model.opt.timestep <= 0.0:
        raise RuntimeError("compiled model has a non-positive physics timestep")
    control_dt = float(model.opt.timestep) * PHYSICS_STEPS_PER_CONTROL_INTERVAL
    if not math.isclose(
        float(model.opt.timestep), EXPECTED_PHYSICS_TIMESTEP_S, rel_tol=0.0, abs_tol=1e-12
    ) or not math.isclose(
        control_dt, EXPECTED_CONTROL_INTERVAL_S, rel_tol=0.0, abs_tol=1e-12
    ):
        raise RuntimeError(
            "compiled model does not preserve the contractual 2 ms physics "
            f"and 20 ms visible control intervals: timestep={model.opt.timestep}"
        )
    joint_ranges = np.asarray(model.jnt_range[joint_ids], dtype=np.float64)
    if joint_ranges.shape != (2, 2) or not np.all(np.isfinite(joint_ranges)):
        raise RuntimeError("compiled joint ranges are missing or non-finite")
    if not np.all(joint_ranges[:, 0] < joint_ranges[:, 1]):
        raise RuntimeError("compiled joint ranges are impossible")
    if any(int(model.jnt_dofadr[index]) < 0 for index in joint_ids):
        raise RuntimeError("compiled joint DOF addresses are invalid")
    if any(int(model.actuator_trnid[index, 0]) < 0 for index in actuator_ids):
        raise RuntimeError("compiled actuator transmission addresses are invalid")
    return joint_ranges, np.asarray(model.jnt_dofadr[joint_ids], dtype=int)


def _compiled_options(model: mujoco.MjModel) -> dict[str, Any]:
    options: dict[str, Any] = {}
    for field in _OPTION_FIELDS:
        if hasattr(model.opt, field):
            options[field] = _json_value(getattr(model.opt, field))
    if "integrator" in options:
        integrator_codes = {
            int(mujoco.mjtIntegrator.mjINT_EULER): "euler",
            int(mujoco.mjtIntegrator.mjINT_RK4): "rk4",
            int(mujoco.mjtIntegrator.mjINT_IMPLICIT): "implicit",
            int(mujoco.mjtIntegrator.mjINT_IMPLICITFAST): "implicitfast",
        }
        options["integrator_name"] = integrator_codes.get(
            int(options["integrator"]), "unknown"
        )
    return options


def _compiled_facts(
    model: mujoco.MjModel,
    joint_ids: list[int],
    actuator_ids: list[int],
    joint_ranges: np.ndarray,
) -> dict[str, Any]:
    joint_records = []
    for index, joint_id in enumerate(joint_ids):
        dof = int(model.jnt_dofadr[joint_id])
        joint_records.append(
            {
                "name": JOINT_NAMES[index],
                "id": int(joint_id),
                "qpos_address": int(model.jnt_qposadr[joint_id]),
                "dof_address": dof,
                "range_rad": _finite_list(
                    joint_ranges[index], label="joint range"
                ),
                "limited": bool(model.jnt_limited[joint_id]),
                "damping_Nm_s_per_rad": _finite_float(
                    model.dof_damping[dof], label="joint damping"
                ),
                "armature_kg_m2": _finite_float(
                    model.dof_armature[dof], label="joint armature"
                ),
            }
        )

    actuator_records = []
    for index, actuator_id in enumerate(actuator_ids):
        actuator_records.append(
            {
                "name": ACTUATOR_NAMES[index],
                "id": int(actuator_id),
                "control_range": _finite_list(
                    model.actuator_ctrlrange[actuator_id],
                    label="actuator control range",
                ),
                "control_limited": bool(model.actuator_ctrllimited[actuator_id]),
                "gear": _finite_list(
                    model.actuator_gear[actuator_id], label="actuator gear"
                ),
            }
        )

    body_records = []
    for body_id in range(model.nbody):
        body_records.append(
            {
                "name": _name(model, mujoco.mjtObj.mjOBJ_BODY, body_id),
                "id": body_id,
                "mass_kg": _finite_float(
                    model.body_mass[body_id], label="body mass"
                ),
                "inertia_kg_m2": _finite_list(
                    model.body_inertia[body_id], label="body inertia"
                ),
            }
        )

    dimensions = {
        field: int(getattr(model, field))
        for field in (
            "nq",
            "nv",
            "nu",
            "na",
            "nbody",
            "njnt",
            "ngeom",
            "nsite",
            "nmocap",
        )
    }
    return {
        "xml_path": str(TWO_JOINT_ARM_XML_PATH),
        "dimensions": dimensions,
        "options": _compiled_options(model),
        "timestep_s": _finite_float(model.opt.timestep, label="timestep"),
        "gravity_m_per_s2": _finite_list(model.opt.gravity, label="gravity"),
        "joints": joint_records,
        "actuators": actuator_records,
        "bodies": body_records,
    }


def _dense_mass_matrix(
    model: mujoco.MjModel, data: mujoco.MjData, q: np.ndarray
) -> list[list[float]]:
    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    data.qpos[:2] = q
    data.ctrl[:] = 0.0
    mujoco.mj_forward(model, data)
    dense = np.zeros((model.nv, model.nv), dtype=np.float64, order="C")
    mujoco.mj_fullM(model, data, dense)
    if not np.all(np.isfinite(dense)):
        raise RuntimeError("compiled dense mass matrix contains non-finite values")
    return _json_value(dense)


def _kinematics(
    model: mujoco.MjModel, data: mujoco.MjData, joint_ranges: np.ndarray
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    reset_q = np.zeros(2, dtype=np.float64)
    reset_fk = _planar_fk(reset_q)
    reset_jacobian = _planar_jacobian(reset_q)
    reset = {
        "q_rad": [0.0, 0.0],
        "fk_xy_m": _finite_list(reset_fk, label="reset FK"),
        "jacobian": _jacobian_diagnostics(reset_jacobian),
    }

    grid: list[dict[str, Any]] = []
    for radius_m in GRID_RADII_M:
        for angle_rad in np.linspace(
            -math.pi, math.pi, GRID_ANGLE_COUNT, endpoint=False
        ):
            branches = [
                _ik_solution(radius_m, float(angle_rad), sign, joint_ranges)
                for sign in (1, -1)
            ]
            grid.append(
                {
                    "radius_m": radius_m,
                    "angle_rad": _finite_float(angle_rad, label="grid angle"),
                    "branches": branches,
                    "any_joint_limit_feasible": any(
                        branch["joint_limit_feasible"] for branch in branches
                    ),
                }
            )

    representative_states: list[dict[str, Any]] = []
    for radius_m in GRID_RADII_M:
        branches = [
            _ik_solution(
                radius_m, REPRESENTATIVE_ANGLE_RAD, sign, joint_ranges
            )
            for sign in (1, -1)
        ]
        feasible = next(
            (branch for branch in branches if branch["joint_limit_feasible"]),
            None,
        )
        if feasible is None:
            raise RuntimeError(
                f"no feasible IK branch for representative radius {radius_m} m"
            )
        representative_states.append(
            {
                "label": f"ik_radius_{radius_m:.2f}m",
                "radius_m": radius_m,
                "angle_rad": REPRESENTATIVE_ANGLE_RAD,
                "branch": feasible["branch"],
                "q_rad": feasible["q_rad"],
                "fk_residual_m": feasible["fk_residual_m"],
            }
        )
    del model, data
    return (
        {
            "link_lengths_m": {
                "upper_arm": UPPER_ARM_LENGTH,
                "forearm": FOREARM_LENGTH,
            },
            "reset": reset,
            "grid": {
                "radii_m": list(GRID_RADII_M),
                "angles_rad": [
                    _finite_float(angle, label="grid angle")
                    for angle in np.linspace(
                        -math.pi, math.pi, GRID_ANGLE_COUNT, endpoint=False
                    )
                ],
                "angle_count": GRID_ANGLE_COUNT,
                "angle_spacing_rad": 2.0 * math.pi / GRID_ANGLE_COUNT,
                "entries": grid,
            },
            "representative_feasible_states": representative_states,
        },
        representative_states,
    )


def _set_state(
    model: mujoco.MjModel, data: mujoco.MjData, q: np.ndarray, qvel: np.ndarray
) -> None:
    mujoco.mj_resetData(model, data)
    data.qpos[:2] = q
    data.qvel[:2] = qvel
    data.ctrl[:] = 0.0
    mujoco.mj_forward(model, data)


def _trajectory_record(
    data: mujoco.MjData,
    site_id: int,
    dof_addresses: np.ndarray,
    control_step: int,
    action: np.ndarray,
) -> dict[str, Any]:
    q = np.asarray(data.qpos[:2], dtype=np.float64).copy()
    qvel = np.asarray(data.qvel[dof_addresses], dtype=np.float64).copy()
    endpoint = np.asarray(data.site(site_id).xpos, dtype=np.float64).copy()
    endpoint_speed = _planar_jacobian(q) @ qvel
    return {
        "control_step": int(control_step),
        "time_s": _finite_float(
            control_step * EXPECTED_CONTROL_INTERVAL_S, label="trajectory time"
        ),
        "q_rad": _finite_list(q, label="trajectory joint angle"),
        "qvel_rad_per_s": _finite_list(qvel, label="trajectory joint speed"),
        "end_effector_position_m": _finite_list(
            endpoint, label="trajectory endpoint position"
        ),
        "end_effector_speed_m_per_s": _finite_float(
            np.linalg.norm(endpoint_speed), label="trajectory endpoint speed"
        ),
        "applied_action": _finite_list(action, label="trajectory action"),
    }


def _response_trajectory(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    site_id: int,
    dof_addresses: np.ndarray,
    initial_state: dict[str, Any],
    impulse_action: np.ndarray,
) -> dict[str, Any]:
    q = np.asarray(initial_state["q_rad"], dtype=np.float64)
    _set_state(model, data, q, np.zeros(2, dtype=np.float64))
    records = [
        _trajectory_record(
            data,
            site_id,
            dof_addresses,
            0,
            np.zeros(2, dtype=np.float64),
        )
    ]
    for control_step in range(1, TRAJECTORY_CONTROL_INTERVALS + 1):
        action = (
            impulse_action
            if control_step <= IMPULSE_CONTROL_INTERVALS
            else np.zeros(2, dtype=np.float64)
        )
        data.ctrl[:] = action
        for _ in range(PHYSICS_STEPS_PER_CONTROL_INTERVAL):
            mujoco.mj_step(model, data)
        records.append(
            _trajectory_record(
                data,
                site_id,
                dof_addresses,
                control_step,
                action,
            )
        )

    initial_endpoint = np.asarray(
        records[0]["end_effector_position_m"], dtype=np.float64
    )
    joint_speeds = np.array(
        [np.linalg.norm(record["qvel_rad_per_s"]) for record in records],
        dtype=np.float64,
    )
    endpoint_speeds = np.array(
        [record["end_effector_speed_m_per_s"] for record in records],
        dtype=np.float64,
    )
    displacements = np.array(
        [
            np.linalg.norm(
                np.asarray(record["end_effector_position_m"]) - initial_endpoint
            )
            for record in records
        ],
        dtype=np.float64,
    )
    start_joint_speed = float(joint_speeds[IMPULSE_CONTROL_INTERVALS])
    start_endpoint_speed = float(endpoint_speeds[IMPULSE_CONTROL_INTERVALS])

    def fraction_remaining(end_value: float, start_value: float) -> float | None:
        if start_value <= RANK_TOLERANCE:
            return None
        return _finite_float(end_value / start_value, label="decay fraction")

    summary = {
        "speed_norm_definitions": {
            "joint_speed": "Euclidean norm of qvel, rad/s",
            "endpoint_speed": "Euclidean norm of analytical planar J(q)qvel, m/s",
        },
        "displacement_definition": (
            "Euclidean endpoint displacement from the trajectory's initial "
            "endpoint position, m"
        ),
        "peak_joint_speed_rad_per_s": _finite_float(
            np.max(joint_speeds), label="peak joint speed"
        ),
        "peak_endpoint_speed_m_per_s": _finite_float(
            np.max(endpoint_speeds), label="peak endpoint speed"
        ),
        "peak_endpoint_displacement_m": _finite_float(
            np.max(displacements), label="peak endpoint displacement"
        ),
        "post_impulse_decay": {
            "zero_torque_start_control_step": IMPULSE_CONTROL_INTERVALS,
            "zero_torque_end_control_step": TRAJECTORY_CONTROL_INTERVALS,
            "joint_speed_start_rad_per_s": _finite_float(
                start_joint_speed, label="post-impulse joint speed"
            ),
            "joint_speed_end_rad_per_s": _finite_float(
                joint_speeds[-1], label="final joint speed"
            ),
            "joint_speed_fraction_remaining": fraction_remaining(
                float(joint_speeds[-1]), start_joint_speed
            ),
            "endpoint_speed_start_m_per_s": _finite_float(
                start_endpoint_speed, label="post-impulse endpoint speed"
            ),
            "endpoint_speed_end_m_per_s": _finite_float(
                endpoint_speeds[-1], label="final endpoint speed"
            ),
            "endpoint_speed_fraction_remaining": fraction_remaining(
                float(endpoint_speeds[-1]), start_endpoint_speed
            ),
            "endpoint_displacement_at_zero_torque_start_m": _finite_float(
                displacements[IMPULSE_CONTROL_INTERVALS],
                label="post-impulse displacement",
            ),
            "endpoint_displacement_at_end_m": _finite_float(
                displacements[-1], label="final endpoint displacement"
            ),
            "interpretation": "reported values only; no decay conclusion is inferred",
        },
    }
    return {
        "initial_state": initial_state,
        "impulse_action": _finite_list(impulse_action, label="impulse action"),
        "impulse_control_intervals": IMPULSE_CONTROL_INTERVALS,
        "zero_torque_control_intervals": TRAJECTORY_CONTROL_INTERVALS
        - IMPULSE_CONTROL_INTERVALS,
        "physics_steps_per_control_interval": PHYSICS_STEPS_PER_CONTROL_INTERVAL,
        "sample_semantics": (
            "sample 0 is the initial state; sample k>=1 is the state after "
            "the recorded action was held for one control interval"
        ),
        "samples": records,
        "summary": summary,
    }


def _trajectories(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    site_id: int,
    dof_addresses: np.ndarray,
    representative_states: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    initial_states = [
        {
            "label": "contractual_reset",
            "q_rad": [0.0, 0.0],
            "qvel_rad_per_s": [0.0, 0.0],
        },
        *representative_states,
    ]
    actions = (
        np.array([1.0, 0.0], dtype=np.float64),
        np.array([0.0, 1.0], dtype=np.float64),
    )
    return [
        _response_trajectory(
            model,
            data,
            site_id,
            dof_addresses,
            initial_state,
            action,
        )
        for initial_state in initial_states
        for action in actions
    ]


def characterize() -> dict[str, Any]:
    """Build the JSON-serializable characterization artifact in memory."""

    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    joint_ids, actuator_ids, site_id = _find_ids(model)
    joint_ranges, dof_addresses = _validate_model(
        model, joint_ids, actuator_ids
    )
    facts = _compiled_facts(model, joint_ids, actuator_ids, joint_ranges)
    kinematics, representative_states = _kinematics(
        model, data, joint_ranges
    )

    representative_configs = [
        {"label": "contractual_reset", "q_rad": [0.0, 0.0]},
        *[
            {
                "label": state["label"],
                "q_rad": state["q_rad"],
                "radius_m": state["radius_m"],
                "branch": state["branch"],
            }
            for state in representative_states
        ],
    ]
    mass_matrices = []
    for configuration in representative_configs:
        q = np.asarray(configuration["q_rad"], dtype=np.float64)
        mass_matrices.append(
            {
                **configuration,
                "mass_matrix_kg_m2": _dense_mass_matrix(model, data, q),
            }
        )
    trajectories = _trajectories(
        model, data, site_id, dof_addresses, representative_states
    )
    control_dt = float(model.opt.timestep) * PHYSICS_STEPS_PER_CONTROL_INTERVAL
    artifact = {
        "schema": {"name": SCHEMA_NAME, "version": SCHEMA_VERSION},
        "measurement": {
            "kind": "compiled_model_and_known_action_response",
            "tool": "robot_learning.lab.characterize_arm",
            "policy_training_or_evaluation": False,
            "scientific_conclusion_inferred": False,
        },
        "source": {
            "xml_path": str(TWO_JOINT_ARM_XML_PATH),
            "xml_loaded_via": "contracts.robots.two_joint_arm.TWO_JOINT_ARM_XML_PATH",
        },
        "units": {
            "length": "m",
            "angle": "rad",
            "time": "s",
            "joint_speed": "rad/s",
            "endpoint_speed": "m/s",
            "mass": "kg",
            "inertia": "kg*m^2",
            "action": "dimensionless, applied to actuator control",
            "generalized_torque": "N*m (nominal gear-scaled motor output)",
        },
        "timing": {
            "physics_timestep_s": _finite_float(
                model.opt.timestep, label="physics timestep"
            ),
            "physics_steps_per_control_interval": PHYSICS_STEPS_PER_CONTROL_INTERVAL,
            "control_interval_s": _finite_float(
                control_dt, label="control interval"
            ),
            "expected_control_interval_s": EXPECTED_CONTROL_INTERVAL_S,
            "control_rate_hz": 1.0 / EXPECTED_CONTROL_INTERVAL_S,
            "trajectory_impulse_intervals": IMPULSE_CONTROL_INTERVALS,
            "trajectory_zero_torque_intervals": TRAJECTORY_CONTROL_INTERVALS
            - IMPULSE_CONTROL_INTERVALS,
        },
        "compiled_model": facts,
        "analytical_planar_kinematics": kinematics,
        "dense_mass_matrices": {
            "matrix_units": "kg*m^2 generalized mass for [shoulder, elbow] coordinates",
            "representative_configurations": mass_matrices,
        },
        "known_action_response_trajectories": trajectories,
    }
    # A strict serialization pass catches accidental NumPy scalars, infinities,
    # and other values before the caller attempts to write the artifact.
    json.dumps(artifact, allow_nan=False)
    return artifact


def _output_path(argument: str) -> Path:
    if not argument.strip():
        raise ValueError("output JSON path must not be empty")
    path = Path(argument)
    if path.exists() and path.is_dir():
        raise ValueError(f"output path is a directory, not a JSON file: {path}")
    if not path.parent.exists():
        raise ValueError(f"output parent directory does not exist: {path.parent}")
    if not path.parent.is_dir():
        raise ValueError(f"output parent is not a directory: {path.parent}")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write compiled two-joint-arm characterization JSON."
    )
    parser.add_argument("output_json", help="path for the single JSON artifact")
    args = parser.parse_args(argv)
    try:
        output = _output_path(args.output_json)
        artifact = characterize()
        output.write_text(
            json.dumps(artifact, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except Exception as error:
        print(f"characterization failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
