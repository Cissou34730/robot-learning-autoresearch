"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

ACTION_FILTER_ALPHA = 0.5


def physical_action(action):
    return action


def make_policy_io():
    previous_action = None

    def reset() -> None:
        nonlocal previous_action
        previous_action = None

    def action(policy_action):
        nonlocal previous_action
        command = np.asarray(physical_action(policy_action), dtype=np.float64)
        if previous_action is None:
            previous_action = command
        else:
            previous_action = (
                ACTION_FILTER_ALPHA * command
                + (1.0 - ACTION_FILTER_ALPHA) * previous_action
            )
        return previous_action

    return PolicyIO(observe=reach_observation, action=action, reset=reset)
