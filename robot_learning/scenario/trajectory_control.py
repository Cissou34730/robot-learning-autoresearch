"""Explicit branch-constrained trajectory guidance for the arm."""

import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH

JOINT_LIMIT = np.deg2rad(170.0)
TRAJECTORY_DURATION_STEPS = 20
REFERENCE_BLEND = 0.45
POSITION_GAIN = np.array([1.4, 1.0], dtype=np.float64)
VELOCITY_GAIN = np.array([0.12, 0.08], dtype=np.float64)
LIMIT_MARGIN = np.deg2rad(8.0)


def wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def branch_joint_targets(target_position: np.ndarray) -> np.ndarray:
    target_x, target_y = (float(value) for value in target_position[:2])
    radius_squared = target_x**2 + target_y**2
    cosine_elbow = (
        radius_squared - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cosine_elbow, -1.0, 1.0)))

    def shoulder_for_elbow(elbow: float) -> float:
        return wrap_to_pi(
            np.arctan2(target_y, target_x)
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )

    return np.asarray(
        [
            [shoulder_for_elbow(elbow_open), elbow_open],
            [shoulder_for_elbow(-elbow_open), -elbow_open],
        ],
        dtype=np.float64,
    )


def branch_errors(data) -> np.ndarray:
    targets = branch_joint_targets(np.asarray(data.mocap_pos[0]))
    return np.asarray(
        [
            wrap_to_pi(float(targets[0, 0] - data.qpos[0])),
            wrap_to_pi(float(targets[0, 1] - data.qpos[1])),
            wrap_to_pi(float(targets[1, 0] - data.qpos[0])),
            wrap_to_pi(float(targets[1, 1] - data.qpos[1])),
        ],
        dtype=np.float32,
    )


def select_branch_target(target_position: np.ndarray) -> np.ndarray:
    candidates = branch_joint_targets(target_position)
    margins = JOINT_LIMIT - np.max(np.abs(candidates), axis=1)
    valid = margins >= 0.0
    if np.any(valid):
        return candidates[int(np.argmax(np.where(valid, margins, -np.inf)))].copy()
    return candidates[int(np.argmax(margins))].copy()


def _smoothstep(phase: float) -> float:
    return phase * phase * (3.0 - 2.0 * phase)


def guided_action(data, action: np.ndarray, step_count: int) -> np.ndarray:
    target = select_branch_target(np.asarray(data.mocap_pos[0]))
    phase = np.clip(
        (step_count + 1) / TRAJECTORY_DURATION_STEPS,
        0.0,
        1.0,
    )
    interpolation = _smoothstep(float(phase))
    reference_position = interpolation * target
    reference_velocity = np.zeros(2, dtype=np.float64)
    if phase < 1.0:
        reference_velocity = (
            target
            * (6.0 * phase * (1.0 - phase))
            / TRAJECTORY_DURATION_STEPS
        )

    position_error = reference_position - np.asarray(data.qpos[:2])
    velocity_error = reference_velocity - np.asarray(data.qvel[:2])
    reference_action = (
        POSITION_GAIN * position_error + VELOCITY_GAIN * velocity_error
    )

    near_limit = np.abs(data.qpos[:2]) >= JOINT_LIMIT - LIMIT_MARGIN
    moving_outward = np.asarray(data.qpos[:2]) * np.asarray(data.qvel[:2]) > 0.0
    reference_action = np.where(
        near_limit & moving_outward,
        reference_action - np.sign(data.qpos[:2]) * np.abs(reference_action),
        reference_action,
    )
    return np.clip(
        (1.0 - REFERENCE_BLEND) * np.asarray(action, dtype=np.float64)
        + REFERENCE_BLEND * reference_action,
        -1.0,
        1.0,
    )
