"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

ACTION_SMOOTHING_CURRENT_WEIGHT = 0.75
TARGETED_RADIUS_MAX = 0.12
TARGETED_CONTROL_DISTANCE = 0.04


def make_policy_io():
    state = {"previous_action": None, "targeted_state": None}

    def observe(data):
        observation = reach_observation(data)
        target = np.asarray(data.mocap_pos[0], dtype=np.float64)
        end_effector = np.asarray(
            data.site("end_effector").xpos, dtype=np.float64
        )
        target_radius = float(np.hypot(target[0], target[1]))
        target_angle = float(np.arctan2(target[1], target[0]))
        distance = float(np.linalg.norm(end_effector - target))
        state["targeted_state"] = (
            target_angle < 0.0
            and target_radius <= TARGETED_RADIUS_MAX
            and distance <= TARGETED_CONTROL_DISTANCE
        )
        return observation

    def action(command):
        command = np.asarray(command, dtype=np.float64)
        previous_action = state["previous_action"]
        if previous_action is None or state["targeted_state"] is False:
            applied = command.copy()
        else:
            applied = (
                ACTION_SMOOTHING_CURRENT_WEIGHT * command
                + (1.0 - ACTION_SMOOTHING_CURRENT_WEIGHT) * previous_action
            )
        state["previous_action"] = applied.copy()
        return applied

    def reset():
        state["previous_action"] = None
        state["targeted_state"] = None

    return PolicyIO(observe=observe, action=action, reset=reset)
