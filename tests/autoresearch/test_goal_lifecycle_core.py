"""Behavioral contract for the strict goal-centered Runner core."""

from __future__ import annotations

import atexit
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from runner import (
    build_brief,
    execution,
    invocation_result,
    paths,
    protocol,
    repository,
    run_experiment,
)
from runner.launcher import phases, summaries


def _init_git_worktree(path: Path) -> None:
    git_dir = Path(os.environ.get("TEMP", str(path.parent))) / f"{path.name}.gitdir"
    if git_dir.exists():
        import shutil

        shutil.rmtree(git_dir)
    subprocess.run(
        ["git", "-C", str(path), "init", "--quiet", "--separate-git-dir", str(git_dir)],
        check=True,
    )


def _short_worktree(prefix: str) -> Path:
    root = Path(__file__).resolve().parents[2] / ".pytest-worktrees"
    root.mkdir(exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix=prefix, dir=root))
    atexit.register(shutil.rmtree, path, ignore_errors=True)
    return path


def _configure(monkeypatch, tmp_path: Path) -> dict:
    research = tmp_path / "campaigns"
    research.mkdir()
    replacements = {
        "ROOT": tmp_path,
        "RESEARCH_DIR": research,
        "STATE_PATH": research / "research_state.json",
        "RESULTS_PATH": research / "results.jsonl",
        "LOG_PATH": research / "EXPERIMENTS.md",
        "OPERATION_REQUEST_PATH": research / "operation_request.json",
        "SCIENTIFIC_MODEL_PATH": tmp_path / "pi_workspace" / "scientific_model.md",
        "TRAINING_LOG_DIR": research / "training_logs",
        "CANDIDATE_ROOT": tmp_path / "models" / "candidates",
        "EVALUATION_DIR": research / "evaluations",
    }
    for name, value in replacements.items():
        monkeypatch.setattr(paths, name, value)
    monkeypatch.setattr(repository, "git", lambda *args: "a" * 40 + "\n")
    monkeypatch.setattr(repository, "scientific_delta", lambda _parent: [])
    monkeypatch.setattr(run_experiment, "TIMESTEPS", 10)
    monkeypatch.setattr(repository, "campaign_lab_manifest", list)
    monkeypatch.setattr(
        run_experiment, "_protected_panel_overlap", lambda *_args: False
    )
    monkeypatch.setattr(
        repository, "publish_scientific_recipe", lambda *_args: "a" * 40
    )
    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        human_goal={
            "source": "contracts/scenario.md",
            "summary": "Reach the protected task success threshold.",
        },
        last_verdict="fresh campaign",
    )
    state["scientific_model"] = {
        "status": "ready",
        "path": "pi_workspace/scientific_model.md",
        "commit": "a" * 40,
    }
    repository.write_state(state)
    return state


def _artifact(path: Path, marker: bytes = b"model") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "model.zip").write_bytes(marker)
    (path / "artifact.json").write_text(
        json.dumps({"timesteps": 10, "completed": True}), encoding="utf-8"
    )
    (path / "policy_runtime.pkl").write_bytes(b"runtime:" + marker)
    return path


def _candidate(identifier: str, artifact: Path) -> dict:
    return {
        "id": identifier,
        "artifact": repository.repo_relative_path(artifact),
        "fingerprint": repository.artifact_fingerprint(artifact),
        "origin_operation": "T1",
        "name": "checkpoint-10",
        "parameters": {"training": {"n_envs": 1}},
        "scientific_commit": "b" * 40,
        "training_steps": 10,
        "evaluation_artifacts": [],
    }


def _superseded_inquiry_events() -> list[dict]:
    request = {
        "action": "open",
        "question": "Which behavior blocks the goal?",
        "goal_connection": "The behavior determines the next useful operation.",
        "closure_condition": "Resolve or reject the proposed distinction.",
        "rationale": "The inquiry focuses the bounded session.",
    }
    return [
        {
            "id": "E1",
            "kind": "inquiry",
            "session_id": "S0",
            "inquiry_id": None,
            "request": request,
            "result": {"status": "failed", "error": "injected failure"},
            "status": "failed",
            "error": "injected failure",
            "supersedes": None,
            "superseded_by": "E2",
            "completed_at": "now",
        },
        {
            "id": "E2",
            "kind": "inquiry",
            "session_id": "S0",
            "inquiry_id": "I0",
            "request": request,
            "result": {
                "status": "completed",
                "action": "open",
                "inquiry_id": "I0",
            },
            "status": "completed",
            "error": None,
            "supersedes": "E1",
            "superseded_by": None,
            "completed_at": "now",
        },
    ]


def _model_role_event(candidate_id: str, evidence: list[str]) -> dict:
    return {
        "id": "E3",
        "kind": "model_role",
        "session_id": "S0",
        "inquiry_id": None,
        "request": {
            "action": "set_best_known",
            "candidate": candidate_id,
            "reason": "Assign the candidate from recorded evidence.",
            "evidence": evidence,
        },
        "result": {
            "status": "assigned",
            "action": "set_best_known",
            "candidate": candidate_id,
            "evidence": evidence,
        },
        "status": "completed",
        "error": None,
        "supersedes": None,
        "superseded_by": None,
        "completed_at": "now",
    }


def _start_session(state: dict, kind: str, objective: str) -> dict:
    if kind == "startup" and state["counters"]["session"] == 0:
        state["campaign_phase"] = "startup"
    session = repository.start_scientific_session(
        state,
        kind=kind,
        objective=objective,
        backend_adapter="copilot",
        backend_model="gpt-5.6-luna",
        backend_reasoning="high",
    )
    repository.write_state(state)
    return session


def _checkpoint(state: dict) -> dict:
    session = state["scientific_session"]
    return {
        "checkpoint": {
            "human_goal_connection": "This work addresses the current task gap.",
            "current_goal_gap": "The policy has not met the protected objective.",
            "current_synthesis": "The completed operations establish factual behavior.",
            "evidence_references": list(session["operation_ids"]),
            "decision_frontier": "Choose whether to continue or close the inquiry.",
            "next_question": "Which uncertainty should the next session resolve?",
            "completed_operations": list(session["operation_ids"]),
            "candidates_and_roles": "Candidates are available; roles remain explicit.",
            "next_direction_or_closure": "Start a fresh bounded session.",
            "cumulative_resource_use": "One bounded session.",
        }
    }


def test_state_is_a_strict_schema7_operation_state(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)

    assert state["model_roles"] == {
        "working": None,
        "best_known": None,
        "retained": {},
    }
    assert state["pending_operation"] is None
    assert state["active_inquiry"] is None
    assert state["scientific_session"] is None
    assert state["pi_checkpoint"] is None
    assert state["campaign_phase"] == "recipe_development"
    assert state["recipe_development"] is None
    assert state["operation_events"] == []
    assert set(state) == repository.STATE_FIELDS


@pytest.mark.parametrize(
    "sessions, kind, phase",
    [(0, None, "startup"), (1, "startup", "startup"), (2, "goal_review", "research")],
)
def test_schema6_read_normalizes_without_writing(
    monkeypatch, tmp_path, sessions, kind, phase
):
    state = _configure(monkeypatch, tmp_path)
    if kind is not None:
        state["campaign_phase"] = phase
        _start_session(state, kind, "Continue the existing scientific session.")
    state.pop("campaign_phase")
    state.pop("recipe_development")
    state["schema_version"] = 6
    state["counters"]["session"] = sessions
    serialized = json.dumps(state)
    paths.STATE_PATH.write_text(serialized, encoding="utf-8")

    loaded = repository.load_state(allow_missing_artifact=True)

    assert loaded["schema_version"] == 7
    assert loaded["campaign_phase"] == phase
    assert loaded["recipe_development"] is None
    assert paths.STATE_PATH.read_text(encoding="utf-8") == serialized
    monkeypatch.setattr(repository, "git", lambda *_args: serialized)
    assert repository.read_committed_state("HEAD") == loaded
    launcher_path = tmp_path / "runner" / "state" / "research_state.json"
    launcher_path.parent.mkdir(parents=True)
    launcher_path.write_text(serialized, encoding="utf-8")
    assert summaries.load_state(tmp_path) == loaded
    assert launcher_path.read_text(encoding="utf-8") == serialized


@pytest.mark.parametrize("cap", [0, 15])
def test_fresh_flow_checkpoints_both_initial_phases_before_the_inquiry_cap(
    monkeypatch, tmp_path, cap
):
    state = _configure(monkeypatch, tmp_path)
    state["campaign"]["max_inquiries"] = cap
    monkeypatch.setattr(repository, "commit_runner_memory", lambda _message: True)
    assert phases.session_kind(state) == "recipe_development"
    assert not phases.inquiry_cap_reached(state)
    for number, kind, next_phase in (
        (1, "recipe_development", "startup"),
        (2, "startup", "research"),
    ):
        session = _start_session(
            state, kind, "Resolve the initial scientific decision."
        )
        assert session["id"] == f"S{number}"
        assert not phases.inquiry_cap_reached(state)
        run_experiment.accept_operation(_checkpoint(state), state)
        assert run_experiment.execute_pending_operation() == 0
        state = repository.load_state(allow_missing_artifact=True)
        assert state["campaign_phase"] == next_phase
        assert state["scientific_session"] is None
        assert state["pending_operation"] is None
        assert state["pi_checkpoint"]["session_id"] == f"S{number}"
        if number == 1:
            handoff = copy.deepcopy(state["recipe_development"])
            assert handoff == state["pi_checkpoint"]
            assert not phases.inquiry_cap_reached(state)
            assert phases.session_kind(state) == "startup"
        else:
            assert state["recipe_development"] == handoff
            assert state["recipe_development"] != state["pi_checkpoint"]
    assert phases.session_kind(state) == "goal_review"
    assert phases.inquiry_cap_reached(state) is (cap == 0)
    assert state["counters"]["training"] == 0
    assert state["counters"]["inquiry"] == 0
    assert [event["id"] for event in state["operation_events"]] == ["E1", "E2"]


