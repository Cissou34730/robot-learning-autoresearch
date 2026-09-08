import json
from pathlib import Path

import pytest

from research import run_experiment
from research import runner_repository as repository


def test_post_training_prompt_requires_diagnostic_evidence_before_closure():
    prompt = Path("run_research.ps1").read_text(encoding="utf-8").lower()

    assert (
        "if the next proposed intervention depends on an unmeasured behavior of a saved policy, "
        "obtain that evidence during the current analysis phase before closing."
    ) in prompt
    assert "partial or unexpected signals" in prompt
    assert "what remains unknown about the broader mechanism" in prompt


def _artifact(path: Path) -> None:
    path.mkdir(parents=True)
    path.joinpath("model.zip").write_bytes(b"model")
    path.joinpath("artifact.json").write_text("{}", encoding="utf-8")
    path.joinpath("policy_runtime.pkl").write_bytes(b"runtime")


def _configure(monkeypatch, tmp_path: Path) -> tuple[Path, Path, Path]:
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
    first_evaluation = first_record["requested_evaluations"][0]
    assert first_evaluation["comparison_semantics"]
    assert first_evaluation["metrics"]["comparison_semantics"]

    request_path.write_text(json.dumps(_request(20)), encoding="utf-8")
    assert run_experiment.execute_pending_evaluations() == 0
    assert calls == [10, 20]
    records = repository.result_records()
    assert len(records) == 1
    assert [item["seed"] for item in records[0]["requested_evaluations"]] == [10, 20]


