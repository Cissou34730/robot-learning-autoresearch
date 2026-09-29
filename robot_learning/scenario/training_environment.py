"""Training-only environment construction for the staged braking recipe.

Only the target distribution the policy trains on lives here. Task mechanics,
success semantics and evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what the
policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

import gymnasium as gym

from robot_learning.scenario.environment import TwoJointArmReachEnv

TRAINING_TARGET_RADIUS_RANGE = (0.14, 0.20)
BRAKING_WARMUP_STEPS = 30_000
BRAKING_RAMP_STEPS = 30_000
BRAKING_FINAL_SCALE = 0.1


class StagedBrakingReachEnv(TwoJointArmReachEnv):
    """Preserve reach learning before introducing a weak boundary objective."""

    def __init__(self) -> None:
        super().__init__(target_radius_range=TRAINING_TARGET_RADIUS_RANGE)
        self._training_steps = 0

    def _current_boundary_braking_scale(self) -> float:
        if self._training_steps < BRAKING_WARMUP_STEPS:
            return 0.0
        ramp_progress = min(
            (self._training_steps - BRAKING_WARMUP_STEPS) / BRAKING_RAMP_STEPS,
            1.0,
        )
        return BRAKING_FINAL_SCALE * ramp_progress

    def step(self, action):
        result = super().step(action)
        self._training_steps += 1
        return result


def make_training_env() -> gym.Env:
    """Build the reach-preserving staged-braking training environment."""
    return StagedBrakingReachEnv()
