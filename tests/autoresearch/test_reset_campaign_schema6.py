"""Strict schema-6 campaign reset and maintenance-import boundaries."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from research import reset_campaign
from research import runner_paths as paths
from research import runner_repository as repository


def _bind_paths(monkeypatch: pytest.MonkeyPatch, root: Path) -> Path:
    research = root / "research"
    values = {
        "ROOT": root,
        "RESEARCH_DIR": research,
        "LOG_PATH": research / "EXPERIMENTS.md",
        "RESULTS_PATH": research / "results.jsonl",
        "OPERATION_REQUEST_PATH": research / "operation_request.json",
        "STATE_PATH": research / "research_state.json",
        "TRAINING_LOG_DIR": research / "training_logs",
        "SCIENTIFIC_MODEL_PATH": research / "scientific_model.md",
        "RECOVERY_PENDING_PATH": research / "RECOVERY_PENDING",
        "RESTART_PENDING_PATH": research / "RESTART_PENDING",
        "CANDIDATE_ROOT": root / "models" / "candidates",
        "EVALUATION_DIR": research / "evaluations",
    }
    for name, value in values.items():
        monkeypatch.setattr(paths, name, value)
    return research


def _candidate(fingerprint: str) -> dict:
    return {
        "id": "T1:checkpoint-10",
        "artifact": "research/checkpoints/candidates/source/t1/checkpoint-10",
        "fingerprint": fingerprint,
        "origin_operation": "T1",
        "name": "checkpoint-10",
        "parameters": {"algorithm": {"name": "ppo"}},
        "scientific_commit": "a" * 40,
        "training_steps": 10,
        "evaluation_artifacts": ["research/evaluations/source/panel.json"],
    }


def _prepared_source_state(candidate: dict) -> dict:
    state = repository.empty_campaign_state(
        campaign={
            "id": "source",
            "started_at": "now",
            "base_commit": "base",
        },
        last_verdict="prepared model",
    )
    state["scientific_model"] = {
        "status": "ready",
        "path": "research/scientific_model.md",
        "commit": "b" * 40,
    }
    state["candidates"] = {candidate["id"]: copy.deepcopy(candidate)}
    state["model_roles"] = {
        "working": candidate["id"],
        "best_known": candidate["id"],
        "retained": {},
    }
    repository.validate_research_state(state, allow_missing_artifact=True)
    return state


def test_fresh_campaign_writes_only_schema6_memory(monkeypatch, tmp_path):
    research = _bind_paths(monkeypatch, tmp_path)
    obsolete = (
        "operation_request.json",
        "BASELINE_PENDING",
        "proposal.json",
        "evaluation_request.json",
        "postmortems.md",
        "archive.md",
        "last_train_summary.md",
        "last_evaluation.json",
        "brief.md",
        "scientific_model.md",
    )
    for relative in obsolete:
        target = research / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("stale\n", encoding="utf-8")
    (research / "checkpoints" / "accepted").mkdir(parents=True)
    (research / "checkpoints" / "accepted" / "envelope.json").write_text(
        "{}\n", encoding="utf-8"
    )
    (research / "results.jsonl").write_text('{"legacy": true}\n', encoding="utf-8")
    monkeypatch.setattr(reset_campaign, "git", lambda *_args, **_kwargs: "head\n")

    state = reset_campaign.write_fresh_campaign(None)

    assert state["schema_version"] == 6
    assert set(state) == repository.STATE_FIELDS
    assert state["scientific_model"] == {
        "status": "pending",
        "path": "research/scientific_model.md",
        "commit": None,
    }
    assert state["model_roles"] == {
        "working": None,
        "best_known": None,
        "retained": {},
    }
    assert state["candidates"] == {}
    assert state["operation_events"] == []
    assert state["pending_operation"] is None
    assert state["active_inquiry"] is None
    assert state["pi_checkpoint"] is None
    assert state["scientific_session"] is None
    assert not {
        "baseline",
        "inquiry_session",
        "active_method",
        "pending_analysis",
        "last_experiment",
    } & set(state)
    assert json.loads(paths.STATE_PATH.read_text(encoding="utf-8")) == state
    assert paths.RESULTS_PATH.read_text(encoding="utf-8") == ""
    assert paths.LOG_PATH.read_text(
        encoding="utf-8"
    ) == repository.render_operation_log([])
    assert not (research / "checkpoints").exists()
    for relative in obsolete:
        assert not (research / relative).exists()
    with pytest.raises(ValueError, match="scientific model must be ready"):
        repository.start_scientific_session(
            state, kind="goal_review", objective="Choose the first operation."
        )


def test_recipe_import_excludes_campaign_memory_and_laboratory(monkeypatch):
    monkeypatch.setattr(
        reset_campaign.protocol,
        "plan_recipe_paths",
        lambda _commit: {
            "parent": "source",
            "restore": [
                "robot_learning/scenario/reward.py",
                "research/current_params.json",
                "research/lab/diagnostic.py",
            ],
            "remove_created": ["robot_learning/training/obsolete.py"],
        },
    )

    assert reset_campaign.scientific_plan("source") == {
        "parent": "source",
        "restore": [
            "robot_learning/scenario/reward.py",
            "research/current_params.json",
        ],
        "remove_created": ["robot_learning/training/obsolete.py"],
    }

    monkeypatch.setattr(
        reset_campaign.protocol,
        "plan_recipe_paths",
        lambda _commit: {
            "parent": "source",
            "restore": ["research/evaluations/source/evidence.json"],
            "remove_created": [],
        },
    )
    with pytest.raises(RuntimeError, match="non-scientific path"):
        reset_campaign.scientific_plan("source")


def test_baseline_import_builds_clean_schema6_state():
    candidate = _candidate("f" * 64)
    source_state = _prepared_source_state(candidate)

    state = reset_campaign.baseline_state(
        source_state,
        candidate,
        base_commit="base",
        recipe_source=candidate["scientific_commit"],
    )

    assert state["campaign"]["id"] != source_state["campaign"]["id"]
    assert state["campaign"]["recipe_source_commit"] == candidate["scientific_commit"]
    assert state["scientific_model"] == source_state["scientific_model"]
    assert state["candidates"] == {candidate["id"]: candidate}
    assert state["model_roles"] == {
        "working": candidate["id"],
        "best_known": candidate["id"],
        "retained": {},
    }
    assert state["active_inquiry"] is None
    assert state["pi_checkpoint"] is None
    assert state["scientific_session"] is None
    assert state["operation_events"] == []
    assert state["pending_operation"] is None
    assert state["terminal_state"] is None
    assert state["official_assessment"] is None


def test_baseline_source_requires_one_schema6_prepared_candidate(monkeypatch):
    contents = {
        "model.zip": b"model",
        "artifact.json": b'{"timesteps": 10}',
        "policy_runtime.pkl": b"runtime",
    }
    fingerprint = hashlib.sha256(
        contents["model.zip"]
        + contents["artifact.json"]
        + contents["policy_runtime.pkl"]
    ).hexdigest()
    candidate = _candidate(fingerprint)
    state = _prepared_source_state(candidate)
    artifact = candidate["artifact"]
    committed = {
        "research/research_state.json",
        "research/scientific_model.md",
        candidate["evaluation_artifacts"][0],
        *(f"{artifact}/{name}" for name in contents),
    }

    monkeypatch.setattr(reset_campaign, "git_json", lambda *_args: state)
    monkeypatch.setattr(reset_campaign, "commit_files", lambda _commit: committed)
    monkeypatch.setattr(reset_campaign, "resolve_commit", lambda value, _label: value)
    monkeypatch.setattr(
        reset_campaign, "verify_task_compatibility", lambda _commit: None
    )
    monkeypatch.setattr(
        reset_campaign,
        "scientific_plan",
        lambda commit: {"parent": commit, "restore": [], "remove_created": []},
    )

    def committed_bytes(_commit: str, relative: str) -> bytes:
        if relative == "research/scientific_model.md":
            return b"scientific model"
        name = relative.rsplit("/", 1)[-1]
        if name not in contents:
            raise RuntimeError("missing optional file")
        return contents[name]

    monkeypatch.setattr(reset_campaign, "git_bytes", committed_bytes)

    restored_state, restored_candidate, restore, recipe = (
        reset_campaign.verify_baseline_source("source")
    )

    assert restored_state == state
    assert restored_candidate == candidate
    assert set(restore) == committed - {"research/research_state.json"}
    assert recipe["parent"] == candidate["scientific_commit"]

    legacy = copy.deepcopy(state)
    legacy["schema_version"] = 5
    monkeypatch.setattr(reset_campaign, "git_json", lambda *_args: legacy)
    with pytest.raises(ValueError, match="schema 6"):
        reset_campaign.verify_baseline_source("source")


def test_clean_reset_refuses_and_preserves_unrelated_untracked_files(monkeypatch):
    calls: list[tuple[str, ...]] = []

    def fake_git(*arguments: str, **_kwargs) -> str:
        calls.append(arguments)
        if arguments[:2] == ("ls-files", "--others"):
            return "docs/inquiry-centered-lifecycle-redesign.md\0research/brief.md\0"
        return ""

    monkeypatch.setattr(reset_campaign, "git", fake_git)

    with pytest.raises(RuntimeError, match="docs/inquiry-centered"):
        reset_campaign.clean_campaign_changes()
    assert not any(arguments[:2] == ("clean", "-fd") for arguments in calls)
