"""Bounded joint-setpoint feedback for learned policy outputs."""

import numpy as np

JOINT_SETPOINT_LIMIT = np.deg2rad(170.0)
POSITION_GAIN = np.array([1.25, 1.0], dtype=np.float64)
VELOCITY_GAIN = np.array([0.20, 0.16], dtype=np.float64)


def setpoint_feedback_action(data, action: np.ndarray) -> np.ndarray:
    """Interpret the learned action as an absolute joint setpoint."""
    setpoint = np.clip(
        np.asarray(action, dtype=np.float64),
        -1.0,
        1.0,
    ) * JOINT_SETPOINT_LIMIT
    position_error = setpoint - np.asarray(data.qpos[:2], dtype=np.float64)
    feedback = POSITION_GAIN * position_error - VELOCITY_GAIN * np.asarray(
        data.qvel[:2], dtype=np.float64
    )
    return np.clip(feedback, -1.0, 1.0)