def test_v4_paired_comparison_reuses_historical_working_evidence(
    monkeypatch, tmp_path
):
    state_path, request_path, _ = _configure(monkeypatch, tmp_path)
    working_artifact = tmp_path / "archive" / "working"
    _artifact(working_artifact)
    working_artifact.joinpath("model.zip").write_bytes(b"working model")
    working_fingerprint = repository.artifact_fingerprint(working_artifact)
    candidate_fingerprint = repository.artifact_fingerprint(
        tmp_path / "archive" / "checkpoint"
    )
    historical_path = tmp_path / "research" / "evaluations" / "working.json"
    historical_path.parent.mkdir(parents=True)
    historical_path.write_text(
        json.dumps(
            {
                "episodes": 2,
                "seed": 10,
                "success_percent": 50.0,
                "episode_results": [
                    {"episode": 0, "episode_seed": 10, "success": False},
                    {"episode": 1, "episode_seed": 11, "success": True},
                ],
            }
        ),
        encoding="utf-8",
    )
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["working_lineage"] = {
        "artifact": "archive/working",
        "fingerprint": working_fingerprint,
        "origin_experiment": 1,
        "candidate": "checkpoint",
        "parameters": {},
        "scientific_commit": "base",
        "training_steps": 100,
        "evaluation_artifacts": ["research/evaluations/working.json"],
        "reason": "Current working model.",
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    repository.upsert_result(
        {
            "schema_version": 4,
            "campaign_id": "campaign",
            "index": 0,
            "requested_evaluations": [
                {
                    "candidate": "checkpoint",
                    "episodes": 2,
                    "seed": 10,
                    "evaluation_semantics": "test",
                    "model_fingerprint": working_fingerprint,
                    "metrics": {
                        "episodes": 2,
                        "seed": 10,
                        "evaluation_semantics": "test",
                        "model_fingerprint": working_fingerprint,
                        "evaluation_artifact": "research/evaluations/working.json",
                    },
                }
            ],
        }
    )
    request = _request(10)
    request["paired_comparisons"] = [
        {"candidate": "checkpoint", "reference": "working"}
    ]
    request_path.write_text(json.dumps(request), encoding="utf-8")
    calls: list[tuple[str, int]] = []

    def evaluate(artifact, seed, output_path, **kwargs):
        del kwargs
        calls.append((Path(artifact).name, seed))
        payload = {
            "episodes": 2,
            "seed": seed,
            "success_percent": 100.0,
            "episode_results": [
                {"episode": 0, "episode_seed": seed, "success": True},
                {"episode": 1, "episode_seed": seed + 1, "success": True},
            ],
        }
        output_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    monkeypatch.setattr("research.runner_execution.evaluate_artifact", evaluate)

    assert run_experiment.execute_pending_evaluations() == 0

    assert calls == [("checkpoint", 10)]
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    comparison = persisted["pending_analysis"]["result"]["paired_comparisons"][0]
    assert comparison["candidate_model_fingerprint"] == candidate_fingerprint
    assert comparison["reference_model_fingerprint"] == working_fingerprint
    assert comparison["source_artifacts"][0].endswith(
        "checkpoint-2ep-seed10-test.json"
    )
    assert comparison["source_artifacts"][1] == "research/evaluations/working.json"


def test_v4_paired_comparison_reports_incompatible_historical_semantics(
    monkeypatch, tmp_path
):
    state_path, request_path, _ = _configure(monkeypatch, tmp_path)
    working_artifact = tmp_path / "archive" / "working"
    _artifact(working_artifact)
    working_artifact.joinpath("model.zip").write_bytes(b"working model")
    working_fingerprint = repository.artifact_fingerprint(working_artifact)
    historical_path = tmp_path / "research" / "evaluations" / "working-old.json"
    historical_path.parent.mkdir(parents=True)
    historical_path.write_text("{}", encoding="utf-8")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["working_lineage"] = {
        "artifact": "archive/working",
        "fingerprint": working_fingerprint,
        "origin_experiment": 1,
        "candidate": "checkpoint",
        "parameters": {},
        "scientific_commit": "base",
        "training_steps": 100,
        "evaluation_artifacts": ["research/evaluations/working-old.json"],
        "reason": "Current working model.",
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    repository.upsert_result(
        {
            "schema_version": 4,
            "campaign_id": "campaign",
            "index": 0,
            "requested_evaluations": [
                {
                    "candidate": "old-alias",
                    "episodes": 2,
                    "seed": 10,
                    "evaluation_semantics": "old-semantics",
                    "model_fingerprint": working_fingerprint,
                    "metrics": {
                        "evaluation_artifact": "research/evaluations/working-old.json"
                    },
                }
            ],
        }
    )
    request = _request(10)
    request["paired_comparisons"] = [
        {"candidate": "checkpoint", "reference": "working"}
    ]
    request_path.write_text(json.dumps(request), encoding="utf-8")
    calls: list[int] = []
    monkeypatch.setattr(
        "research.runner_execution.evaluate_artifact",
        lambda artifact, seed, **kwargs: calls.append(seed),
    )

    with pytest.raises(ValueError) as error:
        run_experiment.execute_pending_evaluations()

    message = str(error.value)
    assert "no compatible research-evaluation semantics" in message
    assert "working-old.json" in message
    assert "checkpoint-2ep-seed10-test.json" in message
    assert calls == []


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
        "## campaign / Experiment 1\n\n"
        "**Hypothesis assessment:** Existing evidence leaves the prediction unresolved.\n\n"
        "**Evidence inspected:** archive/checkpoint/artifact.json\n",
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
        "## campaign / Experiment 1\n\n"
        "**Hypothesis assessment:** The observed improvement supports the prediction, "
        "within one development panel.\n\n"
        "**Evidence inspected:** archive/checkpoint/artifact.json\n",
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
    assert record["hypothesis_assessment"] == (
        "The observed improvement supports the prediction, within one development panel."
    )


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
        "**Hypothesis assessment:** The prediction remains unresolved.\n\n"
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


def test_accepted_legacy_closure_resumes_without_new_assessment(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    repository.upsert_result(
        {
            "schema_version": 4,
            "campaign_id": "campaign",
            "index": 1,
            "hypothesis": "test",
        }
    )
    postmortem = tmp_path / "research" / "postmortems.md"
    postmortem.write_text(
        "## campaign / Experiment 1\n\n"
        "**Hypothesis assessment:** The prediction remains unresolved.\n\n"
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
    accepted_plan = run_experiment._serialize_closure_plan(
        plan, pending_field="pending_analysis"
    )
    accepted_plan.pop("hypothesis_assessment")
    state["pending_closure_operation"] = {
        "experiment": 1,
        "selected": plan["working_name"],
        "code_action": plan["code_action"],
        "plan": accepted_plan,
        "progress": "planned",
    }
    repository.write_state(state)
    postmortem.write_text(
        "## campaign / Experiment 1\n\n"
        "**Evidence inspected:** archive/checkpoint/artifact.json\n",
        encoding="utf-8",
    )

    reloaded = repository.read_state()
    assert not run_experiment.apply_pending_v4_closure(reloaded)

    record = repository.result_records()[0]
    assert record["status"] == "closed"
    assert "hypothesis_assessment" not in record
    assert repository.read_state()["pending_analysis"] is None


def test_v4_closure_retries_after_copy_progress_write_failure(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    (tmp_path / "research" / "postmortems.md").write_text(
        "## campaign / Experiment 1\n\n"
        "**Hypothesis assessment:** The prediction remains unresolved.\n\n"
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
    destination = repository.resolve_repo_path(
        plan["artifact_publications"][0]["destination"]
    )
    original_write = repository.write_state
    failed = False

    def fail_after_copy(value):
        nonlocal failed
        if value["pending_closure_operation"]["progress"] == "copied" and not failed:
            failed = True
            raise OSError("injected copied-progress failure")
        original_write(value)

    monkeypatch.setattr(repository, "write_state", fail_after_copy)
    with pytest.raises(OSError, match="copied-progress"):
        run_experiment.apply_pending_v4_closure(state)

    assert destination.is_dir()
    assert repository.read_state()["pending_closure_operation"]["progress"] == "planned"

    monkeypatch.setattr(repository, "write_state", original_write)
    reloaded = repository.read_state()
    assert not run_experiment.apply_pending_v4_closure(reloaded)
    assert repository.read_state()["pending_closure_operation"]["progress"] == "durable"


def test_v4_closure_retries_role_result_write_without_duplicate_history(
    monkeypatch, tmp_path
):
    _configure(monkeypatch, tmp_path)
    (tmp_path / "research" / "postmortems.md").write_text(
        "## campaign / Experiment 1\n\n"
        "**Hypothesis assessment:** The prediction remains unresolved.\n\n"
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
    original_write = repository.write_state
    failed = False

    def fail_after_result(value):
        nonlocal failed
        if (
            value["pending_closure_operation"]["progress"] == "role_result_written"
            and not failed
        ):
            failed = True
            raise OSError("injected role-result failure")
        original_write(value)

    monkeypatch.setattr(repository, "write_state", fail_after_result)
    with pytest.raises(OSError, match="role-result"):
        run_experiment.apply_pending_v4_closure(state)

    assert (
        repository.read_state()["pending_closure_operation"]["progress"]
        == "code_applied"
    )
    assert len(repository.result_records()) == 1

    monkeypatch.setattr(repository, "write_state", original_write)
    reloaded = repository.read_state()
    assert not run_experiment.apply_pending_v4_closure(reloaded)
    assert len(repository.result_records()) == 1
    persisted = repository.read_state()
    assert persisted["working_lineage"]["candidate"] == "checkpoint"
    assert persisted["pending_closure_operation"]["progress"] == "durable"


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


def test_v4_resumed_measurement_accepts_relocated_identical_model(
    monkeypatch, tmp_path
):
    _, request_path, _ = _configure(monkeypatch, tmp_path)
    state = repository.read_state()
    pending = state["pending_analysis"]
    request = _request(10)
    available = run_experiment.protocol.available_evaluation_candidates(pending, state)
    pending["evaluation_plan"] = request
    pending["evaluation_plan_models"] = (
        run_experiment.protocol.resolved_measurement_models(request, available)
    )
    pending["evaluation_evidence_plan"] = []
    source = tmp_path / "archive" / "checkpoint"
    relocated = tmp_path / "archive" / "relocated"
    source.rename(relocated)
    pending["candidates"][0]["artifact"] = "archive/relocated"
    repository.write_state(state)
    request_path.write_text(json.dumps(request), encoding="utf-8")
    calls: list[Path] = []

    def evaluate(artifact, seed, output_path, **kwargs):
        del kwargs
        calls.append(Path(artifact))
        payload = {
            "episodes": 2,
            "seed": seed,
            "success_percent": 50.0,
            "episode_results": [True, False],
        }
        output_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    monkeypatch.setattr("research.runner_execution.evaluate_artifact", evaluate)

    assert run_experiment.execute_pending_evaluations() == 0
    assert calls == [relocated]


def test_v4_resumed_measurement_rejects_edited_accepted_request(
    monkeypatch, tmp_path
):
    state_path, request_path, _ = _configure(monkeypatch, tmp_path)
    state = repository.read_state()
    pending = state["pending_analysis"]
    request = _request(10)
    available = run_experiment.protocol.available_evaluation_candidates(pending, state)
    pending["evaluation_plan"] = request
    pending["evaluation_plan_models"] = (
        run_experiment.protocol.resolved_measurement_models(request, available)
    )
    pending["evaluation_evidence_plan"] = []
    repository.write_state(state)
    request_path.write_text(json.dumps(_request(20)), encoding="utf-8")

    with pytest.raises(ValueError, match="accepted measurement plan changed"):
        run_experiment.execute_pending_evaluations()

    assert json.loads(state_path.read_text(encoding="utf-8")) == state
