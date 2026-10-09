"""Training-only environment construction for branch/limit-aware coverage.

Only the target distribution the policy trains on lives here. The training
sampler preserves the official support while making one-branch and
low-limit-margin targets more frequent. Task mechanics, success semantics and
evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what the
policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

import gymnasium as gym
import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from contracts.task_spec import TARGET_RADIUS_RANGE
from robot_learning.scenario.environment import TwoJointArmReachEnv

TRAINING_TARGET_RADIUS_RANGE = TARGET_RADIUS_RANGE
JOINT_LIMIT_RAD = float(np.deg2rad(170.0))


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _branch_limit_margins(radius: float, angle: float) -> tuple[float, float]:
    cos_elbow = (
        radius**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))
    margins = []
    for elbow in (elbow_open, -elbow_open):
        shoulder = _wrap_to_pi(
            angle
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )
        margins.append(
            min(
                JOINT_LIMIT_RAD - abs(shoulder),
                JOINT_LIMIT_RAD - abs(elbow),
            )
        )
    return float(margins[0]), float(margins[1])


def _coverage_weight(radius: float, angle: float) -> float:
    margins = _branch_limit_margins(radius, angle)
    feasible_margins = [margin for margin in margins if margin >= 0.0]
    one_branch_bonus = 4.0 if len(feasible_margins) == 1 else 0.0
    minimum_margin = min(feasible_margins)
    low_margin_fraction = np.clip(1.0 - minimum_margin / 0.5, 0.0, 1.0)
    return float(1.0 + one_branch_bonus + 2.0 * low_margin_fraction)


class BranchAwareTrainingEnv(TwoJointArmReachEnv):
    """Sample all official targets while emphasizing limit-sensitive geometry."""

    def _sample_target_position(self) -> None:
        maximum_weight = 7.0
        while True:
            angle = float(self.np_random.uniform(-np.pi, np.pi))
            radius = float(
                self.np_random.uniform(
                    TRAINING_TARGET_RADIUS_RANGE[0],
                    TRAINING_TARGET_RADIUS_RANGE[1],
                )
            )
            weight = _coverage_weight(radius, angle)
            if self.np_random.uniform(0.0, maximum_weight) <= weight:
                break

        target_z = float(self._end_effector_position()[2])
        self.data.mocap_pos[0] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            target_z,
        ]


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return BranchAwareTrainingEnv(target_radius_range=TRAINING_TARGET_RADIUS_RANGE)
