"""Characterize official target geometry and instantiated arm dynamics."""

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
from contracts.task_spec import TARGET_RADIUS_RANGE


def wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def inverse_kinematics(radius: float, angle: float) -> list[tuple[float, float]]:
    cosine = (
        radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_magnitude = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    branches = []
    for elbow in (elbow_magnitude, -elbow_magnitude):
        shoulder = angle - np.arctan2(
            FOREARM_LENGTH * np.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
        )
        branches.append((wrap_to_pi(float(shoulder)), elbow))
    return branches


def jacobian(q1: float, q2: float) -> np.ndarray:
    distal_angle = q1 + q2
    return np.array(
        [
            [
                -UPPER_ARM_LENGTH * np.sin(q1)
                - FOREARM_LENGTH * np.sin(distal_angle),
                -FOREARM_LENGTH * np.sin(distal_angle),
            ],
            [
                UPPER_ARM_LENGTH * np.cos(q1)
                + FOREARM_LENGTH * np.cos(distal_angle),
                FOREARM_LENGTH * np.cos(distal_angle),
            ],
        ],
        dtype=np.float64,
    )


def characterize(samples: int, seed: int) -> dict:
    if samples < 1:
        raise ValueError("samples must be positive")

    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    data = mujoco.MjData(model)
    rng = np.random.default_rng(seed)
    radii = rng.uniform(*TARGET_RADIUS_RANGE, size=samples)
    angles = rng.uniform(-np.pi, np.pi, size=samples)
    lower = np.radians(np.array([-170.0, -170.0]))
    upper = np.radians(np.array([170.0, 170.0]))

    branch_records: list[list[dict]] = []
    valid_counts = [0, 0]
    minimum_margins = [float("inf"), float("inf")]
    minimum_singular_values = [float("inf"), float("inf")]
    maximum_condition_numbers = [0.0, 0.0]
    acceleration_norms: list[float] = []

    for radius, angle in zip(radii, angles):
        target_branches = []
        for branch_index, (q1, q2) in enumerate(inverse_kinematics(float(radius), float(angle))):
            q = np.array([q1, q2], dtype=np.float64)
            margins = np.minimum(q - lower, upper - q)
            matrix = jacobian(q1, q2)
            singular_values = np.linalg.svd(matrix, compute_uv=False)
            valid = bool(np.all(margins >= 0.0))
            if valid:
                valid_counts[branch_index] += 1
            minimum_margins[branch_index] = min(
                minimum_margins[branch_index], float(np.min(margins))
            )
            minimum_singular_values[branch_index] = min(
                minimum_singular_values[branch_index], float(np.min(singular_values))
            )
            condition_number = float(singular_values[0] / singular_values[-1])
            maximum_condition_numbers[branch_index] = max(
                maximum_condition_numbers[branch_index], condition_number
            )

            data.qpos[:] = q
            data.qvel[:] = 0.0
            data.ctrl[:] = [1.0, 1.0]
            mujoco.mj_forward(model, data)
            acceleration_norms.append(float(np.linalg.norm(data.qacc)))
            target_branches.append(
                {
                    "q1_degrees": float(np.degrees(q1)),
                    "q2_degrees": float(np.degrees(q2)),
                    "joint_limit_margin_degrees": float(np.degrees(np.min(margins))),
                    "jacobian_min_singular_value_m": float(np.min(singular_values)),
                    "jacobian_condition_number": condition_number,
                    "joint_limits_valid": valid,
                }
            )
        branch_records.append(target_branches)

    return {
        "schema_version": 1,
        "sample_count": samples,
        "seed": seed,
        "target_radius_range_m": list(TARGET_RADIUS_RANGE),
        "branch_summary": [
            {
                "branch": index,
                "joint_limits_valid_fraction": valid_counts[index] / samples,
                "minimum_joint_limit_margin_degrees": float(
                    np.degrees(minimum_margins[index])
                ),
                "minimum_jacobian_singular_value_m": minimum_singular_values[index],
                "maximum_jacobian_condition_number": maximum_condition_numbers[index],
            }
            for index in range(2)
        ],
        "dynamics": {
            "timestep_s": float(model.opt.timestep),
            "actuator_gear": [float(value) for value in model.actuator_gear[:, 0]],
            "body_masses_kg": [float(value) for value in model.body_mass],
            "body_inertias": model.body_inertia.tolist(),
            "zero_velocity_unit_control_acceleration_norm_range": [
                float(np.min(acceleration_norms)),
                float(np.max(acceleration_norms)),
            ],
        },
        "samples": branch_records,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    artifact = characterize(args.samples, args.seed)
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
