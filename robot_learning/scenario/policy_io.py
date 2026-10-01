"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import OBSERVATION_SIZE, reach_observation

TEMPORAL_CONTEXT_LENGTH = 3
POLICY_OBSERVATION_SIZE = OBSERVATION_SIZE * TEMPORAL_CONTEXT_LENGTH


def physical_action(action):
    return action


def make_policy_io():
    history: list[np.ndarray] = []

    def reset() -> None:
        history.clear()

    def observe(data) -> np.ndarray:
        current = reach_observation(data)
        if not history:
            history.extend(current.copy() for _ in range(TEMPORAL_CONTEXT_LENGTH))
        else:
            history.append(current.copy())
            del history[:-TEMPORAL_CONTEXT_LENGTH]
        return np.concatenate(history).astype(np.float32, copy=False)

    return PolicyIO(observe=observe, action=physical_action, reset=reset)
