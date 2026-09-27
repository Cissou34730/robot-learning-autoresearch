"""Focused tests for generic execution, ownership, and recovery contracts."""

import json
from argparse import Namespace
from pathlib import Path

import pytest

from research import run_experiment
from research import runner_execution as execution
from research import runner_protocol as protocol
from research import runner_repository as repository
from robot_learning.training import research_config


def _campaign_state() -> dict:
    return repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        last_verdict="fresh",
    )


def _baseline_proposal() -> dict:
    return {
        "baseline": True,
        "change": "Train the unchanged baseline.",
        "hypothesis": "Establish the campaign baseline.",
        "initialization": "fresh",
    }


def _training_proposal() -> dict:
    return {
        "kind": "training",
        "method_id": "method-a",
        "family": "observation.representation",
        "initialization": "fresh",
        "change": "Change the observation representation.",
        "investigation_design": {
            "evidence": [
                {"source": "evidence.txt", "observation": "Learning plateaus."}
            ],
            "expected_observation": "Progress changes under the method.",
            "initialization_reason": "Fresh initialization isolates the method.",
            "objective_link": "The plateau limits objective progress.",
            "rationale": "The run tests the active method.",
            "open_question": "Does the representation alter learning?",
        },
    }


def _activate_inquiry_and_method(state: dict) -> None:
    state["inquiry_session"] = {
        "id": "session",
        "campaign_id": "campaign",
        "inquiry_id": 1,
        "role": "principal_investigator",
        "status": "started",
    }
    state["active_inquiry"] = {
        "id": 1,
        "question": "Can a different method improve learning?",
        "scope": "Learning behavior.",
        "closure_condition": "Resolve the method disposition.",
        "status": "active",
        "session_id": "session",
        "reframes": [],
    }
    state["active_method"] = {
        "id": "method-a",
        "inquiry_id": 1,
        "scientific_question": "Can the method improve learning?",
        "rationale": "It tests a distinct representation.",
        "lifecycle": "development",
        "base_scientific_commit": "parent",
        "current_lineage": None,
        "iterations": [],
        "resolution": None,
    }


def test_research_memory_requires_a_decision_frontier(monkeypatch, tmp_path):
    (tmp_path / "evidence.txt").write_text("Observed.", encoding="utf-8")
    memory = tmp_path / "postmortems.md"
    memory.write_text(
        "## campaign / Scientific strategy\n\n"
        "**Current synthesis:** A current explanation.\n\n"
        "**Lessons and limits:** One limited observation.\n\n"
        "**Competing explanations:** Two mechanisms remain.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.POSTMORTEM_PATH", memory)
    proposal = {"investigation_design": _training_proposal()["investigation_design"]}
    with pytest.raises(ValueError, match="Decision frontier"):
        protocol.validate_research_memory(proposal, {"campaign": {"id": "campaign"}})

    memory.write_text(
        memory.read_text(encoding="utf-8")
        + "\n**Decision frontier:** Which observation distinguishes them?\n",
        encoding="utf-8",
    )
    protocol.validate_research_memory(proposal, {"campaign": {"id": "campaign"}})


def test_validation_suites_follow_changed_surface():
    assert protocol.validation_test_paths([], fresh_baseline=False) == ()
    assert (
        protocol.validation_test_paths(
            ["research/current_params.json"], fresh_baseline=False
        )
        == ()
    )
    assert protocol.validation_test_paths(
        ["robot_learning/scenario/reward.py"], fresh_baseline=False
    )


def test_protected_files_are_rejected_from_scientific_delta():
    with pytest.raises(ValueError, match="human-owned"):
        protocol.validate_experiment_semantics(
            _training_proposal(),
            "training",
            "fresh",
            None,
            ["research/run_experiment.py"],
            False,
        )


def test_training_proposal_accepts_generic_investigation_design():
    protocol.validate_training_proposal(_training_proposal(), baseline=False)


def test_continuation_and_replication_do_not_require_a_recipe_change():
    continuation = _training_proposal()
    continuation.update(
        kind="continuation",
        initialization="transfer",
        training_parent="working",
    )
    continuation.pop("change")
    protocol.validate_training_proposal(continuation, baseline=False)
    protocol.validate_experiment_semantics(
        continuation, "continuation", "transfer", None, [], False
    )

    replication = _training_proposal()
    replication.update(kind="replication", training_seed=19, replication_of=1)
    replication.pop("change")
    protocol.validate_training_proposal(replication, baseline=False)
    protocol.validate_experiment_semantics(
        replication, "replication", "fresh", None, [], False
    )


