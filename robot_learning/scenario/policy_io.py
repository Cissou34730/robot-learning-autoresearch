"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.observations import reach_observation

JOINT_LIMIT_RADIANS = np.deg2rad(170.0)
POSTURE_ASSIST_DISTANCE = 0.08
POSTURE_ASSIST_MARGIN = np.deg2rad(20.0)
POSTURE_ASSIST_KP = 0.35
POSTURE_ASSIST_KD = 0.05
POSTURE_ASSIST_MAX = 0.4


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _ik_postures(data) -> tuple[np.ndarray, np.ndarray]:
    target_x = float(data.mocap_pos[0][0])
    target_y = float(data.mocap_pos[0][1])
    cos_elbow = (
        target_x**2 + target_y**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))
    target_angle = float(np.arctan2(target_y, target_x))

    def posture(elbow_angle: float) -> np.ndarray:
        shoulder = target_angle - np.arctan2(
            FOREARM_LENGTH * np.sin(elbow_angle),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow_angle),
        )
        return np.array([_wrap_to_pi(shoulder), elbow_angle], dtype=np.float64)

    return posture(elbow), posture(-elbow)


def _joint_limit_margin(posture: np.ndarray) -> float:
    return float(JOINT_LIMIT_RADIANS - np.max(np.abs(posture)))


def _branch_posture_action(action: np.ndarray, data) -> np.ndarray:
    if data is None:
        return action

    end_effector = np.asarray(data.site("end_effector").xpos, dtype=np.float64)
    target = np.asarray(data.mocap_pos[0], dtype=np.float64)
    if float(np.linalg.norm(end_effector - target)) > POSTURE_ASSIST_DISTANCE:
        return action

    postures = _ik_postures(data)
    margins = [_joint_limit_margin(posture) for posture in postures]
    preferred = postures[int(np.argmax(margins))]
    current_margin = _joint_limit_margin(np.asarray(data.qpos[:2], dtype=np.float64))
    preferred_margin = max(margins)
    if preferred_margin - current_margin < POSTURE_ASSIST_MARGIN and current_margin > 0.0:
        return action

    qpos = np.asarray(data.qpos[:2], dtype=np.float64)
    qvel = np.asarray(data.qvel[:2], dtype=np.float64)
    position_error = np.array(
        [_wrap_to_pi(float(preferred[0] - qpos[0])), preferred[1] - qpos[1]]
    )
    correction = POSTURE_ASSIST_KP * position_error - POSTURE_ASSIST_KD * qvel
    correction = np.clip(correction, -POSTURE_ASSIST_MAX, POSTURE_ASSIST_MAX)
    return np.clip(action + correction, -1.0, 1.0)


def make_policy_io():
    context = {"data": None}

    def observe(data):
        context["data"] = data
        return reach_observation(data)

    def action(command):
        return _branch_posture_action(np.asarray(command, dtype=np.float64), context["data"])

    def reset():
        context["data"] = None

    return PolicyIO(observe=observe, action=action, reset=reset)
