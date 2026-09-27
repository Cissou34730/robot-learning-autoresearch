"""Scenario-owned observation representation.

Generic training code never inspects this layout: it only sees the Gymnasium
observation space declared by the scenario environment.
"""

import numpy as np

from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH

OBSERVATION_SIZE = 23
JOINT_LIMIT_RADIANS = np.deg2rad(170.0)


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
    branch_targets = np.asarray(
        [
            [wrap_to_pi(shoulder_open), elbow_open],
            [wrap_to_pi(shoulder_folded), elbow_folded],
        ],
        dtype=np.float64,
    )
    end_effector = data.site("end_effector").xpos.copy()
    current_joints = np.asarray(data.qpos[:2], dtype=np.float64)
    branch_errors = np.asarray(
        [
            wrap_to_pi(target - current)
            for target, current in zip(branch_targets.flat, np.tile(current_joints, 2))
        ],
        dtype=np.float64,
    )
    branch_limit_margins = (
        JOINT_LIMIT_RADIANS - np.abs(branch_targets)
    ).reshape(-1)
    return np.concatenate(
        [
            data.qpos,
            data.qvel,
            end_effector - data.mocap_pos[0],
            branch_errors,
            np.sin(branch_errors),
            np.cos(branch_errors),
            branch_limit_margins,
        ]
    ).astype(np.float32)
