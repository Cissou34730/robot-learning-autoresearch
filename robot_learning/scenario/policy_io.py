"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

ACTION_DELTA_LIMIT = 0.15


class _ActionRateLimiter:
    def __init__(self) -> None:
        self._previous: np.ndarray | None = None

    def reset(self) -> None:
        self._previous = None

    def __call__(self, action):
        command = np.asarray(action, dtype=np.float64)
        if self._previous is None:
            self._previous = np.zeros_like(command)
        limited = self._previous + np.clip(
            command - self._previous,
            -ACTION_DELTA_LIMIT,
            ACTION_DELTA_LIMIT,
        )
        limited = np.clip(limited, -1.0, 1.0)
        self._previous = limited.copy()
        return limited


def make_policy_io():
    action_mapper = _ActionRateLimiter()
    return PolicyIO(
        observe=reach_observation,
        action=action_mapper,
        reset=action_mapper.reset,
    )
