"""Branch-aware inverse-kinematics guidance for the two-joint arm.

The controller is deliberately episode-scoped: :meth:`select_branch` is
called once after a target is sampled, and the selected inverse-kinematics
configuration is then latched until reset.  The learned action remains a
bounded residual rather than being replaced by this guidance.

After branch selection, control moves through an approach, braking, and hold
schedule.  The schedule is state-driven and one-way; it does not use the
environment's hold counter or episode step count.
"""

from dataclasses import dataclass

import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH

# Branch ranking is deterministic: proximity is minimized first in score form,
# with a smaller preference for configurations farther from their limits.
BRANCH_PROXIMITY_WEIGHT = 1.0
BRANCH_LIMIT_MARGIN_WEIGHT = 0.10

ACTION_LOW = -1.0
ACTION_HIGH = 1.0
IK_REACHABILITY_EPSILON = 1e-10

APPROACH_PHASE = "approach"
BRAKING_PHASE = "braking"
HOLD_PHASE = "hold"

# The phase boundaries use both Cartesian target geometry and the latched
# joint-space target.  They are deliberately margins around the 1 cm task
# boundary rather than the task success counter.
CLOSE_APPROACH_DISTANCE_M = 0.025
CLOSE_APPROACH_ERROR_RAD = 0.35
BRAKING_INWARD_SPEED_RAD_S = 1.5
HOLD_ENTRY_DISTANCE_FRACTION = 0.80
HOLD_ENTRY_ERROR_RAD = 0.12
HOLD_ENTRY_SPEED_RAD_S = 0.35

