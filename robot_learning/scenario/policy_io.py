"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation


ACTION_SLEW_LIMIT = 0.5


def make_policy_io():
    previous_action = np.zeros(2, dtype=np.float32)

    def physical_action(action):
        nonlocal previous_action
        requested_action = np.asarray(action, dtype=np.float32)
        if requested_action.shape != (2,):
            raise ValueError("action must have shape (2,)")
        previous_action = previous_action + np.clip(
            requested_action - previous_action,
            -ACTION_SLEW_LIMIT,
            ACTION_SLEW_LIMIT,
        )
        return previous_action.copy()

    def reset():
        nonlocal previous_action
        previous_action = np.zeros(2, dtype=np.float32)

    return PolicyIO(
        observe=reach_observation,
        action=physical_action,
        reset=reset,
    )
