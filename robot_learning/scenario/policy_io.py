"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation


BRAKING_START_METERS = 0.012
BRAKING_END_METERS = 0.050
SUCCESS_THRESHOLD_METERS = 0.01
SAFE_RADIAL_ACCELERATION = 1.5
RADIAL_VELOCITY_GAIN = 1.2
FOLDED_ANGLE_RANGE_DEGREES = (-155.0, -125.0)
CONTROL_INTERVAL_SECONDS = 0.02
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

    def action_with_prearrival_velocity_shaping(action):
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
            BRAKING_START_METERS < distance <= BRAKING_END_METERS
            and in_folded_failure_sector
            and _is_folded_branch(latest_observation)
        ):
            radial_unit = displacement / distance
            jacobian = _end_effector_jacobian(latest_observation)
            end_effector_velocity = jacobian @ latest_observation[2:4]
            radial_velocity = float(np.dot(end_effector_velocity, radial_unit))
            braking_gap = max(distance - SUCCESS_THRESHOLD_METERS, 0.0)
            safe_radial_velocity = -np.sqrt(
                2.0 * SAFE_RADIAL_ACCELERATION * braking_gap
            )
            velocity_excess = safe_radial_velocity - radial_velocity
            if velocity_excess > 0.0:
                window = (distance - BRAKING_START_METERS) / (
                    BRAKING_END_METERS - BRAKING_START_METERS
                )
                terminal_safe_gate = float(np.clip(window, 0.0, 1.0) ** 2)
                predicted_distance = (
                    distance + radial_velocity * CONTROL_INTERVAL_SECONDS
                )
                overshoot_risk = max(
                    SUCCESS_THRESHOLD_METERS - predicted_distance, 0.0
                )
                overshoot_gain = 1.0 + min(
                    overshoot_risk / braking_gap if braking_gap > 0.0 else 0.0,
                    1.0,
                )
                braking_effort = (
                    terminal_safe_gate
                    * overshoot_gain
                    * RADIAL_VELOCITY_GAIN
                    * velocity_excess
                    * (jacobian.T @ radial_unit)
                )
                action = action + braking_effort / ACTUATOR_GEAR
        return action

    def reset():
        nonlocal latest_observation
        latest_observation = None

    return PolicyIO(
        observe=observe,
        action=action_with_prearrival_velocity_shaping,
        reset=reset,
    )
