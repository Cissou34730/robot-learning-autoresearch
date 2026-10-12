"""Deterministic physical characterization of the contracted two-joint arm.

This module deliberately loads the robot XML directly.  It is a laboratory
measurement, rather than a scenario environment, so that the compiled model,
range geometry, and effective control response are recorded together.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import (
    FOREARM_LENGTH,
    TWO_JOINT_ARM_XML_PATH,
    UPPER_ARM_LENGTH,
)
from contracts.task_spec import FRAME_SKIP, TARGET_RADIUS_RANGE


JOINT_NAMES = ("shoulder", "elbow")
ACTUATOR_NAMES = ("shoulder", "elbow")
REPRESENTATIVE_CONFIGURATIONS = (
    (0.0, 0.0),
    (0.65, -0.9),
    (-0.9, 0.65),
)


def load_model() -> mujoco.MjModel:
    """Load the exact human-owned XML used by the scenario."""
    return mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))


def _joint_ids(
    model: mujoco.MjModel,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ids = []
    for name in JOINT_NAMES:
        joint_id = int(model.joint(name).id)
        if joint_id < 0:
            raise ValueError(f"required joint is missing from compiled model: {name}")
        ids.append(joint_id)
    qpos_ids = np.asarray([model.jnt_qposadr[i] for i in ids], dtype=int)
    dof_ids = np.asarray([model.jnt_dofadr[i] for i in ids], dtype=int)
    return np.asarray(ids, dtype=int), qpos_ids, dof_ids


def _site_id(model: mujoco.MjModel) -> int:
    site_id = int(model.site("end_effector").id)
    if site_id < 0:
        raise ValueError("required end_effector site is missing from compiled model")
    return site_id


def reset_simulation(model: mujoco.MjModel, data: mujoco.MjData) -> None:
    """Reset state to the contract's zero joint position and velocity."""
    mujoco.mj_resetData(model, data)
    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    data.ctrl[:] = 0.0
    mujoco.mj_forward(model, data)


def set_joint_configuration(
    model: mujoco.MjModel, data: mujoco.MjData, qpos: np.ndarray | list[float] | tuple[float, ...]
) -> None:
    """Set a two-joint configuration with zero velocity and update kinematics."""
    q = np.asarray(qpos, dtype=np.float64)
    if q.shape != (2,) or not np.all(np.isfinite(q)):
        raise ValueError("qpos must be a finite two-element vector in radians")
    _, qpos_ids, _ = _joint_ids(model)
    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    data.qpos[qpos_ids] = q
    mujoco.mj_forward(model, data)


def target_position(radius: float, angle: float, *, z: float = 0.02) -> np.ndarray:
    """Return a planar target in metres for a polar radius and angle in radians."""
    radius = float(radius)
    angle = float(angle)
    z = float(z)
    if not all(math.isfinite(v) for v in (radius, angle, z)) or radius < 0.0:
        raise ValueError("target radius, angle, and z must be finite and radius non-negative")
    return np.asarray([radius * math.cos(angle), radius * math.sin(angle), z], dtype=np.float64)


def forward_kinematics(
    model: mujoco.MjModel, data: mujoco.MjData, qpos: np.ndarray | list[float] | tuple[float, ...]
) -> dict[str, np.ndarray]:
    """Forward a configuration and return endpoint position and translational Jacobian."""
    set_joint_configuration(model, data, qpos)
    site_id = _site_id(model)
    _, _, dof_ids = _joint_ids(model)
    jacp = np.zeros((3, model.nv), dtype=np.float64)
    mujoco.mj_jacSite(model, data, jacp, None, site_id)
    return {
        "position": np.asarray(data.site(site_id).xpos, dtype=np.float64).copy(),
        "jacobian": jacp[:, dof_ids].copy(),
    }


