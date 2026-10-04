"""Behavioral contract for the strict goal-centered Runner core."""

from __future__ import annotations

import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from runner import execution, paths, protocol, repository, run_experiment


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
            "completed_operations": list(session["operation_ids"]),
            "candidates_and_roles": "Candidates are available; roles remain explicit.",
            "next_direction_or_closure": "Start a fresh bounded session.",
            "cumulative_resource_use": "One bounded session.",
        }
    }


def test_state_is_a_strict_schema6_operation_state(monkeypatch, tmp_path):
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
    assert set(state) == repository.STATE_FIELDS


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
    with pytest.raises(KeyError, match="unknown model candidate"):
        run_experiment.accept_operation(invalid, state)


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
    monkeypatch, tmp_path, capsys
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
    monkeypatch.setattr(sys, "argv", ["run_experiment.py", "--execute-pending"])
    assert run_experiment.main() == 1
    assert "--reaccept-pending" in capsys.readouterr().out
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


def test_failed_operation_can_be_replaced_by_a_different_valid_request(
    monkeypatch, tmp_path, capsys
):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Correct a failed operation.")
    monkeypatch.setattr(run_experiment.research_config, "load_experiment_config", dict)
    first = run_experiment.accept_operation(
        {
            "training": {
                "initialization": "fresh",
                "seed": 7,
                "steps": 10,
                "description": "Try the original operation.",
                "rationale": "Its result would inform the next decision.",
            }
        },
        state,
    )
    first["failure"] = "published recipe then runtime failed"
    repository.write_state(state)
    replacement = _checkpoint(state)
    paths.OPERATION_REQUEST_PATH.write_text(
        json.dumps(replacement),
        encoding="utf-8",
    )

    assert run_experiment.check_operation() == 0
    assert "OPERATION_VALID: checkpoint" in capsys.readouterr().out

    second = run_experiment.accept_operation(
        replacement,
        repository.read_state(),
    )
    persisted = repository.read_state()
    failed_event = persisted["operation_events"][0]

    assert second["kind"] == "checkpoint"
    assert second["supersedes"] == first["id"]
    assert failed_event["id"] == first["id"]
    assert failed_event["status"] == "failed"
    assert failed_event["superseded_by"] == second["id"]
    assert failed_event["request"] != second["request"]["checkpoint"]
    assert persisted["scientific_session"]["id"] == first["session_id"]


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


