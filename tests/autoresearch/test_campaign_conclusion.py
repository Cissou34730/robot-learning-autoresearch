"""Campaign-level terminal decisions in the goal-centered lifecycle."""

from __future__ import annotations

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
    }.items():
        monkeypatch.setattr(paths, name, value)
    monkeypatch.setattr(repository, "git", lambda *args: "a" * 40 + "\n")
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
        state, kind="goal_review", objective="Decide the campaign outcome."
    )
    repository.write_state(state)
    return state


def test_no_credible_route_is_terminal_without_allocating_training(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    request = {
        "campaign_conclusion": {
            "action": "no_credible_route",
            "reason": "The durable evidence leaves no credible path.",
        }
    }
    run_experiment.accept_operation(request, state)
    assert run_experiment.execute_pending_operation() == 0
    persisted = repository.read_state()
    assert persisted["terminal_state"]["status"] == "no_credible_route"
    assert persisted["counters"]["training"] == 0
    assert persisted["scientific_session"] is None


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
            "action": "no_credible_route",
            "reason": "No route remains.",
        }
    }
    with pytest.raises(ValueError, match="opened inquiry"):
        protocol.validate_operation_request(request, state)
