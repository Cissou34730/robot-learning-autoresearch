"""Campaign isolation contracts retained by the strict schema-6 lifecycle."""

from __future__ import annotations

import json
import uuid

from research import runner_paths, runner_protocol
from research import runner_repository as repository


def _campaign(identifier: str) -> dict:
    return {
        "id": identifier,
        "started_at": "2026-09-01T12:00:00Z",
        "base_commit": "a" * 40,
    }


def test_campaign_identity_and_default_inquiry_guard_are_explicit():
    identifier = str(uuid.uuid4())
    state = repository.empty_campaign_state(
        campaign=_campaign(identifier),
        last_verdict="fresh",
    )

    assert repository.current_campaign_id(state) == identifier
    assert state["campaign"]["max_inquiries"] == repository.DEFAULT_MAX_INQUIRIES
    assert state["counters"] == {
        "inquiry": 0,
        "session": 0,
        "measurement": 0,
        "training": 0,
        "event": 0,
    }


def test_campaign_artifact_paths_are_isolated_by_campaign_and_operation():
    campaign_one = str(uuid.uuid4())
    campaign_two = str(uuid.uuid4())

    assert runner_paths.campaign_candidate_root(campaign_one) != (
        runner_paths.campaign_candidate_root(campaign_two)
    )
    assert runner_paths.campaign_checkpoint_root(campaign_one) != (
        runner_paths.campaign_checkpoint_root(campaign_two)
    )
    assert runner_paths.campaign_evaluation_dir(campaign_one) != (
        runner_paths.campaign_evaluation_dir(campaign_two)
    )
    assert runner_paths.campaign_retained_root(campaign_one) != (
        runner_paths.campaign_retained_root(campaign_two)
    )
    assert runner_paths.training_log_path("T3", 2, campaign_one).name == (
        "t3-attempt-2.log"
    )


def test_measurement_artifact_names_use_operation_identity():
    research_name = runner_protocol.evaluation_artifact_name(
        "M4",
        "T2:checkpoint-100",
        100,
        42,
        "abc123",
        campaign_id="campaign-one",
    )
    reference_name = runner_protocol.task_reference_artifact_name(
        "M5",
        "T2:checkpoint-100",
        "reach",
        campaign_id="campaign-one",
    )

    assert "campaign-one" in research_name
    assert "-m4-" in research_name
    assert "100ep-seed42-abc123" in research_name
    assert "campaign-one" in reference_name
    assert "-m5-" in reference_name
    assert "-reach" in reference_name


def test_operation_history_preserves_campaign_attribution(monkeypatch, tmp_path):
    results = tmp_path / "results.jsonl"
    log = tmp_path / "EXPERIMENTS.md"
    monkeypatch.setattr(runner_paths, "RESULTS_PATH", results)
    monkeypatch.setattr(runner_paths, "LOG_PATH", log)
    event = {
        "campaign_id": "campaign-one",
        "id": "E1",
        "kind": "inquiry",
        "session_id": "S1",
        "inquiry_id": "I1",
        "request": {
            "action": "close",
            "outcome": "The bounded question is resolved.",
            "reason": "The closure condition was met.",
        },
        "result": {
            "status": "completed",
            "action": "close",
            "inquiry_id": "I1",
            "outcome": "The bounded question is resolved.",
            "reason": "The closure condition was met.",
        },
        "status": "completed",
        "error": None,
        "supersedes": None,
        "superseded_by": None,
        "completed_at": "2026-09-01T12:01:00Z",
    }

    repository.upsert_operation_event(event)

    persisted = [
        json.loads(line)
        for line in results.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert persisted == [event]
    assert "| E1 | inquiry | I1 | completed |" in log.read_text(encoding="utf-8")


def test_runner_memory_includes_terminal_goal_marker():
    assert repository.is_runner_memory("research/GOAL_REACHED")
