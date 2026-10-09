"""Scenario-owned observation representation.

Generic training code never inspects this layout: it only sees the Gymnasium
observation space declared by the scenario environment.
"""

import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.model_based_control import (
    JOINT_LIMIT_RAD,
    select_ik_solution,
)

OBSERVATION_SIZE = 16


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
        ]
    ).astype(np.float32)


def branch_limit_conditioned_observation(data) -> np.ndarray:
    """Add a static, limit-aware joint target without phase or action history."""
    base = reach_observation(data)
    target_xy = np.asarray(data.mocap_pos[0][:2], dtype=np.float64)
    branch, target_qpos, limit_margin = select_ik_solution(target_xy)
    branch_indicator = (
        np.array([1.0, 0.0], dtype=np.float64)
        if branch == "positive_elbow"
        else np.array([0.0, 1.0], dtype=np.float64)
    )
    return np.concatenate(
        [
            base,
            target_qpos,
            branch_indicator,
            [np.clip(limit_margin / JOINT_LIMIT_RAD, 0.0, 1.0)],
        ]
    ).astype(np.float32)