@pytest.mark.parametrize(
    "failure_point", ["result_record", "completion_commit", "finalization_commit"]
)
def test_development_checkpoint_retries_without_republishing_or_training(
    monkeypatch, tmp_path, failure_point
):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "recipe_development", "Compare the scientific recipes.")
    run_experiment.accept_operation(_checkpoint(state), state)
    published = []
    monkeypatch.setattr(
        repository,
        "publish_scientific_recipe",
        lambda *_args: published.append("recipe") or "a" * 40,
    )
    monkeypatch.setattr(
        execution,
        "train_candidate",
        lambda *_args, **_kwargs: pytest.fail("checkpoint must not train"),
    )
    original_upsert = repository.upsert_operation_event
    failed = False

    def upsert(event):
        nonlocal failed
        if failure_point == "result_record" and not failed:
            failed = True
            raise OSError("injected publication failure")
        original_upsert(event)

    def commit(message):
        nonlocal failed
        target = (
            "complete E1 checkpoint"
            if failure_point == "completion_commit"
            else "finalize E1"
        )
        if failure_point != "result_record" and message == target and not failed:
            failed = True
            raise OSError("injected publication failure")
        return True

    monkeypatch.setattr(repository, "upsert_operation_event", upsert)
    monkeypatch.setattr(repository, "commit_runner_memory", commit)
    writes = []
    original_write = repository.write_state

    def write(current):
        original_write(current)
        writes.append(copy.deepcopy(current))

    monkeypatch.setattr(repository, "write_state", write)
    with pytest.raises(OSError, match="injected publication failure"):
        run_experiment.execute_pending_operation()
    interrupted = repository.load_state(allow_missing_artifact=True)
    assert interrupted["pending_operation"]["failure"] is None
    if failure_point == "result_record":
        assert interrupted["campaign_phase"] == "recipe_development"
        assert interrupted["recipe_development"] is None
        assert interrupted["pi_checkpoint"] is None
        assert interrupted["scientific_session"]["id"] == "S1"
    else:
        assert interrupted["campaign_phase"] == "startup"
        assert interrupted["recipe_development"] == interrupted["pi_checkpoint"]
        assert interrupted["scientific_session"] is None
    assert run_experiment.execute_pending_operation() == 0
    completed = repository.load_state(allow_missing_artifact=True)
    assert published == ["recipe"]
    assert completed["pending_operation"] is None
    assert completed["campaign_phase"] == "startup"
    assert completed["recipe_development"] == completed["pi_checkpoint"]
    assert completed["counters"] == interrupted["counters"]
    assert [event["id"] for event in completed["operation_events"]] == ["E1"]
    assert [event["id"] for event in repository.history_records()] == ["E1"]
    for snapshot in writes:
        pending = snapshot["pending_operation"]
        if pending is not None and pending["progress"] != "completed":
            assert snapshot["recipe_development"] is None
            assert snapshot["campaign_phase"] == "recipe_development"
        if snapshot["recipe_development"] is not None:
            assert snapshot["scientific_session"] is None
            assert snapshot["campaign_phase"] == "startup"
            assert snapshot["pi_checkpoint"] == snapshot["recipe_development"]


@pytest.mark.parametrize(
    "mutation, message",
    [
        ("phase", "recipe_development phase"),
        ("session", "session S1"),
        ("inquiry", "without an inquiry"),
        ("evidence", "recipe_development evidence_references"),
        ("record", "completed checkpoint event"),
        ("event", "completed checkpoint event"),
        ("completed", "completed_operations"),
        ("latest", "startup must follow"),
        ("research", "startup checkpoint"),
        ("shape", "recipe_development requires exactly"),
    ],
)
def test_development_handoff_requires_consistent_phase_session_and_evidence(
    monkeypatch, tmp_path, mutation, message
):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "recipe_development", "Compare scientific recipes.")
    monkeypatch.setattr(repository, "commit_runner_memory", lambda _message: True)
    run_experiment.accept_operation(_checkpoint(state), state)
    assert run_experiment.execute_pending_operation() == 0
    state = repository.read_state()
    handoff = state["recipe_development"]
    if mutation == "phase":
        state["campaign_phase"] = "recipe_development"
    elif mutation == "session":
        handoff["session_id"] = "S9"
    elif mutation == "inquiry":
        handoff["inquiry_id"] = "I1"
    elif mutation == "evidence":
        handoff["evidence_references"] = ["M404"]
    elif mutation == "record":
        handoff["current_synthesis"] = "A different saved interpretation."
    elif mutation == "event":
        state["operation_events"].clear()
    elif mutation == "completed":
        handoff["completed_operations"] = ["E1"]
        state["operation_events"][0]["request"]["completed_operations"] = ["E1"]
    elif mutation == "latest":
        state["pi_checkpoint"]["current_synthesis"] = "A later interpretation."
    elif mutation == "research":
        state["campaign_phase"] = "research"
    elif mutation == "shape":
        handoff.pop("session_id")
    with pytest.raises(ValueError, match=message):
        repository.validate_research_state(state, allow_missing_artifact=True)


@pytest.mark.parametrize("phase", ["recipe_development", "startup"])
def test_initial_phases_refuse_active_inquiries(monkeypatch, tmp_path, phase):
    state = _configure(monkeypatch, tmp_path)
    state["campaign_phase"] = phase
    state["active_inquiry"] = {
        "id": "I1",
        "question": "Question",
        "goal_connection": "Connection",
        "closure_condition": "Condition",
        "rationale": "Rationale",
        "opened_in_session": "S1",
        "handoff_conclusion": "Conclusion",
        "handoff_question": "Question",
        "handoff_source_session_id": "S1",
        "reframes": [],
    }
    with pytest.raises(
        ValueError, match="active_inquiry requires campaign phase research"
    ):
        repository.validate_research_state(state, allow_missing_artifact=True)


def test_session_kind_must_match_campaign_phase(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "recipe_development", "Compare scientific recipes.")
    state["campaign_phase"] = "startup"
    with pytest.raises(
        ValueError, match="kind recipe_development requires phase recipe_development"
    ):
        repository.validate_research_state(state, allow_missing_artifact=True)


