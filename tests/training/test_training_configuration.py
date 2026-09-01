"""Researcher-owned tests for the active runtime configuration.

`research/current_params.json` describes the currently active training method.
Its sections follow the active method, so replacing the algorithm changes both
the file and this test.
"""

from robot_learning.training.research_config import (
    load_experiment_config,
    merge_param_overrides,
)


def test_current_params_describes_the_active_method():
    config = load_experiment_config()

    assert config["algorithm"]["name"] == "ppo"
    assert config["ppo"]["n_steps"] > 0
    assert config["policy"]["net_arch"]
    assert config["training"]["n_envs"] >= 1


def test_runtime_overrides_merge_without_mutating_the_active_configuration():
    config = load_experiment_config()
    original_learning_rate = config["ppo"]["learning_rate"]
    override_learning_rate = original_learning_rate + 0.0001
    merged = merge_param_overrides(
        config,
        {"ppo": {"learning_rate": override_learning_rate}},
    )

    assert merged["ppo"]["learning_rate"] == override_learning_rate
    assert merged["ppo"]["n_steps"] == config["ppo"]["n_steps"]
    assert config["ppo"]["learning_rate"] == original_learning_rate
