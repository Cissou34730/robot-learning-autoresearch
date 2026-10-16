"""Branch-conditioned task-space guidance for the two-joint arm.

The controller chooses one feasible inverse-kinematics branch at reset, but
does not use that configuration as a joint-space servo target.  During the
episode it measures the live MuJoCo end-effector position and site Jacobian,
commands a bounded Cartesian velocity, and maps that velocity through a
damped least-squares Jacobian inverse.  The selected branch is only a
null-space preference, which keeps the task-space command distinct from the
previous latched proportional joint controller.

The returned values are direct motor commands.  They are finite and smoothly
norm-limited below the physical action-space boundary; a distant target
therefore increases the bounded Cartesian request rather than intentionally
producing a full-scale action.
"""

from dataclasses import dataclass

import mujoco
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

# Cartesian phase limits are finite physical command bounds, in SI units.
# The final motor-command limits are deliberately below [-1, 1], so a large
# Cartesian error is handled by a bounded velocity request, not saturation.
CARTESIAN_APPROACH_SPEED_M_S = 0.24
CARTESIAN_BRAKING_SPEED_M_S = 0.085
CARTESIAN_HOLD_SPEED_M_S = 0.035
GUIDANCE_ACTION_NORM_LIMIT = 0.78
RESIDUAL_ACTION_NORM_LIMIT = 0.32
APPLIED_ACTION_NORM_LIMIT = 0.90

# Phase transitions use the actual Cartesian velocity at the site.  The hold
# envelope is stricter than the task's 1 cm boundary to leave settling margin.
BRAKING_DISTANCE_M = 0.035
BRAKING_INWARD_SPEED_M_S = 0.18
HOLD_ENTRY_DISTANCE_FRACTION = 0.80
HOLD_ENTRY_SPEED_M_S = 0.035
HOLD_EXIT_SPEED_M_S = 0.12
HOLD_EXIT_DISTANCE_FRACTION = 1.20

# Damped least squares remains well-defined at the fully extended reset pose.
TASK_JACOBIAN_DAMPING = 0.012
NULL_SPACE_GAIN_S = 1.25
JOINT_VELOCITY_LIMIT_RAD_S = 4.0

# These gains act on Cartesian position and velocity, not on joint angles.
PHASE_PARAMETERS = {
    APPROACH_PHASE: {
        "position_gain_s": 3.2,
        "velocity_damping_s": 0.35,
        "guidance_weight": 0.88,
        "residual_weight": 0.18,
        "cartesian_speed_limit": CARTESIAN_APPROACH_SPEED_M_S,
    },
    BRAKING_PHASE: {
        "position_gain_s": 3.0,
        "velocity_damping_s": 1.35,
        "guidance_weight": 0.94,
        "residual_weight": 0.08,
        "cartesian_speed_limit": CARTESIAN_BRAKING_SPEED_M_S,
    },
    HOLD_PHASE: {
        "position_gain_s": 2.4,
        "velocity_damping_s": 1.80,
        "guidance_weight": 0.82,
        "residual_weight": 0.04,
        "cartesian_speed_limit": CARTESIAN_HOLD_SPEED_M_S,
    },
}


def _wrap_to_pi(angle):
    """Return an angle error in the half-open interval [-pi, pi)."""
    return (np.asarray(angle) + np.pi) % (2.0 * np.pi) - np.pi


def _smooth_norm_limit(vector, limit: float) -> np.ndarray:
    """Limit a finite vector smoothly, without component-wise saturation."""
    try:
        value = np.asarray(vector, dtype=np.float64)
    except (TypeError, ValueError):
        return np.zeros(2, dtype=np.float64)
    if value.shape != (2,) or not np.all(np.isfinite(value)):
        return np.zeros(2, dtype=np.float64)
    if not np.isfinite(limit) or limit <= 0.0:
        return np.zeros(2, dtype=np.float64)
    norm = float(np.linalg.norm(value))
    if norm <= np.finfo(np.float64).eps:
        return value.copy()
    ratio = norm / float(limit)
    return value * (np.tanh(ratio) / ratio)


@dataclass(frozen=True)
class FeasibleBranch:
    """A joint-space IK solution that satisfies the model's joint limits."""

    name: str
    target: np.ndarray
    proximity_cost: float
    limit_margin: float
    score: float


