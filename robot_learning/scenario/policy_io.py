"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

ACTION_SMOOTHING_FACTOR = 0.5
APPROACH_SMOOTHING_FACTOR = 0.75
APPROACH_DISTANCE_THRESHOLD = 0.03


def make_policy_io():
    previous_action = np.zeros(2, dtype=np.float64)
    last_target_distance = 0.0

    def observe(data):
        nonlocal last_target_distance
        last_target_distance = float(
            np.linalg.norm(data.site("end_effector").xpos - data.mocap_pos[0])
        )
        return reach_observation(data)

    def physical_action(action):
        command = np.asarray(action, dtype=np.float64)
        smoothing_factor = (
            ACTION_SMOOTHING_FACTOR
            if last_target_distance <= APPROACH_DISTANCE_THRESHOLD
            else APPROACH_SMOOTHING_FACTOR
        )
        smoothed = (
            smoothing_factor * command
            + (1.0 - smoothing_factor) * previous_action
        )
        previous_action[:] = smoothed
        return smoothed

    def reset():
        nonlocal last_target_distance
        previous_action.fill(0.0)
        last_target_distance = 0.0

    return PolicyIO(observe=observe, action=physical_action, reset=reset)
