"""Training-only environment factory.

This module configures the conditions under which the policy is trained. It is
excluded from research-evaluation semantics by the Runner, so training
curricula can change without invalidating completed measurements. Evaluation
and the protected benchmark build their own environments from the official task
constants and never import this module.
"""

from robot_learning.scenario.environment import (
    TRAINING_TARGET_RADIUS_RANGE,
    TwoJointArmReachEnv,
)

# Train the hold against a tighter tolerance than the official 10 mm task so the
# policy must reach inside the target band instead of settling on its boundary.
TRAINING_SUCCESS_THRESHOLD = 0.007


def make_training_env() -> TwoJointArmReachEnv:
    """Build the Gymnasium environment used for training this scenario."""
    return TwoJointArmReachEnv(
        target_radius_range=TRAINING_TARGET_RADIUS_RANGE,
        success_threshold=TRAINING_SUCCESS_THRESHOLD,
    )
