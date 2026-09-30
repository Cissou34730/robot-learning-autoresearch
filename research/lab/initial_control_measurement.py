"""Measure torque-limited reach-and-hold feasibility across the official annulus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from robot_learning.benchmark.spec import (
    FRAME_SKIP,
    HOLD_SECONDS,
    MAX_EPISODE_STEPS,
    SUCCESS_THRESHOLD,
    TARGET_RADIUS_RANGE,
)
from robot_learning.robots.two_joint_arm import (
    FOREARM_LENGTH,
    TWO_JOINT_ARM_XML_PATH,
    UPPER_ARM_LENGTH,
)

CONTROL_GAINS = (
    {"name": "conservative", "kp": 12.0, "kd": 2.5},
    {"name": "balanced", "kp": 24.0, "kd": 4.0},
    {"name": "aggressive", "kp": 40.0, "kd": 6.0},
)
RADII = np.linspace(TARGET_RADIUS_RANGE[0], TARGET_RADIUS_RANGE[1], 6)
ANGLES = np.linspace(-np.pi, np.pi, 16, endpoint=False)
JOINT_LIMIT = np.deg2rad(170.0)


def _wrap(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _inverse_kinematics(radius: float, angle: float, elbow_sign: float) -> tuple[float, float]:
    cosine = (
        radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow = elbow_sign * float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    shoulder = angle - np.arctan2(
        FOREARM_LENGTH * np.sin(elbow),
        UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
    )
    return _wrap(float(shoulder)), _wrap(float(elbow))


def _admissible(q_desired: tuple[float, float]) -> bool:
    return all(abs(value) <= JOINT_LIMIT for value in q_desired)


def _run_case(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    *,
    radius: float,
    angle: float,
    branch: str,
    q_desired: tuple[float, float],
    gains: dict[str, float],
    hold_steps_required: int,
) -> dict:
    site_id = mujoco.mj_name2id(
        model, mujoco.mjtObj.mjOBJ_SITE, "end_effector"
    )
    site_jacobian = np.zeros((3, model.nv), dtype=np.float64)
    rotational_jacobian = np.zeros((3, model.nv), dtype=np.float64)
    mujoco.mj_resetData(model, data)
    data.qpos[:] = 0.0
    data.qvel[:] = 0.0
    mujoco.mj_forward(model, data)
    target_z = float(data.site("end_effector").xpos[2])
    data.mocap_pos[0] = [
        radius * np.cos(angle),
        radius * np.sin(angle),
        target_z,
    ]
    mujoco.mj_forward(model, data)

    held_steps = 0
    first_entry: int | None = None
    interruptions = 0
    max_speed_in_tolerance = 0.0
    minimum_distance = float("inf")
    peak_action = 0.0

    for step in range(1, MAX_EPISODE_STEPS + 1):
        error = np.array(
            [_wrap(q_desired[0] - data.qpos[0]), _wrap(q_desired[1] - data.qpos[1])],
            dtype=np.float64,
        )
        torque = gains["kp"] * error - gains["kd"] * data.qvel[:2]
        action = np.clip(torque / 5.0, -1.0, 1.0)
        peak_action = max(peak_action, float(np.max(np.abs(action))))
        data.ctrl[:] = action
        for _ in range(FRAME_SKIP):
            mujoco.mj_step(model, data)

        endpoint = data.site("end_effector").xpos
        distance = float(np.linalg.norm(endpoint - data.mocap_pos[0]))
        minimum_distance = min(minimum_distance, distance)
        in_tolerance = distance <= SUCCESS_THRESHOLD
        mujoco.mj_jacSite(
            model, data, site_jacobian, rotational_jacobian, site_id
        )
        speed = float(np.linalg.norm(site_jacobian @ data.qvel))
        if in_tolerance:
            if first_entry is None:
                first_entry = step
            held_steps += 1
            max_speed_in_tolerance = max(max_speed_in_tolerance, speed)
        else:
            if held_steps:
                interruptions += 1
            held_steps = 0
        if held_steps >= hold_steps_required:
            return {
                "success": True,
                "steps": step,
                "first_entry_step": first_entry,
                "max_held_steps": held_steps,
                "hold_interruptions": interruptions,
                "minimum_distance_cm": 100.0 * minimum_distance,
                "max_speed_in_tolerance_m_per_s": max_speed_in_tolerance,
                "peak_action": peak_action,
            }

    return {
        "success": False,
        "steps": MAX_EPISODE_STEPS,
        "first_entry_step": first_entry,
        "max_held_steps": held_steps,
        "hold_interruptions": interruptions,
        "minimum_distance_cm": 100.0 * minimum_distance,
        "max_speed_in_tolerance_m_per_s": max_speed_in_tolerance,
        "peak_action": peak_action,
    }


def measure(output: Path) -> None:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    hold_steps_required = round(HOLD_SECONDS / (model.opt.timestep * FRAME_SKIP))
    cases: list[dict] = []

    for gains in CONTROL_GAINS:
        for radius in RADII:
            for angle in ANGLES:
                for elbow_sign, branch in ((1.0, "open"), (-1.0, "folded")):
                    q_desired = _inverse_kinematics(radius, angle, elbow_sign)
                    if not _admissible(q_desired):
                        cases.append(
                            {
                                "gain": gains["name"],
                                "radius_m": float(radius),
                                "angle_degrees": float(np.degrees(angle)),
                                "branch": branch,
                                "admissible": False,
                            }
                        )
                        continue
                    result = _run_case(
                        model,
                        data,
                        radius=float(radius),
                        angle=float(angle),
                        branch=branch,
                        q_desired=q_desired,
                        gains=gains,
                        hold_steps_required=hold_steps_required,
                    )
                    cases.append(
                        {
                            "gain": gains["name"],
                            "radius_m": float(radius),
                            "angle_degrees": float(np.degrees(angle)),
                            "branch": branch,
                            "admissible": True,
                            "q_desired_radians": list(q_desired),
                            **result,
                        }
                    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "measurement": "torque_limited_inverse_kinematic_hold",
                "task": {
                    "target_radius_range_m": list(TARGET_RADIUS_RANGE),
                    "success_threshold_m": SUCCESS_THRESHOLD,
                    "hold_steps_required": hold_steps_required,
                    "control_interval_s": model.opt.timestep * FRAME_SKIP,
                    "max_episode_steps": MAX_EPISODE_STEPS,
                },
                "compiled_dynamics": {
                    "timestep_s": model.opt.timestep,
                    "body_mass_kg": model.body_mass.tolist(),
                    "dof_armature": model.dof_armature.tolist(),
                    "dof_damping": model.dof_damping.tolist(),
                    "actuator_gear": model.actuator_gear.tolist(),
                },
                "controller_family": list(CONTROL_GAINS),
                "grid": {
                    "radii_m": [float(value) for value in RADII],
                    "angles_degrees": [float(np.degrees(value)) for value in ANGLES],
                },
                "cases": cases,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    measure(parser.parse_args().output)
