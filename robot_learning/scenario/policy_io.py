"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import mujoco
import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import OBSERVATION_SIZE, reach_observation

POLICY_OBSERVATION_SIZE = OBSERVATION_SIZE
RESIDUAL_START_DISTANCE = 0.08
RESIDUAL_FULL_DISTANCE = 0.02
TASK_DAMPING_GAIN = 12.0
MAX_RESIDUAL_ACTION = 0.12


def _smooth_residual_gate(distance: float) -> float:
    if distance >= RESIDUAL_START_DISTANCE:
        return 0.0
    if distance <= RESIDUAL_FULL_DISTANCE:
        return 1.0
    fraction = (
        (RESIDUAL_START_DISTANCE - distance)
        / (RESIDUAL_START_DISTANCE - RESIDUAL_FULL_DISTANCE)
    )
    return float(fraction * fraction * (3.0 - 2.0 * fraction))


def _task_space_damping_residual(data, distance: float) -> np.ndarray:
    gate = _smooth_residual_gate(distance)
    if gate == 0.0:
        return np.zeros(2, dtype=np.float64)

    jacobian_position = np.zeros((3, data.model.nv), dtype=np.float64)
    jacobian_rotation = np.zeros((3, data.model.nv), dtype=np.float64)
    mujoco.mj_jacSite(
        data.model,
        data,
        jacobian_position,
        jacobian_rotation,
        data.site("end_effector").id,
    )
    jacobian = jacobian_position[:2, :2]

    mass_matrix = np.zeros((2, 2), dtype=np.float64)
    mujoco.mj_fullM(data.model, data, mass_matrix)
    inverse_mass_times_jacobian = np.linalg.solve(mass_matrix, jacobian.T)
    operational_matrix = (
        jacobian @ inverse_mass_times_jacobian + 1.0e-6 * np.eye(2)
    )
    operational_inertia = np.linalg.solve(operational_matrix, np.eye(2))
    task_velocity = jacobian @ np.asarray(data.qvel[:2], dtype=np.float64)
    desired_task_acceleration = -TASK_DAMPING_GAIN * task_velocity
    joint_torque = (
        jacobian.T @ operational_inertia @ desired_task_acceleration
    )
    actuator_gear = np.asarray(data.model.actuator_gear[:2, 0], dtype=np.float64)
    return gate * np.clip(
        joint_torque / actuator_gear,
        -MAX_RESIDUAL_ACTION,
        MAX_RESIDUAL_ACTION,
    )


def make_policy_io():
    latest_data = [None]

    def reset() -> None:
        latest_data[0] = None

    def observe(data) -> np.ndarray:
        latest_data[0] = data
        return reach_observation(data)

    def action(action) -> np.ndarray:
        command = np.asarray(action, dtype=np.float64).copy()
        data = latest_data[0]
        if data is None:
            return command
        distance = float(
            np.linalg.norm(data.site("end_effector").xpos - data.mocap_pos[0])
        )
        return command + _task_space_damping_residual(data, distance)

    return PolicyIO(observe=observe, action=action, reset=reset)
