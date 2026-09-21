"""Issue #51: the cost of training-parent eligibility must be stated.

Only a closure-produced record (``working``, ``best_known`` or a retained ID)
can be a future ``training_parent``; every other candidate loses its weights at
closure. These tests pin that the closure prompt, the research brief and the
contract documents state that deletion consequence, so the warning cannot be
silently dropped again.
"""

import json
from pathlib import Path

from research.build_research_brief import render_research_brief

ROOT = Path(__file__).resolve().parents[2]


def _lineage(label, artifact, *, origin=2, reason="Recorded reason."):
    return {
        "candidate": label,
        "origin_experiment": origin,
        "training_steps": 2000,
        "artifact": f"research/checkpoints/{artifact}",
        "fingerprint": f"{label}-fingerprint",
        "scientific_commit": f"{label}-commit",
        "parameters": {},
        "evaluation_artifacts": [],
        "reason": reason,
    }


def _candidate(name, *, success=0.5, reward=5.0, evaluations=None):
    return {
        "name": name,
        "timesteps": int(name.split("-")[-1]),
        "training_success": success,
        "ep_rew_mean": reward,
        "artifact": f"research/checkpoints/{name}",
        "evaluations": evaluations or [],
    }


def _render_brief(monkeypatch, tmp_path, state):
    research_dir = tmp_path / "research"
    research_dir.mkdir(parents=True, exist_ok=True)
    (research_dir / "current_params.json").write_text("{}", encoding="utf-8")
    (research_dir / "postmortems.md").write_text("", encoding="utf-8")
    (research_dir / "results.jsonl").write_text("", encoding="utf-8")
    (research_dir / "research_state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )
    monkeypatch.setattr("research.build_research_brief.ROOT", tmp_path)
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", research_dir)
    return render_research_brief()


def _base_state(pending_candidates):
    return {
        "schema_version": 4,
        "campaign": {"id": "campaign", "base_commit": "base"},
        "working_lineage": _lineage("checkpoint-working", "working"),
        "best_known_lineage": _lineage("checkpoint-best", "best"),
        "retained_lineages": [
            {
                "id": "alternate",
                **_lineage("checkpoint-alternate", "alternate"),
            }
        ],
        "pending_analysis": {
            "experiment": 3,
            "result": {"index": 3},
            "candidates": pending_candidates,
        },
    }


def test_closure_prompt_states_the_deletion_consequence():
    launcher = " ".join((ROOT / "run_research.ps1").read_text(encoding="utf-8").split())

    assert (
        "Retention is the only way a candidate can be used as a future "
        "training parent." in launcher
    )
    assert (
        "Candidates that receive no role have their weights deleted at closure "
        "and can never be extended, re-measured, or compared against later."
        in launcher
    )
    assert "Retain any checkpoint whose future value is uncertain." in launcher
    assert "Retention has no budget and no preferred count." in launcher


def test_brief_marks_which_candidates_lose_weights_at_closure(monkeypatch, tmp_path):
    state = _base_state(
        [_candidate("checkpoint-5120"), _candidate("checkpoint-10240")]
    )
    brief = _render_brief(monkeypatch, tmp_path, state)
    inventory = brief.split("### Current experiment candidate inventory", 1)[1]

    assert (
        "Every candidate listed below loses its weights at closure unless the "
        "closure names it `working`, `best_known`, or retains it with an ID."
        in inventory
    )
    assert "cannot become a future `training_parent`" in inventory
    assert "Retention has no budget and no preferred count" in inventory
    assert "Weights if no role" in inventory
    # Every listed candidate is marked, not only named in prose.
    assert inventory.count("removed unless named") == 2


def test_brief_states_what_training_parent_identifiers_are_and_how_created(
    monkeypatch, tmp_path
):
    state = _base_state([])
    brief = _render_brief(monkeypatch, tmp_path, state)
    section = brief.split("## Current lineages and scientific recipes", 1)[1].split(
        "## Working lineage", 1
    )[0]

    assert (
        "Valid `training_parent` identifiers: `working`, `best_known`, `alternate`"
        in section
    )
    assert "the only models the Runner can verify and restore as a parent" in section
    assert (
        "A new identifier is created only by a closure that names a candidate "
        "`working` or `best_known`, or retains it with an ID" in section
    )
    assert (
        "Candidates without such a role have their weights removed at closure "
        "and cannot become training parents later." in section
    )


def test_contract_documents_provenance_and_retention_deletion():
    instruments = (ROOT / "research" / "instruments.md").read_text(encoding="utf-8")
    program = (ROOT / "research" / "program.md").read_text(encoding="utf-8")

    for text in (instruments, program):
        assert "training_parent" in text
        assert "retain" in text.lower()

    assert "provenance invariant" in instruments
    assert "finalize_pending_v4_closure" in instruments
    assert "irreversible" in instruments
    assert "Retention has no budget and no preferred count" in instruments
    assert "Retention is therefore the only way to create a future" in program
    assert "weights removed at closure" in program
