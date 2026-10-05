"""Measure transient and hold sensitivity of the two-joint arm."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from robot_learning.scenario.environment import TwoJointArmReachEnv

# Keep the probe's design grid explicit so completed artifacts remain reproducible.
RADII = (0.06, 0.10, 0.14, 0.18, 0.20)
ANGLES = (-np.pi, -np.pi / 2.0, 0.0, np.pi / 2.0)
VELOCITY_MAGNITUDES = (0.05, 0.10, 0.20, 0.50)
IMPULSES = (
    (1.0, 0.0),
    (-1.0, 0.0),
    (0.0, 1.0),
    (0.0, -1.0),
)
HOLD_STEPS = 100


def inverse_kinematics(radius: float, angle: float, branch: int) -> tuple[float, float]:
    cosine = (radius**2 - 0.12**2 - 0.10**2) / (2.0 * 0.12 * 0.10)
    elbow = branch * float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    shoulder = angle - np.arctan2(0.10 * np.sin(elbow), 0.12 + 0.10 * np.cos(elbow))
    shoulder = float((shoulder + np.pi) % (2.0 * np.pi) - np.pi)
    return shoulder, elbow


def set_configuration(
    env: TwoJointArmReachEnv,
    radius: float,
    angle: float,
    branch: int,
) -> bool:
    shoulder, elbow = inverse_kinematics(radius, angle, branch)
    joint_limits = np.asarray(env.model.jnt_range[:2], dtype=np.float64)
    if np.any(np.asarray((shoulder, elbow)) < joint_limits[:, 0]) or np.any(
        np.asarray((shoulder, elbow)) > joint_limits[:, 1]
    ):
        return False
    env.data.qpos[:] = (shoulder, elbow)
    env.data.qvel[:] = 0.0
    env.data.ctrl[:] = 0.0
    env.data.mocap_pos[0] = (
        radius * np.cos(angle),
        radius * np.sin(angle),
        env.data.mocap_pos[0][2],
    )
    import mujoco

    mujoco.mj_forward(env.model, env.data)
    env._step_count = 0
    env._previous_distance = env._distance_to_target()
    env._held_steps = 0
    env._outside_after_hold = False
    return True


def run_sequence(
    env: TwoJointArmReachEnv,
    actions: list[np.ndarray],
) -> dict:
    distances: list[float] = []
    speeds: list[float] = []
    for action in actions:
        _, _, terminated, truncated, info = env.step(action)
        distances.append(float(info["distance"]))
        speeds.append(float(np.linalg.norm(env.data.qvel)))
        if terminated or truncated:
            break
    distances_array = np.asarray(distances, dtype=np.float64)
    outside = np.flatnonzero(distances_array > env.success_threshold)
    return {
        "steps": len(distances),
        "max_distance_cm": float(np.max(distances_array) * 100.0),
        "final_distance_cm": float(distances_array[-1] * 100.0),
        "peak_joint_speed_rad_s": float(max(speeds)),
        "first_outside_step": int(outside[0] + 1) if outside.size else None,
        "completed_hold": bool(len(distances) == HOLD_STEPS and not outside.size),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()

    env = TwoJointArmReachEnv()
    env.reset(seed=0)
    static_hold: list[dict] = []
    velocity_perturbations: list[dict] = []
    impulse_responses: list[dict] = []

    for radius in RADII:
        for angle in ANGLES:
            for branch in (-1, 1):
                if not set_configuration(env, radius, angle, branch):
                    continue
                target = {"radius_cm": radius * 100.0, "angle_degrees": np.degrees(angle)}
                static = run_sequence(
                    env, [np.zeros(2, dtype=np.float64) for _ in range(HOLD_STEPS)]
                )
                static_hold.append({**target, "branch": branch, **static})

                for magnitude in VELOCITY_MAGNITUDES:
                    if not set_configuration(env, radius, angle, branch):
                        continue
                    env.data.qvel[0] = magnitude
                    result = run_sequence(
                        env,
                        [np.zeros(2, dtype=np.float64) for _ in range(HOLD_STEPS)],
                    )
                    velocity_perturbations.append(
                        {
                            **target,
                            "branch": branch,
                            "initial_velocity_joint": 0,
                            "initial_velocity_rad_s": magnitude,
                            **result,
                        }
                    )

                for impulse in IMPULSES:
                    if not set_configuration(env, radius, angle, branch):
                        continue
                    actions = [np.asarray(impulse, dtype=np.float64)] + [
                        np.zeros(2, dtype=np.float64) for _ in range(HOLD_STEPS - 1)
                    ]
                    result = run_sequence(env, actions)
                    impulse_responses.append(
                        {
                            **target,
                            "branch": branch,
                            "impulse": list(impulse),
                            **result,
                        }
                    )

    artifact = {
        "schema_version": 1,
        "experiment": "initial_dynamics_probe",
        "control_interval_seconds": 0.02,
        "hold_steps": HOLD_STEPS,
        "threshold_cm": 1.0,
        "design": {
            "radii_cm": [radius * 100.0 for radius in RADII],
            "angles_degrees": [float(np.degrees(angle)) for angle in ANGLES],
            "velocity_magnitudes_rad_s": list(VELOCITY_MAGNITUDES),
            "impulses": [list(impulse) for impulse in IMPULSES],
        },
        "static_hold": static_hold,
        "velocity_perturbations": velocity_perturbations,
        "impulse_responses": impulse_responses,
    }
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
