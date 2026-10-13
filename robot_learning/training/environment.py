"""Training-only environment construction for the branch-geometry route.

The training route retains a 50/50 mixture of uniform official geometry and a
folded-only bearing sector. Only the target distribution the policy trains on
lives here. Task mechanics, success semantics and evaluation behavior stay in
`robot_learning/scenario/environment.py`. Changing this module changes what
the policy learns but never how an already-saved policy is measured, so it is
excluded from the research-evaluation semantics fingerprint.
"""

import gymnasium as gym
import numpy as np

from robot_learning.scenario.evaluation import classify_target_ik_branches
from robot_learning.scenario.environment import TwoJointArmReachEnv

TRAINING_TARGET_RADIUS_RANGE = (0.06, 0.20)
FOCUSED_BEARING_DEGREES = (-160.0, -105.0)
FOCUSED_BEARING_RANGE = tuple(np.deg2rad(FOCUSED_BEARING_DEGREES))
FOCUSED_ROUTE_PROBABILITY = 0.5
MAX_FOCUSED_SAMPLING_ATTEMPTS = 256


class BranchGeometryTrainingEnv(TwoJointArmReachEnv):
    """Production reach environment with a bounded geometry-focused reset mix."""

    def __init__(self) -> None:
        super().__init__(target_radius_range=TRAINING_TARGET_RADIUS_RANGE)
        self._last_target_route: str | None = None

    def _sample_target_position(self) -> None:
        target_z = float(self._end_effector_position()[2])
        if float(self.np_random.random()) >= FOCUSED_ROUTE_PROBABILITY:
            self._last_target_route = "uniform"
            radius = float(
                self.np_random.uniform(
                    TRAINING_TARGET_RADIUS_RANGE[0],
                    TRAINING_TARGET_RADIUS_RANGE[1],
                )
            )
            bearing = float(self.np_random.uniform(-np.pi, np.pi))
            self.data.mocap_pos[0] = [
                radius * np.cos(bearing),
                radius * np.sin(bearing),
                target_z,
            ]
            return

        self._last_target_route = "focused"
        for _ in range(MAX_FOCUSED_SAMPLING_ATTEMPTS):
            radius = float(
                self.np_random.uniform(
                    TRAINING_TARGET_RADIUS_RANGE[0],
                    TRAINING_TARGET_RADIUS_RANGE[1],
                )
            )
            bearing = float(
                self.np_random.uniform(
                    FOCUSED_BEARING_RANGE[0], FOCUSED_BEARING_RANGE[1]
                )
            )
            candidate = np.array(
                [
                    radius * np.cos(bearing),
                    radius * np.sin(bearing),
                    target_z,
                ],
                dtype=np.float64,
            )
            classification = classify_target_ik_branches(self.model, candidate)
            if classification["union"] == "folded_only":
                self.data.mocap_pos[0] = candidate
                return

        raise RuntimeError(
            "could not draw a folded_only focused target within "
            f"{MAX_FOCUSED_SAMPLING_ATTEMPTS} attempts"
        )


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return BranchGeometryTrainingEnv()
