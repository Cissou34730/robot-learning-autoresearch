"""Behavioral tests for the strict schema-6 PI context."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner import build_brief as brief
from runner import repository


def test_startup_brief_exposes_phase_operations_and_artifact_root(
    monkeypatch, tmp_path: Path
):
    from unittest.mock import Mock

    research = tmp_path / "campaigns"
    research.mkdir()
    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        human_goal={
            "source": "contracts/scenario.md",
            "summary": "Reach the protected task success threshold.",
        },
        last_verdict="fresh campaign",
    )
    state["campaign_phase"] = "startup"
    state["scientific_model"] = {
        "status": "ready",
        "path": "pi_workspace/scientific_model.md",
        "commit": "a" * 40,
    }
    state["scientific_session"] = {
        "id": "S1",
        "kind": "startup",
        "objective": "Establish the initial scientific direction.",
        "inquiry_id": None,
        "backend_session_id": "backend-S1",
        "backend_descriptor": {
            "adapter": "copilot",
            "model": "gpt-5.6-luna",
            "reasoning": "high",
        },
        "scientific_parent_commit": "b" * 40,
        "operation_ids": [],
    }
    state["counters"]["session"] = 1
    repository.validate_research_state(state, allow_missing_artifact=True)
    (research / "research_state.json").write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(brief, "RESEARCH_DIR", research)
    compute_availability = brief.runner_protocol.session_operation_availability
    availability = Mock(wraps=compute_availability)
    monkeypatch.setattr(
        brief.runner_protocol, "session_operation_availability", availability
    )

    text = brief.render_research_brief()

    availability.assert_called_once_with(state)
    allowed = compute_availability(state)["allowed_operations"]
    assert "checkpoint" in allowed
    assert "measurement" in allowed
    assert "inquiry" not in allowed
    assert "campaigns/evaluations/campaign/" in text


@pytest.mark.parametrize("status", ["passed", "failed"])
def test_goal_gap_uses_official_assessment(status):
    assessment = {
        "status": status,
        "model": "T1:checkpoint-120832",
        "summary": f"assessment-result-{status}",
    }
    state = {
        "official_assessment": assessment,
        "pi_checkpoint": {"current_goal_gap": "earlier-pi-goal-gap"},
    }

    assert brief._goal_gap(state) == assessment["summary"]


def test_goal_gap_keeps_unassessed_pi_checkpoint():
    checkpoint = {"current_goal_gap": "current-pi-goal-gap"}
    state = {"official_assessment": None, "pi_checkpoint": checkpoint}

    assert brief._goal_gap(state) == checkpoint["current_goal_gap"]


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {
            "session_id": "S1",
            "scientific_commit": "a" * 40,
            "evidence_references": ["T1"],
        },
    ],
)
def test_assessed_checkpoint_preserves_historical_pi_data(metadata):
    checkpoint = {
        field: f"pi-{field}"
        for field in (
            "human_goal_connection",
            "current_goal_gap",
            "current_synthesis",
            "decision_frontier",
            "next_question",
            "candidates_and_roles",
            "next_direction_or_closure",
            "cumulative_resource_use",
        )
    }
    checkpoint.update(inquiry_id=None, completed_operations=[])
    checkpoint.update(metadata)
    state = {
        "official_assessment": {"summary": "official-result"},
        "pi_checkpoint": checkpoint,
        "active_inquiry": None,
    }
    before = json.dumps(state, sort_keys=True)

    lines = brief._checkpoint_lines(state)

    for value in checkpoint.values():
        if isinstance(value, str):
            assert any(value in line for line in lines)
    for reference in checkpoint.get("evidence_references", []):
        assert any(reference in line for line in lines)
    assert json.dumps(state, sort_keys=True) == before
