"""Evaluation-request tolerance and best-known designation provenance.

The separate terminal-validation protocol was removed: a request needs no
declared purpose, and a legacy ``purpose`` field is tolerated but ignored and
never required. A designation ordinal still distinguishes a new best-known
tenure from idempotent re-designation.
"""

import pytest

from research import runner_protocol as protocol


def _request(*, purpose: str | None = None, instrument: str = "research_evaluation") -> dict:
    entry: dict = {
        "instrument": instrument,
        "candidate": "candidate",
        "selection": "observed signal",
        "omitted_alternative": None,
    }
    if instrument == "research_evaluation":
        entry.update({"episodes": 10, "seed": 1})
    if purpose is not None:
        entry["purpose"] = purpose
    return {
        "experiment": 1,
        "question": "question",
        "reason": "reason",
        "measurements": [entry],
    }


def test_request_without_purpose_is_accepted():
    protocol.validate_evaluation_request(_request())


def test_legacy_purpose_field_is_tolerated():
    # Historical requests may carry `purpose`; it is accepted and ignored.
    protocol.validate_evaluation_request(_request(purpose="terminal_validation"))
    protocol.validate_evaluation_request(
        _request(purpose="selection", instrument="task_reference")
    )


def _lineage(**overrides) -> dict:
    record = {
        "artifact": "archive/candidate",
        "fingerprint": "f",
        "origin_experiment": 1,
        "candidate": "candidate",
        "parameters": {},
        "scientific_commit": "base",
        "training_steps": 100,
        "evaluation_artifacts": [],
        "reason": "measured best",
    }
    record.update(overrides)
    return record


def test_designation_ordinal_is_a_valid_optional_lineage_field():
    from research import runner_repository as repository

    with_ordinal = _lineage(designation_ordinal=1)
    repository.canonicalize_lineage_record(with_ordinal)
    assert with_ordinal["designation_ordinal"] == 1

    # Existing records without the field remain valid.
    repository.canonicalize_lineage_record(_lineage())

    with pytest.raises(ValueError):
        repository.canonicalize_lineage_record(_lineage(designation_ordinal=0))
    with pytest.raises(TypeError):
        repository.canonicalize_lineage_record(_lineage(designation_ordinal="1"))


def test_designation_counter_is_monotonic_and_idempotent():
    assert protocol.next_designation_ordinal(None, "a", 0) == 1
    assert (
        protocol.next_designation_ordinal(
            {"fingerprint": "a", "designation_ordinal": 1}, "a", 1
        )
        == 1
    )
    assert (
        protocol.next_designation_ordinal(
            {"fingerprint": "a", "designation_ordinal": 1}, "b", 1
        )
        == 2
    )
    # Returning to a previously designated fingerprint starts a new tenure.
    assert (
        protocol.next_designation_ordinal(
            {"fingerprint": "b", "designation_ordinal": 2}, "a", 2
        )
        == 3
    )


def test_designation_counter_falls_back_to_the_current_ordinal():
    assert (
        protocol.designation_counter_for(
            {"best_known_lineage": {"fingerprint": "f", "designation_ordinal": 3}}
        )
        == 3
    )
    assert (
        protocol.designation_counter_for(
            {
                "best_known_lineage": {"fingerprint": "f", "designation_ordinal": 3},
                "best_known_designation_counter": 5,
            }
        )
        == 5
    )
    assert protocol.designation_counter_for({}) == 0


def test_closure_serialization_preserves_the_designation_counter():
    from research import run_experiment

    plan = {
        "pending": {},
        "decision": {},
        "working_name": "working",
        "working_record": {},
        "best_known_record": None,
        "best_known_name": None,
        "code_action": "keep",
        "code_reason": "reason",
        "code_plan": {"parent": None, "restore": [], "remove_created": []},
        "retained": [],
        "removed_retained": [],
        "artifact_publications": [],
        "request_final_benchmark": False,
        "hypothesis_assessment": None,
        "designation_counter": 4,
    }
    serialized = run_experiment._serialize_closure_plan(
        plan, pending_field="pending_analysis"
    )
    assert serialized["designation_counter"] == 4
