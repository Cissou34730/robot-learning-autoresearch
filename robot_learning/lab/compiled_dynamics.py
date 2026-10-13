"""Deterministic characterization of the compiled two-joint MuJoCo model.

This is a laboratory measurement, not a controller or a policy benchmark.  It
uses the same XML compilation path as the scenario and preserves the raw
control-step traces needed to distinguish kinematic feasibility, actuation,
and sampled-time behavior.
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
    MAX_REACH,
    TWO_JOINT_ARM_XML_PATH,
    UPPER_ARM_LENGTH,
)
from contracts.task_spec import FRAME_SKIP, SUCCESS_THRESHOLD, TARGET_RADIUS_RANGE


IK_RADIUS_SAMPLES = 29
IK_BEARING_SAMPLES = 360
_TARGET = np.array([0.14, 0.04, 0.02], dtype=np.float64)


def _as_json(value: Any) -> Any:
    """Convert MuJoCo/numpy scalars and arrays into JSON-native values."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, (list, tuple)):
        return [_as_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _as_json(item) for key, item in value.items()}
    return value


def _object_name(model: mujoco.MjModel, object_type: Any, index: int) -> str:
    name = mujoco.mj_id2name(model, object_type, index)
    return name if name else f"unnamed_{index}"


def _compiled_context(model: mujoco.MjModel) -> dict[str, Any]:
    option = model.opt
    return {
        "xml_path": str(TWO_JOINT_ARM_XML_PATH),
        "timestep_seconds": float(option.timestep),
        "frame_skip": FRAME_SKIP,
        "policy_step_seconds": float(option.timestep * FRAME_SKIP),
        "integrator": int(option.integrator),
        "solver": int(option.solver),
        "gravity": np.asarray(option.gravity, dtype=np.float64),
        "solver_iterations": int(option.iterations),
        "solver_tolerance": float(option.tolerance),
        "nq": int(model.nq),
        "nv": int(model.nv),
        "nu": int(len(model.actuator_trnid)),
    }


def _geometry_summary(model: mujoco.MjModel, data: mujoco.MjData) -> dict[str, Any]:
    bodies = []
    for body_id in range(int(model.nbody)):
        bodies.append(
            {
                "id": body_id,
                "name": _object_name(model, mujoco.mjtObj.mjOBJ_BODY, body_id),
                "mass": float(model.body_mass[body_id]),
                "inertia": np.asarray(model.body_inertia[body_id], dtype=np.float64),
                "position": np.asarray(model.body_pos[body_id], dtype=np.float64),
            }
        )

    geoms = []
    for geom_id in range(len(model.geom_type)):
        geoms.append(
            {
                "id": geom_id,
                "name": _object_name(model, mujoco.mjtObj.mjOBJ_GEOM, geom_id),
                "body_id": int(model.geom_bodyid[geom_id]),
                "type": int(model.geom_type[geom_id]),
                "size": np.asarray(model.geom_size[geom_id], dtype=np.float64),
                "contype": int(model.geom_contype[geom_id]),
                "conaffinity": int(model.geom_conaffinity[geom_id]),
            }
        )

    return {
        "reference_link_lengths": {
            "upper_arm_m": UPPER_ARM_LENGTH,
            "forearm_m": FOREARM_LENGTH,
            "maximum_reach_m": MAX_REACH,
        },
        "initial_end_effector_position": np.asarray(
            data.site("end_effector").xpos, dtype=np.float64
        ),
        "bodies": bodies,
        "geoms": geoms,
    }


def _joint_summary(model: mujoco.MjModel) -> list[dict[str, Any]]:
    joints = []
    for joint_id in range(len(model.jnt_range)):
        dof_id = int(model.jnt_dofadr[joint_id])
        joints.append(
            {
                "id": joint_id,
                "name": _object_name(model, mujoco.mjtObj.mjOBJ_JOINT, joint_id),
                "type": int(model.jnt_type[joint_id]),
                "range": np.asarray(model.jnt_range[joint_id], dtype=np.float64),
                "limited": bool(model.jnt_limited[joint_id]),
                "damping": float(model.dof_damping[dof_id]),
                "armature": float(model.dof_armature[dof_id]),
                "frictionloss": float(model.dof_frictionloss[dof_id]),
                "dof_id": dof_id,
            }
        )
    return joints


