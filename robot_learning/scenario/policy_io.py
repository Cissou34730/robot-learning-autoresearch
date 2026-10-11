"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import (
    inverse_kinematic_branches,
    reach_observation,
    wrap_to_pi,
)

STABILIZATION_START_DISTANCE = 0.035
STABILIZATION_FULL_DISTANCE = 0.010
STABILIZATION_POSITION_GAIN = 1.5
STABILIZATION_VELOCITY_GAIN = 0.25


def physical_action(action):
    return action


def make_policy_io():
    latest_data = None
    selected_branch = None

    def reset() -> None:
        nonlocal latest_data, selected_branch
        latest_data = None
        selected_branch = None

    def observe(data):
        nonlocal latest_data, selected_branch
        latest_data = data
        if selected_branch is None:
            branches = inverse_kinematic_branches(
                float(data.mocap_pos[0][0]), float(data.mocap_pos[0][1])
            )
            qpos = np.asarray(data.qpos, dtype=np.float64)
            branch_costs = [
                sum(
                    wrap_to_pi(target - current) ** 2
                    for target, current in zip(branch, qpos)
                )
                for branch in branches
            ]
            selected_branch = int(np.argmin(branch_costs))
        return reach_observation(data)

    def action(policy_action):
        if latest_data is None or selected_branch is None:
            raise RuntimeError("policy action requested before an observation")

        action = np.asarray(physical_action(policy_action), dtype=np.float64)
        distance = float(
            np.linalg.norm(
                latest_data.site("end_effector").xpos - latest_data.mocap_pos[0]
            )
        )
        if distance >= STABILIZATION_START_DISTANCE:
            return action

        branches = inverse_kinematic_branches(
            float(latest_data.mocap_pos[0][0]), float(latest_data.mocap_pos[0][1])
        )
        target = branches[selected_branch]
        qpos = np.asarray(latest_data.qpos, dtype=np.float64)
        qvel = np.asarray(latest_data.qvel, dtype=np.float64)
        stabilization = np.array(
            [
                STABILIZATION_POSITION_GAIN
                * wrap_to_pi(target[index] - qpos[index])
                - STABILIZATION_VELOCITY_GAIN * qvel[index]
                for index in range(2)
            ],
            dtype=np.float64,
        )
        blend = np.clip(
            (STABILIZATION_START_DISTANCE - distance)
            / (STABILIZATION_START_DISTANCE - STABILIZATION_FULL_DISTANCE),
            0.0,
            1.0,
        )
        return np.clip((1.0 - blend) * action + blend * stabilization, -1.0, 1.0)

    return PolicyIO(observe=observe, action=action, reset=reset)
