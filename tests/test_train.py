import pytest

from robot_learning.train import parallel_ppo_params


def test_parallel_envs_preserve_total_rollout_size():
    original = {"n_steps": 1024, "batch_size": 64}

    parallel = parallel_ppo_params(original, n_envs=4)

    assert parallel["n_steps"] == 256
    assert parallel["n_steps"] * 4 == original["n_steps"]
    assert original["n_steps"] == 1024


def test_parallel_envs_require_divisible_rollout_size():
    with pytest.raises(ValueError, match="must be divisible"):
        parallel_ppo_params({"n_steps": 1024}, n_envs=3)


def test_parallel_envs_reject_zero_workers():
    with pytest.raises(ValueError, match="at least 1"):
        parallel_ppo_params({"n_steps": 1024}, n_envs=0)
