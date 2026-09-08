"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

ACTION_SCALE = 0.8


def physical_action(action):
    return action * ACTION_SCALE


def make_policy_io():
    return PolicyIO(observe=reach_observation, action=physical_action)
