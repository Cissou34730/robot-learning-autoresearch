"""Branch-aware inverse-kinematics guidance for the two-joint arm.

The controller is deliberately episode-scoped: :meth:`select_branch` is
called once after a target is sampled, and the selected inverse-kinematics
configuration is then latched until reset.  The learned action remains a
bounded residual rather than being replaced by this guidance.
"""

from dataclasses import dataclass

import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH

# These are the only control gains and blend weights used by this method.
# Guidance is a bounded joint-space command; the policy residual is intentionally
# smaller so it can refine, but not immediately erase, the selected branch.
GUIDANCE_PROPORTIONAL_GAIN = 1.0
GUIDANCE_VELOCITY_DAMPING = 0.10
GUIDANCE_BLEND_WEIGHT = 1.0
POLICY_RESIDUAL_WEIGHT = 0.35

# Branch ranking is deterministic: proximity is minimized first in score form,
# with a smaller preference for configurations farther from their limits.
BRANCH_PROXIMITY_WEIGHT = 1.0
BRANCH_LIMIT_MARGIN_WEIGHT = 0.10

ACTION_LOW = -1.0
ACTION_HIGH = 1.0
IK_REACHABILITY_EPSILON = 1e-10


def _wrap_to_pi(angle):
    """Return an angle error in the half-open interval [-pi, pi)."""
    return (np.asarray(angle) + np.pi) % (2.0 * np.pi) - np.pi


@dataclass(frozen=True)
class FeasibleBranch:
    """A joint-space IK solution that satisfies the model's joint limits."""

    name: str
    target: np.ndarray
    proximity_cost: float
    limit_margin: float
    score: float


class BranchAwareController:
    """Latch a feasible planar IK branch and provide bounded guidance."""

    def __init__(self, model) -> None:
        if int(model.njnt) < 2:
            raise ValueError("branch-aware control requires two arm joints")
        self.model = model
        self._joint_ids = (0, 1)
        self._qpos_indices = tuple(
            int(model.jnt_qposadr[joint_id]) for joint_id in self._joint_ids
        )
        self._qvel_indices = tuple(
            int(model.jnt_dofadr[joint_id]) for joint_id in self._joint_ids
        )
        self.selected_branch: str | None = None
        self.selected_target: np.ndarray | None = None

    def _joint_state(self, data) -> tuple[np.ndarray, np.ndarray]:
        qpos = np.asarray(data.qpos[list(self._qpos_indices)], dtype=np.float64)
        qvel = np.asarray(data.qvel[list(self._qvel_indices)], dtype=np.float64)
        return qpos, qvel

    @staticmethod
    def _shoulder_for_elbow(target_x: float, target_y: float, elbow: float) -> float:
        return float(
            np.arctan2(target_y, target_x)
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )

    def _ik_solutions(self, target: np.ndarray) -> tuple[tuple[str, np.ndarray], ...]:
        target_x, target_y = (float(value) for value in target)
        cosine = (
            target_x**2
            + target_y**2
            - UPPER_ARM_LENGTH**2
            - FOREARM_LENGTH**2
        ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
        if cosine < -1.0 - IK_REACHABILITY_EPSILON or cosine > 1.0 + IK_REACHABILITY_EPSILON:
            return ()
        elbow_open = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
        solutions = []
        for name, elbow in (
            ("elbow_positive", elbow_open),
            ("elbow_negative", -elbow_open),
        ):
            shoulder = self._shoulder_for_elbow(target_x, target_y, elbow)
            solutions.append(
                (name, np.asarray([shoulder, elbow], dtype=np.float64))
            )
        return tuple(solutions)

    def _fit_solution_to_limits(
        self, solution: np.ndarray, current: np.ndarray
    ) -> tuple[np.ndarray, float] | None:
        """Choose an equivalent periodic configuration, rejecting violations."""
        fitted = []
        margins = []
        for position, current_position, joint_id in zip(
            solution, current, self._joint_ids, strict=True
        ):
            if not bool(self.model.jnt_limited[joint_id]):
                fitted.append(float(_wrap_to_pi(position)))
                margins.append(1.0)
                continue

            lower, upper = (
                float(limit) for limit in self.model.jnt_range[joint_id]
            )
            if upper < lower:
                raise ValueError(f"invalid limits for joint {joint_id}")
            minimum_turn = int(
                np.ceil((lower - position) / (2.0 * np.pi))
            )
            maximum_turn = int(
                np.floor((upper - position) / (2.0 * np.pi))
            )
            candidates = [
                float(position + 2.0 * np.pi * turn)
                for turn in range(minimum_turn, maximum_turn + 1)
            ]
            if not candidates:
                return None
            candidate = min(
                candidates,
                key=lambda value: (abs(value - current_position), value),
            )
            fitted.append(candidate)
            span = upper - lower
            margins.append(
                0.0
                if span == 0.0
                else min(candidate - lower, upper - candidate) / span
            )
        return np.asarray(fitted, dtype=np.float64), float(np.mean(margins))

    def select_branch(self, data) -> None:
        """Select and latch one feasible IK branch for the current episode."""
        target = np.asarray(data.mocap_pos[0][:2], dtype=np.float64)
        current, _ = self._joint_state(data)
        feasible: list[FeasibleBranch] = []
        for name, solution in self._ik_solutions(target):
            fitted = self._fit_solution_to_limits(solution, current)
            if fitted is None:
                continue
            fitted_target, limit_margin = fitted
            proximity_error = _wrap_to_pi(fitted_target - current)
            proximity_cost = float(np.sum((proximity_error / np.pi) ** 2))
            score = (
                BRANCH_PROXIMITY_WEIGHT * proximity_cost
                - BRANCH_LIMIT_MARGIN_WEIGHT * limit_margin
            )
            feasible.append(
                FeasibleBranch(
                    name=name,
                    target=fitted_target,
                    proximity_cost=proximity_cost,
                    limit_margin=limit_margin,
                    score=float(score),
                )
            )

        if not feasible:
            self.selected_branch = None
            self.selected_target = None
            raise ValueError(
                "no feasible planar IK branch satisfies the declared joint limits"
            )

        chosen = min(
            feasible,
            key=lambda branch: (branch.score, branch.proximity_cost, branch.name),
        )
        self.selected_branch = chosen.name
        self.selected_target = chosen.target.copy()

    def guidance_action(self, data) -> np.ndarray:
        """Compute bounded PD guidance toward the latched joint-space target."""
        if self.selected_target is None:
            raise RuntimeError("branch-aware guidance requested before branch selection")
        qpos, qvel = self._joint_state(data)
        angle_error = _wrap_to_pi(self.selected_target - qpos)
        guidance = (
            GUIDANCE_PROPORTIONAL_GAIN * angle_error
            - GUIDANCE_VELOCITY_DAMPING * qvel
        )
        return np.clip(guidance, ACTION_LOW, ACTION_HIGH).astype(np.float64)

    def apply(self, policy_action, data) -> tuple[np.ndarray, np.ndarray]:
        """Blend a bounded policy residual with guidance and clip the command."""
        policy = np.clip(
            np.asarray(policy_action, dtype=np.float64), ACTION_LOW, ACTION_HIGH
        )
        guidance = self.guidance_action(data)
        applied = np.clip(
            GUIDANCE_BLEND_WEIGHT * guidance
            + POLICY_RESIDUAL_WEIGHT * policy,
            ACTION_LOW,
            ACTION_HIGH,
        )
        return guidance, applied.astype(np.float64)
