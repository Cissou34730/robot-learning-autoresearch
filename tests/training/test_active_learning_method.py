"""Researcher-owned tests for the active learning method.

The active method is currently PPO, built directly by `robot_learning/train.py`.
These tests describe that implementation; they are not a permanent contract.
Replacing the algorithm is an ordinary research change, and the researcher who
replaces it is expected to rewrite this file together with the training code.
"""

import pytest
from stable_baselines3 import PPO

from robot_learning import train as train_module
from robot_learning.scenario.environment import make_training_env
from robot_learning.training import algorithms
from robot_learning.training.research_config import load_experiment_config


def build_active_model() -> PPO:
    config = load_experiment_config()
    return PPO(
        "MlpPolicy",
        make_training_env(),
        policy_kwargs=train_module.build_policy_kwargs(config["policy"]),
        **train_module.parallel_ppo_params(config["ppo"], 1),
    )


def test_training_entry_point_builds_the_active_method():
    assert train_module.ALGORITHM_NAME == "ppo"
    assert train_module.PPO is PPO


def test_active_configuration_constructs_the_active_model():
    assert isinstance(build_active_model(), PPO)


def test_policy_loading_reloads_the_active_method(tmp_path):
    build_active_model().save(tmp_path / "model.zip")

    reloaded = algorithms.load_policy(
        tmp_path / "model.zip", train_module.ALGORITHM_NAME
    )

    assert isinstance(reloaded, PPO)
    assert hasattr(reloaded, "predict")


def test_parallel_envs_preserve_total_rollout_size():
    original = {"n_steps": 1024, "batch_size": 64}
    parallel = train_module.parallel_ppo_params(original, n_envs=4)

    assert parallel["n_steps"] == 256
    assert parallel["n_steps"] * 4 == original["n_steps"]


def test_parallel_env_count_must_be_valid():
    with pytest.raises(ValueError, match="must be divisible"):
        train_module.parallel_ppo_params({"n_steps": 1024}, n_envs=3)
    with pytest.raises(ValueError, match="at least 1"):
        train_module.parallel_ppo_params({"n_steps": 1024}, n_envs=0)
