"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation


BRAKING_DISTANCE_METERS = 0.055
SUCCESS_THRESHOLD_METERS = 0.01
RADIAL_APPROACH_DAMPING = 2.0
RADIAL_VELOCITY_THRESHOLD = 0.05
FOLDED_ANGLE_RANGE_DEGREES = (-165.0, -105.0)
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


def _target_angle_degrees(observation: np.ndarray) -> float:
    shoulder, elbow = observation[:2]
    total_angle = shoulder + elbow
    end_effector = np.array(
        [
            UPPER_ARM_LENGTH * np.cos(shoulder)
            + FOREARM_LENGTH * np.cos(total_angle),
            UPPER_ARM_LENGTH * np.sin(shoulder)
            + FOREARM_LENGTH * np.sin(total_angle),
        ],
        dtype=np.float64,
    )
    target = end_effector - observation[4:6]
    return float(np.degrees(np.arctan2(target[1], target[0])))


def _is_folded_branch(observation: np.ndarray) -> bool:
    open_residual = float(np.linalg.norm(observation[7:9]))
    folded_residual = float(np.linalg.norm(observation[9:11]))
    return folded_residual < open_residual


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
        target_angle = _target_angle_degrees(latest_observation)
        in_folded_failure_sector = (
            FOLDED_ANGLE_RANGE_DEGREES[0]
            <= target_angle
            <= FOLDED_ANGLE_RANGE_DEGREES[1]
        )
        if (
            SUCCESS_THRESHOLD_METERS < distance <= BRAKING_DISTANCE_METERS
            and in_folded_failure_sector
            and _is_folded_branch(latest_observation)
        ):
            radial_unit = displacement / distance
            jacobian = _end_effector_jacobian(latest_observation)
            end_effector_velocity = jacobian @ latest_observation[2:4]
            radial_velocity = float(np.dot(end_effector_velocity, radial_unit))
            if radial_velocity < -RADIAL_VELOCITY_THRESHOLD:
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
