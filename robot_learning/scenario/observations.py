"""Scenario-owned observation representation.

Generic training code never inspects this layout: it only sees the Gymnasium
observation space declared by the scenario environment.
"""

import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH

OBSERVATION_SIZE = 15


def _compiled_joint_state(data) -> tuple[np.ndarray, np.ndarray]:
    """Return the two compiled joint positions and their scalar ranges."""
    model = data.model
    if int(model.njnt) < 2:
        raise ValueError("the branch-aware observation requires two joints")
    ranges = np.asarray(model.jnt_range[:2], dtype=np.float64)
    if ranges.shape != (2, 2) or not np.all(np.isfinite(ranges)):
        raise ValueError("compiled joint ranges are unavailable")
    if np.any(ranges[:, 1] <= ranges[:, 0]):
        raise ValueError("compiled joint ranges must have positive width")
    qpos = np.asarray(
        [data.qpos[int(model.jnt_qposadr[index])] for index in range(2)],
        dtype=np.float64,
    )
    return qpos, ranges


def _angle_has_compiled_representation(
    angle: float, lower: float, upper: float
) -> bool:
    """Return whether an equivalent angle lies inside a compiled range."""
    turns = range(
        int(np.floor((lower - angle) / (2.0 * np.pi))) - 1,
        int(np.ceil((upper - angle) / (2.0 * np.pi))) + 2,
    )
    return any(
        lower <= angle + (2.0 * np.pi * turn) <= upper for turn in turns
    )


def _branch_feasibility(data) -> np.ndarray:
    """Return open/folded analytic-IK feasibility flags in label order."""
    _, ranges = _compiled_joint_state(data)
    target_x = float(data.mocap_pos[0][0])
    target_y = float(data.mocap_pos[0][1])
    cosine = (
        target_x**2 + target_y**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    if cosine < -1.0 or cosine > 1.0:
        return np.zeros(2, dtype=np.float64)

    elbow_magnitude = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    target_angle = float(np.arctan2(target_y, target_x))
    flags: list[float] = []
    for elbow in (elbow_magnitude, -elbow_magnitude):
        shoulder = float(
            target_angle
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )
        feasible = _angle_has_compiled_representation(
            shoulder, float(ranges[0, 0]), float(ranges[0, 1])
        ) and _angle_has_compiled_representation(
            elbow, float(ranges[1, 0]), float(ranges[1, 1])
        )
        flags.append(1.0 if feasible else 0.0)
    return np.asarray(flags, dtype=np.float64)


def _normalized_joint_margins(data) -> np.ndarray:
    """Return per-joint signed margins normalized by half compiled range."""
    qpos, ranges = _compiled_joint_state(data)
    half_ranges = 0.5 * (ranges[:, 1] - ranges[:, 0])
    margins = np.minimum(qpos - ranges[:, 0], ranges[:, 1] - qpos)
    return np.clip(margins / half_ranges, -1.0, 1.0)


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
    base_observation = np.concatenate(
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
    )
    branch_flags = _branch_feasibility(data)
    joint_margins = _normalized_joint_margins(data)
    return np.concatenate([base_observation, branch_flags, joint_margins]).astype(
        np.float32
    )
