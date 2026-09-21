"""Issue #50: an adjusted continuation names the lineage it extends.

Continuing a lineage and changing the recipe are independent choices. The
relation is expressed as data - ``extends_lineage`` on a ``training`` proposal
with transfer initialization, or implicitly by ``continuation`` - so the
operation description, the experiment family and the brief keep it visible
whether or not the run carried a parameter delta.
"""

import copy
from argparse import Namespace

import pytest

from research import run_experiment
from research.build_research_brief import (
    _change_details,
    _v4_experiment_index_section,
)
from research.runner_protocol import (
    experiment_family,
    operation_description,
    validate_training_proposal,
)


def _frozen_lineage(
    identifier: str = "working",
    candidate: str = "checkpoint-100352",
    origin_experiment: int = 1,
) -> dict:
    return {
        "identifier": identifier,
        "candidate": candidate,
        "origin_experiment": origin_experiment,
    }


def _production_record(
    monkeypatch,
    root,
    proposal: dict,
    *,
    index: int = 1,
) -> dict:
    """Drive the runner's production training path and return its persisted record."""
    campaign_id = "campaign"
    state = {
        "schema_version": 4,
        "campaign": {"id": campaign_id, "base_commit": "base"},
        "working_lineage": None,
        "best_known_lineage": None,
        "retained_lineages": [],
        "pending_analysis": None,
        "last_allocated_experiment": 0,
        "accepted_training_steps": 0,
    }
    parent = {
        **_frozen_lineage(),
        "artifact": "archive/working",
        "parameters": {"algorithm": {"name": "ppo"}},
        "training_steps": 120_000,
    }
    persisted: list[dict] = []

    paths = run_experiment.paths
    repository = run_experiment.repository
    protocol = run_experiment.protocol
    execution = run_experiment.execution
    research_config = run_experiment.research_config

    monkeypatch.setattr(paths, "ROOT", root)
    monkeypatch.setattr(paths, "CANDIDATE_ROOT", root / "candidates")
    monkeypatch.setattr(paths, "TRAINING_LOG_DIR", root / "logs")
    monkeypatch.setattr(paths, "STATE_PATH", root / "research_state.json")
    monkeypatch.setattr(paths, "RESULTS_PATH", root / "results.jsonl")
    monkeypatch.setattr(paths, "PROPOSAL_PATH", root / "proposal.json")
    monkeypatch.setattr(paths, "RESTART_PENDING_PATH", root / "RESTART_PENDING")
    monkeypatch.setattr(paths, "RECOVERY_PENDING_PATH", root / "RECOVERY_PENDING")
    monkeypatch.setattr(repository, "load_state", lambda **kwargs: state)
    monkeypatch.setattr(repository, "write_state", lambda _state: None)
    monkeypatch.setattr(repository, "anchor_scientific_parent", lambda _state: "base")
    monkeypatch.setattr(repository, "scientific_delta", lambda _parent: [])
    monkeypatch.setattr(
        repository, "publish_scientific_recipe", lambda _experiment, _scope: "recipe"
    )
    monkeypatch.setattr(repository, "resolve_repo_path", lambda _path: root)
    monkeypatch.setattr(
        repository, "require_complete_artifact", lambda *_args: None
    )
    monkeypatch.setattr(
        repository, "require_complete_inference_artifact", lambda *_args: None
    )
    monkeypatch.setattr(
        repository, "apply_code_lineage_decision", lambda _plan: None
    )
    monkeypatch.setattr(
        repository,
        "archive_candidates",
        lambda *_args, **_kwargs: [{"name": "checkpoint-120832", "timesteps": 120_832}],
    )
    monkeypatch.setattr(
        repository, "upsert_result", lambda result: persisted.append(copy.deepcopy(result))
    )
    monkeypatch.setattr(protocol, "resolved_training_parent", lambda *_args: parent)
    monkeypatch.setattr(
        protocol,
        "plan_lineage_restore",
        lambda _lineage: {"parent": "base", "restore": [], "remove_created": []},
    )
    monkeypatch.setattr(protocol, "next_experiment_index", lambda *_args, **_kwargs: index)
    monkeypatch.setattr(protocol, "validate_experiment_semantics", lambda *_args: None)
    monkeypatch.setattr(
        protocol, "validation_test_paths", lambda *_args, **_kwargs: ()
    )
    monkeypatch.setattr(execution, "validate_active_configuration", lambda: None)
    monkeypatch.setattr(execution, "training_budget", lambda *_args: 120_000)
    monkeypatch.setattr(execution, "candidate_directories", lambda _path: [])
    monkeypatch.setattr(execution, "remove_candidate_dir", lambda _path: None)
    monkeypatch.setattr(execution, "train_candidate", lambda *_args, **_kwargs: 0.0)
    monkeypatch.setattr(
        execution, "training_attempt", lambda *_args, **_kwargs: 1
    )
    monkeypatch.setattr(
        research_config, "load_experiment_config", lambda: parent["parameters"]
    )
    monkeypatch.setattr(research_config, "write_experiment_config", lambda _config: None)
    monkeypatch.setattr(run_experiment.console, "announce", lambda _message: None)
    monkeypatch.setattr(
        run_experiment.console, "render_experiment_card", lambda _result: ""
    )
    monkeypatch.setattr(
        run_experiment.console, "render_training_summary_card", lambda *_a, **_k: ""
    )

    assert (
        run_experiment.run_training_experiment(
            proposal, Namespace(timesteps=120_000, reuse_candidate=None)
        )
        == 0
    )
    record = state["pending_analysis"]["result"]
    assert persisted == [record]
    return record


