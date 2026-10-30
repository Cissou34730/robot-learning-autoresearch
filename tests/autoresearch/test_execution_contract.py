"""Focused ownership, freezing, and recovery contracts."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

from runner import (
    execution,
    invocation_result,
    paths,
    protocol,
    repository,
    run_experiment,
)


def _checked(tmp_path: Path) -> tuple[int, str]:
    """Run the operation check and return its exit code and launcher message."""
    result = tmp_path / "check-result.json"
    invocation_result.configure(result)
    code = run_experiment.check_operation()
    invocation_result.write(code)
    validation = json.loads(result.read_text(encoding="utf-8"))["validation"]
    return code, validation["message"]


def _result_errors(tmp_path: Path) -> str:
    result = tmp_path / "execution-result.json"
    invocation_result.write(1)
    errors = json.loads(result.read_text(encoding="utf-8"))["errors"]
    invocation_result.configure(result)
    return "\n".join(errors)


def test_each_campaign_validates_in_its_own_pytest_folder(monkeypatch, tmp_path):
    folders = set()
    for name in ("campaign-1", "campaign-2"):
        monkeypatch.setattr(paths, "ROOT", tmp_path / name)
        folders.add(execution.validation_temp_directory())
    assert len(folders) == 2
    assert not any(paths.HARNESS_ROOT in folder.parents for folder in folders)


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
    state["campaign_phase"] = (
        session_kind
        if session_kind in {"recipe_development", "startup"}
        else "research"
    )
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


@pytest.mark.parametrize(
    ("initialization", "root", "variants", "valid"),
    [
        ("transfer", {"parent": "working"}, [{"label": "a"}, {"label": "b"}], True),
        (
            "transfer",
            {"parent": "working"},
            [{"label": "a", "parent": "best_known"}, {"label": "b"}],
            True,
        ),
        (
            "transfer",
            {},
            [
                {"label": "a", "parent": "working"},
                {"label": "b", "parent": "best_known"},
            ],
            True,
        ),
        ("transfer", {}, [{"label": "a", "parent": "working"}, {"label": "b"}], False),
        (
            "transfer",
            {"parent": None},
            [{"label": "a", "parent": "working"}, {"label": "b", "parent": "working"}],
            False,
        ),
        (
            "transfer",
            {"parent": "working"},
            [{"label": "a", "parent": None}, {"label": "b"}],
            False,
        ),
        (
            "transfer",
            {"parent": "working"},
            [{"label": "a", "parent": ""}, {"label": "b"}],
            False,
        ),
        ("fresh", {"parent": None}, [{"label": "a"}, {"label": "b"}], False),
        ("fresh", {}, [{"label": "a", "parent": None}, {"label": "b"}], False),
        ("fresh", {}, [{"label": "a", "parent": ""}, {"label": "b"}], False),
        ("fresh", {}, [{"label": "a", "parent": "working"}, {"label": "b"}], False),
    ],
)
def test_training_variant_parent_request_rules(initialization, root, variants, valid):
    request = {
        **_training()["training"],
        "initialization": initialization,
        **root,
        "variants": variants,
    }
    for validate in (
        protocol.validate_training_request,
        lambda value: protocol.validate_operation_shape("training", value),
    ):
        if valid:
            validate(request)
        else:
            with pytest.raises((ValueError, TypeError)):
                validate(request)


def test_training_range_default_and_maintainer_override(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run_experiment.py"])
    arguments = run_experiment.parse_args()
    assert (arguments.timesteps, arguments.max_timesteps) == (10_000, 500_000)
    monkeypatch.setattr(sys, "argv", ["run_experiment.py", "--timesteps", "60000"])
    assert run_experiment.parse_args().timesteps == 60_000


@pytest.mark.parametrize(
    ("steps", "accepted"), [(5, False), (10, True), (30, True), (31, False)]
)
def test_startup_training_requests_stay_within_the_range(
    monkeypatch, tmp_path, steps, accepted
):
    state = _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(run_experiment, "MAX_TIMESTEPS", 30)
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
        with pytest.raises(ValueError, match="needs between 10 and 30 steps"):
            run_experiment.accept_operation(request, state)
        assert repository.read_state() == before
        assert state == before


@pytest.mark.parametrize(
    ("steps", "accepted"), [(5, False), (10, True), (30, True), (31, False)]
)
def test_inquiry_training_requests_stay_within_the_range(monkeypatch, steps, accepted):
    monkeypatch.setattr(run_experiment, "TIMESTEPS", 10)
    monkeypatch.setattr(run_experiment, "MAX_TIMESTEPS", 30)
    request = _training()["training"]
    request["steps"] = steps
    state = {"scientific_session": {"kind": "inquiry"}}

    if accepted:
        assert run_experiment._training_allocation(request, state) == steps
    else:
        with pytest.raises(ValueError, match="needs between") as error:
            run_experiment._training_allocation(request, state)
        assert "maintainer" not in str(error.value)


def test_changed_maintainer_range_refuses_pending_training_without_mutation(
    monkeypatch, tmp_path
):
    state = _configure(monkeypatch, tmp_path)
    request = _training()
    request["training"]["steps"] = 500_000
    run_experiment.accept_operation(request, state)
    before = repository.read_state()
    monkeypatch.setattr(run_experiment, "MAX_TIMESTEPS", 120_000)

    with pytest.raises(ValueError, match="needs between"):
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
    monkeypatch, tmp_path
):
    _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(
        repository, "scientific_delta", lambda _parent: ["runner/run_experiment.py"]
    )
    _write_request(_training())
    before = repository.read_state()

    code, message = _checked(tmp_path)
    assert code == 1
    assert message.startswith("OPERATION_INVALID: ")
    assert "human-owned" in message
    assert repository.read_state() == before


def test_check_operation_rejects_protected_panel_overlap_without_acceptance(
    monkeypatch, tmp_path
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

    code, message = _checked(tmp_path)
    assert code == 1
    assert "overlap" in message.lower()
    assert repository.read_state() == before


def test_check_operation_rejects_missing_python_module_without_acceptance(
    monkeypatch, tmp_path
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

    code, message = _checked(tmp_path)
    assert code == 1
    assert "python_module source does not exist" in message
    assert repository.read_state() == before


def test_check_operation_rejects_invalid_current_params_without_acceptance(
    monkeypatch, tmp_path
):
    _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(
        run_experiment.research_config,
        "load_experiment_config",
        lambda: (_ for _ in ()).throw(ValueError("current_params.json is invalid")),
    )
    _write_request(_training())
    before = repository.read_state()

    code, message = _checked(tmp_path)
    assert code == 1
    assert "current_params.json is invalid" in message
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


def _add_training_parent(state, tmp_path, name):
    artifact = tmp_path / name
    artifact.mkdir()
    (artifact / "model.zip").write_bytes(name.encode())
    (artifact / "artifact.json").write_text("{}", encoding="utf-8")
    (artifact / "policy_runtime.pkl").write_bytes(b"runtime")
    candidate = {
        "id": f"T0:{name}",
        "artifact": repository.repo_relative_path(artifact),
        "fingerprint": repository.artifact_fingerprint(artifact),
        "origin_operation": "T0",
        "name": name,
        "parameters": {"ppo": {"gamma": 0.5}},
        "scientific_commit": "b" * 40,
        "training_steps": 100,
        "evaluation_artifacts": [],
    }
    state["candidates"][candidate["id"]] = candidate
    return candidate


@pytest.mark.parametrize("missing_at", ["root", "variant"])
@pytest.mark.parametrize("replacement", [False, True])
def test_unknown_training_parent_refuses_acceptance_without_mutation(
    monkeypatch, tmp_path, missing_at, replacement
):
    state = _configure(monkeypatch, tmp_path)
    parent = _add_training_parent(state, tmp_path, "parent")
    if replacement:
        pending = run_experiment.accept_operation(_training(), state)
        pending["failure"] = "training failed"
    repository.write_state(state)
    request = _training()
    request["training"].update(
        initialization="transfer",
        parent="unknown" if missing_at == "root" else parent["id"],
        variants=[{"label": "a"}, {"label": "b", "parent": "unknown"}],
    )
    before = copy.deepcopy(state)
    with pytest.raises(KeyError, match="unknown candidate"):
        run_experiment.accept_operation(request, state)
    assert state == before
    assert repository.read_state() == before


@pytest.mark.parametrize(
    "corruption", ["missing", "extra", "null", "identity", "parameters"]
)
def test_pending_variant_parent_mapping_rejects_corruption(
    monkeypatch, tmp_path, corruption
):
    state = _configure(monkeypatch, tmp_path)
    parent = _add_training_parent(state, tmp_path, "parent")
    request = _training()
    request["training"].update(
        initialization="transfer",
        parent=parent["id"],
        variants=[{"label": "a"}, {"label": "b"}],
    )
    pending = run_experiment.accept_operation(request, state)
    parents = pending["data"]["variant_parents"]
    if corruption == "missing":
        del parents["b"]
    elif corruption == "extra":
        parents["c"] = copy.deepcopy(parents["a"])
    elif corruption == "null":
        parents["b"] = None
    elif corruption == "identity":
        parents["b"]["id"] = "T0:unknown"
    else:
        parents["b"]["parameters"] = {"changed": True}
    with pytest.raises(ValueError, match="parent"):
        repository.validate_research_state(state, allow_missing_artifact=True)


def test_variant_parent_is_revalidated_before_any_training(monkeypatch, tmp_path):
    state = _configure(monkeypatch, tmp_path)
    parent = _add_training_parent(state, tmp_path, "parent")
    request = _training()
    request["training"].update(
        initialization="transfer",
        variants=[{"label": label, "parent": parent["id"]} for label in ("a", "b")],
    )
    pending = run_experiment.accept_operation(request, state)
    pending["data"]["scientific_commit"] = "c" * 40
    (tmp_path / "parent" / "model.zip").write_bytes(b"changed")
    monkeypatch.setattr(execution, "train_variants", lambda *a: pytest.fail("trained"))
    with pytest.raises(
        run_experiment.FrozenOperationMismatch, match="parent fingerprint"
    ):
        run_experiment.execute_training(state, pending)


@pytest.mark.parametrize(
    "failure_point",
    [
        "result_record",
        "completion_commit",
        "finalization_commit",
        "resumed_finalization",
    ],
)
@pytest.mark.parametrize("requested_steps", [10, 20])
def test_completed_training_transaction_retries_publication_without_retraining(
    monkeypatch, tmp_path, failure_point, requested_steps
):
    state = _configure(monkeypatch, tmp_path)
    invocation_result.configure(tmp_path / "execution-result.json")
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
    assert "PUBLICATION FAILED" in _result_errors(tmp_path)

    if failure_point == "resumed_finalization":
        with pytest.raises(OSError, match="publication failure"):
            run_experiment.execute_pending_operation()
        assert repository.read_state() == interrupted
        assert "PUBLICATION FAILED" in _result_errors(tmp_path)

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


@pytest.mark.parametrize(
    ("parent_mode", "publication"),
    [
        ("fresh", "normal"),
        ("inherited", "normal"),
        ("overridden", "normal"),
        ("per_variant", "normal"),
        ("legacy", "normal"),
        ("per_variant", "wrong_resume"),
        ("per_variant", "result_ready"),
        ("legacy", "legacy_result_ready"),
    ],
)
def test_training_variants_train_together_and_record_candidates_per_variant(
    monkeypatch, tmp_path, parent_mode, publication
):
    state = _configure(monkeypatch, tmp_path)
    invocation_result.configure(tmp_path / "execution-result.json")
    active = {"ppo": {"gamma": 0.99, "n_steps": 64}, "training": {"n_envs": 1}}
    monkeypatch.setattr(
        execution,
        "effective_config",
        lambda *_args: pytest.fail("used shared trainer configuration for a variant"),
    )
    monkeypatch.setattr(
        run_experiment.research_config, "load_experiment_config", lambda: active
    )
    request = _training()
    request["training"]["variants"] = [
        {"label": "base"},
        {"label": "short", "parameters": {"ppo": {"gamma": 0.9}}},
    ]
    first = _add_training_parent(state, tmp_path, "first")
    second = _add_training_parent(state, tmp_path, "second")
    state["model_roles"]["working"] = first["id"]
    state["model_roles"]["best_known"] = second["id"]
    if parent_mode != "fresh":
        request["training"].update(initialization="transfer", parent="working")
    if parent_mode in {"overridden", "per_variant"}:
        request["training"]["variants"][1]["parent"] = "best_known"
    if parent_mode == "per_variant":
        del request["training"]["parent"]
        request["training"]["variants"][0]["parent"] = "working"
    expected_parents = {
        "base": None if parent_mode == "fresh" else first,
        "short": (
            None
            if parent_mode == "fresh"
            else second
            if parent_mode in {"overridden", "per_variant"}
            else first
        ),
    }
    package = tmp_path / "robot_learning"
    (package / "variants" / "short").mkdir(parents=True)
    (package / "train.py").write_text("base\n", encoding="utf-8")
    (package / "variants" / "short" / "train.py").write_text(
        "short\n", encoding="utf-8"
    )
    pending = run_experiment.accept_operation(request, state)
    assert pending["data"]["parent"] == (
        None
        if parent_mode in {"fresh", "per_variant"}
        else {key: first[key] for key in pending["data"]["parent"]}
    )
    for label, parent in expected_parents.items():
        frozen = pending["data"]["variant_parents"][label]
        assert frozen == (
            None if parent is None else {key: parent[key] for key in frozen}
        )
    if parent_mode == "legacy":
        del pending["data"]["variant_parents"]
    state["model_roles"]["working"] = second["id"]
    state["model_roles"]["best_known"] = first["id"]
    repository.write_state(state)
    monkeypatch.setattr(
        protocol, "resolve_candidate", lambda *a: pytest.fail("re-resolved parent")
    )
    artifact = tmp_path / "archive"
    artifact.mkdir()
    (artifact / "model.zip").write_bytes(b"model")
    (artifact / "artifact.json").write_text("{}", encoding="utf-8")
    (artifact / "policy_runtime.pkl").write_bytes(b"runtime")
    monkeypatch.setattr(
        repository, "publish_scientific_recipe", lambda *_args: "b" * 40
    )
    monkeypatch.setattr(execution, "validate_active_configuration", dict)
    trained = []

    def train_variants(specs, timesteps, seed, resume, operation_id):
        for spec in specs:
            parent = expected_parents[spec["label"]]
            expected_resume = (
                None if parent is None else tmp_path / parent["name"] / "model.zip"
            )
            assert spec["resume"] == expected_resume
            output = spec["output_dir"]
            output.mkdir(parents=True)
            (output / "model.zip").write_bytes(b"trained")
            (output / "policy_runtime.pkl").write_bytes(b"runtime")
            config = json.loads(spec["parameters_path"].read_text(encoding="utf-8"))
            (output / "artifact.json").write_text(
                json.dumps(
                    {
                        "timesteps": 10,
                        "requested_timesteps": timesteps,
                        "seed": seed,
                        "effective_config": {
                            "variant_runtime": spec["label"],
                            "parameters": config,
                        },
                        "resumed_from": str(tmp_path / "wrong.zip")
                        if publication == "wrong_resume"
                        else str(expected_resume)
                        if expected_resume
                        else None,
                        "completed": True,
                    }
                ),
                encoding="utf-8",
            )
        trained.append(
            {
                spec["label"]: (
                    json.loads(spec["parameters_path"].read_text(encoding="utf-8")),
                    (spec["source_root"] / "robot_learning" / "train.py").read_text(
                        encoding="utf-8"
                    ),
                    (spec["source_root"] / "robot_learning" / "variants").exists(),
                )
                for spec in specs
            }
        )

    monkeypatch.setattr(execution, "train_variants", train_variants)
    monkeypatch.setattr(
        execution,
        "candidate_directories",
        lambda _path: [{"name": "checkpoint-10", "path": _path, "timesteps": 10}],
    )

    def archive(_operation, contenders, _config, *, campaign_id):
        assert _config == {
            "base": active,
            "short": {**active, "ppo": {"gamma": 0.9, "n_steps": 64}},
        }
        return [
            {
                "name": contender["name"],
                "artifact": repository.repo_relative_path(contender["path"]),
                "fingerprint": repository.artifact_fingerprint(contender["path"]),
                "timesteps": 10,
                "training_success": None,
                "ep_rew_mean": None,
            }
            for contender in contenders
        ]

    monkeypatch.setattr(repository, "archive_candidates", archive)
    monkeypatch.setattr(
        repository, "persist_saved_components_inventory", lambda *a, **k: {}
    )
    monkeypatch.setattr(execution, "remove_candidate_dir", lambda _path: None)

    if publication == "wrong_resume":
        with pytest.raises(ValueError, match="resume training checkpoint"):
            run_experiment.execute_pending_operation()
        assert (
            "resume training checkpoint"
            in repository.read_state()["pending_operation"]["failure"]
        )
        return

    if publication != "normal":
        original_upsert = repository.upsert_operation_event

        def fail_publication(_event):
            raise OSError("publication interrupted")

        monkeypatch.setattr(repository, "upsert_operation_event", fail_publication)
        with pytest.raises(OSError, match="publication interrupted"):
            run_experiment.execute_pending_operation()
        interrupted = repository.read_state()
        assert interrupted["pending_operation"]["progress"] == "result_ready"
        if publication == "legacy_result_ready":
            for variant in interrupted["pending_operation"]["data"]["result"][
                "variants"
            ]:
                del variant["parent"]
            repository.write_state(interrupted)
        monkeypatch.setattr(repository, "upsert_operation_event", original_upsert)
        monkeypatch.setattr(
            execution, "train_variants", lambda *a: pytest.fail("retrained")
        )
        monkeypatch.setattr(
            protocol,
            "resolved_training_parent",
            lambda *a: pytest.fail("re-resolved parent"),
        )

    assert run_experiment.execute_pending_operation() == 0

    shorter = {**active, "ppo": {"gamma": 0.9, "n_steps": 64}}
    assert trained == [
        {"base": (active, "base\n", False), "short": (shorter, "short\n", False)}
    ]
    completed = repository.read_state()
    result = completed["operation_events"][0]["result"]
    expected_variants = (
        [
            {
                "label": "base",
                "parent": expected_parents["base"]["id"]
                if expected_parents["base"]
                else None,
                "parameters": {},
                "candidates": ["T1:base-checkpoint-10"],
            },
            {
                "label": "short",
                "parent": expected_parents["short"]["id"]
                if expected_parents["short"]
                else None,
                "parameters": {"ppo": {"gamma": 0.9}},
                "candidates": ["T1:short-checkpoint-10"],
            },
        ]
        if publication != "legacy_result_ready"
        else [
            {
                "label": "base",
                "parameters": {},
                "candidates": ["T1:base-checkpoint-10"],
            },
            {
                "label": "short",
                "parameters": {"ppo": {"gamma": 0.9}},
                "candidates": ["T1:short-checkpoint-10"],
            },
        ]
    )
    assert result["variants"] == expected_variants
    assert completed["candidates"]["T1:short-checkpoint-10"]["parameters"] == shorter
    assert completed["candidates"]["T1:base-checkpoint-10"]["parameters"] == active


def test_variant_process_resume_override_and_shared_fallback(monkeypatch, tmp_path):
    commands = []

    class Process:
        returncode = 0

        def poll(self):
            return 0

    def popen(command, **_kwargs):
        commands.append(command)
        return Process()

    monkeypatch.setattr(execution.subprocess, "Popen", popen)
    specs = []
    for label, override in (
        ("own", {"resume": tmp_path / "own.zip"}),
        ("fresh", {"resume": None}),
        ("inherited", {}),
    ):
        output = tmp_path / label
        output.mkdir()
        for filename in repository.INFERENCE_ARTIFACT_FILES:
            (output / filename).write_bytes(b"output")
        specs.append(
            {
                "label": label,
                "source_root": tmp_path,
                "output_dir": output,
                "parameters_path": tmp_path / "parameters.json",
                "training_log": tmp_path / f"{label}.log",
                **override,
            }
        )
    execution.train_variants(specs, 10, 4, tmp_path / "shared.zip", "T1")
    assert commands[0][-2:] == ["--resume", str(tmp_path / "own.zip")]
    assert "--resume" not in commands[1]
    assert commands[2][-2:] == ["--resume", str(tmp_path / "shared.zip")]


@pytest.mark.parametrize("legacy", [False, True])
def test_saved_comparisons_use_the_parent_of_each_prior_variant(
    monkeypatch, tmp_path, legacy
):
    state = _configure(monkeypatch, tmp_path)
    first = _add_training_parent(state, tmp_path, "first")
    second = _add_training_parent(state, tmp_path, "second")
    variants = [
        {"label": "first", "candidates": [first["id"]], "parent": "earlier:first"},
        {"label": "second", "candidates": [second["id"]], "parent": "earlier:second"},
    ]
    if legacy:
        for variant in variants:
            del variant["parent"]
    state["operation_events"] = [
        {
            "id": "T0",
            "kind": "training",
            "status": "completed",
            "result": {
                "parent": "earlier:root",
                "seed": 4,
                "requested_steps": 100,
                "variants": variants,
            },
        }
    ]
    comparisons = run_experiment._saved_component_comparisons(
        state,
        [{**first, "id": "T1:checkpoint-100"}],
        parent=None,
        seed=4,
        requested_steps=100,
    )["comparisons"]
    assert [item["context"]["parent"] for item in comparisons] == (
        ["earlier:root"] if legacy else ["earlier:first", "earlier:second"]
    )


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