def solve_two_link_ik(radius: float, angle: float) -> dict[str, np.ndarray | None]:
    """Solve the two analytical elbow branches for a planar target."""
    radius = float(radius)
    angle = float(angle)
    if not math.isfinite(radius) or not math.isfinite(angle) or radius < 0.0:
        raise ValueError("IK radius and angle must be finite and radius non-negative")
    cosine = (
        radius * radius - UPPER_ARM_LENGTH * UPPER_ARM_LENGTH - FOREARM_LENGTH * FOREARM_LENGTH
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    if cosine < -1.0 - 1e-12 or cosine > 1.0 + 1e-12:
        return {"elbow_up": None, "elbow_down": None}
    cosine = float(np.clip(cosine, -1.0, 1.0))
    elbow_magnitude = math.acos(cosine)
    solutions: dict[str, np.ndarray] = {}
    for branch, elbow in (("elbow_up", elbow_magnitude), ("elbow_down", -elbow_magnitude)):
        shoulder = angle - math.atan2(
            FOREARM_LENGTH * math.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * math.cos(elbow),
        )
        shoulder = math.atan2(math.sin(shoulder), math.cos(shoulder))
        solutions[branch] = np.asarray([shoulder, elbow], dtype=np.float64)
    return solutions


def _limit_status(
    model: mujoco.MjModel, qpos: np.ndarray
) -> tuple[bool, np.ndarray]:
    joint_ids, _, _ = _joint_ids(model)
    ranges = np.asarray(model.jnt_range[joint_ids], dtype=np.float64)
    margins = np.minimum(qpos - ranges[:, 0], ranges[:, 1] - qpos)
    return bool(np.all(margins >= -1e-12)), margins


def _compiled_facts(model: mujoco.MjModel) -> dict[str, Any]:
    joint_ids, qpos_ids, dof_ids = _joint_ids(model)
    joints = []
    for name, joint_id, qpos_id, dof_id in zip(
        JOINT_NAMES, joint_ids, qpos_ids, dof_ids, strict=True
    ):
        joints.append(
            {
                "name": name,
                "id": int(joint_id),
                "qpos_index": int(qpos_id),
                "dof_index": int(dof_id),
                "range": {
                    "values": np.asarray(model.jnt_range[joint_id], dtype=float).tolist(),
                    "unit": "rad",
                },
                "damping": {
                    "value": float(model.dof_damping[dof_id]),
                    "unit": "N m s/rad",
                },
                "armature": {
                    "value": float(model.dof_armature[dof_id]),
                    "unit": "kg m^2",
                },
            }
        )

    actuators = []
    for name in ACTUATOR_NAMES:
        actuator_id = int(model.actuator(name).id)
        if actuator_id < 0:
            raise ValueError(f"required actuator is missing from compiled model: {name}")
        actuators.append(
            {
                "name": name,
                "id": actuator_id,
                "gear": {
                    "values": np.asarray(model.actuator_gear[actuator_id], dtype=float).tolist(),
                    "unit": "dimensionless gear coefficients",
                },
                "control_range": {
                    "values": np.asarray(
                        model.actuator_ctrlrange[actuator_id], dtype=float
                    ).tolist(),
                    "unit": "normalized control",
                },
            }
        )

    bodies = []
    for body_id in range(model.nbody):
        body_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, body_id)
        bodies.append(
            {
                "name": None if body_name is None else str(body_name),
                "id": int(body_id),
                "mass": {"value": float(model.body_mass[body_id]), "unit": "kg"},
                "inertia": {
                    "values": np.asarray(model.body_inertia[body_id], dtype=float).tolist(),
                    "unit": "kg m^2",
                    "frame": "body principal axes",
                },
            }
        )

    timestep = float(model.opt.timestep)
    return {
        "xml_path": str(TWO_JOINT_ARM_XML_PATH),
        "timestep": {"value": timestep, "unit": "s"},
        "control_interval": {
            "value": timestep * FRAME_SKIP,
            "unit": "s",
            "frame_skip": FRAME_SKIP,
        },
        "joints": joints,
        "actuators": actuators,
        "bodies": bodies,
    }


