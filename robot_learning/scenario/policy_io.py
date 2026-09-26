"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

LOCAL_DAMPING_GAIN = 0.10
LOCAL_DAMPING_START_DISTANCE = 0.05
LOCAL_DAMPING_FULL_DISTANCE = 0.01


def make_policy_io():
    joint_velocity = np.zeros(2, dtype=np.float64)
    target_distance = float("inf")

    def observe(data):
        nonlocal joint_velocity, target_distance
        observation = reach_observation(data)
        joint_velocity = np.asarray(data.qvel[:2], dtype=np.float64).copy()
        target_distance = float(np.linalg.norm(observation[4:7]))
        return observation

    def action(policy_action):
        if LOCAL_DAMPING_START_DISTANCE <= LOCAL_DAMPING_FULL_DISTANCE:
            raise ValueError("local damping distance bounds must be descending")
        blend = np.clip(
            (LOCAL_DAMPING_START_DISTANCE - target_distance)
            / (LOCAL_DAMPING_START_DISTANCE - LOCAL_DAMPING_FULL_DISTANCE),
            0.0,
            1.0,
        )
        action = np.asarray(policy_action, dtype=np.float64)
        return action - blend * LOCAL_DAMPING_GAIN * joint_velocity

    def reset():
        nonlocal joint_velocity, target_distance
        joint_velocity = np.zeros(2, dtype=np.float64)
        target_distance = float("inf")

    return PolicyIO(observe=observe, action=action, reset=reset)
