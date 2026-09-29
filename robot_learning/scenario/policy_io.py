"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.observations import reach_observation

JOINT_LIMIT_RADIANS = np.deg2rad(170.0)


def physical_action(action):
    return action


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _ik_postures(data) -> tuple[np.ndarray, np.ndarray]:
    target_x = float(data.mocap_pos[0][0])
    target_y = float(data.mocap_pos[0][1])
    cos_elbow = (
        target_x**2 + target_y**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))
    target_angle = float(np.arctan2(target_y, target_x))

    def posture(elbow: float) -> np.ndarray:
        shoulder = target_angle - np.arctan2(
            FOREARM_LENGTH * np.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
        )
        return np.array([_wrap_to_pi(shoulder), elbow], dtype=np.float64)

    return posture(elbow_open), posture(-elbow_open)


def _joint_limit_margin(posture: np.ndarray) -> float:
    return float(JOINT_LIMIT_RADIANS - np.max(np.abs(posture)))


def make_policy_io():
    def observe(data):
        observation = reach_observation(data)
        open_posture, folded_posture = _ik_postures(data)
        if (
            _joint_limit_margin(open_posture) < 0.0
            <= _joint_limit_margin(folded_posture)
        ):
            observation[7:11] = observation[[9, 10, 7, 8]]
        return observation

    return PolicyIO(observe=observe, action=physical_action)
