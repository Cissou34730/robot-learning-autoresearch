"""Behavioral tests for the strict schema-6 PI context."""

from __future__ import annotations

import json
from pathlib import Path

from runner import build_brief as brief
from runner import repository


def _state() -> dict:
    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        human_goal={
            "source": "contracts/scenario.md",
            "summary": "Reach and hold with at least 98% official success.",
        },
        last_verdict="measurement completed",
    )
    state["scientific_model"] = {
        "status": "ready",
        "path": "pi_workspace/scientific_model.md",
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
        "backend_descriptor": {
            "adapter": "copilot",
            "model": "gpt-5.6-luna",
            "reasoning": "high",
        },
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
    research = tmp_path / "campaigns"
    research.mkdir()
    state = _state()
    (research / "research_state.json").write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(brief, "RESEARCH_DIR", research)

    text = brief.render_research_brief()
    assert "Reach and hold with at least 98% official success." in text
    assert "Earlier evidence isolates a stabilization failure." in text
    assert "Hold reliability remains below the goal." in text
    assert "Unstable holds prevent the human goal." in text
    assert "`E1` `inquiry` in `I1`: completed" in text
    assert text.count(state["pi_checkpoint"]["current_synthesis"]) == 1


def test_operation_feedback_is_factual_and_operation_specific():
    raw_value = "raw-measurement-value"
    evidence = {
        "episode_results": [{"success": True, "private_value": raw_value}],
        "arbitrary_lab_section": {"series": [{"first": None}, {"later": raw_value}]},
    }
    contents = repository.measurement_artifact_contents(evidence)
    measurement = {
        "kind": "measurement",
        "status": "completed",
        "result": {
            "measurements": [
                {
                    "instrument": "research_evaluation",
                    "label": "candidate panel",
                    "metrics": {
                        "evaluation_artifact": "campaigns/evaluations/panel.json",
                        "success_percent": 97.5,
                        "episodes": 200,
                        "episode_results": evidence["episode_results"],
                        "evaluation_artifact_contents": contents,
                    },
                }
            ],
            "paired_comparisons": [{"candidate": "T2:c", "reference": "T1:c"}],
        },
    }
    training = {
        "kind": "training",
        "result": {
            "initialization": "transfer",
            "parent": "T1:checkpoint-10",
            "seed": 4,
            "requested_steps": 10,
            "completed_steps": 10,
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

    inventory_refs = brief._artifact_inventory_refs({"operation_events": [measurement]})
    measurement_lines = "\n".join(
        brief._event_detail_lines(measurement, inventory_refs=inventory_refs)
    )
    assert "campaigns/evaluations/panel.json" in measurement_lines
    assert "success_percent=97.5" in measurement_lines
    assert "Paired comparisons" in measurement_lines
    key = brief._artifact_inventory_key(contents)
    assert inventory_refs[key] in measurement_lines
    assert json.loads(key) == contents
    assert key in "\n".join(brief._artifact_inventory_lines(inventory_refs))
    assert raw_value not in measurement_lines

    training_lines = "\n".join(
        brief._event_detail_lines(training, inventory_refs=inventory_refs)
    )
    assert training["result"]["parent"] in training_lines
    assert training["result"]["candidates"][0] not in training_lines
    assert "robot_learning/training/algorithm.py" in training_lines


def test_candidate_registry_preserves_every_checkpoint_and_transfer_statistics():
    candidates = {
        "T2:checkpoint-10": {
            "origin_operation": "T2",
            "training_steps": 110,
            "evaluation_artifacts": ["campaigns/evaluations/paired.json"],
        },
        "T2:checkpoint-20": {
            "origin_operation": "T2",
            "training_steps": 120,
            "evaluation_artifacts": [],
        },
    }
    dynamics = [
        {
            "candidate": "T2:checkpoint-10",
            "training_steps": 10,
            "training_success": 0.8,
            "ep_rew_mean": 12.0,
        },
        {
            "candidate": "T2:checkpoint-20",
            "training_steps": 20,
            "training_success": None,
            "ep_rew_mean": None,
        },
    ]
    state = {
        "model_roles": {
            "working": None,
            "best_known": "T2:checkpoint-10",
            "retained": {"control": "T2:checkpoint-20"},
        },
        "candidates": candidates,
        "operation_events": [
            {
                "kind": "training",
                "status": "completed",
                "result": {"learning_dynamics": dynamics},
            }
        ],
    }
    text = "\n".join(brief._candidate_lines(state))
    rows = [line for line in text.splitlines() if line.startswith("| `")]
    assert len(rows) == len(candidates)
    for item in dynamics:
        identifier = item["candidate"]
        candidate = candidates[identifier]
        row = next(line for line in rows if f"`{identifier}`" in line)
        cells = [cell.strip() for cell in row.split("|")]
        assert f"`{candidate['origin_operation']}`" in cells
        assert str(item["training_steps"]) in cells
        assert str(candidate["training_steps"]) in cells
        for field in ("training_success", "ep_rew_mean"):
            value = item[field]
            assert (str(value) if value is not None else "not recorded") in cells
        for artifact in candidate["evaluation_artifacts"]:
            assert artifact in row


def test_artifact_inventory_references_share_only_exact_structures():
    contents = repository.measurement_artifact_contents(
        {"episode_diagnostics": [{"first": None}, {"later": 1}]}
    )
    reordered = dict(reversed(list(contents.items())))
    different = {**contents, "truncated": True}
    measurement = {
        "kind": "measurement",
        "status": "completed",
        "result": {
            "measurements": [
                {
                    "label": label,
                    "metrics": {
                        "evaluation_artifact": f"campaigns/evaluations/{label}.json",
                        "evaluation_artifact_contents": inventory,
                    },
                }
                for label, inventory in [
                    ("first", contents),
                    ("repeat", reordered),
                    ("limited", different),
                    ("unindexed", None),
                ]
            ]
        },
    }
    state = {"operation_events": [measurement]}
    original = json.dumps(state)
    references = brief._artifact_inventory_refs(state)
    assert (
        references[brief._artifact_inventory_key(contents)]
        == references[brief._artifact_inventory_key(reordered)]
    )
    assert (
        references[brief._artifact_inventory_key(contents)]
        != references[brief._artifact_inventory_key(different)]
    )
    registry = "\n".join(brief._artifact_inventory_lines(references))
    details = "\n".join(
        brief._event_detail_lines(measurement, inventory_refs=references)
    )
    for key, reference in references.items():
        assert registry.count(key) == 1
        assert reference in registry
        assert reference in details
    for record in measurement["result"]["measurements"]:
        assert record["metrics"]["evaluation_artifact"] in details
    assert json.dumps(state) == original
    assert "no inventory recorded" in details


def test_failed_and_superseded_attempts_are_history_not_evidence(
    monkeypatch, tmp_path: Path
):
    research = tmp_path / "campaigns"
    research.mkdir()
    state = _state()
    completed = state["operation_events"][0]
    completed["supersedes"] = "E0"
    failed = {
        **completed,
        "id": "E0",
        "result": {"status": "failed", "error": "injected failure"},
        "status": "failed",
        "error": "injected failure",
        "supersedes": None,
        "superseded_by": "E1",
    }
    state["operation_events"] = [failed, completed]
    state["counters"]["event"] = 2
    (research / "research_state.json").write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(brief, "RESEARCH_DIR", research)

    text = brief.render_research_brief()
    evidence = text.split("### Completed operation evidence", 1)[1].split(
        "### Execution history", 1
    )[0]
    history = text.split("### Execution history (not evidence)", 1)[1]

    assert "`E1` `inquiry`" in evidence
    assert "`E0`" not in evidence
    assert "`E0` `inquiry` failed: injected failure; superseded by `E1`." in history
    assert "Strategic resource use" not in text
    assert "completed or allocated" not in text


def test_brief_rejects_unknown_state_fields(monkeypatch, tmp_path: Path):
    research = tmp_path / "campaigns"
    research.mkdir()
    state = _state()
    state["unknown_control_field"] = None
    (research / "research_state.json").write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(brief, "RESEARCH_DIR", research)

    try:
        brief.render_research_brief()
    except RuntimeError as error:
        assert "research state fields are invalid" in str(error)
    else:
        raise AssertionError("incompatible state was rendered")
