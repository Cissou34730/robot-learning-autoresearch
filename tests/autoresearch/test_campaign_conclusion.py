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

from research import run_experiment
from research import runner_protocol as protocol
from research import runner_repository as repository
from research.run_experiment import (
    check_proposal,
    resolve_campaign_conclusion,
)
from research.runner_protocol import (
    plan_campaign_conclusion,
    validate_proposal_against_state,
)


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
    monkeypatch.setattr(
        "research.runner_paths.RESULTS_PATH", research / "results.jsonl"
    )
    monkeypatch.setattr("research.runner_paths.LOG_PATH", research / "EXPERIMENTS.md")
    # The preparation anchor is present but its commit is not resolvable outside a
    # real repository; the delta itself is covered by dedicated tests below.
    monkeypatch.setattr(
        "research.run_experiment.anchored_scientific_delta", lambda state: []
    )
    monkeypatch.setattr("research.runner_repository.status_paths", lambda scope: [])
    monkeypatch.setattr("research.runner_repository.campaign_lab_manifest", list)
    artifact = _artifact(tmp_path / "archive" / "best-known")
    fingerprint = repository.artifact_fingerprint(artifact)
    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        last_verdict="fresh",
    )
    state.update(
        working_lineage=_lineage("archive/best-known", fingerprint),
        best_known_lineage=_lineage("archive/best-known", fingerprint),
        last_experiment=3,
        last_allocated_experiment=3,
        pending_scientific_parent="abc123",
    )
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return state_path, proposal_path, state


def _conclusion(action: str, reason: str = "The evidence supports this decision."):
    return {"campaign_conclusion": {"action": action, "reason": reason}}


def _stub_publication(monkeypatch) -> list[str]:
    published: list[str] = []

    def fake_commit(message: str) -> bool:
        published.append(message)
        return True

    monkeypatch.setattr("research.runner_repository.commit_runner_memory", fake_commit)
    monkeypatch.setattr("research.runner_repository.push_head", lambda: None)
    return published


def test_preparation_accepts_a_final_benchmark_conclusion(monkeypatch, tmp_path):
    state_path, _, state = _configure(monkeypatch, tmp_path)

    contract = validate_proposal_against_state(
        _conclusion("request_final_benchmark"), state
    )

    assert contract == "conclusion"
    # Validation is non-mutating.
    assert (
        json.loads(state_path.read_text(encoding="utf-8"))["pending_final_benchmark"]
        is None
    )


def test_requesting_the_final_benchmark_stages_the_best_known_model(
    monkeypatch, tmp_path
):
    state_path, proposal_path, state = _configure(monkeypatch, tmp_path)
    _stub_publication(monkeypatch)
    proposal_path.write_text(
        json.dumps(_conclusion("request_final_benchmark")), encoding="utf-8"
    )

    assert (
        resolve_campaign_conclusion(_conclusion("request_final_benchmark"), state) == 0
    )

    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    pending = persisted["pending_final_benchmark"]
    assert pending["selected"] == "best_known"
    assert pending["artifact"] == "archive/best-known"
    assert pending["fingerprint"] == persisted["best_known_lineage"]["fingerprint"]
    assert persisted["best_known_lineage"] == pending["best_known"]
    assert persisted["campaign_conclusion"]["action"] == "request_final_benchmark"
    assert persisted["terminal_campaign_status"] is None
    # A clean conclusion releases the preparation anchor.
    assert persisted["pending_scientific_parent"] is None
    assert persisted["pending_campaign_conclusion"] is None
    assert proposal_path.exists() is False


def test_no_further_experiment_ends_the_campaign_without_an_experiment_row(
    monkeypatch, tmp_path
):
    state_path, proposal_path, state = _configure(monkeypatch, tmp_path)
    _stub_publication(monkeypatch)
    results_path = tmp_path / "research" / "results.jsonl"
    results_path.write_text("", encoding="utf-8")
    proposal_path.write_text(
        json.dumps(_conclusion("no_further_experiment")), encoding="utf-8"
    )

    assert resolve_campaign_conclusion(_conclusion("no_further_experiment"), state) == 0

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
        validate_proposal_against_state(_conclusion("no_further_experiment"), persisted)


