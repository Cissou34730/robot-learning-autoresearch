"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

CONTROL_TORQUE_LIMIT = 5.0
JOINT_LIMIT = float(np.deg2rad(170.0))
POSITION_KP = 5.0
POSITION_KD = 0.75


def make_policy_io():
    state = {
        "qpos": np.zeros(2, dtype=np.float64),
        "qvel": np.zeros(2, dtype=np.float64),
    }

    def observe(data):
        state["qpos"] = np.asarray(data.qpos[:2], dtype=np.float64).copy()
        state["qvel"] = np.asarray(data.qvel[:2], dtype=np.float64).copy()
        return reach_observation(data)

    def physical_action(action):
        desired_q = np.clip(np.asarray(action, dtype=np.float64), -1.0, 1.0)
        desired_q = desired_q * JOINT_LIMIT
        error = desired_q - state["qpos"]
        error[0] = (error[0] + np.pi) % (2.0 * np.pi) - np.pi
        torque = POSITION_KP * error - POSITION_KD * state["qvel"]
        return np.clip(
            torque / CONTROL_TORQUE_LIMIT, -1.0, 1.0
        ).astype(np.float32)

    def reset():
        state["qpos"].fill(0.0)
        state["qvel"].fill(0.0)

    return PolicyIO(observe=observe, action=physical_action, reset=reset)
