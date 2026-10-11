"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

VELOCITY_DAMPING_GAIN = 0.05


def make_policy_io():
    last_velocity = np.zeros(2, dtype=np.float64)

    def observe(data):
        observation = reach_observation(data)
        last_velocity[:] = np.asarray(data.qvel[:2], dtype=np.float64)
        return observation

    def action(policy_action):
        command = np.asarray(policy_action, dtype=np.float64)
        return command - VELOCITY_DAMPING_GAIN * last_velocity

    def reset() -> None:
        last_velocity[:] = 0.0

    return PolicyIO(observe=observe, action=action, reset=reset)
