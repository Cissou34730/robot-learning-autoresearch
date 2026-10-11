"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

ACTION_RATE_LIMIT = 0.2


def physical_action(action):
    return action


def make_policy_io():
    previous_action = np.zeros(2, dtype=np.float64)

    def reset() -> None:
        previous_action[:] = 0.0

    def action(policy_action):
        command = np.clip(
            np.asarray(physical_action(policy_action), dtype=np.float64),
            -1.0,
            1.0,
        )
        previous_action[:] += np.clip(
            command - previous_action,
            -ACTION_RATE_LIMIT,
            ACTION_RATE_LIMIT,
        )
        return previous_action.copy()

    return PolicyIO(observe=reach_observation, action=action, reset=reset)
