"""Researcher-owned tests for the current training environment.

These describe the scenario as it is implemented today. A scenario experiment
that changes the training mechanics is expected to update them.
"""

import numpy as np
import pytest

import robot_learning.scenario.environment as environment_module
import robot_learning.scenario.reward as reward_module
from robot_learning.benchmark import final_contract
from robot_learning.benchmark.final_benchmark import official_environment
from robot_learning.scenario.environment import (
    TRAINING_HARD_ANGLE_PROBABILITY,
    TRAINING_HARD_ANGLE_RANGE,
    TRAINING_TARGET_RADIUS_RANGE,
    TwoJointArmReachEnv,
    make_evaluation_env,
    make_training_env,
)


def test_observation_matches_declared_space():
    env = make_training_env()
    obs, _ = env.reset(seed=0)
    assert env.observation_space.contains(obs)


def test_training_distribution_covers_the_official_radius_range():
    training = make_training_env()
    evaluation = make_evaluation_env()

    assert training.target_radius_range == TRAINING_TARGET_RADIUS_RANGE
    assert training.target_radius_range == (0.06, 0.20)
    assert training.hard_angle_range == TRAINING_HARD_ANGLE_RANGE
    assert training.hard_angle_probability == TRAINING_HARD_ANGLE_PROBABILITY
    assert evaluation.target_radius_range == final_contract.TARGET_RADIUS_RANGE
    assert evaluation.hard_angle_range is None


def test_hard_angle_curriculum_can_focus_on_the_recurrent_failure_sector():
    training = TwoJointArmReachEnv(
        hard_angle_range=TRAINING_HARD_ANGLE_RANGE,
        hard_angle_probability=1.0,
    )

    training.reset(seed=0)
    angle = float(
        np.arctan2(training.data.mocap_pos[0][1], training.data.mocap_pos[0][0])
    )

    assert TRAINING_HARD_ANGLE_RANGE[0] <= angle <= TRAINING_HARD_ANGLE_RANGE[1]


def test_training_environment_may_diverge_from_the_official_task():
    curriculum = TwoJointArmReachEnv(
        target_radius_range=(0.06, 0.10),
        success_threshold=0.03,
        hold_seconds=0.5,
        max_episode_steps=200,
    )
    obs, _ = curriculum.reset(seed=0)
    curriculum.step(np.zeros(2))
    radius = float(np.linalg.norm(curriculum.data.mocap_pos[0][:2]))

    assert curriculum.observation_space.contains(obs)
    assert radius <= 0.10 < final_contract.TARGET_RADIUS_RANGE[1]
    assert curriculum.success_threshold != final_contract.SUCCESS_THRESHOLD
    assert curriculum.max_episode_steps != final_contract.MAX_EPISODE_STEPS

    official = official_environment()
    assert official.success_threshold == final_contract.SUCCESS_THRESHOLD
    assert official.target_radius_range == final_contract.TARGET_RADIUS_RANGE
    assert official.max_episode_steps == final_contract.MAX_EPISODE_STEPS


def test_environment_latches_the_outside_penalty_after_losing_hold(monkeypatch):
    """Integration contract only: the reward formula itself lives in test_reward."""
    env = make_training_env()
    env.reset(seed=0)
    env._held_steps = 90
    env._previous_distance = 0.005
    monkeypatch.setattr(env, "_distance_to_target", lambda: 0.0101)
    penalize_outside: list[bool] = []
    produced: list[object] = []
    original_reward = reward_module.reach_reward

    def record(*args, **kwargs):
        penalize_outside.append(bool(kwargs["penalize_outside"]))
        result = original_reward(*args, **kwargs)
        produced.append(result)
        return result

    monkeypatch.setattr(environment_module, "reach_reward", record)

    _, exit_reward, _, _, exit_info = env.step(np.zeros(2))
    _, continued_reward, _, _, continued_info = env.step(np.zeros(2))

    assert penalize_outside == [True, True]
    assert env._outside_after_hold is True
    assert exit_reward == pytest.approx(produced[0].total)
    assert continued_reward == pytest.approx(produced[1].total)
    assert exit_info["reward_components"] == produced[0].components
    assert continued_info["reward_components"] == produced[1].components
