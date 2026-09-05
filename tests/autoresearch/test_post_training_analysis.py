import json
from pathlib import Path

from research import run_experiment
from research import runner_repository as repository


def _artifact(path: Path) -> None:
    path.mkdir(parents=True)
    path.joinpath("model.zip").write_bytes(b"model")
    path.joinpath("artifact.json").write_text("{}", encoding="utf-8")


def _configure(monkeypatch, tmp_path: Path) -> tuple[Path, Path, Path]:
    research = tmp_path / "research"
    research.mkdir()
    state_path = research / "research_state.json"
    request_path = research / "evaluation_request.json"
    proposal_path = research / "proposal.json"
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr(
        "research.runner_paths.RESULTS_PATH", research / "results.jsonl"
    )
    monkeypatch.setattr("research.runner_paths.LOG_PATH", research / "EXPERIMENTS.md")
    monkeypatch.setattr("research.runner_paths.EVALUATION_REQUEST_PATH", request_path)
    monkeypatch.setattr("research.runner_paths.PROPOSAL_PATH", proposal_path)
    monkeypatch.setattr(
        "research.runner_paths.POSTMORTEM_PATH", research / "postmortems.md"
    )
    monkeypatch.setattr(
        "research.runner_paths.EVALUATION_DIR", research / "evaluations"
    )
    monkeypatch.setattr(
        "research.runner_paths.TRAINING_LOG_DIR", research / "training_logs"
    )
    monkeypatch.setattr(
        "research.run_experiment.validate_research_delta", lambda state: []
    )
    monkeypatch.setattr(
        "research.runner_protocol.evaluation_semantics_fingerprint", lambda: "test"
    )
    _artifact(tmp_path / "archive" / "checkpoint")
    state = {
        "schema_version": 4,
        "campaign": {"id": "campaign", "started_at": "now", "base_commit": "base"},
        "working_lineage": None,
        "best_known_lineage": None,
        "retained_lineages": [],
        "pending_analysis": {
            "experiment": 1,
            "candidates": [
                {
                    "name": "checkpoint",
                    "artifact": "archive/checkpoint",
                    "timesteps": 100,
                    "evaluations": [],
                }
            ],
            "parameters": {},
            "initialization": "fresh",
            "training_budget_steps": 100,
            "parent_training_steps": 0,
            "result": {
                "schema_version": 4,
                "campaign_id": "campaign",
                "index": 1,
                "hypothesis": "test",
            },
        },
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return state_path, request_path, proposal_path


def _request(seed: int) -> dict:
    return {
        "experiment": 1,
        "question": "Does this checkpoint behave consistently?",
        "reason": "The next lineage decision needs a measured panel.",
        "measurements": [
            {
                "instrument": "research_evaluation",
                "candidate": "checkpoint",
                "episodes": 2,
                "seed": seed,
            }
        ],
    }


def test_v4_measurements_return_to_analysis_and_upsert_result(monkeypatch, tmp_path):
    state_path, request_path, _ = _configure(monkeypatch, tmp_path)
    calls: list[int] = []

    def evaluate(artifact, seed, output_path, **kwargs):
        del artifact, kwargs
        calls.append(seed)
        output_path.write_text("{}", encoding="utf-8")
        return {
            "episodes": 2,
            "seed": seed,
            "success_percent": 50.0,
            "episode_results": [True, False],
        }

    monkeypatch.setattr("research.runner_execution.evaluate_artifact", evaluate)
    request_path.write_text(json.dumps(_request(10)), encoding="utf-8")

    assert run_experiment.execute_pending_evaluations() == 0
    first = json.loads(state_path.read_text(encoding="utf-8"))
    assert first["pending_analysis"]["evaluation_plan"] is None
    assert [
        item["seed"] for item in first["pending_analysis"]["partial_evaluations"]
    ] == [10]
    first_record = repository.result_records()[0]
    assert "candidate_metrics" not in first_record

    request_path.write_text(json.dumps(_request(20)), encoding="utf-8")
    assert run_experiment.execute_pending_evaluations() == 0
    assert calls == [10, 20]
    records = repository.result_records()
    assert len(records) == 1
    assert [item["seed"] for item in records[0]["requested_evaluations"]] == [10, 20]


def test_analysis_preflight_rejects_measurement_and_closure_conflict(
    monkeypatch, tmp_path, capsys
):
    state_path, request_path, proposal_path = _configure(monkeypatch, tmp_path)
    repository.upsert_result(
        {
            "schema_version": 4,
            "campaign_id": "campaign",
            "index": 1,
            "hypothesis": "test",
        }
    )
    (tmp_path / "research" / "postmortems.md").write_text(
        "## campaign / Experiment 1\n\n**Evidence inspected:** archive/checkpoint/artifact.json\n",
        encoding="utf-8",
    )
    request_path.write_text(json.dumps(_request(10)), encoding="utf-8")
    proposal_path.write_text(
        json.dumps(
            {
                "previous_result_decision": {
                    "experiment": 1,
                    "continue_from": "checkpoint",
                    "reason": "Preserve the trained candidate.",
                    "code": {"action": "keep", "reason": "No recipe change."},
                }
            }
        ),
        encoding="utf-8",
    )

    assert run_experiment.check_analysis_deliverable() == 1
    assert "conflicting actionable" in capsys.readouterr().out
    assert (
        json.loads(state_path.read_text(encoding="utf-8"))["pending_analysis"]
        is not None
    )


def test_v4_closure_updates_result_before_clearing_analysis(monkeypatch, tmp_path):
    state_path, _, _ = _configure(monkeypatch, tmp_path)
    repository.upsert_result(
        {
            "schema_version": 4,
            "campaign_id": "campaign",
            "index": 1,
            "hypothesis": "test",
        }
    )
    (tmp_path / "research" / "postmortems.md").write_text(
        "## campaign / Experiment 1\n\n**Evidence inspected:** archive/checkpoint/artifact.json\n",
        encoding="utf-8",
    )
    proposal = {
        "previous_result_decision": {
            "experiment": 1,
            "continue_from": "checkpoint",
            "reason": "Preserve the trained candidate.",
            "code": {"action": "keep", "reason": "No recipe change."},
        }
    }

    assert not run_experiment.apply_previous_result_decision(
        proposal, repository.read_state()
    )
    assert (
        json.loads(state_path.read_text(encoding="utf-8"))["pending_analysis"] is None
    )
    record = repository.result_records()[0]
    assert record["status"] == "closed"
    assert record["closure_decision"] == proposal["previous_result_decision"]


def test_v4_closure_resume_clears_reloaded_pending_analysis(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    repository.upsert_result(
        {
            "schema_version": 4,
            "campaign_id": "campaign",
            "index": 1,
            "hypothesis": "test",
        }
    )
    (tmp_path / "research" / "postmortems.md").write_text(
        "## campaign / Experiment 1\n\n"
        "**Evidence inspected:** archive/checkpoint/artifact.json\n",
        encoding="utf-8",
    )
    state = repository.read_state()
    plan = run_experiment.protocol.plan_previous_result_decision(
        {
            "previous_result_decision": {
                "experiment": 1,
                "continue_from": "checkpoint",
                "reason": "Preserve the trained candidate.",
                "code": {"action": "keep", "reason": "No recipe change."},
            }
        },
        state,
    )
    state["pending_closure_operation"] = {
        "experiment": 1,
        "selected": plan["working_name"],
        "code_action": plan["code_action"],
        "plan": run_experiment._serialize_closure_plan(
            plan, pending_field="pending_analysis"
        ),
        "progress": "planned",
    }
    repository.write_state(state)

    reloaded = repository.read_state()
    assert not run_experiment.apply_pending_v4_closure(reloaded)

    persisted = repository.read_state()
    assert persisted["pending_analysis"] is None
    assert repository.result_records()[0]["status"] == "closed"


def test_v4_resumed_measurement_rejects_changed_model_identity(monkeypatch, tmp_path):
    state_path, request_path, _ = _configure(monkeypatch, tmp_path)
    state = repository.read_state()
    pending = state["pending_analysis"]
    request = _request(10)
    available = run_experiment.protocol.available_evaluation_candidates(pending, state)
    pending["evaluation_plan"] = request
    pending["evaluation_plan_models"] = (
        run_experiment.protocol.resolved_measurement_models(request, available)
    )
    repository.write_state(state)
    request_path.unlink(missing_ok=True)
    (tmp_path / "archive" / "checkpoint" / "model.zip").write_bytes(b"changed")

    try:
        run_experiment.execute_pending_evaluations()
    except ValueError as error:
        assert str(error) == "accepted measurement plan model identity changed"
    else:
        raise AssertionError("resumed measurement accepted a different model")

    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["pending_analysis"]["evaluation_plan"] == request
