"""Issue #48: experiment preparation has a terminal exit.

Preparation historically required a training proposal, so the only way to reach
the official assessment or to record that no further experiment is warranted was
to execute an unwanted experiment first. A preparation-phase ``campaign_conclusion``
now provides both non-experiment exits, recorded as decisions rather than as
experiment-history rows.
"""

import json
from pathlib import Path

import pytest

from research import runner_repository as repository
from research.run_experiment import (
    apply_campaign_conclusion,
    check_proposal,
)
from research.runner_protocol import (
    plan_campaign_conclusion,
    validate_proposal_against_state,
)

ROOT = Path(__file__).resolve().parents[2]
LOOP = (ROOT / "run_research.ps1").read_text(encoding="utf-8")
INSTRUMENTS = (ROOT / "research" / "instruments.md").read_text(encoding="utf-8")
PROGRAM = (ROOT / "research" / "program.md").read_text(encoding="utf-8")


def _artifact(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "model.zip").write_bytes(b"model")
    (path / "artifact.json").write_text("{}", encoding="utf-8")
    (path / "policy_runtime.pkl").write_bytes(b"runtime")
    return path


def _lineage(artifact: str, fingerprint: str) -> dict:
    return {
        "artifact": artifact,
        "fingerprint": fingerprint,
        "origin_experiment": 3,
        "candidate": "checkpoint",
        "parameters": {},
        "scientific_commit": None,
        "training_steps": 120_000,
        "evaluation_artifacts": [],
        "reason": "Measured model selected for official assessment.",
    }


def _configure(monkeypatch, tmp_path: Path) -> tuple[Path, Path, dict]:
    research = tmp_path / "research"
    research.mkdir()
    state_path = research / "research_state.json"
    proposal_path = research / "proposal.json"
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.RESEARCH_DIR", research)
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.PROPOSAL_PATH", proposal_path)
    monkeypatch.setattr("research.runner_paths.RESULTS_PATH", research / "results.jsonl")
    artifact = _artifact(tmp_path / "archive" / "best-known")
    fingerprint = repository.artifact_fingerprint(artifact)
    state = {
        "schema_version": 4,
        "campaign": {"id": "campaign", "started_at": "now", "base_commit": "base"},
        "working_lineage": None,
        "best_known_lineage": _lineage("archive/best-known", fingerprint),
        "retained_lineages": [],
        "last_experiment": 3,
        "pending_analysis": None,
        "pending_researcher_decision": None,
        "pending_evaluation_request": None,
        "pending_final_benchmark": None,
        "pending_scientific_parent": "abc123",
        "official_benchmark_artifact": None,
        "terminal_campaign_status": None,
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return state_path, proposal_path, state


def _conclusion(action: str, reason: str = "The evidence supports this decision."):
    return {"campaign_conclusion": {"action": action, "reason": reason}}


def test_preparation_accepts_a_final_benchmark_conclusion(monkeypatch, tmp_path):
    state_path, _, state = _configure(monkeypatch, tmp_path)

    contract = validate_proposal_against_state(
        _conclusion("request_final_benchmark"), state
    )

    assert contract == "conclusion"
    # Validation is non-mutating.
    assert json.loads(state_path.read_text(encoding="utf-8"))[
        "pending_final_benchmark"
    ] is None


def test_requesting_the_final_benchmark_stages_the_best_known_model(
    monkeypatch, tmp_path
):
    state_path, _, state = _configure(monkeypatch, tmp_path)
    plan = plan_campaign_conclusion(_conclusion("request_final_benchmark"), state)

    apply_campaign_conclusion(plan, state)

    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    pending = persisted["pending_final_benchmark"]
    assert pending["selected"] == "best_known"
    assert pending["artifact"] == "archive/best-known"
    assert pending["fingerprint"] == persisted["best_known_lineage"]["fingerprint"]
    assert persisted["best_known_lineage"] == pending["best_known"]
    assert persisted["campaign_conclusion"]["action"] == "request_final_benchmark"
    assert persisted["terminal_campaign_status"] is None


def test_no_further_experiment_ends_the_campaign_without_an_experiment_row(
    monkeypatch, tmp_path
):
    state_path, _, state = _configure(monkeypatch, tmp_path)
    results_path = tmp_path / "research" / "results.jsonl"
    results_path.write_text("", encoding="utf-8")
    plan = plan_campaign_conclusion(_conclusion("no_further_experiment"), state)

    apply_campaign_conclusion(plan, state)

    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["terminal_campaign_status"] == "no_further_experiment"
    assert persisted["campaign_conclusion"] == {
        "action": "no_further_experiment",
        "reason": "The evidence supports this decision.",
    }
    assert persisted["pending_scientific_parent"] is None
    # A decision, never an experiment-history row.
    assert results_path.read_text(encoding="utf-8") == ""
    # The phase is over: no new proposal is accepted.
    with pytest.raises(ValueError, match="terminal"):
        validate_proposal_against_state(
            _conclusion("no_further_experiment"), persisted
        )


def test_final_benchmark_conclusion_requires_a_designated_best_known(
    monkeypatch, tmp_path
):
    _, _, state = _configure(monkeypatch, tmp_path)
    state["best_known_lineage"] = None

    with pytest.raises(ValueError, match="best-known"):
        plan_campaign_conclusion(_conclusion("request_final_benchmark"), state)


def test_campaign_conclusion_requires_a_known_action_and_reason(
    monkeypatch, tmp_path
):
    _, _, state = _configure(monkeypatch, tmp_path)

    with pytest.raises(ValueError, match="action must be"):
        plan_campaign_conclusion(_conclusion("stop"), state)
    with pytest.raises(ValueError, match="non-empty reason"):
        plan_campaign_conclusion(_conclusion("no_further_experiment", "  "), state)
    with pytest.raises(ValueError, match="only campaign_conclusion"):
        plan_campaign_conclusion(
            {
                "campaign_conclusion": {
                    "action": "no_further_experiment",
                    "reason": "done",
                },
                "hypothesis": "extra",
            },
            state,
        )


def test_campaign_conclusion_is_rejected_while_a_phase_is_pending(
    monkeypatch, tmp_path
):
    _, _, state = _configure(monkeypatch, tmp_path)
    state["pending_analysis"] = {"experiment": 3}

    with pytest.raises(ValueError, match="closure proposal"):
        validate_proposal_against_state(_conclusion("no_further_experiment"), state)


def test_proposal_preflight_accepts_a_campaign_conclusion(
    monkeypatch, tmp_path, capsys
):
    state_path, proposal_path, _ = _configure(monkeypatch, tmp_path)
    proposal_path.write_text(
        json.dumps(_conclusion("no_further_experiment")), encoding="utf-8"
    )

    assert check_proposal() == 0
    assert "PROPOSAL_VALID: conclusion" in capsys.readouterr().out
    # The preflight does not mutate the campaign.
    assert json.loads(state_path.read_text(encoding="utf-8"))[
        "terminal_campaign_status"
    ] is None


def test_preparation_prompt_and_contract_document_the_two_exits():
    assert "requesting the official final assessment" in LOOP
    assert "concluding that no further experiment is warranted" in LOOP
    assert "campaign_conclusion" in INSTRUMENTS
    assert "no_further_experiment" in INSTRUMENTS
    assert "campaign_conclusion" in PROGRAM
