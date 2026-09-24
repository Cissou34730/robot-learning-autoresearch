"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

ACTION_SMOOTHING_FACTOR = 0.25


class ActionSmoother:
    def __init__(self, factor: float) -> None:
        if not 0.0 <= factor < 1.0:
            raise ValueError("action smoothing factor must be in [0, 1)")
        self.factor = factor
        self.previous: np.ndarray | None = None

    def reset(self) -> None:
        self.previous = None

    def __call__(self, action) -> np.ndarray:
        current = np.asarray(action, dtype=np.float32)
        if self.previous is None:
            smoothed = current
        else:
            smoothed = (1.0 - self.factor) * current + self.factor * self.previous
        self.previous = smoothed.copy()
        return smoothed


def make_policy_io():
    smoother = ActionSmoother(ACTION_SMOOTHING_FACTOR)
    return PolicyIO(observe=reach_observation, action=smoother, reset=smoother.reset)