def _actuator_summary(model: mujoco.MjModel) -> list[dict[str, Any]]:
    actuators = []
    for actuator_id in range(len(model.actuator_trnid)):
        actuators.append(
            {
                "id": actuator_id,
                "name": _object_name(
                    model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_id
                ),
                "transmission_type": int(model.actuator_trntype[actuator_id]),
                "transmission_id": np.asarray(
                    model.actuator_trnid[actuator_id], dtype=np.int64
                ),
                "gear": np.asarray(model.actuator_gear[actuator_id], dtype=np.float64),
                "control_range": np.asarray(
                    model.actuator_ctrlrange[actuator_id], dtype=np.float64
                ),
                "control_limited": bool(model.actuator_ctrllimited[actuator_id]),
                "gain_type": int(model.actuator_gaintype[actuator_id]),
                "gain_parameters": np.asarray(
                    model.actuator_gainprm[actuator_id], dtype=np.float64
                ),
                "bias_type": int(model.actuator_biastype[actuator_id]),
                "bias_parameters": np.asarray(
                    model.actuator_biasprm[actuator_id], dtype=np.float64
                ),
                "force_range": np.asarray(
                    model.actuator_forcerange[actuator_id], dtype=np.float64
                ),
                "force_limited": bool(model.actuator_forcelimited[actuator_id]),
            }
        )
    return actuators


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _ik_configuration(
    radius: float, bearing: float, elbow_sign: float
) -> tuple[np.ndarray | None, float]:
    cosine = (
        radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    if abs(cosine) > 1.0 + 1e-12:
        return None, cosine
    elbow = elbow_sign * float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    shoulder = bearing - np.arctan2(
        FOREARM_LENGTH * np.sin(elbow),
        UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
    )
    return np.array([_wrap_to_pi(float(shoulder)), _wrap_to_pi(elbow)]), cosine


def _jacobian(qpos: np.ndarray) -> np.ndarray:
    shoulder, elbow = qpos
    distal = shoulder + elbow
    return np.array(
        [
            [
                -UPPER_ARM_LENGTH * np.sin(shoulder)
                - FOREARM_LENGTH * np.sin(distal),
                -FOREARM_LENGTH * np.sin(distal),
            ],
            [
                UPPER_ARM_LENGTH * np.cos(shoulder)
                + FOREARM_LENGTH * np.cos(distal),
                FOREARM_LENGTH * np.cos(distal),
            ],
        ],
        dtype=np.float64,
    )


def _ik_branch_summary(
    model: mujoco.MjModel, branch_name: str, elbow_sign: float
) -> dict[str, Any]:
    lower = float(model.jnt_range[0, 0])
    upper = float(model.jnt_range[0, 1])
    elbow_lower = float(model.jnt_range[1, 0])
    elbow_upper = float(model.jnt_range[1, 1])
    radii = np.linspace(
        TARGET_RADIUS_RANGE[0], TARGET_RADIUS_RANGE[1], IK_RADIUS_SAMPLES
    )
    bearings = np.linspace(-np.pi, np.pi, IK_BEARING_SAMPLES, endpoint=False)

    feasible = 0
    valid_geometry = 0
    condition_numbers: list[float] = []
    determinants: list[float] = []
    minimum_singular_values: list[float] = []
    examples = []
    for radius in radii:
        for bearing in bearings:
            qpos, cosine = _ik_configuration(float(radius), float(bearing), elbow_sign)
            if qpos is None:
                continue
            valid_geometry += 1
            legal = (
                lower - 1e-12 <= qpos[0] <= upper + 1e-12
                and elbow_lower - 1e-12 <= qpos[1] <= elbow_upper + 1e-12
            )
            jacobian = _jacobian(qpos)
            singular_values = np.linalg.svd(jacobian, compute_uv=False)
            condition = float(np.linalg.cond(jacobian))
            determinant = float(np.linalg.det(jacobian))
            if legal:
                feasible += 1
                condition_numbers.append(condition)
                determinants.append(abs(determinant))
                minimum_singular_values.append(float(singular_values[-1]))
            if len(examples) < 3:
                examples.append(
                    {
                        "radius_m": float(radius),
                        "bearing_rad": float(bearing),
                        "cosine_elbow": float(cosine),
                        "qpos": qpos,
                        "legal": legal,
                        "jacobian_condition": condition,
                    }
                )

    total = IK_RADIUS_SAMPLES * IK_BEARING_SAMPLES
    summary = {
        "branch": branch_name,
        "radius_range_m": list(TARGET_RADIUS_RANGE),
        "radius_samples": IK_RADIUS_SAMPLES,
        "bearing_samples": IK_BEARING_SAMPLES,
        "evaluated_samples": total,
        "geometrically_valid_samples": valid_geometry,
        "limit_feasible_samples": feasible,
        "limit_feasible_fraction": float(feasible / total),
        "jacobian_condition_min": float(min(condition_numbers))
        if condition_numbers
        else None,
        "jacobian_condition_max": float(max(condition_numbers))
        if condition_numbers
        else None,
        "jacobian_abs_determinant_min": float(min(determinants))
        if determinants
        else None,
        "jacobian_abs_determinant_max": float(max(determinants))
        if determinants
        else None,
        "jacobian_sigma_min_min": float(min(minimum_singular_values))
        if minimum_singular_values
        else None,
        "jacobian_sigma_min_max": float(max(minimum_singular_values))
        if minimum_singular_values
        else None,
        "examples": examples,
    }
    return summary


def _reset(
    model: mujoco.MjModel, data: mujoco.MjData, target: np.ndarray = _TARGET
) -> None:
    mujoco.mj_resetData(model, data)
    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    data.ctrl[:] = 0.0
    data.mocap_pos[0] = target
    mujoco.mj_forward(model, data)


def _distance(data: mujoco.MjData, target: np.ndarray) -> float:
    return float(np.linalg.norm(data.site("end_effector").xpos - target))


def _snapshot(
    data: mujoco.MjData, target: np.ndarray, action: np.ndarray
) -> dict[str, Any]:
    return {
        "time_seconds": float(data.time),
        "distance_m": _distance(data, target),
        "qpos": np.asarray(data.qpos, dtype=np.float64),
        "qvel": np.asarray(data.qvel, dtype=np.float64),
        "qacc": np.asarray(data.qacc, dtype=np.float64),
        "ctrl": np.asarray(action, dtype=np.float64),
        "actuator_force": np.asarray(data.actuator_force, dtype=np.float64),
        "actuator_torque": np.asarray(data.qfrc_actuator, dtype=np.float64),
    }


def _control_trajectories(
    model: mujoco.MjModel, data: mujoco.MjData
) -> list[dict[str, Any]]:
    scenarios = {
        "zero": [np.zeros(2, dtype=np.float64)] * 3,
        "single_joint_saturated": [np.array([1.0, 0.0])] * 5,
        "braking_opposing": [np.array([1.0, 0.0])] * 5
        + [np.array([-1.0, 0.0])] * 5,
    }
    results = []
    reset_index = 0
    for name, actions in scenarios.items():
        replicates = []
        for replicate in range(2):
            _reset(model, data)
            reset_index += 1
            initial = _snapshot(data, _TARGET, np.zeros(2, dtype=np.float64))
            steps = []
            for action in actions:
                action = np.asarray(action, dtype=np.float64)
                data.ctrl[:] = action
                for _ in range(FRAME_SKIP):
                    mujoco.mj_step(model, data)
                steps.append(_snapshot(data, _TARGET, action))
            replicates.append(
                {
                    "replicate": replicate,
                    "reset_index": reset_index,
                    "initial": initial,
                    "steps": steps,
                }
            )
        results.append({"name": name, "replicates": replicates})
    return results


def _substep_trace(model: mujoco.MjModel, data: mujoco.MjData) -> dict[str, Any]:
    _reset(model, data, target=np.array([0.10, 0.08, 0.02], dtype=np.float64))
    action = np.array([1.0, 0.0], dtype=np.float64)
    initial_distance = _distance(data, data.mocap_pos[0])
    distances = []
    times = []
    for _ in range(FRAME_SKIP):
        data.ctrl[:] = action
        mujoco.mj_step(model, data)
        distances.append(_distance(data, data.mocap_pos[0]))
        times.append(float(data.time))
    endpoint_distance = float(distances[-1])
    return {
        "target": np.asarray(data.mocap_pos[0], dtype=np.float64),
        "action": action,
        "initial_distance_m": initial_distance,
        "internal_substep_times_seconds": times,
        "internal_substep_distances_m": distances,
        "sampled_endpoint_distance_m": endpoint_distance,
        "internal_distance_min_m": float(min(distances)),
        "internal_distance_max_m": float(max(distances)),
        "internal_minus_endpoint_max_abs_m": float(
            max(abs(distance - endpoint_distance) for distance in distances)
        ),
        "internal_outside_tolerance_count": int(
            sum(distance > SUCCESS_THRESHOLD for distance in distances)
        ),
        "frame_skip": FRAME_SKIP,
    }


def characterize(*, compatibility: bool = False) -> dict[str, Any]:
    """Build the bounded characterization, without writing an artifact."""
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    _reset(model, data)
    result: dict[str, Any] = {
        "schema": "compiled_dynamics_characterization_v1",
        "compatibility_mode": compatibility,
        "compiled_context": _compiled_context(model),
        "geometry": _geometry_summary(model, data),
        "joints": _joint_summary(model),
        "actuators": _actuator_summary(model),
    }
    if compatibility:
        result["compatibility_transition"] = _control_trajectories(model, data)[1][
            "replicates"
        ][0]
        result["compatibility_substep_trace"] = _substep_trace(model, data)
    else:
        result["ik_branch_feasibility"] = {
            "open": _ik_branch_summary(model, "open", 1.0),
            "folded": _ik_branch_summary(model, "folded", -1.0),
        }
        result["control_trajectories"] = _control_trajectories(model, data)
        result["substep_trace"] = _substep_trace(model, data)
    return _as_json(result)


def write_characterization(output: str | Path, *, compatibility: bool = False) -> None:
    result = characterize(compatibility=compatibility)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="JSON artifact path")
    args = parser.parse_args(argv)
    write_characterization(args.output)


if __name__ == "__main__":
    main()
