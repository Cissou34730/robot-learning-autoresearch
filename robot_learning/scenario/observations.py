"""Scenario-owned observation representation.

Generic training code never inspects this layout: it only sees the Gymnasium
observation space declared by the scenario environment.
"""

import numpy as np

from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH

OBSERVATION_SIZE = 11


def inverse_kinematics_branches(
    target_x: float, target_y: float
) -> tuple[np.ndarray, np.ndarray]:
    cos_elbow = (
        target_x**2 + target_y**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))

    def shoulder_for_elbow(elbow: float) -> float:
        return float(
            np.arctan2(target_y, target_x)
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )

    return (
        np.array([shoulder_for_elbow(elbow_open), elbow_open], dtype=np.float64),
        np.array(
            [shoulder_for_elbow(-elbow_open), -elbow_open], dtype=np.float64
        ),
    )


def reach_observation(data) -> np.ndarray:
    def wrap_to_pi(angle: float) -> float:
        return float((angle + np.pi) % (2.0 * np.pi) - np.pi)

    target_x = float(data.mocap_pos[0][0])
    target_y = float(data.mocap_pos[0][1])
    open_branch, folded_branch = inverse_kinematics_branches(target_x, target_y)
    end_effector = data.site("end_effector").xpos.copy()
    return np.concatenate(
        [
            data.qpos,
            data.qvel,
            end_effector - data.mocap_pos[0],
            [
                wrap_to_pi(open_branch[0] - float(data.qpos[0])),
                wrap_to_pi(open_branch[1] - float(data.qpos[1])),
                wrap_to_pi(folded_branch[0] - float(data.qpos[0])),
                wrap_to_pi(folded_branch[1] - float(data.qpos[1])),
            ],
        ]
    ).astype(np.float32)
