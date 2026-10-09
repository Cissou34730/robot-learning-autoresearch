"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation


JOINT_LIMIT_RAD = float(np.deg2rad(170.0))
JOINT_LIMIT_GUARD_RAD = float(np.deg2rad(15.0))


def make_policy_io():
    latest_qpos = np.zeros(2, dtype=np.float32)

    def observe(data):
        latest_qpos[:] = data.qpos[:2]
        return reach_observation(data)

    def physical_action(action):
        requested_action = np.asarray(action, dtype=np.float32)
        if requested_action.shape != (2,):
            raise ValueError("action must have shape (2,)")
        action_out = requested_action.copy()
        limit_margin = JOINT_LIMIT_RAD - np.abs(latest_qpos)
        guard_scale = np.clip(limit_margin / JOINT_LIMIT_GUARD_RAD, 0.0, 1.0)
        outward = latest_qpos * action_out > 0.0
        action_out[outward] *= guard_scale[outward]
        return action_out

    def reset():
        latest_qpos[:] = 0.0

    return PolicyIO(
        observe=observe,
        action=physical_action,
        reset=reset,
    )
