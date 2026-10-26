"""Focused tests for the external cooperative-stop bridge."""

import asyncio
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from runner import execution, paths, repository, run_experiment
from runner.stop_control import (
    STOP_REQUEST_ENV,
    interrupt_on_stop_request,
    stop_request_path,
    stop_requested,
    wait_for_stop_request,
)


@pytest.mark.parametrize("stop_before_start", [True, False])
def test_launcher_stop_during_runtime_startup_returns_130_without_session(
    tmp_path, stop_before_start
):
    powershell = shutil.which("pwsh")
    if powershell is None:
        pytest.skip("PowerShell 7 is required")
    controller = (
        Path(__file__).resolve().parents[2] / "runner/copilot/copilot_controller.ps1"
    )
    exercise = tmp_path / "startup-stop.ps1"
    exercise.write_text(
        f"""
$ErrorActionPreference = 'Stop'
. '{controller}'
$script:CopilotRepositoryRoot = '{tmp_path}'
$script:StopRequestPath = '{tmp_path / "stop.request"}'
$Model = 'unused'
$Reasoning = 'high'
$script:StopPolls = 0
function Test-CampaignStopRequested {{
    $script:StopPolls += 1
    return ($script:StopPolls -ge {1 if stop_before_start else 2})
}}
function Enter-TrustedMutableInvocation {{}}
function Get-Command {{ [pscustomobject]@{{ Source = '{sys.executable}' }} }}
function Send-CopilotControlMessage {{ throw 'A stopped startup must not submit a session.' }}
try {{
    $code = Invoke-PersistentCopilotSession -SessionArguments @('unused') -Prompt 'unused' -State @{{}}
    if ($code -ne 130) {{ throw "Expected interrupted startup, got $code" }}
    if (${str(stop_before_start).lower()} -and $script:CopilotProcess) {{
        throw 'A pre-existing stop request must not start a runtime.'
    }}
}}
finally {{ Stop-PersistentCopilotRuntime }}
""",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-File", str(exercise)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_stop_request_is_explicit_and_run_scoped(monkeypatch, tmp_path):
    request = tmp_path / "one-run" / "stop.request"
    request.parent.mkdir()
    monkeypatch.setenv(STOP_REQUEST_ENV, str(request))

    assert stop_request_path() == request
    assert not stop_requested()

    request.touch()

    assert stop_requested()


def test_sync_runner_bridge_interrupts_when_request_appears(tmp_path):
    request = tmp_path / "stop.request"
    interrupted = threading.Event()

    with interrupt_on_stop_request(
        request,
        interrupt=interrupted.set,
        poll_seconds=0.005,
    ):
        request.touch()
        assert interrupted.wait(1)


def test_async_researcher_bridge_completes_when_request_appears(tmp_path):
    request = tmp_path / "stop.request"

    async def exercise() -> None:
        waiter = asyncio.create_task(wait_for_stop_request(request))
        await asyncio.sleep(0)
        request.touch()
        await asyncio.wait_for(waiter, timeout=1)

    asyncio.run(exercise())


def test_runner_preserves_an_early_training_interrupt_for_resume(monkeypatch, tmp_path):
    research = tmp_path / "campaigns"
    research.mkdir()
    for name, value in {
        "ROOT": tmp_path,
        "RESEARCH_DIR": research,
        "STATE_PATH": research / "research_state.json",
        "RESULTS_PATH": research / "results.jsonl",
        "LOG_PATH": research / "EXPERIMENTS.md",
        "OPERATION_REQUEST_PATH": research / "operation_request.json",
        "TRAINING_LOG_DIR": research / "training_logs",
        "CANDIDATE_ROOT": tmp_path / "models" / "candidates",
    }.items():
        monkeypatch.setattr(paths, name, value)
    monkeypatch.setattr(repository, "git", lambda *args: "a" * 40 + "\n")
    monkeypatch.setattr(repository, "scientific_delta", lambda _parent: [])
    monkeypatch.setattr(
        repository, "publish_scientific_recipe", lambda *_args: "a" * 40
    )
    monkeypatch.setattr(run_experiment.research_config, "load_experiment_config", dict)
    monkeypatch.setattr(execution, "validate_active_configuration", lambda: None)
    monkeypatch.setattr(
        execution,
        "train_candidate",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt),
    )

    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        last_verdict="fresh",
    )
    state["scientific_model"] = {
        "status": "ready",
        "path": "pi_workspace/scientific_model.md",
        "commit": "a" * 40,
    }
    repository.start_scientific_session(
        state,
        kind="startup",
        objective="Request bounded training evidence.",
        backend_adapter="copilot",
        backend_model="gpt-5.6-luna",
        backend_reasoning="high",
    )
    repository.write_state(state)
    run_experiment.accept_operation(
        {
            "training": {
                "initialization": "fresh",
                "seed": 4,
                "steps": 10,
                "description": "Train the current scientific recipe.",
                "rationale": "Learning dynamics inform the next decision.",
            }
        },
        state,
    )

    assert run_experiment.execute_pending_operation() == 130
    pending = repository.read_state()["pending_operation"]
    assert pending["progress"] == "training_dispatched"
    assert pending["failure"] is None


