"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import (
    reach_observation,
    reflection_observation,
)


def make_policy_io():
    reflection_sign = 1.0

    def canonical_observation(data):
        nonlocal reflection_sign
        reflection_sign = -1.0 if float(data.mocap_pos[0][1]) < 0.0 else 1.0
        observation = reach_observation(data)
        if reflection_sign < 0.0:
            return reflection_observation(observation)
        return observation

    def physical_action(action):
        return reflection_sign * np.asarray(action)

    def reset():
        nonlocal reflection_sign
        reflection_sign = 1.0

    return PolicyIO(observe=canonical_observation, action=physical_action, reset=reset)
