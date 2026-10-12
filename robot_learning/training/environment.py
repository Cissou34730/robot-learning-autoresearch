"""Training-only environment construction for the broadened I2 recipe.

Only the target distribution and training signal the policy trains on live
here. Task mechanics, success semantics and evaluation behavior stay in
`robot_learning/scenario/environment.py`.
"""

from typing import Any

import gymnasium as gym
import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from contracts.task_spec import TARGET_RADIUS_RANGE
from robot_learning.scenario.environment import TwoJointArmReachEnv

TRAINING_TARGET_RADIUS_RANGE = TARGET_RADIUS_RANGE

TRAINING_BRANCH_SEQUENCE = ("open", "folded")
TRAINING_POTENTIAL_COEFFICIENT = 0.05
TRAINING_POTENTIAL_DISCOUNT = 1.0
TRAINING_POTENTIAL_DELTA_LIMIT = 2.0 * float(np.sqrt(2.0) * np.pi)
TRAINING_ESCAPE_COEFFICIENT = 0.05
TRAINING_ESCAPE_DELTA_LIMIT = 0.05
TRAINING_ESCAPE_WINDOW_STEPS = 25


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


class AlternatingBranchTrainingEnv(TwoJointArmReachEnv):
    """Training recipe with explicit IK-branch and reset-escape exposure."""

    def __init__(self) -> None:
        super().__init__(target_radius_range=TRAINING_TARGET_RADIUS_RANGE)
        self._branch_reset_count = 0
        self._training_step_count = 0
        self.selected_branch = TRAINING_BRANCH_SEQUENCE[0]
        self.selected_branch_sign = 1
        self.desired_joint_configuration = np.zeros(2, dtype=np.float64)
        self._previous_branch_potential = 0.0
        self._previous_elbow = 0.0

    def _desired_configuration(self) -> np.ndarray:
        target_x = float(self.data.mocap_pos[0][0])
        target_y = float(self.data.mocap_pos[0][1])
        cos_elbow = (
            target_x**2
            + target_y**2
            - UPPER_ARM_LENGTH**2
            - FOREARM_LENGTH**2
        ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
        elbow = self.selected_branch_sign * float(
            np.arccos(np.clip(cos_elbow, -1.0, 1.0))
        )
        shoulder = float(
            np.arctan2(target_y, target_x)
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )
        return np.array([shoulder, elbow], dtype=np.float64)

    def _branch_potential(self, qpos: np.ndarray) -> float:
        errors = np.asarray(
            [
                _wrap_to_pi(
                    self.desired_joint_configuration[0] - float(qpos[0])
                ),
                _wrap_to_pi(
                    self.desired_joint_configuration[1] - float(qpos[1])
                ),
            ],
            dtype=np.float64,
        )
        potential = -float(np.linalg.norm(errors))
        if not np.isfinite(potential):
            raise FloatingPointError("non-finite branch potential")
        return potential

    def _training_shaping(
        self,
        previous_qpos: np.ndarray,
        current_qpos: np.ndarray,
        step_index: int,
    ) -> tuple[float, float]:
        previous_potential = self._branch_potential(previous_qpos)
        current_potential = self._branch_potential(current_qpos)
        potential_delta = float(
            np.clip(
                TRAINING_POTENTIAL_DISCOUNT * current_potential
                - previous_potential,
                -TRAINING_POTENTIAL_DELTA_LIMIT,
                TRAINING_POTENTIAL_DELTA_LIMIT,
            )
        )
        branch_shaping = TRAINING_POTENTIAL_COEFFICIENT * potential_delta

        escape_shaping = 0.0
        if step_index <= TRAINING_ESCAPE_WINDOW_STEPS:
            signed_elbow_delta = self.selected_branch_sign * (
                float(current_qpos[1]) - float(previous_qpos[1])
            )
            escape_delta = float(
                np.clip(
                    signed_elbow_delta,
                    -TRAINING_ESCAPE_DELTA_LIMIT,
                    TRAINING_ESCAPE_DELTA_LIMIT,
                )
            )
            escape_shaping = TRAINING_ESCAPE_COEFFICIENT * escape_delta

        if not np.isfinite(branch_shaping + escape_shaping):
            raise FloatingPointError("non-finite training shaping")
        return float(branch_shaping), float(escape_shaping)

    def _training_attribution(
        self, branch_shaping: float = 0.0, escape_shaping: float = 0.0
    ) -> dict[str, Any]:
        return {
            "recipe": "I2_broadened_radius_alternating_ik_escape",
            "target_radius_range": tuple(
                float(value) for value in TRAINING_TARGET_RADIUS_RANGE
            ),
            "ik_branch": self.selected_branch,
            "ik_elbow_sign": self.selected_branch_sign,
            "desired_joint_configuration": [
                float(value) for value in self.desired_joint_configuration
            ],
            "branch_potential_shaping": float(branch_shaping),
            "reset_escape_shaping": float(escape_shaping),
            "total_shaping": float(branch_shaping + escape_shaping),
        }

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[np.ndarray, dict[str, Any]]:
        observation, info = super().reset(seed=seed, options=options)

        branch_index = self._branch_reset_count % len(TRAINING_BRANCH_SEQUENCE)
        self.selected_branch = TRAINING_BRANCH_SEQUENCE[branch_index]
        self.selected_branch_sign = 1 if branch_index == 0 else -1
        self._branch_reset_count += 1
        self.desired_joint_configuration = self._desired_configuration()
        self._training_step_count = 0
        current_qpos = np.asarray(self.data.qpos[:2], dtype=np.float64).copy()
        self._previous_branch_potential = self._branch_potential(current_qpos)
        self._previous_elbow = float(current_qpos[1])

        info = dict(info)
        info["training_attribution"] = self._training_attribution()
        return observation, info

    def step(
        self, action: np.ndarray
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        previous_qpos = np.asarray(self.data.qpos[:2], dtype=np.float64).copy()
        next_step = self._training_step_count + 1
        observation, base_reward, terminated, truncated, info = super().step(action)
        current_qpos = np.asarray(self.data.qpos[:2], dtype=np.float64).copy()
        branch_shaping, escape_shaping = self._training_shaping(
            previous_qpos, current_qpos, next_step
        )
        self._training_step_count = next_step
        self._previous_branch_potential = self._branch_potential(current_qpos)
        self._previous_elbow = float(current_qpos[1])

        total_shaping = branch_shaping + escape_shaping
        total_reward = float(base_reward + total_shaping)
        info = dict(info)
        attribution = self._training_attribution(
            branch_shaping, escape_shaping
        )
        attribution["base_reward"] = float(base_reward)
        attribution["total_reward"] = total_reward
        info["training_attribution"] = attribution
        return observation, total_reward, terminated, truncated, info


def make_training_env() -> gym.Env:
    """Build the Gymnasium environment used for training this scenario."""
    return AlternatingBranchTrainingEnv()
