import json
import subprocess
from pathlib import Path

import pytest

from research import runner_protocol as protocol
from research import runner_repository as repository
from research.run_experiment import apply_previous_result_decision


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


def test_v4_continuation_freezes_complete_parent_identity(monkeypatch, tmp_path):
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


def test_v4_continuation_requires_parent_recipe_provenance(monkeypatch, tmp_path):
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


def test_v4_reselecting_role_preserves_original_checkpoint_identity(
    monkeypatch, tmp_path
):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    working = _artifact(tmp_path / "working", "working")
    working_lineage = _lineage(working, steps=100_352)
    working_lineage["candidate"] = "checkpoint-100352"
    state = {
        "schema_version": 4,
        "campaign": {"id": "campaign", "started_at": "now", "base_commit": "base"},
        "working_lineage": working_lineage,
        "best_known_lineage": None,
        "retained_lineages": [],
        "pending_researcher_decision": {
            "experiment": 2,
            "candidates": [],
            "parameters": {},
            "initialization": "fresh",
            "parent_training_steps": 0,
        },
    }

    plan = protocol.plan_previous_result_decision(
        {
            "previous_result_decision": {
                "experiment": 2,
                "continue_from": "working",
                "reason": "Keep the current working model.",
                "code": {"action": "keep", "reason": "Keep the recipe."},
            }
        },
        state,
    )

    assert plan["working_record"]["candidate"] == "checkpoint-100352"
    assert plan["working_record"]["training_steps"] == 100_352


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
    original_best_artifact = state["best_known_lineage"]["artifact"]
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

    assert plan["working_record"]["artifact"].startswith(
        "research/checkpoints/retained/"
    )
    assert plan["working_record"]["training_steps"] == 125_000
    assert plan["best_known_record"]["artifact"].startswith(
        "research/checkpoints/retained/"
    )
    assert state["best_known_lineage"]["artifact"] == original_best_artifact


def test_v4_planning_reuses_one_durable_artifact_for_matching_aliases(
    monkeypatch, tmp_path
):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    durable = _artifact(
        tmp_path / "research" / "checkpoints" / "retained" / "existing",
        "same",
    )
    candidate = _artifact(tmp_path / "candidate", "same")
    best_known = _lineage(durable, steps=10_000)
    best_known["artifact"] = repository.repo_relative_path(durable)
    state = {
        "schema_version": 4,
        "campaign": {"id": "campaign", "started_at": "now", "base_commit": "base"},
        "working_lineage": None,
        "best_known_lineage": best_known,
        "retained_lineages": [],
        "pending_researcher_decision": {
            "experiment": 2,
            "candidates": [
                {
                    "name": "checkpoint-5000",
                    "artifact": repository.repo_relative_path(candidate),
                    "timesteps": 5_000,
                    "evaluations": [],
                }
            ],
            "parameters": {},
            "initialization": "fresh",
            "parent_training_steps": 0,
        },
    }

    plan = protocol.plan_previous_result_decision(
        {
            "previous_result_decision": {
                "experiment": 2,
                "continue_from": "checkpoint-5000",
                "reason": "Use the identical candidate.",
                "code": {"action": "keep", "reason": "Keep the recipe."},
            }
        },
        state,
    )

    durable_path = repository.repo_relative_path(durable)
    assert plan["working_record"]["artifact"] == durable_path
    assert plan["best_known_record"]["artifact"] == durable_path
    assert plan["artifact_publications"] == []


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


