"""Scenario-owned observation representation.

Generic training code never inspects this layout: it only sees the Gymnasium
observation space declared by the scenario environment.
"""

import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from robot_learning.scenario.model_based_control import select_ik_target

OBSERVATION_SIZE = 21
TRAJECTORY_DURATION_STEPS = 30


def reach_observation(data) -> np.ndarray:
    def wrap_to_pi(angle: float) -> float:
        return float((angle + np.pi) % (2.0 * np.pi) - np.pi)

    def shoulder_for_elbow(elbow: float) -> float:
        return float(
            np.arctan2(target_y, target_x)
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )

    target_x = float(data.mocap_pos[0][0])
    target_y = float(data.mocap_pos[0][1])
    cos_elbow = (
        target_x**2 + target_y**2 - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))
    shoulder_open = shoulder_for_elbow(elbow_open)
    elbow_folded = -elbow_open
    shoulder_folded = shoulder_for_elbow(elbow_folded)
    end_effector = data.site("end_effector").xpos.copy()
    return np.concatenate(
        [
            data.qpos,
            data.qvel,
            end_effector - data.mocap_pos[0],
            [
                wrap_to_pi(shoulder_open - float(data.qpos[0])),
                wrap_to_pi(elbow_open - float(data.qpos[1])),
                wrap_to_pi(shoulder_folded - float(data.qpos[0])),
                wrap_to_pi(elbow_folded - float(data.qpos[1])),
            ],
        ]
    ).astype(np.float32)


def phase_aware_observation(
    data,
    *,
    step_count: int = 0,
    held_steps: int = 0,
    hold_steps_required: int = 100,
    previous_action: np.ndarray | None = None,
) -> np.ndarray:
    """Add trajectory, phase and action-history context to the base state."""
    base = reach_observation(data)
    target_xy = np.asarray(data.mocap_pos[0][:2], dtype=np.float64)
    target_qpos = select_ik_target(target_xy)

    trajectory_progress = float(
        np.clip(step_count / TRAJECTORY_DURATION_STEPS, 0.0, 1.0)
    )
    smooth_progress = trajectory_progress**2 * (3.0 - 2.0 * trajectory_progress)
    desired_qpos = smooth_progress * target_qpos
    if 0 < trajectory_progress < 1:
        desired_qvel = (
            target_qpos
            * (6.0 * trajectory_progress - 6.0 * trajectory_progress**2)
            / TRAJECTORY_DURATION_STEPS
        )
    else:
        desired_qvel = np.zeros(2, dtype=np.float64)

    if hold_steps_required <= 0:
        raise ValueError("hold_steps_required must be positive")
    hold_progress = float(np.clip(held_steps / hold_steps_required, 0.0, 1.0))
    hold_active = float(held_steps > 0)
    phase = np.array(
        [
            float(not hold_active),
            hold_active,
            trajectory_progress,
            hold_progress,
        ],
        dtype=np.float64,
    )
    action_history = (
        np.zeros(2, dtype=np.float64)
        if previous_action is None
        else np.asarray(previous_action, dtype=np.float64)
    )
    return np.concatenate(
        [
            base,
            desired_qpos,
            desired_qvel,
            phase,
            np.clip(action_history, -1.0, 1.0),
        ]
    ).astype(np.float32)
