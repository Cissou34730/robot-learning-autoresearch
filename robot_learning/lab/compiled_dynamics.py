"""Deterministic, mechanism-level measurements of the compiled arm model.

This laboratory module does not construct an environment or a policy.  It
loads the operative XML directly through the same path used by the scenario
environment, and records simulator facts separately from derived summaries.
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


SEED = 0
INTERNAL_STEPS_PER_CONTROL = 10
SUCCESS_THRESHOLD = 0.01
PLANE_Z = 0.02
TRACE_TARGET = np.array([0.15, 0.04, PLANE_Z], dtype=np.float64)


def _jsonable(value: Any) -> Any:
    """Convert MuJoCo and NumPy values to strict JSON-compatible values."""
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, np.ndarray):
        return [_jsonable(item) for item in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return "nan" if math.isnan(value) else ("inf" if value > 0 else "-inf")
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _name(model: mujoco.MjModel, object_type: Any, object_id: int) -> str | None:
    value = mujoco.mj_id2name(model, object_type, object_id)
    return None if value is None else str(value)


def _require_model_structure(model: mujoco.MjModel) -> dict[str, int]:
    """Validate assumptions needed by this measurement, rather than guessing."""
    if (model.nq, model.nv, model.nu) != (2, 2, 2):
        raise RuntimeError(
            f"unexpected model dimensions nq/nv/nu={(model.nq, model.nv, model.nu)}"
        )
    if model.nmocap < 1:
        raise RuntimeError("the operative model has no mocap target")

    hinge = int(mujoco.mjtJoint.mjJNT_HINGE)
    joint_ids = []
    for joint_name in ("shoulder", "elbow"):
        joint_id = mujoco.mj_name2id(
            model, mujoco.mjtObj.mjOBJ_JOINT, joint_name
        )
        if joint_id < 0 or int(model.jnt_type[joint_id]) != hinge:
            raise RuntimeError(f"missing or non-hinge joint: {joint_name}")
        joint_ids.append(joint_id)

    site_id = mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_SITE, "end_effector"
    )
    if site_id < 0:
        raise RuntimeError("missing end_effector site")
    target_body_id = mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_BODY, "target"
    )
    if target_body_id < 0:
        raise RuntimeError("missing target body")
    mocap_id = int(model.body_mocapid[target_body_id])
    if mocap_id < 0 or mocap_id >= model.nmocap:
        raise RuntimeError("target body is not connected to a mocap state")

    transmission_joint_ids = np.asarray(model.actuator_trnid[:, 0], dtype=int)
    if not np.array_equal(transmission_joint_ids, np.asarray(joint_ids)):
        raise RuntimeError(
            "actuator transmissions do not match shoulder/elbow joint order"
        )
    return {
        "shoulder_joint_id": int(joint_ids[0]),
        "elbow_joint_id": int(joint_ids[1]),
        "site_id": int(site_id),
        "target_body_id": int(target_body_id),
        "mocap_id": mocap_id,
    }


def load_compiled_model() -> tuple[mujoco.MjModel, dict[str, int]]:
    """Load and structurally validate the operative MuJoCo XML."""
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    return model, _require_model_structure(model)


def planar_forward_kinematics(qpos: np.ndarray | list[float]) -> np.ndarray:
    """Independent planar position formula used to define deterministic targets."""
    q = np.asarray(qpos, dtype=np.float64)
    if q.shape != (2,):
        raise ValueError(f"expected two joint positions, got shape {q.shape}")
    q1, q2 = q
    return np.array(
        [
            UPPER_ARM_LENGTH * np.cos(q1)
            + FOREARM_LENGTH * np.cos(q1 + q2),
            UPPER_ARM_LENGTH * np.sin(q1)
            + FOREARM_LENGTH * np.sin(q1 + q2),
            PLANE_Z,
        ],
        dtype=np.float64,
    )


def _set_state(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    ids: dict[str, int],
    qpos: np.ndarray | list[float],
    qvel: np.ndarray | list[float],
    target: np.ndarray,
) -> None:
    qpos_array = np.asarray(qpos, dtype=np.float64)
    qvel_array = np.asarray(qvel, dtype=np.float64)
    target_array = np.asarray(target, dtype=np.float64)
    if qpos_array.shape != (model.nq,) or qvel_array.shape != (model.nv,):
        raise ValueError("state arrays do not match compiled model dimensions")
    if target_array.shape != (3,):
        raise ValueError("target must have three Cartesian coordinates")
    mujoco.mj_resetData(model, data)
    data.qpos[:] = qpos_array
    data.qvel[:] = qvel_array
    data.ctrl[:] = 0.0
    data.mocap_pos[ids["mocap_id"]] = target_array
    mujoco.mj_forward(model, data)


def _site_position(model: mujoco.MjModel, data: mujoco.MjData, site_id: int) -> np.ndarray:
    return np.asarray(data.site_xpos[site_id], dtype=np.float64).copy()


def _trace_row(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    ids: dict[str, int],
    target: np.ndarray,
    internal_step: int,
    control_step: int,
    control: np.ndarray,
) -> dict[str, Any]:
    position = _site_position(model, data, ids["site_id"])
    error = position - target
    return {
        "internal_step": internal_step,
        "control_step": control_step,
        "time_seconds": (internal_step + 1) * float(model.opt.timestep),
        "qpos": np.asarray(data.qpos, dtype=np.float64).copy(),
        "qvel": np.asarray(data.qvel, dtype=np.float64).copy(),
        "ctrl": np.asarray(control, dtype=np.float64).copy(),
        "end_effector_position_m": position,
        "target_position_m": target.copy(),
        "error_m": error,
        "distance_m": float(np.linalg.norm(error)),
        "contact_count": int(data.ncon),
    }


def _rows_to_trace(rows: list[dict[str, Any]], initial: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "internal_step",
        "control_step",
        "time_seconds",
        "qpos",
        "qvel",
        "ctrl",
        "end_effector_position_m",
        "target_position_m",
        "error_m",
        "distance_m",
        "contact_count",
    )
    return {
        "initial": initial,
        "steps": {field: [row[field] for row in rows] for field in fields},
    }


def run_control_trace(
    model: mujoco.MjModel,
    ids: dict[str, int],
    *,
    qpos: np.ndarray | list[float],
    qvel: np.ndarray | list[float],
    target: np.ndarray | list[float],
    controls: np.ndarray | list[list[float]],
    internal_steps_per_control: int = INTERNAL_STEPS_PER_CONTROL,
) -> dict[str, Any]:
    """Reset, repeatedly apply held controls, and retain every internal state."""
    if internal_steps_per_control <= 0:
        raise ValueError("internal_steps_per_control must be positive")
    controls_array = np.asarray(controls, dtype=np.float64)
    if controls_array.ndim != 2 or controls_array.shape[1] != model.nu:
        raise ValueError("controls must have shape (control_steps, model.nu)")
    target_array = np.asarray(target, dtype=np.float64)
    data = mujoco.MjData(model)
    _set_state(model, data, ids, qpos, qvel, target_array)
    initial_position = _site_position(model, data, ids["site_id"])
    initial = {
        "qpos": np.asarray(data.qpos, dtype=np.float64).copy(),
        "qvel": np.asarray(data.qvel, dtype=np.float64).copy(),
        "ctrl": np.asarray(data.ctrl, dtype=np.float64).copy(),
        "end_effector_position_m": initial_position,
        "target_position_m": target_array.copy(),
        "error_m": initial_position - target_array,
        "distance_m": float(np.linalg.norm(initial_position - target_array)),
        "time_seconds": 0.0,
    }

    rows: list[dict[str, Any]] = []
    internal_step = 0
    for control_step, control in enumerate(controls_array):
        data.ctrl[:] = control
        for _ in range(internal_steps_per_control):
            mujoco.mj_step(model, data)
            rows.append(
                _trace_row(
                    model,
                    data,
                    ids,
                    target_array,
                    internal_step,
                    control_step,
                    control,
                )
            )
            internal_step += 1
    return _rows_to_trace(rows, initial)


def summarize_distance_trace(
    distances: np.ndarray | list[float],
    *,
    tolerance: float,
    internal_steps_per_control: int,
) -> dict[str, Any]:
    """Compare all internal samples with only the control-boundary samples."""
    values = np.asarray(distances, dtype=np.float64)
    if values.ndim != 1 or values.size == 0:
        raise ValueError("distance trace must be a non-empty one-dimensional array")
    if internal_steps_per_control <= 0 or values.size % internal_steps_per_control:
        raise ValueError("distance trace length is not a whole number of controls")
    boundary_indices = np.arange(
        internal_steps_per_control - 1, values.size, internal_steps_per_control
    )
    interior_indices = np.setdiff1d(np.arange(values.size), boundary_indices)
    boundary_values = values[boundary_indices]
    interior_values = values[interior_indices]
    return {
        "sample_count": int(values.size),
        "control_boundary_count": int(boundary_values.size),
        "tolerance_m": float(tolerance),
        "minimum_distance_m": float(np.min(values)),
        "maximum_distance_m": float(np.max(values)),
        "boundary_maximum_distance_m": float(np.max(boundary_values)),
        "boundary_all_within_tolerance": bool(
            np.all(boundary_values <= tolerance)
        ),
        "continuous_all_within_tolerance": bool(np.all(values <= tolerance)),
        "interior_excursion_count": int(np.sum(interior_values > tolerance)),
        "interior_maximum_distance_m": float(np.max(interior_values))
        if interior_values.size
        else None,
    }


def _option_setting(option: Any, name: str) -> Any:
    value = getattr(option, name, None)
    if value is None:
        return None
    if isinstance(value, (int, np.integer)):
        return {"value": int(value), "name": str(value)}
    return _jsonable(value)


def _compiled_facts(model: mujoco.MjModel, ids: dict[str, int]) -> dict[str, Any]:
    option_fields = (
        "timestep",
        "integrator",
        "solver",
        "iterations",
        "ls_iterations",
        "tolerance",
        "ls_tolerance",
        "noslip_iterations",
        "noslip_tolerance",
        "ccd_iterations",
        "ccd_tolerance",
        "impratio",
        "cone",
        "jacobian",
    )
    arrays: dict[str, Any] = {
        "qpos0": model.qpos0,
        "joint_range": model.jnt_range,
        "joint_limited": model.jnt_limited,
        "dof_damping": model.dof_damping,
        "dof_armature": model.dof_armature,
        "dof_frictionloss": model.dof_frictionloss,
        "dof_M0": model.dof_M0,
        "body_mass": model.body_mass,
        "body_inertia": model.body_inertia,
        "body_pos": model.body_pos,
        "actuator_ctrlrange": model.actuator_ctrlrange,
        "actuator_forcerange": model.actuator_forcerange,
        "actuator_ctrllimited": model.actuator_ctrllimited,
        "actuator_forcelimited": model.actuator_forcelimited,
        "actuator_gear": model.actuator_gear,
        "actuator_dynprm": model.actuator_dynprm,
    }
    names = {
        "joint_names": [
            _name(model, mujoco.mjtObj.mjOBJ_JOINT, i) for i in range(model.njnt)
        ],
        "body_names": [
            _name(model, mujoco.mjtObj.mjOBJ_BODY, i) for i in range(model.nbody)
        ],
        "actuator_names": [
            _name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i)
            for i in range(model.nu)
        ],
    }
    return {
        "xml_path": str(TWO_JOINT_ARM_XML_PATH),
        "dimensions": {
            "nq": int(model.nq),
            "nv": int(model.nv),
            "nu": int(model.nu),
            "nbody": int(model.nbody),
            "njnt": int(model.njnt),
            "ndof": int(model.nv),
            "nsite": int(model.nsite),
            "nmocap": int(model.nmocap),
        },
        "option": {field: _option_setting(model.opt, field) for field in option_fields},
        "arrays": {key: _jsonable(value) for key, value in arrays.items()},
        "names": names,
        "resolved_ids": ids,
    }


def _trace_summary(trace: dict[str, Any]) -> dict[str, Any]:
    distances = trace["steps"]["distance_m"]
    return {
        "distance": summarize_distance_trace(
            distances,
            tolerance=SUCCESS_THRESHOLD,
            internal_steps_per_control=INTERNAL_STEPS_PER_CONTROL,
        ),
        "final_qpos": trace["steps"]["qpos"][-1],
        "final_qvel": trace["steps"]["qvel"][-1],
        "final_distance_m": distances[-1],
        "maximum_contact_count": max(trace["steps"]["contact_count"], default=0),
    }


def collect_measurement() -> dict[str, Any]:
    model, ids = load_compiled_model()
    parameters = {
        "seed": SEED,
        "units": {
            "time": "s",
            "distance": "m",
            "joint_position": "rad",
            "joint_velocity": "rad/s",
            "control": "dimensionless command in compiled ctrlrange",
            "nominal_motor_torque": "model force units after actuator transmission",
        },
        "internal_timestep_seconds": float(model.opt.timestep),
        "control_interval_seconds": float(
            model.opt.timestep * INTERNAL_STEPS_PER_CONTROL
        ),
        "internal_steps_per_control": INTERNAL_STEPS_PER_CONTROL,
        "success_threshold_m": SUCCESS_THRESHOLD,
        "fixed_targets": {
            "torque_and_decay_target_m": TRACE_TARGET,
        },
        "fixed_configurations_rad": {
            "reset": [0.0, 0.0],
            "non_singular_torque_step": [0.6, -0.8],
            "free_decay": [0.55, -0.75],
            "near_tolerance": [0.65, -0.9],
        },
    }

    torque_cases = (
        ("reset", [0.0, 0.0], [0.0, 0.0], [1.0, 0.0]),
        ("non_singular", [0.6, -0.8], [0.0, 0.0], [1.0, -1.0]),
    )
    torque_responses: list[dict[str, Any]] = []
    for name, qpos, qvel, control in torque_cases:
        controls = np.repeat(
            np.asarray([control], dtype=np.float64), 4, axis=0
        )
        trace = run_control_trace(
            model,
            ids,
            qpos=qpos,
            qvel=qvel,
            target=TRACE_TARGET,
            controls=controls,
        )
        torque_responses.append(
            {
                "name": name,
                "initial_qpos_rad": qpos,
                "initial_qvel_rad_per_s": qvel,
                "held_control": control,
                "control_steps": int(len(controls)),
                "internal_steps": int(len(trace["steps"]["time_seconds"])),
                "trace": trace,
            }
        )

    decay_qpos = np.asarray([0.55, -0.75], dtype=np.float64)
    decay_qvel = np.asarray([0.8, -0.5], dtype=np.float64)
    decay_controls = np.zeros((5, model.nu), dtype=np.float64)
    decay_trace = run_control_trace(
        model,
        ids,
        qpos=decay_qpos,
        qvel=decay_qvel,
        target=TRACE_TARGET,
        controls=decay_controls,
    )

    near_qpos = np.asarray([0.65, -0.9], dtype=np.float64)
    near_target = planar_forward_kinematics(near_qpos)
    near_target[0] += 0.0085
    near_controls = np.asarray(
        [
            [0.35, -0.25],
            [-0.35, 0.25],
            [0.20, -0.15],
            [-0.20, 0.15],
            [0.0, 0.0],
            [0.0, 0.0],
        ],
        dtype=np.float64,
    )
    near_trace = run_control_trace(
        model,
        ids,
        qpos=near_qpos,
        qvel=[0.0, 0.0],
        target=near_target,
        controls=near_controls,
    )

    raw_facts = {
        "torque_step_responses": torque_responses,
        "zero_action_free_decay": {
            "initial_qpos_rad": decay_qpos,
            "initial_qvel_rad_per_s": decay_qvel,
            "control_steps": int(len(decay_controls)),
            "internal_steps": int(len(decay_trace["steps"]["time_seconds"])),
            "trace": decay_trace,
        },
        "near_tolerance_controlled_trace": {
            "initial_qpos_rad": near_qpos,
            "trajectory_phases": [
                "alternating torque oscillation",
                "alternating lower-amplitude settling",
                "zero-action settling",
            ],
            "target_construction": (
                "analytic FK at initial pose plus 0.0085 m x offset"
            ),
            "target_position_m": near_target,
            "control_schedule": near_controls,
            "control_steps": int(len(near_controls)),
            "internal_steps": int(len(near_trace["steps"]["time_seconds"])),
            "trace": near_trace,
        },
    }
    summaries = {
        "torque_step_responses": [
            {"name": case["name"], **_trace_summary(case["trace"])}
            for case in torque_responses
        ],
        "zero_action_free_decay": _trace_summary(decay_trace),
        "near_tolerance_controlled_trace": _trace_summary(near_trace),
    }
    return {
        "artifact_type": "compiled_dynamics_laboratory_measurement",
        "status": "measured",
        "facts": {
            "compiled_model": _compiled_facts(model, ids),
            "parameters": parameters,
            "raw_traces": raw_facts,
        },
        "derived_summaries": summaries,
        "unchecked_scope": [
            "learned-policy behavior and success",
            "protected evaluator hold implementation",
            "scientific interpretation of measured limitations",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record deterministic compiled MuJoCo dynamics measurements."
    )
    parser.add_argument("output", type=Path, help="JSON artifact output path")
    args = parser.parse_args()
    artifact = collect_measurement()
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(_jsonable(artifact), handle, indent=2, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
