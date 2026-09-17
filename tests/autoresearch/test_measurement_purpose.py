"""Declared measurement purpose and best-known designation provenance.

Audit findings 2 and 3: a new v4 request must declare why each measurement was
requested, only research evaluation can be stopping-validation evidence, and a
designation ordinal distinguishes a new best-known tenure from idempotent
re-designation.
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


def test_new_request_requires_a_declared_purpose():
    with pytest.raises(ValueError, match="requires a purpose"):
        protocol.validate_evaluation_request(_request(), require_purpose=True)
    protocol.validate_evaluation_request(
        _request(purpose="selection"), require_purpose=True
    )


def test_persisted_request_without_purpose_normalizes_to_selection():
    request = _request()
    protocol.normalize_measurement_purposes(request)
    assert request["measurements"][0]["purpose"] == "selection"
    protocol.validate_evaluation_request(request, require_purpose=True)


def test_task_reference_cannot_be_terminal_validation_evidence():
    with pytest.raises(ValueError, match="cannot be terminal-validation"):
        protocol.validate_evaluation_request(
            _request(purpose="terminal_validation", instrument="task_reference"),
            require_purpose=True,
        )


def test_terminal_validation_requires_a_current_designation():
    request = _request(purpose="terminal_validation")
    with pytest.raises(TypeError):
        protocol.validate_terminal_validation_request(request, {})
    with pytest.raises(TypeError):
        protocol.validate_terminal_validation_request(
            request, {"best_known_lineage": {"fingerprint": "f"}}
        )
    protocol.validate_terminal_validation_request(
        request,
        {"best_known_lineage": {"fingerprint": "f", "designation_ordinal": 1}},
    )


def test_designation_ordinal_is_monotonic_and_idempotent():
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
