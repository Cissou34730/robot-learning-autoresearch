"""Campaign-level terminal decisions in the goal-centered lifecycle."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from research import run_experiment
from research import runner_paths as paths
from research import runner_protocol as protocol
from research import runner_repository as repository


def _configure(monkeypatch, tmp_path: Path) -> dict:
    research = tmp_path / "research"
    research.mkdir()
    for name, value in {
        "ROOT": tmp_path,
        "STATE_PATH": research / "research_state.json",
        "RESULTS_PATH": research / "results.jsonl",
        "LOG_PATH": research / "EXPERIMENTS.md",
        "OPERATION_REQUEST_PATH": research / "operation_request.json",
        "GOAL_PATH": research / "GOAL_REACHED",
    }.items():
        monkeypatch.setattr(paths, name, value)
    monkeypatch.setattr(repository, "git", lambda *args: "a" * 40 + "\n")
    monkeypatch.setattr(repository, "scientific_delta", lambda _parent: [])
    monkeypatch.setattr(
        protocol, "require_trusted_assessment_runtime", lambda _path: None
    )
    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        last_verdict="fresh",
    )
    state["scientific_model"] = {
        "status": "ready",
        "path": "research/scientific_model.md",
        "commit": "a" * 40,
    }
    repository.start_scientific_session(
        state,
        kind="goal_review",
        objective="Decide the campaign outcome.",
        backend_adapter="copilot",
        backend_model="gpt-5.6-luna",
        backend_reasoning="high",
    )
    repository.write_state(state)
    return state


def test_no_credible_route_is_rejected_without_changing_campaign(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)
    request = {
        "campaign_conclusion": {
            "action": "no_credible_route",
            "reason": "The durable evidence leaves no credible path.",
        }
    }
    original = repository.read_state()
    with pytest.raises(ValueError, match="must be request_official_assessment"):
        run_experiment.accept_operation(request, state)
    assert repository.read_state() == original
    assert state == original


def test_obsolete_pending_conclusion_cannot_create_a_terminal_state(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    pending = {
        "data": {
            "plan": {
                "status": "no_credible_route",
                "reason": "An obsolete request.",
                "model": None,
            }
        }
    }
    original = repository.read_state()
    with pytest.raises(ValueError, match="only an official-assessment request"):
        run_experiment._execute_campaign_conclusion(state, pending)
    assert repository.read_state() == original
    assert state == original


def test_official_assessment_requires_an_explicit_best_known(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)
    request = {
        "campaign_conclusion": {
            "action": "request_official_assessment",
            "reason": "The best-known model is expected to meet the human goal.",
        }
    }
    with pytest.raises(ValueError, match="best-known"):
        protocol.validate_operation_request(request, state)


def test_historical_terminal_record_remains_readable(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)
    state["scientific_session"] = None
    state["terminal_state"] = {
        "status": "no_credible_route",
        "reason": "A recorded historical stop.",
        "model": None,
    }
    repository.write_state(state)
    assert repository.read_state() == state


def test_official_assessment_records_the_selected_best_known(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)
    artifact = tmp_path / "archive" / "candidate"
    artifact.mkdir(parents=True)
    (artifact / "model.zip").write_bytes(b"model")
    (artifact / "artifact.json").write_text("{}", encoding="utf-8")
    (artifact / "policy_runtime.pkl").write_bytes(b"runtime")
    candidate = {
        "id": "T1:checkpoint-10",
        "artifact": repository.repo_relative_path(artifact),
        "fingerprint": repository.artifact_fingerprint(artifact),
        "origin_operation": "T1",
        "name": "checkpoint-10",
        "parameters": {},
        "scientific_commit": "b" * 40,
        "training_steps": 10,
        "evaluation_artifacts": [],
    }
    state["candidates"][candidate["id"]] = candidate
    state["model_roles"]["best_known"] = candidate["id"]
    repository.write_state(state)
    request = {
        "campaign_conclusion": {
            "action": "request_official_assessment",
            "reason": "The selected model is expected to meet the human goal.",
        }
    }
    run_experiment.accept_operation(request, state)
    assert run_experiment.execute_pending_operation() == 0
    terminal = repository.read_state()["terminal_state"]
    assert terminal == {
        "status": "official_assessment_requested",
        "reason": "The selected model is expected to meet the human goal.",
        "model": candidate["id"],
    }


def test_campaign_conclusion_requires_goal_review_after_inquiry_closure(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    state["active_inquiry"] = {
        "id": "I1",
        "question": "Question",
        "goal_connection": "Connection",
        "closure_condition": "Closure",
        "rationale": "Rationale",
        "opened_in_session": "S0",
        "reframes": [],
    }
    request = {
        "campaign_conclusion": {
            "action": "request_official_assessment",
            "reason": "Assess the selected candidate.",
        }
    }
    with pytest.raises(ValueError, match="opened inquiry"):
        protocol.validate_operation_request(request, state)


@pytest.mark.parametrize(
    ("goal_reached", "expected_status", "goal_marker"),
    [(True, "passed", True), (False, "failed", False)],
)
def test_requested_official_assessment_is_runner_owned_and_recorded(
    monkeypatch, tmp_path, goal_reached, expected_status, goal_marker
):
    state = _configure(monkeypatch, tmp_path)
    artifact = tmp_path / "archive" / "candidate"
    artifact.mkdir(parents=True)
    (artifact / "model.zip").write_bytes(b"model")
    (artifact / "artifact.json").write_text("{}", encoding="utf-8")
    (artifact / "policy_runtime.pkl").write_bytes(b"runtime")
    candidate = {
        "id": "T1:checkpoint-10",
        "artifact": repository.repo_relative_path(artifact),
        "fingerprint": repository.artifact_fingerprint(artifact),
        "origin_operation": "T1",
        "name": "checkpoint-10",
        "parameters": {},
        "scientific_commit": "b" * 40,
        "training_steps": 10,
        "evaluation_artifacts": [],
    }
    state["candidates"][candidate["id"]] = candidate
    state["model_roles"]["best_known"] = candidate["id"]
    repository.write_state(state)
    request = {
        "campaign_conclusion": {
            "action": "request_official_assessment",
            "reason": "The explicit best-known model is ready for assessment.",
        }
    }
    run_experiment.accept_operation(request, state)
    assert run_experiment.execute_pending_operation() == 0

    observed = {}

    def evaluate(model_path, *, progress_callback):
        observed["model"] = model_path
        observed["calls"] = observed.get("calls", 0) + 1
        progress_callback(2, 2)
        return {
            "goal_reached": goal_reached,
            "success_percent": 99.0 if goal_reached else 75.0,
            "episodes": 200,
        }

    monkeypatch.setattr(run_experiment.assessment, "evaluate_official_model", evaluate)
    monkeypatch.setattr(repository, "commit_runner_memory", lambda _message: True)
    monkeypatch.setattr(sys, "argv", ["run_experiment.py", "--run-official-assessment"])

    assert run_experiment.main() == 0
    persisted = repository.read_state()
    assert (
        persisted["terminal_state"]["status"]
        == f"official_assessment_{expected_status}"
    )
    assert persisted["official_assessment"]["status"] == expected_status
    assert persisted["official_assessment"]["model"] == candidate["id"]
    assert persisted["official_assessment"]["artifact"] == candidate["artifact"]
    assert persisted["official_assessment"]["fingerprint"] == candidate["fingerprint"]
    assert "200 episodes" in persisted["official_assessment"]["summary"]
    assert observed["model"] == artifact / "model.zip"
    assert paths.GOAL_PATH.exists() is goal_marker
    history = repository.history_records()
    assert history[-1]["kind"] == "campaign_conclusion"
    assert history[-1]["result"]["status"] == f"official_assessment_{expected_status}"
    assert run_experiment.main() == 0
    assert observed["calls"] == 1


def test_session_start_rejects_max_inquiries_mismatch_after_initialization(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    state["scientific_session"] = None
    repository.write_state(state)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_experiment.py",
            "--start-session",
            "goal_review",
            "--session-objective",
            "Make a bounded goal decision.",
            "--backend-session-id",
            "backend-session",
            "--backend-adapter",
            "copilot",
            "--backend-model",
            "gpt-5.6-luna",
            "--backend-reasoning",
            "high",
            "--max-inquiries",
            "7",
        ],
    )

    with pytest.raises(ValueError, match="does not match persisted"):
        run_experiment.main()


def test_fresh_campaign_initialization_sets_max_inquiries(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)
    state["scientific_session"] = None
    state["counters"]["session"] = 0
    repository.write_state(state)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_experiment.py", "--synchronize-max-inquiries", "7"],
    )

    assert run_experiment.main() == 0
    assert repository.read_state()["campaign"]["max_inquiries"] == 7


def test_official_assessment_restart_reconciles_state_and_history(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    artifact = tmp_path / "archive" / "candidate"
    artifact.mkdir(parents=True)
    (artifact / "model.zip").write_bytes(b"model")
    (artifact / "artifact.json").write_text("{}", encoding="utf-8")
    (artifact / "policy_runtime.pkl").write_bytes(b"runtime")
    candidate = {
        "id": "T1:checkpoint-10",
        "artifact": repository.repo_relative_path(artifact),
        "fingerprint": repository.artifact_fingerprint(artifact),
        "origin_operation": "T1",
        "name": "checkpoint-10",
        "parameters": {},
        "scientific_commit": "b" * 40,
        "training_steps": 10,
        "evaluation_artifacts": [],
    }
    state["candidates"][candidate["id"]] = candidate
    state["model_roles"]["best_known"] = candidate["id"]
    repository.write_state(state)
    request = {
        "campaign_conclusion": {
            "action": "request_official_assessment",
            "reason": "The selected model is ready.",
        }
    }
    run_experiment.accept_operation(request, state)
    assert run_experiment.execute_pending_operation() == 0
    monkeypatch.setattr(
        run_experiment.assessment,
        "evaluate_official_model",
        lambda *_args, **_kwargs: {
            "goal_reached": False,
            "success_percent": 75.0,
            "episodes": 200,
        },
    )
    original_upsert = repository.upsert_operation_event
    calls = {"count": 0}

    def fail_once(event):
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError("interrupted history write")
        original_upsert(event)

    monkeypatch.setattr(repository, "upsert_operation_event", fail_once)
    monkeypatch.setattr(repository, "commit_runner_memory", lambda _message: True)
    with pytest.raises(OSError, match="interrupted history write"):
        run_experiment.run_official_assessment()

    interrupted = repository.read_state()
    assert interrupted["terminal_state"]["status"] == "official_assessment_failed"
    assert interrupted["official_assessment"]["status"] == "failed"

    assert run_experiment.run_official_assessment() == 0
    history = repository.history_records()
    assert history[-1]["result"]["status"] == "official_assessment_failed"


@pytest.mark.parametrize(
    ("damage", "message"),
    [("change", "fingerprint changed"), ("remove", "is incomplete")],
)
def test_official_assessment_recovery_revalidates_the_assessed_artifact(
    monkeypatch, tmp_path, damage, message
):
    state = _configure(monkeypatch, tmp_path)
    artifact = tmp_path / "archive" / "candidate"
    artifact.mkdir(parents=True)
    (artifact / "model.zip").write_bytes(b"model")
    (artifact / "artifact.json").write_text("{}", encoding="utf-8")
    (artifact / "policy_runtime.pkl").write_bytes(b"runtime")
    candidate = {
        "id": "T1:checkpoint-10",
        "artifact": repository.repo_relative_path(artifact),
        "fingerprint": repository.artifact_fingerprint(artifact),
        "origin_operation": "T1",
        "name": "checkpoint-10",
        "parameters": {},
        "scientific_commit": "b" * 40,
        "training_steps": 10,
        "evaluation_artifacts": [],
    }
    state["candidates"][candidate["id"]] = candidate
    state["model_roles"]["best_known"] = candidate["id"]
    repository.write_state(state)
    run_experiment.accept_operation(
        {
            "campaign_conclusion": {
                "action": "request_official_assessment",
                "reason": "The selected model is ready.",
            }
        },
        state,
    )
    assert run_experiment.execute_pending_operation() == 0
    monkeypatch.setattr(
        run_experiment.assessment,
        "evaluate_official_model",
        lambda *_args, **_kwargs: {
            "goal_reached": True,
            "success_percent": 100.0,
            "episodes": 200,
        },
    )
    monkeypatch.setattr(
        repository,
        "upsert_operation_event",
        lambda _event: (_ for _ in ()).throw(OSError("interrupted history write")),
    )
    with pytest.raises(OSError, match="interrupted history write"):
        run_experiment.run_official_assessment()

    if damage == "change":
        (artifact / "model.zip").write_bytes(b"changed")
    else:
        (artifact / "model.zip").unlink()
    monkeypatch.setattr(repository, "upsert_operation_event", lambda _event: None)
    with pytest.raises(ValueError, match=message):
        run_experiment.run_official_assessment()
    assert not paths.GOAL_PATH.exists()
