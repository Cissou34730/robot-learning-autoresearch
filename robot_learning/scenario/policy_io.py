"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation


class PhaseAwareController:
    """Blend learned approach actions into a damped Cartesian settling controller."""

    UPPER_ARM_LENGTH = 0.12
    FOREARM_LENGTH = 0.10
    ACTUATOR_GEAR = 5.0
    BRAKING_DISTANCE = 0.06
    APPROACH_RESET_DISTANCE = 0.075
    SETTLING_DISTANCE = 0.02
    SETTLING_SPEED = 0.35
    REBRAKE_SPEED = 0.75
    POSITION_GAIN = 120.0
    VELOCITY_GAIN = 12.0
    JOINT_DAMPING = 0.4

    def __init__(self) -> None:
        self._observation: np.ndarray | None = None
        self._phase = "approach"

    def reset(self) -> None:
        self._observation = None
        self._phase = "approach"

    def observe(self, data) -> np.ndarray:
        self._observation = reach_observation(data)
        return self._observation

    def _update_phase(self, distance: float, speed: float) -> None:
        if distance > self.APPROACH_RESET_DISTANCE:
            self._phase = "approach"
        elif self._phase == "approach":
            self._phase = "braking"
        elif self._phase == "braking" and (
            distance <= self.SETTLING_DISTANCE and speed <= self.SETTLING_SPEED
        ):
            self._phase = "settling"
        elif self._phase == "settling" and (
            distance > self.SETTLING_DISTANCE * 1.5 or speed > self.REBRAKE_SPEED
        ):
            self._phase = "braking"

    def _settling_action(self, observation: np.ndarray) -> np.ndarray:
        q1, q2 = observation[:2]
        qvel = observation[2:4]
        target_error = -observation[4:6]
        sin_q2 = np.sin(q1 + q2)
        cos_q2 = np.cos(q1 + q2)
        jacobian = np.array(
            [
                [
                    -self.UPPER_ARM_LENGTH * np.sin(q1)
                    - self.FOREARM_LENGTH * sin_q2,
                    -self.FOREARM_LENGTH * sin_q2,
                ],
                [
                    self.UPPER_ARM_LENGTH * np.cos(q1)
                    + self.FOREARM_LENGTH * cos_q2,
                    self.FOREARM_LENGTH * cos_q2,
                ],
            ],
            dtype=np.float64,
        )
        cartesian_velocity = jacobian @ qvel
        force = self.POSITION_GAIN * target_error - self.VELOCITY_GAIN * cartesian_velocity
        torque = jacobian.T @ force - self.JOINT_DAMPING * qvel
        return np.clip(torque / self.ACTUATOR_GEAR, -1.0, 1.0)

    def action(self, action: np.ndarray) -> np.ndarray:
        if self._observation is None:
            raise RuntimeError("an observation is required before mapping an action")
        learned_action = np.asarray(action, dtype=np.float64)
        observation = self._observation
        distance = float(np.linalg.norm(observation[4:6]))
        q1, q2 = observation[:2]
        sin_q2 = np.sin(q1 + q2)
        cos_q2 = np.cos(q1 + q2)
        jacobian = np.array(
            [
                [
                    -self.UPPER_ARM_LENGTH * np.sin(q1)
                    - self.FOREARM_LENGTH * sin_q2,
                    -self.FOREARM_LENGTH * sin_q2,
                ],
                [
                    self.UPPER_ARM_LENGTH * np.cos(q1)
                    + self.FOREARM_LENGTH * cos_q2,
                    self.FOREARM_LENGTH * cos_q2,
                ],
            ],
            dtype=np.float64,
        )
        speed = float(np.linalg.norm(jacobian @ observation[2:4]))
        self._update_phase(distance, speed)

        if self._phase == "approach":
            return learned_action
        if self._phase == "settling":
            return self._settling_action(observation)

        distance_weight = np.clip(
            (self.BRAKING_DISTANCE - distance)
            / (self.BRAKING_DISTANCE - self.SETTLING_DISTANCE),
            0.0,
            1.0,
        )
        speed_weight = np.clip((speed - self.SETTLING_SPEED) / 0.5, 0.0, 1.0)
        blend = max(float(distance_weight), 0.75 * float(speed_weight))
        settling_action = self._settling_action(observation)
        return (1.0 - blend) * learned_action + blend * settling_action