class BranchAwareController:
    """Use a feasible IK branch as a null-space preference for task control."""

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
        try:
            self._site_id = int(
                mujoco.mj_name2id(
                    model, mujoco.mjtObj.mjOBJ_SITE, "end_effector"
                )
            )
        except (AttributeError, TypeError, ValueError):
            self._site_id = -1
        if self._site_id < 0:
            raise ValueError("branch-aware control requires an end_effector site")
        # Derived MuJoCo fields on the environment's live data are intentionally
        # not refreshed here.  The environment evaluates task distance from
        # that data after diagnostics, so changing it would change task
        # semantics.  This private copy lets diagnostics and control derive
        # kinematics from the current qpos without mutating live task state.
        self._kinematic_data = mujoco.MjData(model)

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
        self._last_guidance = np.zeros(2, dtype=np.float64)
        self._last_residual = np.zeros(2, dtype=np.float64)
        self._last_applied = np.zeros(2, dtype=np.float64)

    def _joint_state(
        self, data
    ) -> tuple[np.ndarray, np.ndarray, bool]:
        """Read the two arm joints and explicitly reject malformed state."""
        try:
            qpos = np.asarray(
                data.qpos[list(self._qpos_indices)], dtype=np.float64
            )
            qvel = np.asarray(
                data.qvel[list(self._qvel_indices)], dtype=np.float64
            )
        except (AttributeError, IndexError, TypeError, ValueError):
            return (
                np.zeros(2, dtype=np.float64),
                np.zeros(2, dtype=np.float64),
                False,
            )
        if (
            qpos.shape != (2,)
            or qvel.shape != (2,)
            or not np.all(np.isfinite(qpos))
            or not np.all(np.isfinite(qvel))
        ):
            return (
                np.zeros(2, dtype=np.float64),
                np.zeros(2, dtype=np.float64),
                False,
            )
        return qpos, qvel, True

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

    def _task_state(self, data) -> dict:
        """Return live planar task state, or a finite invalid-state record."""
        invalid = {
            "valid": False,
            "qpos": np.zeros(2, dtype=np.float64),
            "qvel": np.zeros(2, dtype=np.float64),
            "target": np.zeros(2, dtype=np.float64),
            "site": np.zeros(2, dtype=np.float64),
            "error": np.zeros(2, dtype=np.float64),
            "jacobian": np.zeros((2, 2), dtype=np.float64),
            "site_velocity": np.zeros(2, dtype=np.float64),
            "distance": None,
        }
        qpos, qvel, state_valid = self._joint_state(data)
        if not state_valid:
            return invalid
        try:
            full_qpos = np.asarray(data.qpos, dtype=np.float64)
            full_qvel = np.asarray(data.qvel, dtype=np.float64)
            full_mocap_pos = np.asarray(data.mocap_pos, dtype=np.float64)
            if (
                full_qpos.shape != self._kinematic_data.qpos.shape
                or full_qvel.shape != self._kinematic_data.qvel.shape
                or full_mocap_pos.shape
                != self._kinematic_data.mocap_pos.shape
                or not np.all(np.isfinite(full_qpos))
                or not np.all(np.isfinite(full_qvel))
                or not np.all(np.isfinite(full_mocap_pos))
            ):
                return invalid
            target_3d = full_mocap_pos[0]
            if target_3d.shape != (3,) or not np.all(np.isfinite(target_3d)):
                return invalid

            # Copy only state needed to derive kinematics.  In particular,
            # mj_forward must never run on the environment's live MjData.
            self._kinematic_data.qpos[:] = full_qpos
            self._kinematic_data.qvel[:] = full_qvel
            self._kinematic_data.mocap_pos[:] = full_mocap_pos
            mujoco.mj_forward(self.model, self._kinematic_data)
            site_3d = np.asarray(
                self._kinematic_data.site(self._site_id).xpos,
                dtype=np.float64,
            )
            jacobian_3d = np.zeros(
                (3, int(self.model.nv)), dtype=np.float64
            )
            mujoco.mj_jacSite(
                self.model,
                self._kinematic_data,
                jacobian_3d,
                None,
                self._site_id,
            )
            jacobian = jacobian_3d[
                :2, list(self._qvel_indices)
            ]
            site = site_3d[:2]
            target = target_3d[:2]
            if (
                site_3d.shape != (3,)
                or jacobian.shape != (2, 2)
                or not np.all(np.isfinite(site_3d))
                or not np.all(np.isfinite(jacobian))
            ):
                return invalid
            error = target - site
            site_velocity = jacobian @ qvel
            if not (
                np.all(np.isfinite(error))
                and np.all(np.isfinite(site_velocity))
            ):
                return invalid
            distance = float(np.linalg.norm(error))
            if not np.isfinite(distance):
                return invalid
        except (
            AttributeError,
            IndexError,
            TypeError,
            ValueError,
            FloatingPointError,
            RuntimeError,
        ):
            return invalid
        return {
            "valid": True,
            "qpos": qpos,
            "qvel": qvel,
            "target": target,
            "site": site,
            "error": error,
            "jacobian": jacobian,
            "site_velocity": site_velocity,
            "distance": distance,
        }

    def _target_distance(self, data) -> float:
        state = self._task_state(data)
        return (
            float(state["distance"])
            if state["valid"]
            else float("inf")
        )

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
        try:
            target_3d = np.asarray(data.mocap_pos[0], dtype=np.float64)
            target = (
                target_3d[:2]
                if target_3d.shape == (3,)
                else np.zeros(2, dtype=np.float64)
            )
        except (AttributeError, IndexError, TypeError, ValueError):
            target = np.zeros(3, dtype=np.float64)[:2]
        current, _, current_valid = self._joint_state(data)
        if target.shape != (2,) or not np.all(np.isfinite(target)):
            current_valid = False
        feasible: list[FeasibleBranch] = []
        if current_valid:
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
        self._last_guidance.fill(0.0)
        self._last_residual.fill(0.0)
        self._last_applied.fill(0.0)

    def _branch_error(self, qpos: np.ndarray) -> np.ndarray:
        if self.selected_target is None:
            return np.zeros(2, dtype=np.float64)
        return _wrap_to_pi(self.selected_target - qpos).astype(np.float64)

    def _update_phase(self, state: dict) -> None:
        if not state["valid"]:
            return
        distance = float(state["distance"])
        error = state["error"]
        site_velocity = state["site_velocity"]
        speed = float(np.linalg.norm(site_velocity))
        inward_speed = (
            float(np.dot(site_velocity, error) / distance)
            if distance > np.finfo(np.float64).eps
            else 0.0
        )
        branch_error_norm = float(
            np.linalg.norm(self._branch_error(state["qpos"]))
        )
        if self._phase == APPROACH_PHASE and (
            distance <= BRAKING_DISTANCE_M
            or inward_speed >= BRAKING_INWARD_SPEED_M_S
        ):
            self._phase = BRAKING_PHASE
        if self._phase == BRAKING_PHASE:
            hold_distance = (
                HOLD_ENTRY_DISTANCE_FRACTION * self._success_threshold
            )
            if (
                distance <= hold_distance
                and speed <= HOLD_ENTRY_SPEED_M_S
                and branch_error_norm <= 0.45
            ):
                self._phase = HOLD_PHASE
        elif self._phase == HOLD_PHASE and (
            distance
            > HOLD_EXIT_DISTANCE_FRACTION * self._success_threshold
            or speed > HOLD_EXIT_SPEED_M_S
        ):
            self._phase = BRAKING_PHASE

    def _task_velocity_command(self, state: dict) -> np.ndarray:
        parameters = PHASE_PARAMETERS[self._phase]
        raw_command = (
            parameters["position_gain_s"] * state["error"]
            - parameters["velocity_damping_s"] * state["site_velocity"]
        )
        return _smooth_norm_limit(
            raw_command, parameters["cartesian_speed_limit"]
        )

    def guidance_action(self, data) -> np.ndarray:
        """Map bounded Cartesian approach/braking guidance to motor commands."""
        if self.selected_target is None:
            raise RuntimeError("branch-aware guidance requested before branch selection")
        state = self._task_state(data)
        if not state["valid"]:
            # A malformed state must not turn into a NaN or an accidental
            # saturation; the explicit safe command is zero until recovery.
            self._last_guidance.fill(0.0)
            return self._last_guidance.copy()

        self._update_phase(state)
        desired_velocity = self._task_velocity_command(state)
        jacobian = state["jacobian"]
        damping_matrix = (
            jacobian @ jacobian.T
            + TASK_JACOBIAN_DAMPING**2 * np.eye(2, dtype=np.float64)
        )
        try:
            task_inverse = jacobian.T @ np.linalg.solve(
                damping_matrix, np.eye(2, dtype=np.float64)
            )
            qdot_task = task_inverse @ desired_velocity
            null_projector = np.eye(2, dtype=np.float64) - task_inverse @ jacobian
            qdot_null = NULL_SPACE_GAIN_S * (
                null_projector @ self._branch_error(state["qpos"])
            )
            qdot_command = _smooth_norm_limit(
                qdot_task + qdot_null, JOINT_VELOCITY_LIMIT_RAD_S
            )
            # Direct motor control is treated as a bounded velocity-error
            # guidance signal; it is not a position-servo replacement.
            raw_guidance = 0.55 * (qdot_command - state["qvel"])
            guidance = _smooth_norm_limit(
                raw_guidance, GUIDANCE_ACTION_NORM_LIMIT
            )
        except (
            FloatingPointError,
            np.linalg.LinAlgError,
            ValueError,
            TypeError,
        ):
            guidance = np.zeros(2, dtype=np.float64)
        self._last_guidance = guidance
        return guidance.copy()

    def diagnostics(self, data) -> dict:
        """Return synchronized live task diagnostics and last commands."""
        state = self._task_state(data)
        if state["valid"]:
            joint_error = self._branch_error(state["qpos"])
            joint_speed = float(np.linalg.norm(state["qvel"]))
            cartesian_error = state["error"]
            cartesian_speed = state["site_velocity"]
            distance = float(state["distance"])
            inward_speed = (
                float(
                    np.dot(cartesian_speed, cartesian_error)
                    / distance
                )
                if distance > np.finfo(np.float64).eps
                else 0.0
            )
            inward_joint_speed = (
                float(
                    np.dot(state["qvel"], joint_error)
                    / np.linalg.norm(joint_error)
                )
                if np.linalg.norm(joint_error)
                > np.finfo(np.float64).eps
                else 0.0
            )
            try:
                condition = float(np.linalg.cond(state["jacobian"]))
                jacobian_condition = (
                    condition if np.isfinite(condition) else None
                )
            except (FloatingPointError, np.linalg.LinAlgError, ValueError):
                jacobian_condition = float("inf")
        else:
            joint_error = np.zeros(2, dtype=np.float64)
            joint_speed = 0.0
            cartesian_error = np.zeros(2, dtype=np.float64)
            cartesian_speed = np.zeros(2, dtype=np.float64)
            distance = None
            inward_speed = 0.0
            inward_joint_speed = 0.0
            jacobian_condition = None
        parameters = PHASE_PARAMETERS[self._phase]
        return {
            "control_phase": self._phase,
            "braking_active": self._phase in (BRAKING_PHASE, HOLD_PHASE),
            "braking_phase": self._phase == BRAKING_PHASE,
            "guidance_weight": float(parameters["guidance_weight"]),
            "residual_weight": float(parameters["residual_weight"]),
            "joint_error_norm_rad": float(np.linalg.norm(joint_error)),
            "joint_speed_norm_rad_s": joint_speed,
            "inward_joint_speed_rad_s": inward_joint_speed,
            "target_distance_m": distance,
            "cartesian_error_m": [float(value) for value in cartesian_error],
            "cartesian_error_norm_m": float(np.linalg.norm(cartesian_error)),
            "cartesian_speed_m_s": [float(value) for value in cartesian_speed],
            "cartesian_speed_norm_m_s": float(np.linalg.norm(cartesian_speed)),
            "inward_cartesian_speed_m_s": inward_speed,
            "planar_jacobian": (
                state["jacobian"].tolist()
                if state["valid"]
                else [[0.0, 0.0], [0.0, 0.0]]
            ),
            "jacobian_condition": jacobian_condition,
            "controller_state_valid": bool(state["valid"]),
            "guidance_action": [
                float(value) for value in self._last_guidance
            ],
            "residual_action": [
                float(value) for value in self._last_residual
            ],
            "applied_action": [
                float(value) for value in self._last_applied
            ],
        }

    def apply(self, policy_action, data) -> tuple[np.ndarray, np.ndarray]:
        """Blend the learned residual with smoothly bounded task guidance."""
        policy = np.clip(
            self._policy_vector(policy_action), ACTION_LOW, ACTION_HIGH
        )
        residual = _smooth_norm_limit(policy, RESIDUAL_ACTION_NORM_LIMIT)
        guidance = self.guidance_action(data)
        parameters = PHASE_PARAMETERS[self._phase]
        weighted_guidance = parameters["guidance_weight"] * guidance
        weighted_residual = parameters["residual_weight"] * residual
        applied = _smooth_norm_limit(
            weighted_guidance + weighted_residual,
            APPLIED_ACTION_NORM_LIMIT,
        )
        self._last_residual = residual
        self._last_applied = applied
        return guidance.copy(), applied.copy()
