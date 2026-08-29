import numpy as np
import pytest

from robot_learning.benchmark import final_contract
from robot_learning.benchmark.final_benchmark import official_environment
from robot_learning.scenario import make_training_env
from robot_learning.scenario import reward as reward_module
from robot_learning.scenario.environment import TwoJointArmReachEnv
from robot_learning.scenario.reward import HOLD_COMPLETE_BONUS, reach_reward
from robot_learning.train import parallel_ppo_params
from robot_learning.training.candidate_checkpoint_callback import (
    CandidateCheckpointCallback,
)


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


def test_reward_encourages_progress():
    assert reach_reward(0.10, 0.08, 0.03).total > 0
    assert reach_reward(0.08, 0.10, 0.03).total < 0


def test_linear_hold_progress_reward_pays_completion():
    early = reach_reward(
        0.005,
        0.005,
        0.01,
        held_steps=1,
        previous_held_steps=0,
        hold_steps_required=100,
    ).total
    late = reach_reward(
        0.005,
        0.005,
        0.01,
        held_steps=99,
        previous_held_steps=98,
        hold_steps_required=100,
    ).total
    done = reach_reward(
        0.005,
        0.005,
        0.01,
        held_steps=100,
        previous_held_steps=99,
        hold_steps_required=100,
    ).total
    assert early == pytest.approx(late)
    assert early > 0
    assert done - late == pytest.approx(HOLD_COMPLETE_BONUS)


def test_losing_hold_progress_applies_the_configured_forfeit(monkeypatch):
    monkeypatch.setattr(reward_module, "PROGRESS_COEFFICIENT", 0.0)
    monkeypatch.setattr(reward_module, "CLOSENESS_COEFFICIENT", 0.0)
    monkeypatch.setattr(reward_module, "OUTSIDE_BAND_PENALTY", 0.0)
    reward = reach_reward(
        0.005,
        0.0101,
        0.01,
        held_steps=0,
        previous_held_steps=90,
        hold_steps_required=100,
        penalize_outside=True,
    ).total

    expected_forfeit = -(
        reward_module.HOLD_EXIT_FORFEIT_FRACTION
        * reward_module.HOLD_PROGRESS_BONUS
        * 0.9**reward_module.HOLD_PROGRESS_EXPONENT
    )
    assert reward == pytest.approx(expected_forfeit)


def test_outside_penalty_accumulates_and_is_bounded(monkeypatch):
    monkeypatch.setattr(reward_module, "PROGRESS_COEFFICIENT", 0.0)
    monkeypatch.setattr(reward_module, "CLOSENESS_COEFFICIENT", 0.0)
    just_outside = reach_reward(0.0105, 0.0105, 0.01, penalize_outside=True).total
    far_outside = reach_reward(0.10, 0.10, 0.01, penalize_outside=True).total

    assert just_outside == pytest.approx(
        -reward_module.OUTSIDE_BAND_PENALTY * 0.0005 / reward_module.OUTSIDE_BAND_WIDTH
    )
    assert far_outside == pytest.approx(-reward_module.OUTSIDE_BAND_PENALTY)


def test_reward_components_are_free_form_and_sum_to_the_scalar():
    result = reach_reward(
        0.05,
        0.04,
        0.01,
        action=np.full(2, 0.3),
        held_steps=0,
        previous_held_steps=5,
        hold_steps_required=100,
        penalize_outside=True,
    )

    assert isinstance(result.components, dict)
    assert all(isinstance(value, float) for value in result.components.values())
    assert sum(result.components.values()) == pytest.approx(result.total)


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
        reward_module.OUTSIDE_BAND_PENALTY
        * 0.0001
        / reward_module.OUTSIDE_BAND_WIDTH
    )
    assert exit_reward == pytest.approx(expected_penalty)
    assert continued_outside_reward == pytest.approx(expected_penalty)
    assert env._outside_after_hold is True


def test_action_cost_penalizes_large_actions(monkeypatch):
    monkeypatch.setattr(reward_module, "ACTION_COST_COEFFICIENT", 1.0)
    gentle = reach_reward(0.05, 0.04, 0.03, action=np.full(2, 0.1)).total
    violent = reach_reward(0.05, 0.04, 0.03, action=np.full(2, 1.0)).total
    assert violent < gentle


def test_parallel_envs_preserve_total_rollout_size():
    original = {"n_steps": 1024, "batch_size": 64}
    parallel = parallel_ppo_params(original, n_envs=4)
    assert parallel["n_steps"] == 256
    assert parallel["n_steps"] * 4 == original["n_steps"]


def test_parallel_env_count_must_be_valid():
    with pytest.raises(ValueError, match="must be divisible"):
        parallel_ppo_params({"n_steps": 1024}, n_envs=3)
    with pytest.raises(ValueError, match="at least 1"):
        parallel_ppo_params({"n_steps": 1024}, n_envs=0)


def test_candidate_checkpoint_waits_for_a_completed_update(monkeypatch, tmp_path):
    callback = CandidateCheckpointCallback(output_dir=tmp_path, every_steps=20_000)
    checkpoints: list[int] = []

    def record_checkpoint():
        checkpoints.append(callback.num_timesteps)
        callback.last_checkpoint_steps = callback.num_timesteps

    monkeypatch.setattr(callback, "_save", record_checkpoint)

    callback.num_timesteps = 20_000
    assert callback._on_step()
    assert checkpoints == []

    callback.num_timesteps = 21_504
    callback._on_rollout_start()
    assert checkpoints == [21_504]
    assert callback.next_checkpoint == 40_000

    callback._on_training_end()
    assert checkpoints == [21_504]

    callback.num_timesteps = 24_576
    callback._on_training_end()
    assert checkpoints == [21_504, 24_576]