# Each phase has its own finite-time control schedule.  The hold schedule
# retains enough proportional guidance to recover from a small interruption,
# while its stronger velocity damping and small residual weight prevent a
# learned command from undoing the branch target.
PHASE_PARAMETERS = {
    APPROACH_PHASE: {
        "proportional_gain": 1.0,
        "velocity_damping": 0.10,
        "guidance_weight": 1.0,
        "residual_weight": 0.35,
    },
    BRAKING_PHASE: {
        "proportional_gain": 0.80,
        "velocity_damping": 0.45,
        "guidance_weight": 1.0,
        "residual_weight": 0.12,
    },
    HOLD_PHASE: {
        "proportional_gain": 0.45,
        "velocity_damping": 0.90,
        "guidance_weight": 0.85,
        "residual_weight": 0.05,
    },
}


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
    """Latch a feasible planar IK branch and provide scheduled guidance."""

    def __init__(self, model, *, success_threshold: float = 0.01) -> None:
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
        self._phase = APPROACH_PHASE
        try:
            threshold = float(success_threshold)
        except (TypeError, ValueError):
            threshold = 0.01
        self._success_threshold = (
            threshold if np.isfinite(threshold) and threshold > 0.0 else 0.01
        )

    def _joint_state(self, data) -> tuple[np.ndarray, np.ndarray]:
        try:
            qpos = np.asarray(
                data.qpos[list(self._qpos_indices)], dtype=np.float64
            )
            qvel = np.asarray(
                data.qvel[list(self._qvel_indices)], dtype=np.float64
            )
        except (AttributeError, IndexError, TypeError, ValueError):
            return np.zeros(2, dtype=np.float64), np.zeros(2, dtype=np.float64)
        if qpos.shape != (2,) or qvel.shape != (2,):
            return np.zeros(2, dtype=np.float64), np.zeros(2, dtype=np.float64)
        qpos = np.nan_to_num(qpos, nan=0.0, posinf=0.0, neginf=0.0)
        qvel = np.nan_to_num(qvel, nan=0.0, posinf=0.0, neginf=0.0)
        return qpos, qvel

    @staticmethod
    def _policy_vector(policy_action) -> np.ndarray:
        try:
            policy = np.asarray(policy_action, dtype=np.float64)
        except (TypeError, ValueError):
            return np.zeros(2, dtype=np.float64)
        if policy.size != 2:
            return np.zeros(2, dtype=np.float64)
        policy = policy.reshape(2)
        return np.nan_to_num(
            policy, nan=0.0, posinf=ACTION_HIGH, neginf=ACTION_LOW
        )

    def _target_distance(self, data) -> float:
        try:
            target = np.asarray(data.mocap_pos[0][:2], dtype=np.float64)
            qpos = np.asarray(
                data.qpos[list(self._qpos_indices)], dtype=np.float64
            )
        except (AttributeError, IndexError, TypeError, ValueError):
            return float("inf")
        if target.shape != (2,) or qpos.shape != (2,):
            return float("inf")
        if not (np.all(np.isfinite(target)) and np.all(np.isfinite(qpos))):
            return float("inf")
        site = np.asarray(
            [
                UPPER_ARM_LENGTH * np.cos(qpos[0])
                + FOREARM_LENGTH * np.cos(qpos[0] + qpos[1]),
                UPPER_ARM_LENGTH * np.sin(qpos[0])
                + FOREARM_LENGTH * np.sin(qpos[0] + qpos[1]),
            ],
            dtype=np.float64,
        )
        return float(np.linalg.norm(site - target))

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
        if target.shape != (2,) or not np.all(np.isfinite(target)):
            return ()
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
            self._phase = APPROACH_PHASE
            raise ValueError(
                "no feasible planar IK branch satisfies the declared joint limits"
            )

        chosen = min(
            feasible,
            key=lambda branch: (branch.score, branch.proximity_cost, branch.name),
        )
        self.selected_branch = chosen.name
        self.selected_target = chosen.target.copy()
        self._phase = APPROACH_PHASE

    def guidance_action(self, data) -> np.ndarray:
        """Compute scheduled, bounded guidance toward the latched target."""
        if self.selected_target is None:
            raise RuntimeError("branch-aware guidance requested before branch selection")
        qpos, qvel = self._joint_state(data)
        angle_error = _wrap_to_pi(self.selected_target - qpos)
        error_norm = float(np.linalg.norm(angle_error))
        speed_norm = float(np.linalg.norm(qvel))
        inward_speed = (
            float(np.dot(qvel, angle_error) / error_norm)
            if error_norm > np.finfo(np.float64).eps
            else 0.0
        )
        target_distance = self._target_distance(data)

        if self._phase == APPROACH_PHASE:
            close_approach = (
                target_distance <= CLOSE_APPROACH_DISTANCE_M
                and error_norm <= CLOSE_APPROACH_ERROR_RAD
            )
            excessive_inward_speed = (
                inward_speed >= BRAKING_INWARD_SPEED_RAD_S
            )
            if close_approach or excessive_inward_speed:
                self._phase = BRAKING_PHASE
        if self._phase == BRAKING_PHASE:
            hold_distance = (
                HOLD_ENTRY_DISTANCE_FRACTION * self._success_threshold
            )
            if (
                target_distance <= hold_distance
                and error_norm <= HOLD_ENTRY_ERROR_RAD
                and speed_norm <= HOLD_ENTRY_SPEED_RAD_S
            ):
                self._phase = HOLD_PHASE

        parameters = PHASE_PARAMETERS[self._phase]
        guidance = (
            parameters["proportional_gain"] * angle_error
            - parameters["velocity_damping"] * qvel
        )
        guidance = np.nan_to_num(
            guidance, nan=0.0, posinf=ACTION_HIGH, neginf=ACTION_LOW
        )
        return np.clip(guidance, ACTION_LOW, ACTION_HIGH).astype(np.float64)

    def diagnostics(self, data) -> dict[str, float | str | bool]:
        """Return state-driven phase diagnostics for the current control state."""
        qpos, qvel = self._joint_state(data)
        if self.selected_target is None:
            angle_error = np.zeros(2, dtype=np.float64)
        else:
            angle_error = _wrap_to_pi(self.selected_target - qpos)
        error_norm = float(np.linalg.norm(angle_error))
        speed_norm = float(np.linalg.norm(qvel))
        inward_speed = (
            float(np.dot(qvel, angle_error) / error_norm)
            if error_norm > np.finfo(np.float64).eps
            else 0.0
        )
        parameters = PHASE_PARAMETERS[self._phase]
        return {
            "control_phase": self._phase,
            # Braking remains active in hold because hold is the conservative
            # post-braking schedule, while `braking_phase` identifies the
            # transitional phase itself.
            "braking_active": self._phase in (BRAKING_PHASE, HOLD_PHASE),
            "braking_phase": self._phase == BRAKING_PHASE,
            "guidance_weight": float(parameters["guidance_weight"]),
            "residual_weight": float(parameters["residual_weight"]),
            "joint_error_norm_rad": error_norm,
            "joint_speed_norm_rad_s": speed_norm,
            "inward_joint_speed_rad_s": inward_speed,
            "target_distance_m": self._target_distance(data),
        }

    def apply(self, policy_action, data) -> tuple[np.ndarray, np.ndarray]:
        """Blend the scheduled guidance with a bounded policy residual."""
        policy = np.clip(
            self._policy_vector(policy_action), ACTION_LOW, ACTION_HIGH
        )
        guidance = self.guidance_action(data)
        parameters = PHASE_PARAMETERS[self._phase]
        applied = np.clip(
            parameters["guidance_weight"] * guidance
            + parameters["residual_weight"] * policy,
            ACTION_LOW,
            ACTION_HIGH,
        )
        return guidance, applied.astype(np.float64)
