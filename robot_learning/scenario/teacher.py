"""Training-only deterministic controller used for policy distillation."""

import mujoco
import numpy as np

from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH

JOINT_LIMIT = np.deg2rad(170.0)
POSITION_GAIN = 36.0
VELOCITY_GAIN = 12.0
ACCELERATION_LIMIT = 160.0


def _wrap_to_pi(angle: np.ndarray) -> np.ndarray:
    return (np.asarray(angle) + np.pi) % (2.0 * np.pi) - np.pi


def _ik_branches(target_x: float, target_y: float) -> tuple[np.ndarray, np.ndarray]:
    radius_squared = target_x**2 + target_y**2
    cosine = (
        radius_squared - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    bearing = float(np.arctan2(target_y, target_x))
    branches = []
    for elbow_angle in (elbow, -elbow):
        shoulder = bearing - np.arctan2(
            FOREARM_LENGTH * np.sin(elbow_angle),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow_angle),
        )
        branches.append(np.array([shoulder, elbow_angle], dtype=np.float64))
    return branches[0], branches[1]


class ComputedTorqueTeacher:
    """Choose a feasible branch and regulate it with the known dynamics."""

    def __init__(
        self,
        position_gain: float = POSITION_GAIN,
        velocity_gain: float = VELOCITY_GAIN,
        acceleration_limit: float = ACCELERATION_LIMIT,
    ) -> None:
        if position_gain <= 0.0:
            raise ValueError("position_gain must be positive")
        if velocity_gain < 0.0:
            raise ValueError("velocity_gain must be non-negative")
        if acceleration_limit <= 0.0:
            raise ValueError("acceleration_limit must be positive")
        self.position_gain = float(position_gain)
        self.velocity_gain = float(velocity_gain)
        self.acceleration_limit = float(acceleration_limit)
        self._target_q: np.ndarray | None = None
        self._gear: np.ndarray | None = None

    def reset(self, env) -> None:
        self._gear = np.asarray(env.model.actuator_gear[:2, 0], dtype=np.float64)
        if np.any(self._gear <= 0.0):
            raise ValueError("teacher requires positive actuator gear")
        target = np.asarray(env.data.mocap_pos[0], dtype=np.float64)
        branches = _ik_branches(float(target[0]), float(target[1]))
        feasible = [
            branch
            for branch in branches
            if np.all(np.abs(branch) <= JOINT_LIMIT + 1e-9)
        ]
        if not feasible:
            raise ValueError("the target has no feasible inverse-kinematic branch")
        current_q = np.asarray(env.data.qpos[:2], dtype=np.float64)
        self._target_q = min(
            feasible,
            key=lambda branch: (
                -float(np.min(JOINT_LIMIT - np.abs(branch))),
                float(np.sum(np.square(_wrap_to_pi(branch - current_q)))),
            ),
        ).copy()

    def action(self, env) -> np.ndarray:
        if self._target_q is None or self._gear is None:
            raise RuntimeError("teacher action requested before reset")
        current_q = np.asarray(env.data.qpos[:2], dtype=np.float64)
        current_qvel = np.asarray(env.data.qvel[:2], dtype=np.float64)
        desired_acceleration = np.clip(
            self.position_gain * _wrap_to_pi(self._target_q - current_q)
            - self.velocity_gain * current_qvel,
            -self.acceleration_limit,
            self.acceleration_limit,
        )
        mujoco.mj_forward(env.model, env.data)
        mass_matrix = np.zeros((2, 2), dtype=np.float64)
        mujoco.mj_fullM(env.model, env.data, mass_matrix)
        torque = (
            mass_matrix @ desired_acceleration
            + np.asarray(env.data.qfrc_bias[:2], dtype=np.float64)
            - np.asarray(env.data.qfrc_passive[:2], dtype=np.float64)
        )
        return np.clip(torque / self._gear, -1.0, 1.0).astype(np.float32)