@pytest.mark.parametrize("mode", ["list", "exit130", "conflict", "missing"])
def test_launcher_restores_the_callers_directory(tmp_path, mode):
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("no PowerShell host to run launcher")
    launcher = Path(__file__).resolve().parents[2] / "run_research.ps1"
    campaign = tmp_path / "campaign"
    (campaign / ".git").mkdir(parents=True)
    caller = tmp_path / "original folder"
    caller.mkdir()
    arguments = {
        "list": "-ListModels",
        "exit130": "-ListModels",
        "conflict": (
            f"-CampaignRoot '{campaign}' -Provider github-copilot "
            "-Model opencode/test-model"
        ),
        "missing": f"-CampaignRoot '{tmp_path / 'missing'}'",
    }[mode]
    exercise = tmp_path / "exercise-launcher-location.ps1"
    exercise.write_text(
        f"""
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath '{caller}'
$before = (Get-Location).Path
function uv {{
    $global:LASTEXITCODE = {130 if mode == "exit130" else 0}
}}
$caught = $false
$exitCode = 0
try {{
    & '{launcher}' {arguments}
    $exitCode = $LASTEXITCODE
}}
catch {{
    $caught = $true
}}
if ((Get-Location).Path -ne $before) {{
    throw "Launcher left the caller in $((Get-Location).Path), expected $before"
}}
if ($caught -ne ${str(mode in {"conflict", "missing"}).lower()}) {{
    throw 'Unexpected launcher failure behavior'
}}
if (-not $caught -and $exitCode -ne {130 if mode == "exit130" else 0}) {{
    throw "Unexpected exit code $exitCode"
}}
""",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-File", str(exercise)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.parametrize("reset_exit_code", [0, 1, 130])
def test_reset_restores_harness_directory_for_chained_launch(tmp_path, reset_exit_code):
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("no PowerShell host to run reset and launcher")
    harness = Path(__file__).resolve().parents[2]
    campaign = tmp_path / "campaign"
    (campaign / ".git").mkdir(parents=True)
    exercise = tmp_path / "exercise-reset-location.ps1"
    exercise.write_text(
        f"""
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath '{harness}'
$global:ResetCalled = $false
$global:LaunchCalled = $false
function uv {{
    if ($args -contains 'runner.reset_campaign') {{
        if ((Get-Location).Path -ne '{campaign}') {{
            throw 'Reset must still execute in the campaign directory'
        }}
        if ($args -notcontains '--clean' -or
            $args -notcontains 'baseline-distinct-episodes-v3') {{
            throw 'Reset arguments were not preserved'
        }}
        $global:ResetCalled = $true
        $global:LASTEXITCODE = {reset_exit_code}
    }}
    else {{
        $global:LaunchCalled = $true
        $global:LASTEXITCODE = 0
    }}
}}
$caught = $false
try {{
    .\\reset_research.ps1 -CampaignRoot '{campaign}' -Mode Fresh -Clean `
        -RecipeRef baseline-distinct-episodes-v3 -Force
}}
catch {{
    if ($_.Exception.Message -notlike 'Research reset failed.*') {{ throw }}
    $caught = $true
}}
if ($caught -ne ${str(reset_exit_code != 0).lower()}) {{
    throw 'Reset exit status was not preserved'
}}
.\\run_research.ps1 -ListModels
if (-not $global:ResetCalled -or -not $global:LaunchCalled) {{
    throw 'The reset-then-launch sequence did not complete'
}}
if ((Get-Location).Path -ne '{harness}') {{
    throw 'The reset-then-launch sequence changed the caller directory'
}}
""",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-File", str(exercise)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_launcher_stop_helper_executes_the_cooperative_exit_contract(tmp_path):
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("no PowerShell host to run launcher helper")
    launcher = Path(__file__).resolve().parents[2] / "run_research.ps1"
    request = tmp_path / "stop.request"
    exercise = tmp_path / "exercise-stop-helper.ps1"
    exercise.write_text(
        f"""
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    '{launcher}', [ref]$null, [ref]$null)
$names = @(
    'Request-CampaignStop',
    'Test-CampaignStopRequested',
    'Test-StopAfterOperation'
)
$definitions = $ast.FindAll({{
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -in $names
}}, $true)
foreach ($definition in $definitions) {{
    . ([scriptblock]::Create($definition.Extent.Text))
}}
function Write-Status {{ param([string]$Message) }}
$StopTimeoutSeconds = 180
$script:StopRequestPath = '{request}'
$script:CampaignStopRequested = $false
$script:CampaignExitCode = 0
if (Test-StopAfterOperation 0 'PI session') {{
    throw 'stop was reported before the request existed'
}}
New-Item -ItemType File -Path $script:StopRequestPath | Out-Null
if (-not (Test-StopAfterOperation 0 'PI session')) {{
    throw 'cooperative exit was not accepted'
}}
if ($script:CampaignExitCode -ne 130) {{
    throw 'cooperative exit did not set campaign exit code 130'
}}
$script:CampaignStopRequested = $false
try {{
    [void](Test-StopAfterOperation 1 'PI session')
    throw 'non-cooperative exit was accepted'
}}
catch {{
    if ($_.Exception.Message -notlike '*instead of completing cooperatively*') {{
        throw
    }}
}}
""",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(exercise),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def test_launcher_does_not_consume_native_console_interrupts():
    source = (Path(__file__).resolve().parents[2] / "run_research.ps1").read_text(
        encoding="utf-8"
    )

    assert "SetConsoleCtrlHandler" not in source
    assert "RobotResearchConsoleInterrupt" not in source
