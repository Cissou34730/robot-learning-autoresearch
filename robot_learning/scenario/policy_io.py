"""Researcher-owned policy inputs and mapping to the robot's physical commands.

Use the same functions in training and export. Resolve scientific dependencies
before export (module-level imports or captured objects, not runtime imports).
"""

import numpy as np

from robot_learning.policy_runtime import PolicyIO
from robot_learning.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.observations import reach_observation

JOINT_LIMIT = np.deg2rad(170.0)
APPROACH_GAIN = np.array([1.35, 1.35], dtype=np.float64)
VELOCITY_DAMPING = np.array([0.12, 0.12], dtype=np.float64)
LEARNED_RESIDUAL_SCALE = 0.5
APPROACH_START_DISTANCE = 0.04
APPROACH_END_DISTANCE = 0.01


def _wrap_to_pi(angle: np.ndarray | float) -> np.ndarray | float:
    return (np.asarray(angle) + np.pi) % (2.0 * np.pi) - np.pi


def _ik_branches(target_x: float, target_y: float) -> tuple[np.ndarray, np.ndarray]:
    bearing = float(np.arctan2(target_y, target_x))
    radius_squared = target_x**2 + target_y**2
    cosine = (
        radius_squared - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    branches = []
    for elbow_angle in (elbow, -elbow):
        shoulder = bearing - np.arctan2(
            FOREARM_LENGTH * np.sin(elbow_angle),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow_angle),
        )
        branches.append(
            np.array([float(_wrap_to_pi(shoulder)), elbow_angle], dtype=np.float64)
        )
    return branches[0], branches[1]


def _select_ik_target(
    current_q: np.ndarray, target_x: float, target_y: float
) -> np.ndarray:
    branches = _ik_branches(target_x, target_y)
    feasible = [
        branch
        for branch in branches
        if np.all(np.abs(branch) <= JOINT_LIMIT + 1e-9)
    ]
    if not feasible:
        raise ValueError("the target has no feasible inverse-kinematic branch")
    return min(
        feasible,
        key=lambda branch: float(
            np.sum(np.square(_wrap_to_pi(branch - current_q)))
        ),
    ).copy()


def make_policy_io():
    context: dict[str, np.ndarray | float | None] = {
        "q": None,
        "qvel": None,
        "ik_target": None,
        "distance": None,
    }

    def observe(data):
        observation = reach_observation(data)
        current_q = np.asarray(data.qpos[:2], dtype=np.float64).copy()
        context["q"] = current_q
        context["qvel"] = np.asarray(data.qvel[:2], dtype=np.float64).copy()
        target = np.asarray(data.mocap_pos[0], dtype=np.float64)
        context["distance"] = float(
            np.linalg.norm(data.site("end_effector").xpos - target)
        )
        if context["ik_target"] is None:
            context["ik_target"] = _select_ik_target(
                current_q, float(target[0]), float(target[1])
            )
        return observation

    def residual_action(action):
        if (
            context["q"] is None
            or context["qvel"] is None
            or context["ik_target"] is None
            or context["distance"] is None
        ):
            raise RuntimeError("policy action requested before an observation")

        learned_action = np.asarray(action, dtype=np.float64)
        if learned_action.shape != (2,):
            raise ValueError(f"expected a two-joint action, got {learned_action.shape}")

        position_error = np.asarray(
            _wrap_to_pi(np.asarray(context["ik_target"]) - context["q"]),
            dtype=np.float64,
        )
        guidance = APPROACH_GAIN * position_error - VELOCITY_DAMPING * context["qvel"]
        blend = np.clip(
            (float(context["distance"]) - APPROACH_END_DISTANCE)
            / (APPROACH_START_DISTANCE - APPROACH_END_DISTANCE),
            0.0,
            1.0,
        )
        physical = blend * np.clip(guidance, -1.0, 1.0)
        physical += LEARNED_RESIDUAL_SCALE * learned_action
        return np.clip(physical, -1.0, 1.0).astype(np.float32)

    def reset():
        context["q"] = None
        context["qvel"] = None
        context["ik_target"] = None
        context["distance"] = None

    return PolicyIO(observe=observe, action=residual_action, reset=reset)
