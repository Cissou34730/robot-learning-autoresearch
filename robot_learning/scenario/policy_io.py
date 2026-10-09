"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation


BRAKING_ANGLE_MIN_RADIANS = np.radians(-165.0)
BRAKING_ANGLE_MAX_RADIANS = np.radians(-115.0)
BRAKING_DISTANCE_METERS = 0.06
BRAKING_DAMPING = 0.5
ACTUATOR_GEAR = 5.0


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _target_angle(observation: np.ndarray) -> float:
    shoulder, elbow = observation[:2]
    end_effector = np.array(
        [
            0.12 * np.cos(shoulder) + 0.10 * np.cos(shoulder + elbow),
            0.12 * np.sin(shoulder) + 0.10 * np.sin(shoulder + elbow),
        ]
    )
    target = end_effector - observation[4:6]
    return _wrap_to_pi(float(np.arctan2(target[1], target[0])))


def make_policy_io():
    latest_observation: np.ndarray | None = None

    def observe(data):
        nonlocal latest_observation
        latest_observation = reach_observation(data)
        return latest_observation

    def action_with_route_braking(action):
        if latest_observation is None:
            raise RuntimeError("action requested before an observation")

        action = np.asarray(action, dtype=np.float64)
        target_angle = _target_angle(latest_observation)
        distance = float(np.linalg.norm(latest_observation[4:6]))
        targeted_route = (
            BRAKING_ANGLE_MIN_RADIANS
            <= target_angle
            <= BRAKING_ANGLE_MAX_RADIANS
        )
        if targeted_route and distance <= BRAKING_DISTANCE_METERS:
            action = action - (
                BRAKING_DAMPING * latest_observation[2:4] / ACTUATOR_GEAR
            )
        return action

    def reset():
        nonlocal latest_observation
        latest_observation = None

    return PolicyIO(observe=observe, action=action_with_route_braking, reset=reset)
