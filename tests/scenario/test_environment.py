"""Researcher-owned tests for the current training environment.

These describe the scenario as it is implemented today. A scenario experiment
that changes the training mechanics is expected to update them.
"""

import numpy as np
import pytest

from robot_learning.benchmark import final_contract
from robot_learning.benchmark.final_benchmark import official_environment
from robot_learning.scenario import make_training_env
from robot_learning.scenario import reward as reward_module
from robot_learning.scenario.environment import TwoJointArmReachEnv


def test_observation_matches_declared_space():
    env = make_training_env()
    obs, _ = env.reset(seed=0)
    assert env.observation_space.contains(obs)


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


def test_environment_keeps_outside_penalty_active_after_losing_hold(monkeypatch):
    env = make_training_env()
    env.reset(seed=0)
    env._held_steps = 90
    env._previous_distance = 0.005
    monkeypatch.setattr(reward_module, "PROGRESS_COEFFICIENT", 0.0)
    monkeypatch.setattr(reward_module, "CLOSENESS_COEFFICIENT", 0.0)
    monkeypatch.setattr(env, "_distance_to_target", lambda: 0.0101)

    _, exit_reward, _, _, _ = env.step(np.zeros(2))
    _, continued_outside_reward, _, _, _ = env.step(np.zeros(2))

    expected_penalty = -(
        reward_module.OUTSIDE_BAND_PENALTY * 0.0001 / reward_module.OUTSIDE_BAND_WIDTH
    )
    assert exit_reward == pytest.approx(expected_penalty)
    assert continued_outside_reward == pytest.approx(expected_penalty)
    assert env._outside_after_hold is True
