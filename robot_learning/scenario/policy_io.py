"""Researcher-owned policy inputs and mapping to the robot's physical commands."""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.observations import reach_observation

TARGET_GUIDANCE_WEIGHT = 0.2
TARGET_GUIDANCE_ERROR_SCALE = 0.04


class _TargetConditionedAction:
    def __init__(self):
        self._target_xy: np.ndarray | None = None
        self._end_effector_xy: np.ndarray | None = None
        self._joint_positions: np.ndarray | None = None

    def observe(self, data):
        self._target_xy = np.asarray(data.mocap_pos[0][:2], dtype=np.float64).copy()
        self._end_effector_xy = np.asarray(
            data.site("end_effector").xpos[:2], dtype=np.float64
        ).copy()
        self._joint_positions = np.asarray(data.qpos[:2], dtype=np.float64).copy()
        return reach_observation(data)

    def action(self, action):
        if (
            self._target_xy is None
            or self._end_effector_xy is None
            or self._joint_positions is None
        ):
            raise RuntimeError("target-conditioned action used before observation")

        command = np.asarray(action, dtype=np.float64)
        if command.shape != (2,):
            raise ValueError(f"expected a two-joint action, got shape {command.shape}")

        shoulder, elbow = self._joint_positions
        forearm_angle = shoulder + elbow
        jacobian = np.array(
            [
                [
                    -UPPER_ARM_LENGTH * np.sin(shoulder)
                    - FOREARM_LENGTH * np.sin(forearm_angle),
                    -FOREARM_LENGTH * np.sin(forearm_angle),
                ],
                [
                    UPPER_ARM_LENGTH * np.cos(shoulder)
                    + FOREARM_LENGTH * np.cos(forearm_angle),
                    FOREARM_LENGTH * np.cos(forearm_angle),
                ],
            ]
        )
        target_error = self._target_xy - self._end_effector_xy
        guidance = jacobian.T @ target_error / TARGET_GUIDANCE_ERROR_SCALE
        guidance = np.clip(guidance, -1.0, 1.0)
        return np.clip(
            np.clip(command, -1.0, 1.0) + TARGET_GUIDANCE_WEIGHT * guidance,
            -1.0,
            1.0,
        )

    def reset(self):
        self._target_xy = None
        self._end_effector_xy = None
        self._joint_positions = None


def make_policy_io():
    mapping = _TargetConditionedAction()
    return PolicyIO(
        observe=mapping.observe,
        action=mapping.action,
        reset=mapping.reset,
    )
