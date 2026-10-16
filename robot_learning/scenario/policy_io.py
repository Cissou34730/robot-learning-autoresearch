"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import (
    JOINT_LIMIT_RADIANS,
    OBSERVATION_SIZE,
    reach_observation,
)


CONTROLLER_ACTIVATION_ID = "i6_acquisition_maintenance_v2"
ACQUISITION_TOLERANCE_METERS = 0.01
MAINTENANCE_POSITION_GAIN_ACTIONS_PER_RADIAN = 2.0
MAINTENANCE_VELOCITY_GAIN_SECONDS = 0.25
MAINTENANCE_ACTION_LIMIT = 1.0
RESET_ESCAPE_PHASE = "reset_escape"
ACQUISITION_PHASE = "acquisition"
MAINTENANCE_PHASE = "maintenance"
RESET_ESCAPE_MAX_STEPS = 12
RESET_ESCAPE_ELBOW_RADIANS = 0.45
RESET_ESCAPE_POSITION_GAIN_ACTIONS_PER_RADIAN = 2.5
RESET_ESCAPE_VELOCITY_GAIN_SECONDS = 0.35
RESET_ESCAPE_MIN_Q2_RADIANS = 0.18
ACQUISITION_POSITION_GAIN_ACTIONS_PER_RADIAN = 1.75
ACQUISITION_VELOCITY_GAIN_SECONDS = 0.30


def physical_action(action):
    return action


def _bounded_action(action) -> np.ndarray:
    """Return a finite two-joint action for the environment's clipped API."""
    try:
        candidate = np.asarray(action, dtype=np.float64)
    except (TypeError, ValueError):
        return np.zeros(2, dtype=np.float64)
    if candidate.shape not in ((2,), (1, 2)):
        return np.zeros(2, dtype=np.float64)
    candidate = candidate.reshape(2)
    if not np.isfinite(candidate).all():
        return np.zeros(2, dtype=np.float64)
    return np.clip(candidate, -MAINTENANCE_ACTION_LIMIT, MAINTENANCE_ACTION_LIMIT)


def _validated_controller_observation(observation) -> np.ndarray | None:
    """Return the ordinary observation only when it has the required shape."""
    try:
        candidate = np.asarray(observation, dtype=np.float64)
    except (TypeError, ValueError):
        return None
    if candidate.shape != (OBSERVATION_SIZE,) or not np.isfinite(candidate).all():
        return None
    return candidate


