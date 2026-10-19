"""Focused behavioral coverage for launcher/context correctness fixes."""

from __future__ import annotations

import builtins
import copy
import subprocess
import sys
import types
from pathlib import Path

import pytest

from runner import assessment, protocol, repository, run_experiment

ROOT = Path(__file__).resolve().parents[2]


def _ready_state(monkeypatch, *, session_kind: str = "startup") -> dict:
    monkeypatch.setattr(repository, "git", lambda *args: "a" * 40 + "\n")
    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        last_verdict="fresh",
    )
    state["scientific_model"] = {
        "status": "ready",
        "path": "pi_workspace/scientific_model.md",
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
        ("inquiry", "campaign_conclusion", "request_official_assessment", False),
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


@pytest.mark.parametrize("transition", ["open", "reframe", "close"])
def test_reported_operation_availability_matches_checkpoint_enforcement(
    monkeypatch, transition
):
    state = _ready_state(
        monkeypatch,
        session_kind="goal_review" if transition == "open" else "inquiry",
    )
    session = state["scientific_session"]
    if transition == "open":
        state["active_inquiry"] = {
            "id": "I1",
            "opened_in_session": session["id"],
            "question": "Current question",
        }
    elif transition == "close":
        state["active_inquiry"] = None
    session["operation_ids"] = ["E1"]
    state["operation_events"] = [
        {
            "id": "E1",
            "kind": "inquiry",
            "status": "completed",
            "result": {"action": transition},
        }
    ]
    availability = protocol.session_operation_availability(state)
    assert availability["allowed_operations"] == ["checkpoint"]
    assert availability["checkpoint_required"] is True
    assert availability["next_question"] == (
        state["active_inquiry"]["question"] if state["active_inquiry"] else None
    )
    protocol._validate_session_operation("checkpoint", {}, state, session)
    with pytest.raises(ValueError, match="requires a checkpoint"):
        protocol._validate_session_operation("measurement", {}, state, session)


def test_operation_availability_stops_at_pending_and_terminal_boundaries(monkeypatch):
    state = _ready_state(monkeypatch, session_kind="goal_review")
    with pytest.raises(ValueError, match="requires an inquiry opened in this session"):
        protocol._validate_session_operation(
            "checkpoint",
            {},
            state,
            state["scientific_session"],
        )
    assert (
        "checkpoint"
        not in protocol.session_operation_availability(state)["allowed_operations"]
    )
    state["pending_operation"] = {"progress": "accepted", "failure": None}
    assert protocol.session_operation_availability(state)["allowed_operations"] == []
    state["pending_operation"]["failure"] = "Execution failed"
    assert (
        "measurement"
        in protocol.session_operation_availability(state)["allowed_operations"]
    )
    state["pending_operation"]["progress"] = "result_ready"
    assert protocol.session_operation_availability(state)["allowed_operations"] == []
    state["pending_operation"] = None
    state["terminal_state"] = {"status": "official_assessment_requested"}
    assert protocol.session_operation_availability(state)["allowed_operations"] == []


def test_launcher_operation_state_mode_reports_facts_without_loading_or_writing_state(
    monkeypatch, capsys
):
    import io
    import json

    state = _ready_state(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["run_experiment.py", "--operation-state-input"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(state)))
    monkeypatch.setattr(
        repository, "load_state", lambda **_kwargs: pytest.fail("Unexpected state load")
    )
    monkeypatch.setattr(
        repository, "write_state", lambda _state: pytest.fail("Unexpected state write")
    )
    assert run_experiment.main() == 0
    assert json.loads(
        capsys.readouterr().out
    ) == protocol.session_operation_availability(state)


@pytest.mark.parametrize("kind", sorted(repository.OPERATION_KINDS))
def test_every_new_operation_rejects_a_human_owned_scientific_delta(monkeypatch, kind):
    state = _ready_state(monkeypatch)
    monkeypatch.setattr(protocol, "validate_operation_request", lambda *_args: kind)
    monkeypatch.setattr(repository, "require_resolvable_commit", lambda _commit: None)
    monkeypatch.setattr(
        repository,
        "scientific_delta",
        lambda _parent: ["runner/run_experiment.py"],
    )

    with pytest.raises(ValueError, match="human-owned"):
        run_experiment.accept_operation({kind: {}}, state)


def test_committed_human_harness_delta_does_not_block_scientific_operation(
    monkeypatch,
):
    state = _ready_state(monkeypatch)
    monkeypatch.setattr(repository, "write_state", lambda _state: None)
    monkeypatch.setattr(
        run_experiment, "_write_accepted_request_handoff", lambda _pending: None
    )
    monkeypatch.setattr(
        repository,
        "committed_change_paths",
        lambda _parent: ["run_research.ps1"],
    )
    monkeypatch.setattr(repository, "status_paths", lambda _scope: [])
    monkeypatch.setattr(run_experiment.research_config, "load_experiment_config", dict)

    pending = run_experiment.accept_operation(
        {
            "training": {
                "initialization": "fresh",
                "seed": 1,
                "steps": 10,
                "description": "Train after a legitimate harness update.",
                "rationale": "The result informs the next goal decision.",
            }
        },
        state,
    )

    assert pending["data"]["scientific_paths"] == []


def test_runner_state_mutation_is_not_a_scientific_delta(monkeypatch):
    monkeypatch.setattr(repository, "committed_change_paths", lambda _parent: [])
    monkeypatch.setattr(
        repository,
        "status_paths",
        lambda _scope: [
            "runner/state/research_state.json",
            "pi_workspace/operation_request.json",
            "runner/run_experiment.py",
        ],
    )

    assert repository.scientific_delta("parent") == ["runner/run_experiment.py"]


def test_uncommitted_human_harness_delta_still_blocks_scientific_operation(
    monkeypatch,
):
    state = _ready_state(monkeypatch)
    monkeypatch.setattr(repository, "write_state", lambda _state: None)
    monkeypatch.setattr(
        run_experiment, "_write_accepted_request_handoff", lambda _pending: None
    )
    monkeypatch.setattr(repository, "committed_change_paths", lambda _parent: [])
    monkeypatch.setattr(
        repository,
        "status_paths",
        lambda _scope: ["run_research.ps1"],
    )
    monkeypatch.setattr(run_experiment.research_config, "load_experiment_config", dict)

    with pytest.raises(ValueError, match="human-owned"):
        run_experiment.accept_operation(
            {
                "training": {
                    "initialization": "fresh",
                    "seed": 1,
                    "steps": 10,
                    "description": "Do not accept dirty harness code.",
                    "rationale": "Ownership must be corrected first.",
                }
            },
            state,
        )


def test_protected_assessment_requires_clean_committed_runtime(monkeypatch):
    monkeypatch.setattr(
        repository,
        "status_paths",
        lambda _scope: ["benchmark/adapters/task_reference.py"],
    )
    with pytest.raises(ValueError, match="uncommitted changes"):
        protocol.require_trusted_assessment_runtime(
            protocol.TASK_REFERENCE_ADAPTER_PATH
        )

    monkeypatch.setattr(repository, "status_paths", lambda _scope: [])
    monkeypatch.setattr(
        repository,
        "tracked_paths",
        lambda _scope: ["benchmark/final_contract.py"],
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
    assert "contracts/policy_runtime.py" in observed[0]
    assert "benchmark/final_contract.py" in observed[0]


@pytest.mark.parametrize(
    ("adapter_path", "module_name", "attribute", "invoke"),
    [
        (
            protocol.TASK_REFERENCE_ADAPTER_PATH,
            "benchmark.adapters.task_reference",
            "task_reference_panel",
            assessment.task_reference_contract,
        ),
        (
            protocol.OFFICIAL_ASSESSMENT_ADAPTER_PATH,
            "benchmark.adapters.final_benchmark",
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
                "import sys; import runner.run_experiment; "
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


def test_maintainer_can_raise_inquiry_cap_only_at_the_paused_boundary(monkeypatch):
    state = _ready_state(monkeypatch, session_kind="goal_review")
    state["scientific_session"] = None
    cap = state["campaign"]["max_inquiries"]
    state["counters"]["inquiry"] = cap
    original = copy.deepcopy(state)

    assert repository.synchronize_max_inquiries(state, cap + 1)
    original["campaign"]["max_inquiries"] = cap + 1
    assert state == original
    assert state["terminal_state"] is None


@pytest.mark.parametrize(
    "active_field",
    ["scientific_session", "active_inquiry", "pending_operation", "terminal_state"],
)
def test_cap_resume_does_not_change_active_or_terminal_campaigns(
    monkeypatch, active_field
):
    state = _ready_state(monkeypatch, session_kind="goal_review")
    state["scientific_session"] = None
    cap = state["campaign"]["max_inquiries"]
    state["counters"]["inquiry"] = cap
    state[active_field] = {"id": "active"}
    original = copy.deepcopy(state)
    with pytest.raises(ValueError, match="does not match persisted"):
        repository.synchronize_max_inquiries(state, cap + 1)
    assert state == original


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
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_experiment.py",
            "--validate-session-backend",
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

    sys.argv[3] = "copilot"
    assert run_experiment.main() == 0
    assert capsys.readouterr().out == ""


def test_relaunch_without_max_inquiries_uses_persisted_value(monkeypatch, capsys):
    state = _ready_state(monkeypatch)
    state["campaign"]["max_inquiries"] = 7
    monkeypatch.setattr(repository, "load_state", lambda **_kwargs: state)
    monkeypatch.setattr(
        repository,
        "synchronize_max_inquiries",
        lambda *_args: pytest.fail("MaxInquiries was synchronized implicitly"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_experiment.py",
            "--validate-session-backend",
            "--backend-adapter",
            "copilot",
            "--backend-model",
            "gpt-5.6-luna",
            "--backend-reasoning",
            "high",
        ],
    )

    assert run_experiment.main() == 0
    assert state["campaign"]["max_inquiries"] == 7
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("response", ["valid", "invalid", "null", "missing", "nonzero"])
def test_launcher_availability_uses_real_process_capture_and_rejects_bad_responses(
    tmp_path, response
):
    import json
    import shutil

    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("no PowerShell host to run launcher helper")
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("no uv executable to run the installed project stack")
    code = {
        "valid": (
            f"import sys; sys.path.insert(0,{str(ROOT)!r}); "
            "print('inert transport warning',file=sys.stderr); "
            "from runner.run_experiment import main; "
            "sys.argv=['runner','--operation-state-input']; raise SystemExit(main())"
        ),
        "invalid": "print('not JSON')",
        "null": "print('null')",
        "missing": "print('{}')",
        "nonzero": "import sys; print('native stderr diagnostic',file=sys.stderr); raise SystemExit(7)",
    }[response]
    encoded = json.dumps(
        {
            "launcher": str(ROOT / "run_research.ps1"),
            "controller": str(ROOT / "runner" / "copilot" / "copilot_controller.ps1"),
            "root": str(ROOT),
            "uv": uv,
            "code": code,
            "response": response,
        }
    ).replace("'", "''")
    exercise = tmp_path / "exercise-availability.ps1"
    exercise.write_text(
        f"""
$ErrorActionPreference = 'Stop'
$values = ConvertFrom-Json -InputObject '{encoded}'
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $values.launcher, [ref]$null, [ref]$null)
$names = @('Invoke-CooperativeProcess', 'Get-RunnerOperationAvailability',
           'Get-RequiredSessionSummaryTransition')
$definitions = $ast.FindAll({{
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -in $names
}}, $true)
foreach ($definition in $definitions) {{
    . ([scriptblock]::Create($definition.Extent.Text))
}}
function Test-CampaignStopRequested {{ return $false }}
function Get-CampaignResourceSummary {{ param($State); return 'inert resources' }}
function Invoke-Runner {{
    param($Arguments, $InputText, [switch]$CaptureOutput)
    return Invoke-CooperativeProcess -FilePath $values.uv -ArgumentList @(
        'run', '--no-sync', '--project', $values.root, 'python', '-c', $values.code
    ) -Operation 'read-only transport check' -InputText $InputText -CaptureOutput
}}
$state = [pscustomobject]@{{
    campaign = [pscustomobject]@{{id='campaign'}}
    scientific_session = [pscustomobject]@{{
        id='S1'; kind='goal_review'; operation_ids=@(); backend_session_id='inert'
    }}
    active_inquiry = [pscustomobject]@{{
        id='I1'; opened_in_session='S1'; question='Current question'
    }}
    pending_operation=$null; terminal_state=$null; operation_events=@(); model_roles=@{{}}
}}
if ($values.response -ne 'valid') {{
    $rejected = $false
    try {{ Get-RunnerOperationAvailability -State $state | Out-Null }}
    catch {{
        $rejected = $true
        if ($values.response -eq 'nonzero' -and
            $_.Exception.Message -notlike '*native stderr diagnostic*') {{
            throw 'Native error detail was lost.'
        }}
    }}
    if (-not $rejected) {{ throw 'Malformed transport response was accepted.' }}
    exit 0
}}
$availability = Get-RunnerOperationAvailability -State $state
if (-not $availability.checkpoint_required -or
    $availability.allowed_operations[0] -ne 'checkpoint') {{
    throw 'Launcher lost the required checkpoint.'
}}
if ($script:ProcessStderr -notlike '*inert transport warning*') {{
    throw 'The real process helper did not capture stderr.'
}}
$transition = Get-RequiredSessionSummaryTransition -State $state -Availability $availability
if (-not $transition) {{ throw 'Required transition disappeared.' }}
. $values.controller
$result = Get-CopilotOperationState -State $state
if (-not $result.checkpoint_required -or
    $result.allowed_operations[0] -ne 'checkpoint' -or
    $result.next_question -ne 'Current question') {{
    throw 'Controller operation state disagrees with Runner.'
}}
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-File", str(exercise)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
