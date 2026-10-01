"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.hybrid_control import feasible_ik_solutions, wrap_to_pi
from robot_learning.scenario.observations import reach_observation

CONTROL_TORQUE_LIMIT = 5.0
POSITION_KP = 5.0
POSITION_KD = 0.75
RESIDUAL_TORQUE_LIMIT = 1.0


def make_policy_io():
    state = {
        "qpos": np.zeros(2, dtype=np.float64),
        "qvel": np.zeros(2, dtype=np.float64),
        "desired_q": None,
    }

    def observe(data):
        state["qpos"] = np.asarray(data.qpos[:2], dtype=np.float64).copy()
        state["qvel"] = np.asarray(data.qvel[:2], dtype=np.float64).copy()
        return reach_observation(data)

    def physical_action(action):
        if state["desired_q"] is None:
            target = np.asarray(data_target, dtype=np.float64)
            solutions = feasible_ik_solutions(float(target[0]), float(target[1]))
            state["desired_q"] = min(
                solutions,
                key=lambda candidate: float(
                    np.sum(np.square(candidate - state["qpos"]))
                ),
            )
        error = state["desired_q"] - state["qpos"]
        error[0] = wrap_to_pi(float(error[0]))
        torque = POSITION_KP * error - POSITION_KD * state["qvel"]
        residual = np.clip(np.asarray(action, dtype=np.float64), -1.0, 1.0)
        torque += RESIDUAL_TORQUE_LIMIT * residual
        return np.clip(
            torque / CONTROL_TORQUE_LIMIT, -1.0, 1.0
        ).astype(np.float32)

    def reset():
        state["qpos"].fill(0.0)
        state["qvel"].fill(0.0)
        state["desired_q"] = None

    data_target = np.zeros(3, dtype=np.float64)

    def observe_with_target(data):
        data_target[:] = data.mocap_pos[0]
        return observe(data)

    return PolicyIO(observe=observe_with_target, action=physical_action, reset=reset)
