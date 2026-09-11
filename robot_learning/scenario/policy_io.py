"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

ACTION_SMOOTHING_FACTOR = 0.5
HARD_SECTOR_SMOOTHING_FACTOR = 0.75
HARD_SECTOR_MIN_ANGLE = np.deg2rad(-160.0)
HARD_SECTOR_MAX_ANGLE = np.deg2rad(-115.0)


def make_policy_io():
    previous_action = np.zeros(2, dtype=np.float64)
    latest_target_angle = None

    def observe(data):
        nonlocal latest_target_angle
        latest_target_angle = float(
            np.arctan2(data.mocap_pos[0][1], data.mocap_pos[0][0])
        )
        return reach_observation(data)

    def physical_action(action):
        smoothing_factor = ACTION_SMOOTHING_FACTOR
        if latest_target_angle is not None and (
            HARD_SECTOR_MIN_ANGLE <= latest_target_angle < HARD_SECTOR_MAX_ANGLE
        ):
            smoothing_factor = HARD_SECTOR_SMOOTHING_FACTOR
        command = np.asarray(action, dtype=np.float64)
        smoothed = (
            smoothing_factor * command
            + (1.0 - smoothing_factor) * previous_action
        )
        previous_action[:] = smoothed
        return smoothed

    def reset():
        nonlocal latest_target_angle
        previous_action.fill(0.0)
        latest_target_angle = None

    return PolicyIO(observe=observe, action=physical_action, reset=reset)