def test_frozen_training_operation_rejects_proposal_or_source_tampering(
    monkeypatch, tmp_path
):
    source = tmp_path / "robot_learning" / "scenario" / "reward.py"
    source.parent.mkdir(parents=True)
    source.write_text("reward = 1\n", encoding="utf-8")
    proposal = _training_proposal()
    state = {}
    monkeypatch.setattr(run_experiment.paths, "ROOT", tmp_path)
    monkeypatch.setattr(protocol, "resolved_training_parent", lambda *_args: None)
    monkeypatch.setattr(repository, "write_state", lambda _state: None)
    monkeypatch.setattr(
        repository,
        "scientific_delta",
        lambda _parent: ["robot_learning/scenario/reward.py"],
    )
    run_experiment._training_parent_operation(
        proposal,
        state,
        experiment=2,
        initialization="fresh",
        code_parent_commit="parent",
        researcher_changes=["robot_learning/scenario/reward.py"],
    )

    with pytest.raises(
        run_experiment.FrozenOperationMismatch, match="proposal changed"
    ):
        run_experiment._training_parent_operation(
            {**proposal, "change": "Tampered."},
            state,
            experiment=2,
            initialization="fresh",
            code_parent_commit="parent",
            researcher_changes=["robot_learning/scenario/reward.py"],
        )

    source.write_text("reward = 2\n", encoding="utf-8")
    with pytest.raises(run_experiment.FrozenOperationMismatch, match="changed after"):
        run_experiment._training_parent_operation(
            proposal,
            state,
            experiment=2,
            initialization="fresh",
            code_parent_commit="parent",
            researcher_changes=["robot_learning/scenario/reward.py"],
        )


def test_fresh_baseline_uses_the_reset_recipe_anchor(monkeypatch):
    state = {"pending_scientific_parent": "reset-parent"}
    monkeypatch.setattr(repository, "scientific_delta", lambda parent: [])
    monkeypatch.setattr(repository, "status_paths", lambda scope: [])
    monkeypatch.setattr(
        repository,
        "git",
        lambda *args: pytest.fail(f"unexpected Git call: {args}"),
    )
    assert run_experiment.fresh_baseline_scientific_parent(state) == "reset-parent"


def test_method_decision_execution_reanchors_before_delta_validation(
    monkeypatch, tmp_path
):
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps({"method_decision": {}}), encoding="utf-8")
    state = _campaign_state()
    reanchored = False

    monkeypatch.setattr(
        run_experiment,
        "parse_args",
        lambda: Namespace(
            begin_inquiry=False,
            mark_inquiry_session_starting=False,
            mark_inquiry_session_started=False,
            check_proposal=False,
            check_preparation_deliverable=False,
            check_scientific_model_deliverable=False,
            check_evaluation_request=False,
            check_analysis_deliverable=False,
            record_implementation_repair_attempt=False,
            complete_implementation_repair=False,
            evaluate_pending_final=False,
            evaluate_pending=False,
            training_cap_reached=False,
        ),
    )
    monkeypatch.setattr(run_experiment.paths, "PROPOSAL_PATH", proposal_path)
    monkeypatch.setattr(repository, "synchronize_experiment_log", lambda: None)
    monkeypatch.setattr(repository, "read_state", lambda: state)
    monkeypatch.setattr(
        protocol,
        "validate_proposal_against_state",
        lambda *_args, **_kwargs: "method_decision",
    )

    def reanchor(current):
        nonlocal reanchored
        assert current is state
        reanchored = True

    def validate_delta(current):
        assert current is state
        assert reanchored
        return []

    monkeypatch.setattr(run_experiment, "reanchor_phase_parent", reanchor)
    monkeypatch.setattr(run_experiment, "validate_research_delta", validate_delta)
    monkeypatch.setattr(run_experiment, "resolve_method_decision", lambda proposal: 0)

    assert run_experiment.main() == 0
    assert reanchored


