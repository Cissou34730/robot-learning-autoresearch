"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

JOINT_VELOCITY_FEEDBACK_GAIN = 0.05


def make_policy_io():
    latest_joint_velocity = np.zeros(2, dtype=np.float64)

    def observe(data):
        latest_joint_velocity[:] = np.asarray(data.qvel[:2], dtype=np.float64)
        return reach_observation(data)

    def physical_action(action):
        command = np.asarray(action, dtype=np.float64)
        return command - JOINT_VELOCITY_FEEDBACK_GAIN * latest_joint_velocity

    def reset():
        latest_joint_velocity.fill(0.0)

    return PolicyIO(observe=observe, action=physical_action, reset=reset)
