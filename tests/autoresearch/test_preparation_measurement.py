"""Measurement execution, analysis decisions and bounded inquiry operations."""

import copy
import json
from pathlib import Path

import pytest

from research import build_research_brief as brief
from research import run_experiment
from research import runner_protocol as protocol
from research import runner_repository as repository


def _artifact(path: Path, marker: bytes = b"model") -> Path:
    path.mkdir(parents=True)
    path.joinpath("model.zip").write_bytes(marker)
    path.joinpath("artifact.json").write_text("{}", encoding="utf-8")
    path.joinpath("policy_runtime.pkl").write_bytes(b"runtime")
    return path


def _lineage(path: Path) -> dict:
    return {
        "artifact": repository.repo_relative_path(path),
        "fingerprint": repository.artifact_fingerprint(path),
        "origin_experiment": 1,
        "candidate": "baseline",
        "parameters": {},
        "scientific_commit": "a" * 40,
        "training_steps": 120_000,
        "evaluation_artifacts": [],
        "reason": "Selected baseline.",
        "designation_ordinal": 1,
    }


def _configure(monkeypatch, tmp_path: Path) -> tuple[Path, Path, dict]:
    research = tmp_path / "research"
    research.mkdir()
    state_path = research / "research_state.json"
    request_path = research / "evaluation_request.json"
    proposal_path = research / "proposal.json"
    for name, value in {
        "ROOT": tmp_path,
        "RESEARCH_DIR": research,
        "STATE_PATH": state_path,
        "RESULTS_PATH": research / "results.jsonl",
        "LOG_PATH": research / "EXPERIMENTS.md",
        "EVALUATION_REQUEST_PATH": request_path,
        "PROPOSAL_PATH": proposal_path,
        "EVALUATION_DIR": research / "evaluations",
        "POSTMORTEM_PATH": research / "postmortems.md",
        "CANDIDATE_ROOT": tmp_path / "models" / "candidates",
        "BASELINE_PENDING_PATH": research / "BASELINE_PENDING",
    }.items():
        monkeypatch.setattr(repository.paths, name, value)
    monkeypatch.setattr(run_experiment, "validate_research_delta", lambda state: [])
    monkeypatch.setattr(repository, "publish_campaign_laboratory", lambda state: None)
    monkeypatch.setattr(
        protocol, "evaluation_semantics_fingerprint", lambda: "semantics"
    )

    artifact = _artifact(tmp_path / "archive" / "working")
    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        last_verdict="baseline selected",
    )
    state["working_lineage"] = _lineage(artifact)
    state["best_known_lineage"] = _lineage(artifact)
    session = repository.ensure_inquiry_session(state)
    state["active_inquiry"] = {
        "id": session["inquiry_id"],
        "question": "How robust is the baseline?",
        "scope": "Saved-model behavior.",
        "closure_condition": "The uncertainty is bounded.",
        "status": "active",
        "session_id": session["id"],
        "reframes": [],
    }
    repository.write_state(state)
    repository.paths.POSTMORTEM_PATH.write_text(
        "## campaign / Scientific strategy\n\n"
        "**Current synthesis:** Current evidence is incomplete.\n\n"
        "**Lessons and limits:** Only the baseline is measured.\n\n"
        "**Competing explanations:** Control and optimization remain plausible.\n\n"
        "**Decision frontier:** Whether another panel changes the conclusion.\n",
        encoding="utf-8",
    )
    return state_path, request_path, state


