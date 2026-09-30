"""Scenario-owned observation representation.

Generic training code never inspects this layout: it only sees the Gymnasium
observation space declared by the scenario environment.
"""

import numpy as np

from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH

JOINT_LIMIT = float(np.deg2rad(170.0))
OBSERVATION_SIZE = 14


def wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def analytic_ik_references(target: np.ndarray) -> np.ndarray:
    def shoulder_for_elbow(elbow: float) -> float:
        return float(
            np.arctan2(target_y, target_x)
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )

    target_x = float(target[0])
    target_y = float(target[1])
    cos_elbow = (
        target_x**2 + target_y**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))
    shoulder_open = shoulder_for_elbow(elbow_open)
    elbow_folded = -elbow_open
    shoulder_folded = shoulder_for_elbow(elbow_folded)
    return np.array(
        [
            [
                wrap_to_pi(shoulder_open),
                wrap_to_pi(elbow_open),
            ],
            [
                wrap_to_pi(shoulder_folded),
                wrap_to_pi(elbow_folded),
            ],
        ],
        dtype=np.float64,
    )


def select_analytic_ik_reference(
    target: np.ndarray, qpos: np.ndarray
) -> tuple[np.ndarray, int]:
    references = analytic_ik_references(target)
    valid = np.all(np.abs(references) <= JOINT_LIMIT, axis=1)
    if not np.any(valid):
        raise ValueError("target has no joint-limit-compatible IK branch")

    errors = np.array(
        [
            wrap_to_pi(float(reference[0]) - float(qpos[0])) ** 2
            + wrap_to_pi(float(reference[1]) - float(qpos[1])) ** 2
            for reference in references
        ]
    )
    errors[~valid] = np.inf
    branch = int(np.argmin(errors))
    return references[branch].copy(), branch


def reach_observation(
    data,
    *,
    joint_reference: np.ndarray | None = None,
    ik_branch: int | None = None,
) -> np.ndarray:
    end_effector = data.site("end_effector").xpos.copy()
    target = np.asarray(data.mocap_pos[0, :2], dtype=np.float64)
    references = analytic_ik_references(target)
    branch_errors = np.array(
        [
            wrap_to_pi(float(references[0, 0]) - float(data.qpos[0])),
            wrap_to_pi(float(references[0, 1]) - float(data.qpos[1])),
            wrap_to_pi(float(references[1, 0]) - float(data.qpos[0])),
            wrap_to_pi(float(references[1, 1]) - float(data.qpos[1])),
        ],
        dtype=np.float64,
    )
    values = [
        *np.asarray(data.qpos[:2], dtype=np.float64),
        *np.asarray(data.qvel[:2], dtype=np.float64),
        *np.asarray(end_effector - data.mocap_pos[0], dtype=np.float64),
        *branch_errors,
    ]
    if joint_reference is not None:
        if ik_branch not in (0, 1):
            raise ValueError("ik_branch must be 0 or 1 with a joint reference")
        values.extend(np.asarray(joint_reference, dtype=np.float64))
        values.append(1.0 if ik_branch == 0 else -1.0)
    return np.asarray(values, dtype=np.float32)
