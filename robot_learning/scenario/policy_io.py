"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

from typing import Any

import numpy as np

from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation


OBSERVATION_SIZE = 11
ACTION_SIZE = 2
LAUNCH_CONTROL_STEPS = 20


def _validated_vector(
    value: Any, *, name: str, expected_size: int
) -> np.ndarray:
    try:
        vector = np.asarray(value, dtype=np.float64)
    except (OverflowError, TypeError, ValueError) as error:
        raise RuntimeError(
            f"branch launch policy I/O received an invalid {name}; "
            f"expected a finite one-dimensional vector with {expected_size} "
            "elements"
        ) from error
    if vector.ndim != 1 or vector.size != expected_size:
        raise RuntimeError(
            f"branch launch policy I/O received an invalid {name}; "
            f"expected a finite one-dimensional vector with {expected_size} "
            "elements"
        )
    if not np.all(np.isfinite(vector)):
        raise RuntimeError(
            f"branch launch policy I/O received non-finite values in {name}"
        )
    return vector


def physical_action(action):
    """Preserve the existing identity action mapping for direct callers."""
    return action


def make_policy_io():
    """Create the branch-aware adapter used by training and saved runtimes.

    The environment invokes ``reset`` before it has reset MuJoCo's data, so
    branch selection is completed by the first ``observe`` call after reset.
    The observation cache then supplies the same unnormalized observation to
    ``action`` immediately before the environment applies that action.
    """

    state = {
        "current_observation": None,
        "selected_branch": None,
        "control_step": 0,
    }

    def reset() -> None:
        state["current_observation"] = None
        state["selected_branch"] = None
        state["control_step"] = 0

    def observe(data) -> np.ndarray:
        observation = reach_observation(data)
        validated_observation = _validated_vector(
            observation,
            name="observation",
            expected_size=OBSERVATION_SIZE,
        )
        state["current_observation"] = validated_observation.copy()

        if state["selected_branch"] is None:
            open_error = float(np.linalg.norm(validated_observation[7:9]))
            folded_error = float(np.linalg.norm(validated_observation[9:11]))
            # <= makes the open branch deterministic on an exact tie.
            state["selected_branch"] = (
                "open" if open_error <= folded_error else "folded"
            )

        # Return the original observation so this adapter does not alter the
        # established 11-dimensional representation or its dtype.
        return observation

    def action(action_value) -> np.ndarray:
        policy_action = _validated_vector(
            action_value,
            name="policy action",
            expected_size=ACTION_SIZE,
        )
        current_observation = state["current_observation"]
        if current_observation is None or state["selected_branch"] is None:
            raise RuntimeError(
                "branch launch policy I/O received an action before the "
                "episode observation was established"
            )

        state["control_step"] += 1
        if state["control_step"] > LAUNCH_CONTROL_STEPS:
            return policy_action

        branch_error = (
            current_observation[7:9]
            if state["selected_branch"] == "open"
            else current_observation[9:11]
        )
        joint_velocity = current_observation[2:4]
        residual = np.tanh(
            0.75 * branch_error - 0.05 * joint_velocity
        )
        return np.clip(
            0.80 * policy_action + 0.20 * residual,
            -1.0,
            1.0,
        )

    return PolicyIO(observe=observe, action=action, reset=reset)
