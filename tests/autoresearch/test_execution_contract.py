"""Focused ownership, freezing, and recovery contracts."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

from runner import execution, paths, repository, run_experiment


def _configure(monkeypatch, tmp_path: Path, *, session_kind: str = "startup") -> dict:
    research = tmp_path / "campaigns"
    research.mkdir()
    for name, value in {
        "ROOT": tmp_path,
        "STATE_PATH": research / "research_state.json",
        "RESULTS_PATH": research / "results.jsonl",
        "LOG_PATH": research / "EXPERIMENTS.md",
        "OPERATION_REQUEST_PATH": research / "operation_request.json",
        "TRAINING_LOG_DIR": research / "training_logs",
        "CANDIDATE_ROOT": tmp_path / "models" / "candidates",
        "EVALUATION_DIR": research / "evaluations",
    }.items():
        monkeypatch.setattr(paths, name, value)
    monkeypatch.setattr(repository, "git", lambda *args: "a" * 40 + "\n")
    monkeypatch.setattr(repository, "scientific_delta", lambda _parent: [])
    monkeypatch.setattr(run_experiment, "TIMESTEPS", 10)
    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        last_verdict="fresh",
    )
    state["scientific_model"] = {
        "status": "ready",
        "path": "pi_workspace/scientific_model.md",
        "commit": "a" * 40,
    }
    repository.start_scientific_session(
        state,
        kind=session_kind,
        objective="Run one bounded operation.",
        backend_adapter="copilot",
        backend_model="gpt-5.6-luna",
        backend_reasoning="high",
    )
    repository.write_state(state)
    return state


def _training() -> dict:
    return {
        "training": {
            "initialization": "fresh",
            "seed": 4,
            "steps": 10,
            "description": "Train the current scientific recipe.",
            "rationale": "The learning result informs the next decision.",
        }
    }


def _write_request(request: dict) -> None:
    paths.OPERATION_REQUEST_PATH.write_text(json.dumps(request), encoding="utf-8")


def test_training_allocation_default_and_maintainer_override(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run_experiment.py"])
    assert run_experiment.parse_args().timesteps == 120_000
    monkeypatch.setattr(sys, "argv", ["run_experiment.py", "--timesteps", "60000"])
    assert run_experiment.parse_args().timesteps == 60_000


@pytest.mark.parametrize(
    ("allocation", "steps", "accepted"),
    [
        (120_000, 1, True),
        (120_000, 60_000, True),
        (120_000, 120_000, True),
        (120_000, 120_001, False),
        (60_000, 30_000, True),
        (60_000, 60_001, False),
    ],
)
def test_startup_training_requests_respect_maintainer_ceiling(
    monkeypatch, tmp_path, allocation, steps, accepted
):
    state = _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(run_experiment, "TIMESTEPS", allocation)
    request = _training()
    request["training"]["steps"] = steps
    _write_request(request)
    before = repository.read_state()

    assert run_experiment.check_operation() == (0 if accepted else 1)
    assert repository.read_state() == before
    assert state == before

    if accepted:
        assert run_experiment.accept_operation(request, state)["request"] == request
        _write_request(request)
        pending_state = repository.read_state()
        assert run_experiment.check_operation() == 0
        assert repository.read_state() == pending_state
    else:
        with pytest.raises(ValueError, match="maintainer-owned"):
            run_experiment.accept_operation(request, state)
        assert repository.read_state() == before
        assert state == before


@pytest.mark.parametrize("steps", [5, 10, 11])
def test_inquiry_training_requests_still_require_full_allocation(monkeypatch, steps):
    monkeypatch.setattr(run_experiment, "TIMESTEPS", 10)
    request = _training()["training"]
    request["steps"] = steps
    state = {"scientific_session": {"kind": "inquiry"}}

    if steps == 10:
        assert run_experiment._training_allocation(request, state) == steps
    else:
        with pytest.raises(ValueError, match="maintainer-owned"):
            run_experiment._training_allocation(request, state)


def test_changed_maintainer_allocation_refuses_pending_training_without_mutation(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(run_experiment, "TIMESTEPS", 500_000)
    request = _training()
    request["training"]["steps"] = 500_000
    run_experiment.accept_operation(request, state)
    before = repository.read_state()
    monkeypatch.setattr(run_experiment, "TIMESTEPS", 120_000)

    with pytest.raises(ValueError, match="maintainer-owned"):
        run_experiment.execute_pending_operation()
    assert repository.read_state() == before


def test_protected_files_are_rejected_from_training_delta(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(
        repository, "scientific_delta", lambda _parent: ["runner/run_experiment.py"]
    )
    with pytest.raises(ValueError, match="human-owned"):
        run_experiment.accept_operation(_training(), state)


def test_check_operation_rejects_scientific_ownership_without_state_mutation(
    monkeypatch, tmp_path, capsys
):
    _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(
        repository, "scientific_delta", lambda _parent: ["runner/run_experiment.py"]
    )
    _write_request(_training())
    before = repository.read_state()

    assert run_experiment.check_operation() == 1

    assert "human-owned" in capsys.readouterr().out
    assert repository.read_state() == before


def test_check_operation_rejects_protected_panel_overlap_without_acceptance(
    monkeypatch, tmp_path, capsys
):
    state = _configure(monkeypatch, tmp_path)
    artifact = tmp_path / "archive" / "candidate"
    artifact.mkdir(parents=True)
    (artifact / "model.zip").write_bytes(b"model")
    (artifact / "artifact.json").write_text(
        '{"timesteps": 10, "completed": true}',
        encoding="utf-8",
    )
    (artifact / "policy_runtime.pkl").write_bytes(b"runtime")
    candidate = {
        "id": "T1:checkpoint-10",
        "artifact": repository.repo_relative_path(artifact),
        "fingerprint": repository.artifact_fingerprint(artifact),
        "origin_operation": "T1",
        "name": "checkpoint-10",
        "parameters": {},
        "scientific_commit": "b" * 40,
        "training_steps": 10,
        "evaluation_artifacts": [],
    }
    state["candidates"][candidate["id"]] = candidate
    repository.write_state(state)
    monkeypatch.setattr(run_experiment, "_protected_panel_overlap", lambda *_args: True)
    _write_request(
        {
            "measurement": {
                "description": "Measure a development panel.",
                "rationale": "The result informs the next decision.",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": candidate["id"],
                        "episodes": 2,
                        "seed": 1,
                    }
                ],
            }
        }
    )
    before = repository.read_state()

    assert run_experiment.check_operation() == 1

    assert "overlap" in capsys.readouterr().out.lower()
    assert repository.read_state() == before


def test_check_operation_rejects_missing_python_module_without_acceptance(
    monkeypatch, tmp_path, capsys
):
    _configure(monkeypatch, tmp_path)
    artifact = paths.campaign_evaluation_dir("campaign") / "diagnostic.json"
    _write_request(
        {
            "measurement": {
                "description": "Run the requested diagnostic.",
                "rationale": "The result informs the next decision.",
                "measurements": [
                    {
                        "instrument": "python_module",
                        "module": "robot_learning.lab.missing_diagnostic",
                        "args": ["--output", str(artifact)],
                        "artifact": repository.repo_relative_path(artifact),
                    }
                ],
            }
        }
    )
    before = repository.read_state()

    assert run_experiment.check_operation() == 1

    assert "python_module source does not exist" in capsys.readouterr().out
    assert repository.read_state() == before


def test_check_operation_rejects_invalid_current_params_without_acceptance(
    monkeypatch, tmp_path, capsys
):
    _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(
        run_experiment.research_config,
        "load_experiment_config",
        lambda: (_ for _ in ()).throw(ValueError("current_params.json is invalid")),
    )
    _write_request(_training())
    before = repository.read_state()

    assert run_experiment.check_operation() == 1

    assert "current_params.json is invalid" in capsys.readouterr().out
    assert repository.read_state() == before


def test_frozen_training_surface_rejects_tampering(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)
    source = tmp_path / "robot_learning" / "training" / "reward.py"
    source.parent.mkdir(parents=True)
    source.write_text("reward = 1\n", encoding="utf-8")
    monkeypatch.setattr(
        repository,
        "scientific_delta",
        lambda _parent: ["robot_learning/training/reward.py"],
    )
    run_experiment.accept_operation(_training(), state)
    source.write_text("reward = 2\n", encoding="utf-8")
    pending = repository.read_state()["pending_operation"]
    with pytest.raises(run_experiment.FrozenOperationMismatch, match="changed"):
        run_experiment.execute_training(repository.read_state(), pending)


def test_published_training_recipe_is_revalidated_before_retry(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)
    source = tmp_path / "robot_learning" / "training" / "reward.py"
    source.parent.mkdir(parents=True)
    source.write_text("reward = 1\n", encoding="utf-8")
    monkeypatch.setattr(
        repository,
        "scientific_delta",
        lambda _parent: ["robot_learning/training/reward.py"],
    )
    pending = run_experiment.accept_operation(_training(), state)
    pending["data"]["scientific_commit"] = "c" * 40
    repository.write_state(state)
    source.write_text("reward = 2\n", encoding="utf-8")

    with pytest.raises(run_experiment.FrozenOperationMismatch, match="changed"):
        run_experiment.execute_training(repository.read_state(), pending)


def test_published_training_configuration_is_revalidated_before_retry(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    configuration = {"value": {"training": {"n_envs": 1}}}
    monkeypatch.setattr(
        run_experiment.research_config,
        "load_experiment_config",
        lambda: configuration["value"],
    )
    pending = run_experiment.accept_operation(_training(), state)
    pending["data"]["scientific_commit"] = "c" * 40
    repository.write_state(state)
    configuration["value"] = {"training": {"n_envs": 2}}

    with pytest.raises(
        run_experiment.FrozenOperationMismatch, match="configuration changed"
    ):
        run_experiment.execute_training(repository.read_state(), pending)


def test_parameter_only_training_delta_is_frozen_without_source_mismatch(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    params = tmp_path / "campaigns" / "current_params.json"
    params.write_text('{"training": {"n_envs": 1}}', encoding="utf-8")
    monkeypatch.setattr(
        repository,
        "scientific_delta",
        lambda _parent: ["robot_learning/training/current_params.json"],
    )
    monkeypatch.setattr(
        run_experiment.research_config,
        "load_experiment_config",
        lambda: {"training": {"n_envs": 1}},
    )

    pending = run_experiment.accept_operation(_training(), state)

    assert pending["data"]["scientific_manifest"] == []
    assert pending["data"]["scientific_paths"] == [
        "robot_learning/training/current_params.json"
    ]
    protocol_paths = run_experiment.protocol.validation_test_paths(
        pending["data"]["scientific_paths"]
    )
    assert protocol_paths == ()


def test_transfer_parent_is_revalidated_at_execution(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)
    artifact = tmp_path / "archive"
    artifact.mkdir()
    (artifact / "model.zip").write_bytes(b"model")
    (artifact / "artifact.json").write_text("{}", encoding="utf-8")
    (artifact / "policy_runtime.pkl").write_bytes(b"runtime")
    candidate = {
        "id": "T1:checkpoint-10",
        "artifact": repository.repo_relative_path(artifact),
        "fingerprint": repository.artifact_fingerprint(artifact),
        "origin_operation": "T1",
        "name": "checkpoint-10",
        "parameters": {},
        "scientific_commit": "b" * 40,
        "training_steps": 10,
        "evaluation_artifacts": [],
    }
    state["candidates"][candidate["id"]] = candidate
    request = _training()
    request["training"].update(initialization="transfer", parent=candidate["id"])
    pending = run_experiment.accept_operation(request, state)
    pending["data"]["scientific_commit"] = "c" * 40
    repository.write_state(state)
    (artifact / "model.zip").write_bytes(b"replacement")
    monkeypatch.setattr(repository, "require_resolvable_commit", lambda _commit: None)

    with pytest.raises(
        run_experiment.FrozenOperationMismatch, match="parent fingerprint"
    ):
        run_experiment.execute_training(repository.read_state(), pending)


@pytest.mark.parametrize(
    "failure_point",
    [
        "result_record",
        "completion_commit",
        "finalization_commit",
        "resumed_finalization",
    ],
)
@pytest.mark.parametrize("requested_steps", [5, 10])
def test_completed_training_transaction_retries_publication_without_retraining(
    monkeypatch, tmp_path, failure_point, requested_steps, capsys
):
    state = _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(run_experiment.research_config, "load_experiment_config", dict)
    request = _training()
    request["training"]["steps"] = requested_steps
    run_experiment.accept_operation(request, state)
    artifact = tmp_path / "archive"
    artifact.mkdir()
    (artifact / "model.zip").write_bytes(b"model")
    (artifact / "artifact.json").write_text(
        json.dumps({"timesteps": 10, "completed": True}), encoding="utf-8"
    )
    (artifact / "policy_runtime.pkl").write_bytes(b"runtime")
    archived = [
        {
            "name": "checkpoint-10",
            "artifact": repository.repo_relative_path(artifact),
            "fingerprint": repository.artifact_fingerprint(artifact),
            "timesteps": 10,
            "training_success": 0.5,
            "ep_rew_mean": 1.0,
        }
    ]
    calls = {"training": 0, "history": 0, "commit_failures": 0}
    monkeypatch.setattr(
        repository, "publish_scientific_recipe", lambda *_args: "b" * 40
    )
    monkeypatch.setattr(execution, "validate_active_configuration", dict)

    def train(*_args, **_kwargs):
        assert _args[1] == requested_steps
        calls["training"] += 1
        return 1.0

    monkeypatch.setattr(execution, "train_candidate", train)
    monkeypatch.setattr(
        execution,
        "candidate_directories",
        lambda _path: [{"name": "checkpoint-10", "path": artifact, "timesteps": 10}],
    )
    monkeypatch.setattr(
        repository, "archive_candidates", lambda *args, **kwargs: archived
    )
    monkeypatch.setattr(execution, "remove_candidate_dir", lambda _path: None)
    original = repository.upsert_operation_event

    def fail_once(event):
        calls["history"] += 1
        if failure_point == "result_record" and calls["history"] == 1:
            raise OSError("injected publication failure")
        original(event)

    def commit(message):
        failed_messages = {
            "completion_commit": {"complete T1 training"},
            "finalization_commit": {"finalize T1"},
            "resumed_finalization": {"complete T1 training", "finalize T1"},
        }.get(failure_point, set())
        failures = 2 if failure_point == "resumed_finalization" else 1
        if message in failed_messages and calls["commit_failures"] < failures:
            calls["commit_failures"] += 1
            raise OSError("injected publication failure")
        return True

    monkeypatch.setattr(repository, "upsert_operation_event", fail_once)
    monkeypatch.setattr(repository, "commit_runner_memory", commit)
    with pytest.raises(OSError, match="publication failure"):
        run_experiment.execute_pending_operation()
    interrupted = repository.read_state()
    assert interrupted["pending_operation"]["progress"] == (
        "result_ready" if failure_point == "result_record" else "completed"
    )
    assert interrupted["pending_operation"]["failure"] is None
    assert interrupted["pending_operation"]["request"] == request
    assert interrupted["pending_operation"]["data"]["archived_candidates"] == archived
    assert "PUBLICATION FAILED" in capsys.readouterr().out

    if failure_point == "resumed_finalization":
        with pytest.raises(OSError, match="publication failure"):
            run_experiment.execute_pending_operation()
        assert repository.read_state() == interrupted
        assert "PUBLICATION FAILED" in capsys.readouterr().out

    assert run_experiment.execute_pending_operation() == 0
    assert calls["training"] == 1
    completed = repository.read_state()
    assert completed["pending_operation"] is None
    assert completed["counters"] == interrupted["counters"]
    assert [event["id"] for event in completed["operation_events"]] == ["T1"]
    assert [event["id"] for event in repository.history_records()] == ["T1"]
    assert repository.history_records()[0]["request"] == request["training"]
    assert (
        completed["operation_events"][0]["result"]["requested_steps"] == requested_steps
    )
    assert completed["operation_events"][0]["result"]["completed_steps"] == 10


def test_completed_result_retries_memory_publication_without_reacceptance(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path, session_kind="goal_review")
    request = {
        "inquiry": {
            "action": "open",
            "question": "Question",
            "goal_connection": "Connection",
            "closure_condition": "Closure",
            "rationale": "Rationale",
        }
    }
    paths.OPERATION_REQUEST_PATH.write_text(json.dumps(request), encoding="utf-8")
    run_experiment.accept_operation(request, state)
    calls: list[str] = []

    def fail_complete_once(message):
        calls.append(message)
        if message == "complete E1 inquiry" and calls.count(message) == 1:
            persisted = repository.read_state()
            assert persisted["pending_operation"]["progress"] == "completed"
            assert [event["id"] for event in persisted["operation_events"]] == ["E1"]
            assert [event["id"] for event in repository.history_records()] == ["E1"]
            raise OSError("injected memory commit failure")
        return True

    monkeypatch.setattr(repository, "commit_runner_memory", fail_complete_once)
    with pytest.raises(OSError, match="memory commit failure"):
        run_experiment.execute_pending_operation()
    interrupted = repository.read_state()
    assert interrupted["pending_operation"]["progress"] == "completed"
    assert interrupted["pending_operation"]["failure"] is None

    assert run_experiment.execute_pending_operation() == 0
    completed = repository.read_state()
    assert completed["pending_operation"] is None
    assert [event["id"] for event in completed["operation_events"]] == ["E1"]
    assert [event["id"] for event in repository.history_records()] == ["E1"]
    assert not paths.OPERATION_REQUEST_PATH.exists()
    assert calls == ["complete E1 inquiry", "finalize E1"]


def test_finalization_commit_crash_restarts_without_reexecuting_or_duplicate_event(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path, session_kind="goal_review")
    request = {
        "inquiry": {
            "action": "open",
            "question": "Question",
            "goal_connection": "Connection",
            "closure_condition": "Closure",
            "rationale": "Rationale",
        }
    }
    paths.OPERATION_REQUEST_PATH.write_text(json.dumps(request), encoding="utf-8")
    committed: dict[str, dict] = {}
    calls: list[str] = []
    executions = {"count": 0}

    class SimulatedCrash(BaseException):
        pass

    original_execute = run_experiment._execute_inquiry

    def execute(current, pending):
        executions["count"] += 1
        return original_execute(current, pending)

    def commit(message):
        calls.append(message)
        if message == "complete E1 inquiry":
            committed["HEAD"] = copy.deepcopy(repository.read_state())
            return True
        if calls.count("finalize E1") == 1:
            raise SimulatedCrash
        committed["HEAD"] = copy.deepcopy(repository.read_state())
        return True

    monkeypatch.setattr(run_experiment, "_execute_inquiry", execute)
    monkeypatch.setattr(repository, "commit_runner_memory", commit)
    monkeypatch.setattr(
        repository,
        "read_committed_state",
        lambda revision: copy.deepcopy(committed[revision]),
    )
    run_experiment.accept_operation(request, state)
    with pytest.raises(SimulatedCrash):
        run_experiment.execute_pending_operation()

    interrupted = repository.read_state()
    assert interrupted["pending_operation"] is None
    assert paths.OPERATION_REQUEST_PATH.is_file()
    assert json.loads(paths.OPERATION_REQUEST_PATH.read_text(encoding="utf-8")) == {
        run_experiment.ACCEPTED_REQUEST_KEY: {
            "schema_version": run_experiment.ACCEPTED_REQUEST_VERSION,
            "operation_id": "E1",
        }
    }
    assert executions["count"] == 1

    monkeypatch.setattr(sys, "argv", ["run_experiment.py"])
    assert run_experiment.main() == 0
    completed = repository.read_state()
    assert completed["pending_operation"] is None
    assert not paths.OPERATION_REQUEST_PATH.exists()
    assert executions["count"] == 1
    assert [event["id"] for event in completed["operation_events"]] == ["E1"]
    assert [event["id"] for event in repository.history_records()] == ["E1"]
    assert calls == ["complete E1 inquiry", "finalize E1", "finalize E1"]


def test_finalization_push_crash_retries_only_publication_without_duplicate_event(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path, session_kind="goal_review")
    request = {
        "inquiry": {
            "action": "open",
            "question": "Question",
            "goal_connection": "Connection",
            "closure_condition": "Closure",
            "rationale": "Rationale",
        }
    }
    paths.OPERATION_REQUEST_PATH.write_text(json.dumps(request), encoding="utf-8")
    committed: dict[str, dict] = {}
    calls: list[str] = []
    executions = {"count": 0}
    pushes = {"count": 0}

    class SimulatedCrash(BaseException):
        pass

    original_execute = run_experiment._execute_inquiry

    def execute(current, pending):
        executions["count"] += 1
        return original_execute(current, pending)

    def commit(message):
        calls.append(message)
        if message == "complete E1 inquiry":
            committed["HEAD"] = copy.deepcopy(repository.read_state())
            return True
        committed["HEAD^"] = committed["HEAD"]
        committed["HEAD"] = copy.deepcopy(repository.read_state())
        raise SimulatedCrash

    def git(*args):
        if args == ("log", "-1", "--format=%s", "HEAD"):
            return "camp: finalize E1\n"
        return "a" * 40 + "\n"

    monkeypatch.setattr(run_experiment, "_execute_inquiry", execute)
    monkeypatch.setattr(repository, "commit_runner_memory", commit)
    monkeypatch.setattr(repository, "git", git)
    monkeypatch.setattr(
        repository,
        "read_committed_state",
        lambda revision: copy.deepcopy(committed[revision]),
    )
    monkeypatch.setattr(
        repository,
        "push_head",
        lambda: pushes.__setitem__("count", pushes["count"] + 1),
    )
    run_experiment.accept_operation(request, state)
    with pytest.raises(SimulatedCrash):
        run_experiment.execute_pending_operation()

    interrupted = repository.read_state()
    assert interrupted["pending_operation"] is None
    assert paths.OPERATION_REQUEST_PATH.is_file()
    assert json.loads(paths.OPERATION_REQUEST_PATH.read_text(encoding="utf-8")) == {
        run_experiment.ACCEPTED_REQUEST_KEY: {
            "schema_version": run_experiment.ACCEPTED_REQUEST_VERSION,
            "operation_id": "E1",
        }
    }
    assert executions["count"] == 1

    monkeypatch.setattr(sys, "argv", ["run_experiment.py"])
    assert run_experiment.main() == 0
    completed = repository.read_state()
    assert completed["pending_operation"] is None
    assert not paths.OPERATION_REQUEST_PATH.exists()
    assert executions["count"] == 1
    assert [event["id"] for event in completed["operation_events"]] == ["E1"]
    assert [event["id"] for event in repository.history_records()] == ["E1"]
    assert calls == ["complete E1 inquiry", "finalize E1"]
    assert pushes["count"] == 1


def test_completion_publishes_memory_and_consumes_the_request(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path, session_kind="goal_review")
    request = {
        "inquiry": {
            "action": "open",
            "question": "Question",
            "goal_connection": "Connection",
            "closure_condition": "Closure",
            "rationale": "Rationale",
        }
    }
    paths.OPERATION_REQUEST_PATH.write_text(json.dumps(request), encoding="utf-8")
    calls: list[str] = []
    monkeypatch.setattr(
        repository,
        "commit_runner_memory",
        lambda message: calls.append(message) or True,
    )
    run_experiment.accept_operation(request, state)
    assert run_experiment.execute_pending_operation() == 0
    persisted = repository.read_state()
    assert persisted["pending_operation"] is None
    assert [event["id"] for event in persisted["operation_events"]] == ["E1"]
    assert not paths.OPERATION_REQUEST_PATH.exists()
    assert calls == ["complete E1 inquiry", "finalize E1"]


def test_candidate_manifest_preserves_identity_order_and_artifacts(tmp_path):
    names = ["checkpoint-400", "checkpoint-100", "checkpoint-300"]
    source = tmp_path / "source"
    source.mkdir()
    for name in names:
        candidate = source / "checkpoints" / name
        candidate.mkdir(parents=True)
        (candidate / "model.zip").write_bytes(name.encode())
        (candidate / "artifact.json").write_text(
            json.dumps({"timesteps": int(name.split("-")[1])}), encoding="utf-8"
        )
        (candidate / "policy_runtime.pkl").write_bytes(b"runtime")
    (source / "candidate_manifest.json").write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "name": name,
                        "timesteps": int(name.split("-")[1]),
                        "path": f"checkpoints/{name}",
                    }
                    for name in names
                ]
            }
        ),
        encoding="utf-8",
    )
    for filename in repository.INFERENCE_ARTIFACT_FILES:
        (source / filename).write_bytes(
            (source / "checkpoints" / names[-1] / filename).read_bytes()
        )

    execution.copy_candidate_outputs(source, tmp_path / "copied")
    assert [
        item["name"] for item in execution.candidate_directories(tmp_path / "copied")
    ] == names
