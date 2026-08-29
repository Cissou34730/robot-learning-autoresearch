import json

import pytest

from research.run_experiment import (
    apply_previous_result_decision,
    execute_pending_evaluations,
    experiment_family,
    parameter_change_records,
    record_previous_postmortem,
    summarize_evaluations,
    training_budget,
)
from robot_learning.training.comparison import (
    exact_mcnemar_pvalue,
    paired_comparison,
)


def evaluation(seed: int, outcomes: list[bool]) -> dict:
    failures = outcomes.count(False)
    return {
        "episodes": len(outcomes),
        "seed": seed,
        "success_percent": 100 * sum(outcomes) / len(outcomes),
        "failed_episode_progress": {
            "failed_episodes": failures,
            "longest_consecutive_steps_mean": 99.0 if failures else 100.0,
            "best_window_inside_steps_mean": 99.0 if failures else 100.0,
            "best_window_excess_cm_mean": 0.01 if failures else 0.0,
            "required_steps": 100,
        },
        "episode_results": [
            {
                "episode": episode,
                "episode_seed": seed + episode,
                "success": outcome,
                "target_radius_cm": 10.0,
                "target_angle_degrees": 0.0,
                "longest_consecutive_steps": 100 if outcome else 99,
                "best_window_inside_steps": 100 if outcome else 99,
                "best_window_excess_cm": 0.0 if outcome else 0.01,
                "final_distance_cm": 0.5,
            }
            for episode, outcome in enumerate(outcomes)
        ],
    }


def test_paired_comparison_uses_identical_episode_outcomes():
    candidate = [evaluation(3000, [True, True, True, True, True, True])]
    champion = [evaluation(3000, [False, False, False, False, False, False])]

    comparison = paired_comparison(candidate, champion)

    assert comparison["candidate_wins"] == 6
    assert comparison["reference_wins"] == 0
    assert comparison["success_delta_percent"] == 100.0
    assert comparison["exact_p_value"] == pytest.approx(0.03125)


def test_evaluation_summary_keeps_failed_target_diagnostics():
    summary = summarize_evaluations([evaluation(3000, [True, False])])

    assert summary["failure_diagnostics"] == [
        {
            "episode": 1,
            "episode_seed": 3001,
            "success": False,
            "target_radius_cm": 10.0,
            "target_angle_degrees": 0.0,
            "longest_consecutive_steps": 99,
            "best_window_inside_steps": 99,
            "best_window_excess_cm": 0.01,
            "final_distance_cm": 0.5,
        }
    ]


def test_exact_p_value_is_one_without_discordant_episodes():
    assert exact_mcnemar_pvalue(0, 0) == 1.0


