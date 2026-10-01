"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import mujoco
import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import OBSERVATION_SIZE, reach_observation

POLICY_OBSERVATION_SIZE = OBSERVATION_SIZE
JOINT_LIMIT = np.deg2rad(170.0)
BRAKING_START_DISTANCE = 0.07
BRAKING_FULL_DISTANCE = 0.02
POSITION_FEEDBACK_GAIN = 80.0
VELOCITY_FEEDBACK_GAIN = 18.0
MAX_FEEDBACK_ACTION = 0.35


def _wrapped_error(target: np.ndarray, current: np.ndarray) -> np.ndarray:
    return (target - current + np.pi) % (2.0 * np.pi) - np.pi


def _feedback_action(data, target_configuration: np.ndarray, distance: float) -> np.ndarray:
    if distance >= BRAKING_START_DISTANCE:
        return np.zeros(2, dtype=np.float64)

    blend = np.clip(
        (BRAKING_START_DISTANCE - distance)
        / (BRAKING_START_DISTANCE - BRAKING_FULL_DISTANCE),
        0.0,
        1.0,
    )
    qpos = np.asarray(data.qpos[:2], dtype=np.float64)
    qvel = np.asarray(data.qvel[:2], dtype=np.float64)
    q_error = _wrapped_error(target_configuration, qpos)
    desired_acceleration = POSITION_FEEDBACK_GAIN * q_error - VELOCITY_FEEDBACK_GAIN * qvel

    mass_matrix = np.zeros((2, 2), dtype=np.float64)
    mujoco.mj_fullM(data.model, data, mass_matrix)
    joint_torque = mass_matrix @ desired_acceleration
    actuator_gear = np.asarray(data.model.actuator_gear[:2, 0], dtype=np.float64)
    correction = joint_torque / actuator_gear
    return blend * np.clip(correction, -MAX_FEEDBACK_ACTION, MAX_FEEDBACK_ACTION)


def make_policy_io():
    latest_data = [None]
    target_configuration = [None]

    def reset() -> None:
        latest_data[0] = None
        target_configuration[0] = None

    def observe(data) -> np.ndarray:
        current = reach_observation(data)
        qpos = np.asarray(current[:2], dtype=np.float64)
        branch_targets = np.stack(
            [qpos + current[7:9], qpos + current[9:11]], axis=0
        )
        valid = np.all(np.abs(branch_targets) <= JOINT_LIMIT, axis=1)
        branch_errors = np.sum(np.square(branch_targets - qpos), axis=1)
        if np.any(valid):
            branch_errors = np.where(valid, branch_errors, np.inf)
        selected_branch = int(np.argmin(branch_errors))
        latest_data[0] = data
        target_configuration[0] = branch_targets[selected_branch].copy()
        return current.astype(np.float32, copy=False)

    def action(action) -> np.ndarray:
        command = np.asarray(action, dtype=np.float64).copy()
        data = latest_data[0]
        target = target_configuration[0]
        if data is None or target is None:
            return command
        distance = float(
            np.linalg.norm(data.site("end_effector").xpos - data.mocap_pos[0])
        )
        return command + _feedback_action(data, target, distance)

    return PolicyIO(observe=observe, action=action, reset=reset)
