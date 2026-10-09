"""Model-based action prior for the two-joint reach task."""

from __future__ import annotations

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH

JOINT_LIMIT_RAD = float(np.deg2rad(170.0))
MODEL_BASED_KP = 50.0
MODEL_BASED_KD = 14.0


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def select_ik_target(target_xy: np.ndarray) -> np.ndarray:
    return select_ik_solution(target_xy)[1]


def select_ik_solution(target_xy: np.ndarray) -> tuple[str, np.ndarray, float]:
    radius_squared = float(np.dot(target_xy, target_xy))
    target_angle = float(np.arctan2(target_xy[1], target_xy[0]))
    elbow_open = float(
        np.arccos(
            np.clip(
                (radius_squared - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2)
                / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH),
                -1.0,
                1.0,
            )
        )
    )
    solutions: list[tuple[str, np.ndarray, float]] = []
    for branch, elbow in (
        ("positive_elbow", elbow_open),
        ("negative_elbow", -elbow_open),
    ):
        shoulder = _wrap_to_pi(
            target_angle
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )
        qpos = np.array([shoulder, elbow], dtype=np.float64)
        margin = min(JOINT_LIMIT_RAD - abs(shoulder), JOINT_LIMIT_RAD - abs(elbow))
        if margin >= 0.0:
            solutions.append((branch, qpos, margin))
    if not solutions:
        raise RuntimeError("official target has no feasible analytic IK branch")
    return max(solutions, key=lambda item: item[2])


def computed_torque_action(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    target_qpos: np.ndarray,
    *,
    kp: float = MODEL_BASED_KP,
    kd: float = MODEL_BASED_KD,
) -> np.ndarray:
    mass_matrix = np.zeros((model.nv, model.nv), dtype=np.float64)
    mujoco.mj_fullM(model, data, mass_matrix)
    position_error = np.array(
        [
            _wrap_to_pi(float(target_qpos[index] - data.qpos[index]))
            for index in range(2)
        ],
        dtype=np.float64,
    )
    desired_acceleration = kp * position_error - kd * data.qvel[:2]
    torque = mass_matrix[:2, :2] @ desired_acceleration + data.qfrc_bias[:2]
    gear = model.actuator_gear[:2, 0]
    return np.clip(torque / gear, -1.0, 1.0)


def model_based_action(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    target_xy: np.ndarray,
    *,
    kp: float = MODEL_BASED_KP,
    kd: float = MODEL_BASED_KD,
) -> np.ndarray:
    return computed_torque_action(
        model,
        data,
        select_ik_target(target_xy),
        kp=kp,
        kd=kd,
    )