def test_no_further_conclusion_publication_is_retry_safe(monkeypatch, tmp_path):
    state_path, proposal_path, state = _configure(monkeypatch, tmp_path)
    proposal_path.write_text(
        json.dumps(_conclusion("no_further_experiment")), encoding="utf-8"
    )
    calls = {"count": 0}

    def flaky_commit(message: str) -> bool:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("push failed")
        return True

    monkeypatch.setattr("research.runner_repository.commit_runner_memory", flaky_commit)
    monkeypatch.setattr("research.runner_repository.push_head", lambda: None)

    with pytest.raises(RuntimeError, match="push failed"):
        resolve_campaign_conclusion(_conclusion("no_further_experiment"), state)

    # The decision is not yet durable, so no terminal status may be visible; the
    # launcher must not exit before the decision is committed and pushed.
    interrupted = json.loads(state_path.read_text(encoding="utf-8"))
    assert interrupted["terminal_campaign_status"] is None
    assert interrupted["pending_campaign_conclusion"]["progress"] == "planned"

    # A restart resumes the pending decision instead of inheriting terminal state.
    assert resolve_campaign_conclusion(_conclusion("no_further_experiment"), state) == 0
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["terminal_campaign_status"] == "no_further_experiment"
    assert persisted["pending_campaign_conclusion"] is None


def test_final_benchmark_conclusion_requires_a_designated_best_known(
    monkeypatch, tmp_path
):
    _, _, state = _configure(monkeypatch, tmp_path)
    state["best_known_lineage"] = None

    with pytest.raises(ValueError, match="best-known"):
        plan_campaign_conclusion(_conclusion("request_final_benchmark"), state)


def test_campaign_conclusion_requires_a_known_action_and_reason(monkeypatch, tmp_path):
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

    with pytest.raises(ValueError, match="method_decision"):
        validate_proposal_against_state(_conclusion("no_further_experiment"), state)


def test_campaign_conclusion_is_rejected_while_analysis_publication_is_pending(
    monkeypatch, tmp_path
):
    _, _, state = _configure(monkeypatch, tmp_path)
    state["pending_method_decision"] = {"method_id": "method-a", "progress": "durable"}

    with pytest.raises(ValueError, match="decision operation is pending"):
        validate_proposal_against_state(_conclusion("no_further_experiment"), state)
    with pytest.raises(ValueError, match="decision operation is pending"):
        plan_campaign_conclusion(_conclusion("no_further_experiment"), state)


def test_campaign_conclusion_rejects_unresolved_scientific_changes(
    monkeypatch, tmp_path
):
    _, proposal_path, state = _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "research.run_experiment.anchored_scientific_delta",
        lambda state: ["robot_learning/scenario/changed.py"],
    )
    proposal_path.write_text(
        json.dumps(_conclusion("no_further_experiment")), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="unresolved scientific changes"):
        run_experiment.validate_campaign_conclusion_delta(state)


def test_proposal_preflight_accepts_a_clean_campaign_conclusion(
    monkeypatch, tmp_path, capsys
):
    state_path, proposal_path, _ = _configure(monkeypatch, tmp_path)
    proposal_path.write_text(
        json.dumps(_conclusion("no_further_experiment")), encoding="utf-8"
    )

    assert check_proposal() == 0
    assert "PROPOSAL_VALID: conclusion" in capsys.readouterr().out
    # The preflight does not mutate the campaign.
    assert (
        json.loads(state_path.read_text(encoding="utf-8"))["terminal_campaign_status"]
        is None
    )


def test_proposal_preflight_reports_unresolved_science(monkeypatch, tmp_path, capsys):
    _, proposal_path, _ = _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "research.run_experiment.anchored_scientific_delta",
        lambda state: ["robot_learning/scenario/changed.py"],
    )
    proposal_path.write_text(
        json.dumps(_conclusion("no_further_experiment")), encoding="utf-8"
    )

    assert check_proposal() == 1
    assert "unresolved scientific changes" in capsys.readouterr().out


def test_main_rejects_a_conclusion_with_unresolved_science(monkeypatch, tmp_path):
    _, proposal_path, _ = _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "research.run_experiment.anchored_scientific_delta",
        lambda state: ["robot_learning/scenario/changed.py"],
    )
    proposal_path.write_text(
        json.dumps(_conclusion("no_further_experiment")), encoding="utf-8"
    )
    monkeypatch.setattr("sys.argv", ["run_experiment.py"])

    with pytest.raises(ValueError, match="unresolved scientific changes"):
        run_experiment.main()


def test_a_spent_preparation_measurement_round_may_inform_a_conclusion(
    monkeypatch, tmp_path
):
    _, _, state = _configure(monkeypatch, tmp_path)
    state["preparation_measurement"] = {
        "experiment": 4,
        "rounds": [{"round": 1, "evaluations": []}],
    }

    for action in ("request_final_benchmark", "no_further_experiment"):
        assert (
            validate_proposal_against_state(_conclusion(action), state) == "conclusion"
        )


