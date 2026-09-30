"""Scenario-owned observation representation.

Generic training code never inspects this layout: it only sees the Gymnasium
observation space declared by the scenario environment.
"""

import numpy as np

from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH

OBSERVATION_SIZE = 17


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def inverse_kinematic_branch_errors(data) -> np.ndarray:
    def shoulder_for_elbow(elbow: float) -> float:
        return float(
            np.arctan2(target_y, target_x)
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )

    target_x = float(data.mocap_pos[0][0])
    target_y = float(data.mocap_pos[0][1])
    cos_elbow = (
        target_x**2 + target_y**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))
    shoulder_open = shoulder_for_elbow(elbow_open)
    elbow_folded = -elbow_open
    shoulder_folded = shoulder_for_elbow(elbow_folded)
    return np.asarray(
        [
            _wrap_to_pi(shoulder_open - float(data.qpos[0])),
            _wrap_to_pi(elbow_open - float(data.qpos[1])),
            _wrap_to_pi(shoulder_folded - float(data.qpos[0])),
            _wrap_to_pi(elbow_folded - float(data.qpos[1])),
        ],
        dtype=np.float64,
    )


def branch_configuration_error(data) -> float:
    errors = inverse_kinematic_branch_errors(data).reshape(2, 2)
    return float(min(np.linalg.norm(errors[0]), np.linalg.norm(errors[1])))


def _planar_jacobian(data) -> np.ndarray:
    q1, q2 = np.asarray(data.qpos[:2], dtype=np.float64)
    q12 = q1 + q2
    return np.asarray(
        [
            [
                -UPPER_ARM_LENGTH * np.sin(q1) - FOREARM_LENGTH * np.sin(q12),
                -FOREARM_LENGTH * np.sin(q12),
            ],
            [
                UPPER_ARM_LENGTH * np.cos(q1) + FOREARM_LENGTH * np.cos(q12),
                FOREARM_LENGTH * np.cos(q12),
            ],
        ],
        dtype=np.float64,
    )


def task_aligned_regulation_state(data) -> np.ndarray:
    end_effector = np.asarray(data.site("end_effector").xpos, dtype=np.float64)
    target_relative = end_effector - np.asarray(
        data.mocap_pos[0], dtype=np.float64
    )
    planar_jacobian = _planar_jacobian(data)
    planar_velocity = planar_jacobian @ np.asarray(data.qvel[:2], dtype=np.float64)
    end_effector_velocity = np.asarray(
        [planar_velocity[0], planar_velocity[1], 0.0], dtype=np.float64
    )

    radial_distance = float(np.linalg.norm(target_relative[:2]))
    if radial_distance > np.finfo(np.float64).eps:
        radial_direction = target_relative[:2] / radial_distance
        tangential_direction = np.asarray(
            [-radial_direction[1], radial_direction[0]], dtype=np.float64
        )
        radial_velocity = float(np.dot(planar_velocity, radial_direction))
        tangential_velocity = float(
            np.dot(planar_velocity, tangential_direction)
        )
    else:
        radial_velocity = 0.0
        tangential_velocity = 0.0

    singular_values = np.linalg.svd(planar_jacobian, compute_uv=False)
    jacobian_conditioning = float(
        singular_values[-1] / max(singular_values[0], np.finfo(np.float64).eps)
    )
    return np.concatenate(
        [
            end_effector_velocity,
            np.asarray(
                [radial_velocity, tangential_velocity, jacobian_conditioning],
                dtype=np.float64,
            ),
        ]
    )


def reach_observation(data) -> np.ndarray:
    branch_errors = inverse_kinematic_branch_errors(data)
    end_effector = data.site("end_effector").xpos.copy()
    return np.concatenate(
        [
            data.qpos,
            data.qvel,
            end_effector - data.mocap_pos[0],
            branch_errors,
            task_aligned_regulation_state(data),
        ]
    ).astype(np.float32)
