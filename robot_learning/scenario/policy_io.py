"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

ACTION_SMOOTHING = 0.5


def make_policy_io():
    previous_action: np.ndarray | None = None

    def physical_action(action):
        nonlocal previous_action
        current_action = np.asarray(action, dtype=np.float64)
        if previous_action is None:
            smoothed_action = current_action.copy()
        else:
            smoothed_action = (
                ACTION_SMOOTHING * current_action
                + (1.0 - ACTION_SMOOTHING) * previous_action
            )
        previous_action = smoothed_action.copy()
        return smoothed_action

    def reset_action() -> None:
        nonlocal previous_action
        previous_action = None

    return PolicyIO(
        observe=reach_observation,
        action=physical_action,
        reset=reset_action,
    )