class ContinuousResidualController:
    """Apply a continuous feasible-IK torque reference plus a learned residual."""

    UPPER_ARM_LENGTH = 0.12
    FOREARM_LENGTH = 0.10
    ACTUATOR_GEAR = 5.0
    JOINT_LIMIT = np.deg2rad(170.0)
    POSITION_GAIN = np.array([3.0, 2.0], dtype=np.float64)
    VELOCITY_GAIN = np.array([0.35, 0.25], dtype=np.float64)
    RESIDUAL_SCALE = 0.35

    def __init__(self) -> None:
        self._observation: np.ndarray | None = None
        self._target_configuration: np.ndarray | None = None

    def reset(self) -> None:
        self._observation = None
        self._target_configuration = None

    def observe(self, data) -> np.ndarray:
        self._observation = reach_observation(data)
        return self._observation

    @staticmethod
    def _wrap_to_pi(angle: np.ndarray | float) -> np.ndarray | float:
        return (np.asarray(angle) + np.pi) % (2.0 * np.pi) - np.pi

    def _ik_candidates(self, observation: np.ndarray) -> np.ndarray:
        q1, q2 = observation[:2]
        end_effector = np.array(
            [
                self.UPPER_ARM_LENGTH * np.cos(q1)
                + self.FOREARM_LENGTH * np.cos(q1 + q2),
                self.UPPER_ARM_LENGTH * np.sin(q1)
                + self.FOREARM_LENGTH * np.sin(q1 + q2),
            ],
            dtype=np.float64,
        )
        target = end_effector - observation[4:6]
        radius_squared = float(np.dot(target, target))
        elbow_magnitude = float(
            np.arccos(
                np.clip(
                    (
                        radius_squared
                        - self.UPPER_ARM_LENGTH**2
                        - self.FOREARM_LENGTH**2
                    )
                    / (2.0 * self.UPPER_ARM_LENGTH * self.FOREARM_LENGTH),
                    -1.0,
                    1.0,
                )
            )
        )
        target_angle = float(np.arctan2(target[1], target[0]))
        candidates = []
        for elbow in (elbow_magnitude, -elbow_magnitude):
            shoulder = target_angle - np.arctan2(
                self.FOREARM_LENGTH * np.sin(elbow),
                self.UPPER_ARM_LENGTH + self.FOREARM_LENGTH * np.cos(elbow),
            )
            candidates.append(
                np.array(
                    [
                        float(self._wrap_to_pi(shoulder)),
                        elbow,
                    ],
                    dtype=np.float64,
                )
            )
        return np.asarray(candidates)

    def _select_target_configuration(self, observation: np.ndarray) -> np.ndarray:
        candidates = self._ik_candidates(observation)
        current = observation[:2].astype(np.float64)
        errors = self._wrap_to_pi(candidates - current)
        feasible = np.all(np.abs(candidates) <= self.JOINT_LIMIT, axis=1)
        scores = np.sum(np.square(errors), axis=1)
        scores += 0.05 * np.sum(
            np.square(candidates / self.JOINT_LIMIT), axis=1
        )
        if np.any(feasible):
            scores = np.where(feasible, scores, np.inf)
        selected = candidates[int(np.argmin(scores))]
        return np.clip(selected, -self.JOINT_LIMIT, self.JOINT_LIMIT)

    def _reference_action(self, observation: np.ndarray) -> np.ndarray:
        if self._target_configuration is None:
            self._target_configuration = self._select_target_configuration(observation)
        position_error = self._wrap_to_pi(
            self._target_configuration - observation[:2]
        )
        torque = (
            self.POSITION_GAIN * position_error
            - self.VELOCITY_GAIN * observation[2:4]
        )
        return torque / self.ACTUATOR_GEAR

    def action(self, action: np.ndarray) -> np.ndarray:
        if self._observation is None:
            raise RuntimeError("an observation is required before mapping an action")
        learned_action = np.asarray(action, dtype=np.float64)
        reference_action = self._reference_action(self._observation)
        return np.clip(
            reference_action + self.RESIDUAL_SCALE * learned_action,
            -1.0,
            1.0,
        )


def make_policy_io():
    controller = ContinuousResidualController()
    return PolicyIO(
        observe=controller.observe,
        action=controller.action,
        reset=controller.reset,
    )