def test_v4_best_known_uses_historical_fingerprint_binding_not_role_paths(
    monkeypatch, tmp_path
):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr(
        "research.runner_paths.RESULTS_PATH", tmp_path / "results.jsonl"
    )
    candidate = _artifact(tmp_path / "candidate", "candidate")
    fingerprint = repository.artifact_fingerprint(candidate)
    evidence = tmp_path / "historical-evaluation.json"
    evidence.write_text("{}", encoding="utf-8")
    repository.append_result(
        {
            "campaign_id": "campaign",
            "index": 1,
            "requested_evaluations": [
                {
                    "instrument": "research_evaluation",
                    "candidate": "old-alias",
                    "episodes": 2,
                    "seed": 10,
                    "evaluation_semantics": "semantics",
                    "model_fingerprint": fingerprint,
                    "metrics": {
                        "evaluation_artifact": evidence.name,
                        "evaluation_artifact_fingerprint": repository.file_fingerprint(
                            evidence
                        ),
                    },
                }
            ],
        }
    )
    state = {
        "schema_version": 4,
        "campaign": {"id": "campaign"},
        "working_lineage": None,
        "best_known_lineage": None,
        "retained_lineages": [],
        "pending_researcher_decision": {
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
    proposal = {
        "previous_result_decision": {
            "experiment": 2,
            "continue_from": "checkpoint",
            "reason": "Keep it.",
            "code": {"action": "keep", "reason": "No code change."},
            "best_known": {
                "candidate": "checkpoint",
                "reason": "Historical evidence measures these exact weights.",
                "evidence": [evidence.name],
            },
        }
    }

    plan = protocol.plan_previous_result_decision(proposal, state)

    assert plan["best_known_record"]["evaluation_artifacts"] == [evidence.name]

    evidence.write_text('{"replaced": true}', encoding="utf-8")
    with pytest.raises(ValueError, match="content changed after measurement"):
        protocol.plan_previous_result_decision(proposal, state)


def test_v4_best_known_reports_missing_legacy_model_identity(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr(
        "research.runner_paths.RESULTS_PATH", tmp_path / "results.jsonl"
    )
    candidate = _artifact(tmp_path / "candidate", "candidate")
    evidence = tmp_path / "legacy-evaluation.json"
    evidence.write_text("{}", encoding="utf-8")
    repository.append_result(
        {
            "campaign_id": "campaign",
            "index": 1,
            "requested_evaluations": [
                {
                    "candidate": "checkpoint",
                    "episodes": 2,
                    "seed": 10,
                    "evaluation_semantics": "semantics",
                    "metrics": {"evaluation_artifact": evidence.name},
                }
            ],
        }
    )
    state = {
        "schema_version": 4,
        "campaign": {"id": "campaign"},
        "working_lineage": None,
        "best_known_lineage": None,
        "retained_lineages": [],
        "pending_researcher_decision": {
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
    proposal = {
        "previous_result_decision": {
            "experiment": 2,
            "continue_from": "checkpoint",
            "reason": "Keep it.",
            "code": {"action": "keep", "reason": "No code change."},
            "best_known": {
                "candidate": "checkpoint",
                "reason": "Try to use imported legacy evidence.",
                "evidence": [evidence.name],
            },
        }
    }

    with pytest.raises(ValueError, match="lacks model identity metadata"):
        protocol.plan_previous_result_decision(proposal, state)


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


def test_v4_best_known_replacement_resolves_incumbent_evidence_from_state(
    monkeypatch, tmp_path
):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    incumbent = _artifact(tmp_path / "incumbent", "incumbent")
    candidate = _artifact(tmp_path / "candidate", "candidate")
    incumbent_evidence = tmp_path / "incumbent-evaluation.json"
    candidate_evidence = tmp_path / "candidate-evaluation.json"
    _research_evidence(incumbent_evidence)
    _research_evidence(candidate_evidence)
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
            "episodes": 2,
            "seed": 1,
            "evaluation_semantics": "shared-evaluation-semantics",
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
            "episodes": 2,
            "seed": 1,
            "evaluation_semantics": "shared-evaluation-semantics",
            "model_fingerprint": repository.artifact_fingerprint(incumbent),
            "metrics": {
                "evaluation_artifact": incumbent_evidence.name,
                "evaluation_artifact_fingerprint": repository.file_fingerprint(
                    incumbent_evidence
                ),
            },
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
                "evidence": [candidate_evidence.name],
            },
        }
    }

    plan = protocol.plan_previous_result_decision(decision, state)

    assert plan["best_known_record"]["artifact"].startswith(
        "research/checkpoints/retained/"
    )

    state["pending_researcher_decision"]["partial_evaluations"][0][
        "model_fingerprint"
    ] = repository.artifact_fingerprint(incumbent)
    with pytest.raises(ValueError, match="true fingerprint mismatch"):
        protocol.plan_previous_result_decision(decision, state)


def test_v4_best_known_replacement_rejects_missing_incumbent_state_evidence(
    monkeypatch, tmp_path
):
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    incumbent = _artifact(tmp_path / "incumbent", "incumbent")
    candidate = _artifact(tmp_path / "candidate", "candidate")
    candidate_evidence = tmp_path / "candidate-evaluation.json"
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
                    "evaluations": [],
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
                    "evaluation_semantics": "semantics",
                    "model_fingerprint": repository.artifact_fingerprint(candidate),
                    "metrics": {
                        "evaluation_artifact": candidate_evidence.name,
                        "evaluation_artifact_fingerprint": repository.file_fingerprint(
                            candidate_evidence
                        ),
                    },
                }
            ],
        },
    }
    proposal = {
        "previous_result_decision": {
            "experiment": 2,
            "continue_from": "checkpoint",
            "reason": "Continue exploring.",
            "code": {"action": "keep", "reason": "No code change."},
            "best_known": {
                "candidate": "checkpoint",
                "reason": "Designate from candidate evidence.",
                "evidence": [candidate_evidence.name],
            },
        }
    }

    with pytest.raises(
        ValueError, match="incumbent evidence in current lineage state"
    ):
        protocol.plan_previous_result_decision(proposal, state)


