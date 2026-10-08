"""Characterize compiled arm geometry and low-level plant behavior."""

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


def wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def inverse_kinematics(radius: float, angle: float, elbow: float) -> np.ndarray:
    shoulder = angle - np.arctan2(
        FOREARM_LENGTH * np.sin(elbow),
        UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
    )
    return np.array([wrap_to_pi(float(shoulder)), elbow], dtype=np.float64)


def forward_position(q: np.ndarray) -> np.ndarray:
    return np.array(
        [
            UPPER_ARM_LENGTH * np.cos(q[0])
            + FOREARM_LENGTH * np.cos(q[0] + q[1]),
            UPPER_ARM_LENGTH * np.sin(q[0])
            + FOREARM_LENGTH * np.sin(q[0] + q[1]),
        ],
        dtype=np.float64,
    )


def jacobian(q: np.ndarray) -> np.ndarray:
    return np.array(
        [
            [
                -UPPER_ARM_LENGTH * np.sin(q[0])
                - FOREARM_LENGTH * np.sin(q[0] + q[1]),
                -FOREARM_LENGTH * np.sin(q[0] + q[1]),
            ],
            [
                UPPER_ARM_LENGTH * np.cos(q[0])
                + FOREARM_LENGTH * np.cos(q[0] + q[1]),
                FOREARM_LENGTH * np.cos(q[0] + q[1]),
            ],
        ],
        dtype=np.float64,
    )


def characterize_geometry(model: mujoco.MjModel) -> dict:
    radii = np.linspace(0.06, 0.20, 29)
    angles = np.linspace(-np.pi, np.pi, 73)[:-1]
    branches = {
        "elbow_positive": lambda elbow: elbow,
        "elbow_negative": lambda elbow: -elbow,
    }
    joint_ranges = np.asarray(model.jnt_range[:2], dtype=np.float64)
    summaries: dict[str, dict] = {}
    target_branch_feasibility = 0
    total_targets = len(radii) * len(angles)
    for name, elbow_sign in branches.items():
        feasible_count = 0
        min_margin = float("inf")
        min_singular_value = float("inf")
        max_residual = 0.0
        worst_margin: dict | None = None
        worst_condition: dict | None = None
        for radius in radii:
            elbow_magnitude = np.arccos(
                np.clip(
                    (
                        radius**2
                        - UPPER_ARM_LENGTH**2
                        - FOREARM_LENGTH**2
                    )
                    / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH),
                    -1.0,
                    1.0,
                )
            )
            elbow = elbow_sign(float(elbow_magnitude))
            for angle in angles:
                q = inverse_kinematics(float(radius), float(angle), elbow)
                target = np.array(
                    [radius * np.cos(angle), radius * np.sin(angle)]
                )
                residual = float(np.linalg.norm(forward_position(q) - target))
                margin = float(
                    np.min(
                        np.minimum(
                            q - joint_ranges[:, 0], joint_ranges[:, 1] - q
                        )
                    )
                )
                singular_values = np.linalg.svd(jacobian(q), compute_uv=False)
                smallest_singular_value = float(singular_values[-1])
                feasible = bool(margin >= -1e-9)
                feasible_count += int(feasible)
                if margin < min_margin:
                    min_margin = margin
                    worst_margin = {
                        "radius_m": float(radius),
                        "angle_degrees": float(np.degrees(angle)),
                        "q_degrees": np.degrees(q).tolist(),
                        "margin_degrees": float(np.degrees(margin)),
                    }
                if smallest_singular_value < min_singular_value:
                    min_singular_value = smallest_singular_value
                    worst_condition = {
                        "radius_m": float(radius),
                        "angle_degrees": float(np.degrees(angle)),
                        "q_degrees": np.degrees(q).tolist(),
                        "smallest_singular_value_m": smallest_singular_value,
                    }
                max_residual = max(max_residual, residual)
        summaries[name] = {
            "target_samples": total_targets,
            "feasible_samples": feasible_count,
            "feasible_fraction": feasible_count / total_targets,
            "minimum_joint_margin_degrees": float(np.degrees(min_margin)),
            "minimum_jacobian_singular_value_m": min_singular_value,
            "maximum_analytic_fk_residual_m": max_residual,
            "worst_joint_margin": worst_margin,
            "worst_jacobian_condition": worst_condition,
        }

    for radius in radii:
        elbow_magnitude = np.arccos(
            np.clip(
                (
                    radius**2
                    - UPPER_ARM_LENGTH**2
                    - FOREARM_LENGTH**2
                )
                / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH),
                -1.0,
                1.0,
            )
        )
        for angle in angles:
            feasible = False
            for elbow in (elbow_magnitude, -elbow_magnitude):
                q = inverse_kinematics(float(radius), float(angle), float(elbow))
                feasible |= bool(
                    np.all(q >= joint_ranges[:, 0] - 1e-9)
                    and np.all(q <= joint_ranges[:, 1] + 1e-9)
                )
            target_branch_feasibility += int(feasible)

    return {
        "grid": {
            "radius_range_m": [float(radii[0]), float(radii[-1])],
            "angle_range_degrees": [-180.0, 180.0],
            "radius_samples": len(radii),
            "angle_samples": len(angles),
        },
        "target_with_at_least_one_feasible_branch": target_branch_feasibility,
        "target_feasibility_fraction": target_branch_feasibility / total_targets,
        "branches": summaries,
    }


