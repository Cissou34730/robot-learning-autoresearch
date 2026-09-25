"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

NEAR_TARGET_RADIUS = 0.012
SUCCESS_THRESHOLD = 0.01
ENDPOINT_DAMPING_GAIN = 2.0
UPPER_ARM_LENGTH = 0.12
FOREARM_LENGTH = 0.10


def make_policy_io():
    latest_observation: np.ndarray | None = None

    def observe(data) -> np.ndarray:
        nonlocal latest_observation
        latest_observation = reach_observation(data)
        return latest_observation

    def physical_action(action):
        if latest_observation is None:
            raise RuntimeError("an observation is required before applying an action")

        command = np.asarray(action, dtype=np.float64).copy()
        distance = float(np.linalg.norm(latest_observation[4:7]))
        if distance > NEAR_TARGET_RADIUS:
            return command

        band_width = NEAR_TARGET_RADIUS - SUCCESS_THRESHOLD
        activation = float(
            np.clip((NEAR_TARGET_RADIUS - distance) / band_width, 0.0, 1.0)
        )
        q1, q2 = latest_observation[:2]
        qvel = latest_observation[2:4]
        elbow_angle = q1 + q2
        jacobian = np.array(
            [
                [
                    -UPPER_ARM_LENGTH * np.sin(q1)
                    - FOREARM_LENGTH * np.sin(elbow_angle),
                    -FOREARM_LENGTH * np.sin(elbow_angle),
                ],
                [
                    UPPER_ARM_LENGTH * np.cos(q1)
                    + FOREARM_LENGTH * np.cos(elbow_angle),
                    FOREARM_LENGTH * np.cos(elbow_angle),
                ],
            ]
        )
        endpoint_velocity = jacobian @ qvel
        damping = -ENDPOINT_DAMPING_GAIN * (jacobian.T @ endpoint_velocity)
        return command + activation * damping

    def reset() -> None:
        nonlocal latest_observation
        latest_observation = None

    return PolicyIO(observe=observe, action=physical_action, reset=reset)
