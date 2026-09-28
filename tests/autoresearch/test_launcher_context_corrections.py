"""Focused behavioral coverage for launcher/context correctness fixes."""

from __future__ import annotations

import builtins
import subprocess
import sys
import types
from pathlib import Path

import pytest

from research import run_experiment
from research import runner_assessment as assessment
from research import runner_protocol as protocol
from research import runner_repository as repository

ROOT = Path(__file__).resolve().parents[2]


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
        backend_adapter="copilot",
        backend_model="gpt-5.6-luna",
        backend_reasoning="high",
    )
    return state


def test_startup_session_persists_backend_identity_and_has_strict_shape(monkeypatch):
    state = _ready_state(monkeypatch)
    session = state["scientific_session"]

    assert session["kind"] == "startup"
    assert session["backend_session_id"] == "backend-session"
    assert session["backend_descriptor"] == {
        "adapter": "copilot",
        "model": "gpt-5.6-luna",
        "reasoning": "high",
    }
    repository.validate_research_state(state, allow_missing_artifact=True)
    missing = {**state, "scientific_session": dict(session)}
    del missing["scientific_session"]["backend_session_id"]
    with pytest.raises(ValueError, match="scientific_session requires exactly"):
        repository.validate_research_state(missing, allow_missing_artifact=True)
    missing = {**state, "scientific_session": dict(session)}
    del missing["scientific_session"]["backend_descriptor"]
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


@pytest.mark.parametrize(
    ("adapter_path", "module_name", "attribute", "invoke"),
    [
        (
            protocol.TASK_REFERENCE_ADAPTER_PATH,
            "robot_learning.scenario.task_reference",
            "task_reference_panel",
            assessment.task_reference_contract,
        ),
        (
            protocol.OFFICIAL_ASSESSMENT_ADAPTER_PATH,
            "robot_learning.scenario.final_benchmark",
            "evaluate_final_model",
            lambda: assessment.evaluate_official_model(Path("model.zip")),
        ),
    ],
)
def test_protected_assessment_establishes_trust_before_scenario_import(
    monkeypatch, adapter_path, module_name, attribute, invoke
):
    events = []
    fake = types.ModuleType(module_name)
    setattr(
        fake,
        attribute,
        (lambda *_args, **_kwargs: {"panel": "trusted"})
        if attribute == "task_reference_panel"
        else (lambda *_args, **_kwargs: {"goal_reached": False}),
    )
    monkeypatch.setitem(sys.modules, module_name, fake)
    monkeypatch.setattr(
        protocol,
        "require_trusted_assessment_runtime",
        lambda path: events.append(("trust", path)),
    )
    original_import = builtins.__import__

    def observed_import(name, *args, **kwargs):
        if name == module_name:
            events.append(("import", name))
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", observed_import)
    invoke()

    assert events[:2] == [("trust", adapter_path), ("import", module_name)]


def test_runner_import_does_not_load_pi_owned_training_or_scenario_code():
    completed = subprocess.run(
        [
            str(ROOT / ".venv" / "Scripts" / "python.exe"),
            "-c",
            (
                "import sys; import research.run_experiment; "
                "blocked=sorted(name for name in sys.modules "
                "if name.startswith(('robot_learning.training', "
                "'robot_learning.scenario'))); "
                "print('\\n'.join(blocked))"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == ""


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
        backend_adapter="copilot",
        backend_model="gpt-5.6-luna",
        backend_reasoning="high",
    )
    with pytest.raises(ValueError, match="does not match persisted"):
        repository.synchronize_max_inquiries(state, 8)
    assert not repository.synchronize_max_inquiries(state, 7)


def test_active_session_backend_descriptor_must_match_until_checkpoint(monkeypatch):
    state = _ready_state(monkeypatch)
    repository.require_scientific_session_backend(
        state,
        adapter="copilot",
        model="gpt-5.6-luna",
        reasoning="high",
    )
    with pytest.raises(ValueError, match="same adapter, model, and reasoning"):
        repository.require_scientific_session_backend(
            state,
            adapter="opencode",
            model="gpt-5.6-luna",
            reasoning="high",
        )
    state["scientific_session"] = None
    repository.require_scientific_session_backend(
        state,
        adapter="opencode",
        model="another-model",
        reasoning="xhigh",
    )


def test_launcher_restart_validation_rejects_backend_descriptor_change(
    monkeypatch, capsys
):
    state = _ready_state(monkeypatch)
    monkeypatch.setattr(repository, "load_state", lambda **_kwargs: state)
    monkeypatch.setattr(repository, "synchronize_max_inquiries", lambda *_args: False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_experiment.py",
            "--synchronize-max-inquiries",
            "15",
            "--backend-adapter",
            "opencode",
            "--backend-model",
            "gpt-5.6-luna",
            "--backend-reasoning",
            "high",
        ],
    )

    with pytest.raises(ValueError, match="same adapter, model, and reasoning"):
        run_experiment.main()

    sys.argv[4] = "copilot"
    assert run_experiment.main() == 0
    output = capsys.readouterr().out
    assert "[campaign] GUARD" in output
    assert "MaxInquiries 15" in output
