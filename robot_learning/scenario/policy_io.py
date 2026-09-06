"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

ACTION_SMOOTHING_CURRENT_WEIGHT = 0.75


class SmoothedPhysicalAction:
    def __init__(self) -> None:
        self.previous_action: np.ndarray | None = None

    def __call__(self, action) -> np.ndarray:
        physical_action = np.clip(np.asarray(action, dtype=np.float64), -1.0, 1.0)
        if self.previous_action is not None:
            physical_action = (
                ACTION_SMOOTHING_CURRENT_WEIGHT * physical_action
                + (1.0 - ACTION_SMOOTHING_CURRENT_WEIGHT) * self.previous_action
            )
        self.previous_action = physical_action.copy()
        return physical_action

    def reset(self) -> None:
        self.previous_action = None


def make_policy_io() -> PolicyIO:
    action = SmoothedPhysicalAction()
    return PolicyIO(observe=reach_observation, action=action, reset=action.reset)
