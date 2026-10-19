"""Strict schema-6 factual campaign report."""

from __future__ import annotations

import copy
import json

import pytest

from runner import repository
from tools import campaign_report


def _event(
    identifier: str,
    kind: str,
    request: dict,
    result: dict,
    *,
    status: str = "completed",
    session_id: str = "S1",
    inquiry_id: str | None = "I1",
    supersedes: str | None = None,
    superseded_by: str | None = None,
) -> dict:
    error = result.get("error") if status == "failed" else None
    return {
        "id": identifier,
        "kind": kind,
        "session_id": session_id,
        "inquiry_id": inquiry_id,
        "request": request,
        "result": result,
        "status": status,
        "error": error,
        "supersedes": supersedes,
        "superseded_by": superseded_by,
        "completed_at": f"2026-01-01T00:00:0{len(identifier)}Z",
    }


def _campaign_repository(tmp_path):
    campaign_id = "11111111-1111-1111-1111-111111111111"
    state = repository.empty_campaign_state(
        campaign={
            "id": campaign_id,
            "started_at": "2026-01-01T00:00:00Z",
            "base_commit": "a" * 40,
            "recipe_source_commit": "b" * 40,
        },
        last_verdict="official assessment goal reached",
        human_goal={
            "source": "contracts/scenario.md",
            "summary": "Reach and hold on the protected task.",
        },
    )
    state["scientific_model"] = {
        "status": "ready",
        "path": "pi_workspace/scientific_model.md",
        "commit": "c" * 40,
    }
    candidate_id = "T2:checkpoint-10"
    candidate = {
        "id": candidate_id,
        "artifact": "campaigns/checkpoints/candidates/campaign/t2/checkpoint-10",
        "fingerprint": "d" * 64,
        "origin_operation": "T2",
        "name": "checkpoint-10",
        "parameters": {"algorithm": {"name": "ppo"}},
        "scientific_commit": "e" * 40,
        "training_steps": 10,
        "evaluation_artifacts": [
            "campaigns/evaluations/campaign/development-panel.json"
        ],
    }
    measurement_request = {
        "description": "Measure the selected candidate.",
        "rationale": "The panel result informs the next goal decision.",
        "measurements": [
            {
                "instrument": "research_evaluation",
                "candidate": candidate_id,
                "episodes": 2,
                "seed": 100,
            }
        ],
    }
    failed_measurement = _event(
        "M1",
        "measurement",
        measurement_request,
        {"status": "failed", "error": "instrument interrupted"},
        status="failed",
        superseded_by="M2",
    )
    measurement_result = {
        "status": "completed",
        "measurements": [
            {
                "instrument": "research_evaluation",
                "candidate": candidate_id,
                "candidate_id": candidate_id,
                "label": "development panel",
                "metrics": {
                    "episodes": 2,
                    "seed": 100,
                    "success_percent": 50.0,
                    "evaluation_semantics": "semantics-v1",
                    "evaluation_artifact": (
                        "campaigns/evaluations/campaign/development-panel.json"
                    ),
                    "evaluation_artifact_fingerprint": "f" * 64,
                    "model_fingerprint": candidate["fingerprint"],
                },
            },
            {
                "instrument": "research_evaluation",
                "candidate": candidate_id,
                "candidate_id": candidate_id,
                "label": "development panel repeat",
                "metrics": {
                    "episodes": 2,
                    "seed": 100,
                    "success_percent": 50.0,
                    "evaluation_semantics": "semantics-v1",
                    "evaluation_artifact": (
                        "campaigns/evaluations/campaign/development-panel-repeat.json"
                    ),
                    "evaluation_artifact_fingerprint": "1" * 64,
                    "model_fingerprint": candidate["fingerprint"],
                },
            },
        ],
        "paired_comparisons": [],
        "tool_provenance": None,
    }
    completed_measurement = _event(
        "M2",
        "measurement",
        measurement_request,
        measurement_result,
        supersedes="M1",
    )
    training_request = {
        "initialization": "fresh",
        "seed": 7,
        "steps": 10,
        "description": "Train the current recipe.",
        "rationale": "Learning dynamics inform the route.",
    }
    failed_training = _event(
        "T1",
        "training",
        training_request,
        {"status": "failed", "error": "worker interrupted"},
        status="failed",
        superseded_by="T2",
    )
    completed_training = _event(
        "T2",
        "training",
        training_request,
        {
            "status": "completed",
            "initialization": "fresh",
            "parent": None,
            "seed": 7,
            "requested_steps": 10,
            "completed_steps": 10,
            "scientific_commit": candidate["scientific_commit"],
            "mechanical_provenance": {
                "code_parent_commit": "a" * 40,
                "changed_files": [],
            },
            "candidates": [candidate_id],
            "learning_dynamics": [
                {
                    "candidate": candidate_id,
                    "training_steps": 10,
                    "training_success": 0.5,
                    "ep_rew_mean": 12.0,
                }
            ],
        },
        supersedes="T1",
    )
    inquiry_open = _event(
        "E1",
        "inquiry",
        {
            "action": "open",
            "question": "Does the selected route close the goal gap?",
            "goal_connection": "The answer determines the campaign route.",
            "closure_condition": "Measure and decide.",
            "rationale": "The bounded question can change the next decision.",
        },
        {"status": "completed", "action": "open", "inquiry_id": "I1"},
        session_id="S0",
        inquiry_id="I1",
    )
    role_event = _event(
        "E2",
        "model_role",
        {
            "action": "set_best_known",
            "candidate": candidate_id,
            "reason": "Completed evidence supports the explicit role.",
            "evidence": ["T2", "M2"],
        },
        {
            "status": "assigned",
            "action": "set_best_known",
            "candidate": candidate_id,
            "evidence": ["T2", "M2"],
        },
    )
    checkpoint_request = {
        "human_goal_connection": (
            "The measured candidate is the current route toward the human goal."
        ),
        "current_goal_gap": "The final protected assessment is still outstanding.",
        "current_synthesis": (
            "Training and development measurements support goal review."
        ),
        "evidence_references": ["T2", "M2"],
        "decision_frontier": (
            "Choose whether the recorded evidence supports closing the inquiry."
        ),
        "completed_operations": ["E1", "T2", "M2", "E2"],
        "candidates_and_roles": (
            "T2:checkpoint-10 is best-known and retained for assessment."
        ),
        "next_direction_or_closure": (
            "Close the inquiry and request official assessment."
        ),
        "cumulative_resource_use": (
            "Two training attempts, two measurement attempts, one inquiry."
        ),
    }
    checkpoint_event = _event(
        "E3",
        "checkpoint",
        checkpoint_request,
        {"status": "completed", "session_id": "S1"},
    )
    inquiry_close = _event(
        "E4",
        "inquiry",
        {
            "action": "close",
            "outcome": "The route is ready for goal review.",
            "reason": "The closure condition is satisfied.",
        },
        {
            "status": "completed",
            "action": "close",
            "inquiry_id": "I1",
            "outcome": "The route is ready for goal review.",
            "reason": "The closure condition is satisfied.",
        },
    )
    conclusion = _event(
        "E5",
        "campaign_conclusion",
        {
            "action": "request_official_assessment",
            "reason": "The explicitly selected model is ready.",
        },
        {"status": "official_assessment_passed", "model": candidate_id},
        session_id="S2",
        inquiry_id=None,
    )
    state["operation_events"] = [
        inquiry_open,
        failed_training,
        completed_training,
        failed_measurement,
        completed_measurement,
        role_event,
        checkpoint_event,
        inquiry_close,
        conclusion,
    ]
    state["counters"] = {
        "inquiry": 1,
        "session": 2,
        "measurement": 2,
        "training": 2,
        "event": 5,
    }
    state["pi_checkpoint"] = {
        "session_id": "S1",
        "inquiry_id": "I1",
        **checkpoint_request,
        "scientific_commit": candidate["scientific_commit"],
    }
    state["candidates"] = {candidate_id: candidate}
    state["model_roles"] = {
        "working": None,
        "best_known": candidate_id,
        "retained": {"assessment": candidate_id},
    }
    state["terminal_state"] = {
        "status": "official_assessment_passed",
        "reason": "The explicitly selected model is ready.",
        "model": candidate_id,
    }
    state["official_assessment"] = {
        "status": "passed",
        "model": candidate_id,
        "artifact": candidate["artifact"],
        "fingerprint": candidate["fingerprint"],
        "summary": "goal reached; success 98.0%; 200 episodes",
        "completed_at": "2026-01-01T01:00:00Z",
    }

    runner_state = tmp_path / "runner" / "state"
    runner_state.mkdir(parents=True)
    campaigns = tmp_path / "campaigns"
    campaigns.mkdir()
    (runner_state / "research_state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )
    (campaigns / "results.jsonl").write_text(
        "".join(
            json.dumps({"campaign_id": campaign_id, **event}) + "\n"
            for event in state["operation_events"]
        ),
        encoding="utf-8",
    )
    usage = tmp_path / "reports" / "session_usage"
    usage.mkdir(parents=True)
    (usage / f"{campaign_id}.jsonl").write_text(
        json.dumps(
            {
                "campaign_id": campaign_id,
                "phase": "inquiry",
                "attempt": 1,
                "session_id": "backend-1",
                "recorded_at": "2026-01-01T00:30:00Z",
                "model": "gpt-5.6-luna",
                "reasoning": "high",
                "duration_seconds": 12.5,
                "exit_code": 0,
                "input_tokens": 1000,
                "cache_read_tokens": 400,
                "output_tokens": 100,
                "aiu": 1.5,
                "tool_calls": 3,
                "tools_by_name": {"view": 2, "apply_patch": 1},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return state


def test_report_accounts_for_schema6_lifecycle_without_retired_shapes(tmp_path):
    _campaign_repository(tmp_path)

    campaign = campaign_report.load_campaign(tmp_path)
    campaign["state"]["pi_checkpoint"]["completed_operations"] = ["E5"]
    campaign["state"]["pi_checkpoint"]["candidates_and_roles"] = (
        "Current state changed after the historical checkpoint."
    )
    checkpoint_rows = campaign_report.checkpoint_history_rows(campaign)
    assert checkpoint_rows[0][8] == "E1, T2, M2, E2"
    assert (
        checkpoint_rows[0][9]
        == "T2:checkpoint-10 is best-known and retained for assessment."
    )

    report = campaign_report.render_report([campaign])

    assert "Completed operation evidence" in report
    assert "Failed and superseded execution history" in report
    assert "These attempts are execution history and are not counted" in report
    assert "M1" in report and "superseded by" in report.lower()
    assert "T1" in report and "T2" in report
    assert "Completed measurements" in report
    assert "Completed training operations" in report
    assert "Development-panel reuse accounting" in report
    assert "research_evaluation | unavailable | unavailable | 100 | 2" in report
    assert "2 | 1 | M2, M2 | yes" in report
    assert "Model-role assignment history" in report
    assert "set_best_known" in report
    assert "Operation decisions" in report
    assert "Train the current recipe." in report
    assert "Learning dynamics inform the route." in report
    assert "The explicitly selected model is ready." in report
    assert "Checkpoint history" in report
    assert (
        "The measured candidate is the current route toward the human goal." in report
    )
    assert "The final protected assessment is still outstanding." in report
    assert "Training and development measurements support goal review." in report
    assert "T2, M2" in report
    assert "| Completed operations | Candidates and roles |" in report
    assert "E1, T2, M2, E2" in report
    assert "T2:checkpoint-10 is best-known and retained for assessment." in report
    assert (
        "Choose whether the recorded evidence supports closing the inquiry." in report
    )
    assert "Close the inquiry and request official assessment." in report
    assert "Two training attempts, two measurement attempts, one inquiry." in report
    assert "Does the selected route close the goal gap?" in report
    assert "official_assessment_passed" in report
    assert "success 98.0%; 200 episodes" in report
    assert "New input tokens (input minus cache reads) | 600.00" in report
    assert "method" not in report.lower()
    assert "pending_analysis" not in report
    assert "experiment" not in report.lower()


def test_report_requires_exact_current_schema6_state(tmp_path):
    state = _campaign_repository(tmp_path)
    state["schema_version"] = 5
    (tmp_path / "runner" / "state" / "research_state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )

    with pytest.raises(RuntimeError, match="unsupported research state schema"):
        campaign_report.load_campaign(tmp_path)

    state["schema_version"] = 6
    state["pending_analysis"] = copy.deepcopy(state["pending_operation"])
    (tmp_path / "runner" / "state" / "research_state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="pending_analysis"):
        campaign_report.load_campaign(tmp_path)


@pytest.mark.parametrize("defect", ["duplicate", "reordered", "content", "foreign"])
def test_report_rejects_non_exact_results_history(tmp_path, defect):
    state = _campaign_repository(tmp_path)
    path = tmp_path / "campaigns" / "results.jsonl"
    rows = [
        {"campaign_id": state["campaign"]["id"], **event}
        for event in state["operation_events"]
    ]
    if defect == "duplicate":
        rows.append(copy.deepcopy(rows[-1]))
        message = "duplicate results operation event id"
    elif defect == "reordered":
        rows[0], rows[1] = rows[1], rows[0]
        message = "in order and content"
    elif defect == "content":
        rows[0]["completed_at"] = "2026-01-02T00:00:00Z"
        message = "in order and content"
    else:
        rows[0]["campaign_id"] = "22222222-2222-2222-2222-222222222222"
        message = "foreign campaign"
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        campaign_report.load_campaign(tmp_path)


def test_report_rejects_dangling_supersession(tmp_path):
    state = _campaign_repository(tmp_path)
    failed = next(event for event in state["operation_events"] if event["id"] == "T1")
    successor = next(
        event for event in state["operation_events"] if event["id"] == "T2"
    )
    failed["superseded_by"] = "T999"
    successor["supersedes"] = None
    (tmp_path / "runner" / "state" / "research_state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="superseded_by link is dangling"):
        campaign_report.load_campaign(tmp_path)


def test_report_rejects_unknown_role_candidate(tmp_path):
    state = _campaign_repository(tmp_path)
    state["model_roles"]["working"] = "T999:missing"
    (tmp_path / "runner" / "state" / "research_state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="working names an unknown candidate"):
        campaign_report.load_campaign(tmp_path)
