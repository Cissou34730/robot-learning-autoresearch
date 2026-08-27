import numpy as np
import pytest

from robot_learning.environments.reach_env import TwoJointArmReachEnv
from robot_learning.rewards import reach_reward as reward_module
from robot_learning.rewards.reach_reward import HOLD_COMPLETE_BONUS, reach_reward
from robot_learning.train import parallel_ppo_params
from robot_learning.training.selection_callback import SelectionCallback


def test_observation_matches_declared_space():
    env = TwoJointArmReachEnv()
    obs, _ = env.reset(seed=0)
    assert env.observation_space.contains(obs)


def test_reward_encourages_progress():
    assert reach_reward(0.10, 0.08, 0.03) > 0
    assert reach_reward(0.08, 0.10, 0.03) < 0


def test_reward_pays_dwell_and_completion():
    early = reach_reward(0.005, 0.005, 0.01, held_steps=1, hold_steps_required=100)
    late = reach_reward(0.005, 0.005, 0.01, held_steps=99, hold_steps_required=100)
    done = reach_reward(0.005, 0.005, 0.01, held_steps=100, hold_steps_required=100)
    assert early == pytest.approx(reward_module.DWELL_BONUS_PER_STEP)
    assert late == pytest.approx(early)
    assert done - late == pytest.approx(HOLD_COMPLETE_BONUS)


def test_action_cost_penalizes_large_actions(monkeypatch):
    monkeypatch.setattr(reward_module, "ACTION_COST_COEFFICIENT", 1.0)
    gentle = reach_reward(0.05, 0.04, 0.03, action=np.full(2, 0.1))
    violent = reach_reward(0.05, 0.04, 0.03, action=np.full(2, 1.0))
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


def test_selection_waits_for_a_completed_rollout_update(monkeypatch, tmp_path):
    callback = SelectionCallback(
        output_dir=tmp_path,
        eval_every_steps=20_000,
        episodes=10,
    )
    evaluations: list[int] = []
    callback.best_rank = (101.0, 101.0, 101.0, 0.0)
    monkeypatch.setattr(
        callback,
        "_evaluate",
        lambda: evaluations.append(callback.num_timesteps)
        or {
            "success_percent": 100.0,
            "consecutive_hold_steps": {
                "median": 100.0,
                "mean": 100.0,
                "required": 100,
            },
            "closest_distance_cm": {"median": 0.1},
            "timesteps": callback.num_timesteps,
        },
    )

    callback.num_timesteps = 20_000
    assert callback._on_step()
    assert evaluations == []

    callback.num_timesteps = 21_504
    callback._on_rollout_start()
    assert evaluations == [21_504]
    assert callback.next_evaluation == 40_000

    callback.evaluate_final_policy()
    assert evaluations == [21_504]

    callback.num_timesteps = 24_576
    callback.evaluate_final_policy()
    assert evaluations == [21_504, 24_576]
