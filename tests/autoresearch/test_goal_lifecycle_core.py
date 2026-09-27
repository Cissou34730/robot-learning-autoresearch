"""Behavioral contract for the strict goal-centered Runner core."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research import run_experiment
from research import runner_execution as execution
from research import runner_paths as paths
from research import runner_protocol as protocol
from research import runner_repository as repository


def _configure(monkeypatch, tmp_path: Path) -> dict:
    research = tmp_path / "research"
    research.mkdir()
    replacements = {
        "ROOT": tmp_path,
        "RESEARCH_DIR": research,
        "STATE_PATH": research / "research_state.json",
        "RESULTS_PATH": research / "results.jsonl",
        "LOG_PATH": research / "EXPERIMENTS.md",
        "OPERATION_REQUEST_PATH": research / "operation_request.json",
        "SCIENTIFIC_MODEL_PATH": research / "scientific_model.md",
        "TRAINING_LOG_DIR": research / "training_logs",
        "CANDIDATE_ROOT": tmp_path / "models" / "candidates",
        "EVALUATION_DIR": research / "evaluations",
    }
    for name, value in replacements.items():
        monkeypatch.setattr(paths, name, value)
    monkeypatch.setattr(repository, "git", lambda *args: "a" * 40 + "\n")
    monkeypatch.setattr(repository, "scientific_delta", lambda _parent: [])
    monkeypatch.setattr(
        repository, "publish_scientific_recipe", lambda *_args: "a" * 40
    )
    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        human_goal={
            "source": "research/scenario.md",
            "summary": "Reach the protected task success threshold.",
        },
        last_verdict="fresh campaign",
    )
    state["scientific_model"] = {
        "status": "ready",
        "path": "research/scientific_model.md",
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


def _start_session(state: dict, kind: str, objective: str) -> dict:
    session = repository.start_scientific_session(state, kind=kind, objective=objective)
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
            "completed_operations": list(session["operation_ids"]),
            "candidates_and_roles": "Candidates are available; roles remain explicit.",
            "next_direction_or_closure": "Start a fresh bounded session.",
            "cumulative_resource_use": "One bounded session.",
        }
    }


def test_state_is_a_strict_replacement_without_baseline_or_method_fields(
    monkeypatch, tmp_path
):
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
    assert state["operation_events"] == []
    assert not {
        "pending_analysis",
        "pending_method_decision",
        "active_method",
        "inquiry_session",
    } & set(state)

    state["pending_analysis"] = None
    with pytest.raises(RuntimeError, match="pending_analysis"):
        repository.validate_research_state(state, allow_missing_artifact=True)


def test_inquiry_closure_is_method_independent_and_sessions_end_at_checkpoints(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    first = _start_session(state, "goal_review", "Open the most useful inquiry.")
    open_request = {
        "inquiry": {
            "action": "open",
            "question": "Why does the policy fail near the boundary?",
            "goal_connection": "Boundary failures block the human goal.",
            "closure_condition": "Identify the route-changing cause or reject it.",
            "rationale": "Resolving this obstacle changes the next operation.",
        }
    }
    run_experiment.accept_operation(open_request, state)
    assert run_experiment.execute_pending_operation() == 0
    state = repository.read_state()
    assert state["active_inquiry"]["id"] == "I1"
    assert state["scientific_session"]["id"] == first["id"]

    run_experiment.accept_operation(_checkpoint(state), state)
    assert run_experiment.execute_pending_operation() == 0
    state = repository.read_state()
    assert state["scientific_session"] is None
    assert state["pi_checkpoint"]["session_id"] == "S1"
    assert state["pi_checkpoint"]["scientific_commit"] == "a" * 40

    _start_session(state, "inquiry", "Resolve the bounded boundary-failure question.")
    close_request = {
        "inquiry": {
            "action": "close",
            "outcome": "The evidence redirects work away from this mechanism.",
            "reason": "The closure condition is satisfied.",
        }
    }
    run_experiment.accept_operation(close_request, state)
    assert run_experiment.execute_pending_operation() == 0
    state = repository.read_state()
    assert state["active_inquiry"] is None
    assert "method" not in json.dumps(state)


def test_one_pending_transaction_freezes_the_request(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "goal_review", "Choose the first useful operation.")
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
    session = _start_session(state, "goal_review", "Establish useful model evidence.")
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


def test_measurement_has_independent_identity_and_returns_to_same_session(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    session = _start_session(state, "goal_review", "Measure the available candidate.")
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


def test_measurement_rejects_semantics_changes_after_acceptance(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "goal_review", "Run a PI-authored diagnostic.")
    evaluator = tmp_path / "robot_learning" / "scenario" / "evaluation.py"
    evaluator.parent.mkdir(parents=True)
    evaluator.write_text("version = 1\n", encoding="utf-8")
    artifact = paths.campaign_evaluation_dir("campaign") / "custom-diagnostic.json"
    request = {
        "measurement": {
            "description": "Run the current diagnostic implementation.",
            "rationale": "Its factual output informs the next decision.",
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
    evaluator.write_text("version = 2\n", encoding="utf-8")
    with pytest.raises(
        run_experiment.FrozenOperationMismatch, match="semantics changed"
    ):
        run_experiment.execute_pending_operation()


def test_generic_measurement_executes_pi_owned_tool_and_records_artifact(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    session = _start_session(state, "goal_review", "Run a PI-authored diagnostic.")
    artifact = paths.campaign_evaluation_dir("campaign") / "diagnostic.json"
    request = {
        "measurement": {
            "description": "Run the current diagnostic implementation.",
            "rationale": "Its factual output informs the next decision.",
            "measurements": [
                {
                    "instrument": "python_module",
                    "module": "research.lab.diagnostic",
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
    assert event["result"]["measurements"][0]["metrics"]["data"] == {"observation": 3}
    assert event["result"]["tool_provenance"]["commit"] == "c" * 40
    assert persisted["scientific_session"]["id"] == session["id"]


def test_transfer_parent_is_explicit_and_frozen(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "goal_review", "Train from a selected candidate.")
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
    _start_session(state, "goal_review", "Assign a model role from evidence.")
    artifact = _artifact(tmp_path / "archive" / "candidate")
    candidate = _candidate("T1:checkpoint-10", artifact)
    state["candidates"][candidate["id"]] = candidate
    state["operation_events"].append(
        {
            "id": "M1",
            "kind": "measurement",
            "session_id": "S0",
            "inquiry_id": None,
            "request": {},
            "result": {"status": "completed"},
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


def test_recipe_restoration_is_mechanical_and_does_not_change_roles(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    session = _start_session(state, "goal_review", "Restore a selected recipe.")
    artifact = _artifact(tmp_path / "archive" / "candidate")
    candidate = _candidate("T1:checkpoint-10", artifact)
    state["candidates"][candidate["id"]] = candidate
    repository.write_state(state)
    request = {
        "restore_recipe": {
            "candidate": candidate["id"],
            "reason": "Use the candidate's recorded recipe for the next operation.",
        }
    }
    monkeypatch.setattr(repository, "require_resolvable_commit", lambda _commit: None)
    monkeypatch.setattr(repository, "scientific_delta", lambda _commit: [])
    run_experiment.accept_operation(request, state)
    monkeypatch.setattr(repository, "apply_recipe_restore", lambda _plan: None)
    monkeypatch.setattr(
        run_experiment.research_config, "write_experiment_config", lambda _value: None
    )
    monkeypatch.setattr(
        run_experiment.research_config,
        "load_experiment_config",
        lambda: candidate["parameters"],
    )
    assert run_experiment.execute_pending_operation() == 0
    persisted = repository.read_state()
    assert (
        persisted["scientific_session"]["scientific_parent_commit"]
        == candidate["scientific_commit"]
    )
    assert persisted["scientific_session"]["id"] == session["id"]
    assert persisted["model_roles"]["working"] is None


def test_max_inquiries_is_not_a_training_or_campaign_stopping_rule(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    state["counters"]["inquiry"] = 15
    _start_session(state, "goal_review", "Choose the next useful operation.")
    training = {
        "training": {
            "initialization": "fresh",
            "seed": 3,
            "steps": 10,
            "description": "Train a candidate.",
            "rationale": "The result improves the next goal decision.",
        }
    }
    assert protocol.validate_operation_request(training, state) == "training"
    opening = {
        "inquiry": {
            "action": "open",
            "question": "Another question",
            "goal_connection": "It concerns the human goal.",
            "closure_condition": "Resolve it.",
            "rationale": "It could change the route.",
        }
    }
    with pytest.raises(ValueError, match="MaxInquiries"):
        protocol.validate_operation_request(opening, state)
    with pytest.raises(TypeError, match="active scientific session"):
        protocol.validate_operation_request(
            {"campaign_conclusion": {"action": "no_credible_route", "reason": "Done."}},
            {**state, "scientific_session": None},
        )