def test_checkpoint_and_model_role_requests_reject_noncompleted_evidence(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Use only completed evidence.")
    state["operation_events"] = _superseded_inquiry_events()
    artifact = _artifact(tmp_path / "archive" / "candidate")
    candidate = _candidate("T1:checkpoint-10", artifact)
    state["candidates"][candidate["id"]] = candidate

    checkpoint = _checkpoint(state)
    checkpoint["checkpoint"]["evidence_references"] = ["E1"]
    with pytest.raises(ValueError, match="status == completed"):
        protocol.validate_operation_request(checkpoint, state)

    evidence_file = tmp_path / "campaigns" / "evaluations" / "untracked.json"
    evidence_file.parent.mkdir(parents=True)
    evidence_file.write_text("{}", encoding="utf-8")
    checkpoint["checkpoint"]["evidence_references"] = [
        repository.repo_relative_path(evidence_file)
    ]
    with pytest.raises(ValueError, match="status == completed"):
        protocol.validate_operation_request(checkpoint, state)

    checkpoint["checkpoint"]["evidence_references"] = ["E2"]
    assert protocol.validate_operation_request(checkpoint, state) == "checkpoint"

    role = {
        "model_role": {
            "action": "set_best_known",
            "candidate": candidate["id"],
            "reason": "Assign the candidate from recorded evidence.",
            "evidence": ["E1"],
        }
    }
    with pytest.raises(ValueError, match="status == completed"):
        protocol.validate_operation_request(role, state)

    role["model_role"]["evidence"] = ["E2"]
    assert protocol.validate_operation_request(role, state) == "model_role"


def test_strict_state_rejects_noncompleted_checkpoint_and_model_role_evidence(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    state["operation_events"] = _superseded_inquiry_events()
    state["pi_checkpoint"] = {
        "session_id": "S0",
        "inquiry_id": None,
        "human_goal_connection": "The evidence bears on the human goal.",
        "current_goal_gap": "The remaining gap is unresolved.",
        "current_synthesis": "One operation failed and its retry completed.",
        "evidence_references": ["E1"],
        "decision_frontier": "Choose the next bounded operation.",
        "completed_operations": ["E2"],
        "candidates_and_roles": "No role is assigned.",
        "next_direction_or_closure": "Continue from completed evidence.",
        "cumulative_resource_use": "One completed operation.",
        "scientific_commit": "a" * 40,
    }
    with pytest.raises(ValueError, match="status == completed"):
        repository.validate_research_state(state, allow_missing_artifact=True)

    state["pi_checkpoint"]["evidence_references"] = ["E2"]
    artifact = _artifact(tmp_path / "archive" / "candidate")
    candidate = _candidate("T1:checkpoint-10", artifact)
    state["candidates"][candidate["id"]] = candidate
    state["model_roles"]["best_known"] = candidate["id"]
    state["operation_events"].append(_model_role_event(candidate["id"], ["E1"]))
    with pytest.raises(ValueError, match="status == completed"):
        repository.validate_research_state(state, allow_missing_artifact=True)


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


def test_recipe_restoration_is_mechanical_and_does_not_change_roles(
    monkeypatch, tmp_path
):
    scientific_delta = repository.scientific_delta
    state = _configure(monkeypatch, tmp_path)
    session = _start_session(state, "startup", "Restore a selected recipe.")
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
    monkeypatch.setattr(repository, "scientific_delta", scientific_delta)
    monkeypatch.setattr(
        repository,
        "committed_change_paths",
        lambda _commit: ["run_research.ps1"],
    )
    monkeypatch.setattr(repository, "status_paths", lambda _scope: [])
    run_experiment.accept_operation(request, state)
    monkeypatch.setattr(repository, "apply_recipe_restore", lambda _plan: None)
    monkeypatch.setattr(repository, "recipe_paths_match_commit", lambda _plan: True)
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
    checkpoint = run_experiment.accept_operation(_checkpoint(persisted), persisted)
    assert checkpoint["kind"] == "checkpoint"
    assert checkpoint["data"]["scientific_paths"] == []


def test_recipe_restoration_rejects_worktree_changes_after_acceptance(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Restore a selected recipe.")
    artifact = _artifact(tmp_path / "archive" / "candidate")
    candidate = _candidate("T1:checkpoint-10", artifact)
    state["candidates"][candidate["id"]] = candidate
    repository.write_state(state)
    source = tmp_path / "robot_learning" / "training" / "reward.py"
    source.parent.mkdir(parents=True)
    source.write_text("reward = 1\n", encoding="utf-8")
    changed = ["robot_learning/training/reward.py"]
    monkeypatch.setattr(repository, "require_resolvable_commit", lambda _commit: None)
    monkeypatch.setattr(repository, "scientific_delta", lambda _commit: list(changed))
    monkeypatch.setattr(repository, "tracked_at_commit", lambda _commit, _path: True)
    request = {
        "restore_recipe": {
            "candidate": candidate["id"],
            "reason": "Restore the candidate recipe exactly.",
        }
    }
    run_experiment.accept_operation(request, state)
    addition = tmp_path / "robot_learning" / "scenario" / "new_tool.py"
    addition.parent.mkdir(parents=True, exist_ok=True)
    addition.write_text("new = True\n", encoding="utf-8")
    changed.append("robot_learning/scenario/new_tool.py")
    with pytest.raises(run_experiment.FrozenOperationMismatch, match="inputs changed"):
        run_experiment.execute_pending_operation()


def test_recipe_restore_recovers_from_crash_after_restoring_progress_write(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Restore a selected recipe.")
    candidate = _candidate(
        "T1:checkpoint-10", _artifact(tmp_path / "archive" / "candidate")
    )
    state["candidates"][candidate["id"]] = candidate
    repository.write_state(state)
    request = {
        "restore_recipe": {
            "candidate": candidate["id"],
            "reason": "Restore the frozen recipe.",
        }
    }
    monkeypatch.setattr(repository, "require_resolvable_commit", lambda _commit: None)
    monkeypatch.setattr(repository, "scientific_delta", lambda _commit: [])
    run_experiment.accept_operation(request, state)
    original_write = repository.write_state
    crashed = {"value": False}

    class SimulatedCrash(BaseException):
        pass

    def crash_after_write(current):
        original_write(current)
        pending = current["pending_operation"]
        if (
            isinstance(pending, dict)
            and pending["progress"] == "restoring"
            and not crashed["value"]
        ):
            crashed["value"] = True
            raise SimulatedCrash

    monkeypatch.setattr(repository, "write_state", crash_after_write)
    monkeypatch.setattr(repository, "apply_recipe_restore", lambda _plan: None)
    monkeypatch.setattr(repository, "recipe_paths_match_commit", lambda _plan: True)
    monkeypatch.setattr(
        run_experiment.research_config,
        "load_experiment_config",
        lambda: candidate["parameters"],
    )
    with pytest.raises(SimulatedCrash):
        run_experiment.execute_pending_operation()
    assert repository.read_state()["pending_operation"]["progress"] == "restoring"
    monkeypatch.setattr(
        protocol,
        "plan_recipe_restore",
        lambda *_args: pytest.fail("accepted preconditions were revalidated"),
    )
    assert run_experiment.execute_pending_operation() == 0


def test_recipe_restore_recovers_from_crash_after_idempotent_apply(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    _start_session(state, "startup", "Restore a selected recipe.")
    candidate = _candidate(
        "T1:checkpoint-10", _artifact(tmp_path / "archive" / "candidate")
    )
    state["candidates"][candidate["id"]] = candidate
    repository.write_state(state)
    request = {
        "restore_recipe": {
            "candidate": candidate["id"],
            "reason": "Restore the frozen recipe.",
        }
    }
    monkeypatch.setattr(repository, "require_resolvable_commit", lambda _commit: None)
    monkeypatch.setattr(repository, "scientific_delta", lambda _commit: [])
    run_experiment.accept_operation(request, state)
    applies = {"count": 0}

    class SimulatedCrash(BaseException):
        pass

    def apply_then_crash(_plan):
        applies["count"] += 1
        if applies["count"] == 1:
            raise SimulatedCrash

    monkeypatch.setattr(repository, "apply_recipe_restore", apply_then_crash)
    monkeypatch.setattr(repository, "recipe_paths_match_commit", lambda _plan: True)
    monkeypatch.setattr(
        run_experiment.research_config,
        "load_experiment_config",
        lambda: candidate["parameters"],
    )
    with pytest.raises(SimulatedCrash):
        run_experiment.execute_pending_operation()
    assert repository.read_state()["pending_operation"]["progress"] == "restoring"
    monkeypatch.setattr(
        protocol,
        "plan_recipe_restore",
        lambda *_args: pytest.fail("accepted preconditions were revalidated"),
    )
    assert run_experiment.execute_pending_operation() == 0
    assert applies["count"] == 2


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


def test_mark_scientific_model_ready_commits_exact_content(monkeypatch, tmp_path):
    research = tmp_path / "campaigns"
    research.mkdir()
    for name, value in {
        "ROOT": tmp_path,
        "RESEARCH_DIR": research,
        "STATE_PATH": tmp_path / "runner" / "state" / "research_state.json",
        "RESULTS_PATH": research / "results.jsonl",
        "LOG_PATH": research / "EXPERIMENTS.md",
        "OPERATION_REQUEST_PATH": tmp_path / "pi_workspace" / "operation_request.json",
        "SCIENTIFIC_MODEL_PATH": tmp_path / "pi_workspace" / "scientific_model.md",
    }.items():
        monkeypatch.setattr(paths, name, value)
    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        last_verdict="fresh campaign",
    )
    repository.write_state(state)
    content = "exact scientific model\nwith two lines\n"
    paths.SCIENTIFIC_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    paths.SCIENTIFIC_MODEL_PATH.write_text(content, encoding="utf-8")
    committed: dict[str, str | list[str]] = {}

    def commit_paths(message: str, scope: list[str]) -> None:
        committed["message"] = message
        committed["scope"] = scope
        committed["content"] = paths.SCIENTIFIC_MODEL_PATH.read_text(encoding="utf-8")

    def require_path_at_commit(commit: str, relative: str) -> None:
        assert commit == "model-commit"
        assert relative == "pi_workspace/scientific_model.md"
        assert committed["content"] == content

    monkeypatch.setattr(repository, "commit_paths", commit_paths)
    monkeypatch.setattr(repository, "git", lambda *_args, **_kwargs: "model-commit\n")
    monkeypatch.setattr(repository, "require_path_at_commit", require_path_at_commit)
    monkeypatch.setattr(repository, "commit_runner_memory", lambda _message: True)
    monkeypatch.setattr(repository, "push_head", lambda: None)
    monkeypatch.setattr(
        sys, "argv", ["run_experiment.py", "--mark-scientific-model-ready"]
    )

    assert run_experiment.main() == 0
    persisted = repository.read_state()
    commit = persisted["scientific_model"]["commit"]
    assert committed == {
        "message": repository.campaign_commit_message("scientific model"),
        "scope": ["pi_workspace/scientific_model.md"],
        "content": content,
    }
    assert persisted["scientific_model"] == {
        "status": "ready",
        "path": "pi_workspace/scientific_model.md",
        "commit": commit,
    }
    with pytest.raises(ValueError, match="only once from pending"):
        run_experiment.main()


def test_max_inquiries_is_not_a_training_or_campaign_stopping_rule(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    state["counters"]["inquiry"] = 15
    _start_session(state, "startup", "Choose the first useful operation.")
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
    run_experiment.accept_operation(_checkpoint(state), state)
    assert run_experiment.execute_pending_operation() == 0
    state = repository.read_state()
    _start_session(state, "goal_review", "Choose the next goal-level action.")
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


def test_goal_review_checkpoint_requires_opened_inquiry(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)
    session = _start_session(state, "goal_review", "Make a goal-level decision.")
    request = _checkpoint(state)["checkpoint"]

    with pytest.raises(ValueError, match="requires an inquiry opened"):
        protocol.plan_checkpoint(request, state)

    state["active_inquiry"] = {
        "id": "I1",
        "question": "Which obstacle matters?",
        "goal_connection": "It determines the next route toward the goal.",
        "closure_condition": "Resolve the obstacle.",
        "rationale": "The answer changes the next decision.",
        "opened_in_session": session["id"],
        "reframes": [],
    }
    planned = protocol.plan_checkpoint(request, state)
    assert planned["session_id"] == session["id"]


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


def test_schema_six_rejects_unknown_nested_control_fields(monkeypatch, tmp_path):
    campaign_root = tmp_path / "campaign"
    campaign_root.mkdir()
    state = _configure(monkeypatch, campaign_root)
    state["campaign"]["unexpected"] = True
    with pytest.raises(ValueError, match="campaign requires exactly"):
        repository.validate_research_state(state, allow_missing_artifact=True)

    pending_root = tmp_path / "pending"
    pending_root.mkdir()
    state = _configure(monkeypatch, pending_root)
    _start_session(state, "goal_review", "Open a bounded inquiry.")
    pending = run_experiment.accept_operation(
        {
            "inquiry": {
                "action": "open",
                "question": "Question",
                "goal_connection": "Connection",
                "closure_condition": "Closure",
                "rationale": "Rationale",
            }
        },
        state,
    )
    pending["data"]["unexpected"] = True
    with pytest.raises(ValueError, match="pending inquiry data requires exactly"):
        repository.validate_research_state(state, allow_missing_artifact=True)
    del pending["data"]["unexpected"]
    pending["progress"] = "unexpected_progress"
    with pytest.raises(ValueError, match="unsupported progress"):
        repository.validate_research_state(state, allow_missing_artifact=True)
    pending["progress"] = "accepted"
    repository.write_state(state)
    assert run_experiment.execute_pending_operation() == 0
    completed = repository.read_state()
    completed["operation_events"][0]["result"]["unexpected"] = True
    with pytest.raises(ValueError, match="completed inquiry result requires exactly"):
        repository.validate_research_state(completed, allow_missing_artifact=True)

    assessment_root = tmp_path / "assessment"
    assessment_root.mkdir()
    state = _configure(monkeypatch, assessment_root)
    artifact = _artifact(assessment_root / "assessed")
    candidate = _candidate("T1:checkpoint-10", artifact)
    state["candidates"][candidate["id"]] = candidate
    state["terminal_state"] = {
        "status": "official_assessment_requested",
        "reason": "Assess the selected model.",
        "model": candidate["id"],
    }
    state["official_assessment"] = {
        "status": "passed",
        "model": candidate["id"],
        "artifact": candidate["artifact"],
        "fingerprint": candidate["fingerprint"],
        "summary": "The protected goal was met.",
        "completed_at": "now",
        "unexpected": True,
    }
    with pytest.raises(ValueError, match="official_assessment requires exactly"):
        repository.validate_research_state(state, allow_missing_artifact=True)
