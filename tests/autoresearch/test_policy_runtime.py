"""Saved policies retain their semantics under subsequent scientific edits."""

import sys
import types

import numpy as np
import pytest

from research.runner_repository import artifact_fingerprint, copy_artifact
from robot_learning.policy_runtime import PolicyIO, load_runtime, save_runtime


def scientific_module(monkeypatch, size, scale=0.1):
    name = "robot_learning.scenario.runtime_test_policy"
    module = types.ModuleType(name)
    exec(  # noqa: S102 -- a disposable scientific module tests by-value capture
        "import numpy as np\n"
        "from gymnasium.spaces import Box\n"
        "from robot_learning.policy_runtime import PolicyIO\n"
        f"SIZE = {size}\nSCALE = {scale}\n"
        "def observe(data): return np.full(SIZE, 0.25, dtype=np.float32)\n"
        "def action(value): return np.asarray(value) * SCALE\n"
        "class Model:\n"
        " def __init__(self):\n"
        "  self.observation_space = Box(-np.inf, np.inf, (SIZE,), dtype=np.float32)\n"
        "  self.action_space = Box(-1, 1, (2,), dtype=np.float32)\n"
        " def predict(self, obs, **kwargs):\n"
        "  assert obs.shape == (SIZE,)\n"
        "  return np.ones(2) * obs[0], None\n"
        "def load(path, algorithm=None): return Model()\n",
        module.__dict__,
    )
    monkeypatch.setitem(sys.modules, name, module)
    return module


def artifact(tmp_path, module):
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "model.zip"
    path.write_bytes(b"weights")
    (tmp_path / "artifact.json").write_text("{}")
    save_runtime(
        path,
        policy_io=PolicyIO(module.observe, module.action),
        loader=module.load,
        normalizer=None,
    )
    return path


@pytest.mark.parametrize("size", [3, 17, 30])
def test_runtime_retains_code_and_shape_after_scientific_module_replacement(
    monkeypatch, tmp_path, size
):
    module = scientific_module(monkeypatch, size)
    path = artifact(tmp_path, module)
    scientific_module(monkeypatch, size + 2, scale=9)
    runtime = load_runtime(path)
    observation = runtime.io.observe(None)
    assert observation.shape == (size,)
    np.testing.assert_allclose(
        runtime.io.action(runtime.predict(observation)), [0.025, 0.025]
    )


def test_same_shape_semantic_changes_are_isolated(monkeypatch, tmp_path):
    module = scientific_module(monkeypatch, 3)
    path = artifact(tmp_path, module)
    module.SCALE = 9
    module.observe = lambda data: np.full(3, 100)
    module.load = lambda *args: pytest.fail("Current loader must never run")
    runtime = load_runtime(path)
    np.testing.assert_allclose(runtime.io.observe(None), [0.25] * 3)
    np.testing.assert_allclose(runtime.io.action(np.ones(2)), [0.1, 0.1])


def test_all_evaluation_paths_use_each_policys_inputs_and_same_task(
    monkeypatch, tmp_path
):
    from robot_learning.benchmark.final_benchmark import official_environment
    from robot_learning.benchmark.reference_evaluation import task_reference_environment
    from robot_learning.scenario.environment import make_evaluation_env

    for factory in (
        official_environment,
        task_reference_environment,
        make_evaluation_env,
    ):
        positions = []
        for size in (3, 30):
            path = artifact(
                tmp_path / f"{factory.__name__}-{size}",
                scientific_module(monkeypatch, size),
            )
            runtime = load_runtime(path)
            env = factory(policy_runtime=runtime)
            obs, _ = env.reset(seed=7)
            positions.append(env.data.mocap_pos[0].copy())
            assert obs.shape == (size,)
            env.step(np.ones(2))
            np.testing.assert_allclose(env.data.ctrl, [0.1, 0.1])
            env.close()
        np.testing.assert_array_equal(*positions)


def test_missing_runtime_or_stats_and_wrong_weights_fail_explicitly(
    monkeypatch, tmp_path
):
    module = scientific_module(monkeypatch, 3)
    path = artifact(tmp_path, module)
    stats = tmp_path / "vecnormalize.pkl"
    stats.write_bytes(b"statistics")
    save_runtime(
        path,
        policy_io=PolicyIO(module.observe, module.action),
        loader=module.load,
        normalizer=None,
        stats_path=stats,
    )
    stats.unlink()
    with pytest.raises(ValueError, match="normalization"):
        load_runtime(path)
    stats.write_bytes(b"statistics")
    path.write_bytes(b"other weights")
    with pytest.raises(ValueError, match="weights"):
        load_runtime(path)
    (tmp_path / "policy_runtime.pkl").unlink()
    with pytest.raises(ValueError, match="Legacy"):
        load_runtime(path)


def test_copy_and_identity_include_executable_contract(monkeypatch, tmp_path):
    module = scientific_module(monkeypatch, 3)
    source = artifact(tmp_path / "source", module)
    before = artifact_fingerprint(source.parent)
    copy_artifact(source.parent, tmp_path / "accepted")
    assert artifact_fingerprint(tmp_path / "accepted") == before
    runtime = load_runtime(tmp_path / "accepted/model.zip")
    assert runtime.io.observe(None).shape == (3,)
    module.SCALE = 0.2
    artifact(source.parent, module)
    assert artifact_fingerprint(source.parent) != before


def test_candidate_without_manifest_requires_its_runtime(tmp_path):
    from research.runner_execution import candidate_directories

    directory = tmp_path / "final_checkpoint"
    directory.mkdir()
    (directory / "model.zip").write_bytes(b"weights")
    (directory / "artifact.json").write_text('{"timesteps": 100}')
    with pytest.raises(RuntimeError, match="policy_runtime.pkl"):
        candidate_directories(tmp_path)
    (directory / "policy_runtime.pkl").write_bytes(b"runtime")
    assert candidate_directories(tmp_path)[0]["path"] == directory


def test_real_sb3_checkpoint_preserves_normalization_and_prediction(
    monkeypatch, tmp_path
):
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

    from robot_learning.scenario import observations
    from robot_learning.scenario.environment import (
        make_evaluation_env,
        make_training_env,
    )
    from robot_learning.training.checkpoint import save_checkpoint

    venv = VecNormalize(DummyVecEnv([make_training_env]), norm_reward=False)
    model = PPO(
        "MlpPolicy",
        venv,
        n_steps=8,
        batch_size=4,
        policy_kwargs={"net_arch": [8]},
        seed=0,
        device="cpu",
    )
    # Update normalization without training an algorithm or running a campaign.
    venv.reset()
    venv.step(np.zeros((1, 2)))
    save_checkpoint(model, venv, tmp_path)
    runtime = load_runtime(tmp_path / "model.zip")
    env = make_evaluation_env(policy_runtime=runtime)
    obs, _ = env.reset(seed=19)
    expected, _ = model.predict(venv.normalize_obs(obs), deterministic=True)
    monkeypatch.setattr(observations, "reach_observation", lambda data: np.ones(30))
    monkeypatch.setattr(
        "robot_learning.training.algorithms.load_policy",
        lambda *args: pytest.fail("Must use frozen loader"),
    )
    reloaded = load_runtime(tmp_path / "model.zip")
    np.testing.assert_allclose(reloaded.predict(obs), expected, rtol=1e-6)
    np.testing.assert_allclose(reloaded.normalizer(obs), venv.normalize_obs(obs))
    env.close()
    venv.close()
