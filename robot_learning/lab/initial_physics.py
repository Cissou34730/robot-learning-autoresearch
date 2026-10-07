"""Characterize official-task geometry and compiled MuJoCo dynamics."""

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

JOINT_LIMIT = np.deg2rad(170.0)


def wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def inverse_kinematics(
    radius: float, angle: float, elbow_sign: float
) -> tuple[float, float]:
    cosine = (
        radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow = elbow_sign * float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    shoulder = angle - np.arctan2(
        FOREARM_LENGTH * np.sin(elbow),
        UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
    )
    return wrap_to_pi(float(shoulder)), elbow


def jacobian(q: tuple[float, float]) -> np.ndarray:
    q1, q2 = q
    forearm_angle = q1 + q2
    return np.array(
        [
            [
                -UPPER_ARM_LENGTH * np.sin(q1)
                - FOREARM_LENGTH * np.sin(forearm_angle),
                -FOREARM_LENGTH * np.sin(forearm_angle),
            ],
            [
                UPPER_ARM_LENGTH * np.cos(q1)
                + FOREARM_LENGTH * np.cos(forearm_angle),
                FOREARM_LENGTH * np.cos(forearm_angle),
            ],
        ]
    )


def measure_kinematic_grid() -> dict:
    radii = np.linspace(0.06, 0.20, 29)
    angles = np.linspace(-np.pi, np.pi, 73)[:-1]
    rows: list[dict] = []
    valid_target_count = 0
    branch_valid_count = 0
    worst_targets: list[dict] = []

    for radius in radii:
        for angle in angles:
            branches = []
            for branch_name, elbow_sign in (("open", 1.0), ("folded", -1.0)):
                q = inverse_kinematics(float(radius), float(angle), elbow_sign)
                margin = float(JOINT_LIMIT - np.max(np.abs(q)))
                singular_values = np.linalg.svd(jacobian(q), compute_uv=False)
                branch = {
                    "name": branch_name,
                    "q_degrees": [float(np.degrees(value)) for value in q],
                    "joint_limit_margin_degrees": float(np.degrees(margin)),
                    "valid": bool(margin >= 0.0),
                    "jacobian_singular_values": [
                        float(value) for value in singular_values
                    ],
                    "jacobian_min_singular_value": float(singular_values[-1]),
                }
                branches.append(branch)
                branch_valid_count += int(branch["valid"])

            valid_branches = [branch for branch in branches if branch["valid"]]
            valid_target_count += int(bool(valid_branches))
            best = max(
                branches,
                key=lambda branch: branch["joint_limit_margin_degrees"],
            )
            row = {
                "radius_m": float(radius),
                "angle_degrees": float(np.degrees(angle)),
                "branches": branches,
                "best_branch": best["name"],
                "best_joint_limit_margin_degrees": best["joint_limit_margin_degrees"],
                "best_jacobian_min_singular_value": max(
                    branch["jacobian_min_singular_value"] for branch in valid_branches
                )
                if valid_branches
                else 0.0,
                "any_valid_branch": bool(valid_branches),
            }
            rows.append(row)
            worst_targets.append(
                {
                    "radius_m": row["radius_m"],
                    "angle_degrees": row["angle_degrees"],
                    "best_branch": row["best_branch"],
                    "best_joint_limit_margin_degrees": row[
                        "best_joint_limit_margin_degrees"
                    ],
                    "any_valid_branch": row["any_valid_branch"],
                }
            )

    worst_targets.sort(key=lambda row: row["best_joint_limit_margin_degrees"])
    return {
        "grid": {
            "radius_range_m": [0.06, 0.20],
            "radius_samples": len(radii),
            "angle_samples": len(angles),
            "target_samples": len(rows),
            "joint_limit_degrees": [-170.0, 170.0],
        },
        "summary": {
            "targets_with_at_least_one_valid_branch": valid_target_count,
            "target_valid_fraction": valid_target_count / len(rows),
            "branch_valid_fraction": branch_valid_count / (2 * len(rows)),
            "minimum_best_joint_limit_margin_degrees": worst_targets[0][
                "best_joint_limit_margin_degrees"
            ],
            "minimum_valid_branch_jacobian_singular_value": min(
                row["best_jacobian_min_singular_value"]
                for row in rows
                if row["any_valid_branch"]
            ),
            "worst_targets": worst_targets[:20],
        },
        "target_rows": rows,
    }


def measure_dynamics() -> dict:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    compiled = {
        "nq": int(model.nq),
        "nv": int(model.nv),
        "nu": int(model.nu),
        "timestep_s": float(model.opt.timestep),
        "body_mass": [float(value) for value in model.body_mass],
        "body_inertia": [
            [float(value) for value in row] for row in model.body_inertia
        ],
        "dof_damping": [float(value) for value in model.dof_damping],
        "dof_armature": [float(value) for value in model.dof_armature],
        "joint_ranges_degrees": [
            [float(np.degrees(value)) for value in row] for row in model.jnt_range
        ],
        "actuator_gear": [
            [float(value) for value in row] for row in model.actuator_gear
        ],
        "actuator_ctrlrange": [
            [float(value) for value in row] for row in model.actuator_ctrlrange
        ],
    }

    configurations = {
        "extended": (0.0, 0.0),
        "open_folded": (0.0, np.deg2rad(90.0)),
        "folded": (0.0, np.deg2rad(-90.0)),
        "bent": (np.deg2rad(90.0), np.deg2rad(-90.0)),
    }
    responses = []
    for name, q in configurations.items():
        mujoco.mj_resetData(model, data)
        data.qpos[:2] = q
        data.qvel[:2] = 0.0
        data.ctrl[:2] = 1.0
        mujoco.mj_forward(model, data)
        initial_acceleration = data.qacc[:2].copy()
        initial_actuator_force = data.actuator_force[:2].copy()
        for _ in range(10):
            mujoco.mj_step(model, data)
        responses.append(
            {
                "configuration": name,
                "q_degrees": [float(np.degrees(value)) for value in q],
                "control": [1.0, 1.0],
                "initial_qacc_radians_per_second_squared": [
                    float(value) for value in initial_acceleration
                ],
                "initial_actuator_force": [
                    float(value) for value in initial_actuator_force
                ],
                "qvel_after_10_substeps": [
                    float(value) for value in data.qvel[:2]
                ],
                "qpos_delta_after_10_substeps": [
                    float(value - start) for value, start in zip(data.qpos[:2], q)
                ],
            }
        )
    return {"compiled_model": compiled, "torque_response_probes": responses}


def run(artifact: Path) -> None:
    result = {
        "schema_version": 1,
        "experiment": "official_geometry_and_compiled_dynamics",
        "sources": {
            "xml": str(TWO_JOINT_ARM_XML_PATH),
            "official_radius_range_m": [0.06, 0.20],
            "official_joint_limit_degrees": [-170.0, 170.0],
        },
        "kinematic_grid": measure_kinematic_grid(),
        "dynamics": measure_dynamics(),
    }
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args().artifact)