def test_baseline_proposal_requires_a_true_fresh_campaign(monkeypatch, tmp_path):
    baseline_pending = tmp_path / "BASELINE_PENDING"
    baseline_pending.write_text("pending\n", encoding="utf-8")
    monkeypatch.setattr(protocol.paths, "BASELINE_PENDING_PATH", baseline_pending)
    state = _campaign_state()

    assert (
        protocol.validate_proposal_against_state(_baseline_proposal(), state)
        == "training"
    )

    state["last_allocated_experiment"] = 1
    state["campaign_experiment_counters"]["campaign"] = 1
    with pytest.raises(ValueError, match="true fresh campaign"):
        protocol.validate_proposal_against_state(_baseline_proposal(), state)


def test_method_start_accepts_owned_edits_but_rejects_protected_edits(
    monkeypatch, tmp_path, capsys
):
    research = tmp_path / "research"
    research.mkdir()
    state = _campaign_state()
    _activate_inquiry_and_method(state)
    state["active_method"] = None
    state["pending_scientific_parent"] = "parent"
    proposal = {
        "method": {
            "action": "start",
            "id": "method-b",
            "scientific_question": "Can a new controller improve learning?",
            "rationale": "The inquiry evidence supports implementing it.",
            "lifecycle": "concept",
        }
    }
    state_path = research / "state.json"
    proposal_path = research / "proposal.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
    monkeypatch.setattr(repository.paths, "STATE_PATH", state_path)
    monkeypatch.setattr(repository.paths, "PROPOSAL_PATH", proposal_path)
    monkeypatch.setattr(run_experiment, "reanchor_phase_parent", lambda current: None)
    monkeypatch.setattr(repository, "campaign_lab_change_paths", lambda paths: [])
    monkeypatch.setattr(
        run_experiment,
        "anchored_scientific_delta",
        lambda current: ["robot_learning/scenario/new_method.py"],
    )

    assert run_experiment.check_proposal() == 0
    assert "PROPOSAL_VALID: method" in capsys.readouterr().out

    monkeypatch.setattr(
        run_experiment,
        "anchored_scientific_delta",
        lambda current: ["tests/autoresearch/test_execution_contract.py"],
    )
    assert run_experiment.check_proposal() == 1
    assert "not part of the researcher's surface" in capsys.readouterr().out


def test_restored_recipe_dispatches_as_fresh_experiment_one(monkeypatch, tmp_path):
    research = tmp_path / "research"
    research.mkdir()
    state_path = research / "research_state.json"
    state = repository.empty_campaign_state(
        campaign={
            "id": "campaign",
            "started_at": "now",
            "base_commit": "reset-commit",
            "recipe_source_commit": "recipe-commit",
        },
        last_verdict="fresh baseline pending after research reset",
    )
    state_path.write_text(json.dumps(state), encoding="utf-8")
    baseline_pending = research / "BASELINE_PENDING"
    baseline_pending.write_text("pending\n", encoding="utf-8")
    for name, value in {
        "ROOT": tmp_path,
        "RESEARCH_DIR": research,
        "STATE_PATH": state_path,
        "RESULTS_PATH": research / "results.jsonl",
        "LOG_PATH": research / "EXPERIMENTS.md",
        "POSTMORTEM_PATH": research / "postmortems.md",
        "PROPOSAL_PATH": research / "proposal.json",
        "CANDIDATE_ROOT": tmp_path / "models" / "candidates",
        "TRAINING_LOG_DIR": research / "training_logs",
        "BASELINE_PENDING_PATH": baseline_pending,
        "RESTART_PENDING_PATH": research / "RESTART_PENDING",
        "RECOVERY_PENDING_PATH": research / "RECOVERY_PENDING",
    }.items():
        monkeypatch.setattr(repository.paths, name, value)

    dispatched: list[dict] = []

    def stop_before_training(
        output_dir, timesteps, seed, resume, training_log, **kwargs
    ):
        dispatched.append(
            {
                "output_dir": output_dir,
                "timesteps": timesteps,
                "seed": seed,
                "resume": resume,
                "training_log": training_log,
                "label": kwargs["label"],
            }
        )
        raise KeyboardInterrupt

    monkeypatch.setattr(repository, "git", lambda *args: "reset-commit\n")
    monkeypatch.setattr(repository, "scientific_delta", lambda parent: [])
    monkeypatch.setattr(repository, "publish_scientific_recipe", lambda *args: "recipe")
    monkeypatch.setattr(execution, "validate_active_configuration", lambda: None)
    monkeypatch.setattr(execution, "validate_dependency_metadata", lambda: None)
    monkeypatch.setattr(execution, "run_validation_suites", lambda paths: None)
    monkeypatch.setattr(execution, "train_candidate", stop_before_training)
    monkeypatch.setattr("research.runner_console.announce", lambda message: None)

    assert (
        run_experiment.run_training_experiment(
            _baseline_proposal(), Namespace(timesteps=120_000, reuse_candidate=None)
        )
        == 130
    )
    assert dispatched[0]["timesteps"] == 120_000
    assert dispatched[0]["resume"] is None
    assert dispatched[0]["label"] == "baseline training"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["last_allocated_experiment"] == 1
    assert persisted["working_lineage"] is None
    assert baseline_pending.exists()


