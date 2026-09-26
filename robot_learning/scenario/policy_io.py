"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

ACTION_SMOOTHING = 0.5


def make_policy_io():
    previous_action = np.zeros(2, dtype=np.float64)

    def reset() -> None:
        previous_action.fill(0.0)

    def physical_action(action):
        nonlocal previous_action
        current_action = np.clip(
            np.asarray(action, dtype=np.float64), -1.0, 1.0
        )
        previous_action = (
            ACTION_SMOOTHING * current_action
            + (1.0 - ACTION_SMOOTHING) * previous_action
        )
        return previous_action.copy()

    return PolicyIO(
        observe=reach_observation,
        action=physical_action,
        reset=reset,
    )
