"""Scenario-owned observation representation.

Generic training code never inspects this layout: it only sees the Gymnasium
observation space declared by the scenario environment.
"""

import numpy as np

JOINT_LIMIT = float(np.deg2rad(170.0))
TASK_SPACE_VELOCITY_SCALE = 1.0
OBSERVATION_SIZE = 13


def wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _task_space_velocity(qpos: np.ndarray, qvel: np.ndarray) -> np.ndarray:
    """Return the planar end-effector velocity from the joint state."""
    link_sum = float(qpos[0] + qpos[1])
    jacobian = np.array(
        [
            [
                -0.12 * np.sin(qpos[0]) - 0.10 * np.sin(link_sum),
                -0.10 * np.sin(link_sum),
            ],
            [
                0.12 * np.cos(qpos[0]) + 0.10 * np.cos(link_sum),
                0.10 * np.cos(link_sum),
            ],
        ],
        dtype=np.float64,
    )
    return jacobian @ qvel


def reach_observation(data) -> np.ndarray:
    target = np.asarray(data.mocap_pos[0, :2], dtype=np.float64)
    end_effector = np.asarray(data.site("end_effector").xpos[:2], dtype=np.float64)
    target_radius = float(np.linalg.norm(target))
    target_angle = float(np.arctan2(target[1], target[0]))
    radial = target / target_radius
    tangential = np.array([-radial[1], radial[0]], dtype=np.float64)
    target_error = target - end_effector

    qpos = np.asarray(data.qpos[:2], dtype=np.float64)
    qvel = np.asarray(data.qvel[:2], dtype=np.float64)
    end_effector_velocity = _task_space_velocity(qpos, qvel)
    radial_velocity, tangential_velocity = np.dot(
        np.array([radial, tangential], dtype=np.float64), end_effector_velocity
    )
    task_space_velocity = np.clip(
        np.array([radial_velocity, tangential_velocity], dtype=np.float64)
        / TASK_SPACE_VELOCITY_SCALE,
        -1.0,
        1.0,
    )
    limit_margins = np.array(
        [
            qpos[0] + JOINT_LIMIT,
            JOINT_LIMIT - qpos[0],
            qpos[1] + JOINT_LIMIT,
            JOINT_LIMIT - qpos[1],
        ],
        dtype=np.float64,
    ) / JOINT_LIMIT
    values = [
        target_radius,
        float(np.dot(target_error, radial)),
        float(np.dot(target_error, tangential)),
        wrap_to_pi(float(qpos[0]) - target_angle),
        float(qpos[1]),
        *task_space_velocity,
        *qvel,
        *limit_margins,
    ]
    return np.asarray(values, dtype=np.float32)
