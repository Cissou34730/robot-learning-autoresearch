"""Scenario-owned observation representation.

Generic training code never inspects this layout: it only sees the Gymnasium
observation space declared by the scenario environment.
"""

import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH

OBSERVATION_SIZE = 13


def reach_observation(data) -> np.ndarray:
    def wrap_to_pi(angle: float) -> float:
        return float((angle + np.pi) % (2.0 * np.pi) - np.pi)

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
    end_effector = data.site("end_effector").xpos.copy()
    shoulder, elbow = (float(value) for value in data.qpos[:2])
    shoulder_velocity, elbow_velocity = (
        float(value) for value in data.qvel[:2]
    )
    end_effector_velocity = np.asarray(
        [
            -UPPER_ARM_LENGTH * np.sin(shoulder) * shoulder_velocity
            - FOREARM_LENGTH
            * np.sin(shoulder + elbow)
            * (shoulder_velocity + elbow_velocity),
            UPPER_ARM_LENGTH * np.cos(shoulder) * shoulder_velocity
            + FOREARM_LENGTH
            * np.cos(shoulder + elbow)
            * (shoulder_velocity + elbow_velocity),
        ],
        dtype=np.float32,
    )
    target_error = data.mocap_pos[0][:2] - end_effector[:2]
    error_norm = float(np.linalg.norm(target_error))
    if error_norm > 0.0:
        radial_direction = target_error / error_norm
        tangential_direction = np.asarray(
            [-radial_direction[1], radial_direction[0]], dtype=np.float32
        )
        approach_velocity = float(
            np.dot(end_effector_velocity, radial_direction)
        )
        tangential_velocity = float(
            np.dot(end_effector_velocity, tangential_direction)
        )
    else:
        approach_velocity = 0.0
        tangential_velocity = 0.0
    return np.concatenate(
        [
            data.qpos,
            data.qvel,
            end_effector - data.mocap_pos[0],
            [
                wrap_to_pi(shoulder_open - float(data.qpos[0])),
                wrap_to_pi(elbow_open - float(data.qpos[1])),
                wrap_to_pi(shoulder_folded - float(data.qpos[0])),
                wrap_to_pi(elbow_folded - float(data.qpos[1])),
            ],
            [approach_velocity, tangential_velocity],
        ]
    ).astype(np.float32)
