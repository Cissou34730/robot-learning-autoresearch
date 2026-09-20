"""Training-only environment construction for the staged curriculum recipe.

Only the target distribution the policy trains on lives here. Task mechanics,
success semantics and evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what the
policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

import gymnasium as gym
import numpy as np

from robot_learning.scenario.environment import TwoJointArmReachEnv

TRAINING_TARGET_RADIUS_RANGE = (0.14, 0.20)
HARD_TARGET_RADIUS_RANGE = (0.06, 0.14)
CURRICULUM_WARMUP_STEPS = 40_000
CURRICULUM_RAMP_STEPS = 40_000
MAX_HARD_TARGET_PROBABILITY = 0.5


class StagedCurriculumReachEnv(TwoJointArmReachEnv):
    """Preserve baseline training before gradually adding inner-radius targets."""

    def __init__(self) -> None:
        super().__init__(target_radius_range=TRAINING_TARGET_RADIUS_RANGE)
        self._training_steps = 0

    def _sample_target_position(self) -> None:
        ramp_progress = np.clip(
            (self._training_steps - CURRICULUM_WARMUP_STEPS)
            / CURRICULUM_RAMP_STEPS,
            0.0,
            1.0,
        )
        hard_target_probability = (
            float(ramp_progress) * MAX_HARD_TARGET_PROBABILITY
        )
        if self.np_random.random() < hard_target_probability:
            self.target_radius_range = HARD_TARGET_RADIUS_RANGE
        else:
            self.target_radius_range = TRAINING_TARGET_RADIUS_RANGE
        super()._sample_target_position()

    def step(
        self, action: np.ndarray
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, object]]:
        result = super().step(action)
        self._training_steps += 1
        return result


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used to train this scenario."""
    return StagedCurriculumReachEnv()
