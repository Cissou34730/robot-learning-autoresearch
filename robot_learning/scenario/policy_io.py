"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

from dataclasses import dataclass, field

import numpy as np

from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation


ACTION_SERVO_RESPONSE = 0.25


@dataclass
class DampedActionMapper:
    """Apply a first-order command servo before direct actuator application."""

    previous: np.ndarray = field(default_factory=lambda: np.zeros(2, dtype=np.float64))

    def __call__(self, action):
        action = np.asarray(action, dtype=np.float64)
        self.previous += ACTION_SERVO_RESPONSE * (action - self.previous)
        return self.previous.copy()

    def reset(self):
        self.previous.fill(0.0)


def make_policy_io():
    action_mapper = DampedActionMapper()
    return PolicyIO(
        observe=reach_observation,
        action=action_mapper,
        reset=action_mapper.reset,
    )
