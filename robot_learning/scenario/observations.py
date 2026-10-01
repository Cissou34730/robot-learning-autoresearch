"""Scenario-owned observation representation.

Generic training code never inspects this layout: it only sees the Gymnasium
observation space declared by the scenario environment.
"""

import mujoco
import numpy as np

from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH

DYNAMICS_FEATURE_SIZE = 8
OBSERVATION_SIZE = 11 + DYNAMICS_FEATURE_SIZE

MASS_SCALES = np.array([0.012, 0.010, 0.001], dtype=np.float64)
JACOBIAN_SINGULAR_VALUE_SCALE = 0.24
JACOBIAN_DETERMINANT_SCALE = 0.012
ACTUATION_AUTHORITY_SCALE = 140.0


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


def _dynamics_observation(data) -> np.ndarray:
    mass_matrix = np.zeros((2, 2), dtype=np.float64)
    mujoco.mj_fullM(data.model, data, mass_matrix)
    jacobian_position = np.zeros((3, data.model.nv), dtype=np.float64)
    jacobian_rotation = np.zeros((3, data.model.nv), dtype=np.float64)
    mujoco.mj_jacSite(
        data.model,
        data,
        jacobian_position,
        jacobian_rotation,
        data.site("end_effector").id,
    )
    jacobian = jacobian_position[:2, :2]
    inverse_mass_actuation = np.linalg.solve(
        mass_matrix,
        np.diag(np.asarray(data.model.actuator_gear[:2, 0], dtype=np.float64)),
    )
    action_to_acceleration = jacobian @ inverse_mass_actuation
    singular_values = np.linalg.svd(jacobian, compute_uv=False)
    authority = np.sum(np.abs(action_to_acceleration), axis=1)
    features = np.array(
        [
            mass_matrix[0, 0] / MASS_SCALES[0],
            mass_matrix[1, 1] / MASS_SCALES[1],
            mass_matrix[0, 1] / MASS_SCALES[2],
            singular_values[0] / JACOBIAN_SINGULAR_VALUE_SCALE,
            singular_values[1] / JACOBIAN_SINGULAR_VALUE_SCALE,
            np.linalg.det(jacobian) / JACOBIAN_DETERMINANT_SCALE,
            authority[0] / ACTUATION_AUTHORITY_SCALE,
            authority[1] / ACTUATION_AUTHORITY_SCALE,
        ],
        dtype=np.float64,
    )
    return np.clip(features, -1.0, 1.0)


def reach_observation(data) -> np.ndarray:
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
    return np.concatenate(
        [
            qpos,
            np.asarray(data.qvel[:2], dtype=np.float64),
            end_effector - data.mocap_pos[0],
            branch_errors,
            _dynamics_observation(data),
        ]
    ).astype(np.float32)
