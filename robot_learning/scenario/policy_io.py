"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

ACTION_SMOOTHING_FACTOR = 0.5


def make_policy_io():
    previous_action = np.zeros(2, dtype=np.float64)

    def observe(data):
        return reach_observation(data, previous_action)

    def physical_action(action):
        command = np.asarray(action, dtype=np.float64)
        smoothed = (
            ACTION_SMOOTHING_FACTOR * command
            + (1.0 - ACTION_SMOOTHING_FACTOR) * previous_action
        )
        previous_action[:] = smoothed
        return smoothed

    def reset():
        previous_action.fill(0.0)

    return PolicyIO(observe=observe, action=physical_action, reset=reset)
