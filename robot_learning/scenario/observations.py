"""Scenario-owned observation representation.

Generic training code never inspects this layout: it only sees the Gymnasium
observation space declared by the scenario environment.
"""

import numpy as np

JOINT_LIMIT = float(np.deg2rad(170.0))
OBSERVATION_SIZE = 11


def wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


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
        *qvel,
        *limit_margins,
    ]
    return np.asarray(values, dtype=np.float32)
