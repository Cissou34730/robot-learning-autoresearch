"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation


BRAKING_DISTANCE_METERS = 0.08
SUCCESS_THRESHOLD_METERS = 0.01
RADIAL_APPROACH_DAMPING = 1.0
ACTUATOR_GEAR = 5.0


def _end_effector_jacobian(observation: np.ndarray) -> np.ndarray:
    shoulder, elbow = observation[:2]
    total_angle = shoulder + elbow
    return np.array(
        [
            [
                -0.12 * np.sin(shoulder) - 0.10 * np.sin(total_angle),
                -0.10 * np.sin(total_angle),
            ],
            [
                0.12 * np.cos(shoulder) + 0.10 * np.cos(total_angle),
                0.10 * np.cos(total_angle),
            ],
        ],
        dtype=np.float64,
    )


def make_policy_io():
    latest_observation: np.ndarray | None = None

    def observe(data):
        nonlocal latest_observation
        latest_observation = reach_observation(data)
        return latest_observation

    def action_with_prearrival_damping(action):
        if latest_observation is None:
            raise RuntimeError("action requested before an observation")

        action = np.asarray(action, dtype=np.float64)
        displacement = latest_observation[4:6].astype(np.float64)
        distance = float(np.linalg.norm(displacement))
        if SUCCESS_THRESHOLD_METERS < distance <= BRAKING_DISTANCE_METERS:
            radial_unit = -displacement / distance
            jacobian = _end_effector_jacobian(latest_observation)
            end_effector_velocity = jacobian @ latest_observation[2:4]
            radial_velocity = float(np.dot(end_effector_velocity, radial_unit))
            if radial_velocity > 0.0:
                damping_effort = (
                    -RADIAL_APPROACH_DAMPING
                    * radial_velocity
                    * (jacobian.T @ radial_unit)
                )
                action = action + damping_effort / ACTUATOR_GEAR
        return action

    def reset():
        nonlocal latest_observation
        latest_observation = None

    return PolicyIO(
        observe=observe,
        action=action_with_prearrival_damping,
        reset=reset,
    )
