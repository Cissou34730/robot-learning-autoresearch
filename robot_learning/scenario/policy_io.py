"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.observations import reach_observation

ACTION_SMOOTHING_FACTOR = 0.5
IK_ASSIST_STRENGTH = 0.25
IK_POSITION_GAIN = 0.8
IK_VELOCITY_GAIN = 0.1


def _wrap_to_pi(angle: np.ndarray | float) -> np.ndarray | float:
    return (np.asarray(angle) + np.pi) % (2.0 * np.pi) - np.pi


def _branch_target(target: np.ndarray, qpos: np.ndarray) -> np.ndarray:
    target_x, target_y = target[:2]
    cos_elbow = (
        target_x**2
        + target_y**2
        - UPPER_ARM_LENGTH**2
        - FOREARM_LENGTH**2
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

    candidates = np.array(
        [
            [shoulder_for_elbow(elbow_open), elbow_open],
            [shoulder_for_elbow(-elbow_open), -elbow_open],
        ],
        dtype=np.float64,
    )
    distance = np.sum(np.abs(_wrap_to_pi(candidates - qpos)), axis=1)
    return candidates[int(np.argmin(distance))]


def _ik_assist(qpos: np.ndarray, qvel: np.ndarray, target: np.ndarray) -> np.ndarray:
    desired = _branch_target(target, qpos)
    position_error = np.asarray(_wrap_to_pi(desired - qpos), dtype=np.float64)
    feedback = IK_POSITION_GAIN * position_error - IK_VELOCITY_GAIN * qvel
    return np.clip(feedback, -1.0, 1.0)


def make_policy_io(*, use_ik_assist: bool = True):
    previous_action = np.zeros(2, dtype=np.float64)
    latest_state: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None

    def observe(data):
        nonlocal latest_state
        if use_ik_assist:
            latest_state = (
                np.asarray(data.qpos, dtype=np.float64).copy(),
                np.asarray(data.qvel, dtype=np.float64).copy(),
                np.asarray(data.mocap_pos[0], dtype=np.float64).copy(),
            )
        return reach_observation(data)

    def physical_action(action):
        command = np.asarray(action, dtype=np.float64)
        smoothed = (
            ACTION_SMOOTHING_FACTOR * command
            + (1.0 - ACTION_SMOOTHING_FACTOR) * previous_action
        )
        previous_action[:] = smoothed
        if not use_ik_assist:
            return smoothed
        if latest_state is None:
            raise RuntimeError("IK-assisted action requested before an observation")
        qpos, qvel, target = latest_state
        return np.clip(
            smoothed + IK_ASSIST_STRENGTH * _ik_assist(qpos, qvel, target),
            -1.0,
            1.0,
        )

    def reset():
        nonlocal latest_state
        previous_action.fill(0.0)
        latest_state = None

    return PolicyIO(observe=observe, action=physical_action, reset=reset)
