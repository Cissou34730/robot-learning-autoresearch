"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation

HANDOFF_RADIUS = 0.03
SUCCESS_THRESHOLD = 0.01
POSITION_GAIN = 180.0
VELOCITY_GAIN = 4.0
JOINT_DAMPING_GAIN = 0.15
ACTUATOR_GEAR = 5.0
UPPER_ARM_LENGTH = 0.12
FOREARM_LENGTH = 0.10


class AcquisitionRegulationHandoff:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._qpos: np.ndarray | None = None
        self._qvel: np.ndarray | None = None
        self._target: np.ndarray | None = None

    def observe(self, data) -> np.ndarray:
        self._qpos = np.array(data.qpos[:2], dtype=np.float64, copy=True)
        self._qvel = np.array(data.qvel[:2], dtype=np.float64, copy=True)
        self._target = np.array(data.mocap_pos[0, :2], dtype=np.float64, copy=True)
        return reach_observation(data)

    def action(self, action) -> np.ndarray:
        requested = np.asarray(action, dtype=np.float64)
        if self._qpos is None or self._qvel is None or self._target is None:
            return requested

        shoulder, elbow = self._qpos
        distal_angle = shoulder + elbow
        sin_shoulder = np.sin(shoulder)
        cos_shoulder = np.cos(shoulder)
        sin_distal = np.sin(distal_angle)
        cos_distal = np.cos(distal_angle)
        end_effector = np.array(
            [
                UPPER_ARM_LENGTH * cos_shoulder + FOREARM_LENGTH * cos_distal,
                UPPER_ARM_LENGTH * sin_shoulder + FOREARM_LENGTH * sin_distal,
            ],
            dtype=np.float64,
        )
        jacobian = np.array(
            [
                [
                    -UPPER_ARM_LENGTH * sin_shoulder
                    - FOREARM_LENGTH * sin_distal,
                    -FOREARM_LENGTH * sin_distal,
                ],
                [
                    UPPER_ARM_LENGTH * cos_shoulder
                    + FOREARM_LENGTH * cos_distal,
                    FOREARM_LENGTH * cos_distal,
                ],
            ],
            dtype=np.float64,
        )
        distance = float(np.linalg.norm(end_effector - self._target))
        blend = np.clip(
            (HANDOFF_RADIUS - distance) / (HANDOFF_RADIUS - SUCCESS_THRESHOLD),
            0.0,
            1.0,
        )
        if blend == 0.0:
            return requested

        endpoint_velocity = jacobian @ self._qvel
        task_force = (
            POSITION_GAIN * (self._target - end_effector)
            - VELOCITY_GAIN * endpoint_velocity
        )
        regulator = (
            jacobian.T @ task_force - JOINT_DAMPING_GAIN * self._qvel
        ) / ACTUATOR_GEAR
        return ((1.0 - blend) * requested + blend * regulator).astype(
            np.float64, copy=False
        )


def physical_action(action):
    return action


def make_policy_io():
    handoff = AcquisitionRegulationHandoff()
    return PolicyIO(
        observe=handoff.observe,
        action=handoff.action,
        reset=handoff.reset,
    )
