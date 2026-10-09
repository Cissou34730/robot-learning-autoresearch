"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation
from robot_learning.scenario.trajectory_control import guided_action


def physical_action(action):
    return action


def make_policy_io():
    latest_data = None
    step_count = 0

    def observe(data):
        nonlocal latest_data
        latest_data = data
        return reach_observation(data)

    def action(value):
        nonlocal step_count
        if latest_data is None:
            raise RuntimeError("policy action requested before an observation")
        guided = guided_action(latest_data, physical_action(value), step_count)
        step_count += 1
        return guided

    def reset():
        nonlocal latest_data, step_count
        latest_data = None
        step_count = 0

    return PolicyIO(observe=observe, action=action, reset=reset)