def _branch_targets_and_validity(
    observation: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Reconstruct the two observed IK targets and apply joint limits."""
    qpos = observation[0:2]
    branch_errors = observation[7:11].reshape(2, 2)
    branch_targets = (qpos[None, :] + branch_errors + np.pi) % (
        2.0 * np.pi
    ) - np.pi
    valid = np.isfinite(branch_targets).all(axis=1) & np.all(
        np.abs(branch_targets) <= JOINT_LIMIT_RADIANS, axis=1
    )
    return branch_targets, valid


def _nearest_valid_branch(
    observation: np.ndarray,
    *,
    preferred: int | None = None,
) -> int | None:
    """Choose one limit-compatible branch, retaining a valid latch if given."""
    branch_targets, valid = _branch_targets_and_validity(observation)
    if preferred is not None and 0 <= preferred < 2 and valid[preferred]:
        return preferred
    if not np.any(valid):
        return None

    branch_errors = observation[7:11].reshape(2, 2)
    distances = np.linalg.norm(branch_errors, axis=1)
    distances = np.where(valid, distances, np.inf)
    return int(np.argmin(distances))


def _branch_error(
    observation: np.ndarray,
    branch_index: int,
) -> np.ndarray | None:
    """Return the selected branch error after checking its finite shape."""
    if branch_index not in (0, 1):
        return None
    errors = observation[7:11].reshape(2, 2)
    error = errors[branch_index]
    if not np.isfinite(error).all():
        return None
    return error


def make_controller_policy_io() -> PolicyIO:
    """Build the stateful reset-escape, acquisition, and maintenance runtime.

    The controller only sees the ordinary eleven-entry observation.  It first
    bends the elbow away from the reset singularity, then drives a latched,
    joint-limit-compatible IK branch.  Once an observed endpoint enters the
    official tolerance band, it uses the established position/velocity
    maintenance law and returns to acquisition after an exit.
    """
    state = {
        "observation": None,
        "phase": RESET_ESCAPE_PHASE,
        "escape_steps": 0,
        "branch_index": None,
    }

    def observe(data):
        observation = np.asarray(reach_observation(data), dtype=np.float32)
        state["observation"] = observation.copy()
        return observation

    def reset():
        state["observation"] = None
        state["phase"] = RESET_ESCAPE_PHASE
        state["escape_steps"] = 0
        state["branch_index"] = None

    def action(learned_action):
        learned = _bounded_action(learned_action)
        observation = _validated_controller_observation(state["observation"])
        if observation is None:
            # A malformed observation cannot safely drive a feedback law.  Do
            # not retain a partially advanced phase across that fault.
            state["phase"] = RESET_ESCAPE_PHASE
            state["escape_steps"] = 0
            state["branch_index"] = None
            return learned

        endpoint_to_target = observation[4:7]
        endpoint_distance = float(np.linalg.norm(endpoint_to_target))
        if not np.isfinite(endpoint_distance):
            state["phase"] = RESET_ESCAPE_PHASE
            state["escape_steps"] = 0
            state["branch_index"] = None
            return learned

        qpos = observation[0:2]
        qvel = observation[2:4]
        phase = state["phase"]

        if phase == RESET_ESCAPE_PHASE:
            branch_index = _nearest_valid_branch(
                observation, preferred=state["branch_index"]
            )
            if branch_index is None:
                return learned
            state["branch_index"] = branch_index
            branch_targets, _ = _branch_targets_and_validity(observation)
            target = branch_targets[branch_index]

            # Use a bounded intermediate target rather than asking the policy
            # to act from q2=0.  The selected branch supplies the bend sign;
            # the shoulder error also starts moving toward that same branch.
            elbow_sign = float(np.sign(target[1]))
            if elbow_sign == 0.0:
                elbow_sign = float(np.sign(observation[7 + 2 * branch_index + 1]))
            if elbow_sign == 0.0:
                elbow_sign = 1.0
            escape_elbow_magnitude = min(
                max(abs(float(target[1])), RESET_ESCAPE_MIN_Q2_RADIANS),
                RESET_ESCAPE_ELBOW_RADIANS,
            )
            escape_target = np.asarray(
                [
                    qpos[0] + 0.35 * (target[0] - qpos[0]),
                    elbow_sign * escape_elbow_magnitude,
                ],
                dtype=np.float64,
            )
            escape_error = escape_target - qpos
            escape_action = (
                RESET_ESCAPE_POSITION_GAIN_ACTIONS_PER_RADIAN * escape_error
                - RESET_ESCAPE_VELOCITY_GAIN_SECONDS * qvel
            )
            state["escape_steps"] += 1
            if (
                state["escape_steps"] >= RESET_ESCAPE_MAX_STEPS
                or abs(float(qpos[1])) >= RESET_ESCAPE_MIN_Q2_RADIANS
            ):
                state["phase"] = ACQUISITION_PHASE
            return np.clip(
                escape_action,
                -MAINTENANCE_ACTION_LIMIT,
                MAINTENANCE_ACTION_LIMIT,
            ).astype(np.float64, copy=False)

        if phase not in (ACQUISITION_PHASE, MAINTENANCE_PHASE):
            state["phase"] = RESET_ESCAPE_PHASE
            state["escape_steps"] = 0
            state["branch_index"] = None
            return learned

        if endpoint_distance <= ACQUISITION_TOLERANCE_METERS:
            state["phase"] = MAINTENANCE_PHASE
        elif phase == MAINTENANCE_PHASE:
            # Preserve the v1 handoff: an exit immediately returns to the
            # branch-directed acquisition controller.
            state["phase"] = ACQUISITION_PHASE

        if state["phase"] == ACQUISITION_PHASE:
            branch_index = _nearest_valid_branch(
                observation, preferred=state["branch_index"]
            )
            if branch_index is None:
                return learned
            state["branch_index"] = branch_index
        else:
            # Maintenance retains v1's nearest-valid-IK selection rather than
            # allowing an invalid or stale latched branch to command the arm.
            branch_index = _nearest_valid_branch(observation)
            if branch_index is None:
                state["phase"] = ACQUISITION_PHASE
                state["branch_index"] = None
                return learned

        position_error = _branch_error(observation, branch_index)
        if position_error is None:
            state["phase"] = ACQUISITION_PHASE
            state["branch_index"] = None
            return learned
        if state["phase"] == ACQUISITION_PHASE:
            feedback_action = (
                ACQUISITION_POSITION_GAIN_ACTIONS_PER_RADIAN * position_error
                - ACQUISITION_VELOCITY_GAIN_SECONDS * qvel
            )
        else:
            feedback_action = (
                MAINTENANCE_POSITION_GAIN_ACTIONS_PER_RADIAN * position_error
                - MAINTENANCE_VELOCITY_GAIN_SECONDS * qvel
            )
        return np.clip(
            feedback_action,
            -MAINTENANCE_ACTION_LIMIT,
            MAINTENANCE_ACTION_LIMIT,
        ).astype(np.float64, copy=False)

    activation_attributes = {
        "controller_activation_id": CONTROLLER_ACTIVATION_ID,
        "controller_enabled": True,
        "controller_callable_path": True,
    }
    for callable_ in (observe, action, reset):
        callable_.__dict__.update(activation_attributes)
    policy_io = PolicyIO(observe=observe, action=action, reset=reset)
    # These attributes make activation explicit in newly created runtimes.
    # The callable copies above also survive PolicyRuntime's runtime restore,
    # which reconstructs a plain PolicyIO instance from the saved callables.
    policy_io.__dict__.update(activation_attributes)
    return policy_io


def make_policy_io(*, controller_enabled: bool = False) -> PolicyIO:
    """Return identity I/O by default, or the explicitly enabled I6 runtime."""
    if controller_enabled:
        return make_controller_policy_io()
    return PolicyIO(observe=reach_observation, action=physical_action)
