"""Training-only environment construction for the targeted exposure recipe.

Only the target distribution the policy trains on lives here. Task mechanics,
success semantics and evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what the
policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

import math

import gymnasium as gym

from contracts.task_spec import TARGET_RADIUS_RANGE
from robot_learning.scenario.environment import TwoJointArmReachEnv

TRAINING_TARGET_RADIUS_RANGE = TARGET_RADIUS_RANGE
DIFFICULT_ANGLE_RANGE = (-0.5 * math.pi, 0.0)
DIFFICULT_ANGLE_MIXTURE = 0.5


class TargetedTrainingEnv(TwoJointArmReachEnv):
    """Training environment with the I2 target-exposure distribution."""

    def _sample_target_position(self) -> None:
        if self.np_random.random() < DIFFICULT_ANGLE_MIXTURE:
            angle = float(self.np_random.uniform(*DIFFICULT_ANGLE_RANGE))
        else:
            angle = float(self.np_random.uniform(-math.pi, math.pi))
        radius = float(
            self.np_random.uniform(
                self.target_radius_range[0], self.target_radius_range[1]
            )
        )
        # Keep the target in the arm's plane, matching the shared scenario
        # sampler without changing evaluation or task mechanics.
        target_z = float(self._end_effector_position()[2])
        self.data.mocap_pos[0] = [
            radius * math.cos(angle),
            radius * math.sin(angle),
            target_z,
        ]


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return TargetedTrainingEnv(target_radius_range=TRAINING_TARGET_RADIUS_RANGE)
