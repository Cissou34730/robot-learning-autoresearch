"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

HOLD_STEPS_REQUIRED = 100
SUCCESS_THRESHOLD = 0.01


def physical_action(action):
    return action


def make_policy_io():
    held_steps = 0

    def reset():
        nonlocal held_steps
        held_steps = 0

    def observe(data):
        nonlocal held_steps
        distance = float(
            np.linalg.norm(
                data.site("end_effector").xpos - data.mocap_pos[0]
            )
        )
        held_steps = held_steps + 1 if distance <= SUCCESS_THRESHOLD else 0
        return reach_observation(data, held_steps / HOLD_STEPS_REQUIRED)

    return PolicyIO(observe=observe, action=physical_action, reset=reset)
