"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

ACTION_SMOOTHING_WEIGHT = 0.5


class _ActionSmoother:
    def __init__(self) -> None:
        self._previous: np.ndarray | None = None

    def __call__(self, action):
        current = np.asarray(action, dtype=np.float32)
        if self._previous is None:
            blended = current
        else:
            blended = (
                ACTION_SMOOTHING_WEIGHT * current
                + (1.0 - ACTION_SMOOTHING_WEIGHT) * self._previous
            )
        self._previous = blended.copy()
        return blended

    def reset(self) -> None:
        self._previous = None


def make_policy_io():
    smoother = _ActionSmoother()
    return PolicyIO(
        observe=reach_observation,
        action=smoother,
        reset=smoother.reset,
    )