def test_inquiry_phase_reanchors_without_replacing_session(monkeypatch, tmp_path):
    state_path = tmp_path / "state.json"
    state = _campaign_state()
    state["working_lineage"] = {
        "artifact": "working",
        "fingerprint": "fingerprint",
        "origin_experiment": 1,
        "candidate": "baseline",
        "parameters": {},
        "scientific_commit": "a" * 40,
        "training_steps": 120_000,
        "evaluation_artifacts": [],
        "reason": "Selected baseline.",
    }
    _activate_inquiry_and_method(state)
    state_path.write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    monkeypatch.setattr(
        repository,
        "reanchor_scientific_parent",
        lambda current: (
            current.update(pending_scientific_parent="new-head") or "new-head"
        ),
    )
    monkeypatch.setattr("research.runner_console.announce", lambda message: None)

    assert run_experiment.begin_inquiry_phase() == 0
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["pending_scientific_parent"] == "new-head"
    assert persisted["inquiry_session"]["id"] == "session"
    assert persisted["active_inquiry"]["id"] == 1


def test_experiment_identity_is_consumed_before_training(monkeypatch, tmp_path):
    state = _campaign_state()
    _activate_inquiry_and_method(state)
    state["pending_scientific_parent"] = "parent"
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(repository.paths, "ROOT", tmp_path)
    monkeypatch.setattr(repository.paths, "STATE_PATH", state_path)
    for name, value in {
        "RESEARCH_DIR": tmp_path / "research",
        "RESULTS_PATH": tmp_path / "research" / "results.jsonl",
        "LOG_PATH": tmp_path / "research" / "EXPERIMENTS.md",
        "POSTMORTEM_PATH": tmp_path / "research" / "postmortems.md",
        "PROPOSAL_PATH": tmp_path / "research" / "proposal.json",
        "CANDIDATE_ROOT": tmp_path / "models" / "candidates",
        "TRAINING_LOG_DIR": tmp_path / "research" / "training_logs",
        "RESTART_PENDING_PATH": tmp_path / "research" / "RESTART_PENDING",
        "RECOVERY_PENDING_PATH": tmp_path / "research" / "RECOVERY_PENDING",
    }.items():
        monkeypatch.setattr(repository.paths, name, value)
    monkeypatch.setattr(repository, "git", lambda *args: "parent\n")
    monkeypatch.setattr(repository, "scientific_delta", lambda parent: [])
    monkeypatch.setattr(repository, "publish_campaign_laboratory", lambda state: None)
    monkeypatch.setattr(execution, "validate_active_configuration", lambda: None)
    monkeypatch.setattr(execution, "validate_dependency_metadata", lambda: None)
    monkeypatch.setattr(
        execution,
        "train_candidate",
        lambda *args, **kwargs: (_ for _ in ()).throw(KeyboardInterrupt),
    )
    monkeypatch.setattr("research.runner_console.announce", lambda message: None)

    proposal = _training_proposal()
    proposal["params"] = {"training": {"n_envs": 1}}
    assert (
        run_experiment.run_training_experiment(
            proposal, Namespace(timesteps=10, reuse_candidate=None)
        )
        == 130
    )
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["last_allocated_experiment"] == 1
    assert persisted["pending_training_operation"]["experiment"] == 1


