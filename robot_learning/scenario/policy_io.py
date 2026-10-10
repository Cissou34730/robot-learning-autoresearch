"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation
from robot_learning.scenario.trajectory_control import branch_transition_action


def make_policy_io():
    latest_data = None
    transition_state = {"holding": False}

    def observe(data):
        nonlocal latest_data
        latest_data = data
        return reach_observation(data)

    def action(value):
        if latest_data is None:
            raise RuntimeError("policy action requested before an observation")
        return branch_transition_action(latest_data, value, transition_state)

    def reset():
        nonlocal latest_data
        latest_data = None
        transition_state["holding"] = False

    return PolicyIO(observe=observe, action=action, reset=reset)
