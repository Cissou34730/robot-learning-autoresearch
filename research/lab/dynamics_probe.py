"""Measure the task's kinematic and local dynamic difficulty without a policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from robot_learning.robots.two_joint_arm import (
    FOREARM_LENGTH,
    TWO_JOINT_ARM_XML_PATH,
    UPPER_ARM_LENGTH,
)

RADIUS_VALUES = np.linspace(0.06, 0.20, 8)
ANGLE_COUNT = 32
JOINT_LIMIT = np.deg2rad(170.0)


def wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def inverse_kinematics(radius: float, angle: float, elbow_sign: int) -> tuple[float, float]:
    cosine = (
        radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow = elbow_sign * float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    shoulder = angle - np.arctan2(
        FOREARM_LENGTH * np.sin(elbow),
        UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
    )
    return wrap_to_pi(float(shoulder)), elbow


def planar_jacobian(q: tuple[float, float]) -> np.ndarray:
    shoulder, elbow = q
    wrist = shoulder + elbow
    return np.array(
        [
            [
                -UPPER_ARM_LENGTH * np.sin(shoulder)
                - FOREARM_LENGTH * np.sin(wrist),
                -FOREARM_LENGTH * np.sin(wrist),
            ],
            [
                UPPER_ARM_LENGTH * np.cos(shoulder)
                + FOREARM_LENGTH * np.cos(wrist),
                FOREARM_LENGTH * np.cos(wrist),
            ],
        ],
        dtype=np.float64,
    )


def mass_matrix(model: mujoco.MjModel, data: mujoco.MjData) -> np.ndarray:
    full = np.zeros((model.nv, model.nv), dtype=np.float64)
    mujoco.mj_fullM(model, full, data.qM)
    return full


def measure() -> dict:
    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    branches: list[dict] = []
    angles = np.linspace(-np.pi, np.pi, ANGLE_COUNT, endpoint=False)

    for radius in RADIUS_VALUES:
        for angle in angles:
            for elbow_sign, branch_name in ((1, "open"), (-1, "folded")):
                q = inverse_kinematics(float(radius), float(angle), elbow_sign)
                valid = max(abs(q[0]), abs(q[1])) <= JOINT_LIMIT
                record = {
                    "radius_cm": float(radius * 100.0),
                    "angle_degrees": float(np.degrees(angle)),
                    "branch": branch_name,
                    "q1_degrees": float(np.degrees(q[0])),
                    "q2_degrees": float(np.degrees(q[1])),
                    "joint_limit_valid": bool(valid),
                }
                if valid:
                    data.qpos[:] = q
                    data.qvel[:] = 0.0
                    data.ctrl[:] = 0.0
                    mujoco.mj_forward(model, data)
                    inertia = mass_matrix(model, data)
                    jacobian = planar_jacobian(q)
                    jacobian_singular_values = np.linalg.svd(
                        jacobian, compute_uv=False
                    )
                    acceleration_map = 5.0 * jacobian @ np.linalg.inv(inertia)
                    acceleration_singular_values = np.linalg.svd(
                        acceleration_map, compute_uv=False
                    )
                    record.update(
                        {
                            "jacobian_condition": float(
                                jacobian_singular_values[0]
                                / jacobian_singular_values[-1]
                            ),
                            "jacobian_min_singular_value": float(
                                jacobian_singular_values[-1]
                            ),
                            "inertia_min_eigenvalue": float(
                                np.linalg.eigvalsh(inertia)[0]
                            ),
                            "inertia_max_eigenvalue": float(
                                np.linalg.eigvalsh(inertia)[-1]
                            ),
                            "saturated_cartesian_accel_min": float(
                                acceleration_singular_values[-1]
                            ),
                            "saturated_cartesian_accel_max": float(
                                acceleration_singular_values[0]
                            ),
                        }
                    )
                branches.append(record)

    valid = [item for item in branches if item["joint_limit_valid"]]
    by_radius = []
    for radius in RADIUS_VALUES:
        group = [
            item for item in valid if item["radius_cm"] == float(radius * 100.0)
        ]
        by_radius.append(
            {
                "radius_cm": float(radius * 100.0),
                "valid_branch_fraction": float(
                    sum(item["joint_limit_valid"] for item in branches if item["radius_cm"] == float(radius * 100.0))
                    / (2 * ANGLE_COUNT)
                ),
                "jacobian_condition_p95": float(
                    np.percentile([item["jacobian_condition"] for item in group], 95)
                ),
                "inertia_max_eigenvalue_p95": float(
                    np.percentile(
                        [item["inertia_max_eigenvalue"] for item in group], 95
                    )
                ),
                "saturated_cartesian_accel_min_p05": float(
                    np.percentile(
                        [item["saturated_cartesian_accel_min"] for item in group], 5
                    )
                ),
            }
        )

    return {
        "schema_version": 1,
        "measurement": "official_annulus_kinematic_dynamic_map",
        "sampling": {
            "radii_cm": [float(radius * 100.0) for radius in RADIUS_VALUES],
            "angles": ANGLE_COUNT,
            "branches_per_target": 2,
        },
        "units": {
            "inertia": "joint_torque_seconds_squared_per_radian",
            "cartesian_acceleration": "metres_per_second_squared_per_action_unit",
        },
        "summary_by_radius": by_radius,
        "branch_records": branches,
        "aggregate": {
            "valid_branch_fraction": float(
                sum(item["joint_limit_valid"] for item in branches) / len(branches)
            ),
            "jacobian_condition_p95": float(
                np.percentile([item["jacobian_condition"] for item in valid], 95)
            ),
            "inertia_max_eigenvalue_p95": float(
                np.percentile([item["inertia_max_eigenvalue"] for item in valid], 95)
            ),
            "saturated_cartesian_accel_min_p05": float(
                np.percentile(
                    [item["saturated_cartesian_accel_min"] for item in valid], 5
                )
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True)
    args = parser.parse_args()
    output = Path(args.artifact)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(measure(), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