def _proposal(reasoning, **overrides):
    proposal = {
        "kind": "training",
        "family": "learning.learning_rate",
        "investigation_type": "confirmatory",
        "hypothesis": "a smaller learning rate refines the parent",
        "change": "lower the learning rate",
        "initialization": "transfer",
        "training_parent": "working",
        "extends_lineage": True,
        "params": {"ppo": {"learning_rate": 0.0001}},
        "reasoning": reasoning,
    }
    proposal.update(overrides)
    return proposal


def test_adjusted_continuation_is_expressible_as_a_training_proposal(
    scientific_reasoning,
):
    validate_training_proposal(_proposal(scientific_reasoning), baseline=False)


def test_extends_lineage_rejects_a_non_boolean(scientific_reasoning):
    proposal = _proposal(scientific_reasoning, extends_lineage="yes")

    with pytest.raises(ValueError, match="extends_lineage must be a boolean"):
        validate_training_proposal(proposal, baseline=False)


def test_extends_lineage_requires_transfer_initialization(scientific_reasoning):
    proposal = _proposal(scientific_reasoning)
    proposal.pop("training_parent")
    proposal["initialization"] = "fresh"

    with pytest.raises(ValueError, match="extends_lineage requires transfer"):
        validate_training_proposal(proposal, baseline=False)


def test_extends_lineage_is_only_valid_for_training(scientific_reasoning):
    proposal = _proposal(scientific_reasoning)
    proposal["kind"] = "continuation"
    proposal.pop("change")

    with pytest.raises(ValueError, match="only valid for a training"):
        validate_training_proposal(proposal, baseline=False)


def test_adjusted_continuation_description_names_the_lineage():
    description = operation_description(
        {
            "kind": "training",
            "training_parent": "working",
            "extends_lineage": True,
            "change": "lower the learning rate",
        }
    )

    assert description == (
        "Continue training lineage working with a changed recipe: "
        "lower the learning rate"
    )


def test_unchanged_continuation_description_names_the_lineage():
    assert operation_description(
        {"kind": "continuation", "training_parent": "working"}
    ) == "Continue training lineage working"


def test_operation_description_base_is_stable_across_a_parameter_delta():
    record = {
        "kind": "training",
        "training_parent": "working",
        "extends_lineage": True,
        "change": "lower the learning rate",
    }
    with_delta = {
        **record,
        "parameter_changes": [
            {"path": "ppo.learning_rate", "before": 3e-4, "after": 1e-4}
        ],
    }

    base = "Continue training lineage working with a changed recipe"
    assert operation_description(record).startswith(base)
    assert operation_description(with_delta).startswith(base)


def test_experiment_family_names_the_extended_lineage():
    proposal = {
        "kind": "training",
        "training_parent": "working",
        "extends_lineage": True,
    }

    assert experiment_family(proposal, "training", [], []) == "lineage.working"
    changes = [{"path": "ppo.learning_rate", "before": 3e-4, "after": 1e-4}]
    assert experiment_family(proposal, "training", changes, []) == (
        "lineage.working+ppo.learning_rate"
    )


def test_continuations_of_different_lineages_are_not_pooled():
    declared = {"kind": "continuation", "family": "training.continuation"}

    assert (
        experiment_family(
            {**declared, "training_parent": "working"}, "continuation", [], []
        )
        == "lineage.working"
    )
    assert (
        experiment_family(
            {**declared, "training_parent": "best_known"}, "continuation", [], []
        )
        == "lineage.best_known"
    )


