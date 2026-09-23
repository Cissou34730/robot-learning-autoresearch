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
from research import runner_repository as repository
from research.run_experiment import (
    begin_hypothesis_phase,
    check_proposal,
    resolve_campaign_conclusion,
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
    monkeypatch.setattr(
        "research.runner_paths.RESULTS_PATH", research / "results.jsonl"
    )
    monkeypatch.setattr("research.runner_paths.LOG_PATH", research / "EXPERIMENTS.md")
    # The preparation anchor is present but its commit is not resolvable outside a
    # real repository; the delta itself is covered by dedicated tests below.
    monkeypatch.setattr(
        "research.run_experiment.anchored_scientific_delta", lambda state: []
    )
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
        "pending_campaign_conclusion": None,
        "pending_closure_operation": None,
        "pending_scientific_parent": "abc123",
        "preparation_conclusion_only": None,
        "official_benchmark_artifact": None,
        "terminal_campaign_status": None,
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return state_path, proposal_path, state


def _conclusion(action: str, reason: str = "The evidence supports this decision."):
    if action == "request_final_benchmark":
        return {
            "campaign_conclusion": {
                "action": action,
                "terminal_expectation": {
                    "expected_verdict": "goal_reached",
                    "reason": reason,
                },
            }
        }
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
    # A clean conclusion releases the preparation anchor and the budget flag.
    assert persisted["pending_scientific_parent"] is None
    assert persisted["preparation_conclusion_only"] is None
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

    with pytest.raises(ValueError, match="closure proposal"):
        validate_proposal_against_state(_conclusion("no_further_experiment"), state)


def test_campaign_conclusion_is_rejected_while_a_closure_is_pending(
    monkeypatch, tmp_path
):
    _, _, state = _configure(monkeypatch, tmp_path)
    # A closure can be durable while its pending analysis field is already clear.
    state["pending_closure_operation"] = {"experiment": 3, "progress": "durable"}

    with pytest.raises(ValueError, match="closure operation is pending"):
        validate_proposal_against_state(_conclusion("no_further_experiment"), state)
    with pytest.raises(ValueError, match="closure operation is pending"):
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


def test_a_spent_preparation_measurement_round_owes_an_experiment_proposal(
    monkeypatch, tmp_path
):
    """Issue: measuring in preparation must not buy a free terminal decision.

    Campaigns e88f7b9e and 7624cdd2 both ended by measuring already-saved
    lineages during preparation - which consumes no experiment - and then
    concluding from that round. The round is requested because its result would
    change the next decision, and in this phase that decision is which
    experiment to prepare, so the phase still owes a proposal.
    """
    _, _, state = _configure(monkeypatch, tmp_path)
    state["preparation_measurement"] = {
        "experiment": 4,
        "rounds": [{"round": 1, "evaluations": []}],
    }

    for action in ("request_final_benchmark", "no_further_experiment"):
        with pytest.raises(ValueError, match="owes an experiment proposal"):
            validate_proposal_against_state(_conclusion(action), state)


def test_an_unspent_preparation_phase_may_still_conclude(monkeypatch, tmp_path):
    _, _, state = _configure(monkeypatch, tmp_path)
    state["preparation_measurement"] = {"experiment": 4, "rounds": []}

    assert (
        validate_proposal_against_state(_conclusion("request_final_benchmark"), state)
        == "conclusion"
    )


def test_budget_reached_allows_a_conclusion_and_rejects_training(monkeypatch, tmp_path):
    """The launcher's --conclusion-only preparation path, exercised directly."""
    state_path, _, _ = _configure(monkeypatch, tmp_path)

    assert begin_hypothesis_phase(conclusion_only=True) == 0

    anchored = json.loads(state_path.read_text(encoding="utf-8"))
    assert anchored["preparation_conclusion_only"] is True
    # A phase that may not prepare an experiment at all still concludes, even
    # after spending a measurement round.
    anchored["preparation_measurement"] = {
        "experiment": 4,
        "rounds": [{"round": 1, "evaluations": []}],
    }

    with pytest.raises(ValueError, match="budget is exhausted"):
        validate_proposal_against_state({"hypothesis": "another run"}, anchored)
    assert (
        validate_proposal_against_state(
            _conclusion("request_final_benchmark"), anchored
        )
        == "conclusion"
    )


def test_launcher_restricts_a_budget_reached_phase_to_conclusions():
    # The budget no longer breaks the loop before preparation; it asks the
    # runner for a conclusion-only anchor and offers only the two exits.
    assert '"--begin-hypothesis", "--conclusion-only"' in LOOP
    assert "Experiment budget reached" in LOOP
    assert "Only a campaign conclusion may be prepared" in LOOP
    assert "Current phase: conclude the campaign." in LOOP
    assert "pending_campaign_conclusion" in LOOP, (
        "an interrupted conclusion must resume rather than exit on terminal state"
    )


def test_launcher_retry_after_budget_reached_offers_only_conclusions():
    # The retry after a validation failure must branch on the reached budget;
    # otherwise it offers an experiment or a saved-lineage measurement that the
    # conclusion-only state rejects, and following it consumes the one retry.
    retry = LOOP.split("$retryPrompt = @(", 1)[1].split(
        "Invoke-ResearcherSession -Prompt $retryPrompt", 1
    )[0]
    budget_branch, _, ordinary_branch = retry.partition("else {")

    assert "$budgetReached" in budget_branch
    assert "which must contain a campaign_conclusion" in budget_branch
    assert "containing only a campaign_conclusion" in budget_branch
    # The exhausted-budget branch must not offer an experiment or a
    # saved-lineage measurement; the conclusion-only anchor rejects both.
    assert "for experiment $nextExperiment" not in budget_branch
    assert "saved-lineage research/evaluation_request.json" not in budget_branch
    # The ordinary retry still offers the two preparation deliverables.
    assert "for experiment $nextExperiment" in ordinary_branch
    assert "saved-lineage research/evaluation_request.json" in ordinary_branch
    assert "which must contain a campaign_conclusion" not in ordinary_branch


def test_preparation_prompt_and_contract_document_the_two_exits():
    assert "requesting the official final assessment" in LOOP
    assert "concluding that no further experiment is warranted" in LOOP
    assert "campaign_conclusion" in INSTRUMENTS
    assert "no_further_experiment" in INSTRUMENTS
    assert "campaign_conclusion" in PROGRAM