def test_completed_training_is_published_after_restart_without_retraining(
    monkeypatch, tmp_path
):
    state = _campaign_state()
    _activate_inquiry_and_method(state)
    state["pending_scientific_parent"] = "parent"
    ledger_rounds = [{"round": 1, "inquiry_id": 1, "status": "completed"}]
    state["preparation_measurement"] = {
        "experiment": 1,
        "inquiry_id": 1,
        "campaign_lab": None,
        "rounds": ledger_rounds,
        "partial_evaluations": [],
        "partial_task_reference_evaluations": [],
    }
    state_path = tmp_path / "research" / "state.json"
    state_path.parent.mkdir()
    state_path.write_text(json.dumps(state), encoding="utf-8")
    for name, value in {
        "ROOT": tmp_path,
        "RESEARCH_DIR": tmp_path / "research",
        "STATE_PATH": state_path,
        "RESULTS_PATH": tmp_path / "research" / "results.jsonl",
        "LOG_PATH": tmp_path / "research" / "EXPERIMENTS.md",
        "POSTMORTEM_PATH": tmp_path / "research" / "postmortems.md",
        "PROPOSAL_PATH": tmp_path / "research" / "proposal.json",
        "CANDIDATE_ROOT": tmp_path / "models" / "candidates",
        "TRAINING_LOG_DIR": tmp_path / "research" / "training_logs",
        "RESTART_PENDING_PATH": tmp_path / "research" / "RESTART_PENDING",
        "RECOVERY_PENDING_PATH": tmp_path / "research" / "RECOVERY_PENDING",
    }.items():
        monkeypatch.setattr(repository.paths, name, value)

    archived = {
        "name": "candidate",
        "artifact": "archive/candidate",
        "fingerprint": "candidate-fingerprint",
        "timesteps": 10,
        "evaluations": [],
    }
    train_calls = 0
    removals = []

    def train_once(*_args, **_kwargs):
        nonlocal train_calls
        train_calls += 1
        return 1.0

    original_upsert = repository.upsert_result
    publication_attempts = 0

    def fail_first_publication(result):
        nonlocal publication_attempts
        publication_attempts += 1
        if publication_attempts == 1:
            raise OSError("injected publication failure")
        original_upsert(result)

    monkeypatch.setattr(repository, "git", lambda *args: "parent\n")
    monkeypatch.setattr(repository, "scientific_delta", lambda parent: [])
    monkeypatch.setattr(repository, "publish_campaign_laboratory", lambda state: None)
    monkeypatch.setattr(repository, "publish_scientific_recipe", lambda *args: "recipe")
    monkeypatch.setattr(repository, "require_resolvable_commit", lambda commit: None)
    monkeypatch.setattr(
        repository, "require_complete_inference_artifact", lambda *args: None
    )
    monkeypatch.setattr(
        repository,
        "archive_candidates",
        lambda *args, **kwargs: [dict(archived)],
    )
    monkeypatch.setattr(repository, "upsert_result", fail_first_publication)
    monkeypatch.setattr(protocol, "validate_experiment_semantics", lambda *args: None)
    monkeypatch.setattr(execution, "validate_active_configuration", lambda: None)
    monkeypatch.setattr(execution, "train_candidate", train_once)
    monkeypatch.setattr(
        execution,
        "candidate_directories",
        lambda candidate_dir: [{"name": "candidate", "timesteps": 10}],
    )
    monkeypatch.setattr(
        execution,
        "remove_candidate_dir",
        lambda candidate_dir: removals.append(candidate_dir),
    )
    monkeypatch.setattr("research.runner_console.announce", lambda message: None)

    args = Namespace(timesteps=10, reuse_candidate=None)
    assert run_experiment.run_training_experiment(_training_proposal(), args) == 1
    interrupted = json.loads(state_path.read_text(encoding="utf-8"))
    assert interrupted["pending_training_operation"]["progress"] == (
        "candidates_archived"
    )
    assert interrupted["pending_analysis"] is None
    assert interrupted["preparation_measurement"]["rounds"] == ledger_rounds
    assert removals == []

    assert run_experiment.run_training_experiment(_training_proposal(), args) == 0
    recovered = json.loads(state_path.read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in repository.paths.RESULTS_PATH.read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    assert train_calls == 1
    assert publication_attempts == 2
    assert len(removals) == 1
    assert recovered["pending_training_operation"] is None
    assert recovered["pending_analysis"]["experiment"] == 1
    assert [(record["index"], record["status"]) for record in records] == [
        (1, "trained")
    ]
    assert records[0]["preparation_evaluation_rounds"] == ledger_rounds
    assert recovered["pending_analysis"]["preparation_evaluation_rounds"] == (
        ledger_rounds
    )
    assert recovered["preparation_measurement"] is None


def _complete_artifact(path: Path, marker: bytes = b"model") -> Path:
    path.mkdir(parents=True)
    path.joinpath("model.zip").write_bytes(marker)
    path.joinpath("artifact.json").write_text("{}", encoding="utf-8")
    path.joinpath("policy_runtime.pkl").write_bytes(b"runtime:" + marker)
    return path


def _saved_lineage(path: Path) -> dict:
    return {
        "artifact": repository.repo_relative_path(path),
        "fingerprint": repository.artifact_fingerprint(path),
        "origin_experiment": 1,
        "candidate": "checkpoint-100",
        "parameters": {"training": {"n_envs": 1}},
        "scientific_commit": "a" * 40,
        "training_steps": 100,
        "evaluation_artifacts": [],
        "reason": "Selected lineage.",
        "designation_ordinal": 1,
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("scientific_commit", "", "no scientific_commit provenance"),
        ("parameters", None, "no effective parameters"),
        ("fingerprint", "stale", "fingerprint does not match"),
    ],
)
def test_continuation_parent_requires_recipe_provenance(
    monkeypatch, tmp_path, field, value, message
):
    monkeypatch.setattr(repository.paths, "ROOT", tmp_path)
    state = _campaign_state()
    state["working_lineage"] = _saved_lineage(_complete_artifact(tmp_path / "w"))
    state["working_lineage"][field] = value

    with pytest.raises(ValueError, match=message):
        protocol.resolved_training_parent(
            {"kind": "continuation", "training_parent": "working"}, state, "transfer"
        )


