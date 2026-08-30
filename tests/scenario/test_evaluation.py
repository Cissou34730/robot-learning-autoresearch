"""Researcher-owned tests for the scenario research evaluation.

The scenario owns a minimal factual baseline plus `research_evidence`, an opaque
channel it may fill with anything. Changing what that channel carries is a
normal research change.
"""

from types import SimpleNamespace

import numpy as np
import pytest

from robot_learning.scenario import evaluation as scenario_evaluation
from robot_learning.scenario import summarize_research_evaluations

BASELINE_EPISODE_FIELDS = {
    "episode",
    "episode_seed",
    "success",
    "reward_total",
    "steps",
    "terminated",
    "truncated",
}

# Predefined behavioral diagnostics the default evaluator no longer preselects.
REMOVED_PREDEFINED_DIAGNOSTICS = (
    "aggregate_metrics",
    "metrics",
    "actions",
    "reward_components",
    "held_steps",
    "distance",
    "target_radius_cm",
    "target_angle_degrees",
    "failed_episode_progress",
    "failure_diagnostics",
    "distance_trace_cm",
)


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
                "reward_total": 1.0,
                "steps": 100,
                "terminated": outcome,
                "truncated": not outcome,
            }
            for episode, outcome in enumerate(outcomes)
        ],
        "research_evidence": {},
    }


def test_evaluation_respects_the_requested_panel(stub_policy):
    result = scenario_evaluation.evaluate_research_model(
        stub_policy, episodes=2, seed=7
    )

    assert result["episodes"] == 2
    assert result["seed"] == 7
    assert [episode["episode_seed"] for episode in result["episode_results"]] == [7, 8]


def test_evaluation_exposes_only_the_minimal_baseline(stub_policy):
    result = scenario_evaluation.evaluate_research_model(
        stub_policy, episodes=1, seed=11
    )
    episode = result["episode_results"][0]

    assert set(episode) == BASELINE_EPISODE_FIELDS
    assert episode["steps"] > 0
    assert episode["terminated"] is False
    assert episode["truncated"] is True
    assert result["research_evidence"] == {}


@pytest.mark.parametrize("field", REMOVED_PREDEFINED_DIAGNOSTICS)
def test_evaluation_emits_no_predefined_diagnostics(stub_policy, field):
    result = scenario_evaluation.evaluate_research_model(
        stub_policy, episodes=1, seed=5
    )

    assert field not in result
    assert field not in result["episode_results"][0]


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


def test_evaluation_summary_pools_the_actual_panel_sizes():
    summary = summarize_research_evaluations(
        [evaluation(3000, [True, False]), evaluation(4000, [True, True, True, True])]
    )

    assert summary["episodes"] == 6
    assert summary["seed_count"] == 2
    assert summary["pooled_success_percent"] == pytest.approx(100 * 5 / 6)
    assert summary["worst_seed_success_percent"] == pytest.approx(50.0)
    assert summary["seed_success_percent"] == {"3000": 50.0, "4000": 100.0}


def test_research_evaluation_does_not_depend_on_the_final_threshold():
    summary = summarize_research_evaluations([evaluation(3000, [True, True])])

    assert "seeds_passing_98_percent" not in summary
    assert not hasattr(scenario_evaluation, "FINAL_SUCCESS_PERCENT")


def test_evaluation_summary_does_not_rebuild_scenario_diagnosis():
    summary = summarize_research_evaluations([evaluation(3000, [True, False])])

    for removed in ("failure_diagnostics", "failed_episode_progress"):
        assert removed not in summary
