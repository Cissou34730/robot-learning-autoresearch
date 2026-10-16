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


CONTROLLER_ACTIVATION_ID = "i5_acquisition_maintenance_v1"
ACQUISITION_TOLERANCE_METERS = 0.01
MAINTENANCE_POSITION_GAIN_ACTIONS_PER_RADIAN = 2.0
MAINTENANCE_VELOCITY_GAIN_SECONDS = 0.25
MAINTENANCE_ACTION_LIMIT = 1.0


def physical_action(action):
    return action


def _bounded_action(action) -> np.ndarray:
    """Return a finite two-joint action for the environment's clipped API."""
    try:
        candidate = np.asarray(action, dtype=np.float64)
    except (TypeError, ValueError):
        return np.zeros(2, dtype=np.float64)
    if candidate.size != 2:
        return np.zeros(2, dtype=np.float64)
    candidate = candidate.reshape(2)
    if not np.isfinite(candidate).all():
        return np.zeros(2, dtype=np.float64)
    return np.clip(candidate, -MAINTENANCE_ACTION_LIMIT, MAINTENANCE_ACTION_LIMIT)


def make_controller_policy_io() -> PolicyIO:
    """Build the stateful acquisition-to-maintenance runtime used by I5.

    The controller only sees the ordinary eleven-entry observation.  It takes
    over after an observed endpoint enters the official tolerance band and
    gives control back to the learned policy when a later observation leaves
    that band.
    """
    state = {"observation": None, "in_maintenance": False}

    def observe(data):
        observation = np.asarray(reach_observation(data), dtype=np.float32)
        state["observation"] = observation.copy()
        return observation

    def reset():
        state["observation"] = None
        state["in_maintenance"] = False

    def action(learned_action):
        learned = _bounded_action(learned_action)
        observation = state["observation"]
        if observation is None:
            return learned
        try:
            observation = np.asarray(observation, dtype=np.float64)
        except (TypeError, ValueError):
            state["in_maintenance"] = False
            return learned
        if observation.shape != (OBSERVATION_SIZE,) or not np.isfinite(
            observation
        ).all():
            state["in_maintenance"] = False
            return learned

        endpoint_to_target = observation[4:7]
        endpoint_distance = float(np.linalg.norm(endpoint_to_target))
        if not np.isfinite(endpoint_distance):
            state["in_maintenance"] = False
            return learned
        if endpoint_distance > ACQUISITION_TOLERANCE_METERS:
            state["in_maintenance"] = False
            return learned
        state["in_maintenance"] = True

        qpos = observation[0:2]
        qvel = observation[2:4]
        branch_errors = observation[7:11].reshape(2, 2)
        # The existing branch errors encode q_target - q.  Reconstruct each
        # candidate target, wrap it to the joint-angle convention, and reject
        # branches outside the robot's joint limits before choosing the nearest
        # feasible one.
        branch_targets = (qpos[None, :] + branch_errors + np.pi) % (
            2.0 * np.pi
        ) - np.pi
        valid = np.all(
            np.abs(branch_targets) <= JOINT_LIMIT_RADIANS, axis=1
        )
        if not np.any(valid):
            state["in_maintenance"] = False
            return learned
        branch_distances = np.linalg.norm(branch_errors, axis=1)
        branch_distances = np.where(valid, branch_distances, np.inf)
        branch_index = int(np.argmin(branch_distances))
        position_error = branch_errors[branch_index]
        maintenance_action = (
            MAINTENANCE_POSITION_GAIN_ACTIONS_PER_RADIAN * position_error
            - MAINTENANCE_VELOCITY_GAIN_SECONDS * qvel
        )
        return np.clip(
            maintenance_action,
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
    """Return identity I/O by default, or the explicitly enabled I5 runtime."""
    if controller_enabled:
        return make_controller_policy_io()
    return PolicyIO(observe=reach_observation, action=physical_action)
