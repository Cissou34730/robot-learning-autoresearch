"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.scenario.observations import (
    OBSERVATION_SIZE,
    ik_branch_targets,
    reach_observation,
)

POLICY_OBSERVATION_SIZE = OBSERVATION_SIZE
JOINT_LIMIT = np.deg2rad(170.0)


def make_policy_io():
    selected_branch = [None]

    def reset() -> None:
        selected_branch[0] = None

    def observe(data) -> np.ndarray:
        if selected_branch[0] is None:
            qpos = np.asarray(data.qpos[:2], dtype=np.float64)
            branch_targets = ik_branch_targets(data)
            valid = np.all(np.abs(branch_targets) <= JOINT_LIMIT, axis=1)
            branch_distances = np.sum(np.square(branch_targets - qpos), axis=1)
            if np.any(valid):
                branch_distances = np.where(valid, branch_distances, np.inf)
            selected_branch[0] = int(np.argmin(branch_distances))
        return reach_observation(data, branch_index=selected_branch[0])

    def action(action) -> np.ndarray:
        return np.asarray(action, dtype=np.float64).copy()

    return PolicyIO(observe=observe, action=action, reset=reset)
