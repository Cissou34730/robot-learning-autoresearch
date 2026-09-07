"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

ACTION_SMOOTHING_CURRENT_WEIGHT = 0.75


class ActionSmoother:
    def __init__(self) -> None:
        self._previous_action: np.ndarray | None = None

    def __call__(self, action) -> np.ndarray:
        current_action = np.clip(
            np.asarray(action, dtype=np.float64), -1.0, 1.0
        )
        if self._previous_action is None:
            smoothed_action = current_action
        else:
            smoothed_action = (
                ACTION_SMOOTHING_CURRENT_WEIGHT * current_action
                + (1.0 - ACTION_SMOOTHING_CURRENT_WEIGHT) * self._previous_action
            )
        self._previous_action = smoothed_action.copy()
        return smoothed_action

    def reset(self) -> None:
        self._previous_action = None


def make_policy_io():
    smoother = ActionSmoother()
    return PolicyIO(
        observe=reach_observation,
        action=smoother,
        reset=smoother.reset,
    )
