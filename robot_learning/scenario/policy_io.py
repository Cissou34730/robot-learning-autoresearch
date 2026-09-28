"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.observations import reach_observation

JOINT_LIMIT_RADIANS = np.deg2rad(170.0)
BRANCH_COMMIT_DISTANCE_METERS = 0.06


def physical_action(action):
    return action


def make_policy_io():
    branch_remapped = False

    def reset():
        nonlocal branch_remapped
        branch_remapped = False

    def observe(data):
        nonlocal branch_remapped
        observation = reach_observation(data)
        if not branch_remapped and float(np.linalg.norm(observation[4:7])) <= (
            BRANCH_COMMIT_DISTANCE_METERS
        ):
            target_x = float(data.mocap_pos[0][0])
            target_y = float(data.mocap_pos[0][1])
            target_angle = float(np.arctan2(target_y, target_x))
            cos_elbow = (
                target_x**2
                + target_y**2
                - UPPER_ARM_LENGTH**2
                - FOREARM_LENGTH**2
            ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
            elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))
            elbow_folded = -elbow_open

            def shoulder_for_elbow(elbow: float) -> float:
                return float(
                    (
                        target_angle
                        - np.arctan2(
                            FOREARM_LENGTH * np.sin(elbow),
                            UPPER_ARM_LENGTH
                            + FOREARM_LENGTH * np.cos(elbow),
                        )
                        + np.pi
                    )
                    % (2.0 * np.pi)
                    - np.pi
                )

            shoulder_open = shoulder_for_elbow(elbow_open)
            shoulder_folded = shoulder_for_elbow(elbow_folded)
            open_margin = min(
                JOINT_LIMIT_RADIANS - abs(shoulder_open),
                JOINT_LIMIT_RADIANS - abs(elbow_open),
            )
            folded_margin = min(
                JOINT_LIMIT_RADIANS - abs(shoulder_folded),
                JOINT_LIMIT_RADIANS - abs(elbow_folded),
            )
            if open_margin < 0.0 <= folded_margin:
                branch_remapped = True

        if branch_remapped:
            observation[7:11] = observation[[9, 10, 7, 8]]
        return observation

    return PolicyIO(observe=observe, action=physical_action, reset=reset)
