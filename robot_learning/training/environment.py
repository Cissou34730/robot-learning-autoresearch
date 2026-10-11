"""Training-only environment construction for the staged-coverage recipe.

Only the target distribution the policy trains on lives here. Task mechanics,
success semantics and evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what the
policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

from typing import Any

import gymnasium as gym

from robot_learning.scenario.environment import TwoJointArmReachEnv

STAGED_RADIUS_RANGES = (
    (0.14, 0.20),
    (0.10, 0.20),
    (0.06, 0.20),
)
STAGE_STEPS = 40_000


class StagedCoverageEnv(TwoJointArmReachEnv):
    """Expose the missing inner workspace progressively during transfer."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(target_radius_range=STAGED_RADIUS_RANGES[0], **kwargs)
        self._training_steps = 0

    def _active_radius_range(self) -> tuple[float, float]:
        stage = min(self._training_steps // STAGE_STEPS, len(STAGED_RADIUS_RANGES) - 1)
        return STAGED_RADIUS_RANGES[stage]

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[Any, dict[str, Any]]:
        self.target_radius_range = self._active_radius_range()
        return super().reset(seed=seed, options=options)

    def step(self, action: Any) -> tuple[Any, float, bool, bool, dict[str, Any]]:
        result = super().step(action)
        self._training_steps += 1
        return result


def make_training_env() -> gym.Env:
    """Build the staged target-distribution environment used for transfer."""
    return StagedCoverageEnv()
