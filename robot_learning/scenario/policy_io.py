"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

REGULATION_DISTANCE = 0.025
HOLD_DISTANCE = 0.01
FAR_COMMAND_SCALE = 1.0
NEAR_COMMAND_SCALE = 0.6
FAR_VELOCITY_DAMPING = 0.05
NEAR_VELOCITY_DAMPING = 0.15


def make_policy_io():
    last_velocity = np.zeros(2, dtype=np.float64)
    last_distance = REGULATION_DISTANCE

    def observe(data):
        nonlocal last_distance
        observation = reach_observation(data)
        last_velocity[:] = np.asarray(data.qvel[:2], dtype=np.float64)
        endpoint = np.asarray(data.site("end_effector").xpos, dtype=np.float64)
        target = np.asarray(data.mocap_pos[0], dtype=np.float64)
        last_distance = float(np.linalg.norm(endpoint - target))
        return observation

    def action(policy_action):
        command = np.asarray(policy_action, dtype=np.float64)
        phase = np.clip(
            (last_distance - HOLD_DISTANCE)
            / (REGULATION_DISTANCE - HOLD_DISTANCE),
            0.0,
            1.0,
        )
        command_scale = NEAR_COMMAND_SCALE + (
            (FAR_COMMAND_SCALE - NEAR_COMMAND_SCALE) * phase
        )
        damping_gain = NEAR_VELOCITY_DAMPING + (
            (FAR_VELOCITY_DAMPING - NEAR_VELOCITY_DAMPING) * phase
        )
        return np.clip(
            command_scale * command - damping_gain * last_velocity,
            -1.0,
            1.0,
        )

    def reset() -> None:
        nonlocal last_distance
        last_velocity[:] = 0.0
        last_distance = REGULATION_DISTANCE

    return PolicyIO(observe=observe, action=action, reset=reset)
