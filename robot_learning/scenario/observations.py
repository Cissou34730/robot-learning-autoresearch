"""Scenario-owned observation representation.

Generic training code never inspects this layout: it only sees the Gymnasium
observation space declared by the scenario environment.
"""

import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH

OBSERVATION_SIZE = 9


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
    joint_limit = np.pi * 170.0 / 180.0
    branch_targets = [
        np.array([shoulder_open, elbow_open], dtype=np.float64),
        np.array([shoulder_folded, elbow_folded], dtype=np.float64),
    ]
    branch_margins = [
        float(np.min(joint_limit - np.abs(target))) for target in branch_targets
    ]
    feasible_branches = [
        index
        for index, margin in enumerate(branch_margins)
        if margin >= 0.0
    ]
    selected_branch = max(
        feasible_branches or range(len(branch_targets)),
        key=lambda index: branch_margins[index],
    )
    selected_target = branch_targets[selected_branch]
    end_effector = data.site("end_effector").xpos.copy()
    return np.concatenate(
        [
            data.qpos,
            data.qvel,
            end_effector - data.mocap_pos[0],
            [
                wrap_to_pi(float(selected_target[0]) - float(data.qpos[0])),
                wrap_to_pi(float(selected_target[1]) - float(data.qpos[1])),
            ],
        ]
    ).astype(np.float32)
