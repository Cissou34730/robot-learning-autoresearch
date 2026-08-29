import json

import pytest

from research.run_experiment import (
    apply_previous_result_decision,
    execute_pending_evaluations,
    execute_pending_final_benchmark,
    experiment_family,
    parameter_change_records,
    plan_previous_result_decision,
    training_budget,
    training_parent,
    validate_experiment_semantics,
    validate_training_proposal,
)
from robot_learning.scenario import (
    summarize_research_evaluations as summarize_evaluations,
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


def test_paired_comparison_rejects_incompatible_episode_panels():
    with pytest.raises(ValueError, match="identical episodes"):
        paired_comparison(
            [evaluation(3000, [True, False])],
            [evaluation(4000, [True, False])],
        )


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
    monkeypatch.setattr("research.run_experiment.EVALUATION_REQUEST_PATH", request_path)
    monkeypatch.setattr("research.run_experiment.CANDIDATE_ROOT", tmp_path)
    monkeypatch.setattr("research.run_experiment.BASELINE_PENDING_PATH", baseline_path)

    def skip_result_recording(result):
        del result

    def skip_result_commit(index, change):
        del index, change

    monkeypatch.setattr("research.run_experiment.append_result", skip_result_recording)
    monkeypatch.setattr("research.run_experiment.commit_result", skip_result_commit)

    calls: list[int] = []

    def interrupt_second(artifact, seed, **kwargs):
        del artifact, kwargs
        calls.append(seed)
        if len(calls) == 2:
            raise KeyboardInterrupt
        return evaluation(seed, [True, False])

    monkeypatch.setattr("research.run_experiment.evaluate_artifact", interrupt_second)
    assert execute_pending_evaluations() == 130
    assert calls == [1000, 2000]

    request_path.unlink()
    resumed_calls: list[int] = []

    def finish(artifact, seed, **kwargs):
        del artifact, kwargs
        resumed_calls.append(seed)
        return evaluation(seed, [True, True])

    monkeypatch.setattr("research.run_experiment.evaluate_artifact", finish)
    assert execute_pending_evaluations() == 0
    assert resumed_calls == [2000]
    final_state = json.loads(state_path.read_text(encoding="utf-8"))
    candidate = final_state["pending_researcher_decision"]["candidates"][0]
    assert len(candidate["evaluations"]) == 2
    assert candidate["summary"]["episodes"] == 4


def test_evaluation_deduplication_ignores_label(monkeypatch, tmp_path):
    state_path = tmp_path / "research_state.json"
    request_path = tmp_path / "evaluation_request.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "accepted_artifact": "accepted",
                "pending_evaluation_request": {
                    "experiment": 4,
                    "candidates": [
                        {
                            "name": "checkpoint",
                            "artifact": "archive/checkpoint",
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
                    "result": {
                        "index": 4,
                        "change": "baseline",
                        "hypothesis": "measure",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    request_path.write_text(
        json.dumps(
            {
                "experiment": 4,
                "evaluations": [
                    {
                        "candidate": "checkpoint",
                        "episodes": 2,
                        "seed": 1000,
                        "label": "first",
                    },
                    {
                        "candidate": "checkpoint",
                        "episodes": 2,
                        "seed": 1000,
                        "label": "renamed",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.run_experiment.STATE_PATH", state_path)
    monkeypatch.setattr("research.run_experiment.EVALUATION_REQUEST_PATH", request_path)
    monkeypatch.setattr("research.run_experiment.CANDIDATE_ROOT", tmp_path)
    monkeypatch.setattr(
        "research.run_experiment.BASELINE_PENDING_PATH", tmp_path / "BASELINE_PENDING"
    )

    def skip_result_recording(result):
        del result

    monkeypatch.setattr("research.run_experiment.append_result", skip_result_recording)
    calls = []

    def record_evaluation(artifact, seed, **kwargs):
        del artifact, kwargs
        calls.append(seed)
        return evaluation(seed, [True, False])

    monkeypatch.setattr("research.run_experiment.evaluate_artifact", record_evaluation)

    assert execute_pending_evaluations() == 0
    assert calls == [1000]
    final_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert (
        len(final_state["pending_researcher_decision"]["candidates"][0]["evaluations"])
        == 1
    )


def test_researcher_can_request_evaluations_across_two_rounds(monkeypatch, tmp_path):
    state_path = tmp_path / "research_state.json"
    request_path = tmp_path / "evaluation_request.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "accepted_artifact": "accepted",
                "pending_evaluation_request": {
                    "experiment": 4,
                    "candidates": [
                        {
                            "name": "checkpoint",
                            "artifact": "archive/checkpoint",
                            "timesteps": 100,
                            "evaluations": [],
                        }
                    ],
                    "champion_available": False,
                    "parameters": {},
                    "initialization": "fresh",
                    "training_budget_steps": 100,
                    "parent_training_steps": 0,
                    "result": {"index": 4, "change": "measure", "hypothesis": "test"},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.run_experiment.ROOT", tmp_path)
    monkeypatch.setattr("research.run_experiment.STATE_PATH", state_path)
    monkeypatch.setattr("research.run_experiment.EVALUATION_REQUEST_PATH", request_path)
    monkeypatch.setattr("research.run_experiment.CANDIDATE_ROOT", tmp_path)
    monkeypatch.setattr(
        "research.run_experiment.BASELINE_PENDING_PATH", tmp_path / "BASELINE_PENDING"
    )
    monkeypatch.setattr("research.run_experiment.append_result", lambda result: None)

    calls: list[int] = []

    def record_evaluation(artifact, seed, **kwargs):
        del artifact, kwargs
        calls.append(seed)
        return evaluation(seed, [True, False])

    monkeypatch.setattr("research.run_experiment.evaluate_artifact", record_evaluation)
    request_path.write_text(
        json.dumps(
            {
                "experiment": 4,
                "evaluations": [
                    {"candidate": "checkpoint", "episodes": 2, "seed": 1000},
                ],
                "need_more_evidence": True,
            }
        ),
        encoding="utf-8",
    )

    assert execute_pending_evaluations() == 0
    first_round = json.loads(state_path.read_text(encoding="utf-8"))
    assert calls == [1000]
    assert first_round["pending_researcher_decision"] is None
    assert [
        item["seed"]
        for item in first_round["pending_evaluation_request"]["partial_evaluations"]
    ] == [1000]

    request_path.write_text(
        json.dumps(
            {
                "experiment": 4,
                "evaluations": [
                    {
                        "candidate": "checkpoint",
                        "episodes": 2,
                        "seed": 1000,
                        "label": "reused A",
                    },
                    {
                        "candidate": "checkpoint",
                        "episodes": 2,
                        "seed": 2000,
                        "label": "new B",
                    },
                ],
                "need_more_evidence": False,
            }
        ),
        encoding="utf-8",
    )

    assert execute_pending_evaluations() == 0
    second_round = json.loads(state_path.read_text(encoding="utf-8"))
    candidate = second_round["pending_researcher_decision"]["candidates"][0]
    assert calls == [1000, 2000]
    assert [item["seed"] for item in candidate["evaluations"]] == [1000, 2000]
    assert candidate["summary"]["episodes"] == 4


def test_pending_result_requires_an_explicit_researcher_decision():
    state = {
        "pending_researcher_decision": {
            "experiment": 7,
            "candidates": [],
            "champion_available": True,
        }
    }

    with pytest.raises(ValueError, match="previous_result_decision"):
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
    monkeypatch.setattr("research.run_experiment.GOAL_PATH", tmp_path / "GOAL_REACHED")
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

    assert (
        experiment_family(
            proposal,
            "training",
            [],
            ["robot_learning/rewards/reach_reward.py"],
        )
        == "reward.outside_boundary_penalty"
    )


def _artifact(path):
    path.mkdir(parents=True, exist_ok=True)
    for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
        (path / filename).write_bytes(b"artifact")
    return path


def _decision_state(candidate_artifact, measurements):
    return {
        "accepted_artifact": "accepted",
        "accepted_training_steps": 0,
        "pending_researcher_decision": {
            "experiment": 8,
            "candidates": [
                {
                    "name": "candidate",
                    "artifact": candidate_artifact,
                    "timesteps": 120_000,
                    "evaluations": measurements,
                    "summary": summarize_evaluations(measurements),
                }
            ],
            "champion_available": False,
            "parameters": {"algorithm": {"name": "ppo"}},
            "initialization": "fresh",
            "training_budget_steps": 120_000,
        },
    }


def _lineage_decision():
    return {
        "previous_result_decision": {
            "experiment": 8,
            "continue_from": "candidate",
            "reason": "Measured policy is the useful parent.",
            "code": {"action": "keep", "reason": "Keep the measured method."},
        }
    }


def test_final_benchmark_runs_after_separate_lineage_resolution(monkeypatch, tmp_path):
    _artifact(tmp_path / "archive" / "candidate")
    monkeypatch.setattr("research.run_experiment.ROOT", tmp_path)
    monkeypatch.setattr("research.run_experiment.ACCEPTED_DIR", tmp_path / "accepted")
    monkeypatch.setattr("research.run_experiment.STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr("research.run_experiment.GOAL_PATH", tmp_path / "GOAL_REACHED")

    state = _decision_state("archive/candidate", [evaluation(1000, [True] * 2)])
    request = _lineage_decision()
    request["previous_result_decision"]["request_final_benchmark"] = True
    calls = []
    monkeypatch.setattr(
        "research.run_experiment.evaluate_final_model",
        lambda model: (
            calls.append(model)
            or {
                "episodes": 200,
                "seed": 1000,
                "success_percent": 100.0,
                "goal_reached": True,
            }
        ),
    )
    assert not apply_previous_result_decision(request, state)
    assert calls == []
    assert state["pending_researcher_decision"] is None
    assert state["pending_final_benchmark"]["artifact"] == "accepted"
    assert not (tmp_path / "GOAL_REACHED").exists()

    assert execute_pending_final_benchmark() == 0
    assert calls == [tmp_path / "accepted" / "model.zip"]
    persisted = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert persisted["official_metrics"]["success_percent"] == 100.0
    assert persisted["pending_final_benchmark"] is None
    assert (tmp_path / "GOAL_REACHED").exists()


def test_pending_final_benchmark_survives_failure_and_failed_result(
    monkeypatch, tmp_path
):
    _artifact(tmp_path / "archive" / "candidate")
    monkeypatch.setattr("research.run_experiment.ROOT", tmp_path)
    monkeypatch.setattr("research.run_experiment.ACCEPTED_DIR", tmp_path / "accepted")
    state_path = tmp_path / "state.json"
    monkeypatch.setattr("research.run_experiment.STATE_PATH", state_path)
    monkeypatch.setattr("research.run_experiment.GOAL_PATH", tmp_path / "GOAL_REACHED")
    state = _decision_state("archive/candidate", [evaluation(1000, [True] * 2)])
    request = _lineage_decision()
    request["previous_result_decision"]["request_final_benchmark"] = True
    assert not apply_previous_result_decision(request, state)

    def failed_benchmark(model):
        del model
        raise RuntimeError("benchmark crashed")

    monkeypatch.setattr(
        "research.run_experiment.evaluate_final_model", failed_benchmark
    )
    with pytest.raises(RuntimeError, match="benchmark crashed"):
        execute_pending_final_benchmark()
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert (
        persisted["pending_final_benchmark"]["fingerprint"]
        == state["pending_final_benchmark"]["fingerprint"]
    )
    assert persisted["official_metrics"] is None

    monkeypatch.setattr(
        "research.run_experiment.evaluate_final_model",
        lambda model: {
            "episodes": 200,
            "seed": 1000,
            "success_percent": 97.5,
            "goal_reached": False,
        },
    )
    assert execute_pending_final_benchmark() == 0
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["pending_final_benchmark"] is None
    assert persisted["official_metrics"]["success_percent"] == 97.5
    assert not (tmp_path / "GOAL_REACHED").exists()


def test_identical_artifact_cannot_repeat_final_benchmark(monkeypatch, tmp_path):
    _artifact(tmp_path / "archive" / "candidate")
    monkeypatch.setattr("research.run_experiment.ROOT", tmp_path)
    monkeypatch.setattr("research.run_experiment.RESEARCH_DIR", tmp_path / "research")
    state = _decision_state("archive/candidate", [evaluation(44, [True, False])])
    decision = _lineage_decision()
    decision["previous_result_decision"]["request_final_benchmark"] = True
    fingerprint = plan_previous_result_decision(decision, state)["selected_fingerprint"]
    state["official_benchmark_artifact"] = fingerprint

    with pytest.raises(ValueError, match="already received"):
        plan_previous_result_decision(decision, state)


def test_research_evaluation_request_rejects_official_benchmark(monkeypatch, tmp_path):
    state_path = tmp_path / "research_state.json"
    request_path = tmp_path / "evaluation_request.json"
    state = {
        "schema_version": 2,
        "accepted_artifact": "accepted",
        "pending_evaluation_request": {
            "experiment": 8,
            "candidates": [
                {
                    "name": "candidate",
                    "artifact": "archive/candidate",
                    "timesteps": 1,
                    "evaluations": [],
                }
            ],
            "champion_available": False,
            "parameters": {},
            "initialization": "fresh",
            "training_budget_steps": 1,
            "parent_training_steps": 0,
            "result": {"index": 8, "change": "measure", "hypothesis": "test"},
        },
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    request_path.write_text(
        json.dumps(
            {
                "experiment": 8,
                "evaluations": [
                    {
                        "candidate": "candidate",
                        "episodes": 200,
                        "seed": 1000,
                        "official_benchmark": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.run_experiment.STATE_PATH", state_path)
    monkeypatch.setattr("research.run_experiment.EVALUATION_REQUEST_PATH", request_path)
    with pytest.raises(ValueError, match="not valid"):
        execute_pending_evaluations()


def test_continuation_and_replication_allow_unchanged_methods():
    validate_experiment_semantics({}, "continuation", "transfer", None, [], False)
    with pytest.raises(ValueError, match="continuation requires transfer"):
        validate_experiment_semantics({}, "continuation", "fresh", None, [], False)

    validate_experiment_semantics(
        {"training_seed": 19, "replication_of": 12},
        "replication",
        "fresh",
        None,
        [],
        False,
    )
    with pytest.raises(ValueError, match="explicit training_seed"):
        validate_experiment_semantics({}, "replication", "fresh", None, [], False)

    with pytest.raises(ValueError, match="human-owned final benchmark"):
        validate_experiment_semantics(
            {},
            "training",
            "transfer",
            {"ppo": {"n_steps": 2048}},
            ["robot_learning/benchmark/final_contract.py"],
            False,
        )


def test_training_proposal_has_no_postmortem_or_lineage_payload():
    proposal = {
        "kind": "training",
        "family": "reward.hold",
        "hypothesis": "test",
        "change": "test",
        "initialization": "transfer",
        "training_parent": "accepted",
        "training_seed": 0,
        "params": {},
    }
    validate_training_proposal(proposal, baseline=False)
    proposal["previous_experiment_postmortem"] = {}
    with pytest.raises(ValueError, match="lineage-only"):
        validate_training_proposal(proposal, baseline=False)


def test_champion_can_be_retained_before_replacement(monkeypatch, tmp_path):
    champion = _artifact(tmp_path / "accepted")
    challenger = _artifact(tmp_path / "archive" / "candidate")
    challenger_model = challenger.joinpath("model.zip").read_bytes()
    monkeypatch.setattr("research.run_experiment.ROOT", tmp_path)
    monkeypatch.setattr("research.run_experiment.RESEARCH_DIR", tmp_path / "research")
    monkeypatch.setattr("research.run_experiment.ACCEPTED_DIR", tmp_path / "accepted")
    monkeypatch.setattr("research.run_experiment.STATE_PATH", tmp_path / "state.json")
    state = _decision_state("archive/candidate", [evaluation(44, [True, False])])
    state.update(
        {
            "accepted_artifact": "accepted",
            "accepted_training_steps": 55,
            "accepted_parameters": {"algorithm": {"name": "ppo"}},
        }
    )
    state["pending_researcher_decision"]["champion_available"] = True
    decision = _lineage_decision()
    decision["previous_result_decision"]["retain"] = [
        {
            "candidate": "champion",
            "id": "pre-change-policy",
            "reason": "Useful contrast.",
        }
    ]
    assert not apply_previous_result_decision(decision, state)
    retained = state["retained_lineages"][0]
    assert retained["id"] == "pre-change-policy"
    assert (
        tmp_path / retained["artifact"] / "model.zip"
    ).read_bytes() == champion.joinpath("model.zip").read_bytes()
    assert (tmp_path / "accepted" / "model.zip").read_bytes() == challenger_model
    identifier, parent, steps = training_parent(
        {"training_parent": "pre-change-policy"}, state, "transfer"
    )
    assert (identifier, parent, steps) == (
        "pre-change-policy",
        tmp_path / retained["artifact"],
        55,
    )


def test_removing_retained_lineage_keeps_history_but_removes_artifact(
    monkeypatch, tmp_path
):
    _artifact(tmp_path / "archive" / "candidate")
    retained = _artifact(
        tmp_path / "research" / "checkpoints" / "retained" / "obsolete"
    )
    monkeypatch.setattr("research.run_experiment.ROOT", tmp_path)
    monkeypatch.setattr("research.run_experiment.RESEARCH_DIR", tmp_path / "research")
    monkeypatch.setattr("research.run_experiment.ACCEPTED_DIR", tmp_path / "accepted")
    monkeypatch.setattr("research.run_experiment.STATE_PATH", tmp_path / "state.json")
    state = _decision_state("archive/candidate", [evaluation(44, [True, False])])
    state["retained_lineages"] = [
        {
            "id": "obsolete",
            "artifact": "research/checkpoints/retained/obsolete",
            "origin_experiment": 2,
        }
    ]
    decision = _lineage_decision()
    decision["previous_result_decision"]["remove_retained"] = ["obsolete"]
    assert not apply_previous_result_decision(decision, state)
    assert state["retained_lineages"] == []
    assert retained.joinpath("artifact.json").exists()
    assert not retained.joinpath("model.zip").exists()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda decision: decision["previous_result_decision"].update(
            {"continue_from": "missing"}
        ),
        lambda decision: decision["previous_result_decision"]["code"].update(
            {"action": "revise"}
        ),
        lambda decision: decision["previous_result_decision"].update(
            {"retain": [{"candidate": "missing", "id": "alternative", "reason": "bad"}]}
        ),
        lambda decision: decision["previous_result_decision"].update(
            {"remove_retained": ["missing"]}
        ),
    ],
)
def test_invalid_lineage_decisions_mutate_nothing(monkeypatch, tmp_path, mutate):
    candidate = _artifact(tmp_path / "archive" / "candidate")
    accepted = _artifact(tmp_path / "accepted")
    state_path = tmp_path / "state.json"
    monkeypatch.setattr("research.run_experiment.ROOT", tmp_path)
    monkeypatch.setattr("research.run_experiment.ACCEPTED_DIR", accepted)
    monkeypatch.setattr("research.run_experiment.RESEARCH_DIR", tmp_path / "research")
    monkeypatch.setattr("research.run_experiment.STATE_PATH", state_path)
    state = _decision_state("archive/candidate", [evaluation(44, [True, False])])
    state["retained_lineages"] = []
    before_state = json.dumps(state, sort_keys=True)
    before_accepted = accepted.joinpath("model.zip").read_bytes()
    before_candidate = candidate.joinpath("model.zip").read_bytes()
    decision = _lineage_decision()
    mutate(decision)
    with pytest.raises((TypeError, ValueError)):
        apply_previous_result_decision(decision, state)
    assert json.dumps(state, sort_keys=True) == before_state
    assert accepted.joinpath("model.zip").read_bytes() == before_accepted
    assert candidate.joinpath("model.zip").read_bytes() == before_candidate


def test_conflicting_retention_is_rejected_before_mutation(monkeypatch, tmp_path):
    _artifact(tmp_path / "archive" / "candidate")
    accepted = _artifact(tmp_path / "accepted")
    monkeypatch.setattr("research.run_experiment.ROOT", tmp_path)
    monkeypatch.setattr("research.run_experiment.ACCEPTED_DIR", accepted)
    monkeypatch.setattr("research.run_experiment.RESEARCH_DIR", tmp_path / "research")
    state = _decision_state("archive/candidate", [evaluation(44, [True, False])])
    state["retained_lineages"] = [
        {"id": "alternative", "artifact": "old", "origin_experiment": 1}
    ]
    decision = _lineage_decision()
    decision["previous_result_decision"]["retain"] = [
        {"candidate": "candidate", "id": "alternative", "reason": "bad"}
    ]
    with pytest.raises(ValueError, match="do not retain|conflicting"):
        plan_previous_result_decision(decision, state)
    assert accepted.joinpath("model.zip").exists()


def test_discarded_candidates_keep_history_but_lose_heavyweight_files(
    monkeypatch, tmp_path
):
    _artifact(tmp_path / "archive" / "selected")
    discarded = _artifact(tmp_path / "archive" / "discarded")
    (discarded / "replay_buffer.pkl").write_bytes(b"large")
    monkeypatch.setattr("research.run_experiment.ROOT", tmp_path)
    monkeypatch.setattr("research.run_experiment.ACCEPTED_DIR", tmp_path / "accepted")
    monkeypatch.setattr("research.run_experiment.STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr("research.run_experiment.GOAL_PATH", tmp_path / "GOAL_REACHED")
    measurements = [evaluation(44, [True, False])]
    state = _decision_state("archive/selected", measurements)
    state["pending_researcher_decision"]["candidates"].append(
        {
            "name": "discarded",
            "artifact": "archive/discarded",
            "timesteps": 120_000,
            "evaluations": measurements,
            "summary": summarize_evaluations(measurements),
        }
    )
    assert not apply_previous_result_decision(_lineage_decision(), state)
    assert (discarded / "artifact.json").exists()
    assert not (discarded / "model.zip").exists()
    assert not (discarded / "vecnormalize.pkl").exists()
    assert not (discarded / "replay_buffer.pkl").exists()
