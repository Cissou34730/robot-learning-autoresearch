import json
from pathlib import Path

import pytest

from research import runner_protocol as protocol
from research import runner_repository as repository
from research.run_experiment import apply_previous_result_decision


def _artifact(path: Path, marker: str) -> Path:
    path.mkdir(parents=True)
    path.joinpath("model.zip").write_bytes(marker.encode("ascii"))
    path.joinpath("artifact.json").write_text(
        json.dumps({"marker": marker}), encoding="utf-8"
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


def test_v4_lineage_roles_are_independent_training_parents(monkeypatch, tmp_path):
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


def test_v4_measurement_catalog_exposes_roles_and_retained(monkeypatch, tmp_path):
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


def test_v4_rejects_legacy_role_aliases(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    working = _artifact(tmp_path / "working-checkpoint", "working")
    state = {
        "schema_version": 4,
        "working_lineage": _lineage(working, steps=120_000),
        "best_known_lineage": None,
        "retained_lineages": [],
    }

    for identifier in ("accepted", "champion"):
        try:
            protocol.training_parent({"training_parent": identifier}, state, "transfer")
        except ValueError as error:
            assert str(error) == f"unknown training parent {identifier!r}"
        else:
            raise AssertionError(f"legacy role {identifier!r} was accepted")


def test_v4_working_and_best_known_planning_are_independent(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    working = _artifact(tmp_path / "working", "working")
    best = _artifact(tmp_path / "best", "best")
    candidate = _artifact(tmp_path / "candidate", "candidate")
    state = {
        "schema_version": 4,
        "working_lineage": _lineage(working, steps=120_000),
        "best_known_lineage": _lineage(best, steps=90_000),
        "retained_lineages": [],
        "pending_researcher_decision": {
            "experiment": 2,
            "candidates": [
                {
                    "name": "checkpoint-5000",
                    "artifact": candidate.name,
                    "timesteps": 5_000,
                    "evaluations": [],
                }
            ],
            "parameters": {"algorithm": {"name": "ppo"}},
            "initialization": "transfer",
            "parent_training_steps": 120_000,
        },
    }
    plan = protocol.plan_previous_result_decision(
        {
            "previous_result_decision": {
                "experiment": 2,
                "continue_from": "checkpoint-5000",
                "reason": "Explore its learning trajectory.",
                "code": {"action": "keep", "reason": "The recipe remains active."},
            }
        },
        state,
    )

    assert plan["working_record"]["artifact"] == candidate.name
    assert plan["working_record"]["training_steps"] == 125_000
    assert plan["best_known_record"]["artifact"] == best.name


def test_v4_best_known_requires_evidence_for_its_candidate(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    candidate = _artifact(tmp_path / "candidate", "candidate")
    state = {
        "schema_version": 4,
        "working_lineage": None,
        "best_known_lineage": None,
        "retained_lineages": [],
        "pending_researcher_decision": {
            "experiment": 1,
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
    proposal = {
        "previous_result_decision": {
            "experiment": 1,
            "continue_from": "checkpoint",
            "reason": "Keep it.",
            "code": {"action": "keep", "reason": "No code change."},
            "best_known": {
                "candidate": "checkpoint",
                "reason": "Measured well.",
                "evidence": ["missing.json"],
            },
        }
    }

    try:
        protocol.plan_previous_result_decision(proposal, state)
    except ValueError as error:
        assert "best_known evidence" in str(error)
    else:
        raise AssertionError("best-known designation accepted unrelated evidence")


def test_v4_retained_lineage_is_selectable_and_preserved(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    retained = _artifact(tmp_path / "retained", "retained")
    candidate = _artifact(tmp_path / "candidate", "candidate")
    state = {
        "schema_version": 4,
        "working_lineage": None,
        "best_known_lineage": None,
        "retained_lineages": [],
        "pending_researcher_decision": {
            "experiment": 1,
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
    retained_plan = protocol.plan_previous_result_decision(
        {
            "previous_result_decision": {
                "experiment": 1,
                "continue_from": "checkpoint",
                "reason": "Keep it.",
                "code": {"action": "keep", "reason": "No code change."},
                "retain": [
                    {
                        "candidate": "checkpoint",
                        "id": "alternate",
                        "reason": "Keep the checkpoint reusable.",
                    }
                ],
            }
        },
        state,
    )
    state["retained_lineages"] = retained_plan["retained"]
    state["retained_lineages"][0]["artifact"] = retained.name
    state["retained_lineages"][0]["fingerprint"] = (
        protocol.repository.artifact_fingerprint(retained)
    )

    parent = protocol.training_parent(
        {"training_parent": "alternate"}, state, "transfer"
    )

    assert parent == ("alternate", retained, 5_000)
    assert retained in protocol.repository.role_and_retention_artifacts(state)


def test_v4_state_rejects_legacy_accepted_aliases(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    state = {
        "schema_version": 4,
        "working_lineage": None,
        "best_known_lineage": None,
        "retained_lineages": [],
        "campaign": {
            "id": "campaign-test",
            "started_at": "2026-09-05T00:00:00Z",
            "base_commit": "a" * 40,
        },
        "accepted_artifact": "legacy",
    }

    try:
        repository.validate_v4_state(state, allow_missing_artifact=False)
    except RuntimeError as error:
        assert "legacy accepted aliases" in str(error)
    else:
        raise AssertionError("schema-v4 state accepted a legacy role alias")


def test_v4_best_known_replacement_requires_and_accepts_both_evidence(
    monkeypatch, tmp_path
):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    incumbent = _artifact(tmp_path / "incumbent", "incumbent")
    candidate = _artifact(tmp_path / "candidate", "candidate")
    incumbent_evidence = tmp_path / "incumbent-evaluation.json"
    candidate_evidence = tmp_path / "candidate-evaluation.json"
    incumbent_evidence.write_text("{}", encoding="utf-8")
    candidate_evidence.write_text("{}", encoding="utf-8")
    state = {
        "schema_version": 4,
        "working_lineage": _lineage(incumbent, steps=10_000),
        "best_known_lineage": _lineage(incumbent, steps=10_000),
        "retained_lineages": [],
        "pending_researcher_decision": {
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
        },
    }
    state["best_known_lineage"]["evaluation_artifacts"] = [incumbent_evidence.name]
    state["pending_researcher_decision"]["partial_evaluations"] = [
        {
            "candidate": "checkpoint",
            "episodes": 200,
            "seed": 1,
            "evaluation_semantics": "semantics",
            "model_fingerprint": repository.artifact_fingerprint(candidate),
            "metrics": {"evaluation_artifact": candidate_evidence.name},
        },
        {
            "candidate": "best_known",
            "episodes": 200,
            "seed": 1,
            "evaluation_semantics": "semantics",
            "model_fingerprint": repository.artifact_fingerprint(incumbent),
            "metrics": {"evaluation_artifact": incumbent_evidence.name},
        },
    ]
    decision = {
        "previous_result_decision": {
            "experiment": 2,
            "continue_from": "checkpoint",
            "reason": "Continue exploring.",
            "code": {"action": "keep", "reason": "No code change."},
            "best_known": {
                "candidate": "checkpoint",
                "reason": "Designate from comparable evidence.",
                "evidence": [candidate_evidence.name, incumbent_evidence.name],
            },
        }
    }

    plan = protocol.plan_previous_result_decision(decision, state)

    assert plan["best_known_record"]["artifact"] == candidate.name


def test_v4_best_known_replacement_rejects_incompatible_panels(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr(
        "research.runner_paths.RESULTS_PATH", tmp_path / "results.jsonl"
    )
    incumbent = _artifact(tmp_path / "incumbent", "incumbent")
    candidate = _artifact(tmp_path / "candidate", "candidate")
    incumbent_evidence = tmp_path / "incumbent-evaluation.json"
    candidate_evidence = tmp_path / "candidate-evaluation.json"
    incumbent_evidence.write_text("{}", encoding="utf-8")
    candidate_evidence.write_text("{}", encoding="utf-8")
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
                    "metrics": {"evaluation_artifact": candidate_evidence.name},
                },
                {
                    "candidate": "best_known",
                    "episodes": 200,
                    "seed": 1,
                    "evaluation_semantics": "incumbent-semantics",
                    "model_fingerprint": repository.artifact_fingerprint(incumbent),
                    "metrics": {"evaluation_artifact": incumbent_evidence.name},
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
                "evidence": [candidate_evidence.name, incumbent_evidence.name],
            },
        }
    }
    monkeypatch.setattr(
        protocol, "validate_postmortem_evidence", lambda *args, **kwargs: None
    )

    with pytest.raises(ValueError, match="compatible instrument and panel settings"):
        protocol.plan_previous_result_decision(proposal, state)


def test_v4_cleanup_preserves_working_artifact(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr(repository, "write_state", lambda state: None)
    candidate = _artifact(tmp_path / "candidate", "candidate")
    state = {
        "schema_version": 4,
        "working_lineage": None,
        "best_known_lineage": None,
        "retained_lineages": [],
        "pending_researcher_decision": {
            "experiment": 1,
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
    proposal = {
        "previous_result_decision": {
            "experiment": 1,
            "continue_from": "checkpoint",
            "reason": "Keep the promising model.",
            "code": {"action": "keep", "reason": "No code change."},
        }
    }

    assert not apply_previous_result_decision(proposal, state)

    assert state["working_lineage"]["artifact"] == candidate.name
    assert candidate.joinpath("model.zip").read_bytes() == b"candidate"
    assert candidate.joinpath("artifact.json").is_file()


def test_v4_restore_uses_predecision_lineage_recipe(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    working = _artifact(tmp_path / "working", "working")
    candidate = _artifact(tmp_path / "candidate", "candidate")
    state = {
        "schema_version": 4,
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


def test_v4_restore_rejects_lineage_without_recipe_provenance(monkeypatch, tmp_path):
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


def test_v4_cleanup_completion_is_recorded_without_removed_retained(
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