def test_requested_evaluations_resume_without_repeating_completed_work(
    monkeypatch, tmp_path
):
    state_path = tmp_path / "research_state.json"
    request_path = tmp_path / "evaluation_request.json"
    baseline_path = tmp_path / "BASELINE_PENDING"
    state = {
        "schema_version": 2,
        "accepted_artifact": "accepted",
        "pending_evaluation_request": {
            "experiment": 4,
            "candidates": [
                {
                    "name": "checkpoint-100",
                    "artifact": "archive/checkpoint-100",
                    "timesteps": 100,
                    "evaluations": [],
                }
            ],
            "champion_available": False,
            "parameters": {},
            "initialization": "fresh",
            "training_budget_steps": 100,
            "parent_training_steps": 0,
            "baseline": True,
            "result": {"index": 4, "change": "baseline", "hypothesis": "measure"},
        },
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    request_path.write_text(
        json.dumps(
            {
                "experiment": 4,
                "evaluations": [
                    {
                        "candidate": "checkpoint-100",
                        "episodes": 2,
                        "seed": 1000,
                        "label": "first panel",
                    },
                    {
                        "candidate": "checkpoint-100",
                        "episodes": 2,
                        "seed": 2000,
                        "label": "second panel",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.run_experiment.ROOT", tmp_path)
    monkeypatch.setattr("research.run_experiment.STATE_PATH", state_path)
    monkeypatch.setattr(
        "research.run_experiment.EVALUATION_REQUEST_PATH", request_path
    )
    monkeypatch.setattr("research.run_experiment.CANDIDATE_ROOT", tmp_path)
    monkeypatch.setattr("research.run_experiment.BASELINE_PENDING_PATH", baseline_path)
    monkeypatch.setattr("research.run_experiment.append_result", lambda _result: None)
    monkeypatch.setattr(
        "research.run_experiment.commit_result", lambda _index, _change: None
    )

    calls: list[int] = []

    def interrupt_second(_artifact, seed, **_kwargs):
        calls.append(seed)
        if len(calls) == 2:
            raise KeyboardInterrupt
        return evaluation(seed, [True, False])

    monkeypatch.setattr(
        "research.run_experiment.evaluate_artifact", interrupt_second
    )
    assert execute_pending_evaluations() == 130
    assert calls == [1000, 2000]

    request_path.unlink()
    resumed_calls: list[int] = []

    def finish(_artifact, seed, **_kwargs):
        resumed_calls.append(seed)
        return evaluation(seed, [True, True])

    monkeypatch.setattr("research.run_experiment.evaluate_artifact", finish)
    assert execute_pending_evaluations() == 0
    assert resumed_calls == [2000]
    final_state = json.loads(state_path.read_text(encoding="utf-8"))
    candidate = final_state["pending_researcher_decision"]["candidates"][0]
    assert len(candidate["evaluations"]) == 2
    assert candidate["summary"]["episodes"] == 4


def test_pending_result_requires_an_explicit_researcher_decision():
    state = {
        "pending_researcher_decision": {
            "experiment": 7,
            "candidates": [],
            "champion_available": True,
        }
    }

    with pytest.raises(TypeError, match="previous_result_decision"):
        apply_previous_result_decision({}, state)


def test_researcher_can_select_an_archived_candidate_as_next_lineage(
    monkeypatch, tmp_path
):
    candidate = tmp_path / "archive" / "candidate-2"
    candidate.mkdir(parents=True)
    for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
        (candidate / filename).write_bytes(b"artifact")
    summary = summarize_evaluations([evaluation(3000, [True, False])])
    state = {
        "accepted_artifact": "accepted",
        "accepted_training_steps": 0,
        "pending_researcher_decision": {
            "experiment": 7,
            "candidates": [
                {
                    "name": "candidate-2",
                    "artifact": "archive/candidate-2",
                    "summary": summary,
                }
            ],
            "champion_available": False,
            "parameters": {"algorithm": {"name": "ppo"}},
            "initialization": "fresh",
            "training_budget_steps": 120_000,
        },
    }
    monkeypatch.setattr("research.run_experiment.ROOT", tmp_path)
    monkeypatch.setattr("research.run_experiment.ACCEPTED_DIR", tmp_path / "accepted")
    monkeypatch.setattr(
        "research.run_experiment.STATE_PATH", tmp_path / "research_state.json"
    )
    monkeypatch.setattr(
        "research.run_experiment.GOAL_PATH", tmp_path / "GOAL_REACHED"
    )
    monkeypatch.setattr(
        "research.run_experiment.evaluate_artifact",
        lambda *_args, **_kwargs: {
            "seed": 1000,
            "episodes": 200,
            "success_percent": 50.0,
        },
    )

    reached = apply_previous_result_decision(
        {
            "previous_result_decision": {
                "experiment": 7,
                "continue_from": "candidate-2",
                "reason": "It is the most useful measured lineage.",
                "code": {
                    "action": "keep",
                    "reason": "The learning change remains the useful parent.",
                },
            }
        },
        state,
    )

    assert not reached
    assert (tmp_path / "accepted" / "model.zip").read_bytes() == b"artifact"
    assert state["accepted_metrics"] == summary
    assert state["accepted_training_steps"] == 120_000
    assert state["pending_researcher_decision"] is None


def test_runner_uses_the_human_defined_budget_for_all_initializations():
    assert training_budget(120_000, "transfer", False, 720_000) == 120_000
    assert training_budget(120_000, "fresh", False, 720_000) == 120_000
    assert training_budget(120_000, "fresh", True, 720_000) == 120_000


def test_experiment_card_records_exact_nested_parameter_changes():
    previous = {"ppo": {"n_steps": 4096, "learning_rate": 5e-5}}
    overrides = {"ppo": {"n_steps": 16384}}

    changes = parameter_change_records(previous, overrides)

    assert changes == [{"path": "ppo.n_steps", "before": 4096, "after": 16384}]
    assert experiment_family({}, "training", changes, []) == "ppo.n_steps"


def test_declared_code_family_is_stable_across_numeric_variants():
    proposal = {"family": "reward.outside_boundary_penalty"}

    assert experiment_family(
        proposal,
        "training",
        [],
        ["robot_learning/rewards/reach_reward.py"],
    ) == "reward.outside_boundary_penalty"


def test_previous_postmortem_is_required_and_recorded(monkeypatch, tmp_path):
    results = tmp_path / "results.jsonl"
    postmortems = tmp_path / "postmortems.md"
    results.write_text(json.dumps({"index": 7}) + "\n", encoding="utf-8")
    postmortems.write_text("# Research postmortems\n", encoding="utf-8")
    monkeypatch.setattr("research.run_experiment.RESULTS_PATH", results)
    monkeypatch.setattr("research.run_experiment.RESEARCH_DIR", tmp_path)

    with pytest.raises(TypeError, match="previous_experiment_postmortem"):
        record_previous_postmortem({}, baseline=False)

    record_previous_postmortem(
        {
            "previous_experiment_postmortem": {
                "experiment": 7,
                "result": "No promotion.",
                "behavior": "Candidate tied the champion.",
                "learned": "Do not repeat the same optimizer change.",
                "next_class": "Inspect failure geometry.",
            }
        },
        baseline=False,
    )

    memory = postmortems.read_text(encoding="utf-8")
    assert "## Experiment 7" in memory
    assert "Inspect failure geometry" in memory
