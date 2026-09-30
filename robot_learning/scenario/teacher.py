"""Training-only deterministic controller used for policy initialization."""

import numpy as np

from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH

JOINT_LIMIT = np.deg2rad(170.0)


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


class DampedIKTeacher:
    """Choose one feasible branch per episode and damp motion toward its pose."""

    def __init__(
        self,
        *,
        position_gain: float,
        velocity_damping: float,
    ) -> None:
        if position_gain <= 0.0:
            raise ValueError("position_gain must be positive")
        if velocity_damping < 0.0:
            raise ValueError("velocity_damping must be non-negative")
        self.position_gain = float(position_gain)
        self.velocity_damping = float(velocity_damping)
        self._ik_target: np.ndarray | None = None

    def reset(self, env) -> None:
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
        self._ik_target = min(
            feasible,
            key=lambda branch: float(
                np.sum(np.square(_wrap_to_pi(branch - current_q)))
            ),
        ).copy()

    def action(self, env) -> np.ndarray:
        if self._ik_target is None:
            raise RuntimeError("teacher action requested before reset")
        current_q = np.asarray(env.data.qpos[:2], dtype=np.float64)
        current_qvel = np.asarray(env.data.qvel[:2], dtype=np.float64)
        action = self.position_gain * _wrap_to_pi(self._ik_target - current_q)
        action -= self.velocity_damping * current_qvel
        return np.clip(action, -1.0, 1.0).astype(np.float32)
