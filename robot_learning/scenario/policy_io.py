"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from contracts.policy_runtime import PolicyIO
from robot_learning.scenario.observations import reach_observation


JOINT_COUNT = 2
BRAKING_CAPTURE_DISTANCE_M = 0.05
BRAKING_SUCCESS_DISTANCE_M = 0.01
JOINT_DAMPING_GAIN = 0.2
MAX_DAMPING_CORRECTION = 0.25
MAX_DAMPING_VELOCITY_RAD_PER_S = MAX_DAMPING_CORRECTION / JOINT_DAMPING_GAIN


def physical_action(action):
    return action


def make_policy_io():
    state = {}

    def observe(data):
        observation = reach_observation(data)
        joint_positions = np.asarray(data.qpos, dtype=np.float64)
        joint_velocities = np.asarray(data.qvel, dtype=np.float64)
        endpoint_error = np.asarray(
            data.site("end_effector").xpos - data.mocap_pos[0],
            dtype=np.float64,
        )
        for name, value, shape in (
            ("joint positions", joint_positions, (JOINT_COUNT,)),
            ("joint velocities", joint_velocities, (JOINT_COUNT,)),
            ("endpoint error", endpoint_error, (3,)),
        ):
            if value.shape != shape or not np.all(np.isfinite(value)):
                raise RuntimeError(
                    f"Policy IO received invalid {name}: expected finite shape "
                    f"{shape}, got {value.shape}"
                )
        state["joint_positions"] = joint_positions.copy()
        state["joint_velocities"] = joint_velocities.copy()
        state["endpoint_error"] = endpoint_error.copy()
        return observation

    def action(policy_action):
        feed_forward = np.asarray(physical_action(policy_action), dtype=np.float64)
        if feed_forward.shape != (JOINT_COUNT,) or not np.all(
            np.isfinite(feed_forward)
        ):
            raise RuntimeError(
                "Policy IO received a non-finite or incorrectly shaped policy "
                f"action: expected {(JOINT_COUNT,)}, got {feed_forward.shape}"
            )
        if not state:
            raise RuntimeError(
                "Policy IO action requested before an observation captured "
                "the current joint state"
            )

        joint_velocities = state["joint_velocities"]
        endpoint_error = state["endpoint_error"]
        endpoint_distance = float(np.linalg.norm(endpoint_error))
        if not np.isfinite(endpoint_distance):
            raise RuntimeError("Policy IO received a non-finite endpoint distance")

        if endpoint_distance >= BRAKING_CAPTURE_DISTANCE_M:
            capture = 0.0
        elif endpoint_distance <= BRAKING_SUCCESS_DISTANCE_M:
            capture = 1.0
        else:
            normalized_distance = (
                BRAKING_CAPTURE_DISTANCE_M - endpoint_distance
            ) / (BRAKING_CAPTURE_DISTANCE_M - BRAKING_SUCCESS_DISTANCE_M)
            capture = normalized_distance**2 * (3.0 - 2.0 * normalized_distance)

        bounded_velocity = np.clip(
            joint_velocities,
            -MAX_DAMPING_VELOCITY_RAD_PER_S,
            MAX_DAMPING_VELOCITY_RAD_PER_S,
        )
        damping = np.clip(
            JOINT_DAMPING_GAIN * capture * bounded_velocity,
            -MAX_DAMPING_CORRECTION,
            MAX_DAMPING_CORRECTION,
        )
        correction = -damping
        if not np.all(np.isfinite(correction)):
            raise RuntimeError("Policy IO produced a non-finite damping correction")

        command = feed_forward + correction
        if command.shape != (JOINT_COUNT,) or not np.all(np.isfinite(command)):
            raise RuntimeError("Policy IO produced an invalid torque command")
        return command

    def reset():
        state.clear()

    return PolicyIO(observe=observe, action=action, reset=reset)
