"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import (
    branch_limit_conditioned_observation,
)


def physical_action(action):
    return action


def make_policy_io():
    return PolicyIO(
        observe=branch_limit_conditioned_observation,
        action=physical_action,
    )
