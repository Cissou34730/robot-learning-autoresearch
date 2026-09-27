"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation


def make_policy_io():
    smoothing_alpha = 0.75
    previous_action = np.zeros(2, dtype=np.float32)

    def physical_action(action):
        nonlocal previous_action
        action = np.asarray(action, dtype=np.float32)
        previous_action = (
            smoothing_alpha * action + (1.0 - smoothing_alpha) * previous_action
        )
        return previous_action

    def reset_action():
        nonlocal previous_action
        previous_action = np.zeros(2, dtype=np.float32)

    return PolicyIO(
        observe=reach_observation,
        action=physical_action,
        reset=reset_action,
    )
