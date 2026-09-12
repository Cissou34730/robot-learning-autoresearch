"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

ACTION_DEADBAND = 0.1


def physical_action(action):
    action = np.asarray(action, dtype=np.float32)
    return np.where(np.abs(action) < ACTION_DEADBAND, 0.0, action)


def make_policy_io():
    return PolicyIO(observe=reach_observation, action=physical_action)