def dynamic_probe(
    model: mujoco.MjModel,
    q: np.ndarray,
    qvel: np.ndarray,
    ctrl: np.ndarray,
) -> dict:
    data = mujoco.MjData(model)
    data.qpos[:2] = q
    data.qvel[:2] = qvel
    data.ctrl[:2] = ctrl
    mujoco.mj_forward(model, data)
    return {
        "q_degrees": np.degrees(q).tolist(),
        "qvel_rad_s": qvel.tolist(),
        "ctrl": ctrl.tolist(),
        "actuator_force": data.actuator_force[:2].tolist(),
        "generalized_actuator_force": data.qfrc_actuator[:2].tolist(),
        "qacc_rad_s2": data.qacc[:2].tolist(),
    }


def free_decay(model: mujoco.MjModel) -> dict:
    data = mujoco.MjData(model)
    data.qpos[:2] = [0.35, -0.8]
    data.qvel[:2] = [1.0, -0.7]
    data.ctrl[:] = 0.0
    mujoco.mj_forward(model, data)
    initial_velocity = data.qvel[:2].copy()
    for _ in range(500):
        mujoco.mj_step(model, data)
    return {
        "duration_seconds": 500 * model.opt.timestep,
        "initial_qvel_rad_s": initial_velocity.tolist(),
        "final_q_degrees": np.degrees(data.qpos[:2]).tolist(),
        "final_qvel_rad_s": data.qvel[:2].tolist(),
        "maximum_abs_qvel_rad_s": float(np.max(np.abs(data.qvel[:2]))),
    }


def characterize(model: mujoco.MjModel) -> dict:
    nominal_q = np.array([0.4, -1.0], dtype=np.float64)
    return {
        "schema_version": 1,
        "model": "two_joint_arm",
        "timestep_seconds": float(model.opt.timestep),
        "joint_ranges_degrees": np.degrees(model.jnt_range[:2]).tolist(),
        "body_mass_kg": model.body_mass.tolist(),
        "body_inertia": model.body_inertia.tolist(),
        "actuator": {
            "gear": model.actuator_gear[:2, 0].tolist(),
            "control_range": model.actuator_ctrlrange[:2].tolist(),
            "joint_transmission": model.actuator_trnid[:2, 0].tolist(),
        },
        "geometry": characterize_geometry(model),
        "dynamic_probes": [
            dynamic_probe(
                model,
                nominal_q,
                np.zeros(2, dtype=np.float64),
                np.array([1.0, 0.0], dtype=np.float64),
            ),
            dynamic_probe(
                model,
                nominal_q,
                np.zeros(2, dtype=np.float64),
                np.array([0.0, 1.0], dtype=np.float64),
            ),
            dynamic_probe(
                model,
                nominal_q,
                np.zeros(2, dtype=np.float64),
                np.array([1.0, 1.0], dtype=np.float64),
            ),
        ],
        "free_decay": free_decay(model),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True)
    args = parser.parse_args()

    model = mujoco.MjModel.from_xml_path(str(TWO_JOINT_ARM_XML_PATH))
    artifact = Path(args.artifact)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        json.dumps(characterize(model), indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