def test_frozen_training_parent_survives_role_change_but_not_replacement(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(repository.paths, "ROOT", tmp_path)
    monkeypatch.setattr(repository, "write_state", lambda _state: None)
    monkeypatch.setattr(repository, "scientific_delta", lambda _parent: [])
    monkeypatch.setattr(
        protocol,
        "plan_lineage_restore",
        lambda parent: {"parent": "a" * 40, "restore": [], "remove_created": []},
    )
    working = _complete_artifact(tmp_path / "working", b"working")
    state = _campaign_state()
    state["working_lineage"] = _saved_lineage(working)
    proposal = {"kind": "continuation", "training_parent": "working"}
    frozen = {
        "experiment": 2,
        "initialization": "transfer",
        "code_parent_commit": "parent",
        "researcher_changes": [],
    }
    operation = run_experiment._training_parent_operation(proposal, state, **frozen)
    parent = dict(operation["parent"])

    state["working_lineage"] = _saved_lineage(
        _complete_artifact(tmp_path / "reassigned", b"reassigned")
    )
    resumed = run_experiment._training_parent_operation(proposal, state, **frozen)

    assert resumed["parent"] == parent
    assert repository.resolve_repo_path(parent["artifact"]) == working
    assert parent["scientific_commit"] == "a" * 40
    assert parent["parameters"] == {"training": {"n_envs": 1}}
    working.joinpath("model.zip").write_bytes(b"replaced")
    with pytest.raises(
        run_experiment.FrozenOperationMismatch, match="parent fingerprint changed"
    ):
        run_experiment._apply_training_parent_operation(resumed, state)


def _write_manifest(root: Path, names: list[str]) -> None:
    for name in names:
        _complete_artifact(root / "checkpoints" / name, name.encode())
    root.joinpath("candidate_manifest.json").write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "name": name,
                        "timesteps": int(name.split("-")[1]),
                        "path": f"checkpoints/{name}",
                        "training_success": index / 10,
                    }
                    for index, name in enumerate(names)
                ]
            }
        ),
        encoding="utf-8",
    )


