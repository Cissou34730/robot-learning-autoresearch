"""Training-only environment construction for the coverage-focused recipe.

Only the target distribution and the training reward live here.  The task
mechanics, success semantics, observations, and evaluation environment stay
in ``robot_learning.scenario.environment``.
"""

from itertools import product
from typing import Any

import gymnasium as gym
import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.environment import TwoJointArmReachEnv

TRAINING_TARGET_RADIUS_RANGE = (0.06, 0.20)
SAFE_BRANCH_POTENTIAL_COEFFICIENT = 1.0
_TWO_PI = 2.0 * np.pi


class SafeBranchTrajectoryEnv(TwoJointArmReachEnv):
    """T2 mechanics with training-only safe-IK trajectory shaping.

    The selected reference is not added to the observation.  It is used only
    to form a bounded potential difference in the training reward.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._validate_compiled_state()
        self._safe_reference = np.zeros(2, dtype=np.float64)
        self._safe_branch_index = -1
        self._safe_reference_margin = 0.0

    @property
    def safe_reference(self) -> np.ndarray:
        """The selected compiled-limit-feasible joint reference."""
        return self._safe_reference.copy()

    @property
    def safe_branch_index(self) -> int:
        """Zero for the positive-elbow branch and one for the negative branch."""
        return int(self._safe_branch_index)

    @property
    def safe_reference_margin(self) -> float:
        """Minimum normalized joint-limit margin of the selected reference."""
        return float(self._safe_reference_margin)

    def _validate_compiled_state(self) -> np.ndarray:
        if int(self.model.njnt) < 2:
            raise ValueError("safe branch shaping requires two compiled joints")
        ranges = np.asarray(self.model.jnt_range[:2], dtype=np.float64)
        if (
            ranges.shape != (2, 2)
            or not np.all(np.isfinite(ranges))
            or np.any(ranges[:, 1] <= ranges[:, 0])
        ):
            raise ValueError("compiled joint ranges are malformed")
        qpos_addresses = np.asarray(self.model.jnt_qposadr[:2], dtype=np.int64)
        qvel_addresses = np.asarray(self.model.jnt_dofadr[:2], dtype=np.int64)
        if (
            qpos_addresses.shape != (2,)
            or qvel_addresses.shape != (2,)
            or np.any(qpos_addresses < 0)
            or np.any(qvel_addresses < 0)
            or np.any(qpos_addresses >= int(self.model.nq))
            or np.any(qvel_addresses >= int(self.model.nv))
        ):
            raise ValueError("compiled joint addresses are malformed")
        if not np.all(np.isfinite(self.data.qpos[qpos_addresses])):
            raise ValueError("compiled joint positions are non-finite")
        if not np.all(np.isfinite(self.data.qvel[qvel_addresses])):
            raise ValueError("compiled joint velocities are non-finite")
        if self.data.mocap_pos.shape[0] < 1:
            raise ValueError("compiled model has no target mocap body")
        return ranges

    def _joint_positions(self) -> np.ndarray:
        self._validate_compiled_state()
        addresses = np.asarray(self.model.jnt_qposadr[:2], dtype=np.int64)
        positions = np.asarray(self.data.qpos[addresses], dtype=np.float64)
        if positions.shape != (2,) or not np.all(np.isfinite(positions)):
            raise ValueError("compiled joint positions are malformed")
        return positions.copy()

    @staticmethod
    def _wrapped_delta(positions: np.ndarray, reference: np.ndarray) -> np.ndarray:
        positions = np.asarray(positions, dtype=np.float64)
        reference = np.asarray(reference, dtype=np.float64)
        if positions.shape != (2,) or reference.shape != (2,):
            raise ValueError("joint positions and references must have shape (2,)")
        if not np.all(np.isfinite(positions)) or not np.all(
            np.isfinite(reference)
        ):
            raise ValueError("joint positions and references must be finite")
        return (positions - reference + np.pi) % _TWO_PI - np.pi

    @classmethod
    def _wrapped_distance(
        cls, positions: np.ndarray, reference: np.ndarray
    ) -> float:
        delta = cls._wrapped_delta(positions, reference)
        distance = float(np.linalg.norm(delta))
        if not np.isfinite(distance):
            raise ValueError("wrapped joint distance is non-finite")
        return distance

    @classmethod
    def _safe_potential(
        cls, positions: np.ndarray, reference: np.ndarray
    ) -> float:
        distance = cls._wrapped_distance(positions, reference)
        normalizer = np.sqrt(2.0) * np.pi
        potential = 1.0 - distance / normalizer
        if not np.isfinite(potential) or not -1e-12 <= potential <= 1.0 + 1e-12:
            raise ValueError("safe-branch potential is outside its finite bound")
        return float(np.clip(potential, 0.0, 1.0))

    @staticmethod
    def _angle_representations(
        angle: float, lower: float, upper: float
    ) -> tuple[float, ...]:
        if not np.isfinite([angle, lower, upper]).all() or upper <= lower:
            raise ValueError("malformed angle or joint range")
        first = int(np.ceil((lower - angle) / _TWO_PI))
        last = int(np.floor((upper - angle) / _TWO_PI))
        values = tuple(
            float(angle + _TWO_PI * turn) for turn in range(first, last + 1)
        )
        if not all(lower <= value <= upper for value in values):
            raise ValueError("angle representation enumeration failed")
        return values

    def _branch_candidates(
        self, target_xy: np.ndarray, ranges: np.ndarray
    ) -> tuple[tuple[np.ndarray, float, float], ...]:
        target_xy = np.asarray(target_xy, dtype=np.float64)
        if target_xy.shape != (2,) or not np.all(np.isfinite(target_xy)):
            raise ValueError("target planar position must be a finite shape-(2,) value")
        cosine = (
            float(np.dot(target_xy, target_xy))
            - UPPER_ARM_LENGTH**2
            - FOREARM_LENGTH**2
        ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
        if not np.isfinite(cosine) or cosine < -1.0 or cosine > 1.0:
            raise ValueError("target is outside the analytic two-link workspace")
        elbow_magnitude = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
        target_angle = float(np.arctan2(target_xy[1], target_xy[0]))
        candidates: list[tuple[np.ndarray, float, float]] = []
        for branch_index, elbow in enumerate(
            (elbow_magnitude, -elbow_magnitude)
        ):
            shoulder = float(
                target_angle
                - np.arctan2(
                    FOREARM_LENGTH * np.sin(elbow),
                    UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
                )
            )
            shoulder_values = self._angle_representations(
                shoulder, float(ranges[0, 0]), float(ranges[0, 1])
            )
            elbow_values = self._angle_representations(
                elbow, float(ranges[1, 0]), float(ranges[1, 1])
            )
            for representation in product(shoulder_values, elbow_values):
                reference = np.asarray(representation, dtype=np.float64)
                half_ranges = 0.5 * (ranges[:, 1] - ranges[:, 0])
                margins = np.minimum(
                    reference - ranges[:, 0], ranges[:, 1] - reference
                ) / half_ranges
                margin = float(np.min(margins))
                if not np.isfinite(margin) or margin < 0.0:
                    raise ValueError("compiled-limit margin is malformed")
                candidates.append((reference, margin, float(branch_index)))
        return tuple(candidates)

    def _select_safe_reference(self) -> None:
        ranges = self._validate_compiled_state()
        target = np.asarray(self.data.mocap_pos[0], dtype=np.float64)
        if target.shape != (3,) or not np.all(np.isfinite(target)):
            raise ValueError("compiled target position is malformed")
        candidates = self._branch_candidates(target[:2], ranges)
        if not candidates:
            raise ValueError("target has no joint-limit-feasible IK branch")
        reset_positions = self._joint_positions()
        best = candidates[0]
        best_distance = self._wrapped_distance(best[0], reset_positions)
        for candidate in candidates[1:]:
            candidate_distance = self._wrapped_distance(
                candidate[0], reset_positions
            )
            if candidate[1] > best[1] and not np.isclose(
                candidate[1], best[1], rtol=1e-12, atol=1e-12
            ):
                best = candidate
                best_distance = candidate_distance
            elif np.isclose(
                candidate[1], best[1], rtol=1e-12, atol=1e-12
            ) and candidate_distance < best_distance:
                best = candidate
                best_distance = candidate_distance
        self._safe_reference = best[0].copy()
        self._safe_reference_margin = float(best[1])
        self._safe_branch_index = int(best[2])

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[np.ndarray, dict[str, Any]]:
        observation, info = super().reset(seed=seed, options=options)
        self._select_safe_reference()
        return observation, info

    def step(
        self, action: np.ndarray
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        ranges = self._validate_compiled_state()
        target = np.asarray(self.data.mocap_pos[0], dtype=np.float64)
        if target.shape != (3,) or not np.all(np.isfinite(target)):
            raise ValueError("compiled target position is malformed")
        if not self._branch_candidates(target[:2], ranges):
            raise ValueError("target has no joint-limit-feasible IK branch")
        previous_positions = self._joint_positions()
        previous_potential = self._safe_potential(
            previous_positions, self._safe_reference
        )
        observation, base_reward, terminated, truncated, info = super().step(action)
        current_positions = self._joint_positions()
        current_potential = self._safe_potential(
            current_positions, self._safe_reference
        )
        safe_branch_potential = SAFE_BRANCH_POTENTIAL_COEFFICIENT * (
            current_potential - previous_potential
        )
        if not np.isfinite(safe_branch_potential) or abs(
            safe_branch_potential
        ) > SAFE_BRANCH_POTENTIAL_COEFFICIENT + 1e-12:
            raise ValueError("safe-branch potential difference is unbounded")
        components = dict(info["reward_components"])
        components["safe_branch_potential"] = float(safe_branch_potential)
        total = float(base_reward + safe_branch_potential)
        if not np.isfinite(total):
            raise ValueError("training reward is non-finite")
        updated_info = dict(info)
        updated_info["reward_components"] = components
        return observation, total, terminated, truncated, updated_info


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used by the safe-branch recipe."""
    return SafeBranchTrajectoryEnv(target_radius_range=TRAINING_TARGET_RADIUS_RANGE)
