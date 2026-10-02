"""Scenario-owned observation representation.

Generic training code never inspects this layout: it only sees the Gymnasium
observation space declared by the scenario environment.
"""

import numpy as np

from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH

OBSERVATION_SIZE = 19


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
    branch_configurations = (
        (wrap_to_pi(shoulder_open), elbow_open),
        (wrap_to_pi(shoulder_folded), elbow_folded),
    )

    joint_ranges = np.asarray(data.model.jnt_range[:2], dtype=np.float64)

    def limit_margin(joint: float, limits: np.ndarray) -> float:
        return min(joint - float(limits[0]), float(limits[1]) - joint)

    actual_limit_margins = [
        limit_margin(float(joint), limits)
        for joint, limits in zip(data.qpos, joint_ranges, strict=True)
    ]
    branch_limit_margins = [
        [
            limit_margin(float(joint), limits)
            for joint, limits in zip(configuration, joint_ranges, strict=True)
        ]
        for configuration in branch_configurations
    ]
    branch_min_margins = [min(margins) for margins in branch_limit_margins]
    branch_feasible = [float(margin >= 0.0) for margin in branch_min_margins]
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
            actual_limit_margins,
            branch_limit_margins[0],
            branch_limit_margins[1],
            branch_feasible,
        ]
    ).astype(np.float32)