def test_v4_best_known_replacement_rejects_incompatible_panels(monkeypatch, tmp_path):
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
                    "episodes": 2,
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
                    "episodes": 2,
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
                "evidence": [candidate_evidence.name],
            },
        }
    }
    monkeypatch.setattr(
        protocol, "validate_postmortem_evidence", lambda *args, **kwargs: None
    )

    with pytest.raises(ValueError, match="compatible instrument and panel settings"):
        protocol.plan_previous_result_decision(proposal, state)


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

    assert state["working_lineage"]["artifact"].startswith(
        "research/checkpoints/retained/"
    )
    assert candidate.joinpath("model.zip").read_bytes() == b"candidate"
    assert candidate.joinpath("artifact.json").is_file()


def test_v4_publication_copies_complete_artifact_and_reuses_matching_destination(
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


def test_v4_publication_refuses_different_matching_destination(monkeypatch, tmp_path):
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


def test_v4_publication_requires_saved_policy_runtime(monkeypatch, tmp_path):
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


def test_v4_durable_artifact_path_is_compact_and_identity_derived(
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


def test_v4_publication_failure_leaves_no_partial_destination(monkeypatch, tmp_path):
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


def test_v4_cleanup_complete_resume_does_not_regress_progress(monkeypatch, tmp_path):
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


def test_v4_cleanup_retries_after_partial_deletion(monkeypatch, tmp_path):
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


def test_v4_clearance_push_failure_restores_recoverable_operation(
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


def test_v4_clearance_interrupt_restores_recoverable_operation(monkeypatch):
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


def test_published_v4_roles_survive_clean_clone(monkeypatch, tmp_path):
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    monkeypatch.setattr("research.runner_paths.ROOT", repository_root)
    monkeypatch.setattr(
        "research.runner_paths.RESEARCH_DIR", repository_root / "research"
    )
    state_path = repository_root / "research" / "research_state.json"
    monkeypatch.setattr("research.runner_paths.STATE_PATH", state_path)
    working = _artifact(
        repository_root / "research" / "checkpoints" / "challengers" / "working",
        "working",
    )
    best = _artifact(
        repository_root / "research" / "checkpoints" / "challengers" / "best",
        "best",
    )
    alternative = _artifact(
        repository_root / "research" / "checkpoints" / "challengers" / "alternative",
        "alternative",
    )
    best_known = _lineage(best, steps=80_000)
    best_known["artifact"] = repository.repo_relative_path(best)
    state = {
        "schema_version": 4,
        "campaign": {"id": "campaign", "started_at": "now", "base_commit": "base"},
        "working_lineage": None,
        "best_known_lineage": best_known,
        "retained_lineages": [],
        "pending_researcher_decision": {
            "experiment": 3,
            "candidates": [
                {
                    "name": "checkpoint-100352",
                    "artifact": repository.repo_relative_path(working),
                    "timesteps": 100_352,
                    "evaluations": [],
                },
                {
                    "name": "checkpoint-40960",
                    "artifact": repository.repo_relative_path(alternative),
                    "timesteps": 40_960,
                    "evaluations": [],
                },
            ],
            "parameters": {},
            "initialization": "fresh",
            "parent_training_steps": 0,
        },
    }
    repository.write_state(state)
    proposal = {
        "previous_result_decision": {
            "experiment": 3,
            "continue_from": "checkpoint-100352",
            "reason": "Continue the working model.",
            "code": {"action": "keep", "reason": "Keep the recipe."},
            "retain": [
                {
                    "candidate": "checkpoint-40960",
                    "id": "alternative",
                    "reason": "Preserve a distinct alternative.",
                }
            ],
        }
    }

    assert not apply_previous_result_decision(proposal, state)
    published = repository.read_state()
    assert published["working_lineage"]["candidate"] == "checkpoint-100352"
    assert published["best_known_lineage"]["candidate"] == best.name
    assert published["retained_lineages"][0]["id"] == "alternative"

    subprocess.run(
        ["git", "init"], cwd=repository_root, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "core.longpaths", "true"],
        cwd=repository_root,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=repository_root,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test Runner"],
        cwd=repository_root,
        check=True,
    )
    subprocess.run(
        ["git", "add", "research/checkpoints/retained", "research/research_state.json"],
        cwd=repository_root,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "publish lineage"],
        cwd=repository_root,
        check=True,
        capture_output=True,
    )
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", str(remote)],
        cwd=repository_root,
        check=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", "HEAD"],
        cwd=repository_root,
        check=True,
        capture_output=True,
    )
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "-c", "core.longpaths=true", "clone", str(remote), str(clone)],
        check=True,
        capture_output=True,
    )
    cloned_state = json.loads(
        clone.joinpath("research/research_state.json").read_text(encoding="utf-8")
    )
    cloned_records = [
        cloned_state["working_lineage"],
        cloned_state["best_known_lineage"],
        *cloned_state["retained_lineages"],
    ]
    assert len({record["fingerprint"] for record in cloned_records}) == 3
    for record in cloned_records:
        cloned_artifact = clone / record["artifact"]
        repository.require_complete_inference_artifact(
            cloned_artifact, "cloned lineage"
        )
        assert repository.artifact_fingerprint(cloned_artifact) == record["fingerprint"]