def test_brief_keeps_development_handoff_separate_from_latest_startup_record(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(build_brief, "RESEARCH_DIR", paths.RESEARCH_DIR)
    monkeypatch.setattr(repository, "commit_runner_memory", lambda _message: True)
    for kind in ("recipe_development", "startup"):
        _start_session(state, kind, "Resolve the initial scientific decision.")
        assert f"`{kind}`" in "\n".join(build_brief._active_inquiry_lines(state))
        request = _checkpoint(state)
        request["checkpoint"]["current_synthesis"] = f"Saved interpretation for {kind}."
        run_experiment.accept_operation(request, state)
        assert run_experiment.execute_pending_operation() == 0
        state = repository.read_state()
        rendered = build_brief.render_research_brief()
        assert f"`{state['campaign_phase']}`" in rendered
        handoff = state["recipe_development"]
        assert handoff["current_synthesis"] in rendered
        assert handoff["next_question"] in rendered
        assert state["pi_checkpoint"]["current_synthesis"] in rendered
        assert handoff["current_synthesis"] in "\n".join(
            build_brief._checkpoint_lines(state, development=True)
        )
    assert state["recipe_development"]["session_id"] == "S1"
    assert state["pi_checkpoint"]["session_id"] == "S2"


def test_brief_normalizes_legacy_state_without_rewriting_it(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(build_brief, "RESEARCH_DIR", paths.RESEARCH_DIR)
    _start_session(state, "startup", "Review the existing recipe.")
    state["schema_version"] = 6
    state.pop("campaign_phase")
    state.pop("recipe_development")
    serialized = json.dumps(state)
    paths.STATE_PATH.write_text(serialized, encoding="utf-8")
    assert "`startup`" in build_brief.render_research_brief()
    assert paths.STATE_PATH.read_text(encoding="utf-8") == serialized


def test_one_pending_transaction_freezes_the_request(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Choose the first useful operation.")
    request = {
        "training": {
            "initialization": "fresh",
            "seed": 7,
            "steps": 10,
            "description": "Train the current scientific recipe.",
            "rationale": "Its learning dynamics inform the next goal decision.",
        }
    }
    pending = run_experiment.accept_operation(request, state)

    assert pending["id"] == "T1"
    assert run_experiment.accept_operation(request, repository.read_state()) == pending
    changed = json.loads(json.dumps(request))
    changed["training"]["seed"] = 8
    with pytest.raises(ValueError, match="different Runner operation"):
        run_experiment.accept_operation(changed, repository.read_state())


def test_training_returns_facts_to_same_session_without_assigning_roles(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    session = _start_session(state, "startup", "Establish useful model evidence.")
    request = {
        "training": {
            "initialization": "fresh",
            "seed": 7,
            "steps": 10,
            "description": "Train the current scientific recipe.",
            "rationale": "Learning dynamics will inform the next goal decision.",
        }
    }
    monkeypatch.setattr(
        run_experiment.research_config,
        "load_experiment_config",
        lambda: {"training": {"n_envs": 1}},
    )
    run_experiment.accept_operation(request, state)
    archived_artifact = _artifact(tmp_path / "archive" / "checkpoint")
    archived = [
        {
            "name": "checkpoint-10",
            "artifact": repository.repo_relative_path(archived_artifact),
            "fingerprint": repository.artifact_fingerprint(archived_artifact),
            "timesteps": 10,
            "training_success": 0.5,
            "ep_rew_mean": 12.0,
        }
    ]
    monkeypatch.setattr(repository, "scientific_delta", lambda _parent: [])
    monkeypatch.setattr(
        repository, "publish_scientific_recipe", lambda *_args: "b" * 40
    )
    monkeypatch.setattr(execution, "validate_active_configuration", dict)
    monkeypatch.setattr(execution, "train_candidate", lambda *args, **kwargs: 1.0)
    monkeypatch.setattr(
        execution,
        "candidate_directories",
        lambda _path: [
            {
                "name": "checkpoint-10",
                "path": archived_artifact,
                "timesteps": 10,
            }
        ],
    )
    monkeypatch.setattr(
        repository, "archive_candidates", lambda *args, **kwargs: archived
    )
    monkeypatch.setattr(execution, "remove_candidate_dir", lambda _path: None)

    assert run_experiment.execute_pending_operation() == 0
    persisted = repository.read_state()
    event = persisted["operation_events"][-1]
    assert event["id"] == "T1"
    assert event["result"]["seed"] == 7
    assert event["result"]["requested_steps"] == 10
    assert event["result"]["scientific_commit"] == "b" * 40
    assert event["result"]["mechanical_provenance"]["changed_files"] == []
    assert persisted["scientific_session"]["id"] == session["id"]
    assert persisted["scientific_session"]["operation_ids"] == ["T1"]
    assert persisted["model_roles"] == {
        "working": None,
        "best_known": None,
        "retained": {},
    }
    assert "T1:checkpoint-10" in persisted["candidates"]


def test_completed_training_rejects_existing_candidate_key(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Train without replacing prior evidence.")
    existing_artifact = _artifact(tmp_path / "archive" / "existing", b"existing")
    existing = _candidate("T1:checkpoint-10", existing_artifact)
    state["candidates"][existing["id"]] = existing
    repository.write_state(state)
    request = {
        "training": {
            "initialization": "fresh",
            "seed": 7,
            "steps": 10,
            "description": "Train the current scientific recipe.",
            "rationale": "The result must not replace an existing candidate.",
        }
    }
    monkeypatch.setattr(
        run_experiment.research_config,
        "load_experiment_config",
        lambda: {"training": {"n_envs": 1}},
    )
    run_experiment.accept_operation(request, state)
    archived_artifact = _artifact(tmp_path / "archive" / "new", b"new")
    archived = [
        {
            "name": "checkpoint-10",
            "artifact": repository.repo_relative_path(archived_artifact),
            "fingerprint": repository.artifact_fingerprint(archived_artifact),
            "timesteps": 10,
            "training_success": 0.5,
            "ep_rew_mean": 12.0,
        }
    ]
    monkeypatch.setattr(execution, "validate_active_configuration", dict)
    monkeypatch.setattr(execution, "train_candidate", lambda *args, **kwargs: 1.0)
    monkeypatch.setattr(
        execution,
        "candidate_directories",
        lambda _path: [
            {
                "name": "checkpoint-10",
                "path": archived_artifact,
                "timesteps": 10,
            }
        ],
    )
    monkeypatch.setattr(
        repository, "archive_candidates", lambda *args, **kwargs: archived
    )

    with pytest.raises(ValueError, match="candidate key collision.*T1:checkpoint-10"):
        run_experiment.execute_pending_operation()

    persisted = repository.read_state()
    assert persisted["candidates"][existing["id"]] == existing
    assert persisted["operation_events"] == []
    assert persisted["pending_operation"]["progress"] == "candidates_archived"


def test_measurement_has_independent_identity_and_returns_to_same_session(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    session = _start_session(state, "startup", "Measure the available candidate.")
    artifact = _artifact(tmp_path / "archive" / "candidate")
    candidate = _candidate("T1:checkpoint-10", artifact)
    state["candidates"][candidate["id"]] = candidate
    repository.write_state(state)
    request = {
        "measurement": {
            "description": "Measure the candidate on a development panel.",
            "rationale": "The factual result informs the next goal decision.",
            "measurements": [
                {
                    "instrument": "research_evaluation",
                    "candidate": candidate["id"],
                    "episodes": 2,
                    "seed": 100,
                }
            ],
        }
    }
    run_experiment.accept_operation(request, state)

    def evaluate(
        _artifact,
        seed,
        *,
        label,
        episodes,
        output_path,
        **_kwargs,
    ):
        metrics = {
            "episodes": episodes,
            "seed": seed,
            "success_percent": 50.0,
            "episode_results": [
                {"episode": 0, "episode_seed": seed, "success": True},
                {"episode": 1, "episode_seed": seed + 1, "success": False},
            ],
        }
        output_path.write_text(json.dumps(metrics), encoding="utf-8")
        return metrics

    monkeypatch.setattr(execution, "evaluate_artifact", evaluate)
    assert run_experiment.execute_pending_operation() == 0
    persisted = repository.read_state()
    event = persisted["operation_events"][-1]
    assert event["id"] == "M1"
    assert event["result"]["status"] == "completed"
    assert persisted["scientific_session"]["id"] == session["id"]
    assert persisted["scientific_session"]["operation_ids"] == ["M1"]
    assert persisted["pending_operation"] is None
    assert len(persisted["candidates"][candidate["id"]]["evaluation_artifacts"]) == 1


def test_research_evaluation_rejects_semantics_changes_after_acceptance(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Measure a candidate.")
    evaluator = tmp_path / "robot_learning" / "scenario" / "evaluation.py"
    evaluator.parent.mkdir(parents=True)
    evaluator.write_text("version = 1\n", encoding="utf-8")
    artifact = _artifact(tmp_path / "archive" / "candidate")
    candidate = _candidate("T1:checkpoint-10", artifact)
    state["candidates"][candidate["id"]] = candidate
    repository.write_state(state)
    request = {
        "measurement": {
            "description": "Measure the candidate.",
            "rationale": "Its factual output informs the next decision.",
            "measurements": [
                {
                    "instrument": "research_evaluation",
                    "candidate": candidate["id"],
                    "episodes": 2,
                    "seed": 100,
                }
            ],
        }
    }
    run_experiment.accept_operation(request, state)
    evaluator.write_text("version = 2\n", encoding="utf-8")
    with pytest.raises(
        run_experiment.FrozenOperationMismatch, match="semantics changed"
    ):
        run_experiment.execute_pending_operation()


@pytest.mark.parametrize("instrument", ["research_evaluation", "task_reference"])
def test_evaluation_result_indexes_the_actual_artifact_without_modifying_it(
    monkeypatch, tmp_path, instrument
):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    evidence = {
        "episodes": 2,
        "seed": 10,
        "success_percent": 50.0,
        "episode_results": [{"success": True}, {"success": False}],
        "research_evidence": {"custom_rows": [{"first": None}, {"later": 2}]},
    }
    artifact = tmp_path / "measurement.json"
    artifact.write_text(json.dumps(evidence), encoding="utf-8")
    fingerprint = repository.file_fingerprint(artifact)
    spec = {
        "instrument": instrument,
        "candidate": "T1:checkpoint-10",
        "candidate_id": "T1:checkpoint-10",
        "label": "current measurement",
        "model_fingerprint": "model-fingerprint",
    }
    result = run_experiment._measurement_result(
        spec,
        repository.measurement_record(evidence),
        artifact,
        semantics="semantics" if instrument == "research_evaluation" else None,
    )
    metrics = result["metrics"]
    assert metrics["evaluation_artifact_contents"] == (
        repository.measurement_artifact_contents(evidence)
    )
    assert metrics["evaluation_artifact_fingerprint"] == fingerprint
    assert repository.file_fingerprint(artifact) == fingerprint
    assert (
        repository.measurement_evidence(metrics)["research_evidence"]
        == (evidence["research_evidence"])
    )
    assert "research_evidence" not in metrics


def test_python_module_uses_frozen_module_manifest_not_evaluation_semantics(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Run a PI-authored diagnostic.")
    module = tmp_path / "robot_learning" / "lab" / "diagnostic.py"
    module.parent.mkdir(parents=True)
    module.write_text("version = 1\n", encoding="utf-8")
    artifact = paths.campaign_evaluation_dir("campaign") / "diagnostic.json"
    request = {
        "measurement": {
            "description": "Run the current diagnostic implementation.",
            "rationale": "Its factual output informs the next decision.",
            "measurements": [
                {
                    "instrument": "python_module",
                    "module": "robot_learning.lab.diagnostic",
                    "args": ["--output", str(artifact)],
                    "artifact": repository.repo_relative_path(artifact),
                }
            ],
        }
    }
    pending = run_experiment.accept_operation(request, state)
    assert pending["data"]["evaluation_semantics"] is None
    module.write_text("version = 2\n", encoding="utf-8")
    with pytest.raises(
        run_experiment.FrozenOperationMismatch, match="python_module source changed"
    ):
        run_experiment.execute_pending_operation()


def test_python_module_campaign_scope_error_states_expected_prefix(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Run a PI-authored diagnostic.")
    request = {
        "description": "Run the current diagnostic implementation.",
        "rationale": "Its factual output informs the next decision.",
        "measurements": [
            {
                "instrument": "python_module",
                "module": "robot_learning.lab.diagnostic",
                "args": [],
                "artifact": "campaigns/evaluations/diagnostic.json",
            }
        ],
    }

    with pytest.raises(
        ValueError,
        match=r"start with campaigns/evaluations/campaign/",
    ):
        protocol.planned_measurements(request, state)


def test_generic_measurement_executes_pi_owned_tool_and_records_artifact(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    session = _start_session(state, "startup", "Run a PI-authored diagnostic.")
    module = tmp_path / "robot_learning" / "lab" / "diagnostic.py"
    module.parent.mkdir(parents=True)
    module.write_text("def main():\n    return None\n", encoding="utf-8")
    artifact = paths.campaign_evaluation_dir("campaign") / "diagnostic.json"
    request = {
        "measurement": {
            "description": "Run the current diagnostic implementation.",
            "rationale": "Its factual output informs the next decision.",
            "measurements": [
                {
                    "instrument": "python_module",
                    "module": "robot_learning.lab.diagnostic",
                    "args": ["--output", str(artifact)],
                    "artifact": repository.repo_relative_path(artifact),
                }
            ],
        }
    }
    run_experiment.accept_operation(request, state)

    def run_module(_module, *_args):
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text('{"observation": 3}', encoding="utf-8")
        return "diagnostic complete"

    monkeypatch.setattr(execution, "run_module", run_module)
    monkeypatch.setattr(
        repository,
        "publish_campaign_laboratory",
        lambda _operation_id: {"commit": "c" * 40, "manifest": [], "fingerprint": "f"},
    )
    assert run_experiment.execute_pending_operation() == 0
    persisted = repository.read_state()
    event = persisted["operation_events"][-1]
    assert event["id"] == "M1"
    metrics = event["result"]["measurements"][0]["metrics"]
    assert "data" not in metrics
    assert repository.measurement_evidence(metrics)["observation"] == 3
    assert metrics["evaluation_artifact_contents"] == (
        repository.measurement_artifact_contents(
            json.loads(
                repository.resolve_repo_path(metrics["evaluation_artifact"]).read_text(
                    encoding="utf-8"
                )
            )
        )
    )
    assert (
        event["result"]["tool_provenance"]["campaign_lab_publication"]["commit"]
        == "c" * 40
    )
    assert persisted["scientific_session"]["id"] == session["id"]


@pytest.mark.parametrize("module_failure", [False, True])
def test_python_module_failure_preserves_invocation_facts(
    monkeypatch, tmp_path, module_failure
):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Run a diagnostic.")
    module = tmp_path / "robot_learning" / "lab" / "diagnostic.py"
    module.parent.mkdir(parents=True)
    module.write_text("def main():\n    return None\n", encoding="utf-8")
    artifact = paths.campaign_evaluation_dir("campaign") / "diagnostic.json"
    args = ["--output", str(artifact), "--label", "literal value with spaces"]
    request = {
        "measurement": {
            "description": "Run the diagnostic",
            "rationale": "Inspect a quantity",
            "measurements": [
                {
                    "instrument": "python_module",
                    "module": "robot_learning.lab.diagnostic",
                    "args": args,
                    "artifact": repository.repo_relative_path(artifact),
                }
            ],
        }
    }
    run_experiment.accept_operation(request, state)

    def run_module(name, *received):
        assert name == "robot_learning.lab.diagnostic"
        assert list(received) == args
        if module_failure:
            raise RuntimeError("preserved process error")
        return "successful exit without output"

    monkeypatch.setattr(execution, "run_module", run_module)
    monkeypatch.setattr(
        repository,
        "publish_campaign_laboratory",
        lambda _id: {
            "commit": "c" * 40,
            "manifest": [],
            "fingerprint": "f",
        },
    )
    with pytest.raises(RuntimeError) as caught:
        run_experiment.execute_pending_operation()
    error = str(caught.value)
    assert "robot_learning.lab.diagnostic" in error
    assert json.dumps(args) in error
    assert request["measurement"]["measurements"][0]["artifact"] in error
    if module_failure:
        assert "preserved process error" in error
    persisted = repository.read_state()
    assert persisted["pending_operation"]["failure"] == error
    assert persisted["pending_operation"]["request"] == request
    assert persisted["operation_events"] == []


def test_identical_raw_measurement_after_completion_allocates_next_operation(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Repeat one bounded diagnostic.")
    module = tmp_path / "robot_learning" / "lab" / "diagnostic.py"
    module.parent.mkdir(parents=True)
    module.write_text("def main():\n    return None\n", encoding="utf-8")
    artifact = paths.campaign_evaluation_dir("campaign") / "diagnostic.json"
    request = {
        "measurement": {
            "description": "Run the same diagnostic again.",
            "rationale": "Each invocation is a distinct PI request.",
            "measurements": [
                {
                    "instrument": "python_module",
                    "module": "robot_learning.lab.diagnostic",
                    "args": ["--output", str(artifact)],
                    "artifact": repository.repo_relative_path(artifact),
                }
            ],
        }
    }
    executions: list[int] = []

    def run_module(_module, *_args):
        executions.append(len(executions) + 1)
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(
            json.dumps({"observation": executions[-1]}), encoding="utf-8"
        )

    monkeypatch.setattr(execution, "run_module", run_module)
    monkeypatch.setattr(
        repository,
        "publish_campaign_laboratory",
        lambda _operation_id: {
            "commit": "c" * 40,
            "manifest": [],
            "fingerprint": "f",
        },
    )
    monkeypatch.setattr(repository, "commit_runner_memory", lambda _message: True)
    monkeypatch.setattr(sys, "argv", ["run_experiment.py"])

    paths.OPERATION_REQUEST_PATH.write_text(json.dumps(request), encoding="utf-8")
    assert run_experiment.main() == 0
    assert not paths.OPERATION_REQUEST_PATH.exists()
    first_event = repository.read_state()["operation_events"][0]
    first_metrics = first_event["result"]["measurements"][0]["metrics"]
    first_path = repository.resolve_repo_path(first_metrics["evaluation_artifact"])
    first_fingerprint = first_metrics["evaluation_artifact_fingerprint"]
    assert "M1" in first_path.name
    assert repository.measurement_evidence(first_metrics)["observation"] == 1

    paths.OPERATION_REQUEST_PATH.write_text(json.dumps(request), encoding="utf-8")
    assert run_experiment.main() == 0

    persisted = repository.read_state()
    second_metrics = persisted["operation_events"][1]["result"]["measurements"][0][
        "metrics"
    ]
    second_path = repository.resolve_repo_path(second_metrics["evaluation_artifact"])
    assert executions == [1, 2]
    assert [event["id"] for event in persisted["operation_events"]] == ["M1", "M2"]
    assert first_path != second_path
    assert first_path.is_file()
    assert second_path.is_file()
    assert "M2" in second_path.name
    assert repository.file_fingerprint(first_path) == first_fingerprint
    assert repository.measurement_evidence(first_metrics)["observation"] == 1
    assert repository.measurement_evidence(second_metrics)["observation"] == 2
    assert persisted["scientific_session"]["operation_ids"] == ["M1", "M2"]
    assert persisted["counters"]["measurement"] == 2
    assert not paths.OPERATION_REQUEST_PATH.exists()


def test_completed_python_module_recovery_rejects_mutated_archived_evidence(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Recover one completed diagnostic.")
    module = tmp_path / "robot_learning" / "lab" / "diagnostic.py"
    module.parent.mkdir(parents=True)
    module.write_text("def main():\n    return None\n", encoding="utf-8")
    artifact = paths.campaign_evaluation_dir("campaign") / "diagnostic.json"
    request = {
        "measurement": {
            "description": "Run one diagnostic.",
            "rationale": "Its durable result informs the next decision.",
            "measurements": [
                {
                    "instrument": "python_module",
                    "module": "robot_learning.lab.diagnostic",
                    "args": ["--output", str(artifact)],
                    "artifact": repository.repo_relative_path(artifact),
                }
            ],
        }
    }
    run_experiment.accept_operation(request, state)

    def run_module(_module, *_args):
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text('{"observation": 1}', encoding="utf-8")

    class SimulatedCrash(BaseException):
        pass

    def interrupt_finalization(_state, _pending):
        raise SimulatedCrash

    monkeypatch.setattr(execution, "run_module", run_module)
    monkeypatch.setattr(
        repository,
        "publish_campaign_laboratory",
        lambda _operation_id: {
            "commit": "c" * 40,
            "manifest": [],
            "fingerprint": "f",
        },
    )
    monkeypatch.setattr(repository, "commit_runner_memory", lambda _message: True)
    original_finalize = run_experiment._finalize_operation
    monkeypatch.setattr(
        run_experiment,
        "_finalize_operation",
        interrupt_finalization,
    )
    with pytest.raises(SimulatedCrash):
        run_experiment.execute_pending_operation()

    interrupted = repository.read_state()
    assert interrupted["pending_operation"]["progress"] == "completed"
    metrics = interrupted["pending_operation"]["data"]["result"]["measurements"][0][
        "metrics"
    ]
    archived = repository.resolve_repo_path(metrics["evaluation_artifact"])
    archived.write_text('{"observation": 2}', encoding="utf-8")
    monkeypatch.setattr(run_experiment, "_finalize_operation", original_finalize)

    with pytest.raises(run_experiment.FrozenOperationMismatch, match="content changed"):
        run_experiment.execute_pending_operation()


def test_python_module_publishes_changed_non_lab_science_before_execution(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    session = _start_session(state, "startup", "Run changed scientific code.")
    module = tmp_path / "robot_learning" / "scenario" / "diagnostic.py"
    module.parent.mkdir(parents=True)
    module.write_text("def main():\n    return None\n", encoding="utf-8")
    relative = "robot_learning/scenario/diagnostic.py"
    monkeypatch.setattr(repository, "scientific_delta", lambda _parent: [relative])
    artifact = paths.campaign_evaluation_dir("campaign") / "diagnostic.json"
    request = {
        "measurement": {
            "description": "Run the changed scientific diagnostic.",
            "rationale": "Its result informs the next goal decision.",
            "measurements": [
                {
                    "instrument": "python_module",
                    "module": "robot_learning.scenario.diagnostic",
                    "args": ["--output", str(artifact)],
                    "artifact": repository.repo_relative_path(artifact),
                }
            ],
        }
    }
    run_experiment.accept_operation(request, state)
    order: list[str] = []

    def publish(operation_id, scope):
        order.append(f"publish:{operation_id}")
        assert scope == [relative]
        return "c" * 40

    def run_module(_module, *_args):
        order.append("execute")
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text('{"scientific_metric": 7}', encoding="utf-8")

    monkeypatch.setattr(execution, "validate_changed_sources", lambda _paths: None)
    monkeypatch.setattr(repository, "publish_scientific_recipe", publish)
    monkeypatch.setattr(execution, "run_module", run_module)

    assert run_experiment.execute_pending_operation() == 0
    persisted = repository.read_state()
    provenance = persisted["operation_events"][-1]["result"]["tool_provenance"]
    assert order == ["publish:M1", "execute"]
    assert provenance["scientific_commit"] == "c" * 40
    assert provenance["scientific_paths"] == [relative]
    assert provenance["campaign_lab_publication"] is None
    assert persisted["scientific_session"]["scientific_parent_commit"] == "c" * 40
    assert persisted["scientific_session"]["id"] == session["id"]


def test_comparisons_are_resolved_to_planned_canonical_candidates_at_acceptance(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Compare two measured candidates.")
    first_artifact = _artifact(tmp_path / "archive" / "first", b"first")
    second_artifact = _artifact(tmp_path / "archive" / "second", b"second")
    first = _candidate("T1:checkpoint-10", first_artifact)
    second = _candidate("T2:checkpoint-10", second_artifact)
    state["candidates"] = {first["id"]: first, second["id"]: second}
    state["model_roles"]["working"] = first["id"]
    repository.write_state(state)
    request = {
        "measurement": {
            "description": "Compare two candidates.",
            "rationale": "The paired result informs the next decision.",
            "measurements": [
                {
                    "instrument": "research_evaluation",
                    "candidate": "working",
                    "episodes": 2,
                    "seed": 100,
                },
                {
                    "instrument": "research_evaluation",
                    "candidate": second["id"],
                    "episodes": 2,
                    "seed": 100,
                },
            ],
            "paired_comparisons": [{"candidate": second["id"], "reference": "working"}],
        }
    }
    pending = run_experiment.accept_operation(request, state)
    comparison = pending["data"]["paired_comparisons"][0]
    assert comparison["candidate"] == second["id"]
    assert comparison["reference"] == first["id"]
    assert comparison["candidate_model_fingerprint"] == second["fingerprint"]
    assert comparison["reference_model_fingerprint"] == first["fingerprint"]
    assert comparison["shared_episode_seeds"] == [100, 101]
    assert comparison["candidate_measurement_indexes"] == [1]
    assert comparison["reference_measurement_indexes"] == [0]
    invalid = json.loads(json.dumps(request))
    invalid["measurement"]["paired_comparisons"][0]["candidate"] = "typo"
    state = repository.read_state()
    state["pending_operation"] = None
    with pytest.raises(KeyError, match="unknown candidate"):
        run_experiment.accept_operation(invalid, state)


def test_measurement_request_refuses_a_repeated_panel(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Compare two candidates.")
    first = _candidate("T1:checkpoint-10", _artifact(tmp_path / "first", b"first"))
    second = _candidate("T2:checkpoint-10", _artifact(tmp_path / "second", b"second"))
    state["candidates"] = {first["id"]: first, second["id"]: second}
    state["model_roles"]["working"] = first["id"]
    panel = {"instrument": "research_evaluation", "episodes": 2, "seed": 100}
    request = {
        "description": "Compare two candidates.",
        "rationale": "The paired result informs the next decision.",
        "measurements": [
            {**panel, "candidate": first["id"]},
            {**panel, "candidate": second["id"]},
            {**panel, "candidate": "working"},
        ],
    }

    with pytest.raises(ValueError, match="measurement 3 repeats measurement 1"):
        protocol.planned_measurements(request, state)
    request["measurements"][2]["seed"] = 200
    assert len(protocol.planned_measurements(request, state)) == 3


def test_paired_comparison_uses_only_the_exact_frozen_shared_episodes(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Compare exact shared evidence.")
    first = _candidate("T1:checkpoint-10", _artifact(tmp_path / "first", b"first"))
    second = _candidate("T2:checkpoint-10", _artifact(tmp_path / "second", b"second"))
    state["candidates"] = {first["id"]: first, second["id"]: second}
    repository.write_state(state)
    request = {
        "measurement": {
            "description": "Compare only deterministic shared episodes.",
            "rationale": "The exact paired evidence informs the next decision.",
            "measurements": [
                {
                    "instrument": "research_evaluation",
                    "candidate": first["id"],
                    "episodes": 3,
                    "seed": 100,
                },
                {
                    "instrument": "research_evaluation",
                    "candidate": second["id"],
                    "episodes": 3,
                    "seed": 101,
                },
                {
                    "instrument": "research_evaluation",
                    "candidate": first["id"],
                    "episodes": 2,
                    "seed": 500,
                },
                {
                    "instrument": "research_evaluation",
                    "candidate": second["id"],
                    "episodes": 2,
                    "seed": 600,
                },
            ],
            "paired_comparisons": [
                {"candidate": second["id"], "reference": first["id"]}
            ],
        }
    }
    pending = run_experiment.accept_operation(request, state)
    frozen = pending["data"]["paired_comparisons"][0]
    assert frozen["shared_episode_seeds"] == [101, 102]
    assert frozen["candidate_measurement_indexes"] == [1]
    assert frozen["reference_measurement_indexes"] == [0]

    def evaluate(_artifact, seed, *, label, episodes, output_path, **_kwargs):
        del label
        metrics = {
            "episodes": episodes,
            "seed": seed,
            "success_percent": 50.0,
            "episode_results": [
                {
                    "episode": index,
                    "episode_seed": seed + index,
                    "success": (seed + index) % 2 == 0,
                }
                for index in range(episodes)
            ],
        }
        output_path.write_text(json.dumps(metrics), encoding="utf-8")
        return metrics

    monkeypatch.setattr(execution, "evaluate_artifact", evaluate)
    assert run_experiment.execute_pending_operation() == 0
    result = repository.read_state()["operation_events"][-1]["result"]
    comparison = result["paired_comparisons"][0]
    assert comparison["episodes"] == 2
    assert comparison["shared_episode_seeds"] == [101, 102]
    assert len(comparison["source_artifacts"]) == 2
    all_artifacts = [
        measurement["metrics"]["evaluation_artifact"]
        for measurement in result["measurements"]
    ]
    assert comparison["source_artifacts"] == [all_artifacts[1], all_artifacts[0]]


def test_paired_comparison_reuses_the_stored_reference_on_shared_seeds(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Compare against a stored reference.")
    first = _candidate("T1:checkpoint-10", _artifact(tmp_path / "first", b"first"))
    second = _candidate("T2:checkpoint-10", _artifact(tmp_path / "second", b"second"))
    state["candidates"] = {first["id"]: first, second["id"]: second}
    repository.write_state(state)
    evaluated = []

    def evaluate(artifact, seed, *, label, episodes, output_path, **_kwargs):
        del label
        evaluated.append(str(artifact))
        metrics = {
            "episodes": episodes,
            "seed": seed,
            "success_percent": 50.0,
            "episode_results": [
                {
                    "episode": index,
                    "episode_seed": seed + index,
                    "success": (seed + index) % 2 == 0,
                }
                for index in range(episodes)
            ],
        }
        output_path.write_text(json.dumps(metrics), encoding="utf-8")
        return metrics

    monkeypatch.setattr(execution, "evaluate_artifact", evaluate)

    def measure(candidate: str, comparisons: list[dict]) -> dict:
        request = {
            "measurement": {
                "description": "Measure on the shared panel.",
                "rationale": "The paired result informs the next decision.",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": candidate,
                        "episodes": 3,
                        "seed": 100,
                    }
                ],
                "paired_comparisons": comparisons,
            }
        }
        pending = run_experiment.accept_operation(request, repository.read_state())
        assert run_experiment.execute_pending_operation() == 0
        return pending

    measure(first["id"], [])
    stored_artifact = repository.read_state()["operation_events"][-1]["result"][
        "measurements"
    ][0]["metrics"]["evaluation_artifact"]
    pending = measure(
        second["id"], [{"candidate": second["id"], "reference": first["id"]}]
    )

    frozen = pending["data"]["paired_comparisons"][0]
    assert frozen["reference_measurement_indexes"] == []
    assert [
        item["metrics"]["evaluation_artifact"]
        for item in frozen["reference_stored_measurements"]
    ] == [stored_artifact]
    assert len(evaluated) == 2
    comparison = repository.read_state()["operation_events"][-1]["result"][
        "paired_comparisons"
    ][0]
    assert comparison["episodes"] == 3
    assert comparison["shared_episode_seeds"] == [100, 101, 102]
    assert comparison["source_artifacts"][-1] == stored_artifact


@pytest.mark.parametrize("damage", ["corrupt", "remove"])
def test_measurement_recovery_rejects_damaged_partial_artifact(
    monkeypatch, tmp_path, damage
):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Recover a partially completed measurement.")
    artifact = _artifact(tmp_path / "archive" / "candidate")
    candidate = _candidate("T1:checkpoint-10", artifact)
    state["candidates"][candidate["id"]] = candidate
    repository.write_state(state)
    request = {
        "measurement": {
            "description": "Measure two panels.",
            "rationale": "Both panels are needed for the next decision.",
            "measurements": [
                {
                    "instrument": "research_evaluation",
                    "candidate": candidate["id"],
                    "episodes": 2,
                    "seed": 100,
                },
                {
                    "instrument": "research_evaluation",
                    "candidate": candidate["id"],
                    "episodes": 2,
                    "seed": 200,
                },
            ],
        }
    }
    run_experiment.accept_operation(request, state)
    calls = {"count": 0}

    class SimulatedCrash(BaseException):
        pass

    def evaluate(
        _artifact,
        seed,
        *,
        label,
        episodes,
        output_path,
        **_kwargs,
    ):
        del label
        calls["count"] += 1
        if calls["count"] == 2:
            raise SimulatedCrash
        metrics = {
            "episodes": episodes,
            "seed": seed,
            "success_percent": 50.0,
            "episode_results": [
                {"episode": 0, "episode_seed": seed, "success": True},
                {"episode": 1, "episode_seed": seed + 1, "success": False},
            ],
        }
        output_path.write_text(json.dumps(metrics), encoding="utf-8")
        return metrics

    monkeypatch.setattr(execution, "evaluate_artifact", evaluate)
    with pytest.raises(SimulatedCrash):
        run_experiment.execute_pending_operation()
    interrupted = repository.read_state()
    partial = interrupted["pending_operation"]["data"]["partial_results"][0]
    assert "episode_results" not in partial["metrics"]
    partial_path = repository.resolve_repo_path(
        partial["metrics"]["evaluation_artifact"]
    )
    if damage == "corrupt":
        partial_path.write_text('{"corrupt": true}', encoding="utf-8")
        expected = "content changed"
    else:
        partial_path.unlink()
        expected = "is missing"
    with pytest.raises(run_experiment.FrozenOperationMismatch, match=expected):
        run_experiment.execute_pending_operation()
    assert calls["count"] == 2


def test_failed_operation_can_be_reaccepted_with_repaired_provenance(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Repair a failed training operation.")
    source = tmp_path / "robot_learning" / "training" / "reward.py"
    source.parent.mkdir(parents=True)
    source.write_text("reward = 1\n", encoding="utf-8")
    monkeypatch.setattr(
        repository,
        "scientific_delta",
        lambda _parent: ["robot_learning/training/reward.py"],
    )
    monkeypatch.setattr(run_experiment.research_config, "load_experiment_config", dict)
    request = {
        "training": {
            "initialization": "fresh",
            "seed": 7,
            "steps": 10,
            "description": "Train repaired scientific code.",
            "rationale": "The repaired run informs the next decision.",
        }
    }
    first = run_experiment.accept_operation(request, state)
    assert json.loads(paths.OPERATION_REQUEST_PATH.read_text(encoding="utf-8")) == {
        run_experiment.ACCEPTED_REQUEST_KEY: {
            "schema_version": run_experiment.ACCEPTED_REQUEST_VERSION,
            "operation_id": "T1",
        }
    }
    source.write_text("reward = 2\n", encoding="utf-8")
    with pytest.raises(run_experiment.FrozenOperationMismatch, match="changed"):
        run_experiment.execute_pending_operation()
    failed = repository.read_state()["pending_operation"]
    assert failed["failure"]
    work = {"calls": 0}

    def retry_work(_state, _pending):
        work["calls"] += 1
        return 0

    monkeypatch.setattr(run_experiment, "execute_training", retry_work)
    with pytest.raises(ValueError, match="--reaccept-pending"):
        run_experiment.execute_pending_operation()
    assert work["calls"] == 0
    result = tmp_path / "result.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_experiment.py", "--execute-pending", "--result-path", str(result)],
    )
    assert run_experiment.main() == 1
    invocation_result.write(1)
    errors = json.loads(result.read_text(encoding="utf-8"))["errors"]
    assert any("--reaccept-pending" in error for error in errors)
    assert work["calls"] == 0
    second = run_experiment.reaccept_pending_operation()
    assert second["id"] == "T2"
    assert second["supersedes"] == first["id"]
    assert json.loads(paths.OPERATION_REQUEST_PATH.read_text(encoding="utf-8")) == {
        run_experiment.ACCEPTED_REQUEST_KEY: {
            "schema_version": run_experiment.ACCEPTED_REQUEST_VERSION,
            "operation_id": "T2",
        }
    }
    assert second["data"]["scientific_manifest"][0]["fingerprint"] == (
        repository.file_fingerprint(source)
    )
    persisted = repository.read_state()
    failed_event = persisted["operation_events"][0]
    assert failed_event["id"] == first["id"]
    assert failed_event["status"] == "failed"
    assert failed_event["error"] == failed["failure"]
    assert failed_event["superseded_by"] == second["id"]

    run_experiment._complete_operation(
        persisted,
        {
            "status": "completed",
            "initialization": "fresh",
            "parent": None,
            "seed": 7,
            "requested_steps": 10,
            "completed_steps": 0,
            "scientific_commit": "a" * 40,
            "mechanical_provenance": {
                "code_parent_commit": "a" * 40,
                "changed_files": second["data"]["scientific_manifest"],
            },
            "candidates": ["T2:checkpoint-0"],
            "learning_dynamics": [
                {
                    "candidate": "T2:checkpoint-0",
                    "training_steps": 0,
                    "training_success": None,
                    "ep_rew_mean": None,
                }
            ],
        },
    )
    events = repository.read_state()["operation_events"]
    assert [event["id"] for event in events] == ["T1", "T2"]
    assert events[1]["status"] == "completed"
    assert events[1]["supersedes"] == "T1"


def test_active_nonfailed_operation_cannot_be_replaced(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Keep one active operation frozen.")
    monkeypatch.setattr(run_experiment.research_config, "load_experiment_config", dict)
    run_experiment.accept_operation(
        {
            "training": {
                "initialization": "fresh",
                "seed": 7,
                "steps": 10,
                "description": "Keep this operation active.",
                "rationale": "Its result informs the next decision.",
            }
        },
        state,
    )

    with pytest.raises(ValueError, match="different Runner operation"):
        run_experiment.accept_operation(
            _checkpoint(state),
            repository.read_state(),
        )


def test_transfer_parent_is_explicit_and_frozen(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(run_experiment, "TIMESTEPS", 20)
    _start_session(state, "startup", "Train from a selected candidate.")
    artifact = _artifact(tmp_path / "archive" / "candidate")
    candidate = _candidate("T1:checkpoint-10", artifact)
    state["candidates"][candidate["id"]] = candidate
    state["model_roles"]["working"] = candidate["id"]
    repository.write_state(state)

    request = {
        "training": {
            "initialization": "transfer",
            "parent": "working",
            "seed": 9,
            "steps": 20,
            "description": "Continue from the explicitly selected model.",
            "rationale": "The parent isolates the intended transfer.",
        }
    }
    pending = run_experiment.accept_operation(request, state)
    assert pending["data"]["parent"]["id"] == candidate["id"]
    assert pending["data"]["parent"]["fingerprint"] == candidate["fingerprint"]

    invalid = json.loads(json.dumps(request))
    del invalid["training"]["parent"]
    state["pending_operation"] = None
    with pytest.raises(ValueError, match="parent"):
        protocol.validate_operation_request(invalid, state)


def test_model_roles_change_only_through_explicit_evidence_backed_operation(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Assign a model role from evidence.")
    artifact = _artifact(tmp_path / "archive" / "candidate")
    candidate = _candidate("T1:checkpoint-10", artifact)
    state["candidates"][candidate["id"]] = candidate
    state["operation_events"].append(
        {
            "id": "M1",
            "kind": "measurement",
            "session_id": "S0",
            "inquiry_id": None,
            "request": {
                "description": "Recorded evidence.",
                "rationale": "Support an explicit role assignment.",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": candidate["id"],
                        "episodes": 1,
                        "seed": 1,
                    }
                ],
            },
            "result": {
                "status": "completed",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": candidate["id"],
                        "candidate_id": candidate["id"],
                        "label": "recorded evidence",
                        "metrics": {
                            "evaluation_artifact": (
                                "campaigns/evaluations/campaign/evidence.json"
                            ),
                            "evaluation_artifact_fingerprint": "e" * 64,
                            "model_fingerprint": candidate["fingerprint"],
                        },
                    }
                ],
                "paired_comparisons": [],
                "tool_provenance": None,
            },
            "status": "completed",
            "error": None,
            "supersedes": None,
            "superseded_by": None,
            "completed_at": "now",
        }
    )
    repository.write_state(state)
    request = {
        "model_role": {
            "action": "set_working",
            "candidate": candidate["id"],
            "reason": "The PI selects this candidate from the recorded evidence.",
            "evidence": ["M1"],
        }
    }
    run_experiment.accept_operation(request, state)
    monkeypatch.setattr(repository, "publish_artifact", lambda _publication: None)
    assert run_experiment.execute_pending_operation() == 0
    assert repository.read_state()["model_roles"]["working"] == candidate["id"]


def test_official_assessment_rejects_role_backed_only_by_failed_evidence(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    artifact = _artifact(tmp_path / "archive" / "candidate")
    candidate = _candidate("T1:checkpoint-10", artifact)
    state["candidates"][candidate["id"]] = candidate
    state["model_roles"]["best_known"] = candidate["id"]
    state["operation_events"] = [
        *_superseded_inquiry_events(),
        _model_role_event(candidate["id"], ["E1"]),
    ]
    state["scientific_session"] = None
    state["terminal_state"] = {
        "status": "official_assessment_requested",
        "reason": "Assess the selected model.",
        "model": candidate["id"],
    }
    paths.STATE_PATH.write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(
        run_experiment.assessment,
        "evaluate_official_model",
        lambda *_args, **_kwargs: pytest.fail("assessment must not run"),
    )

    with pytest.raises(ValueError, match="status == completed"):
        run_experiment.run_official_assessment()


def test_recipe_restore_removes_additions_and_restores_edits_and_deletions(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    source = tmp_path / "robot_learning" / "scenario"
    source.mkdir(parents=True)
    edited = source / "edited.py"
    deleted = source / "deleted.py"
    edited.write_text("value = 1\n", encoding="utf-8")
    deleted.write_text("present = True\n", encoding="utf-8")
    snapshot = {
        "robot_learning/scenario/edited.py": "value = 1\n",
        "robot_learning/scenario/deleted.py": "present = True\n",
    }
    edited.write_text("value = 2\n", encoding="utf-8")
    deleted.unlink()
    added = source / "added.py"
    added.write_text("extra = True\n", encoding="utf-8")

    def restore_paths(commit: str, restorable: list[str]) -> None:
        assert commit == "source"
        for relative in restorable:
            target = tmp_path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(snapshot[relative], encoding="utf-8")

    monkeypatch.setattr(repository, "restore_paths", restore_paths)
    monkeypatch.setattr(repository, "git", lambda *_args, **_kwargs: "")
    plan = {
        "parent": "source",
        "restore": list(snapshot),
        "remove_created": ["robot_learning/scenario/added.py"],
    }
    repository.apply_recipe_restore(plan)

    assert repository.recipe_paths_match_commit(plan)
    assert edited.read_text(encoding="utf-8") == "value = 1\n"
    assert deleted.read_text(encoding="utf-8") == "present = True\n"
    assert not added.exists()


def test_task_reference_uses_frozen_protected_contract(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Measure the protected task reference.")
    artifact = _artifact(tmp_path / "archive" / "candidate")
    candidate = _candidate("T1:checkpoint-10", artifact)
    state["candidates"][candidate["id"]] = candidate
    repository.write_state(state)
    contract = {"panel": "reference", "panel_version": 1, "episodes": 2, "seed": 5}
    monkeypatch.setattr(
        run_experiment, "_task_reference_contract", lambda: dict(contract)
    )
    request = {
        "measurement": {
            "description": "Measure the protected reference.",
            "rationale": "The result informs the next decision.",
            "measurements": [
                {"instrument": "task_reference", "candidate": candidate["id"]}
            ],
        }
    }
    pending = run_experiment.accept_operation(request, state)
    assert pending["data"]["evaluation_semantics"] is None
    contract["panel_version"] = 2
    with pytest.raises(
        run_experiment.FrozenOperationMismatch, match="contract changed"
    ):
        run_experiment.execute_pending_operation()


def test_measurement_reports_earlier_measurement_of_same_episodes():
    def event(identifier: str, instrument: str, metrics: dict) -> dict:
        return {
            "id": identifier,
            "kind": "measurement",
            "status": "completed",
            "result": {
                "measurements": [
                    {
                        "instrument": instrument,
                        "label": identifier,
                        "metrics": {"model_fingerprint": "model", **metrics},
                    }
                ]
            },
        }

    contract = {"panel": "reference", "panel_version": 1, "episodes": 200, "seed": 5}
    state = {
        "operation_events": [
            event("M1", "task_reference", {"panel": "reference", "panel_version": 1}),
            event(
                "M2",
                "research_evaluation",
                {"evaluation_semantics": "s", "seed": 100, "episodes": 50},
            ),
            event(
                "M3",
                "research_evaluation",
                {"evaluation_semantics": "other", "seed": 100, "episodes": 50},
            ),
        ]
    }

    def repeats(spec: dict) -> list[dict]:
        return run_experiment._earlier_measurements_of_same_episodes(
            state,
            {"model_fingerprint": "model", **spec},
            semantics="s",
            task_reference_contract=contract,
        )

    assert repeats({"instrument": "task_reference"}) == [
        {"operation_id": "M1", "label": "M1", "shared_episodes": 200}
    ]
    assert repeats(
        {"instrument": "research_evaluation", "seed": 140, "episodes": 50}
    ) == [{"operation_id": "M2", "label": "M2", "shared_episodes": 10}]
    assert (
        repeats({"instrument": "research_evaluation", "seed": 150, "episodes": 50})
        == []
    )


@pytest.mark.parametrize("instrument", ["research_evaluation", "task_reference"])
def test_repeated_measurement_preserves_repeat_metadata_through_pending_state(
    monkeypatch, tmp_path, instrument
):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Repeat a candidate measurement.")
    candidate = _candidate(
        "T1:checkpoint-10", _artifact(tmp_path / "archive" / "candidate")
    )
    state["candidates"][candidate["id"]] = candidate
    repository.write_state(state)
    contract = {"panel": "reference", "panel_version": 1, "episodes": 2, "seed": 100}
    monkeypatch.setattr(
        run_experiment, "_task_reference_contract", lambda: dict(contract)
    )
    entry = {
        "instrument": instrument,
        "candidate": candidate["id"],
        "label": "repeat-panel",
    }
    if instrument == "research_evaluation":
        entry.update(episodes=2, seed=100)
    request = {
        "measurement": {
            "description": "Repeat the same candidate on the same episodes.",
            "rationale": "Record the diagnostic replay without counting new samples.",
            "measurements": [entry],
        }
    }

    def evaluate(
        _artifact, seed, *, episodes, output_path, task_reference=False, **_kwargs
    ):
        metrics = {
            "episodes": episodes,
            "seed": seed,
            "success_percent": 50.0,
            "episode_results": [
                {"episode": 0, "episode_seed": seed, "success": True},
                {"episode": 1, "episode_seed": seed + 1, "success": False},
            ],
        }
        if task_reference:
            metrics.update(contract)
        output_path.write_text(json.dumps(metrics), encoding="utf-8")
        return metrics

    monkeypatch.setattr(execution, "evaluate_artifact", evaluate)
    run_experiment.accept_operation(request, state)
    assert run_experiment.execute_pending_operation() == 0
    state = repository.load_state(allow_missing_artifact=True)
    pending = run_experiment.accept_operation(request, state)
    expected = [{"operation_id": "M1", "label": "repeat-panel", "shared_episodes": 2}]
    field = run_experiment.REPEATS_FIELD
    assert pending["data"]["measurements"][0][field] == expected
    reloaded = repository.load_state(allow_missing_artifact=True)
    assert reloaded["pending_operation"]["data"]["measurements"][0][field] == expected

    invalid = repository.read_state()
    repeat = invalid["pending_operation"]["data"]["measurements"][0][field][0]
    repeat["shared_episodes"] = 0
    with pytest.raises(ValueError, match="shared_episodes must be at least 1"):
        repository.write_state(invalid)
    repeat["shared_episodes"] = 2
    repeat["unexpected"] = True
    with pytest.raises(ValueError, match="pending measurement repeat requires exactly"):
        repository.write_state(invalid)
    invalid["pending_operation"]["data"]["measurements"][0][field] = {}
    with pytest.raises(TypeError, match="repeats_earlier_measurements must be a list"):
        repository.write_state(invalid)

    assert run_experiment.execute_pending_operation() == 0
    completed = repository.read_state()["operation_events"][-1]
    assert completed["id"] == "M2"
    assert completed["result"]["measurements"][0]["metrics"][field] == expected


def test_supersession_graph_requires_one_reciprocal_failed_successor(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Repair one failed operation.")
    monkeypatch.setattr(run_experiment.research_config, "load_experiment_config", dict)
    request = {
        "training": {
            "initialization": "fresh",
            "seed": 7,
            "steps": 10,
            "description": "Train one candidate.",
            "rationale": "The result informs the next decision.",
        }
    }
    first = run_experiment.accept_operation(request, state)
    first["failure"] = "injected failure"
    repository.write_state(state)
    second = run_experiment.reaccept_pending_operation()
    valid = repository.read_state()
    repository.validate_research_state(valid, allow_missing_artifact=True)

    cases = []

    dangling = json.loads(json.dumps(valid))
    dangling["pending_operation"]["supersedes"] = "T404"
    cases.append((dangling, "dangling"))

    nonreciprocal = json.loads(json.dumps(valid))
    nonreciprocal["operation_events"][0]["superseded_by"] = "T3"
    cases.append((nonreciprocal, "not reciprocal"))

    cyclic = json.loads(json.dumps(valid))
    cyclic["operation_events"][0]["supersedes"] = second["id"]
    cases.append((cyclic, "cycle"))

    multiple = json.loads(json.dumps(valid))
    multiple["operation_events"].append(
        {
            "id": "T3",
            "kind": "training",
            "session_id": second["session_id"],
            "inquiry_id": second["inquiry_id"],
            "request": second["request"]["training"],
            "result": {
                "status": "completed",
                "initialization": "fresh",
                "parent": None,
                "seed": 7,
                "requested_steps": 10,
                "completed_steps": 0,
                "scientific_commit": "a" * 40,
                "mechanical_provenance": {
                    "code_parent_commit": "a" * 40,
                    "changed_files": [],
                },
                "candidates": ["T3:checkpoint-0"],
                "learning_dynamics": [
                    {
                        "candidate": "T3:checkpoint-0",
                        "training_steps": 0,
                        "training_success": None,
                        "ep_rew_mean": None,
                    }
                ],
            },
            "status": "completed",
            "error": None,
            "supersedes": first["id"],
            "superseded_by": None,
            "completed_at": "now",
        }
    )
    cases.append((multiple, "multiple supersession successors"))

    for damaged, message in cases:
        with pytest.raises(ValueError, match=message):
            repository.validate_research_state(damaged, allow_missing_artifact=True)


def test_completed_runner_results_are_strict_but_metrics_remain_extensible(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    measurement_event = {
        "id": "M1",
        "kind": "measurement",
        "session_id": "S1",
        "inquiry_id": None,
        "request": {
            "description": "Run a diagnostic.",
            "rationale": "The output informs the next decision.",
            "measurements": [
                {
                    "instrument": "python_module",
                    "module": "robot_learning.lab.diagnostic",
                    "args": [],
                    "artifact": "campaigns/evaluations/campaign/diagnostic.json",
                }
            ],
        },
        "result": {
            "status": "completed",
            "measurements": [
                {
                    "instrument": "python_module",
                    "module": "robot_learning.lab.diagnostic",
                    "args": [],
                    "label": "diagnostic",
                    "metrics": {
                        "evaluation_artifact": (
                            "campaigns/evaluations/campaign/diagnostic.json"
                        ),
                        "evaluation_artifact_fingerprint": "f" * 64,
                        "scientific_metric": {
                            "extensible": [1, 2, {"interpretation": "PI-owned"}]
                        },
                    },
                }
            ],
            "paired_comparisons": [
                {
                    "candidate": "T2:checkpoint-10",
                    "reference": "T1:checkpoint-10",
                    "episodes": 1,
                    "candidate_wins": 1,
                    "reference_wins": 0,
                    "discordant_episodes": 1,
                    "net_wins": 1,
                    "success_delta_percent": 100.0,
                    "candidate_model_fingerprint": "c" * 64,
                    "reference_model_fingerprint": "r" * 64,
                    "shared_episode_seeds": [100],
                    "source_artifacts": [
                        "campaigns/evaluations/campaign/candidate.json",
                        "campaigns/evaluations/campaign/reference.json",
                    ],
                }
            ],
            "tool_provenance": {
                "code_parent_commit": "a" * 40,
                "scientific_manifest": [],
                "scientific_paths": [],
                "scientific_commit": None,
                "effective_parameters": {},
                "module_paths": ["robot_learning/lab/diagnostic.py"],
                "module_manifest": [
                    {
                        "path": "robot_learning/lab/diagnostic.py",
                        "exists": True,
                        "fingerprint": "m" * 64,
                    }
                ],
                "campaign_lab_manifest": [
                    {
                        "path": "robot_learning/lab/diagnostic.py",
                        "fingerprint": "m" * 64,
                    }
                ],
                "campaign_lab_publication": {
                    "commit": "b" * 40,
                    "manifest": [
                        {
                            "path": "robot_learning/lab/diagnostic.py",
                            "fingerprint": "m" * 64,
                        }
                    ],
                    "fingerprint": "p" * 64,
                },
            },
        },
        "status": "completed",
        "error": None,
        "supersedes": None,
        "superseded_by": None,
        "completed_at": "now",
    }
    state["operation_events"] = [measurement_event]
    repository.validate_research_state(state, allow_missing_artifact=True)

    measurement_extra = json.loads(json.dumps(state))
    measurement_extra["operation_events"][0]["result"]["measurements"][0][
        "runner_extra"
    ] = True
    with pytest.raises(ValueError, match="completed measurement requires exactly"):
        repository.validate_research_state(
            measurement_extra, allow_missing_artifact=True
        )

    comparison_extra = json.loads(json.dumps(state))
    comparison_extra["operation_events"][0]["result"]["paired_comparisons"][0][
        "runner_extra"
    ] = True
    with pytest.raises(
        ValueError, match="completed paired comparison requires exactly"
    ):
        repository.validate_research_state(
            comparison_extra, allow_missing_artifact=True
        )

    provenance_extra = json.loads(json.dumps(state))
    provenance_extra["operation_events"][0]["result"]["tool_provenance"][
        "runner_extra"
    ] = True
    with pytest.raises(ValueError, match="completed tool provenance requires exactly"):
        repository.validate_research_state(
            provenance_extra, allow_missing_artifact=True
        )

    training_event = {
        "id": "T1",
        "kind": "training",
        "session_id": "S1",
        "inquiry_id": None,
        "request": {
            "initialization": "fresh",
            "seed": 7,
            "steps": 10,
            "description": "Train a candidate.",
            "rationale": "The result informs the next decision.",
        },
        "result": {
            "status": "completed",
            "initialization": "fresh",
            "parent": None,
            "seed": 7,
            "requested_steps": 10,
            "completed_steps": 12,
            "scientific_commit": "a" * 40,
            "mechanical_provenance": {
                "code_parent_commit": "b" * 40,
                "changed_files": [
                    {
                        "path": "robot_learning/training/reward.py",
                        "exists": True,
                        "fingerprint": "f" * 64,
                    }
                ],
            },
            "candidates": ["T1:checkpoint-12"],
            "learning_dynamics": [
                {
                    "candidate": "T1:checkpoint-12",
                    "training_steps": 12,
                    "training_success": 0.5,
                    "ep_rew_mean": -1.0,
                }
            ],
        },
        "status": "completed",
        "error": None,
        "supersedes": None,
        "superseded_by": None,
        "completed_at": "now",
    }
    state["operation_events"] = [training_event]
    repository.validate_research_state(state, allow_missing_artifact=True)

    training_provenance_extra = json.loads(json.dumps(state))
    training_provenance_extra["operation_events"][0]["result"]["mechanical_provenance"][
        "runner_extra"
    ] = True
    with pytest.raises(
        ValueError, match="completed training mechanical_provenance requires exactly"
    ):
        repository.validate_research_state(
            training_provenance_extra, allow_missing_artifact=True
        )

    invalid_candidates = json.loads(json.dumps(state))
    invalid_candidates["operation_events"][0]["result"]["candidates"] = [
        {"id": "T1:checkpoint-12"}
    ]
    with pytest.raises(ValueError, match="completed training candidates"):
        repository.validate_research_state(
            invalid_candidates, allow_missing_artifact=True
        )

    dynamics_extra = json.loads(json.dumps(state))
    dynamics_extra["operation_events"][0]["result"]["learning_dynamics"][0][
        "runner_extra"
    ] = True
    with pytest.raises(
        ValueError, match="completed training learning dynamic requires exactly"
    ):
        repository.validate_research_state(dynamics_extra, allow_missing_artifact=True)