def _grid_measurement(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    radius_count: int,
    angle_count: int,
) -> dict[str, Any]:
    radii = np.linspace(TARGET_RADIUS_RANGE[0], TARGET_RADIUS_RANGE[1], radius_count)
    angles = np.linspace(-math.pi, math.pi, angle_count, endpoint=False)
    z = float(forward_kinematics(model, data, (0.0, 0.0))["position"][2])
    records: list[dict[str, Any]] = []

    for radius in radii:
        for angle in angles:
            target = target_position(float(radius), float(angle), z=z)
            solutions = solve_two_link_ik(float(radius), float(angle))
            for branch in ("elbow_up", "elbow_down"):
                solution = solutions[branch]
                if solution is None:
                    records.append(
                        {
                            "radius_m": float(radius),
                            "angle_rad": float(angle),
                            "branch": branch,
                            "target_position_m": target.tolist(),
                            "geometric_feasible": False,
                            "range_feasible": False,
                            "joint_limit_margins_rad": None,
                            "qpos_rad": None,
                            "endpoint_reconstruction_error_m": None,
                            "jacobian_singular_values_m_per_rad": None,
                            "infeasibility_reason": "outside_two_link_reach",
                        }
                    )
                    continue
                range_feasible, margins = _limit_status(model, solution)
                fk = forward_kinematics(model, data, solution)
                singular_values = np.linalg.svd(fk["jacobian"][:2, :], compute_uv=False)
                records.append(
                    {
                        "radius_m": float(radius),
                        "angle_rad": float(angle),
                        "branch": branch,
                        "target_position_m": target.tolist(),
                        "geometric_feasible": True,
                        "range_feasible": range_feasible,
                        "joint_limit_margins_rad": margins.tolist(),
                        "qpos_rad": solution.tolist(),
                        "endpoint_reconstruction_error_m": float(
                            np.linalg.norm(fk["position"] - target)
                        ),
                        "jacobian_singular_values_m_per_rad": singular_values.tolist(),
                        "infeasibility_reason": None if range_feasible else "joint_limit",
                    }
                )

    feasible_records = [r for r in records if r["range_feasible"]]
    infeasible_records = [r for r in records if not r["range_feasible"]]
    worst = None
    if feasible_records:
        worst_record = min(
            feasible_records,
            key=lambda record: record["jacobian_singular_values_m_per_rad"][-1],
        )
        values = worst_record["jacobian_singular_values_m_per_rad"]
        worst = {
            "radius_m": worst_record["radius_m"],
            "angle_rad": worst_record["angle_rad"],
            "branch": worst_record["branch"],
            "smallest_singular_value_m_per_rad": values[-1],
            "singular_values_m_per_rad": values,
            "condition_number": (
                float(values[0] / values[-1]) if values[-1] > 0.0 else None
            ),
        }
    return {
        "sampling": {
            "radius_count": radius_count,
            "angle_count": angle_count,
            "radius_range_m": list(TARGET_RADIUS_RANGE),
            "angle_range_rad": [-math.pi, math.pi],
            "angle_endpoint": "excluded; full circular range without duplicate endpoint",
        },
        "records": records,
        "summary": {
            "record_count": len(records),
            "geometrically_feasible_count": sum(
                bool(r["geometric_feasible"]) for r in records
            ),
            "range_feasible_count": len(feasible_records),
            "range_infeasible_count": len(infeasible_records),
            "worst_feasible_conditioning": worst,
            "infeasible_target_branch_regions": [
                {
                    "radius_m": r["radius_m"],
                    "angle_rad": r["angle_rad"],
                    "branch": r["branch"],
                    "reason": r["infeasibility_reason"],
                }
                for r in infeasible_records
            ],
        },
    }