def test_an_unspent_preparation_phase_may_still_conclude(monkeypatch, tmp_path):
    _, _, state = _configure(monkeypatch, tmp_path)
    state["preparation_measurement"] = {"experiment": 4, "rounds": []}

    assert (
        validate_proposal_against_state(_conclusion("request_final_benchmark"), state)
        == "conclusion"
    )


def test_baseline_alone_may_request_the_final_benchmark(monkeypatch, tmp_path):
    _, _, state = _configure(monkeypatch, tmp_path)
    state["last_experiment"] = 1
    state["preparation_measurement"] = {"experiment": 2, "rounds": []}

    assert (
        validate_proposal_against_state(_conclusion("request_final_benchmark"), state)
        == "conclusion"
    )


def test_training_cap_allows_inquiry_close_and_rejects_training(monkeypatch, tmp_path):
    state_path, proposal_path, state = _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(protocol, "scientific_strategy_section", lambda *args: "ok")
    monkeypatch.setattr(protocol, "scientific_strategy_registers", lambda section: {})
    state["inquiry_session"] = {
        "id": "session",
        "campaign_id": "campaign",
        "inquiry_id": 2,
        "role": "principal_investigator",
        "status": "started",
    }
    state["active_inquiry"] = {
        "id": 2,
        "question": "Is the campaign complete?",
        "scope": "Current evidence.",
        "closure_condition": "Record a bounded conclusion.",
        "status": "active",
        "session_id": "session",
        "reframes": [],
    }
    close = {
        "inquiry": {
            "action": "close",
            "outcome": "No further method development is justified.",
        }
    }
    assert (
        validate_proposal_against_state(close, state, training_allocation_closed=True)
        == "inquiry"
    )
    reframe = {
        "inquiry": {
            "action": "reframe",
            "question": "Which non-training evidence resolves the campaign?",
            "scope": "Existing lineages and measurements.",
            "closure_condition": "Record the remaining uncertainty.",
            "rationale": "Training allocation is exhausted.",
        }
    }
    assert (
        validate_proposal_against_state(reframe, state, training_allocation_closed=True)
        == "inquiry"
    )
    state["active_method"] = {
        "id": "method-a",
        "inquiry_id": 2,
        "scientific_question": "Can another method improve learning?",
        "rationale": "It tests a distinct approach.",
        "lifecycle": "development",
        "base_scientific_commit": "abc123",
        "current_lineage": None,
        "iterations": [{"experiment": 3, "status": "continue"}],
        "resolution": None,
    }
    training = {
        "kind": "training",
        "method_id": "method-a",
        "initialization": "fresh",
        "change": "Allocate another run.",
        "investigation_design": {
            "evidence": [{"source": "evidence", "observation": "Observed."}],
            "objective_link": "Objective.",
            "initialization_reason": "Fresh run.",
            "rationale": "Another run.",
            "expected_observation": "A result.",
            "open_question": "What happens?",
        },
    }
    with pytest.raises(ValueError, match="training allocation cap"):
        validate_proposal_against_state(
            training, state, training_allocation_closed=True
        )
    abandon = {
        "method_decision": {
            "action": "abandon",
            "outcome": "The concept is not justified.",
            "reason": "The inquiry evidence rejects the premise before training.",
            "code": {"action": "revert", "reason": "Restore the pre-method recipe."},
        }
    }
    monkeypatch.setattr(repository, "scientific_delta", lambda parent: [])
    assert (
        validate_proposal_against_state(abandon, state, training_allocation_closed=True)
        == "method_decision"
    )
    assert (
        protocol.plan_method_decision(abandon, state)["active_method"]["lifecycle"]
        == "abandoned"
    )
    state["active_method"]["current_lineage"] = dict(state["working_lineage"])
    retain = {
        "method_decision": {
            "action": "retain",
            "outcome": "Keep the developed method as an alternative.",
            "reason": "It remains scientifically useful without replacing working.",
            "retained_id": "method-a-cap",
            "code": {"action": "keep", "reason": "Keep the developed recipe."},
        }
    }
    assert (
        validate_proposal_against_state(retain, state, training_allocation_closed=True)
        == "method_decision"
    )
    retain_plan = protocol.plan_method_decision(retain, state)
    assert retain_plan["active_method"]["lifecycle"] == "retained"
    assert retain_plan["working_record"] == state["working_lineage"]
    state_path.write_text(json.dumps(state), encoding="utf-8")
    proposal_path.write_text(json.dumps(training), encoding="utf-8")
    assert check_proposal(training_allocation_closed=True) == 1
    state["active_inquiry"] = None
    state["active_method"] = None
    state["inquiry_session"] = None
    assert (
        validate_proposal_against_state(
            _conclusion("request_final_benchmark"),
            state,
            training_allocation_closed=True,
        )
        == "conclusion"
    )
