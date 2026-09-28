"""Focused behavioral coverage for launcher/context correctness fixes."""

from __future__ import annotations

import pytest

from research import run_experiment
from research import runner_protocol as protocol
from research import runner_repository as repository


def _ready_state(monkeypatch, *, session_kind: str = "startup") -> dict:
    monkeypatch.setattr(repository, "git", lambda *args: "a" * 40 + "\n")
    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        last_verdict="fresh",
    )
    state["scientific_model"] = {
        "status": "ready",
        "path": "research/scientific_model.md",
        "commit": "a" * 40,
    }
    if session_kind == "inquiry":
        state["active_inquiry"] = {
            "id": "I1",
            "question": "Question",
            "goal_connection": "Connection",
            "closure_condition": "Closure",
            "rationale": "Rationale",
            "opened_in_session": "S0",
            "reframes": [],
        }
    repository.start_scientific_session(
        state,
        kind=session_kind,
        objective="Make one bounded decision.",
        backend_session_id="backend-session",
    )
    return state


def test_startup_session_persists_backend_identity_and_has_strict_shape(monkeypatch):
    state = _ready_state(monkeypatch)
    session = state["scientific_session"]

    assert session["kind"] == "startup"
    assert session["backend_session_id"] == "backend-session"
    repository.validate_research_state(state, allow_missing_artifact=True)
    missing = {**state, "scientific_session": dict(session)}
    del missing["scientific_session"]["backend_session_id"]
    with pytest.raises(ValueError, match="scientific_session requires exactly"):
        repository.validate_research_state(missing, allow_missing_artifact=True)
    session["unexpected"] = True
    with pytest.raises(ValueError, match="scientific_session requires exactly"):
        repository.validate_research_state(state, allow_missing_artifact=True)


@pytest.mark.parametrize(
    ("session_kind", "kind", "action", "allowed"),
    [
        ("startup", "training", None, True),
        ("startup", "inquiry", "open", False),
        ("goal_review", "inquiry", "open", True),
        ("goal_review", "training", None, False),
        ("inquiry", "measurement", None, True),
        ("inquiry", "inquiry", "reframe", True),
        ("inquiry", "inquiry", "open", False),
        ("inquiry", "campaign_conclusion", "no_credible_route", False),
    ],
)
def test_scientific_session_operation_matrix_is_explicit(
    monkeypatch, session_kind, kind, action, allowed
):
    state = _ready_state(monkeypatch, session_kind=session_kind)
    request = {} if action is None else {"action": action}
    session = state["scientific_session"]

    if allowed:
        protocol._validate_session_operation(kind, request, state, session)
    else:
        with pytest.raises(ValueError, match="not available|may only"):
            protocol._validate_session_operation(kind, request, state, session)


def test_inquiry_reframe_forces_checkpoint_before_more_work(monkeypatch):
    state = _ready_state(monkeypatch, session_kind="inquiry")
    session = state["scientific_session"]
    session["operation_ids"] = ["E1"]
    state["operation_events"] = [
        {
            "id": "E1",
            "kind": "inquiry",
            "result": {"action": "reframe"},
        }
    ]

    with pytest.raises(ValueError, match="requires a checkpoint"):
        protocol._validate_session_operation("measurement", {}, state, session)
    protocol._validate_session_operation("checkpoint", {}, state, session)


@pytest.mark.parametrize("kind", sorted(repository.OPERATION_KINDS))
def test_every_new_operation_rejects_a_human_owned_scientific_delta(monkeypatch, kind):
    state = _ready_state(monkeypatch)
    monkeypatch.setattr(protocol, "validate_operation_request", lambda *_args: kind)
    monkeypatch.setattr(repository, "require_resolvable_commit", lambda _commit: None)
    monkeypatch.setattr(
        repository,
        "scientific_delta",
        lambda _parent: ["research/run_experiment.py"],
    )

    with pytest.raises(ValueError, match="human-owned"):
        run_experiment.accept_operation({kind: {}}, state)


def test_protected_assessment_requires_clean_committed_runtime(monkeypatch):
    monkeypatch.setattr(
        repository,
        "status_paths",
        lambda _scope: ["robot_learning/scenario/task_reference.py"],
    )
    with pytest.raises(ValueError, match="uncommitted changes"):
        protocol.require_trusted_assessment_runtime(
            protocol.TASK_REFERENCE_ADAPTER_PATH
        )

    monkeypatch.setattr(repository, "status_paths", lambda _scope: [])
    monkeypatch.setattr(
        repository,
        "tracked_paths",
        lambda _scope: ["robot_learning/benchmark/final_contract.py"],
    )
    observed: list[list[str]] = []
    monkeypatch.setattr(
        repository,
        "require_paths_at_head",
        lambda paths: observed.append(paths),
    )
    protocol.require_trusted_assessment_runtime(
        protocol.OFFICIAL_ASSESSMENT_ADAPTER_PATH
    )
    assert protocol.OFFICIAL_ASSESSMENT_ADAPTER_PATH in observed[0]
    assert "robot_learning/policy_runtime.py" in observed[0]
    assert "robot_learning/benchmark/final_contract.py" in observed[0]


def test_max_inquiries_changes_only_during_fresh_or_startup_initialization(monkeypatch):
    state = _ready_state(monkeypatch)
    state["scientific_session"] = None
    state["counters"]["session"] = 0
    assert repository.synchronize_max_inquiries(state, 7)
    assert state["campaign"]["max_inquiries"] == 7

    repository.start_scientific_session(
        state,
        kind="startup",
        objective="Initial scientific design.",
        backend_session_id="backend-session",
    )
    with pytest.raises(ValueError, match="does not match persisted"):
        repository.synchronize_max_inquiries(state, 8)
    assert not repository.synchronize_max_inquiries(state, 7)
