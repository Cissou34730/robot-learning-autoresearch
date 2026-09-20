"""Issue #50: an adjusted continuation names the lineage it extends.

Continuing a lineage and changing the recipe are independent choices. The
relation is expressed as data - ``extends_lineage`` on a ``training`` proposal
with transfer initialization, or implicitly by ``continuation`` - so the
operation description, the experiment family and the brief keep it visible
whether or not the run carried a parameter delta.
"""

import pytest

from research.build_research_brief import (
    _change_details,
    _v4_experiment_index_section,
)
from research.run_experiment import apply_lineage_extension_fields
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


def _experiment_record(
    *,
    index: int,
    kind: str,
    proposal: dict,
    parent: dict | None,
    recipe_restored: bool = False,
) -> dict:
    """Build a result record through the runner's own field construction."""
    raw_change = proposal.get("change")
    raw_change = raw_change.strip() if isinstance(raw_change, str) else ""
    change = operation_description(proposal)
    result = {
        "index": index,
        "kind": kind,
        "change": change,
        "initialization": "transfer" if parent is not None else "fresh",
        "parameter_changes": [],
        "code_changes": [],
    }
    if raw_change and raw_change != change:
        result["researcher_change"] = raw_change
    apply_lineage_extension_fields(
        result,
        proposal,
        kind,
        parent,
        recipe_restored=recipe_restored,
    )
    return result


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


def test_extension_record_keeps_raw_change_apart_from_the_derived_description():
    proposal = {
        "kind": "training",
        "change": "lower the learning rate",
        "extends_lineage": True,
        "training_parent": "working",
    }
    result = _experiment_record(
        index=3,
        kind="training",
        proposal=proposal,
        parent=_frozen_lineage(),
        recipe_restored=False,
    )

    assert result["researcher_change"] == "lower the learning rate"
    description = operation_description(result)
    assert description == (
        "Continue training lineage checkpoint-100352@1 with a changed recipe: "
        "lower the learning rate"
    )
    assert description.count("lower the learning rate") == 1
    assert result["change"] == description


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


def test_transfer_record_persists_the_recipe_basis():
    parent = _frozen_lineage()
    restored = _experiment_record(
        index=1,
        kind="continuation",
        proposal={"kind": "continuation", "training_parent": "working"},
        parent=parent,
        recipe_restored=True,
    )
    current = _experiment_record(
        index=2,
        kind="training",
        proposal={
            "kind": "training",
            "change": "lower the learning rate",
            "extends_lineage": True,
            "training_parent": "working",
        },
        parent=parent,
        recipe_restored=False,
    )

    assert restored["recipe_basis"] == "parent_recipe"
    assert current["recipe_basis"] == "current_science"


def test_historical_index_renders_each_transfer_recipe_basis():
    parent = _frozen_lineage()
    restored = _experiment_record(
        index=1,
        kind="continuation",
        proposal={"kind": "continuation", "training_parent": "working"},
        parent=parent,
        recipe_restored=True,
    )
    current = _experiment_record(
        index=2,
        kind="training",
        proposal={
            "kind": "training",
            "change": "lower the learning rate",
            "extends_lineage": True,
            "training_parent": "working",
        },
        parent=parent,
        recipe_restored=False,
    )

    text = "\n".join(_v4_experiment_index_section([restored, current]))

    assert "the parent's restored recipe" in text
    assert "the current worktree science" in text
