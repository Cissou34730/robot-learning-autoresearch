"""Numerical regression guards for the scenario extraction.

The golden values were captured from the implementation before it moved into
`robot_learning/scenario/`; the migration must be bit-identical.
"""

import json
from pathlib import Path

import mujoco
import numpy as np
import pytest

from robot_learning.scenario import evaluate_research_model, make_training_env
from robot_learning.scenario.evaluation import evaluate_research_model as _evaluation
from robot_learning.scenario.observations import reach_observation
from robot_learning.scenario.reward import reach_reward

GOLDENS = json.loads(
    (Path(__file__).resolve().parent / "scenario_goldens.json").read_text(
        encoding="utf-8"
    )
)


class ZeroPolicy:
    def predict(self, obs, deterministic=True):
        del obs, deterministic
        return np.zeros(2, dtype=np.float32), None


def test_seeded_reset_produces_the_same_target_and_observation():
    env = make_training_env()
    obs, _ = env.reset(seed=42)

    assert [float(value) for value in env.data.mocap_pos[0]] == GOLDENS["reset_target"]
    assert [float(value) for value in obs] == GOLDENS["reset_observation"]


def test_identical_state_produces_the_identical_observation():
    env = make_training_env()
    env.reset(seed=7)
    env.data.qpos[:] = [0.3, -0.4]
    env.data.qvel[:] = [0.1, -0.2]
    mujoco.mj_forward(env.model, env.data)

    observation = [float(value) for value in reach_observation(env.data)]
    assert observation == GOLDENS["observation_from_state"]


def test_environment_transitions_are_unchanged():
    env = make_training_env()
    env.reset(seed=42)

    for index, expected in enumerate(GOLDENS["steps"]):
        action = np.array([0.4 - 0.1 * index, -0.3 + 0.05 * index], dtype=np.float64)
        observation, reward, terminated, truncated, info = env.step(action)

        assert [float(value) for value in observation] == expected["observation"]
        assert float(reward) == expected["reward"]
        assert bool(terminated) is expected["terminated"]
        assert bool(truncated) is expected["truncated"]
        assert float(info["distance"]) == expected["distance"]
        assert int(info["held_steps"]) == expected["held_steps"]


def test_reward_scalar_is_numerically_unchanged():
    for case in GOLDENS["rewards"]:
        result = reach_reward(*case["args"], **case["kwargs"])
        assert result.total == case["total"], case

    for case in GOLDENS["rewards_with_action"]:
        result = reach_reward(0.05, 0.04, 0.03, action=np.array(case["action"]))
        assert result.total == case["total"], case


def test_reward_components_reconstruct_the_scalar():
    for case in GOLDENS["rewards"]:
        result = reach_reward(*case["args"], **case["kwargs"])
        assert sum(result.components.values()) == pytest.approx(result.total)


def test_research_evaluation_preserves_current_metrics(monkeypatch):
    monkeypatch.setattr(
        "robot_learning.scenario.evaluation.load_policy",
        lambda path, algorithm=None: ZeroPolicy(),
    )
    monkeypatch.setattr(
        "robot_learning.scenario.evaluation.load_observation_normalizer",
        lambda path: None,
    )

    result = evaluate_research_model(Path("stub-model.zip"), episodes=2, seed=1000)

    assert result.pop("model") == "stub-model.zip"
    traces = [
        episode.pop("distance_trace_cm", None) for episode in result["episode_results"]
    ]
    assert result == GOLDENS["research_evaluation"]
    for trace, expected in zip(traces, GOLDENS["research_evaluation_distance_traces"]):
        if expected is None:
            assert trace is None
            continue
        assert len(trace) == expected["steps"]
        assert trace[0] == expected["first"]
        assert trace[-1] == expected["last"]


def test_the_boundary_exposes_the_scenario_implementation():
    assert evaluate_research_model is _evaluation


def test_final_benchmark_adapter_adds_an_explicit_goal_verdict(monkeypatch):
    from robot_learning.scenario import final_benchmark as adapter

    def protected(success_percent):
        def evaluate(path, algorithm=None, progress_callback=None):
            del path, algorithm, progress_callback
            return {
                "schema_version": 1,
                "episodes": 200,
                "seed": 1000,
                "success_percent": success_percent,
            }

        return evaluate

    monkeypatch.setattr(adapter, "_protected_evaluate_final_model", protected(98.0))
    passing = adapter.evaluate_final_model(Path("stub-model.zip"))
    assert passing["goal_reached"] is True
    assert passing["success_percent"] == 98.0

    monkeypatch.setattr(adapter, "_protected_evaluate_final_model", protected(97.9))
    assert adapter.evaluate_final_model(Path("stub-model.zip"))["goal_reached"] is False