def test_change_details_prefixes_the_delta_with_the_lineage_operation():
    details = _change_details(
        {
            "kind": "continuation",
            "training_parent": "working",
            "parameter_changes": [
                {"path": "ppo.learning_rate", "before": 3e-4, "after": 1e-4}
            ],
        }
    )

    assert details.startswith("Continue training lineage working; ")
    assert "ppo.learning_rate: 0.0003 → 0.0001" in details


def test_brief_index_renders_extensions_as_one_operation():
    records = [
        {
            "index": 1,
            "kind": "continuation",
            "training_parent": "working",
            "family": "lineage.working",
        },
        {
            "index": 2,
            "kind": "training",
            "training_parent": "working",
            "extends_lineage": True,
            "family": "lineage.working+ppo.learning_rate",
            "change": "lower the learning rate",
        },
    ]

    rows = [
        line
        for line in _v4_experiment_index_section(records)
        if line.startswith(("| 1 |", "| 2 |"))
    ]

    assert len(rows) == 2
    assert all("Continue training lineage working" in row for row in rows)


def test_extension_record_keeps_raw_change_apart_from_the_derived_description(
    monkeypatch, tmp_path
):
    proposal = {
        "kind": "training",
        "hypothesis": "a smaller learning rate refines the parent",
        "change": "lower the learning rate",
        "extends_lineage": True,
        "training_parent": "working",
    }
    result = _production_record(monkeypatch, tmp_path, proposal)

    assert result["researcher_change"] == "lower the learning rate"
    description = operation_description(result)
    assert description == (
        "Continue training lineage checkpoint-100352@1 with a changed recipe: "
        "lower the learning rate"
    )
    assert description.count("lower the learning rate") == 1
    assert result["change"] == description
    # The production path froze the lineage relation and its family.
    assert result["extends_lineage"] is True
    assert result["training_parent_lineage"]["candidate"] == "checkpoint-100352"
    assert result["family"] == "lineage.checkpoint-100352@1"


def test_role_reassignment_does_not_pool_two_different_lineages():
    proposal = {
        "kind": "continuation",
        "family": "training.continuation",
        "training_parent": "working",
    }

    first = experiment_family(
        proposal,
        "continuation",
        [],
        [],
        training_parent_lineage=_frozen_lineage(candidate="checkpoint-100352"),
    )
    second = experiment_family(
        proposal,
        "continuation",
        [],
        [],
        training_parent_lineage=_frozen_lineage(
            candidate="checkpoint-50000", origin_experiment=2
        ),
    )

    assert first == "lineage.checkpoint-100352@1"
    assert second == "lineage.checkpoint-50000@2"
    assert first != second


def test_same_lineage_keeps_identity_after_a_role_reassignment():
    lineage = _frozen_lineage()
    proposal = {
        "kind": "continuation",
        "family": "training.continuation",
        "training_parent": "working",
    }

    as_working = experiment_family(
        proposal,
        "continuation",
        [],
        [],
        training_parent_lineage=lineage,
    )
    reassigned = experiment_family(
        {**proposal, "training_parent": "best_known"},
        "continuation",
        [],
        [],
        training_parent_lineage={**lineage, "identifier": "best_known"},
    )

    assert as_working == reassigned == "lineage.checkpoint-100352@1"


def test_transfer_record_persists_the_recipe_basis(monkeypatch, tmp_path):
    restored = _production_record(
        monkeypatch,
        tmp_path / "continuation",
        {
            "kind": "continuation",
            "hypothesis": "continuing the lineage is sufficient",
            "training_parent": "working",
        },
    )
    current = _production_record(
        monkeypatch,
        tmp_path / "extension",
        {
            "kind": "training",
            "hypothesis": "a smaller learning rate refines the parent",
            "change": "lower the learning rate",
            "extends_lineage": True,
            "training_parent": "working",
        },
    )

    assert restored["recipe_basis"] == "parent_recipe"
    assert current["recipe_basis"] == "current_science"


def test_historical_index_renders_each_transfer_recipe_basis(monkeypatch, tmp_path):
    restored = _production_record(
        monkeypatch,
        tmp_path / "continuation",
        {
            "kind": "continuation",
            "hypothesis": "continuing the lineage is sufficient",
            "training_parent": "working",
        },
        index=1,
    )
    current = _production_record(
        monkeypatch,
        tmp_path / "extension",
        {
            "kind": "training",
            "hypothesis": "a smaller learning rate refines the parent",
            "change": "lower the learning rate",
            "extends_lineage": True,
            "training_parent": "working",
        },
        index=2,
    )

    text = "\n".join(_v4_experiment_index_section([restored, current]))

    assert "the parent's restored recipe" in text
    assert "the current worktree science" in text
