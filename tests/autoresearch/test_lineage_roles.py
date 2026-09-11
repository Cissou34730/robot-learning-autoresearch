import json
from pathlib import Path

import pytest

from research import runner_protocol as protocol
from research import runner_repository as repository


@pytest.fixture(autouse=True)
def _redirect_research_dir(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.RESEARCH_DIR", tmp_path / "research")
    monkeypatch.setattr("research.runner_paths.LOG_PATH", tmp_path / "EXPERIMENTS.md")


def _artifact(path: Path, marker: str) -> Path:
    path.mkdir(parents=True)
    path.joinpath("model.zip").write_bytes(marker.encode("ascii"))
    path.joinpath("artifact.json").write_text(
        json.dumps({"marker": marker}), encoding="utf-8"
    )
    path.joinpath("policy_runtime.pkl").write_bytes(
        b"runtime:" + marker.encode("ascii")
    )
    return path


def _lineage(path: Path, *, steps: int) -> dict:
    return {
        "artifact": path.name,
        "fingerprint": repository.artifact_fingerprint(path),
        "origin_experiment": 1,
        "candidate": path.name,
        "parameters": {"algorithm": {"name": path.name}},
        "scientific_commit": "a" * 40,
        "training_steps": steps,
        "evaluation_artifacts": [],
        "reason": f"Preserve {path.name}.",
    }


def _research_evidence(path: Path, *, seed: int = 1) -> None:
    path.write_text(
        json.dumps(
            {
                "episodes": 2,
                "seed": seed,
                "episode_results": [
                    {"episode": episode, "episode_seed": seed + episode, "success": True}
                    for episode in range(2)
                ],
            }
        ),
        encoding="utf-8",
    )


def test_lineage_roles_are_independent_training_parents(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    working = _artifact(tmp_path / "working-checkpoint", "working")
    best_known = _artifact(tmp_path / "best-known-checkpoint", "best-known")
    retained = _artifact(tmp_path / "retained-checkpoint", "retained")
    state = {
        "schema_version": 4,
        "working_lineage": _lineage(working, steps=120_000),
        "best_known_lineage": _lineage(best_known, steps=80_000),
        "retained_lineages": [
            {"id": "alternative", **_lineage(retained, steps=60_000)}
        ],
    }

    working_parent = protocol.training_parent(
        {"training_parent": "working"}, state, "transfer"
    )
    best_parent = protocol.training_parent(
        {"training_parent": "best_known"}, state, "transfer"
    )
    retained_parent = protocol.training_parent(
        {"training_parent": "alternative"}, state, "transfer"
    )

    assert working_parent == ("working", working, 120_000)
    assert best_parent == ("best_known", best_known, 80_000)
    assert retained_parent == ("alternative", retained, 60_000)
    assert working.joinpath("model.zip").read_bytes() == b"working"
    assert best_known.joinpath("model.zip").read_bytes() == b"best-known"


def test_continuation_freezes_complete_parent_identity(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    working = _artifact(tmp_path / "working-checkpoint", "working")
    lineage = _lineage(working, steps=120_000)
    lineage["candidate"] = "checkpoint-100352"
    state = {
        "schema_version": 4,
        "working_lineage": lineage,
        "best_known_lineage": None,
        "retained_lineages": [],
    }

    resolved = protocol.resolved_training_parent(
        {
            "kind": "continuation",
            "training_parent": "working",
        },
        state,
        "transfer",
    )

    assert resolved == {
        "identifier": "working",
        "artifact": working.name,
        "fingerprint": lineage["fingerprint"],
        "origin_experiment": 1,
        "candidate": "checkpoint-100352",
        "parameters": lineage["parameters"],
        "scientific_commit": "a" * 40,
        "training_steps": 120_000,
    }


def test_continuation_requires_parent_recipe_provenance(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    working = _artifact(tmp_path / "working-checkpoint", "working")
    lineage = _lineage(working, steps=120_000)
    lineage["scientific_commit"] = None
    state = {
        "schema_version": 4,
        "working_lineage": lineage,
        "best_known_lineage": None,
        "retained_lineages": [],
    }

    with pytest.raises(ValueError, match="has no scientific_commit provenance"):
        protocol.resolved_training_parent(
            {"kind": "continuation", "training_parent": "working"},
            state,
            "transfer",
        )


def test_lineage_restore_includes_effective_parameter_file(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr(repository, "require_resolvable_commit", lambda commit: None)
    monkeypatch.setattr(
        repository,
        "scientific_delta",
        lambda commit: [
            "robot_learning/scenario/reward.py",
            "research/current_params.json",
            "research/run_experiment.py",
        ],
    )
    monkeypatch.setattr(repository, "tracked_at_commit", lambda commit, path: True)

    plan = protocol.plan_lineage_restore({"scientific_commit": "a" * 40})

    assert plan["restore"] == [
        "robot_learning/scenario/reward.py",
        "research/current_params.json",
    ]


def test_lineage_restore_is_noop_when_parent_recipe_is_current(monkeypatch):
    monkeypatch.setattr(repository, "require_resolvable_commit", lambda commit: None)
    monkeypatch.setattr(repository, "scientific_delta", lambda commit: [])

    assert protocol.plan_lineage_restore({"scientific_commit": "a" * 40}) == {
        "parent": "a" * 40,
        "restore": [],
        "remove_created": [],
    }


def test_measurement_catalog_exposes_roles_and_retained(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    working = _artifact(tmp_path / "working-checkpoint", "working")
    best_known = _artifact(tmp_path / "best-known-checkpoint", "best-known")
    retained = _artifact(tmp_path / "retained-checkpoint", "retained")
    state = {
        "schema_version": 4,
        "working_lineage": _lineage(working, steps=120_000),
        "best_known_lineage": _lineage(best_known, steps=80_000),
        "retained_lineages": [
            {"id": "alternative", **_lineage(retained, steps=60_000)}
        ],
    }
    pending = {
        "candidates": [
            {
                "name": "checkpoint-40k",
                "artifact": "current-checkpoint",
                "evaluations": [],
            }
        ]
    }

    available = protocol.available_evaluation_candidates(pending, state)

    assert set(available) == {
        "checkpoint-40k",
        "working",
        "best_known",
        "alternative",
    }
    assert available["working"]["artifact"] == working.name
    assert available["best_known"]["artifact"] == best_known.name
    assert available["alternative"]["artifact"] == retained.name


def test_best_known_replacement_does_not_require_incumbent_panel_equality(
    monkeypatch, tmp_path
):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr(
        "research.runner_paths.RESULTS_PATH", tmp_path / "results.jsonl"
    )
    incumbent = _artifact(tmp_path / "incumbent", "incumbent")
    candidate = _artifact(tmp_path / "candidate", "candidate")
    incumbent_evidence = tmp_path / "incumbent-evaluation.json"
    candidate_evidence = tmp_path / "candidate-evaluation.json"
    _research_evidence(incumbent_evidence)
    _research_evidence(candidate_evidence)
    state = {
        "schema_version": 4,
        "campaign": {"id": "campaign", "started_at": "now", "base_commit": "base"},
        "working_lineage": _lineage(incumbent, steps=10_000),
        "best_known_lineage": _lineage(incumbent, steps=10_000),
        "retained_lineages": [],
        "pending_analysis": {
            "experiment": 2,
            "candidates": [
                {
                    "name": "checkpoint",
                    "artifact": candidate.name,
                    "timesteps": 5_000,
                    "evaluations": [{"evaluation_artifact": candidate_evidence.name}],
                }
            ],
            "parameters": {},
            "initialization": "fresh",
            "parent_training_steps": 0,
            "partial_evaluations": [
                {
                    "candidate": "checkpoint",
                    "episodes": 200,
                    "seed": 1,
                    "evaluation_semantics": "candidate-semantics",
                    "model_fingerprint": repository.artifact_fingerprint(candidate),
                    "metrics": {
                        "evaluation_artifact": candidate_evidence.name,
                        "evaluation_artifact_fingerprint": repository.file_fingerprint(
                            candidate_evidence
                        ),
                    },
                },
                {
                    "candidate": "best_known",
                    "episodes": 1000,
                    "seed": 1,
                    "evaluation_semantics": "incumbent-semantics",
                    "model_fingerprint": repository.artifact_fingerprint(incumbent),
                    "metrics": {
                        "evaluation_artifact": incumbent_evidence.name,
                        "evaluation_artifact_fingerprint": repository.file_fingerprint(
                            incumbent_evidence
                        ),
                    },
                },
            ],
        },
    }
    state["best_known_lineage"]["evaluation_artifacts"] = [incumbent_evidence.name]
    proposal = {
        "previous_result_decision": {
            "experiment": 2,
            "continue_from": "checkpoint",
            "reason": "Continue exploring.",
            "code": {"action": "keep", "reason": "No code change."},
            "best_known": {
                "candidate": "checkpoint",
                "reason": "Designate from comparable evidence.",
            },
        }
    }
    monkeypatch.setattr(
        protocol, "validate_postmortem_evidence", lambda *args, **kwargs: None
    )

    plan = protocol.plan_previous_result_decision(proposal, state)
    assert plan["best_known_record"]["evaluation_artifacts"] == [
        candidate_evidence.name
    ]


def test_best_known_evidence_compatibility_keeps_task_reference_exact():
    task_reference = {
        "instrument": "task_reference",
        "settings": ("task_reference", "fixed-panel", 1, 100, 42),
    }

    assert protocol._evidence_records_compatible(task_reference, dict(task_reference))
    assert not protocol._evidence_records_compatible(
        task_reference,
        {
            "instrument": "task_reference",
            "settings": ("task_reference", "fixed-panel", 2, 100, 42),
        },
    )
    assert not protocol._evidence_records_compatible(
        task_reference,
        {
            "instrument": "research_evaluation",
            "settings": ("research_evaluation", 100, 42, "broad-semantics"),
        },
    )


def test_publication_copies_complete_artifact_and_reuses_matching_destination(
    monkeypatch, tmp_path
):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    source = tmp_path / "models" / "candidates" / "source"
    source.mkdir(parents=True)
    for filename, content in {
        "model.zip": b"model",
        "artifact.json": b"{}",
        "policy_runtime.pkl": b"runtime",
        "vecnormalize.pkl": b"normalization",
        "replay_buffer.pkl": b"replay",
    }.items():
        (source / filename).write_bytes(content)
    destination = tmp_path / "research" / "checkpoints" / "retained" / "lineage"
    publication = {
        "source": repository.repo_relative_path(source),
        "destination": repository.repo_relative_path(destination),
        "fingerprint": repository.artifact_fingerprint(source),
    }

    repository.validate_artifact_publication(publication)
    repository.publish_artifact(publication)
    for source_file in source.iterdir():
        source_file.unlink()
    source.rmdir()
    repository.publish_artifact(publication)

    assert repository.artifact_fingerprint(destination) == publication["fingerprint"]
    assert (destination / "policy_runtime.pkl").read_bytes() == b"runtime"
    assert (destination / "vecnormalize.pkl").read_bytes() == b"normalization"
    assert (destination / "replay_buffer.pkl").read_bytes() == b"replay"


def test_publication_refuses_different_matching_destination(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    source = _artifact(tmp_path / "source", "source")
    destination = _artifact(
        tmp_path / "research" / "checkpoints" / "retained" / "lineage", "other"
    )
    publication = {
        "source": repository.repo_relative_path(source),
        "destination": repository.repo_relative_path(destination),
        "fingerprint": repository.artifact_fingerprint(source),
    }

    with pytest.raises(ValueError, match="collides with a different artifact"):
        repository.validate_artifact_publication(publication)


def test_publication_requires_saved_policy_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    source.joinpath("model.zip").write_bytes(b"model")
    source.joinpath("artifact.json").write_text("{}", encoding="utf-8")
    publication = {
        "source": repository.repo_relative_path(source),
        "destination": "research/checkpoints/retained/lineage",
        "fingerprint": repository.artifact_fingerprint(source),
    }

    with pytest.raises(ValueError, match="policy_runtime.pkl"):
        repository.validate_artifact_publication(publication)


def test_durable_artifact_path_is_compact_and_identity_derived(
    monkeypatch, tmp_path
):
    monkeypatch.setattr("research.runner_paths.RESEARCH_DIR", tmp_path / "research")
    fingerprint = "a" * 64

    first = repository.durable_artifact_destination(
        campaign_id="campaign",
        origin_experiment=123,
        candidate="checkpoint-100352-" + "long-name-" * 20,
        fingerprint=fingerprint,
    )
    second = repository.durable_artifact_destination(
        campaign_id="campaign",
        origin_experiment=123,
        candidate="checkpoint-120832-" + "long-name-" * 20,
        fingerprint=fingerprint,
    )

    assert first != second
    assert first.name.startswith("e123-c")
    assert first.name.endswith(f"-{fingerprint}")
    assert len(first.name) == 79


def test_publication_failure_leaves_no_partial_destination(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    source = _artifact(tmp_path / "source", "source")
    destination = tmp_path / "research" / "checkpoints" / "retained" / "lineage"
    publication = {
        "source": repository.repo_relative_path(source),
        "destination": repository.repo_relative_path(destination),
        "fingerprint": repository.artifact_fingerprint(source),
    }
    original_copy = repository.copy_artifact

    def fail_after_staging(source_path, destination_path):
        original_copy(source_path, destination_path)
        raise OSError("injected publication failure")

    monkeypatch.setattr(repository, "copy_artifact", fail_after_staging)
    with pytest.raises(OSError, match="injected publication failure"):
        repository.publish_artifact(publication)

    assert not destination.exists()
    assert not list(destination.parent.glob(".lineage-*.tmp"))


def test_restore_uses_predecision_lineage_recipe(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.RESULTS_PATH", tmp_path / "results.jsonl")
    working = _artifact(tmp_path / "working", "working")
    candidate = _artifact(tmp_path / "candidate", "candidate")
    state = {
        "schema_version": 4,
        "campaign": {"id": "campaign", "started_at": "now", "base_commit": "base"},
        "working_lineage": _lineage(working, steps=10_000),
        "best_known_lineage": None,
        "retained_lineages": [],
        "pending_analysis": {
            "experiment": 2,
            "candidates": [
                {
                    "name": "checkpoint",
                    "artifact": candidate.name,
                    "timesteps": 5_000,
                    "evaluations": [],
                }
            ],
            "parameters": {},
            "initialization": "fresh",
            "parent_training_steps": 0,
        },
    }
    monkeypatch.setattr(repository, "require_resolvable_commit", lambda commit: None)
    monkeypatch.setattr(
        protocol, "validate_postmortem_evidence", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        repository,
        "scientific_delta",
        lambda commit: [
            "robot_learning/scenario/reward.py",
            "tests/scenario/test_reward.py",
        ],
    )
    monkeypatch.setattr(
        repository,
        "tracked_at_commit",
        lambda commit, path: path == "robot_learning/scenario/reward.py",
    )

    plan = protocol.plan_previous_result_decision(
        {
            "previous_result_decision": {
                "experiment": 2,
                "continue_from": "checkpoint",
                "reason": "Continue the candidate.",
                "code": {
                    "action": "restore",
                    "reason": "Return to the working recipe.",
                    "lineage": "working",
                },
            }
        },
        state,
    )

    assert plan["code_plan"]["parent"] == "a" * 40
    assert plan["code_plan"]["restore"] == ["robot_learning/scenario/reward.py"]
    assert plan["code_plan"]["remove_created"] == [
        (tmp_path / "tests/scenario/test_reward.py").resolve()
    ]


def test_restore_rejects_lineage_without_recipe_provenance(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    working = _artifact(tmp_path / "working", "working")
    candidate = _artifact(tmp_path / "candidate", "candidate")
    lineage = _lineage(working, steps=10_000)
    lineage["scientific_commit"] = None
    monkeypatch.setattr(
        protocol, "validate_postmortem_evidence", lambda *args, **kwargs: None
    )
    state = {
        "schema_version": 4,
        "working_lineage": lineage,
        "best_known_lineage": None,
        "retained_lineages": [],
        "pending_analysis": {
            "experiment": 2,
            "candidates": [
                {
                    "name": "checkpoint",
                    "artifact": candidate.name,
                    "timesteps": 5_000,
                    "evaluations": [],
                }
            ],
            "parameters": {},
            "initialization": "fresh",
            "parent_training_steps": 0,
        },
    }

    with pytest.raises(ValueError, match="scientific_commit provenance"):
        protocol.plan_previous_result_decision(
            {
                "previous_result_decision": {
                    "experiment": 2,
                    "continue_from": "checkpoint",
                    "reason": "Continue.",
                    "code": {
                        "action": "restore",
                        "reason": "Restore.",
                        "lineage": "working",
                    },
                }
            },
            state,
        )


def test_cleanup_completion_is_recorded_without_removed_retained(
    monkeypatch, tmp_path
):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr(repository, "write_state", lambda state: None)
    selected = _artifact(tmp_path / "selected", "selected")
    disposable = _artifact(tmp_path / "disposable", "disposable")
    state = {
        "working_lineage": _lineage(selected, steps=10_000),
        "best_known_lineage": None,
        "retained_lineages": [],
        "pending_closure_operation": {
            "progress": "durable",
            "plan": {
                "pending": {
                    "candidates": [
                        {
                            "name": "selected",
                            "artifact": selected.name,
                        },
                        {
                            "name": "disposable",
                            "artifact": disposable.name,
                        },
                    ]
                },
                "removed_retained": [],
            },
        },
    }

    from research.run_experiment import finalize_pending_v4_closure

    finalize_pending_v4_closure(state)

    assert state["pending_closure_operation"]["progress"] == "cleanup_complete"
    assert selected.joinpath("model.zip").is_file()
    assert not disposable.joinpath("model.zip").exists()


def test_cleanup_complete_resume_does_not_regress_progress(monkeypatch, tmp_path):
    monkeypatch.setattr(repository, "write_state", lambda state: None)
    state = {
        "pending_closure_operation": {
            "progress": "cleanup_complete",
            "plan": {"pending": {}},
        }
    }

    from research.run_experiment import apply_pending_v4_closure

    assert not apply_pending_v4_closure(state)
    assert state["pending_closure_operation"]["progress"] == "cleanup_complete"


def test_cleanup_retries_after_partial_deletion(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr(repository, "write_state", lambda state: None)
    first = _artifact(tmp_path / "first", "first")
    second = _artifact(tmp_path / "second", "second")
    state = {
        "working_lineage": None,
        "best_known_lineage": None,
        "retained_lineages": [],
        "pending_closure_operation": {
            "progress": "durable",
            "plan": {
                "pending": {
                    "candidates": [
                        {"name": "first", "artifact": first.name},
                        {"name": "second", "artifact": second.name},
                    ]
                },
                "removed_retained": [],
            },
        },
    }
    original_remove = repository.remove_heavyweight_artifacts
    interrupted = False

    def interrupt_second(artifact):
        nonlocal interrupted
        if artifact == second and not interrupted:
            interrupted = True
            raise OSError("injected cleanup failure")
        original_remove(artifact)

    monkeypatch.setattr(repository, "remove_heavyweight_artifacts", interrupt_second)

    from research.run_experiment import finalize_pending_v4_closure

    with pytest.raises(OSError, match="cleanup failure"):
        finalize_pending_v4_closure(state)

    assert not first.joinpath("model.zip").exists()
    assert second.joinpath("model.zip").exists()
    assert state["pending_closure_operation"]["progress"] == "durable"

    monkeypatch.setattr(repository, "remove_heavyweight_artifacts", original_remove)
    finalize_pending_v4_closure(state)
    assert not second.joinpath("model.zip").exists()
    assert state["pending_closure_operation"]["progress"] == "cleanup_complete"


def test_clearance_push_failure_restores_recoverable_operation(
    monkeypatch, tmp_path
):
    operation = {
        "experiment": 4,
        "progress": "cleanup_complete",
        "plan": {"pending": {"candidates": []}, "removed_retained": []},
    }
    state = {"pending_closure_operation": operation}
    writes = []
    calls = 0

    def commit_memory(message):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected push failure")
        return True

    monkeypatch.setattr(repository, "commit_runner_memory", commit_memory)
    monkeypatch.setattr(
        repository, "write_state", lambda value: writes.append(value.copy())
    )

    from research.run_experiment import publish_v4_closure_completion

    with pytest.raises(RuntimeError, match="injected push failure"):
        publish_v4_closure_completion(state)

    assert state["pending_closure_operation"] is operation
    assert writes[-1]["pending_closure_operation"] is operation


def test_clearance_interrupt_restores_recoverable_operation(monkeypatch):
    operation = {
        "experiment": 4,
        "progress": "cleanup_complete",
        "plan": {"pending": {"candidates": []}, "removed_retained": []},
    }
    state = {"pending_closure_operation": operation}
    writes = []
    interrupted = False

    def write_state(value):
        nonlocal interrupted
        writes.append(value.copy())
        if value["pending_closure_operation"] is None and not interrupted:
            interrupted = True
            raise KeyboardInterrupt

    monkeypatch.setattr(repository, "commit_runner_memory", lambda message: True)
    monkeypatch.setattr(repository, "write_state", write_state)

    from research.run_experiment import publish_v4_closure_completion

    with pytest.raises(KeyboardInterrupt):
        publish_v4_closure_completion(state)

    assert state["pending_closure_operation"] is operation
    assert writes[-1]["pending_closure_operation"] is operation
