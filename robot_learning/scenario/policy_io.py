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


def make_policy_io():
    controller = PhaseAwareController()
    return PolicyIO(
        observe=controller.observe,
        action=controller.action,
        reset=controller.reset,
    )