def test_candidate_manifest_preserves_identity_order_and_artifacts(tmp_path):
    names = ["checkpoint-400", "checkpoint-100", "checkpoint-300", "checkpoint-200"]
    source = tmp_path / "source"
    _write_manifest(source, names)
    _complete_artifact(source / "final", b"final")
    for filename in ("model.zip", "artifact.json", "policy_runtime.pkl"):
        (source / filename).write_bytes((source / "final" / filename).read_bytes())

    execution.copy_candidate_outputs(source, tmp_path / "copied")
    candidates = execution.candidate_directories(tmp_path / "copied")

    assert [item["name"] for item in candidates] == names
    assert [item["timesteps"] for item in candidates] == [400, 100, 300, 200]
    assert [item["training_success"] for item in candidates] == [0, 0.1, 0.2, 0.3]
    for item in candidates:
        original = source / "checkpoints" / item["name"]
        assert repository.artifact_fingerprint(
            item["path"]
        ) == repository.artifact_fingerprint(original)


@pytest.mark.parametrize(
    ("corruption", "message"),
    [("name", "checkpoint-<steps>"), ("runtime", "candidate is incomplete")],
)
def test_candidate_manifest_rejects_unnamed_or_incomplete_candidates(
    tmp_path, corruption, message
):
    _write_manifest(tmp_path, ["checkpoint-100", "checkpoint-200"])
    if corruption == "name":
        manifest = json.loads((tmp_path / "candidate_manifest.json").read_text())
        manifest["candidates"][1]["name"] = "final"
        (tmp_path / "candidate_manifest.json").write_text(json.dumps(manifest))
    else:
        (tmp_path / "checkpoints" / "checkpoint-200" / "policy_runtime.pkl").unlink()

    with pytest.raises(RuntimeError, match=message):
        execution.candidate_directories(tmp_path)


