"""Executable proposal check for the I2 broadened training recipe.

This module is intended for Runner execution.  It uses controlled joint-state
transitions for the training-only shaping terms and also performs one real
environment step to check reward/info composition.
"""

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from contracts.robots.two_joint_arm import FOREARM_LENGTH, UPPER_ARM_LENGTH
from contracts.task_spec import (
    FRAME_SKIP,
    HOLD_SECONDS,
    MAX_EPISODE_STEPS,
    SUCCESS_THRESHOLD,
    TARGET_RADIUS_RANGE,
)
from robot_learning.scenario.environment import (
    TwoJointArmReachEnv,
    make_evaluation_env,
)
from robot_learning.training.environment import (
    TRAINING_ESCAPE_WINDOW_STEPS,
    TRAINING_TARGET_RADIUS_RANGE,
    AlternatingBranchTrainingEnv,
    make_training_env,
)


def _wrap_to_pi(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _reference_configuration(
    target: np.ndarray, elbow_sign: int
) -> np.ndarray:
    target_x = float(target[0])
    target_y = float(target[1])
    cos_elbow = (
        target_x**2
        + target_y**2
        - UPPER_ARM_LENGTH**2
        - FOREARM_LENGTH**2
    ) / (2.0 * UPPER_ARM_LENGTH * FOREARM_LENGTH)
    elbow = elbow_sign * float(np.arccos(np.clip(cos_elbow, -1.0, 1.0)))
    shoulder = float(
        np.arctan2(target_y, target_x)
        - np.arctan2(
            FOREARM_LENGTH * np.sin(elbow),
            UPPER_ARM_LENGTH + FOREARM_LENGTH * np.cos(elbow),
        )
    )
    return np.array([shoulder, elbow], dtype=np.float64)


def _reference_potential(target_q: np.ndarray, qpos: np.ndarray) -> float:
    errors = np.array(
        [
            _wrap_to_pi(float(target_q[0]) - float(qpos[0])),
            _wrap_to_pi(float(target_q[1]) - float(qpos[1])),
        ],
        dtype=np.float64,
    )
    return -float(np.linalg.norm(errors))


def _set_joint_state(env: AlternatingBranchTrainingEnv, qpos: np.ndarray) -> None:
    env.data.qpos[:2] = qpos
    env.data.qvel[:] = 0.0
    mujoco.mj_forward(env.model, env.data)


def _check_recipe() -> dict[str, object]:
    training = make_training_env()
    evaluation = make_evaluation_env()
    if type(training) is not AlternatingBranchTrainingEnv:
        raise AssertionError("make_training_env did not return the I2 environment")
    if type(evaluation) is not TwoJointArmReachEnv:
        raise AssertionError("evaluation construction was replaced by training code")
    if (
        training.observation_space.shape != evaluation.observation_space.shape
        or training.action_space.shape != evaluation.action_space.shape
        or not np.array_equal(training.action_space.low, evaluation.action_space.low)
        or not np.array_equal(training.action_space.high, evaluation.action_space.high)
    ):
        raise AssertionError("training spaces are incompatible with evaluation")

    expected_range = (0.06, 0.20)
    if tuple(TRAINING_TARGET_RADIUS_RANGE) != expected_range:
        raise AssertionError("training range is not the exact official range")
    if tuple(training.target_radius_range) != tuple(TARGET_RADIUS_RANGE):
        raise AssertionError("training environment did not receive official range")
    if tuple(evaluation.target_radius_range) != tuple(TARGET_RADIUS_RANGE):
        raise AssertionError("evaluation range changed")
    expected_hold_steps = round(
        HOLD_SECONDS / (evaluation.model.opt.timestep * FRAME_SKIP)
    )
    if (
        evaluation.success_threshold != SUCCESS_THRESHOLD
        or evaluation.frame_skip != FRAME_SKIP
        or evaluation.max_episode_steps != MAX_EPISODE_STEPS
        or evaluation.hold_steps_required != expected_hold_steps
    ):
        raise AssertionError("evaluation mechanics or hold settings changed")

    seed = 271828
    branches: list[str] = []
    signs: list[int] = []
    targets: list[np.ndarray] = []
    configurations: list[np.ndarray] = []
    for index in range(6):
        training.reset(seed=seed if index == 0 else None)
        branches.append(training.selected_branch)
        signs.append(training.selected_branch_sign)
        targets.append(training.data.mocap_pos[0][:2].copy())
        configurations.append(training.desired_joint_configuration.copy())
        expected_sign = 1 if index % 2 == 0 else -1
        if training.selected_branch_sign != expected_sign:
            raise AssertionError("branch assignment did not alternate")
        reference = _reference_configuration(
            training.data.mocap_pos[0][:2], expected_sign
        )
        if not np.allclose(training.desired_joint_configuration, reference):
            raise AssertionError("desired IK configuration is not analytic reference")
        if np.sign(training.desired_joint_configuration[1]) != expected_sign:
            raise AssertionError("desired elbow sign is incorrect")

    replay = make_training_env()
    replay_targets: list[np.ndarray] = []
    replay_branches: list[str] = []
    for index in range(6):
        replay.reset(seed=seed if index == 0 else None)
        replay_targets.append(replay.data.mocap_pos[0][:2].copy())
        replay_branches.append(replay.selected_branch)
    if branches != replay_branches or not all(
        np.allclose(left, right) for left, right in zip(targets, replay_targets)
    ):
        raise AssertionError("branch/target sequence is not seed reproducible")

    # Use a state farther from the selected target and compare controlled
    # transitions against an independently computed wrapped-angle potential.
    training.reset(seed=seed)
    target_q = _reference_configuration(
        training.data.mocap_pos[0][:2], training.selected_branch_sign
    )
    start = target_q + np.array([0.04, 0.04 * training.selected_branch_sign])
    toward = target_q + np.array([0.02, 0.02 * training.selected_branch_sign])
    away = target_q + np.array([0.06, 0.06 * training.selected_branch_sign])
    _set_joint_state(training, start)
    _set_joint_state(training, toward)
    toward_q = training.data.qpos[:2].copy()
    _set_joint_state(training, away)
    away_q = training.data.qpos[:2].copy()
    expected_toward_delta = _reference_potential(
        target_q, toward_q
    ) - _reference_potential(target_q, start)
    expected_away_delta = _reference_potential(
        target_q, away_q
    ) - _reference_potential(target_q, start)
    toward_branch, toward_escape = training._training_shaping(
        start, toward_q, TRAINING_ESCAPE_WINDOW_STEPS + 1
    )
    away_branch, away_escape = training._training_shaping(
        start, away_q, TRAINING_ESCAPE_WINDOW_STEPS + 1
    )
    if not (expected_toward_delta > 0.0 and toward_branch > 0.0):
        raise AssertionError("movement toward selected branch was not rewarded")
    if not (expected_away_delta < 0.0 and away_branch < 0.0):
        raise AssertionError("movement away from selected branch was not penalized")
    if toward_escape != 0.0 or away_escape != 0.0:
        raise AssertionError("escape shaping remained active after its window")

    repeated_escape: list[float] = []
    repeated_previous = np.zeros(2, dtype=np.float64)
    for step_index in range(1, TRAINING_ESCAPE_WINDOW_STEPS + 2):
        repeated_current = np.array(
            [0.0, 0.002 * training.selected_branch_sign * step_index],
            dtype=np.float64,
        )
        _, escape_value = training._training_shaping(
            repeated_previous, repeated_current, step_index
        )
        repeated_escape.append(escape_value)
        repeated_previous = repeated_current
    if not all(value > 0.0 for value in repeated_escape[:-1]):
        raise AssertionError("escape shaping did not persist through its window")
    if repeated_escape[-1] != 0.0:
        raise AssertionError("escape shaping did not stop after its window")

    selected_departure = np.array(
        [target_q[0], 0.02 * training.selected_branch_sign], dtype=np.float64
    )
    reverse_departure = np.array(
        [target_q[0], -0.02 * training.selected_branch_sign], dtype=np.float64
    )
    _, selected_escape = training._training_shaping(
        np.zeros(2), selected_departure, 1
    )
    _, reverse_escape = training._training_shaping(
        np.zeros(2), reverse_departure, 1
    )
    if not (selected_escape > 0.0 and reverse_escape < 0.0):
        raise AssertionError("early escape shaping did not follow elbow direction")

    reset_branch = training.selected_branch
    training.reset()
    if (
        training.selected_branch == reset_branch
        or training._training_step_count != 0
        or training._previous_elbow != 0.0
    ):
        raise AssertionError("reset did not clear shaping state or continue alternation")

    _, reward, _, _, info = training.step(np.zeros(2, dtype=np.float32))
    attribution = info["training_attribution"]
    if "reward_components" not in info:
        raise AssertionError("base reward attribution was dropped")
    if not np.isfinite(reward) or not np.isfinite(
        float(attribution["total_shaping"])
    ):
        raise AssertionError("training reward transition was not finite")
    if not np.isclose(
        reward,
        float(attribution["base_reward"])
        + float(attribution["total_shaping"]),
    ):
        raise AssertionError("training shaping was not appended to base reward")

    observed = {
        "training_type": type(training).__name__,
        "evaluation_type": type(evaluation).__name__,
        "training_radius_range": list(training.target_radius_range),
        "official_radius_range": list(TARGET_RADIUS_RANGE),
        "branch_sequence": branches,
        "elbow_sign_sequence": signs,
        "desired_elbow_signs": [
            int(np.sign(configuration[1])) for configuration in configurations
        ],
        "controlled_branch_shaping": {
            "toward": float(toward_branch),
            "away": float(away_branch),
        },
        "controlled_escape_shaping": {
            "selected_direction": float(selected_escape),
            "reverse_direction": float(reverse_escape),
            "after_window_toward": float(toward_escape),
            "after_window_away": float(away_escape),
            "repeated_window_values": [float(value) for value in repeated_escape],
        },
        "reset_training_step_count": training._training_step_count,
        "checked_hold_steps": evaluation.hold_steps_required,
    }
    training.close()
    replay.close()
    evaluation.close()
    return {
        "check_name": "i2_broadened_training_recipe",
        "checked_scope": [
            "exact official training radius range",
            "seed-reproducible alternating analytic IK branches",
            "wrapped branch potential progress and reversal",
            "signed early reset escape and finite window",
            "reset history clearing and continued alternation",
            "base reward/info preservation through a real training step",
            "distinct training construction and official evaluation mechanics",
        ],
        "observed": observed,
        "unchecked_scope": [
            "policy-learning outcomes and PPO convergence",
            "official evaluation success or hold performance",
            "scientific attribution of any complete-artifact comparison",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_json")
    args = parser.parse_args()
    artifact = _check_recipe()
    Path(args.output_json).write_text(
        json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
