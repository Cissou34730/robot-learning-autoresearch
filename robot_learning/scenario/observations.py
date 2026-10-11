"""Scenario-owned observation representation.

Generic training code never inspects this layout: it only sees the Gymnasium
observation space declared by the scenario environment.
"""

import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH

OBSERVATION_SIZE = 11


def wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def inverse_kinematic_branches(
    target_x: float, target_y: float
) -> tuple[np.ndarray, np.ndarray]:
    cos_elbow = (
        target_x**2 + target_y**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))

    def joint_target(elbow: float) -> np.ndarray:
        shoulder = float(
            np.arctan2(target_y, target_x)
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )
        return np.array([shoulder, elbow], dtype=np.float64)

    return joint_target(elbow_open), joint_target(-elbow_open)


def reach_observation(data) -> np.ndarray:
    target_x = float(data.mocap_pos[0][0])
    target_y = float(data.mocap_pos[0][1])
    open_branch, folded_branch = inverse_kinematic_branches(target_x, target_y)
    qpos = np.asarray(data.qpos, dtype=np.float64)
    end_effector = data.site("end_effector").xpos.copy()
    return np.concatenate(
        [
            qpos,
            data.qvel,
            end_effector - data.mocap_pos[0],
            [
                wrap_to_pi(open_branch[0] - qpos[0]),
                wrap_to_pi(open_branch[1] - qpos[1]),
                wrap_to_pi(folded_branch[0] - qpos[0]),
                wrap_to_pi(folded_branch[1] - qpos[1]),
            ],
        ]
    ).astype(np.float32)
