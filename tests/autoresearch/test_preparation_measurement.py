"""Issue #49: measurements can be requested while preparing the next experiment.

Preparation is where the next experiment, its parent and its initialization are
chosen, yet measurement used to be available only during post-training analysis.
A preparation-phase ``research/evaluation_request.json`` may now measure saved
lineages (``working``, ``best_known`` or a retained ID); it may not name the
candidates of an experiment that has not run. The completed round returns to
preparation, recorded under the upcoming experiment, rather than to analysis.
"""

import json
from pathlib import Path

import pytest

from research import run_experiment
from research import runner_repository as repository
from research.runner_protocol import (
    preparation_measurement_context,
    validate_preparation_evaluation_request,
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
        "reason": "Saved lineage available for preparation measurement.",
    }


def _configure(monkeypatch, tmp_path: Path) -> tuple[Path, Path, Path, dict]:
    research = tmp_path / "research"
    research.mkdir()
    state_path = research / "research_state.json"
    request_path = research / "evaluation_request.json"
    proposal_path = research / "proposal.json"
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.RESEARCH_DIR", research)
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr("research.runner_paths.RESULTS_PATH", research / "results.jsonl")
    monkeypatch.setattr("research.runner_paths.LOG_PATH", research / "EXPERIMENTS.md")
    monkeypatch.setattr(
        "research.runner_paths.EVALUATION_REQUEST_PATH", request_path
    )
    monkeypatch.setattr("research.runner_paths.PROPOSAL_PATH", proposal_path)
    monkeypatch.setattr(
        "research.runner_paths.EVALUATION_DIR", research / "evaluations"
    )
    monkeypatch.setattr(
        "research.run_experiment.validate_research_delta", lambda state: []
    )
    monkeypatch.setattr(
        "research.runner_protocol.evaluation_semantics_fingerprint", lambda: "test"
    )
    artifact = _artifact(tmp_path / "archive" / "working")
    fingerprint = repository.artifact_fingerprint(artifact)
    state = {
        "schema_version": 4,
        "campaign": {"id": "campaign", "started_at": "now", "base_commit": "base"},
        "working_lineage": _lineage("archive/working", fingerprint),
        "best_known_lineage": None,
        "retained_lineages": [],
        "last_experiment": 3,
        "last_allocated_experiment": 3,
        "pending_analysis": None,
        "pending_evaluation_request": None,
        "pending_researcher_decision": None,
        "pending_closure_operation": None,
        "pending_final_benchmark": None,
        "pending_campaign_conclusion": None,
        "campaign_experiment_counters": {"campaign": 3},
        "preparation_conclusion_only": None,
        "official_benchmark_artifact": None,
        "terminal_campaign_status": None,
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return state_path, request_path, proposal_path, state


def _request(candidate: str = "working") -> dict:
    return {
        "question": "Is the saved lineage a suitable parent for the next experiment?",
        "reason": "The parent choice needs a measured panel before proposing.",
        "measurements": [
            {
                "instrument": "research_evaluation",
                "candidate": candidate,
                "episodes": 2,
                "seed": 10,
                "selection": "the saved lineage the parent decision would use",
                "omitted_alternative": None,
            }
        ],
    }


def test_preparation_request_resolves_to_a_lineage_only_context(monkeypatch, tmp_path):
    _, _, _, state = _configure(monkeypatch, tmp_path)

    context = validate_preparation_evaluation_request(_request(), state)

    assert context["preparation"] is True
    assert context["candidates"] == []
    assert context["champion_available"] is False
    assert context["experiment"] == 4
    # Forecasting an identity does not consume it.
    assert state["campaign_experiment_counters"]["campaign"] == 3
    assert "preparation" not in state


def test_preparation_request_rejects_experiment_candidates(monkeypatch, tmp_path):
    _, _, _, state = _configure(monkeypatch, tmp_path)

    with pytest.raises(ValueError, match="unknown measurement candidate"):
        validate_preparation_evaluation_request(
            _request(candidate="experiment-4"), state
        )


def test_preparation_request_rejects_when_no_saved_lineage_exists(
    monkeypatch, tmp_path
):
    _, _, _, state = _configure(monkeypatch, tmp_path)
    state["working_lineage"] = None

    with pytest.raises(ValueError, match="no saved lineages"):
        validate_preparation_evaluation_request(_request(), state)


def test_preparation_request_rejected_while_analysis_is_pending(monkeypatch, tmp_path):
    _, _, _, state = _configure(monkeypatch, tmp_path)
    state["pending_analysis"] = {"experiment": 3}

    with pytest.raises(ValueError, match="post-training analysis is pending"):
        validate_preparation_evaluation_request(_request(), state)


def test_preparation_request_rejected_when_budget_is_exhausted(monkeypatch, tmp_path):
    _, _, _, state = _configure(monkeypatch, tmp_path)
    state["preparation_conclusion_only"] = True

    with pytest.raises(ValueError, match="budget is exhausted"):
        validate_preparation_evaluation_request(_request(), state)


def test_preparation_request_ignores_a_stale_experiment_field(monkeypatch, tmp_path):
    _, _, _, state = _configure(monkeypatch, tmp_path)
    request = _request()
    request["experiment"] = 3

    # The request is still resolved against lineages; the stale experiment field
    # is not trusted. The request itself stays a lineage-only measurement.
    context = validate_preparation_evaluation_request(request, state)
    assert context["experiment"] == 4


def test_preparation_measurement_returns_to_preparation(monkeypatch, tmp_path):
    state_path, request_path, _, _ = _configure(monkeypatch, tmp_path)
    calls: list[int] = []

    def evaluate(artifact, seed, output_path, **kwargs):
        del artifact, kwargs
        calls.append(seed)
        payload = {
            "episodes": 2,
            "seed": seed,
            "success_percent": 50.0,
            "episode_results": [
                {"episode": 0, "episode_seed": seed, "success": True},
                {"episode": 1, "episode_seed": seed + 1, "success": False},
            ],
        }
        output_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    monkeypatch.setattr("research.runner_execution.evaluate_artifact", evaluate)
    request_path.write_text(json.dumps(_request()), encoding="utf-8")
    results_path = tmp_path / "research" / "results.jsonl"

    assert run_experiment.execute_pending_evaluations() == 0

    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["pending_analysis"] is None
    assert persisted["pending_evaluation_request"] is None
    # The next experiment identity is not consumed by the measurement.
    assert persisted["last_experiment"] == 3
    assert persisted["last_allocated_experiment"] == 3
    assert persisted["last_verdict"] == "preparation measurement complete"
    rounds = persisted["preparation_evaluation_rounds"]
    assert [record["round"] for record in rounds] == [1]
    assert rounds[0]["status"] == "completed"
    assert rounds[0]["experiment"] == 4
    assert [
        item["seed"] for item in rounds[0]["results"]["research_evaluations"]
    ] == [10]
    assert [item["seed"] for item in persisted["preparation_partial_evaluations"]] == [
        10
    ]
    assert calls == [10]
    # A preparation measurement is not an experiment-history row.
    assert not results_path.exists() or results_path.read_text(encoding="utf-8") == ""
    assert not request_path.exists()


def test_preparation_measurement_reuses_an_accumulated_panel(monkeypatch, tmp_path):
    _, request_path, _, _ = _configure(monkeypatch, tmp_path)
    calls: list[int] = []

    def evaluate(artifact, seed, output_path, **kwargs):
        del artifact, kwargs
        calls.append(seed)
        payload = {
            "episodes": 2,
            "seed": seed,
            "success_percent": 50.0,
            "episode_results": [
                {"episode": 0, "episode_seed": seed, "success": True},
                {"episode": 1, "episode_seed": seed + 1, "success": False},
            ],
        }
        output_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    monkeypatch.setattr("research.runner_execution.evaluate_artifact", evaluate)
    request_path.write_text(json.dumps(_request()), encoding="utf-8")
    assert run_experiment.execute_pending_evaluations() == 0
    request_path.write_text(json.dumps(_request()), encoding="utf-8")
    assert run_experiment.execute_pending_evaluations() == 0
    # The identical panel is resolved from the accumulated ledger, not re-run.
    assert calls == [10]


def test_preparation_preflight_accepts_a_request_and_rejects_a_conflict(
    monkeypatch, tmp_path
):
    state_path, request_path, proposal_path, _ = _configure(monkeypatch, tmp_path)
    request_path.write_text(json.dumps(_request()), encoding="utf-8")

    assert run_experiment.check_preparation_deliverable() == 0

    proposal_path.write_text(json.dumps({"hypothesis": "next"}), encoding="utf-8")
    assert run_experiment.check_preparation_deliverable() == 1
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["pending_evaluation_request"] is None


def test_preparation_measurement_rounds_are_rendered_during_preparation():
    from research import build_research_brief as brief

    state = {
        "preparation_evaluation_rounds": [
            {
                "round": 1,
                "experiment": 4,
                "question": "is the parent suitable",
                "reason": "parent choice needs evidence",
                "status": "completed",
                "results": {
                    "research_evaluations": [
                        {
                            "candidate": "working",
                            "seed": 10,
                            "episodes": 2,
                            "success_percent": 90.0,
                            "selection": "candidate parent",
                            "evaluation_artifact": "research/evaluations/e.json",
                        }
                    ]
                },
            }
        ]
    }

    rendered = "\n".join(brief._v4_measurement_rounds_section(state, [], None))

    assert "Completed measurement rounds" in rendered
    assert "working" in rendered
    assert "success 90.00%" in rendered
    # Preparation still shows the rationale de-templated, not as a form to copy.
    assert "parent choice needs evidence" in rendered
    assert "Reason:" not in rendered


def test_launcher_executes_a_preparation_measurement_before_proposing():
    assert "--check-preparation-deliverable" in LOOP
    assert "Executing the researcher's saved-lineage measurement request" in LOOP
    assert "Preparation measurement complete" in LOOP
    assert "candidates of a not-yet-run experiment are not available" in LOOP
    # The preparation phase still validates its deliverables with the protected
    # validator, and the analysis phase keeps the closure proposal behavior.
    assert "Get-ProposalSessionStatus" in LOOP


def test_contracts_document_preparation_measurement_scope():
    assert "experiment preparation" in INSTRUMENTS
    assert "saved lineages" in INSTRUMENTS
    assert "candidates of an experiment that has not run" in INSTRUMENTS
    assert "during experiment preparation" in PROGRAM
    assert "saved lineages" in PROGRAM


def test_preparation_measurement_context_is_non_mutating(monkeypatch, tmp_path):
    _, _, _, state = _configure(monkeypatch, tmp_path)

    before = json.loads(json.dumps(state))
    preparation_measurement_context(state)

    assert state == before
