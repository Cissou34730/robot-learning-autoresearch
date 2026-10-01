"""Configuration-aware kinematics used by the hybrid policy interface."""

import math

import numpy as np

from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH

JOINT_LIMIT = float(np.deg2rad(170.0))


def wrap_to_pi(angle: float) -> float:
    return float((angle + math.pi) % (2.0 * math.pi) - math.pi)


def feasible_ik_solutions(x: float, y: float) -> tuple[np.ndarray, ...]:
    radius_squared = x * x + y * y
    cosine = (
        radius_squared - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_magnitude = math.acos(float(np.clip(cosine, -1.0, 1.0)))
    target_angle = math.atan2(y, x)
    solutions: list[np.ndarray] = []
    for elbow in (elbow_magnitude, -elbow_magnitude):
        shoulder = target_angle - math.atan2(
            FOREARM_LENGTH * math.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * math.cos(elbow),
        )
        candidate = np.array([wrap_to_pi(shoulder), elbow], dtype=np.float64)
        if np.all(np.abs(candidate) <= JOINT_LIMIT):
            solutions.append(candidate)
    if not solutions:
        raise ValueError(f"target ({x}, {y}) has no feasible IK branch")
    return tuple(solutions)
