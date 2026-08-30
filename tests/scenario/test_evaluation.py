"""Researcher-owned tests for the scenario research evaluation.

The scenario owns which signals are observed and how they are mechanically
aggregated. Changing those observations is a normal research change.
"""

from types import SimpleNamespace

import numpy as np
import pytest

from robot_learning.scenario import evaluation as scenario_evaluation
from robot_learning.scenario import summarize_research_evaluations


class ZeroPolicy:
    def predict(self, observation, deterministic=False):
        del observation, deterministic
        return np.zeros(2), None


class ScriptedEnv:
    """Reports a scenario outcome independently of Gymnasium termination."""

    def __init__(self, is_success: bool, terminated: bool, truncated: bool):
        self.is_success = is_success
        self.terminated = terminated
        self.truncated = truncated
        self.data = SimpleNamespace(mocap_pos=[[0.1, 0.0, 0.0]])

    def reset(self, seed=None):
        del seed
        return np.zeros(2), {}

    def step(self, action):
        del action
        info = {
            "distance": 0.5,
            "held_steps": 0,
            "is_success": self.is_success,
            "reward_components": {"progress": 1.0},
        }
        return np.zeros(2), 1.0, self.terminated, self.truncated, info


@pytest.fixture
def stub_policy(monkeypatch, tmp_path):
    monkeypatch.setattr(
        scenario_evaluation, "load_policy", lambda path, algorithm: ZeroPolicy()
    )
    monkeypatch.setattr(
        scenario_evaluation, "load_observation_normalizer", lambda path: None
    )
    return tmp_path / "model.zip"


def evaluation(seed: int, outcomes: list[bool]) -> dict:
    return {
        "episodes": len(outcomes),
        "seed": seed,
        "success_percent": 100 * sum(outcomes) / len(outcomes),
        "episode_results": [
            {
                "episode": episode,
                "episode_seed": seed + episode,
                "success": outcome,
                "steps": 100,
                "terminated": outcome,
                "truncated": not outcome,
                "target_radius_cm": 10.0,
                "target_angle_degrees": 0.0,
                "reward_total": 1.0,
                "reward_components": {"progress": 1.0},
                "metrics": {},
                "actions": {},
            }
            for episode, outcome in enumerate(outcomes)
        ],
    }


def test_evaluation_respects_the_requested_panel(stub_policy):
    result = scenario_evaluation.evaluate_research_model(
        stub_policy, episodes=2, seed=7
    )

    assert result["episodes"] == 2
    assert result["seed"] == 7
    assert [episode["episode_seed"] for episode in result["episode_results"]] == [7, 8]


def test_evaluation_keeps_per_episode_observations(stub_policy):
    result = scenario_evaluation.evaluate_research_model(
        stub_policy, episodes=1, seed=11
    )
    episode = result["episode_results"][0]

    assert episode["steps"] > 0
    assert episode["terminated"] is False
    assert episode["truncated"] is True
    assert episode["target_radius_cm"] > 0
    assert set(episode["metrics"]) == set(scenario_evaluation.OBSERVED_STEP_SIGNALS)
    assert set(episode["metrics"]["distance"]) == {
        "count",
        "mean",
        "std",
        "min",
        "max",
        "final",
    }
    assert episode["metrics"]["distance"]["count"] == episode["steps"]
    assert set(episode["actions"]) == {"action_0", "action_1"}


def test_evaluation_sums_whatever_reward_components_exist(stub_policy, monkeypatch):
    from robot_learning.scenario import environment as environment_module
    from robot_learning.scenario.reward import RewardResult

    monkeypatch.setattr(
        environment_module,
        "reach_reward",
        lambda *args, **kwargs: RewardResult(
            total=0.5, components={"invented_term": 0.25}
        ),
    )

    result = scenario_evaluation.evaluate_research_model(
        stub_policy, episodes=1, seed=3
    )
    episode = result["episode_results"][0]

    assert episode["reward_components"] == {
        "invented_term": pytest.approx(0.25 * episode["steps"])
    }
    assert episode["reward_total"] == pytest.approx(0.5 * episode["steps"])
    assert set(result["aggregate_metrics"]["reward_components"]) == {"invented_term"}


def test_evaluation_emits_no_hold_diagnostics(stub_policy):
    result = scenario_evaluation.evaluate_research_model(
        stub_policy, episodes=1, seed=5
    )

    assert "failed_episode_progress" not in result
    assert "failure_diagnostics" not in result
    assert "distance_trace_cm" not in result["episode_results"][0]


@pytest.mark.parametrize(
    ("is_success", "terminated", "truncated"),
    [
        # Terminating for a non-success reason is not a task outcome.
        (False, True, False),
        # Succeeding without terminating is still a task outcome.
        (True, False, True),
    ],
)
def test_success_is_read_from_the_scenario_signal_not_termination(
    stub_policy, monkeypatch, is_success, terminated, truncated
):
    monkeypatch.setattr(
        scenario_evaluation,
        "make_training_env",
        lambda: ScriptedEnv(is_success, terminated, truncated),
    )

    result = scenario_evaluation.evaluate_research_model(
        stub_policy, episodes=1, seed=0
    )
    episode = result["episode_results"][0]

    assert episode["success"] is is_success
    assert episode["terminated"] is terminated
    assert episode["truncated"] is truncated
    assert result["success_percent"] == (100.0 if is_success else 0.0)


def test_evaluation_aggregates_mechanically(stub_policy):
    result = scenario_evaluation.evaluate_research_model(
        stub_policy, episodes=2, seed=5
    )
    aggregate = result["aggregate_metrics"]

    assert set(aggregate["steps"]) == {"mean", "std", "min", "max"}
    assert set(aggregate["metrics"]) == set(scenario_evaluation.OBSERVED_STEP_SIGNALS)
    assert set(aggregate["actions"]) == {"action_0", "action_1"}
    assert result["success_percent"] == 0.0


def test_evaluation_summary_pools_the_actual_panel_sizes():
    summary = summarize_research_evaluations(
        [evaluation(3000, [True, False]), evaluation(4000, [True, True, True, True])]
    )

    assert summary["episodes"] == 6
    assert summary["seed_count"] == 2
    assert summary["pooled_success_percent"] == pytest.approx(100 * 5 / 6)
    assert summary["worst_seed_success_percent"] == pytest.approx(50.0)
    assert summary["seed_success_percent"] == {"3000": 50.0, "4000": 100.0}


def test_evaluation_summary_does_not_rebuild_scenario_diagnosis():
    summary = summarize_research_evaluations([evaluation(3000, [True, False])])

    for removed in ("failure_diagnostics", "failed_episode_progress"):
        assert removed not in summary
