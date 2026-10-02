"""Scenario-owned observation representation.

Generic training code never inspects this layout: it only sees the Gymnasium
observation space declared by the scenario environment.
"""

import numpy as np

from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH

OBSERVATION_SIZE = 19


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def reach_observation(data) -> np.ndarray:
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
    target_angle = float(np.arctan2(target_y, target_x))
    cos_elbow = (
        target_x**2 + target_y**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))
    shoulder_open = shoulder_for_elbow(elbow_open)
    elbow_folded = -elbow_open
    shoulder_folded = shoulder_for_elbow(elbow_folded)
    end_effector = data.site("end_effector").xpos.copy()
    target_angle_sin = np.sin(target_angle)
    target_angle_cos = np.cos(target_angle)
    displacement = end_effector[:2] - data.mocap_pos[0][:2]
    radial_axis = np.array([target_angle_cos, target_angle_sin])
    tangential_axis = np.array([-target_angle_sin, target_angle_cos])
    target_frame_displacement = [
        np.dot(displacement, radial_axis),
        np.dot(displacement, tangential_axis),
    ]
    return np.concatenate(
        [
            data.qpos,
            data.qvel,
            end_effector - data.mocap_pos[0],
            target_frame_displacement,
            [target_angle_sin, target_angle_cos],
            [shoulder_open, elbow_open, shoulder_folded, elbow_folded],
            [
                _wrap_to_pi(shoulder_open - float(data.qpos[0])),
                _wrap_to_pi(elbow_open - float(data.qpos[1])),
                _wrap_to_pi(shoulder_folded - float(data.qpos[0])),
                _wrap_to_pi(elbow_folded - float(data.qpos[1])),
            ],
        ]
    ).astype(np.float32)
