"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation
from robot_learning.scenario.trajectory_control import anticipatory_target_action


def make_policy_io():
    latest_data = None

    def observe(data):
        nonlocal latest_data
        latest_data = data
        return reach_observation(data)

    def action(value):
        if latest_data is None:
            raise RuntimeError("policy action requested before an observation")
        return anticipatory_target_action(latest_data, value)

    def reset():
        nonlocal latest_data
        latest_data = None

    return PolicyIO(observe=observe, action=action, reset=reset)