def run_response_sequence(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    initial_qpos: np.ndarray | list[float] | tuple[float, ...],
    *,
    response_steps: int = 20,
    frame_skip: int = FRAME_SKIP,
) -> dict[str, Any]:
    """Apply a deterministic bounded command reversal and record each control step."""
    if response_steps < 2:
        raise ValueError("response_steps must be at least 2 to contain a reversal")
    if frame_skip < 1:
        raise ValueError("frame_skip must be positive")
    q = np.asarray(initial_qpos, dtype=np.float64)
    if q.shape != (2,) or not np.all(np.isfinite(q)):
        raise ValueError("initial_qpos must be a finite two-element vector in radians")
    range_feasible, _ = _limit_status(model, q)
    if not range_feasible:
        raise ValueError("response initial_qpos is outside compiled joint ranges")

    _, qpos_ids, dof_ids = _joint_ids(model)
    site_id = _site_id(model)
    ctrl_range = np.asarray(model.actuator_ctrlrange[: model.nu], dtype=np.float64)
    if model.nu != 2 or ctrl_range.shape != (2, 2):
        raise ValueError("expected exactly two actuators with two-element control ranges")
    set_joint_configuration(model, data, q)
    control_interval = float(model.opt.timestep) * frame_skip
    reversal_step = response_steps // 2
    records: list[dict[str, Any]] = []

    for step_index in range(response_steps):
        sign = 1.0 if step_index < reversal_step else -1.0
        raw_control = np.full(model.nu, sign, dtype=np.float64)
        applied_control = np.clip(raw_control, ctrl_range[:, 0], ctrl_range[:, 1])
        qpos_before = np.asarray(data.qpos[qpos_ids], dtype=np.float64).copy()
        qvel_before = np.asarray(data.qvel[dof_ids], dtype=np.float64).copy()
        data.ctrl[:] = applied_control
        mujoco.mj_step(model, data, nstep=frame_skip)
        qpos_after = np.asarray(data.qpos[qpos_ids], dtype=np.float64).copy()
        qvel_after = np.asarray(data.qvel[dof_ids], dtype=np.float64).copy()
        acceleration = (qvel_after - qvel_before) / control_interval
        jacp = np.zeros((3, model.nv), dtype=np.float64)
        mujoco.mj_jacSite(model, data, jacp, None, site_id)
        endpoint_velocity = jacp @ np.asarray(data.qvel, dtype=np.float64)
        records.append(
            {
                "control_step": step_index,
                "time_s": float((step_index + 1) * control_interval),
                "raw_control": raw_control.tolist(),
                "applied_control": applied_control.tolist(),
                "saturated": bool(np.any(np.abs(applied_control - raw_control) > 1e-12)),
                "at_control_limit": bool(
                    np.any(
                        (np.abs(applied_control - ctrl_range[:, 0]) <= 1e-12)
                        | (np.abs(applied_control - ctrl_range[:, 1]) <= 1e-12)
                    )
                ),
                "qpos_rad": qpos_after.tolist(),
                "qvel_rad_per_s": qvel_after.tolist(),
                "finite_difference_acceleration_rad_per_s2": acceleration.tolist(),
                "endpoint_speed_m_per_s": float(np.linalg.norm(endpoint_velocity)),
                "qpos_before_rad": qpos_before.tolist(),
                "qvel_before_rad_per_s": qvel_before.tolist(),
            }
        )

    pre = records[reversal_step - 1]
    post = records[reversal_step]
    return {
        "initial_qpos_rad": q.tolist(),
        "frame_skip": frame_skip,
        "control_interval": {"value": control_interval, "unit": "s"},
        "command_schedule": {
            "positive_control_steps": reversal_step,
            "negative_control_steps": response_steps - reversal_step,
            "command_values": ["+1", "-1"],
            "unit": "normalized control",
        },
        "steps": records,
        "summary": {
            "max_abs_acceleration_rad_per_s2": float(
                max(
                    np.max(np.abs(step["finite_difference_acceleration_rad_per_s2"]))
                    for step in records
                )
            ),
            "max_abs_velocity_rad_per_s": float(
                max(np.max(np.abs(step["qvel_rad_per_s"])) for step in records)
            ),
            "max_endpoint_speed_m_per_s": float(
                max(step["endpoint_speed_m_per_s"] for step in records)
            ),
            "saturated_control_step_count": sum(bool(step["saturated"]) for step in records),
            "reversal": {
                "step_index": reversal_step,
                "pre_reversal_endpoint_speed_m_per_s": pre["endpoint_speed_m_per_s"],
                "post_reversal_endpoint_speed_m_per_s": post["endpoint_speed_m_per_s"],
                "pre_reversal_acceleration_rad_per_s2": pre[
                    "finite_difference_acceleration_rad_per_s2"
                ],
                "post_reversal_acceleration_rad_per_s2": post[
                    "finite_difference_acceleration_rad_per_s2"
                ],
            },
            "braking_response": {
                "pre_reversal_qvel_norm_rad_per_s": float(
                    np.linalg.norm(np.asarray(pre["qvel_rad_per_s"], dtype=float))
                ),
                "post_reversal_qvel_norm_rad_per_s": float(
                    np.linalg.norm(np.asarray(post["qvel_rad_per_s"], dtype=float))
                ),
                "post_reversal_acceleration_projection_rad_per_s2": float(
                    np.dot(
                        np.asarray(post["applied_control"], dtype=float),
                        np.asarray(
                            post["finite_difference_acceleration_rad_per_s2"],
                            dtype=float,
                        ),
                    )
                ),
            },
        },
    }


