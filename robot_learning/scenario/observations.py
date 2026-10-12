"""Scenario-owned observation representation.

Generic training code never inspects this layout: it only sees the Gymnasium
observation space declared by the scenario environment.
"""

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH

OBSERVATION_SIZE = 15
IK_RANGE_TOLERANCE = 1e-9
# The feature order is open indicator, open margin, folded indicator, folded
# margin.  A zero margin is the bounded sentinel for an infeasible branch; the
# indicator disambiguates it from a feasible branch exactly at a limit.
# A feasible margin is the minimum per-joint distance to a compiled limit,
# normalized by that joint's compiled range width, and is therefore in [0, 0.5].
INFEASIBLE_BRANCH_MARGIN = 0.0
_TASK_JOINT_NAMES = ("shoulder", "elbow")
_IK_BRANCHES = (("open", 1.0), ("folded", -1.0))


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

    branch_features: list[float] = []
    joint_ids = tuple(
        mujoco.mj_name2id(data.model, mujoco.mjtObj.mjOBJ_JOINT, name)
        for name in _TASK_JOINT_NAMES
    )
    if any(joint_id < 0 for joint_id in joint_ids):
        raise RuntimeError("the compiled model is missing a task joint")
    joint_ranges = tuple(
        (
            float(data.model.jnt_range[joint_id][0]),
            float(data.model.jnt_range[joint_id][1]),
        )
        for joint_id in joint_ids
    )

    def closest_in_range(angle: float, lower: float, upper: float) -> float:
        candidates = [angle + 2.0 * np.pi * turns for turns in range(-2, 3)]
        in_range = [
            candidate
            for candidate in candidates
            if lower - IK_RANGE_TOLERANCE
            <= candidate
            <= upper + IK_RANGE_TOLERANCE
        ]
        if in_range:
            return float(min(in_range, key=lambda candidate: abs(candidate - angle)))
        return float((angle + np.pi) % (2.0 * np.pi) - np.pi)

    if -1.0 - IK_RANGE_TOLERANCE <= cos_elbow <= 1.0 + IK_RANGE_TOLERANCE:
        elbow_magnitude = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))
        for _, sign in _IK_BRANCHES:
            elbow = sign * elbow_magnitude
            shoulder = shoulder_for_elbow(elbow)
            joint_angles = (
                closest_in_range(shoulder, *joint_ranges[0]),
                closest_in_range(elbow, *joint_ranges[1]),
            )
            feasible = all(
                lower - IK_RANGE_TOLERANCE <= angle <= upper + IK_RANGE_TOLERANCE
                for angle, (lower, upper) in zip(joint_angles, joint_ranges)
            )
            if feasible:
                normalized_margin = min(
                    min(angle - lower, upper - angle) / (upper - lower)
                    for angle, (lower, upper) in zip(joint_angles, joint_ranges)
                )
                normalized_margin = float(np.clip(normalized_margin, 0.0, 0.5))
            else:
                normalized_margin = INFEASIBLE_BRANCH_MARGIN
            branch_features.extend([float(feasible), normalized_margin])
    else:
        for _ in _IK_BRANCHES:
            branch_features.extend([0.0, INFEASIBLE_BRANCH_MARGIN])

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
            branch_features,
        ]
    ).astype(np.float32)
