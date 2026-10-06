"""Measure compiled kinematic feasibility and local control response."""

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


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _ik(radius: float, angle: float, elbow_sign: float) -> np.ndarray:
    cosine = (
        radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow = elbow_sign * float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    shoulder = angle - np.arctan2(
        FOREARM_LENGTH * np.sin(elbow),
        UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
    )
    return np.array([_wrap_to_pi(float(shoulder)), elbow], dtype=np.float64)


def _forward_position(data) -> np.ndarray:
    return data.site("end_effector").xpos.copy()


def _legal(q: np.ndarray, joint_ranges: np.ndarray) -> bool:
    return bool(np.all(q >= joint_ranges[:, 0]) and np.all(q <= joint_ranges[:, 1]))


def _probe_kinematics(
    model: mujoco.MjModel,
    data: mujoco.MjData,
) -> dict:
    radii = np.linspace(0.06, 0.20, 141)
    angles = np.linspace(-np.pi, np.pi, 360, endpoint=False)
    branch_signs = (1.0, -1.0)
    branch_names = {1.0: "open", -1.0: "folded"}
    joint_ranges = np.asarray(model.jnt_range[:2], dtype=np.float64)
    total = 0
    legal = 0
    forward_residuals: list[float] = []
    branch_counts = {name: 0 for name in branch_names.values()}
    branch_min_margins = {name: float("inf") for name in branch_names.values()}
    radius_rows = []

    for radius in radii:
        row = {"radius_m": float(radius), "branches": {}}
        for elbow_sign in branch_signs:
            name = branch_names[elbow_sign]
            count = 0
            min_margin = float("inf")
            for angle in angles:
                q = _ik(float(radius), float(angle), elbow_sign)
                total += 1
                data.qpos[:] = 0.0
                data.qvel[:] = 0.0
                data.qpos[:2] = q
                mujoco.mj_forward(model, data)
                target = np.array(
                    [radius * np.cos(angle), radius * np.sin(angle), data.site("end_effector").xpos[2]]
                )
                residual = float(np.linalg.norm(_forward_position(data) - target))
                forward_residuals.append(residual)
                if _legal(q, joint_ranges):
                    legal += 1
                    count += 1
                    margin = float(np.min(np.minimum(q - joint_ranges[:, 0], joint_ranges[:, 1] - q)))
                    min_margin = min(min_margin, margin)
                    branch_counts[name] += 1
                    branch_min_margins[name] = min(branch_min_margins[name], margin)
            row["branches"][name] = {
                "legal_count": count,
                "total_count": len(angles),
                "legal_fraction": count / len(angles),
                "minimum_joint_margin_rad": None if count == 0 else min_margin,
            }
        radius_rows.append(row)

    return {
        "grid": {
            "radius_min_m": float(radii[0]),
            "radius_max_m": float(radii[-1]),
            "radius_count": len(radii),
            "angle_count": len(angles),
            "branch_count": len(branch_signs),
        },
        "total_branch_targets": total,
        "legal_branch_targets": legal,
        "legal_fraction": legal / total,
        "branch_summary": {
            name: {
                "legal_count": branch_counts[name],
                "total_count": len(radii) * len(angles),
                "legal_fraction": branch_counts[name] / (len(radii) * len(angles)),
                "minimum_joint_margin_rad": (
                    None if branch_counts[name] == 0 else branch_min_margins[name]
                ),
            }
            for name in branch_names.values()
        },
        "maximum_forward_residual_m": max(forward_residuals),
        "radius_rows": radius_rows,
    }


def _settle_step(velocity_norms: list[float], threshold: float) -> int | None:
    for index, value in enumerate(velocity_norms):
        if all(later <= threshold for later in velocity_norms[index:]):
            return index + 1
    return None


def _run_response(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    q_start: np.ndarray,
    pulse: np.ndarray,
    frame_skip: int,
    horizon: int = 120,
) -> dict:
    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    data.ctrl[:] = 0.0
    data.qpos[:2] = q_start
    mujoco.mj_forward(model, data)
    start_position = _forward_position(data)
    positions = []
    velocities = []
    for control_step in range(horizon):
        data.ctrl[:] = pulse if control_step == 0 else 0.0
        for _ in range(frame_skip):
            mujoco.mj_step(model, data)
        positions.append(data.qpos[:2].copy())
        velocities.append(data.qvel[:2].copy())

    position_array = np.asarray(positions)
    velocity_array = np.asarray(velocities)
    displacement = position_array - q_start
    velocity_norms = np.linalg.norm(velocity_array, axis=1)
    end_position = _forward_position(data)
    return {
        "pulse": pulse.tolist(),
        "peak_velocity_rad_per_s": float(np.max(np.linalg.norm(velocity_array, axis=1))),
        "peak_joint_displacement_rad": float(np.max(np.linalg.norm(displacement, axis=1))),
        "peak_cross_joint_displacement_rad": float(
            np.max(np.abs(displacement[:, 1 if pulse[0] != 0.0 else 0]))
        ),
        "peak_end_effector_displacement_m": float(
            np.linalg.norm(end_position - start_position)
        ),
        "settle_control_step_at_velocity_threshold": _settle_step(
            velocity_norms.tolist(), 0.01
        ),
        "final_velocity_norm_rad_per_s": float(velocity_norms[-1]),
    }


def _probe_dynamics(model: mujoco.MjModel, data: mujoco.MjData) -> dict:
    frame_skip = 10
    radii = (0.06, 0.10, 0.14, 0.18, 0.20)
    angles = (-np.pi, -np.pi / 2.0, 0.0, np.pi / 2.0)
    joint_ranges = np.asarray(model.jnt_range[:2], dtype=np.float64)
    rows = []
    for radius in radii:
        for angle in angles:
            for elbow_sign, branch in ((1.0, "open"), (-1.0, "folded")):
                q = _ik(radius, angle, elbow_sign)
                if not _legal(q, joint_ranges):
                    continue
                for pulse_joint in range(2):
                    for amplitude in (0.25, 1.0):
                        pulse = np.zeros(2, dtype=np.float64)
                        pulse[pulse_joint] = amplitude
                        response = _run_response(model, data, q, pulse, frame_skip)
                        rows.append(
                            {
                                "radius_m": radius,
                                "angle_degrees": float(np.degrees(angle)),
                                "branch": branch,
                                "initial_q_rad": q.tolist(),
                                "pulse_joint": pulse_joint,
                                "pulse_amplitude": amplitude,
                                "response": response,
                            }
                        )
    return {
        "frame_skip": frame_skip,
        "control_dt_s": float(model.opt.timestep * frame_skip),
        "pulse_horizon_control_steps": 120,
        "velocity_settle_threshold_rad_per_s": 0.01,
        "responses": rows,
    }


def run(artifact: Path) -> None:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    joint_ranges = np.asarray(model.jnt_range[:2], dtype=np.float64)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "schema_version": 1,
        "measurement": "compiled_kinematics_and_local_dynamics",
        "model": {
            "timestep_s": float(model.opt.timestep),
            "integrator": int(model.opt.integrator),
            "joint_ranges_rad": joint_ranges.tolist(),
            "dof_damping": np.asarray(model.dof_damping[:2]).tolist(),
            "dof_armature": np.asarray(model.dof_armature[:2]).tolist(),
            "actuator_gear": np.asarray(model.actuator_gear[:, :2]).tolist(),
            "actuator_ctrlrange": np.asarray(model.actuator_ctrlrange).tolist(),
            "body_mass": np.asarray(model.body_mass).tolist(),
            "body_inertia": np.asarray(model.body_inertia).tolist(),
        },
        "kinematics": _probe_kinematics(model, data),
        "dynamics": _probe_dynamics(model, data),
    }
    artifact.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.artifact)