def _response_measurement(
    model: mujoco.MjModel, data: mujoco.MjData, response_steps: int
) -> dict[str, Any]:
    sequences = [
        run_response_sequence(
            model,
            data,
            np.asarray(configuration, dtype=np.float64),
            response_steps=response_steps,
        )
        for configuration in REPRESENTATIVE_CONFIGURATIONS
    ]
    return {
        "sampling": {
            "sequence_count": len(sequences),
            "steps_per_sequence": response_steps,
            "control_interval_unit": "s",
            "qpos_unit": "rad",
            "qvel_unit": "rad/s",
            "finite_difference_acceleration_unit": "rad/s^2",
            "endpoint_speed_unit": "m/s",
        },
        "sequences": sequences,
        "summary": {
            "sequence_count": len(sequences),
            "max_abs_acceleration_rad_per_s2": float(
                max(
                    sequence["summary"]["max_abs_acceleration_rad_per_s2"]
                    for sequence in sequences
                )
            ),
            "max_abs_velocity_rad_per_s": float(
                max(sequence["summary"]["max_abs_velocity_rad_per_s"] for sequence in sequences)
            ),
            "max_endpoint_speed_m_per_s": float(
                max(sequence["summary"]["max_endpoint_speed_m_per_s"] for sequence in sequences)
            ),
            "saturated_control_step_count": sum(
                sequence["summary"]["saturated_control_step_count"] for sequence in sequences
            ),
            "braking_response": [
                sequence["summary"]["braking_response"] for sequence in sequences
            ],
        },
    }


def measure_physical_characterization(
    *,
    radius_count: int = 15,
    angle_count: int = 32,
    response_steps: int = 20,
) -> dict[str, Any]:
    """Return the bounded compiled-model, IK/Jacobian, and response measurement."""
    if not 2 <= radius_count <= 64:
        raise ValueError("radius_count must be between 2 and 64")
    if not 2 <= angle_count <= 64:
        raise ValueError("angle_count must be between 2 and 64")
    if not 2 <= response_steps <= 200:
        raise ValueError("response_steps must be between 2 and 200")

    model = load_model()
    if model.nq != 2 or model.nv != 2 or model.nu != 2:
        raise ValueError(
            f"compiled XML must have nq=nv=nu=2, got {model.nq}, {model.nv}, {model.nu}"
        )
    data = mujoco.MjData(model)
    reset_simulation(model, data)
    grid = _grid_measurement(model, data, radius_count, angle_count)
    responses = _response_measurement(model, data, response_steps)
    return {
        "schema": "physical_characterization.v1",
        "measurement": {
            "purpose": "compiled dynamics, range-constrained planar IK/Jacobian, and bounded control response",
            "source_xml": str(TWO_JOINT_ARM_XML_PATH),
            "deterministic": True,
        },
        "compiled_facts": _compiled_facts(model),
        "ik_jacobian_grid": grid,
        "controlled_responses": responses,
    }


def _ensure_finite_json(value: Any, path: str = "artifact") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            _ensure_finite_json(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _ensure_finite_json(item, f"{path}[{index}]")
    elif isinstance(value, (float, np.floating)) and not math.isfinite(float(value)):
        raise ValueError(f"non-finite numeric value at {path}")


def write_json_artifact(artifact: Mapping[str, Any], output_path: str | Path) -> Path:
    """Write a validated JSON artifact and reject invalid output paths/data."""
    path = Path(output_path)
    if not str(path).strip():
        raise ValueError("artifact path must not be empty")
    if path.exists() and path.is_dir():
        raise ValueError(f"artifact path is a directory: {path}")
    _ensure_finite_json(artifact)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(artifact, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
    except OSError as exc:
        raise OSError(f"could not write artifact {path}: {exc}") from exc
    return path


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True, help="output JSON artifact path")
    parser.add_argument("--radius-count", type=int, default=15)
    parser.add_argument("--angle-count", type=int, default=32)
    parser.add_argument("--response-steps", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _argument_parser().parse_args(argv)
    artifact = measure_physical_characterization(
        radius_count=args.radius_count,
        angle_count=args.angle_count,
        response_steps=args.response_steps,
    )
    write_json_artifact(artifact, args.artifact)


if __name__ == "__main__":
    main()
