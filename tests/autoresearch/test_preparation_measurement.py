"""Issue #49: measurements can be requested while preparing the next experiment.

Preparation is where the next experiment, its parent and its initialization are
chosen, yet measurement used to be available only during post-training analysis.
A preparation-phase ``research/evaluation_request.json`` may now measure saved
lineages (``working``, ``best_known``, ``developing_method`` or a retained ID); it may not name the
candidates of an experiment that has not run, and it must omit the ``experiment``
field. The completed round returns to preparation, scoped to the upcoming
experiment, and is carried into that experiment's analysis when it starts.
"""

import json
from pathlib import Path

import pytest

from research import build_research_brief as brief
from research import run_experiment
from research import runner_repository as repository
from research.runner_protocol import (
    preparation_measurement_context,
    validate_preparation_evaluation_request,
)


def _artifact(path: Path, model: bytes = b"model") -> Path:
    path.mkdir(parents=True)
    (path / "model.zip").write_bytes(model)
    (path / "artifact.json").write_text("{}", encoding="utf-8")
    (path / "policy_runtime.pkl").write_bytes(b"runtime")
    return path


def _lineage(artifact: str, fingerprint: str) -> dict:
    return {
        "artifact": artifact,
        "fingerprint": fingerprint,
        "origin_experiment": 3,
        "candidate": "checkpoint",
        "parameters": {},
        "scientific_commit": None,
        "training_steps": 120_000,
        "evaluation_artifacts": [],
        "reason": "Saved lineage available for preparation measurement.",
    }


