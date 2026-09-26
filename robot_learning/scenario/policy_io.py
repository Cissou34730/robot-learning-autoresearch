"""Researcher-owned policy inputs and mapping to the robot's physical commands."""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.observations import reach_observation


def make_policy_io():
    state = {"qpos": np.zeros(2), "endpoint_error": np.zeros(2)}

    def observe(data):
        observation = reach_observation(data)
        state["qpos"] = np.asarray(data.qpos[:2], dtype=np.float64).copy()
        state["endpoint_error"] = np.asarray(observation[4:6], dtype=np.float64).copy()
        return observation

    def physical_action(action):
        q1, q2 = state["qpos"]
        q12 = q1 + q2
        jacobian = np.array(
            [
                [
                    -UPPER_ARM_LENGTH * np.sin(q1)
                    - FOREARM_LENGTH * np.sin(q12),
                    -FOREARM_LENGTH * np.sin(q12),
                ],
                [
                    UPPER_ARM_LENGTH * np.cos(q1)
                    + FOREARM_LENGTH * np.cos(q12),
                    FOREARM_LENGTH * np.cos(q12),
                ],
            ]
        )
        task_space_torque = jacobian.T @ (-state["endpoint_error"])
        correction = 0.35 * np.tanh(20.0 * task_space_torque)
        return np.asarray(action, dtype=np.float64) + correction

    def reset():
        state["qpos"] = np.zeros(2)
        state["endpoint_error"] = np.zeros(2)

    return PolicyIO(observe=observe, action=physical_action, reset=reset)
