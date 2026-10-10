"""Target-conditioned anticipatory braking for the arm."""

import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from contracts.task_spec import SUCCESS_THRESHOLD

JOINT_LIMIT = np.deg2rad(170.0)
TRAJECTORY_DURATION_STEPS = 20
REFERENCE_BLEND = 0.45
LIMIT_BRAKE_BLEND = 0.35
POSITION_GAIN = np.array([1.4, 1.0], dtype=np.float64)
VELOCITY_GAIN = np.array([0.12, 0.08], dtype=np.float64)
LIMIT_MARGIN = np.deg2rad(8.0)
TARGET_LIMIT_MARGIN = np.deg2rad(18.0)
LIMIT_POSITION_GAIN = 4.0
LIMIT_VELOCITY_GAIN = 0.25
ACQUISITION_DISTANCE = 0.025
ACQUISITION_BLEND = 0.25
HOLD_BLEND = 0.08
NEAR_LIMIT_POSITION_GAIN = np.array([1.0, 0.7], dtype=np.float64)
NEAR_LIMIT_VELOCITY_GAIN = np.array([0.10, 0.08], dtype=np.float64)
ANTICIPATORY_DISTANCE = 0.08
ANTICIPATORY_TARGET_MARGIN = np.deg2rad(30.0)
ANTICIPATORY_LOOKAHEAD_SECONDS = 0.12
ANTICIPATORY_BRAKING_ACCELERATION = 4.0
ANTICIPATORY_POSITION_GAIN = np.array([1.0, 0.7], dtype=np.float64)
ANTICIPATORY_VELOCITY_GAIN = np.array([0.20, 0.16], dtype=np.float64)
BRANCH_SWITCH_HYSTERESIS = np.deg2rad(6.0)
LIMIT_FORCE_FEEDBACK_GAIN = 0.8
ACTUATOR_FORCE_SCALE = 5.0
TRANSITION_DISTANCE = 0.04
HOLD_EXIT_DISTANCE = 0.015
STATE_HOLD_BLEND = 0.5


def wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def branch_joint_targets(target_position: np.ndarray) -> np.ndarray:
    target_x, target_y = (float(value) for value in target_position[:2])
    radius_squared = target_x**2 + target_y**2
    cosine_elbow = (
        radius_squared - UPPER_ARM_LENGTH**2 - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow_open = float(np.arccos(np.clip(cosine_elbow, -1.0, 1.0)))

    def shoulder_for_elbow(elbow: float) -> float:
        return wrap_to_pi(
            np.arctan2(target_y, target_x)
            - np.arctan2(
                FOREARM_LENGTH * np.sin(elbow),
                UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
            )
        )

    return np.asarray(
        [
            [shoulder_for_elbow(elbow_open), elbow_open],
            [shoulder_for_elbow(-elbow_open), -elbow_open],
        ],
        dtype=np.float64,
    )


def branch_errors(data) -> np.ndarray:
    targets = branch_joint_targets(np.asarray(data.mocap_pos[0]))
    return np.asarray(
        [
            wrap_to_pi(float(targets[0, 0] - data.qpos[0])),
            wrap_to_pi(float(targets[0, 1] - data.qpos[1])),
            wrap_to_pi(float(targets[1, 0] - data.qpos[0])),
            wrap_to_pi(float(targets[1, 1] - data.qpos[1])),
        ],
        dtype=np.float32,
    )


def select_branch_target(target_position: np.ndarray) -> np.ndarray:
    candidates = branch_joint_targets(target_position)
    margins = JOINT_LIMIT - np.max(np.abs(candidates), axis=1)
    valid = margins >= 0.0
    if np.any(valid):
        return candidates[int(np.argmax(np.where(valid, margins, -np.inf)))].copy()
    return candidates[int(np.argmax(margins))].copy()


def _branch_score(
    candidates: np.ndarray, qpos: np.ndarray, margins: np.ndarray
) -> np.ndarray:
    position_error = np.asarray(
        [
            [
                wrap_to_pi(float(candidate[index] - qpos[index]))
                for index in range(2)
            ]
            for candidate in candidates
        ],
        dtype=np.float64,
    )
    shoulder_margin = JOINT_LIMIT - np.abs(candidates[:, 0])
    return (
        -np.linalg.norm(position_error, axis=1)
        + 0.25 * shoulder_margin
        + 0.05 * margins
    )


def hysteretic_branch_target(data, state: dict[str, object]) -> np.ndarray:
    """Commit to a feasible branch until another is materially better."""
    candidates = branch_joint_targets(np.asarray(data.mocap_pos[0]))
    margins = JOINT_LIMIT - np.max(np.abs(candidates), axis=1)
    valid = margins >= 0.0
    qpos = np.asarray(data.qpos[:2], dtype=np.float64)
    scores = _branch_score(candidates, qpos, margins)

    committed = state.get("branch_index")
    if not isinstance(committed, int) or not valid[committed]:
        feasible = np.where(valid, margins, -np.inf)
        committed = int(np.argmax(feasible))
    else:
        best = int(np.argmax(np.where(valid, scores, -np.inf)))
        if (
            valid[best]
            and best != committed
            and scores[best] > scores[committed] + BRANCH_SWITCH_HYSTERESIS
        ):
            committed = best
    state["branch_index"] = committed
    return candidates[committed].copy()


def _smoothstep(phase: float) -> float:
    return phase * phase * (3.0 - 2.0 * phase)


def anticipatory_target_action(
    data, action: np.ndarray, target: np.ndarray | None = None
) -> np.ndarray:
    """Apply target-conditioned lookahead braking near a shoulder limit."""
    if target is None:
        target = select_branch_target(np.asarray(data.mocap_pos[0]))
    qpos = np.asarray(data.qpos[:2], dtype=np.float64)
    qvel = np.asarray(data.qvel[:2], dtype=np.float64)
    guided = np.asarray(action, dtype=np.float64).copy()

    target_margin = JOINT_LIMIT - abs(float(target[0]))
    if target_margin >= ANTICIPATORY_TARGET_MARGIN:
        return np.clip(guided, -1.0, 1.0)


    distance = float(
        np.linalg.norm(
            data.site("end_effector").xpos - np.asarray(data.mocap_pos[0])
        )
    )
    distance_weight = np.clip(
        (ANTICIPATORY_DISTANCE - distance)
        / (ANTICIPATORY_DISTANCE - SUCCESS_THRESHOLD),
        0.0,
        1.0,
    )
    target_weight = np.clip(
        (ANTICIPATORY_TARGET_MARGIN - target_margin)
        / ANTICIPATORY_TARGET_MARGIN,
        0.0,
        1.0,
    )
    branch_error = np.asarray(
        [wrap_to_pi(float(target[index] - qpos[index])) for index in range(2)],
        dtype=np.float64,
    )
    projected_qpos = qpos + ANTICIPATORY_LOOKAHEAD_SECONDS * qvel
    projected_error = np.asarray(
        [
            wrap_to_pi(float(target[index] - projected_qpos[index]))
            for index in range(2)
        ],
        dtype=np.float64,
    )
    stopping_distance = np.square(qvel) / (
        2.0 * ANTICIPATORY_BRAKING_ACCELERATION
    )
    moving_toward_target = branch_error * qvel > 0.0
    overshoot_risk = np.clip(
        stopping_distance / np.maximum(np.abs(branch_error), 0.05),
        0.0,
        1.0,
    )
    brake_weight = distance_weight * target_weight * overshoot_risk
    brake_weight = np.where(moving_toward_target, brake_weight, 0.0)
    reference_action = (
        ANTICIPATORY_POSITION_GAIN * projected_error
        - ANTICIPATORY_VELOCITY_GAIN * qvel
    )
    guided = (1.0 - 0.35 * brake_weight) * guided + (
        0.35 * brake_weight * np.clip(reference_action, -1.0, 1.0)
    )
    return np.clip(guided, -1.0, 1.0)


def stateful_branch_limit_action(
    data, action: np.ndarray, state: dict[str, object]
) -> np.ndarray:
    """Combine committed-branch stabilization with measured limit damping."""
    target = hysteretic_branch_target(data, state)
    guided = anticipatory_target_action(data, action, target)
    qpos = np.asarray(data.qpos[:2], dtype=np.float64)
    qvel = np.asarray(data.qvel[:2], dtype=np.float64)

    if abs(target[0]) >= JOINT_LIMIT - TARGET_LIMIT_MARGIN:
        distance = float(
            np.linalg.norm(
                data.site("end_effector").xpos
                - np.asarray(data.mocap_pos[0])
            )
        )
        holding = bool(state.get("holding", False))
        if holding and distance > HOLD_EXIT_DISTANCE:
            holding = False
        elif not holding and distance <= SUCCESS_THRESHOLD:
            holding = True
        state["holding"] = holding

        if distance <= TRANSITION_DISTANCE or holding:
            branch_error = np.asarray(
                [
                    wrap_to_pi(float(target[index] - qpos[index]))
                    for index in range(2)
                ],
                dtype=np.float64,
            )
            reference_action = (
                NEAR_LIMIT_POSITION_GAIN * branch_error
                - NEAR_LIMIT_VELOCITY_GAIN * qvel
            )
            blend = STATE_HOLD_BLEND if holding else ACQUISITION_BLEND
            guided = (1.0 - blend) * guided + blend * np.clip(
                reference_action, -1.0, 1.0
            )

    shoulder_sign = np.sign(qpos[0])
    if shoulder_sign == 0.0:
        shoulder_sign = np.sign(target[0])
    near_limit = abs(qpos[0]) >= JOINT_LIMIT - LIMIT_MARGIN
    constraint_force = float(data.qfrc_constraint[0])
    force_active = abs(constraint_force) > 0.5
    if near_limit or force_active:
        proximity = np.clip(
            (abs(qpos[0]) - (JOINT_LIMIT - LIMIT_MARGIN)) / LIMIT_MARGIN,
            0.0,
            1.0,
        )
        outward_velocity = max(shoulder_sign * qvel[0], 0.0)
        velocity_damping = -shoulder_sign * LIMIT_VELOCITY_GAIN * min(
            outward_velocity, 2.0
        )
        force_damping = LIMIT_FORCE_FEEDBACK_GAIN * np.clip(
            constraint_force / ACTUATOR_FORCE_SCALE,
            -1.0,
            1.0,
        )
        damping_weight = max(proximity, float(force_active))
        guided[0] += damping_weight * (velocity_damping + force_damping)

    return np.clip(guided, -1.0, 1.0)


def guided_action(data, action: np.ndarray, step_count: int) -> np.ndarray:
    target = select_branch_target(np.asarray(data.mocap_pos[0]))
    phase = np.clip(
        (step_count + 1) / TRAJECTORY_DURATION_STEPS,
        0.0,
        1.0,
    )
    interpolation = _smoothstep(float(phase))
    reference_position = interpolation * target
    reference_velocity = np.zeros(2, dtype=np.float64)
    if phase < 1.0:
        reference_velocity = (
            target
            * (6.0 * phase * (1.0 - phase))
            / TRAJECTORY_DURATION_STEPS
        )

    position_error = reference_position - np.asarray(data.qpos[:2])
    velocity_error = reference_velocity - np.asarray(data.qvel[:2])
    reference_action = (
        POSITION_GAIN * position_error + VELOCITY_GAIN * velocity_error
    )

    near_limit = np.abs(data.qpos[:2]) >= JOINT_LIMIT - LIMIT_MARGIN
    moving_outward = np.asarray(data.qpos[:2]) * np.asarray(data.qvel[:2]) > 0.0
    limit_brake = np.where(
        near_limit & moving_outward,
        -np.sign(data.qpos[:2]) * np.minimum(np.abs(data.qvel[:2]), 1.0),
        0.0,
    )
    trajectory_blend = REFERENCE_BLEND * (1.0 - interpolation)
    return np.clip(
        (1.0 - trajectory_blend) * np.asarray(action, dtype=np.float64)
        + trajectory_blend * reference_action
        + LIMIT_BRAKE_BLEND * limit_brake,
        -1.0,
        1.0,
    )