def _request(candidate: str = "working", seed: int = 10) -> dict:
    return {
        "question": "How does the saved lineage behave on this panel?",
        "reason": "The result can change the inquiry decision.",
        "measurements": [
            {
                "instrument": "research_evaluation",
                "candidate": candidate,
                "episodes": 2,
                "seed": seed,
                "selection": "The saved lineage directly answers the question.",
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
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    return evaluate


def test_inquiry_measurement_context_is_lineage_only(monkeypatch, tmp_path):
    _, _, state = _configure(monkeypatch, tmp_path)
    context = protocol.validate_preparation_evaluation_request(_request(), state)
    assert context["preparation"] is True
    assert context["candidates"] == []
    assert context["inquiry_id"] == 1
    assert state["last_allocated_experiment"] == 0


def test_inquiry_measurement_remains_legal_at_training_cap(monkeypatch, tmp_path):
    _, request_path, _ = _configure(monkeypatch, tmp_path)
    request_path.write_text(json.dumps(_request()), encoding="utf-8")

    assert (
        run_experiment.check_preparation_deliverable(training_allocation_closed=True)
        == 0
    )


def test_inquiry_measurement_does_not_require_working_when_method_exists(
    monkeypatch, tmp_path
):
    _, _, state = _configure(monkeypatch, tmp_path)
    method_artifact = _artifact(tmp_path / "archive" / "method", b"method")
    state["active_method"] = {
        "id": "method-a",
        "inquiry_id": 1,
        "scientific_question": "How does the method learn?",
        "rationale": "Inspect its own trajectory.",
        "lifecycle": "development",
        "base_scientific_commit": "a" * 40,
        "current_lineage": _lineage(method_artifact),
        "iterations": [],
        "resolution": None,
    }
    state["working_lineage"] = None
    context = protocol.validate_preparation_evaluation_request(
        _request("active_method"), state
    )
    assert "active_method" in protocol.available_evaluation_candidates(context, state)


def test_inquiry_measurement_returns_to_same_inquiry(monkeypatch, tmp_path):
    state_path, request_path, _ = _configure(monkeypatch, tmp_path)
    calls: list[int] = []
    monkeypatch.setattr(
        run_experiment.execution, "evaluate_artifact", _evaluator(calls)
    )
    monkeypatch.setattr(repository, "append_result", lambda result: None)
    request_path.write_text(json.dumps(_request()), encoding="utf-8")

    assert run_experiment.execute_pending_evaluations() == 0
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["active_inquiry"]["id"] == 1
    assert (
        persisted["inquiry_session"]["id"] == persisted["active_inquiry"]["session_id"]
    )
    assert persisted["pending_evaluation_request"] is None
    assert persisted["preparation_measurement"]["inquiry_id"] == 1
    assert calls == [10]


def test_repeated_identical_panel_is_reused(monkeypatch, tmp_path):
    state_path, request_path, _ = _configure(monkeypatch, tmp_path)
    calls: list[int] = []
    monkeypatch.setattr(
        run_experiment.execution, "evaluate_artifact", _evaluator(calls)
    )
    monkeypatch.setattr(repository, "append_result", lambda result: None)
    for _ in range(2):
        request_path.write_text(json.dumps(_request()), encoding="utf-8")
        assert run_experiment.execute_pending_evaluations() == 0

    ledger = json.loads(state_path.read_text(encoding="utf-8"))[
        "preparation_measurement"
    ]
    assert calls == [10]
    assert [item["round"] for item in ledger["rounds"]] == [1, 2]
    assert {item["inquiry_id"] for item in ledger["rounds"]} == {1}
    reused = ledger["rounds"][1]["results"]["research_evaluations"][0]
    assert reused["status"] == "reused"
    assert reused["reused_from_round"] == 1
    assert len(ledger["partial_evaluations"]) == 1


def test_inquiry_can_be_reframed_without_changing_identity(monkeypatch, tmp_path):
    _, _, state = _configure(monkeypatch, tmp_path)
    plan = protocol.plan_inquiry_operation(
        {
            "inquiry": {
                "action": "reframe",
                "question": "Which failure mode remains?",
                "scope": "Method and saved-model evidence.",
                "closure_condition": "One explanation is ruled out.",
                "rationale": "The first measurement narrowed the question.",
            }
        },
        state,
    )
    assert plan["inquiry_id"] == 1
    assert plan["action"] == "reframe"


def test_closing_inquiry_clears_session_and_preserves_campaign_roles(
    monkeypatch, tmp_path
):
    state_path, _, state = _configure(monkeypatch, tmp_path)
    working = state["working_lineage"]
    closed_session_id = state["inquiry_session"]["id"]
    plan = protocol.plan_inquiry_operation(
        {
            "inquiry": {
                "action": "close",
                "outcome": "The baseline uncertainty is sufficiently bounded.",
            }
        },
        state,
    )
    state["pending_inquiry_operation"] = {**plan, "progress": "planned"}
    repository.write_state(state)
    monkeypatch.setattr(repository, "commit_runner_memory", lambda message: True)

    run_experiment.complete_inquiry_operation(state)
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["active_inquiry"] is None
    assert persisted["active_method"] is None
    assert persisted["inquiry_session"] is None
    assert persisted["working_lineage"] == working
    assert persisted["last_inquiry"] == 1
    next_session = repository.ensure_inquiry_session(persisted)
    assert next_session["id"] != closed_session_id
    assert next_session["inquiry_id"] == 2


def test_active_nonterminal_method_blocks_inquiry_close(monkeypatch, tmp_path):
    _, _, state = _configure(monkeypatch, tmp_path)
    state["active_method"] = {
        "id": "method-a",
        "inquiry_id": 1,
        "scientific_question": "Can it learn?",
        "rationale": "It tests another method.",
        "lifecycle": "development",
        "base_scientific_commit": "a" * 40,
        "current_lineage": None,
        "iterations": [],
        "resolution": None,
    }
    with pytest.raises(ValueError, match="promoting, retaining, or abandoning"):
        protocol.plan_inquiry_operation(
            {"inquiry": {"action": "close", "outcome": "Done."}}, state
        )


def test_generic_brief_exposes_state_without_scenario_diagnosis(monkeypatch, tmp_path):
    state_path, _, state = _configure(monkeypatch, tmp_path)
    rendered = brief._render_inquiry_centered_brief(
        state,
        [{"campaign_id": "campaign", "index": 1}],
        [],
        repository.paths.POSTMORTEM_PATH.read_text(encoding="utf-8"),
        "campaign",
        "base",
    )
    assert "Active inquiry" in rendered
    assert "How robust is the baseline?" in rendered
    assert "failure mode" not in rendered.lower()
    assert "scenario-specific diagnoses" in rendered
    assert (
        json.loads(state_path.read_text(encoding="utf-8"))["active_inquiry"]["id"] == 1
    )


def _tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _method(lineage: dict | None = None, iterations: list | None = None) -> dict:
    return {
        "id": "method-a",
        "inquiry_id": 1,
        "scientific_question": "Can method A improve control?",
        "rationale": "It tests a distinct learning path.",
        "lifecycle": "development",
        "base_scientific_commit": "a" * 40,
        "current_lineage": lineage,
        "iterations": iterations or [],
        "resolution": None,
    }


def test_inquiry_measurement_context_does_not_mutate_state(monkeypatch, tmp_path):
    _, _, state = _configure(monkeypatch, tmp_path)
    state["preparation_measurement"] = {
        "experiment": 1,
        "inquiry_id": 1,
        "campaign_lab": None,
        "rounds": [{"round": 1, "inquiry_id": 1, "status": "completed"}],
        "partial_evaluations": [],
        "partial_task_reference_evaluations": [],
    }
    before = copy.deepcopy(state)

    context = protocol.preparation_measurement_context(state)
    protocol.validate_preparation_evaluation_request(_request(), state)
    context["evaluation_rounds"].append({"round": 2})

    assert state == before
    assert [item["round"] for item in context["evaluation_rounds"]] == [1, 2]
    state["preparation_measurement"]["inquiry_id"] = 7
    assert protocol.preparation_measurement_context(state)["evaluation_rounds"] == []


@pytest.mark.parametrize("failing_frame", ["researcher", "dependency"])
def test_measurement_failure_reopens_only_for_changed_researcher_code(
    monkeypatch, tmp_path, failing_frame
):
    state_path, request_path, _ = _configure(monkeypatch, tmp_path)
    relative = "robot_learning/scenario/environment.py"
    researcher_file = tmp_path / relative
    researcher_file.parent.mkdir(parents=True)
    researcher_file.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(run_experiment, "validate_research_delta", lambda s: [relative])
    frames = [f'  File "{researcher_file}", line 12, in step']
    if failing_frame == "dependency":
        frames.append('  File "C:\\runtime\\site-packages\\mujoco\\core.py", line 3')

    def fail(*args, **kwargs):
        raise RuntimeError(
            "Traceback (most recent call last):\n" + "\n".join(frames) + "\nboom"
        )

    monkeypatch.setattr(run_experiment.execution, "evaluate_artifact", fail)
    request_path.write_text(json.dumps(_request()), encoding="utf-8")

    if failing_frame == "researcher":
        assert (
            run_experiment.execute_pending_evaluations()
            == run_experiment.RESEARCHER_IMPLEMENTATION_ERROR_EXIT
        )
    else:
        with pytest.raises(RuntimeError, match="boom"):
            run_experiment.execute_pending_evaluations()

    pending = json.loads(state_path.read_text(encoding="utf-8"))[
        "pending_evaluation_request"
    ]
    error = pending.get("implementation_error")
    if failing_frame == "researcher":
        assert error["causal_path"] == relative
        assert pending["implementation_repair_attempts"] == 0
    else:
        assert error is None
    assert pending["partial_evaluations"] == []
    assert pending["evaluation_rounds"][-1]["results"]["research_evaluations"] == []
    assert request_path.exists()


def test_implementation_repair_is_bounded_and_freezes_the_request(
    monkeypatch, tmp_path
):
    state_path, request_path, state = _configure(monkeypatch, tmp_path)
    request_path.write_text(json.dumps(_request()), encoding="utf-8")
    state["pending_evaluation_request"] = {
        **protocol.preparation_measurement_context(state),
        "implementation_error": {
            "causal_path": "robot_learning/scenario/environment.py",
            "error": "AttributeError",
            "request_fingerprint": repository.file_fingerprint(request_path),
        },
        "implementation_repair_attempts": 0,
    }
    repository.write_state(state)

    assert run_experiment.complete_implementation_repair() == 1
    assert run_experiment.record_implementation_repair_attempt() == 0
    request_path.write_text(json.dumps(_request(seed=11)), encoding="utf-8")
    assert run_experiment.complete_implementation_repair() == 1
    request_path.write_text(json.dumps(_request()), encoding="utf-8")
    assert run_experiment.record_implementation_repair_attempt() == 0
    assert run_experiment.record_implementation_repair_attempt() == 1
    assert run_experiment.complete_implementation_repair() == 0

    pending = json.loads(state_path.read_text(encoding="utf-8"))[
        "pending_evaluation_request"
    ]
    assert pending["implementation_repair_attempts"] == 2
    assert "implementation_error" not in pending


def test_inquiry_close_recovery_records_history_once(monkeypatch, tmp_path):
    state_path, _, state = _configure(monkeypatch, tmp_path)
    state["preparation_measurement"] = {
        "experiment": 1,
        "inquiry_id": 1,
        "campaign_lab": None,
        "rounds": [{"round": 1, "inquiry_id": 1, "status": "completed"}],
        "partial_evaluations": [],
        "partial_task_reference_evaluations": [],
    }
    plan = protocol.plan_inquiry_operation(
        {"inquiry": {"action": "close", "outcome": "The uncertainty is bounded."}},
        state,
    )
    state["pending_inquiry_operation"] = {**plan, "progress": "planned"}
    repository.write_state(state)
    repository.paths.PROPOSAL_PATH.write_text("{}", encoding="utf-8")
    failures = ["close inquiry 1"]

    def publish(message):
        if message in failures:
            failures.remove(message)
            raise OSError("injected memory publication failure")

    monkeypatch.setattr(run_experiment, "_publish_runner_memory", publish)
    with pytest.raises(OSError, match="injected"):
        run_experiment.complete_inquiry_operation(state)
    interrupted = repository.read_state()
    assert interrupted["pending_inquiry_operation"]["progress"] == "artifacts_released"
    assert repository.paths.PROPOSAL_PATH.exists()

    run_experiment.complete_inquiry_operation(interrupted)

    records = repository.history_records()
    assert [record["record_type"] for record in records] == ["inquiry"]
    assert [item["round"] for item in records[0]["measurement_rounds"]] == [1]
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["pending_inquiry_operation"] is None
    assert persisted["preparation_measurement"] is None
    assert not repository.paths.PROPOSAL_PATH.exists()


@pytest.mark.parametrize(("ledger_inquiry", "transferred"), [(1, True), (2, False)])
def test_preparation_ledger_transfers_only_to_its_inquiry_once(
    ledger_inquiry, transferred
):
    ledger = {
        "experiment": 3,
        "inquiry_id": ledger_inquiry,
        "rounds": [{"round": 1, "inquiry_id": ledger_inquiry}],
        "partial_evaluations": [{"candidate": "working"}],
        "partial_task_reference_evaluations": [],
    }
    state = {"preparation_measurement": copy.deepcopy(ledger)}
    result: dict = {"inquiry_id": 1}
    pending: dict = {}

    run_experiment.transfer_preparation_measurements(state, result, pending, 3)
    run_experiment.transfer_preparation_measurements(state, result, pending, 3)

    if transferred:
        assert state["preparation_measurement"] is None
        assert result["preparation_evaluation_rounds"] == ledger["rounds"]
        assert pending["preparation_evaluation_rounds"] == ledger["rounds"]
    else:
        assert state["preparation_measurement"] == ledger
        assert "preparation_evaluation_rounds" not in result


# --- post-training analysis ------------------------------------------------


def _analysis(monkeypatch, tmp_path: Path, *, baseline: bool) -> tuple[Path, Path]:
    state_path, request_path, state = _configure(monkeypatch, tmp_path)
    candidates = [
        _artifact(tmp_path / "models" / "candidates" / name, name.encode())
        for name in ("checkpoint-100", "checkpoint-200")
    ]
    pending = {
        "experiment": 1,
        "candidates": [
            {
                "name": path.name,
                "artifact": repository.repo_relative_path(path),
                "timesteps": int(path.name.split("-")[1]),
                "evaluations": [],
            }
            for path in candidates
        ],
        "champion_available": False,
        "parameters": {},
        "initialization": "fresh",
        "training_budget_steps": 200,
        "parent_training_steps": 0,
        "baseline": baseline,
        "code_parent_commit": "a" * 40,
        "result": {
            "schema_version": 1,
            "record_type": "experiment",
            "campaign_id": "campaign",
            "index": 1,
            "change": "Train the recipe.",
            "status": "trained",
            "verdict": "trained; awaiting measurement",
        },
    }
    if baseline:
        state.update(
            working_lineage=None,
            best_known_lineage=None,
            active_inquiry=None,
            inquiry_session=None,
        )
    else:
        pending.update(inquiry_id=1, method_id="method-a")
        pending["result"]["inquiry_id"] = 1
        state["active_method"] = _method(
            iterations=[{"experiment": 1, "status": "awaiting_analysis"}]
        )
    state.update(
        pending_analysis=pending, last_experiment=1, last_allocated_experiment=1
    )
    state["campaign_experiment_counters"] = {"campaign": 1}
    repository.write_state(state)
    return state_path, request_path


def _analysis_request(*seeds: int, labels: tuple[str, ...] = ()) -> dict:
    request = _request("checkpoint-100", seeds[0])
    template = request["measurements"][0]
    request["measurements"] = [{**template, "seed": seed} for seed in seeds]
    for measurement, label in zip(request["measurements"], labels):
        measurement["label"] = label
    return {"experiment": 1, **request}


def test_interrupted_analysis_measurement_resumes_only_remaining_panels(
    monkeypatch, tmp_path
):
    state_path, request_path = _analysis(monkeypatch, tmp_path, baseline=True)
    calls: list[int] = []
    evaluate = _evaluator(calls)
    interrupted: list[int] = []

    def interrupt_second_panel(artifact, seed, output_path, **kwargs):
        if seed == 20 and not interrupted:
            interrupted.append(seed)
            raise KeyboardInterrupt
        return evaluate(artifact, seed, output_path, **kwargs)

    monkeypatch.setattr(
        run_experiment.execution, "evaluate_artifact", interrupt_second_panel
    )
    request_path.write_text(json.dumps(_analysis_request(10, 20)), encoding="utf-8")

    assert run_experiment.execute_pending_evaluations() == 130
    paused = json.loads(state_path.read_text(encoding="utf-8"))["pending_analysis"]
    assert [item["seed"] for item in paused["partial_evaluations"]] == [10]
    assert run_experiment.execute_pending_evaluations() == 0

    assert calls == [10, 20]
    measured = json.loads(state_path.read_text(encoding="utf-8"))["pending_analysis"]
    summary = measured["candidates"][0]["summary"]
    assert (summary["episodes"], summary["seed_count"]) == (4, 2)
    assert measured["candidates"][1]["summary"] is None


def test_measurement_reuse_ignores_labels_and_tracks_semantics(monkeypatch, tmp_path):
    state_path, request_path = _analysis(monkeypatch, tmp_path, baseline=True)
    calls: list[int] = []
    monkeypatch.setattr(
        run_experiment.execution, "evaluate_artifact", _evaluator(calls)
    )
    request_path.write_text(
        json.dumps(_analysis_request(10, 10, labels=("first", "second"))),
        encoding="utf-8",
    )
    assert run_experiment.execute_pending_evaluations() == 0
    request_path.write_text(
        json.dumps(_analysis_request(10, labels=("relabelled",))), encoding="utf-8"
    )
    assert run_experiment.execute_pending_evaluations() == 0
    assert calls == [10]

    monkeypatch.setattr(protocol, "evaluation_semantics_fingerprint", lambda: "new")
    request_path.write_text(json.dumps(_analysis_request(10)), encoding="utf-8")
    assert run_experiment.execute_pending_evaluations() == 0

    assert calls == [10, 10]
    pending = json.loads(state_path.read_text(encoding="utf-8"))["pending_analysis"]
    assert [
        item["evaluation_semantics"] for item in pending["partial_evaluations"]
    ] == [
        "semantics",
        "new",
    ]


@pytest.mark.parametrize("baseline", [True, False])
def test_completed_measurement_waits_for_explicit_decision(
    monkeypatch, tmp_path, baseline
):
    state_path, request_path = _analysis(monkeypatch, tmp_path, baseline=baseline)
    monkeypatch.setattr(run_experiment.execution, "evaluate_artifact", _evaluator([]))
    request_path.write_text(json.dumps(_analysis_request(10)), encoding="utf-8")

    assert run_experiment.execute_pending_evaluations() == 0

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["pending_analysis"]["experiment"] == 1
    [record] = repository.result_records()
    assert record["decision_pending"] is True
    expected = "baseline_decision" if baseline else "method_decision"
    for proposal in (
        {"kind": "training", "method_id": "method-a"},
        {"inquiry": {"action": "close", "outcome": "Done."}},
    ):
        with pytest.raises(ValueError, match=f"requires only {expected}"):
            protocol.validate_proposal_phase(proposal, state)


def _baseline_decision(**changes) -> dict:
    decision = {
        "experiment": 1,
        "candidate": "checkpoint-100",
        "reason": "It is the measured baseline.",
    }
    decision.update(changes)
    return {"baseline_decision": decision}


@pytest.mark.parametrize(
    ("proposal", "message"),
    [
        (_baseline_decision(experiment=2), "wrong experiment"),
        (_baseline_decision(candidate="checkpoint-999"), "must name one of"),
        (_baseline_decision(extra="field"), "requires exactly"),
        (_baseline_decision(), "no recorded campaign measurement"),
    ],
)
def test_invalid_baseline_decision_mutates_nothing(
    monkeypatch, tmp_path, proposal, message
):
    _analysis(monkeypatch, tmp_path, baseline=True)
    before = _tree(tmp_path)

    with pytest.raises(ValueError, match=message):
        run_experiment.resolve_baseline_decision(proposal, repository.read_state())

    assert _tree(tmp_path) == before


def test_baseline_publication_failure_is_atomic_and_recoverable(monkeypatch, tmp_path):
    state_path, request_path = _analysis(monkeypatch, tmp_path, baseline=True)
    monkeypatch.setattr(run_experiment.execution, "evaluate_artifact", _evaluator([]))
    request_path.write_text(json.dumps(_analysis_request(10)), encoding="utf-8")
    assert run_experiment.execute_pending_evaluations() == 0
    [evaluation] = (tmp_path / "research" / "evaluations").rglob("*.json")
    evidence = evaluation.read_bytes()
    state = repository.load_state(allow_unmeasured=True, allow_missing_artifact=True)
    plan = protocol.plan_baseline_decision(_baseline_decision(), state)
    [publication] = plan["artifact_publications"]
    destination = repository.resolve_repo_path(publication["destination"])
    original_copy = repository.copy_artifact

    def fail_midway(source, target):
        original_copy(source, target)
        raise OSError("injected publication failure")

    monkeypatch.setattr(repository, "copy_artifact", fail_midway)
    with pytest.raises(OSError, match="injected publication failure"):
        run_experiment.apply_baseline_decision(plan, state)

    interrupted = repository.read_state()
    assert interrupted["pending_baseline_decision"]["progress"] == "planned"
    assert interrupted["working_lineage"] is None
    assert interrupted["pending_analysis"] is not None
    assert not destination.exists()
    assert list(destination.parent.glob(".*.tmp")) == []

    monkeypatch.setattr(repository, "copy_artifact", original_copy)
    run_experiment.complete_pending_baseline_decision(interrupted)
    run_experiment.finalize_pending_baseline_decision(interrupted)

    recovered = json.loads(state_path.read_text(encoding="utf-8"))
    assert recovered["pending_baseline_decision"]["progress"] == "cleanup_complete"
    assert recovered["pending_analysis"] is None
    assert recovered["working_lineage"] == recovered["best_known_lineage"]
    assert (
        repository.resolve_repo_path(recovered["working_lineage"]["artifact"])
        == destination
    )
    assert (destination / "model.zip").exists()
    [record] = repository.result_records()
    assert record["decision_pending"] is False
    for name in ("checkpoint-100", "checkpoint-200"):
        released = tmp_path / "models" / "candidates" / name
        assert not (released / "model.zip").exists()
        assert (released / "artifact.json").exists()
    assert evaluation.read_bytes() == evidence


def _inquiry_method_decision(**changes) -> dict:
    decision = {
        "action": "retain",
        "outcome": "The method is a useful alternative.",
        "reason": "Its evidence is distinct.",
        "retained_id": "method-alternative",
        "code": {"action": "keep", "reason": "Keep the method recipe."},
    }
    decision.update(changes)
    return {"method_decision": {k: v for k, v in decision.items() if v is not None}}


@pytest.mark.parametrize(
    ("proposal", "message"),
    [
        (
            _inquiry_method_decision(action="promote", retained_id=None),
            "already marked mature",
        ),
        (
            _inquiry_method_decision(action="abandon", retained_id=None),
            "explicit revert or restore",
        ),
        (_inquiry_method_decision(retained_id="kept"), "must be unique"),
        (
            _inquiry_method_decision(
                best_known={"candidate": "active_method", "reason": "Best."}
            ),
            "best_known is valid only for promote",
        ),
        (
            _inquiry_method_decision(action="continue", retained_id=None),
            "requires pending post-training analysis",
        ),
        (_inquiry_method_decision(unexpected=True), "unsupported method_decision"),
    ],
)
def test_invalid_method_decision_mutates_nothing(
    monkeypatch, tmp_path, proposal, message
):
    _, _, state = _configure(monkeypatch, tmp_path)
    method = _artifact(tmp_path / "archive" / "method", b"method")
    kept = _artifact(tmp_path / "archive" / "kept", b"kept")
    state["active_method"] = _method(_lineage(method))
    state["retained_lineages"] = [{"id": "kept", **_lineage(kept)}]
    repository.write_state(state)
    monkeypatch.setattr(
        run_experiment,
        "_publish_method_science",
        lambda plan: pytest.fail("an invalid decision published science"),
    )
    before = _tree(tmp_path)

    with pytest.raises(ValueError, match=message):
        run_experiment.resolve_method_decision(proposal)

    assert _tree(tmp_path) == before


@pytest.mark.parametrize(
    ("failing", "interrupted_progress", "roles_recorded"),
    [("science", "code_applied", False), ("memory", "decision_recorded", True)],
)
def test_method_science_and_memory_publication_retry_separately(
    monkeypatch, tmp_path, failing, interrupted_progress, roles_recorded
):
    _, _, state = _configure(monkeypatch, tmp_path)
    method = _artifact(tmp_path / "archive" / "method", b"method")
    state["active_method"] = _method(_lineage(method))
    repository.write_state(state)
    failures = {failing}
    published: list[str] = []

    def publish(boundary: str):
        if boundary in failures:
            failures.discard(boundary)
            raise OSError(f"injected {boundary} publication failure")
        published.append(boundary)

    monkeypatch.setattr(
        run_experiment, "_publish_method_science", lambda plan: publish("science")
    )
    monkeypatch.setattr(
        run_experiment, "_publish_runner_memory", lambda message: publish("memory")
    )
    proposal = _inquiry_method_decision()

    with pytest.raises(OSError, match=f"injected {failing}"):
        run_experiment.resolve_method_decision(proposal)
    interrupted = repository.read_state()
    assert interrupted["pending_method_decision"]["progress"] == interrupted_progress
    assert (interrupted["active_method"]["lifecycle"] == "retained") is roles_recorded

    assert run_experiment.resolve_method_decision(proposal) == 0
    resolved = repository.read_state()
    assert resolved["pending_method_decision"] is None
    assert [item["id"] for item in resolved["retained_lineages"]] == [
        "method-alternative"
    ]
    assert published.count("science") == 1


def test_pending_measurement_of_another_inquiry_is_rejected(monkeypatch, tmp_path):
    _, request_path, state = _configure(monkeypatch, tmp_path)
    request_path.write_text(json.dumps(_request()), encoding="utf-8")
    state["pending_evaluation_request"] = {
        **protocol.preparation_measurement_context(state),
        "inquiry_id": 2,
    }
    repository.write_state(state)
    monkeypatch.setattr(
        run_experiment.execution,
        "evaluate_artifact",
        lambda *args, **kwargs: pytest.fail("a foreign measurement was executed"),
    )

    with pytest.raises(ValueError, match="belongs to another scientific inquiry"):
        run_experiment.execute_pending_evaluations()
