"""Scenario-owned observation representation.

Generic training code never inspects this layout: it only sees the Gymnasium
observation space declared by the scenario environment.
"""

import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH

OBSERVATION_SIZE = 11


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _ik_solutions(data) -> tuple[tuple[float, float], tuple[float, float]]:
    target_x = float(data.mocap_pos[0][0])
    target_y = float(data.mocap_pos[0][1])
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

    shoulder_open = shoulder_for_elbow(elbow_open)
    elbow_folded = -elbow_open
    shoulder_folded = shoulder_for_elbow(elbow_folded)
    return (shoulder_open, elbow_open), (shoulder_folded, elbow_folded)


def branch_errors(data) -> np.ndarray:
    (shoulder_open, elbow_open), (shoulder_folded, elbow_folded) = _ik_solutions(data)
    return np.asarray(
        [
            _wrap_to_pi(shoulder_open - float(data.qpos[0])),
            _wrap_to_pi(elbow_open - float(data.qpos[1])),
            _wrap_to_pi(shoulder_folded - float(data.qpos[0])),
            _wrap_to_pi(elbow_folded - float(data.qpos[1])),
        ],
        dtype=np.float64,
    )


def preferred_branch_error(data) -> float:
    """Return error to the IK branch requiring less reset-posture motion."""
    (shoulder_open, elbow_open), (shoulder_folded, elbow_folded) = _ik_solutions(data)
    open_reset_error = np.hypot(_wrap_to_pi(shoulder_open), elbow_open)
    folded_reset_error = np.hypot(_wrap_to_pi(shoulder_folded), elbow_folded)
    if open_reset_error <= folded_reset_error:
        target_shoulder, target_elbow = shoulder_open, elbow_open
    else:
        target_shoulder, target_elbow = shoulder_folded, elbow_folded
    return float(
        np.hypot(
            _wrap_to_pi(target_shoulder - float(data.qpos[0])),
            _wrap_to_pi(target_elbow - float(data.qpos[1])),
        )
    )


def reach_observation(data) -> np.ndarray:
    end_effector = data.site("end_effector").xpos.copy()
    return np.concatenate(
        [
            data.qpos,
            data.qvel,
            end_effector - data.mocap_pos[0],
            branch_errors(data),
        ]
    ).astype(np.float32)
