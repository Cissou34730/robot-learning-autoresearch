"""Scenario-owned observation representation.

Generic training code never inspects this layout: it only sees the Gymnasium
observation space declared by the scenario environment.
"""

import numpy as np

from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH

OBSERVATION_SIZE = 11


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _branch_targets(data) -> np.ndarray:
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
    return np.array(
        [
            [shoulder_open, elbow_open],
            [shoulder_folded, elbow_folded],
        ],
        dtype=np.float64,
    )


def reach_observation(data, branch_index: int | None = None) -> np.ndarray:
    branch_targets = _branch_targets(data)
    end_effector = data.site("end_effector").xpos.copy()
    qpos = np.asarray(data.qpos[:2], dtype=np.float64)
    branch_errors = np.array(
        [
            _wrap_to_pi(branch_targets[0, 0] - qpos[0]),
            _wrap_to_pi(branch_targets[0, 1] - qpos[1]),
            _wrap_to_pi(branch_targets[1, 0] - qpos[0]),
            _wrap_to_pi(branch_targets[1, 1] - qpos[1]),
        ],
        dtype=np.float64,
    )
    if branch_index is None:
        target_errors = branch_errors
        branch_identity = np.empty(0, dtype=np.float64)
    else:
        if branch_index not in (0, 1):
            raise ValueError("branch_index must be 0 or 1")
        target_errors = branch_errors[2 * branch_index : 2 * branch_index + 2]
        branch_identity = np.eye(2, dtype=np.float64)[branch_index]
    return np.concatenate(
        [
            qpos,
            np.asarray(data.qvel[:2], dtype=np.float64),
            end_effector - data.mocap_pos[0],
            target_errors,
            branch_identity,
        ]
    ).astype(np.float32)


def ik_branch_targets(data) -> np.ndarray:
    return _branch_targets(data)
