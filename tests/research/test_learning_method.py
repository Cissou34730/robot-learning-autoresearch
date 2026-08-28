import numpy as np
import pytest

from robot_learning.environments.reach_env import TwoJointArmReachEnv
from robot_learning.rewards import reach_reward as reward_module
from robot_learning.rewards.reach_reward import HOLD_COMPLETE_BONUS, reach_reward
from robot_learning.train import parallel_ppo_params
from robot_learning.training.selection_callback import (
    SelectionCallback,
    select_top_finalists,
)


def test_observation_matches_declared_space():
    env = TwoJointArmReachEnv()
    obs, _ = env.reset(seed=0)
    assert env.observation_space.contains(obs)


def test_reward_encourages_progress():
    assert reach_reward(0.10, 0.08, 0.03) > 0
    assert reach_reward(0.08, 0.10, 0.03) < 0


def test_hold_progress_reward_accelerates_and_pays_completion():
    early = reach_reward(
        0.005,
        0.005,
        0.01,
        held_steps=1,
        previous_held_steps=0,
        hold_steps_required=100,
    )
    late = reach_reward(
        0.005,
        0.005,
        0.01,
        held_steps=99,
        previous_held_steps=98,
        hold_steps_required=100,
    )
    done = reach_reward(
        0.005,
        0.005,
        0.01,
        held_steps=100,
        previous_held_steps=99,
        hold_steps_required=100,
    )
    assert late > early > 0
    assert done - late == pytest.approx(
        HOLD_COMPLETE_BONUS
        + reward_module.HOLD_PROGRESS_BONUS * 2 / 10_000
    )


def test_losing_hold_progress_forfeits_accumulated_capital():
    reward = reach_reward(
        0.005,
        0.0101,
        0.01,
        held_steps=0,
        previous_held_steps=90,
        hold_steps_required=100,
        penalize_outside=True,
    )

    assert reward < -40.0


def test_outside_penalty_accumulates_and_is_bounded(monkeypatch):
    monkeypatch.setattr(reward_module, "PROGRESS_COEFFICIENT", 0.0)
    monkeypatch.setattr(reward_module, "CLOSENESS_COEFFICIENT", 0.0)
    just_outside = reach_reward(0.0105, 0.0105, 0.01, penalize_outside=True)
    far_outside = reach_reward(0.10, 0.10, 0.01, penalize_outside=True)

    assert just_outside == pytest.approx(-0.025)
    assert far_outside == pytest.approx(-reward_module.OUTSIDE_BAND_PENALTY)


def test_environment_keeps_outside_penalty_active_after_losing_hold(monkeypatch):
    env = TwoJointArmReachEnv()
    env.reset(seed=0)
    env._held_steps = 90
    env._previous_distance = 0.005
    monkeypatch.setattr(env, "_distance_to_target", lambda: 0.0101)

    _, exit_reward, _, _, _ = env.step(np.zeros(2))
    _, continued_outside_reward, _, _, _ = env.step(np.zeros(2))

    assert exit_reward < -40.0
    assert continued_outside_reward < 0.0
    assert env._outside_after_hold is True


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
        episodes=50,
        top_k=3,
    )
    evaluations: list[int] = []
    def record_evaluation():
        evaluations.append(callback.num_timesteps)
        callback.last_evaluation_steps = callback.num_timesteps

    monkeypatch.setattr(callback, "_evaluate_and_save", record_evaluation)
    monkeypatch.setattr(callback, "_finalize_selection", lambda: None)

    callback.num_timesteps = 20_000
    assert callback._on_step()
    assert evaluations == []

    callback.num_timesteps = 21_504
    callback._on_rollout_start()
    assert evaluations == [21_504]
    assert callback.next_evaluation == 40_000

    callback._on_training_end()
    assert evaluations == [21_504]

    callback.num_timesteps = 24_576
    callback._on_training_end()
    assert evaluations == [21_504, 24_576]


def test_selection_retains_exactly_the_three_best_checkpoints():
    entries = [
        {"rank": [score, 0, 0, 0], "timesteps": score, "path": str(score)}
        for score in (1, 4, 2, 5, 3)
    ]

    selected = select_top_finalists(entries, top_k=3)

    assert [item["rank"][0] for item in selected] == [5, 4, 3]


def test_equivalent_checkpoints_are_spread_over_training_time():
    entries = [
        {
            "rank": [98, 2, 2, -21 + step / 100_000],
            "timesteps": step,
            "path": str(step),
            "paired_vs_reference": {
                "net_wins": 0,
                "exact_p_value": 1.0,
            },
        }
        for step in (20_000, 40_000, 60_000, 80_000, 100_000, 120_000)
    ]

    selected = select_top_finalists(entries, top_k=3)

    assert [item["timesteps"] for item in selected] == [20_000, 60_000, 120_000]


def test_meaningfully_better_checkpoint_precedes_equivalent_ones():
    equivalent = [
        {
            "rank": [98, 2, 2, -21],
            "timesteps": step,
            "path": str(step),
            "paired_vs_reference": {"net_wins": 0, "exact_p_value": 1.0},
        }
        for step in (20_000, 60_000, 120_000)
    ]
    better = {
        "rank": [99, 50, 90, -1],
        "timesteps": 80_000,
        "path": "better",
        "paired_vs_reference": {"net_wins": 8, "exact_p_value": 0.01},
    }

    selected = select_top_finalists([*equivalent, better], top_k=3)

    assert selected[0] is better
