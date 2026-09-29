"""Training-only environment construction for terminal stabilization.

The intervention is inactive during approach and penalizes velocity only after
the endpoint has entered the official tolerance. Evaluation continues to use
the shared task mechanics without this training-only target distribution.
"""

import gymnasium as gym

from robot_learning.scenario.environment import TwoJointArmReachEnv

TRAINING_TARGET_RADIUS_RANGE = (0.14, 0.20)
TERMINAL_STABILIZATION_SCALE = 0.25


class TerminalStabilizationReachEnv(TwoJointArmReachEnv):
    """Preserve approach learning while rewarding a low-velocity terminal state."""

    def __init__(self) -> None:
        super().__init__(
            target_radius_range=TRAINING_TARGET_RADIUS_RANGE,
            boundary_braking_scale=0.0,
            terminal_stabilization_scale=TERMINAL_STABILIZATION_SCALE,
        )


def make_training_env() -> gym.Env:
    """Build the reach-preserving terminal-stabilization training environment."""
    return TerminalStabilizationReachEnv()
