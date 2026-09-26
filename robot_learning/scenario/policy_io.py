"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

MAX_ACTION_DELTA = 0.25


def make_policy_io():
    previous_action = np.zeros(2, dtype=np.float64)

    def reset() -> None:
        previous_action[:] = 0.0

    def physical_action(action):
        raw_action = np.asarray(action, dtype=np.float64)
        if raw_action.shape != previous_action.shape:
            raise ValueError(
                f"expected a two-element action, got shape {raw_action.shape}"
            )
        raw_action = np.clip(raw_action, -1.0, 1.0)
        action_delta = np.clip(
            raw_action - previous_action,
            -MAX_ACTION_DELTA,
            MAX_ACTION_DELTA,
        )
        previous_action[:] = np.clip(previous_action + action_delta, -1.0, 1.0)
        return previous_action.copy()

    return PolicyIO(observe=reach_observation, action=physical_action, reset=reset)