def test_interrupted_training_resumes_remaining_budget_under_one_identity(
    monkeypatch, tmp_path
):
    state = _campaign_state()
    _activate_inquiry_and_method(state)
    state["pending_scientific_parent"] = "parent"
    research = tmp_path / "research"
    research.mkdir()
    state_path = research / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    for name, value in {
        "ROOT": tmp_path,
        "RESEARCH_DIR": research,
        "STATE_PATH": state_path,
        "RESULTS_PATH": research / "results.jsonl",
        "LOG_PATH": research / "EXPERIMENTS.md",
        "POSTMORTEM_PATH": research / "postmortems.md",
        "PROPOSAL_PATH": research / "proposal.json",
        "CANDIDATE_ROOT": tmp_path / "models" / "candidates",
        "TRAINING_LOG_DIR": research / "training_logs",
        "RESTART_PENDING_PATH": research / "RESTART_PENDING",
        "RECOVERY_PENDING_PATH": research / "RECOVERY_PENDING",
    }.items():
        monkeypatch.setattr(repository.paths, name, value)
    config_path = research / "current_params.json"
    config_path.write_text(
        research_config.CONFIG_PATH.read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr(research_config, "CONFIG_PATH", config_path)
    dispatched: list[dict] = []

    def train(output_dir, timesteps, seed, resume, training_log, **kwargs):
        dispatched.append(
            {
                "timesteps": timesteps,
                "resume": resume,
                "continue": kwargs.get("continue_timesteps", False),
            }
        )
        if len(dispatched) > 1:
            return 1.0
        training_log.parent.mkdir(parents=True, exist_ok=True)
        training_log.write_text("interrupted\n", encoding="utf-8")
        _complete_artifact(output_dir)
        output_dir.joinpath("artifact.json").write_text(
            json.dumps({"timesteps": 4, "completed": False}), encoding="utf-8"
        )
        raise KeyboardInterrupt

    monkeypatch.setattr(repository, "git", lambda *args: "parent\n")
    monkeypatch.setattr(repository, "scientific_delta", lambda parent: [])
    monkeypatch.setattr(repository, "publish_campaign_laboratory", lambda state: None)
    monkeypatch.setattr(repository, "publish_scientific_recipe", lambda *args: "recipe")
    monkeypatch.setattr(repository, "require_resolvable_commit", lambda commit: None)
    monkeypatch.setattr(
        repository, "require_complete_inference_artifact", lambda *args: None
    )
    monkeypatch.setattr(
        repository,
        "archive_candidates",
        lambda index, contenders, *args, **kwargs: [
            {
                "name": "checkpoint-10",
                "artifact": f"archive/experiment-{index}",
                "fingerprint": "candidate-fingerprint",
                "timesteps": 10,
                "evaluations": [],
            }
        ],
    )
    monkeypatch.setattr(protocol, "validate_experiment_semantics", lambda *args: None)
    monkeypatch.setattr(execution, "validate_active_configuration", lambda: None)
    monkeypatch.setattr(execution, "validate_dependency_metadata", lambda: None)
    monkeypatch.setattr(execution, "validate_reusable_candidate", lambda *a, **k: None)
    monkeypatch.setattr(execution, "train_candidate", train)
    monkeypatch.setattr(
        execution,
        "candidate_directories",
        lambda candidate_dir: [{"name": "checkpoint-10", "timesteps": 10}],
    )
    monkeypatch.setattr(execution, "remove_candidate_dir", lambda path: None)
    monkeypatch.setattr("research.runner_console.announce", lambda message: None)

    first = Namespace(timesteps=10, reuse_candidate=None)
    assert run_experiment.run_training_experiment(_training_proposal(), first) == 130
    recovery = repository.resolve_repo_path(
        repository.paths.RECOVERY_PENDING_PATH.read_text(encoding="utf-8").strip()
    )
    assert recovery.name == "recovery-experiment-1"

    resumed = Namespace(timesteps=10, reuse_candidate=recovery)
    assert run_experiment.run_training_experiment(_training_proposal(), resumed) == 0

    assert dispatched[0] == {"timesteps": 10, "resume": None, "continue": False}
    assert dispatched[-1] == {
        "timesteps": 6,
        "resume": recovery / "model.zip",
        "continue": True,
    }
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["last_allocated_experiment"] == 1
    assert persisted["campaign_experiment_counters"]["campaign"] == 1
    assert persisted["pending_analysis"]["experiment"] == 1
    assert [record["index"] for record in repository.result_records()] == [1]
    assert not repository.paths.RECOVERY_PENDING_PATH.exists()


def test_inquiry_measurement_history_is_append_only_across_rounds():
    state = _campaign_state()
    state["preparation_measurement"] = {
        "experiment": 2,
        "inquiry_id": 1,
        "campaign_lab": None,
        "rounds": [{"round": 1, "status": "completed"}],
        "partial_evaluations": [{"evaluation_artifact": "round-1.json"}],
        "partial_task_reference_evaluations": [],
    }
    pending = {
        "experiment": 3,
        "inquiry_id": 1,
        "evaluation_rounds": [
            {"round": 1, "status": "completed"},
            {"round": 2, "status": "completed"},
        ],
    }

    run_experiment.append_preparation_measurement(
        state,
        pending,
        executed=[
            {"evaluation_artifact": "round-1.json"},
            {"evaluation_artifact": "round-2.json"},
        ],
        reference_executed=[{"evaluation_artifact": "reference-2.json"}],
    )

    ledger = state["preparation_measurement"]
    assert [item["round"] for item in ledger["rounds"]] == [1, 2]
    assert [item["evaluation_artifact"] for item in ledger["partial_evaluations"]] == [
        "round-1.json",
        "round-2.json",
    ]
    assert ledger["partial_task_reference_evaluations"] == [
        {"evaluation_artifact": "reference-2.json"}
    ]


def test_role_change_preserves_measurement_round_history_but_not_stale_reuse():
    state = _campaign_state()
    _activate_inquiry_and_method(state)
    state["working_lineage"] = {
        "artifact": "working",
        "fingerprint": "new-fingerprint",
        "origin_experiment": 2,
        "candidate": "new-working",
        "parameters": {},
        "scientific_commit": "b" * 40,
        "training_steps": 20,
        "evaluation_artifacts": [],
        "reason": "New working lineage.",
    }
    state["preparation_measurement"] = {
        "experiment": 3,
        "inquiry_id": 1,
        "rounds": [{"round": 1, "status": "completed"}],
        "partial_evaluations": [
            {
                "candidate": "working",
                "model_fingerprint": "old-fingerprint",
                "evaluation_artifact": "old.json",
            }
        ],
        "partial_task_reference_evaluations": [],
    }

    pending = protocol.preparation_measurement_context(state)

    assert pending["evaluation_rounds"] == [{"round": 1, "status": "completed"}]
    assert pending["partial_evaluations"] == []