def _configure(monkeypatch, tmp_path: Path) -> tuple[Path, Path, Path, dict]:
    research = tmp_path / "research"
    research.mkdir()
    state_path = research / "research_state.json"
    request_path = research / "evaluation_request.json"
    proposal_path = research / "proposal.json"
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.RESEARCH_DIR", research)
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr(
        "research.runner_paths.RESULTS_PATH", research / "results.jsonl"
    )
    monkeypatch.setattr("research.runner_paths.LOG_PATH", research / "EXPERIMENTS.md")
    monkeypatch.setattr("research.runner_paths.EVALUATION_REQUEST_PATH", request_path)
    monkeypatch.setattr("research.runner_paths.PROPOSAL_PATH", proposal_path)
    monkeypatch.setattr(
        "research.runner_paths.EVALUATION_DIR", research / "evaluations"
    )
    monkeypatch.setattr(
        "research.runner_paths.POSTMORTEM_PATH", research / "postmortems.md"
    )
    monkeypatch.setattr(
        "research.run_experiment.validate_research_delta", lambda state: []
    )
    monkeypatch.setattr(repository, "publish_campaign_laboratory", lambda state: None)
    monkeypatch.setattr(
        "research.runner_protocol.evaluation_semantics_fingerprint", lambda: "test"
    )
    artifact = _artifact(tmp_path / "archive" / "working")
    fingerprint = repository.artifact_fingerprint(artifact)
    state = {
        "schema_version": 4,
        "campaign": {"id": "campaign", "started_at": "now", "base_commit": "base"},
        "working_lineage": _lineage("archive/working", fingerprint),
        "best_known_lineage": None,
        "retained_lineages": [],
        "last_experiment": 3,
        "last_allocated_experiment": 3,
        "pending_analysis": None,
        "pending_evaluation_request": None,
        "pending_researcher_decision": None,
        "pending_closure_operation": None,
        "pending_final_benchmark": None,
        "pending_campaign_conclusion": None,
        "campaign_experiment_counters": {"campaign": 3},
        "campaign_inquiry_counters": {"campaign": 1},
        "last_allocated_inquiry": 1,
        "last_inquiry": 0,
        "active_inquiry": {"id": 1, "status": "active"},
        "pending_inquiry_operation": None,
        "principal_investigator_session": None,
        "campaign_lab": None,
        "preparation_conclusion_only": None,
        "preparation_measurement": None,
        "official_benchmark_artifact": None,
        "terminal_campaign_status": None,
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    (research / "postmortems.md").write_text(
        "## campaign / Scientific strategy\n\n"
        "**Current synthesis:** Current evidence is mixed.\n\n"
        "**Lessons and limits:** The available panel is limited.\n\n"
        "**Competing explanations:** Control and optimization remain plausible.\n\n"
        "**Decision frontier:** Whether their predicted behavior differs on the "
        "measured panel.\n",
        encoding="utf-8",
    )
    return state_path, request_path, proposal_path, state


def _request(candidate: str = "working", seed: int = 10) -> dict:
    return {
        "question": "Is the saved lineage a suitable parent for the next experiment?",
        "reason": "The parent choice needs a measured panel before proposing.",
        "measurements": [
            {
                "instrument": "research_evaluation",
                "candidate": candidate,
                "episodes": 2,
                "seed": seed,
                "selection": "the saved lineage the parent decision would use",
                "omitted_alternative": None,
            }
        ],
    }


def _evaluator(calls: list[int]):
    def evaluate(artifact, seed, output_path, **kwargs):
        del artifact, kwargs
        calls.append(seed)
        payload = {
            "episodes": 2,
            "seed": seed,
            "success_percent": 50.0,
            "episode_results": [
                {"episode": 0, "episode_seed": seed, "success": True},
                {"episode": 1, "episode_seed": seed + 1, "success": False},
            ],
        }
        output_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    return evaluate


# --- request validation ----------------------------------------------------


def test_preparation_request_resolves_to_a_lineage_only_context(monkeypatch, tmp_path):
    _, _, _, state = _configure(monkeypatch, tmp_path)

    context = validate_preparation_evaluation_request(_request(), state)

    assert context["preparation"] is True
    assert context["candidates"] == []
    assert context["champion_available"] is False
    assert context["experiment"] == 4
    assert context["inquiry_id"] == 1
    assert context["evaluation_rounds"] == []
    # Forecasting an identity does not consume it.
    assert state["campaign_experiment_counters"]["campaign"] == 3
    assert "preparation_measurement" not in context


def test_preparation_request_rejects_experiment_candidates(monkeypatch, tmp_path):
    _, _, _, state = _configure(monkeypatch, tmp_path)

    with pytest.raises(ValueError, match="unknown measurement candidate"):
        validate_preparation_evaluation_request(
            _request(candidate="experiment-4"), state
        )


def test_preparation_request_rejects_an_experiment_field(monkeypatch, tmp_path):
    _, _, _, state = _configure(monkeypatch, tmp_path)
    request = _request()
    request["experiment"] = 3

    with pytest.raises(ValueError, match="must omit experiment"):
        validate_preparation_evaluation_request(request, state)


def test_preparation_request_rejects_when_no_saved_lineage_exists(
    monkeypatch, tmp_path
):
    _, _, _, state = _configure(monkeypatch, tmp_path)
    state["working_lineage"] = None

    with pytest.raises(ValueError, match="no saved lineages"):
        validate_preparation_evaluation_request(_request(), state)


def test_preparation_request_rejected_while_analysis_is_pending(monkeypatch, tmp_path):
    _, _, _, state = _configure(monkeypatch, tmp_path)
    state["pending_analysis"] = {"experiment": 3}

    with pytest.raises(ValueError, match="post-training analysis is pending"):
        validate_preparation_evaluation_request(_request(), state)


def test_preparation_request_rejected_when_budget_is_exhausted(monkeypatch, tmp_path):
    _, _, _, state = _configure(monkeypatch, tmp_path)
    state["preparation_conclusion_only"] = True

    with pytest.raises(ValueError, match="budget is exhausted"):
        validate_preparation_evaluation_request(_request(), state)


def test_preparation_measurement_context_is_non_mutating(monkeypatch, tmp_path):
    _, _, _, state = _configure(monkeypatch, tmp_path)

    before = json.loads(json.dumps(state))
    preparation_measurement_context(state)

    assert state == before


def test_preparation_measurement_context_adopts_a_legacy_null_inquiry(
    monkeypatch, tmp_path
):
    _, _, _, state = _configure(monkeypatch, tmp_path)
    state["preparation_measurement"] = {
        "experiment": 4,
        "inquiry_id": None,
        "rounds": [{"round": 1, "experiment": 4, "status": "completed"}],
        "partial_evaluations": [],
        "partial_task_reference_evaluations": [],
    }

    context = preparation_measurement_context(state)

    assert context["inquiry_id"] == 1
    assert context["evaluation_rounds"] == [
        {"round": 1, "experiment": 4, "status": "completed"}
    ]


# --- execution -------------------------------------------------------------


def test_preparation_measurement_returns_to_preparation(monkeypatch, tmp_path):
    state_path, request_path, _, _ = _configure(monkeypatch, tmp_path)
    calls: list[int] = []
    monkeypatch.setattr(
        "research.runner_execution.evaluate_artifact", _evaluator(calls)
    )
    request_path.write_text(json.dumps(_request()), encoding="utf-8")
    results_path = tmp_path / "research" / "results.jsonl"

    assert run_experiment.execute_pending_evaluations() == 0

    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["pending_analysis"] is None
    assert persisted["pending_evaluation_request"] is None
    assert persisted["last_experiment"] == 3
    assert persisted["last_allocated_experiment"] == 3
    assert persisted["last_verdict"] == "preparation measurement complete"
    ledger = persisted["preparation_measurement"]
    assert ledger["experiment"] == 4
    assert ledger["inquiry_id"] == 1
    assert [record["round"] for record in ledger["rounds"]] == [1]
    assert ledger["rounds"][0]["status"] == "completed"
    assert [
        item["seed"] for item in ledger["rounds"][0]["results"]["research_evaluations"]
    ] == [10]
    assert [item["seed"] for item in ledger["partial_evaluations"]] == [10]
    assert (
        ledger["partial_evaluations"][0]["model_fingerprint"]
        == persisted["working_lineage"]["fingerprint"]
    )
    assert calls == [10]
    assert not results_path.exists() or results_path.read_text(encoding="utf-8") == ""
    assert not request_path.exists()


def test_preparation_rounds_accumulate_with_provenance(monkeypatch, tmp_path):
    state_path, request_path, _, _ = _configure(monkeypatch, tmp_path)
    calls: list[int] = []
    monkeypatch.setattr(
        "research.runner_execution.evaluate_artifact", _evaluator(calls)
    )

    request_path.write_text(json.dumps(_request()), encoding="utf-8")
    assert run_experiment.execute_pending_evaluations() == 0
    request_path.write_text(json.dumps(_request()), encoding="utf-8")
    assert run_experiment.execute_pending_evaluations() == 0

    ledger = json.loads(state_path.read_text(encoding="utf-8"))[
        "preparation_measurement"
    ]
    assert ledger["experiment"] == 4
    assert [record["round"] for record in ledger["rounds"]] == [1, 2]
    # The identical panel is resolved from the accumulated ledger, not re-run,
    # and the second round records the round that first resolved it.
    assert calls == [10]
    reused = ledger["rounds"][1]["results"]["research_evaluations"]
    assert reused[0]["status"] == "reused"
    assert reused[0]["reused_from_round"] == 1
    assert len(ledger["partial_evaluations"]) == 1


def test_preparation_measurement_retires_a_stale_alias(monkeypatch, tmp_path):
    state_path, request_path, _, _ = _configure(monkeypatch, tmp_path)
    calls: list[int] = []
    monkeypatch.setattr(
        "research.runner_execution.evaluate_artifact", _evaluator(calls)
    )
    request_path.write_text(json.dumps(_request()), encoding="utf-8")
    assert run_experiment.execute_pending_evaluations() == 0

    # Repoint the alias at a different artifact: the recorded measurement no
    # longer describes the lineage and must not be reused.
    replacement = _artifact(tmp_path / "archive" / "working-v2", model=b"model-v2")
    replacement_fingerprint = repository.artifact_fingerprint(replacement)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["working_lineage"]["artifact"] = "archive/working-v2"
    state["working_lineage"]["fingerprint"] = replacement_fingerprint
    state_path.write_text(json.dumps(state), encoding="utf-8")

    request_path.write_text(json.dumps(_request()), encoding="utf-8")
    assert run_experiment.execute_pending_evaluations() == 0

    ledger = json.loads(state_path.read_text(encoding="utf-8"))[
        "preparation_measurement"
    ]
    # The stale ledger is retired: numbering restarts and the model is re-measured.
    assert [record["round"] for record in ledger["rounds"]] == [1]
    assert calls == [10, 10]
    assert ledger["partial_evaluations"][0]["model_fingerprint"] == (
        replacement_fingerprint
    )


def test_preparation_measurement_rejects_an_experiment_field_on_execution(
    monkeypatch, tmp_path
):
    _, request_path, _, _ = _configure(monkeypatch, tmp_path)
    request = _request()
    request["experiment"] = 4
    request_path.write_text(json.dumps(request), encoding="utf-8")

    with pytest.raises(ValueError, match="must omit experiment"):
        run_experiment.execute_pending_evaluations()


def test_researcher_code_error_reopens_without_recording_scientific_failure(
    monkeypatch, tmp_path
):
    state_path, request_path, _, _ = _configure(monkeypatch, tmp_path)
    scenario_path = tmp_path / "robot_learning" / "scenario" / "environment.py"
    scenario_path.parent.mkdir(parents=True)
    scenario_path.write_text("VALUE = 1\n", encoding="utf-8")
    relative = "robot_learning/scenario/environment.py"
    monkeypatch.setattr(
        "research.run_experiment.validate_research_delta",
        lambda state: [relative],
    )

    def fail_from_researcher_code(*args, **kwargs):
        del args, kwargs
        raise RuntimeError(
            "evaluation failed:\n"
            "Traceback (most recent call last):\n"
            f'  File "{scenario_path}", line 12, in step\n'
            "AttributeError: native API member is unavailable"
        )

    monkeypatch.setattr(
        "research.runner_execution.evaluate_artifact",
        fail_from_researcher_code,
    )
    request_path.write_text(json.dumps(_request()), encoding="utf-8")

    assert (
        run_experiment.execute_pending_evaluations()
        == run_experiment.RESEARCHER_IMPLEMENTATION_ERROR_EXIT
    )

    pending = json.loads(state_path.read_text(encoding="utf-8"))[
        "pending_evaluation_request"
    ]
    assert pending["implementation_error"]["causal_path"] == relative
    assert pending["implementation_repair_attempts"] == 0
    assert pending["partial_evaluations"] == []
    assert pending["evaluation_rounds"][-1]["results"]["research_evaluations"] == []
    assert request_path.exists()


def test_external_runtime_error_stops_without_reopening_the_researcher(
    monkeypatch, tmp_path
):
    state_path, request_path, _, _ = _configure(monkeypatch, tmp_path)
    scenario_path = tmp_path / "robot_learning" / "scenario" / "environment.py"
    scenario_path.parent.mkdir(parents=True)
    scenario_path.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(
        "research.run_experiment.validate_research_delta",
        lambda state: ["robot_learning/scenario/environment.py"],
    )

    def fail_in_dependency(*args, **kwargs):
        del args, kwargs
        raise RuntimeError(
            "evaluation failed:\n"
            "Traceback (most recent call last):\n"
            f'  File "{scenario_path}", line 12, in step\n'
            '  File "C:\\runtime\\site-packages\\mujoco\\bindings.py", '
            "line 20, in call\n"
            "RuntimeError: native failure"
        )

    monkeypatch.setattr(
        "research.runner_execution.evaluate_artifact",
        fail_in_dependency,
    )
    request_path.write_text(json.dumps(_request()), encoding="utf-8")

    with pytest.raises(RuntimeError, match="native failure"):
        run_experiment.execute_pending_evaluations()

    pending = json.loads(state_path.read_text(encoding="utf-8"))[
        "pending_evaluation_request"
    ]
    assert "implementation_error" not in pending
    assert pending["evaluation_rounds"][-1]["results"]["research_evaluations"] == []


def test_implementation_repair_is_bounded_and_freezes_the_request(
    monkeypatch, tmp_path
):
    state_path, request_path, _, _ = _configure(monkeypatch, tmp_path)
    request_path.write_text(json.dumps(_request()), encoding="utf-8")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["pending_evaluation_request"] = {
        "implementation_error": {
            "causal_path": "robot_learning/scenario/environment.py",
            "error": "AttributeError",
            "request_fingerprint": repository.file_fingerprint(request_path),
        },
        "implementation_repair_attempts": 0,
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")

    assert run_experiment.record_implementation_repair_attempt() == 0
    request_path.write_text(json.dumps(_request(seed=11)), encoding="utf-8")
    assert run_experiment.complete_implementation_repair() == 1
    assert run_experiment.record_implementation_repair_attempt() == 0
    assert run_experiment.record_implementation_repair_attempt() == 1

    pending = json.loads(state_path.read_text(encoding="utf-8"))[
        "pending_evaluation_request"
    ]
    assert pending["implementation_repair_attempts"] == 2
    assert "implementation_error" in pending


def test_valid_implementation_repair_clears_only_the_operational_error(
    monkeypatch, tmp_path
):
    state_path, request_path, _, _ = _configure(monkeypatch, tmp_path)
    request_path.write_text(json.dumps(_request()), encoding="utf-8")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["pending_evaluation_request"] = {
        "implementation_error": {
            "causal_path": "robot_learning/scenario/environment.py",
            "error": "AttributeError",
            "request_fingerprint": repository.file_fingerprint(request_path),
        },
        "implementation_repair_attempts": 0,
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")

    assert run_experiment.record_implementation_repair_attempt() == 0
    assert run_experiment.complete_implementation_repair() == 0

    pending = json.loads(state_path.read_text(encoding="utf-8"))[
        "pending_evaluation_request"
    ]
    assert "implementation_error" not in pending
    assert pending["implementation_repair_attempts"] == 1


def test_legacy_operational_failures_are_removed_from_measurement_results():
    active_round = {
        "results": {
            "research_evaluations": [
                {"candidate": "working", "status": "failed"},
                {"candidate": "reference", "status": "reused"},
            ],
            "task_reference_evaluations": [
                {"candidate": "working", "status": "failed"}
            ],
        }
    }

    assert run_experiment._remove_operational_failures(active_round)
    assert active_round["results"]["research_evaluations"] == [
        {"candidate": "reference", "status": "reused"}
    ]
    assert active_round["results"]["task_reference_evaluations"] == []


def test_pending_preparation_adopts_harness_head_without_restoring_science(
    monkeypatch, tmp_path
):
    state_path, request_path, _, _ = _configure(monkeypatch, tmp_path)
    scenario_path = tmp_path / "robot_learning" / "scenario" / "environment.py"
    scenario_path.parent.mkdir(parents=True)
    scenario_path.write_text("RESEARCHER_CHANGE = True\n", encoding="utf-8")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["pending_scientific_parent"] = "old-head"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    def adopt_harness_head(current):
        current["pending_scientific_parent"] = "new-harness-head"
        return "new-harness-head"

    def validate_delta(current):
        assert current["pending_scientific_parent"] == "new-harness-head"
        return ["robot_learning/scenario/environment.py"]

    monkeypatch.setattr(
        "research.run_experiment.reanchor_phase_parent", adopt_harness_head
    )
    monkeypatch.setattr(
        "research.run_experiment.validate_research_delta", validate_delta
    )
    monkeypatch.setattr(
        "research.runner_execution.evaluate_artifact", _evaluator([])
    )
    request_path.write_text(json.dumps(_request()), encoding="utf-8")

    assert run_experiment.execute_pending_evaluations() == 0
    assert scenario_path.read_text(encoding="utf-8") == "RESEARCHER_CHANGE = True\n"


def test_preparation_measurement_preflight_accepts_a_request_and_rejects_a_conflict(
    monkeypatch, tmp_path
):
    state_path, request_path, proposal_path, _ = _configure(monkeypatch, tmp_path)
    request_path.write_text(json.dumps(_request()), encoding="utf-8")

    assert run_experiment.check_preparation_deliverable() == 0

    proposal_path.write_text(json.dumps({"hypothesis": "next"}), encoding="utf-8")
    assert run_experiment.check_preparation_deliverable() == 1
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["pending_evaluation_request"] is None


# --- transfer and brief association ----------------------------------------


def test_training_transfers_the_preparation_ledger_into_analysis():
    state = {
        "preparation_measurement": {
            "experiment": 4,
            "inquiry_id": 2,
            "rounds": [{"round": 1, "results": {}}],
            "partial_evaluations": [{"candidate": "working"}],
            "partial_task_reference_evaluations": [],
        }
    }
    result: dict = {"inquiry_id": 2}
    pending: dict = {}

    run_experiment.transfer_preparation_measurements(state, result, pending, 4)

    assert result["preparation_evaluation_rounds"] == [{"round": 1, "results": {}}]
    assert result["preparation_evaluations"] == [{"candidate": "working"}]
    assert pending["preparation_evaluation_rounds"] == [{"round": 1, "results": {}}]
    assert state["preparation_measurement"] is None


def test_training_leaves_a_ledger_for_another_experiment_untouched():
    state = {
        "preparation_measurement": {
            "experiment": 5,
            "inquiry_id": 3,
            "rounds": [],
        }
    }
    result: dict = {"inquiry_id": 2}
    pending: dict = {}

    run_experiment.transfer_preparation_measurements(state, result, pending, 4)

    assert result == {"inquiry_id": 2}
    assert pending == {}
    assert state["preparation_measurement"] == {
        "experiment": 5,
        "inquiry_id": 3,
        "rounds": [],
    }


def test_measurement_only_inquiry_closes_without_allocating_an_experiment(
    monkeypatch, tmp_path
):
    state_path, _, proposal_path, state = _configure(monkeypatch, tmp_path)
    state["preparation_measurement"] = {
        "experiment": 4,
        "inquiry_id": 1,
        "rounds": [{"round": 1, "status": "completed"}],
        "partial_evaluations": [],
        "partial_task_reference_evaluations": [],
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    proposal_path.write_text(
        json.dumps(
            {
                "inquiry_decision": {
                    "action": "close",
                    "outcome": "The measured behavior rules out the current explanation.",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(repository, "publish_campaign_laboratory", lambda current: None)
    monkeypatch.setattr(run_experiment, "_publish_runner_memory", lambda message: None)

    assert (
        run_experiment.resolve_inquiry_decision(
            json.loads(proposal_path.read_text(encoding="utf-8"))
        )
        == 0
    )

    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["active_inquiry"] is None
    assert persisted["last_inquiry"] == 1
    assert persisted["last_experiment"] == 3
    assert persisted["last_allocated_experiment"] == 3
    history = [
        json.loads(line)
        for line in (tmp_path / "research" / "results.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert history[0]["record_type"] == "inquiry"
    assert history[0]["inquiry_id"] == 1
    assert history[0]["measurement_rounds"][0]["round"] == 1
    assert "Inquiry outcomes" in (tmp_path / "research" / "EXPERIMENTS.md").read_text(
        encoding="utf-8"
    )


def test_closing_inquiry_releases_its_unpromoted_experimental_lineage(
    monkeypatch, tmp_path
):
    state_path, _, proposal_path, state = _configure(monkeypatch, tmp_path)
    experimental = _artifact(tmp_path / "archive" / "inquiry", b"experimental")
    state["inquiry_lineage"] = {
        **_lineage(
            "archive/inquiry",
            repository.artifact_fingerprint(experimental),
        ),
        "inquiry_id": 1,
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    proposal_path.write_text(
        json.dumps(
            {
                "inquiry_decision": {
                    "action": "close",
                    "outcome": "The experimental branch no longer warrants continuation.",
                    "developing_method": {
                        "action": "abandon",
                        "reason": "Its evidence does not justify preserving the branch.",
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(repository, "publish_campaign_laboratory", lambda current: None)
    monkeypatch.setattr(run_experiment, "_publish_runner_memory", lambda message: None)

    assert (
        run_experiment.resolve_inquiry_decision(
            json.loads(proposal_path.read_text(encoding="utf-8"))
        )
        == 0
    )

    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["inquiry_lineage"] is None
    assert not experimental.joinpath("model.zip").exists()
    assert experimental.joinpath("artifact.json").is_file()
    inquiry = next(
        item
        for item in repository.history_records()
        if item.get("record_type") == "inquiry"
    )
    assert inquiry["developing_method"]["candidate"] == "checkpoint"


@pytest.mark.parametrize("action", ["promote", "retain"])
def test_closing_inquiry_can_preserve_its_experimental_lineage(
    monkeypatch, tmp_path, action
):
    state_path, _, proposal_path, state = _configure(monkeypatch, tmp_path)
    experimental = _artifact(tmp_path / "archive" / "inquiry", b"experimental")
    state["inquiry_lineage"] = {
        **_lineage(
            "archive/inquiry",
            repository.artifact_fingerprint(experimental),
        ),
        "inquiry_id": 1,
    }
    disposition = {
        "action": action,
        "reason": "The branch remains scientifically useful.",
    }
    if action == "retain":
        disposition["id"] = "inquiry-one-method"
    proposal_path.write_text(
        json.dumps(
            {
                "inquiry_decision": {
                    "action": "close",
                    "outcome": "The inquiry reached a bounded conclusion.",
                    "developing_method": disposition,
                }
            }
        ),
        encoding="utf-8",
    )
    state_path.write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(repository, "publish_campaign_laboratory", lambda current: None)
    monkeypatch.setattr(run_experiment, "_publish_runner_memory", lambda message: None)

    assert (
        run_experiment.resolve_inquiry_decision(
            json.loads(proposal_path.read_text(encoding="utf-8"))
        )
        == 0
    )

    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    preserved = (
        persisted["working_lineage"]
        if action == "promote"
        else persisted["retained_lineages"][-1]
    )
    assert preserved["candidate"] == "checkpoint"
    assert "inquiry_id" not in preserved
    assert experimental.joinpath("model.zip").is_file()


def test_inquiry_recovery_does_not_duplicate_history(monkeypatch, tmp_path):
    state_path, _, proposal_path, state = _configure(monkeypatch, tmp_path)
    proposal_path.write_text(
        json.dumps(
            {
                "inquiry_decision": {
                    "action": "close",
                    "outcome": "A bounded inquiry outcome.",
                }
            }
        ),
        encoding="utf-8",
    )
    state["pending_inquiry_operation"] = {
        "action": "close",
        "outcome": "A bounded inquiry outcome.",
        "inquiry_id": 1,
        "progress": "planned",
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    calls = 0

    def publish_once(message):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("interrupted publication")

    monkeypatch.setattr(run_experiment, "_publish_runner_memory", publish_once)
    with pytest.raises(RuntimeError, match="interrupted"):
        run_experiment.complete_inquiry_decision(repository.read_state())

    run_experiment.complete_inquiry_decision(repository.read_state())
    history = repository.history_records()
    assert (
        len([record for record in history if record.get("record_type") == "inquiry"])
        == 1
    )
    assert not proposal_path.exists()


def test_legacy_preparation_ledger_is_adopted_by_active_inquiry(
    monkeypatch, tmp_path
):
    state_path, proposal_path, _, state = _configure(monkeypatch, tmp_path)
    legacy_round = {
        "round": 1,
        "experiment": 4,
        "status": "completed",
        "results": {"research_evaluations": []},
    }
    state["preparation_measurement"] = {
        "experiment": 4,
        "rounds": [legacy_round],
        "partial_evaluations": [{"candidate": "working"}],
        "partial_task_reference_evaluations": [],
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    proposal_path.write_text(
        json.dumps(
            {
                "inquiry_decision": {
                    "action": "close",
                    "outcome": "The legacy evidence resolved this inquiry.",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(repository, "publish_campaign_laboratory", lambda current: None)
    monkeypatch.setattr(run_experiment, "_publish_runner_memory", lambda message: None)

    assert (
        run_experiment.resolve_inquiry_decision(
            json.loads(proposal_path.read_text(encoding="utf-8"))
        )
        == 0
    )

    record = next(
        item
        for item in repository.history_records()
        if item.get("record_type") == "inquiry"
    )
    assert record["measurement_rounds"] == [legacy_round]
    assert record["preparation_evaluations"] == [{"candidate": "working"}]


def _brief_state() -> dict:
    return {
        "campaign": {"id": "campaign", "started_at": "now", "base_commit": "base"},
        "last_experiment": 3,
        "last_allocated_experiment": 3,
        "campaign_experiment_counters": {"campaign": 3},
        "preparation_measurement": {
            "experiment": 4,
            "rounds": [
                {
                    "round": 1,
                    "experiment": 4,
                    "question": "is the parent suitable",
                    "reason": "parent choice needs evidence",
                    "status": "completed",
                    "results": {
                        "research_evaluations": [
                            {
                                "candidate": "working",
                                "seed": 10,
                                "episodes": 2,
                                "success_percent": 90.0,
                                "selection": "candidate parent",
                                "evaluation_artifact": "research/evaluations/e.json",
                            }
                        ]
                    },
                }
            ],
            "partial_evaluations": [],
        },
    }


def _completed_experiment_3() -> dict:
    return {
        "index": 3,
        "evaluation_rounds": [
            {
                "round": 1,
                "experiment": 3,
                "status": "completed",
                "results": {
                    "research_evaluations": [
                        {
                            "candidate": "checkpoint-3",
                            "seed": 900,
                            "episodes": 2,
                            "success_percent": 10.0,
                        }
                    ]
                },
            }
        ],
    }


def test_brief_leads_with_inquiry_lineage_and_surfaces_laboratory_outputs():
    state = _brief_state()
    state.update(
        {
            "schema_version": 4,
            "working_lineage": {
                **_lineage("archive/working", "working-fingerprint"),
                "candidate": "working-checkpoint",
            },
            "best_known_lineage": None,
            "retained_lineages": [],
            "active_inquiry": {"id": 2, "status": "active"},
            "inquiry_lineage": {
                **_lineage("archive/inquiry", "inquiry-fingerprint"),
                "candidate": "experimental-checkpoint",
                "inquiry_id": 2,
            },
            "principal_investigator_session": None,
            "campaign_lab": {
                "commit": "a" * 40,
                "fingerprint": "b" * 64,
                "manifest": [
                    {
                        "path": "research/lab/settling_analysis.json",
                        "fingerprint": "c" * 64,
                    }
                ],
            },
            "pending_analysis": None,
            "pending_final_benchmark": None,
            "terminal_campaign_status": None,
        }
    )
    rendered = brief._render_v4_research_brief(
        state,
        [],
        [],
        "## campaign / Scientific strategy\n\n"
        "**Current synthesis:** A synthesis.\n\n"
        "**Lessons and limits:** A limit.\n\n"
        "**Competing explanations:** Two explanations.\n\n"
        "**Decision frontier:** A distinction.",
        "campaign",
        "base",
        "current method",
        {},
    )

    assert rendered.index("## Causal research map") < rendered.index(
        "## Inquiry continuity"
    )
    assert rendered.index("### Developing method for this inquiry") < rendered.index(
        "## Latest experiment"
    )
    assert rendered.index("## Development evidence index") < rendered.index(
        "## Current lineages and scientific recipes"
    )
    assert "`research/lab/settling_analysis.json`" in rendered


def test_preparation_rounds_render_for_the_upcoming_experiment():
    rendered = "\n".join(
        brief._v4_measurement_rounds_section(
            _brief_state(), [_completed_experiment_3()], None
        )
    )

    assert "Preparation measurement rounds for the active inquiry" in rendered
    assert "working" in rendered
    assert "success 90.00%" in rendered
    # The upcoming experiment's round is never shown as the previous one's.
    assert "checkpoint-3" not in rendered
    assert (
        "Completed measurement rounds from the most recent experiment" not in rendered
    )


def test_activity_record_counts_the_live_preparation_ledger():
    """A campaign concluded from preparation still performed those measurements.

    The ledger of an experiment that never ran has no durable record, so an
    activity tally read from the records alone hid the very rounds the
    conclusion was taken on, understated the executed episodes, and presented an
    already-consumed panel as still available.
    """
    state = _brief_state()
    state["preparation_measurement"]["partial_evaluations"] = [
        {
            "candidate": "working",
            "instrument": "research_evaluation",
            "seed": 10,
            "episodes": 2,
            "model_fingerprint": "abc",
            "metrics": {
                "successes": 1,
                "episodes": 2,
                "seed": 10,
                "evaluation_artifact": "research/evaluations/e.json",
            },
        }
    ]

    rendered = "\n".join(
        brief._v4_activity_record_section(state, [_completed_experiment_3()], None)
    )
    without_ledger = dict(state, preparation_measurement=None)
    baseline = "\n".join(
        brief._v4_activity_record_section(
            without_ledger, [_completed_experiment_3()], None
        )
    )

    # The unran preparation experiment is work, not an experiment.
    assert "Training experiments: 1." in rendered
    assert "Training experiments: 1." in baseline
    assert "Evaluation rounds: 2." in rendered
    assert "Instrument executions: 1 research_evaluation" in rendered
    assert "2 episode executions" in rendered
    assert "intervals consumed: 10\u201311." in rendered
    # Without the ledger the same campaign looks like it measured nothing.
    assert "Instrument executions: 0 research_evaluation" in baseline
    assert "intervals consumed: none." in baseline


def test_fresh_restart_line_counts_discretionary_restarts_only():
    """The brief reports how much of a campaign left the baseline recipe.

    Across this repository's campaign history, the only campaign-level quantity
    that separated the converging campaigns from the stalled ones was how many
    experiments trained from zero on a changed recipe instead of continuing the
    baseline lineage. It was absent from the brief. The automatic experiment-1
    baseline is always fresh and is excluded, because it is not a choice.
    """
    stalled = [
        {"index": 1, "initialization": "fresh"},
        {"index": 2, "initialization": "transfer"},
        {"index": 3, "initialization": "transfer"},
    ]
    converging = stalled + [
        {"index": 4, "initialization": "fresh"},
        {"index": 5, "initialization": "fresh"},
    ]

    assert (
        brief._fresh_restart_line(stalled)
        == "- Fresh restarts after the baseline: none (0 of 3 experiments)."
    )
    assert brief._fresh_restart_line(converging) == (
        "- Fresh restarts after the baseline: experiment 4, experiment 5 "
        "(2 of 5 experiments)."
    )


def test_preparation_rounds_fall_back_to_the_last_experiment_without_a_ledger():
    state = _brief_state()
    state["preparation_measurement"] = None

    rendered = "\n".join(
        brief._v4_measurement_rounds_section(state, [_completed_experiment_3()], None)
    )

    assert "Completed measurement rounds from the most recent experiment" in rendered
    assert "checkpoint-3" in rendered


def test_preparation_rounds_are_kept_when_the_experiment_enters_analysis():
    pending = {
        "experiment": 4,
        "preparation_evaluation_rounds": [
            {
                "round": 1,
                "experiment": 4,
                "status": "completed",
                "results": {
                    "research_evaluations": [
                        {
                            "candidate": "working",
                            "seed": 10,
                            "episodes": 2,
                            "success_percent": 90.0,
                        }
                    ]
                },
            }
        ],
        "evaluation_rounds": [
            {
                "round": 1,
                "experiment": 4,
                "status": "completed",
                "results": {
                    "research_evaluations": [
                        {
                            "candidate": "checkpoint-4",
                            "seed": 20,
                            "episodes": 2,
                            "success_percent": 50.0,
                        }
                    ]
                },
            }
        ],
    }

    rendered = "\n".join(brief._v4_measurement_rounds_section({}, [], pending))

    assert "Measurement rounds for the current experiment" in rendered
    assert "working" in rendered
    assert "checkpoint-4" in rendered
    # Preparation rounds were requested before the experiment's own rounds.
    assert rendered.index("working") < rendered.index("checkpoint-4")


def test_conclusion_only_brief_lists_only_campaign_conclusions():
    lines = brief._v4_phase_section(
        {
            "preparation_conclusion_only": True,
            "last_verdict": "awaiting conclusion",
        },
        None,
        None,
        "none",
        None,
        "campaign",
        "base",
    )
    rendered = "\n".join(lines)

    assert "only a `campaign_conclusion`" in rendered
    assert "budget is exhausted" in rendered
    assert "saved-lineage" not in rendered
