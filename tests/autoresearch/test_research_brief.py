"""Behavioral tests for the strict schema-6 PI context."""

from __future__ import annotations

import json
from pathlib import Path

from research import build_research_brief as brief
from research import runner_repository as repository


def _state() -> dict:
    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        human_goal={
            "source": "research/scenario.md",
            "summary": "Reach and hold with at least 98% official success.",
        },
        last_verdict="measurement completed",
    )
    state["scientific_model"] = {
        "status": "ready",
        "path": "research/scientific_model.md",
        "commit": "a" * 40,
    }
    state["active_inquiry"] = {
        "id": "I1",
        "question": "What prevents reliable stabilization?",
        "goal_connection": "Unstable holds prevent the human goal.",
        "closure_condition": "Evidence selects or rejects a stabilization route.",
        "rationale": "The result changes the next goal-directed operation.",
        "opened_in_session": "S1",
        "reframes": [],
    }
    state["scientific_session"] = {
        "id": "S2",
        "kind": "inquiry",
        "objective": "Resolve the stabilization question.",
        "inquiry_id": "I1",
        "backend_session_id": "backend-S2",
        "scientific_parent_commit": "b" * 40,
        "operation_ids": ["E1"],
    }
    state["counters"].update(inquiry=1, session=2, event=1)
    state["operation_events"] = [
        {
            "id": "E1",
            "kind": "inquiry",
            "session_id": "S2",
            "inquiry_id": "I1",
            "request": {
                "action": "reframe",
                "question": "What prevents reliable stabilization?",
                "goal_connection": "Unstable holds prevent the human goal.",
                "closure_condition": "Evidence selects or rejects a route.",
                "rationale": "The current evidence narrows the question.",
            },
            "result": {
                "status": "completed",
                "action": "reframe",
                "inquiry_id": "I1",
            },
            "status": "completed",
            "error": None,
            "supersedes": None,
            "superseded_by": None,
            "completed_at": "now",
        }
    ]
    state["pi_checkpoint"] = {
        "session_id": "S1",
        "inquiry_id": "I1",
        "human_goal_connection": "Reliable stabilization is required.",
        "current_goal_gap": "Hold reliability remains below the goal.",
        "current_synthesis": "Earlier evidence isolates a stabilization failure.",
        "evidence_references": ["E1"],
        "decision_frontier": "Whether the revised diagnostic changes the route.",
        "completed_operations": ["E1"],
        "candidates_and_roles": "No role is assigned.",
        "next_direction_or_closure": "Inspect the new diagnostic result.",
        "cumulative_resource_use": "One measurement.",
        "scientific_commit": "b" * 40,
    }
    repository.validate_research_state(state, allow_missing_artifact=True)
    return state


def test_brief_leads_with_goal_evidence_gap_inquiry_and_checkpoint(
    monkeypatch, tmp_path: Path
):
    research = tmp_path / "research"
    research.mkdir()
    (research / "research_state.json").write_text(
        json.dumps(_state()), encoding="utf-8"
    )
    monkeypatch.setattr(brief, "RESEARCH_DIR", research)

    text = brief.render_research_brief()
    headings = [
        "## Human goal",
        "## Best evidence relative to the goal",
        "## Current goal gap",
        "## Active inquiry and goal relevance",
        "## Latest durable PI checkpoint",
        "## Available artifacts and evidence",
        "## Strategic resource use",
    ]
    positions = [text.index(heading) for heading in headings]
    assert positions == sorted(positions)
    assert "Reach and hold with at least 98% official success." in text
    assert "Earlier evidence isolates a stabilization failure." in text
    assert "Hold reliability remains below the goal." in text
    assert "Unstable holds prevent the human goal." in text
    assert "`E1` `inquiry` in `I1`: completed" in text


def test_operation_feedback_is_factual_and_operation_specific():
    measurement = {
        "kind": "measurement",
        "result": {
            "measurements": [
                {
                    "instrument": "research_evaluation",
                    "label": "candidate panel",
                    "metrics": {
                        "evaluation_artifact": "research/evaluations/panel.json",
                        "success_percent": 97.5,
                        "episodes": 200,
                        "episode_results": [{"success": True}],
                    },
                }
            ],
            "paired_comparisons": [{"candidate": "T2:c", "reference": "T1:c"}],
        },
    }
    training = {
        "kind": "training",
        "result": {
            "candidates": ["T2:checkpoint-10"],
            "learning_dynamics": [
                {
                    "candidate": "T2:checkpoint-10",
                    "training_steps": 10,
                    "training_success": 0.8,
                    "ep_rew_mean": 12.0,
                }
            ],
            "mechanical_provenance": {
                "code_parent_commit": "a" * 40,
                "changed_files": [{"path": "robot_learning/training/algorithm.py"}],
            },
        },
    }

    measurement_lines = "\n".join(brief._event_detail_lines(measurement))
    assert "research/evaluations/panel.json" in measurement_lines
    assert "success_percent=97.5" in measurement_lines
    assert "Paired comparisons" in measurement_lines
    assert "episode_results" not in measurement_lines

    training_lines = "\n".join(brief._event_detail_lines(training))
    assert "T2:checkpoint-10" in training_lines
    assert "training_success" in training_lines
    assert "robot_learning/training/algorithm.py" in training_lines


def test_brief_rejects_non_schema6_state(monkeypatch, tmp_path: Path):
    research = tmp_path / "research"
    research.mkdir()
    state = _state()
    state["pending_analysis"] = None
    (research / "research_state.json").write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(brief, "RESEARCH_DIR", research)

    try:
        brief.render_research_brief()
    except RuntimeError as error:
        assert "research state fields are invalid" in str(error)
    else:
        raise AssertionError("legacy state was rendered")
