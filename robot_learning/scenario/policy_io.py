"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation


def physical_action(action):
    return action


def make_policy_io():
    previous_action = np.zeros(2, dtype=np.float32)

    def observe(data):
        return reach_observation(data, previous_action=previous_action)

    def action(command):
        previous_action[:] = np.asarray(command, dtype=np.float32)
        return command

    def reset():
        previous_action[:] = 0.0

    return PolicyIO(observe=observe, action=action, reset=reset)
