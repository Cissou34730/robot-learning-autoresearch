"""Scenario-owned observation representation.

Generic training code never inspects this layout: it only sees the Gymnasium
observation space declared by the scenario environment.
"""

import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH

OBSERVATION_SIZE = 11
JOINT_LIMIT_RADIANS = float(np.deg2rad(170.0))


def wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def ik_branch_targets(data) -> np.ndarray:
    """Return the two planar point-IK targets as ``(open, folded)`` rows."""
    target_x = float(data.mocap_pos[0][0])
    target_y = float(data.mocap_pos[0][1])
    cos_elbow = (
        target_x**2 + target_y**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))
    elbow_folded = -elbow_open
    target_angle = np.arctan2(target_y, target_x)

    def shoulder_for_elbow(elbow: float) -> float:
        return float(
            target_angle
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )

    return np.asarray(
        [
            [shoulder_for_elbow(elbow_open), elbow_open],
            [shoulder_for_elbow(elbow_folded), elbow_folded],
        ],
        dtype=np.float64,
    )


def ik_branch_errors(data) -> np.ndarray:
    """Return wrapped shoulder/elbow errors for the two existing IK branches."""
    targets = ik_branch_targets(data)
    qpos = np.asarray(data.qpos[:2], dtype=np.float64)
    return np.asarray(
        [
            [
                wrap_to_pi(targets[0, 0] - qpos[0]),
                wrap_to_pi(targets[0, 1] - qpos[1]),
            ],
            [
                wrap_to_pi(targets[1, 0] - qpos[0]),
                wrap_to_pi(targets[1, 1] - qpos[1]),
            ],
        ],
        dtype=np.float64,
    )


def ik_branch_validity(data) -> np.ndarray:
    """Return which point-IK branches satisfy the two joint limits."""
    targets = ik_branch_targets(data)
    if targets.shape != (2, 2) or not np.isfinite(targets).all():
        return np.zeros(2, dtype=bool)

    shoulder_angles = np.asarray(
        [wrap_to_pi(float(shoulder)) for shoulder in targets[:, 0]],
        dtype=np.float64,
    )
    elbow_angles = targets[:, 1]
    return (
        (np.abs(shoulder_angles) <= JOINT_LIMIT_RADIANS)
        & (np.abs(elbow_angles) <= JOINT_LIMIT_RADIANS)
    )


def target_elbow_magnitude(data) -> float:
    """Return the finite, non-negative elbow magnitude required by the target."""
    targets = ik_branch_targets(data)
    if not np.isfinite(targets).all():
        return 0.0
    magnitude = abs(float(targets[0, 1]))
    if not np.isfinite(magnitude):
        return 0.0
    return float(np.clip(magnitude, 0.0, np.pi))


def reach_observation(data) -> np.ndarray:
    branch_errors = ik_branch_errors(data)
    end_effector = data.site("end_effector").xpos.copy()
    return np.concatenate(
        [
            data.qpos,
            data.qvel,
            end_effector - data.mocap_pos[0],
            branch_errors.reshape(-1),
        ]
    ).astype(np.float32)
