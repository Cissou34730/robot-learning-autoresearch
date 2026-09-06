"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

ACTION_SMOOTHING_FACTOR = 0.5


def make_policy_io():
    previous_action = np.zeros(2, dtype=np.float32)

    def smooth_action(action):
        nonlocal previous_action
        requested = np.clip(np.asarray(action, dtype=np.float32), -1.0, 1.0)
        applied = (
            ACTION_SMOOTHING_FACTOR * requested
            + (1.0 - ACTION_SMOOTHING_FACTOR) * previous_action
        )
        previous_action = applied
        return applied

    def reset_action():
        nonlocal previous_action
        previous_action = np.zeros(2, dtype=np.float32)

    return PolicyIO(observe=reach_observation, action=smooth_action, reset=reset_action)
