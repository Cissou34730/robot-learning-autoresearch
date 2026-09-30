"""Launcher and prompt contracts for the strict schema-6 lifecycle."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from research import reset_campaign, run_experiment, runner_paths, runner_protocol
from research import runner_repository as repository

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "run_research.ps1"
TRUST_SCRIPT_PATH = ROOT / "researcher_session.ps1"
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
powershell_only = pytest.mark.skipif(
    POWERSHELL is None, reason="no PowerShell host to run launcher functions"
)


def _scientific_model_registers_valid(tmp_path: Path, content: str) -> bool:
    content_path = tmp_path / "model.md"
    content_path.write_text(content, encoding="utf-8")
    script = tmp_path / "model-registers.ps1"
    script.write_text(
        f"""
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    '{SCRIPT_PATH}', [ref]$null, [ref]$null)
$definition = $ast.FindAll({{
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq 'Test-ScientificModelRegisters'
}}, $true) | Select-Object -First 1
. ([scriptblock]::Create($definition.Extent.Text))
$content = Get-Content -Raw '{content_path}'
if (Test-ScientificModelRegisters -Content $content) {{ exit 0 }} else {{ exit 1 }}
""",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode == 0


def _run_launcher_trust_script(
    tmp_path: Path, body: str
) -> subprocess.CompletedProcess:
    script = tmp_path / "trust-gate.ps1"
    script.write_text(
        f"""
. '{TRUST_SCRIPT_PATH}'
{body}
""",
        encoding="utf-8",
    )
    return subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


@powershell_only
def test_redirected_status_lines_are_one_write_each(tmp_path):
    script = tmp_path / "status-write-probe.ps1"
    script.write_text(
        f"""
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    '{TRUST_SCRIPT_PATH}', [ref]$null, [ref]$null)
$definition = $ast.FindAll({{
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq 'Write-Status'
}}, $true) | Select-Object -First 1
. ([scriptblock]::Create($definition.Extent.Text))
$script:writes = @()
function global:Write-Host {{
    param(
        [Parameter(Position=0, ValueFromRemainingArguments=$true)][object[]]$Object,
        [ConsoleColor]$ForegroundColor,
        [switch]$NoNewline
    )
    $script:writes += [pscustomobject]@{{
        text = ($Object -join ' ')
        no_newline = [bool]$NoNewline
    }}
}}
Write-Status -Message (('boundary prose ' * 60).Trim()) `
    -Color Magenta -Label session
$script:writes | ConvertTo-Json -Compress
""",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    writes = json.loads(completed.stdout)
    if isinstance(writes, dict):
        writes = [writes]
    assert len(writes) == 1
    assert not writes[0]["no_newline"]
    assert writes[0]["text"].startswith("[")
    assert "[session]" in writes[0]["text"]
    assert "\r" not in writes[0]["text"]
    assert "\n" not in writes[0]["text"]
    assert "  " not in writes[0]["text"]


def _trust_test_repository(path: Path) -> None:
    (path / "research" / "evaluations" / "campaign").mkdir(parents=True)
    (path / "robot_learning" / "scenario").mkdir(parents=True)
    (path / "robot_learning" / "training").mkdir(parents=True)
    (path / "docs").mkdir()
    (path / "run_research.ps1").write_text("# trusted launcher\n", encoding="utf-8")
    (path / "robot_learning" / "scenario" / "final_benchmark.py").write_text(
        "VALUE = 'protected'\n", encoding="utf-8"
    )
    (path / "research" / "research_state.json").write_text(
        '{"status":"initial"}\n', encoding="utf-8"
    )
    (path / "robot_learning" / "training" / "algorithm.py").write_text(
        "VALUE = 1\n", encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "-c",
            "user.name=Tests",
            "-c",
            "user.email=tests@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    (path / "docs" / "untracked-plan.md").write_text(
        "preserve this plan\n", encoding="utf-8"
    )
    (path / "research" / "research_state.json").write_text(
        '{"status":"stopped"}\n', encoding="utf-8"
    )
    (path / "research" / "evaluations" / "campaign" / "interrupted.json").write_text(
        '{"completed":false}\n', encoding="utf-8"
    )


@powershell_only
def test_scientific_model_requires_three_substantive_registers(tmp_path):
    valid = """
# Scientific model

## Established facts
The robot has two actuated joints.

## Physical consequences
The coupled links constrain reachable poses.

## Unknowns
Closed-loop settling behavior is not established.
"""
    assert _scientific_model_registers_valid(tmp_path, valid)
    assert not _scientific_model_registers_valid(
        tmp_path,
        valid.replace(
            "The coupled links constrain reachable poses.",
            "",
        ),
    )


@powershell_only
def test_launcher_trust_gate_allows_only_the_documented_pi_surface(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _trust_test_repository(root)
    quoted_root = str(root).replace("'", "''")
    completed = _run_launcher_trust_script(
        tmp_path,
        f"""
$root = '{quoted_root}'
$snapshot = New-PITrustSnapshot -Root $root
Set-Content -LiteralPath (Join-Path $root 'robot_learning\\training\\algorithm.py') `
    -Value 'VALUE = 2'
Set-Content -LiteralPath (Join-Path $root 'research\\operation_request.json') `
    -Value '{{"checkpoint": {{}}}}'
Assert-PITrustSnapshot -Snapshot $snapshot -Root $root
""",
    )
    assert completed.returncode == 0, completed.stderr
    assert (root / "docs" / "untracked-plan.md").read_text(
        encoding="utf-8"
    ) == "preserve this plan\n"
    assert (root / "research" / "research_state.json").read_text(
        encoding="utf-8"
    ) == '{"status":"stopped"}\n'
    assert (
        root / "research" / "evaluations" / "campaign" / "interrupted.json"
    ).read_text(encoding="utf-8") == '{"completed":false}\n'


@powershell_only
@pytest.mark.parametrize(
    "relative",
    [
        "run_research.ps1",
        "robot_learning/scenario/final_benchmark.py",
        "docs/untracked-plan.md",
    ],
)
def test_launcher_trust_snapshot_rejects_protected_file_modification(
    tmp_path, relative
):
    root = tmp_path / "repo"
    root.mkdir()
    _trust_test_repository(root)
    quoted_root = str(root).replace("'", "''")
    quoted_relative = relative.replace("/", "\\")
    completed = _run_launcher_trust_script(
        tmp_path,
        f"""
$root = '{quoted_root}'
$snapshot = New-PITrustSnapshot -Root $root
Add-Content -LiteralPath (Join-Path $root '{quoted_relative}') -Value 'PI mutation'
Assert-PITrustSnapshot -Snapshot $snapshot -Root $root
""",
    )
    assert completed.returncode != 0
    assert relative in completed.stderr


@powershell_only
def test_launcher_trust_snapshot_ignores_assume_unchanged_index_mask(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _trust_test_repository(root)
    quoted_root = str(root).replace("'", "''")
    completed = _run_launcher_trust_script(
        tmp_path,
        f"""
$root = '{quoted_root}'
$snapshot = New-PITrustSnapshot -Root $root
& git -C $root update-index --assume-unchanged run_research.ps1
Add-Content -LiteralPath (Join-Path $root 'run_research.ps1') -Value 'hidden mutation'
Assert-PITrustSnapshot -Snapshot $snapshot -Root $root
""",
    )
    assert completed.returncode != 0
    assert "run_research.ps1" in completed.stderr


@powershell_only
def test_launcher_trust_snapshot_rejects_protected_commit_and_head_change(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _trust_test_repository(root)
    quoted_root = str(root).replace("'", "''")
    completed = _run_launcher_trust_script(
        tmp_path,
        f"""
$root = '{quoted_root}'
$snapshot = New-PITrustSnapshot -Root $root
Add-Content -LiteralPath (Join-Path $root 'run_research.ps1') -Value 'committed mutation'
& git -C $root add run_research.ps1
& git -C $root -c user.name=Tests -c user.email=tests@example.invalid `
    commit -qm 'untrusted protected commit'
Assert-PITrustSnapshot -Snapshot $snapshot -Root $root
""",
    )
    assert completed.returncode != 0
    assert "HEAD" in completed.stderr
    assert "run_research.ps1" in completed.stderr


@powershell_only
def test_launcher_trust_snapshot_rejects_added_non_pi_file(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _trust_test_repository(root)
    quoted_root = str(root).replace("'", "''")
    completed = _run_launcher_trust_script(
        tmp_path,
        f"""
$root = '{quoted_root}'
$snapshot = New-PITrustSnapshot -Root $root
Set-Content -LiteralPath (Join-Path $root 'docs\\new-plan.md') -Value 'new'
Assert-PITrustSnapshot -Snapshot $snapshot -Root $root
""",
    )
    assert completed.returncode != 0
    assert "docs/new-plan.md" in completed.stderr


@powershell_only
def test_launcher_trust_snapshot_rejects_deleted_non_pi_file(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _trust_test_repository(root)
    quoted_root = str(root).replace("'", "''")
    completed = _run_launcher_trust_script(
        tmp_path,
        f"""
$root = '{quoted_root}'
$snapshot = New-PITrustSnapshot -Root $root
Remove-Item -LiteralPath (Join-Path $root 'docs\\untracked-plan.md')
Assert-PITrustSnapshot -Snapshot $snapshot -Root $root
""",
    )
    assert completed.returncode != 0
    assert "docs/untracked-plan.md" in completed.stderr


@powershell_only
def test_launcher_trust_snapshot_allows_pi_edit_and_generated_request(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _trust_test_repository(root)
    quoted_root = str(root).replace("'", "''")
    completed = _run_launcher_trust_script(
        tmp_path,
        f"""
$root = '{quoted_root}'
$snapshot = New-PITrustSnapshot -Root $root
Set-Content -LiteralPath (Join-Path $root 'robot_learning\\training\\algorithm.py') `
    -Value 'VALUE = 2'
Set-Content -LiteralPath (Join-Path $root 'research\\operation_request.json') `
    -Value '{{"checkpoint": {{}}}}'
Assert-PITrustSnapshot -Snapshot $snapshot -Root $root
""",
    )
    assert completed.returncode == 0, completed.stderr


@powershell_only
def test_preliminary_snapshot_allows_only_scientific_model_handoff(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _trust_test_repository(root)
    model = root / "research" / "scientific_model.md"
    model.write_text("initial model\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(root), "add", "research/scientific_model.md"], check=True
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Tests",
            "-c",
            "user.email=tests@example.invalid",
            "commit",
            "-qm",
            "add scientific model",
        ],
        check=True,
    )
    quoted_root = str(root).replace("'", "''")
    completed = _run_launcher_trust_script(
        tmp_path,
        f"""
$root = '{quoted_root}'
$snapshot = New-PITrustSnapshot -Root $root -Preliminary
Set-Content -LiteralPath (Join-Path $root 'research\\scientific_model.md') `
    -Value 'updated model'
Assert-PITrustSnapshot -Snapshot $snapshot -Root $root
Set-Content -LiteralPath (Join-Path $root 'research\\operation_request.json') `
    -Value '{{"checkpoint": {{}}}}'
Assert-PITrustSnapshot -Snapshot $snapshot -Root $root
""",
    )
    assert completed.returncode != 0
    assert "research/operation_request.json" in completed.stderr


@powershell_only
def test_launcher_trust_snapshot_refresh_accepts_trusted_runner_commit(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _trust_test_repository(root)
    quoted_root = str(root).replace("'", "''")
    completed = _run_launcher_trust_script(
        tmp_path,
        f"""
$root = '{quoted_root}'
$snapshot = New-PITrustSnapshot -Root $root
Set-Content -LiteralPath (Join-Path $root 'research\\research_state.json') `
    -Value '{{"status":"trusted"}}'
& git -C $root add research/research_state.json
& git -C $root -c user.name=Tests -c user.email=tests@example.invalid `
    commit -qm 'trusted runner state'
try {{
    Assert-PITrustSnapshot -Snapshot $snapshot -Root $root
    throw 'old snapshot unexpectedly accepted the new HEAD'
}}
catch {{
    if ($_.Exception.Message -notlike '*HEAD*') {{ throw }}
}}
$snapshot = New-PITrustSnapshot -Root $root
Assert-PITrustSnapshot -Snapshot $snapshot -Root $root
""",
    )
    assert completed.returncode == 0, completed.stderr


@powershell_only
def test_failed_runner_exit_refreshes_snapshot_after_trusted_publication(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _trust_test_repository(root)
    quoted_root = str(root).replace("'", "''")
    completed = _run_launcher_trust_script(
        tmp_path,
        f"""
$root = '{quoted_root}'
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    '{SCRIPT_PATH}', [ref]$null, [ref]$null)
$names = @('Enter-TrustedMutableInvocation', 'Invoke-Runner')
$definitions = $ast.FindAll({{
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -in $names
}}, $true)
foreach ($definition in $definitions) {{
    . ([scriptblock]::Create($definition.Extent.Text))
}}
$script:PITrustPreliminary = $false
$script:PublishedBeforeFailure = $false
Remove-Item Function:\\New-PITrustSnapshot
function New-PITrustSnapshot {{
    param([switch]$Preliminary)
    [pscustomobject]@{{
        PublishedBeforeFailure = $script:PublishedBeforeFailure
        Preliminary = [bool]$Preliminary
    }}
}}
$script:PITrustSnapshot = New-PITrustSnapshot
function Get-Command {{
    [pscustomobject]@{{ Source = 'uv.exe' }}
}}
function Invoke-CooperativeProcess {{
    Set-Content -LiteralPath (Join-Path $root 'research\\research_state.json') `
        -Value '{{"status":"published-before-failure"}}'
    & git -C $root add research/research_state.json
    & git -C $root -c user.name=Tests -c user.email=tests@example.invalid `
        commit -qm 'trusted publication before failure'
    $script:PublishedBeforeFailure = $true
    return 1
}}
Push-Location $root
try {{
    $exitCode = Invoke-Runner
    if ($exitCode -ne 1) {{ throw "Runner exit status was not preserved." }}
    if (-not $script:PITrustSnapshot.PublishedBeforeFailure) {{
        throw "Runner trust snapshot was not refreshed after the failed exit."
    }}
}}
finally {{
    Pop-Location
}}
""",
    )
    assert completed.returncode == 0, completed.stderr


@powershell_only
@pytest.mark.parametrize("progress", ["result_ready", "completed"])
def test_pending_publication_failure_stops_without_pi_repair(tmp_path, progress):
    root = tmp_path / "repo"
    (root / "research").mkdir(parents=True)
    operation_id = f"T-{uuid4().hex}"
    state = {
        "pending_operation": {
            "id": operation_id,
            "progress": progress,
            "failure": None,
        }
    }
    (root / "research" / "research_state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )
    completed = _run_launcher_trust_script(
        tmp_path,
        f"""
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    '{SCRIPT_PATH}', [ref]$null, [ref]$null)
$definitions = $ast.FindAll({{
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -in @('Stop-OnPublicationFailure', 'Invoke-PendingOperation')
}}, $true)
foreach ($definition in $definitions) {{
    . ([scriptblock]::Create($definition.Extent.Text))
}}
$script:runnerCalls = 0
$script:piCalls = 0
function Invoke-Runner {{
    param($Arguments)
    $script:runnerCalls += 1
    return 1
}}
function Invoke-PISession {{
    $script:piCalls += 1
    throw 'Scientific repair must not run for publication failures.'
}}
function Test-StopAfterOperation {{ return $false }}
Push-Location '{root}'
try {{
    $state = Get-Content 'research\\research_state.json' -Raw | ConvertFrom-Json
    try {{
        [void](Invoke-PendingOperation -State $state)
        $stopped = $false
        $message = ''
    }}
    catch {{
        $stopped = $true
        $message = $_.Exception.Message
    }}
    [pscustomobject]@{{
        stopped = $stopped
        message = $message
        runner_calls = $script:runnerCalls
        pi_calls = $script:piCalls
    }} | ConvertTo-Json -Compress
}}
finally {{ Pop-Location }}
""",
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["stopped"]
    assert operation_id in result["message"]
    assert result["runner_calls"] == 1
    assert result["pi_calls"] == 0
    assert (
        json.loads(
            (root / "research" / "research_state.json").read_text(encoding="utf-8")
        )
        == state
    )


@powershell_only
@pytest.mark.parametrize("progress", [None, "training_dispatched"])
def test_publication_failure_guard_preserves_other_recovery_routes(tmp_path, progress):
    pending = (
        {"id": "T1", "progress": progress, "failure": "execution error"}
        if progress is not None
        else None
    )
    state_json = json.dumps({"pending_operation": pending})
    completed = _run_launcher_trust_script(
        tmp_path,
        f"""
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    '{SCRIPT_PATH}', [ref]$null, [ref]$null)
$definition = $ast.FindAll({{
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq 'Stop-OnPublicationFailure'
}}, $true) | Select-Object -First 1
. ([scriptblock]::Create($definition.Extent.Text))
$state = '{state_json}' | ConvertFrom-Json
Stop-OnPublicationFailure -State $state
""",
    )
    assert completed.returncode == 0, completed.stderr


def test_schema6_state_and_model_are_the_only_fresh_start_contract():
    assert "research/operation_request.json" in reset_campaign.CAMPAIGN_PATHS
    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        last_verdict="fresh",
    )
    assert state["schema_version"] == 6
    assert set(state) == repository.STATE_FIELDS
    assert state["scientific_model"]["status"] == "pending"
    assert state["active_inquiry"] is None
    assert state["pi_checkpoint"] is None
    assert state["scientific_session"] is None


def test_scientific_model_and_request_paths_remain_protected():
    assert runner_protocol.is_protected_source("research/scientific_model.md")
    assert not runner_protocol.is_researcher_owned("research/scientific_model.md")
    assert repository.is_runner_owned("research/operation_request.json")


@powershell_only
@pytest.mark.parametrize("kind", ["startup", "goal_review", "inquiry"])
def test_scientific_session_prompt_preserves_checkpoint_frontier(tmp_path, kind):
    markers = {
        name: f"{name}-{uuid4().hex}"
        for name in ("goal", "synthesis", "gap", "frontier", "objective")
    }
    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        last_verdict="fresh",
    )
    state["human_goal"]["summary"] = markers["goal"]
    state["scientific_session"] = {
        "id": "S1",
        "kind": kind,
        "objective": markers["objective"],
        "operation_ids": [],
    }
    if kind != "startup":
        state["pi_checkpoint"] = {
            "inquiry_id": None,
            "human_goal_connection": markers["goal"],
            "current_goal_gap": markers["gap"],
            "current_synthesis": markers["synthesis"],
            "evidence_references": [],
            "decision_frontier": markers["frontier"],
            "completed_operations": [],
            "candidates_and_roles": "No roles assigned.",
            "next_direction_or_closure": "Choose the next scientific action.",
            "cumulative_resource_use": "No completed operations.",
        }
    if kind == "inquiry":
        state["active_inquiry"] = {
            "id": "I1",
            "question": "Resolve a consequential uncertainty.",
            "goal_connection": markers["goal"],
            "closure_condition": "Establish the answer's bearing on the next decision.",
            "opened_in_session": "S0",
        }
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    script = tmp_path / "session-context.ps1"
    script.write_text(
        f"""
$ErrorActionPreference = 'Stop'
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    '{SCRIPT_PATH}', [ref]$null, [ref]$null)
$names = @(
    'Get-HumanGoalSummary', 'Get-LatestSessionResult',
    'Get-RequiredSessionSummaryTransition', 'New-ScientificSessionPrompt'
)
foreach ($name in $names) {{
    $definition = $ast.FindAll({{
        param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
            $node.Name -eq $name
    }}, $true) | Select-Object -First 1
    if (-not $definition) {{ throw "Missing launcher function $name" }}
    . ([scriptblock]::Create($definition.Extent.Text))
}}
$state = Get-Content -Raw -LiteralPath '{state_path}' | ConvertFrom-Json
New-ScientificSessionPrompt -State $state
""",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert markers["goal"] in completed.stdout
    assert markers["objective"] in completed.stdout
    if state["pi_checkpoint"] is not None:
        assert markers["synthesis"] in completed.stdout
        assert markers["gap"] in completed.stdout
        assert markers["frontier"] in completed.stdout
    assert not runner_protocol.is_researcher_owned("research/operation_request.json")


def _goal_review_candidate(
    monkeypatch, tmp_path: Path, *, at_cap: bool = True
) -> tuple[dict, dict]:
    research = tmp_path / "research"
    research.mkdir()
    for name, value in {
        "ROOT": tmp_path,
        "RESEARCH_DIR": research,
        "STATE_PATH": research / "research_state.json",
        "RESULTS_PATH": research / "results.jsonl",
        "LOG_PATH": research / "EXPERIMENTS.md",
        "OPERATION_REQUEST_PATH": research / "operation_request.json",
    }.items():
        monkeypatch.setattr(runner_paths, name, value)
    monkeypatch.setattr(
        runner_paths,
        "campaign_retained_root",
        lambda campaign_id: research / "checkpoints" / "retained" / campaign_id,
    )
    monkeypatch.setattr(repository, "git", lambda *args: "a" * 40 + "\n")
    monkeypatch.setattr(repository, "scientific_delta", lambda _parent: [])
    monkeypatch.setattr(repository, "campaign_lab_manifest", list)
    monkeypatch.setattr(
        repository, "publish_scientific_recipe", lambda *_args: "a" * 40
    )
    monkeypatch.setattr(
        runner_protocol, "require_trusted_assessment_runtime", lambda _path: None
    )
    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        last_verdict="fresh",
    )
    state["scientific_model"] = {
        "status": "ready",
        "path": "research/scientific_model.md",
        "commit": "a" * 40,
    }
    if at_cap:
        state["counters"]["inquiry"] = state["campaign"]["max_inquiries"]
    repository.start_scientific_session(
        state,
        kind="goal_review",
        objective="Choose the campaign decision from completed evidence.",
        backend_adapter="copilot",
        backend_model="gpt-5.6-luna",
        backend_reasoning="high",
    )
    artifact = tmp_path / "archive" / "candidate"
    artifact.mkdir(parents=True)
    (artifact / "model.zip").write_bytes(b"model")
    (artifact / "artifact.json").write_text("{}", encoding="utf-8")
    (artifact / "policy_runtime.pkl").write_bytes(b"runtime")
    candidate = {
        "id": "T1:checkpoint-10",
        "artifact": repository.repo_relative_path(artifact),
        "fingerprint": repository.artifact_fingerprint(artifact),
        "origin_operation": "T1",
        "name": "checkpoint-10",
        "parameters": {},
        "scientific_commit": "b" * 40,
        "training_steps": 10,
        "evaluation_artifacts": [],
    }
    state["candidates"][candidate["id"]] = candidate
    evidence = research / "evaluations" / "campaign" / "evidence.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text("{}", encoding="utf-8")
    state["operation_events"].append(
        {
            "id": "M1",
            "kind": "measurement",
            "session_id": "S0",
            "inquiry_id": None,
            "request": {
                "description": "Measure the available candidate.",
                "rationale": "Support a model-role decision.",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": candidate["id"],
                        "episodes": 1,
                        "seed": 1,
                    }
                ],
            },
            "result": {
                "status": "completed",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": candidate["id"],
                        "candidate_id": candidate["id"],
                        "label": "recorded evidence",
                        "metrics": {
                            "episodes": 1,
                            "successes": 0,
                            "success_percent": 0.0,
                            "evaluation_artifact": repository.repo_relative_path(
                                evidence
                            ),
                            "evaluation_artifact_fingerprint": hashlib.sha256(
                                evidence.read_bytes()
                            ).hexdigest(),
                            "model_fingerprint": candidate["fingerprint"],
                        },
                    }
                ],
                "paired_comparisons": [],
                "tool_provenance": None,
            },
            "status": "completed",
            "error": None,
            "supersedes": None,
            "superseded_by": None,
            "completed_at": "now",
        }
    )
    repository.write_state(state)
    return state, candidate


def _best_known_request(candidate: dict) -> dict:
    return {
        "model_role": {
            "action": "set_best_known",
            "candidate": candidate["id"],
            "reason": "Select the strongest available evidence-backed candidate.",
            "evidence": ["M1"],
        }
    }


def _open_inquiry_request() -> dict:
    return {
        "inquiry": {
            "action": "open",
            "question": "Which method addresses the remaining uncertainty?",
            "goal_connection": "The answer determines the next campaign direction.",
            "closure_condition": "Resolve the method decision.",
            "rationale": "The current evidence leaves a consequential uncertainty.",
        }
    }


def test_goal_review_assigns_best_known_and_requests_assessment_at_cap(
    monkeypatch, tmp_path
):
    state, candidate = _goal_review_candidate(monkeypatch, tmp_path)
    assessment = {
        "campaign_conclusion": {
            "action": "request_official_assessment",
            "reason": "The PI chooses to assess its explicitly selected candidate.",
        }
    }
    with pytest.raises(ValueError, match="best-known"):
        runner_protocol.validate_operation_request(assessment, state)
    with pytest.raises(ValueError, match="cap"):
        runner_protocol.validate_operation_request(_open_inquiry_request(), state)

    training_count = state["counters"]["training"]
    run_experiment.accept_operation(_best_known_request(candidate), state)
    assert run_experiment.execute_pending_operation() == 0
    assigned = repository.read_state()
    assert assigned["model_roles"]["best_known"] == candidate["id"]
    assert assigned["terminal_state"] is None
    assert assigned["official_assessment"] is None
    assert assigned["counters"]["inquiry"] == state["campaign"]["max_inquiries"]
    assert assigned["counters"]["training"] == training_count
    run_experiment.accept_operation(assessment, assigned)
    assert run_experiment.execute_pending_operation() == 0
    persisted = repository.read_state()
    assert persisted["terminal_state"]["status"] == "official_assessment_requested"
    assert persisted["terminal_state"]["model"] == candidate["id"]
    assert persisted["official_assessment"] is None
    assert persisted["counters"]["inquiry"] == state["campaign"]["max_inquiries"]
    assert persisted["counters"]["training"] == training_count


@pytest.mark.parametrize("action", ["set_working", "retain"])
def test_goal_review_permits_other_model_roles_at_cap(monkeypatch, tmp_path, action):
    state, candidate = _goal_review_candidate(monkeypatch, tmp_path)
    request = _best_known_request(candidate)
    request["model_role"]["action"] = action
    if action == "retain":
        request["model_role"]["label"] = "reference"
    assert runner_protocol.validate_operation_request(request, state) == "model_role"


@pytest.mark.parametrize("evidence", [[], ["M404"], ["M1"]])
def test_goal_review_role_requires_completed_evidence(monkeypatch, tmp_path, evidence):
    state, candidate = _goal_review_candidate(monkeypatch, tmp_path)
    state["operation_events"][0].update(
        status="failed",
        result={"status": "failed", "error": "implementation failure"},
        error="implementation failure",
    )
    request = _best_known_request(candidate)
    request["model_role"]["evidence"] = evidence
    with pytest.raises(ValueError, match="evidence"):
        runner_protocol.validate_operation_request(request, state)


def test_goal_review_role_cannot_bypass_open_inquiry_checkpoint(monkeypatch, tmp_path):
    state, candidate = _goal_review_candidate(monkeypatch, tmp_path, at_cap=False)
    run_experiment.accept_operation(_open_inquiry_request(), state)
    assert run_experiment.execute_pending_operation() == 0
    opened = repository.read_state()
    with pytest.raises(ValueError, match="checkpoint"):
        runner_protocol.validate_operation_request(
            _best_known_request(candidate), opened
        )
    checkpoint = {
        "checkpoint": {
            "human_goal_connection": "The inquiry addresses a current task gap.",
            "current_goal_gap": "The candidate has not established goal success.",
            "current_synthesis": "An evidence-linked inquiry has been opened.",
            "evidence_references": list(opened["scientific_session"]["operation_ids"]),
            "decision_frontier": "Resolve the method question in its fresh session.",
            "completed_operations": list(opened["scientific_session"]["operation_ids"]),
            "candidates_and_roles": "The candidate remains available.",
            "next_direction_or_closure": "Begin the fresh inquiry session.",
            "cumulative_resource_use": "One inquiry opening.",
        }
    }
    run_experiment.accept_operation(checkpoint, opened)
    assert run_experiment.execute_pending_operation() == 0
    checkpointed = repository.read_state()
    assert checkpointed["scientific_session"] is None
    assert checkpointed["active_inquiry"] is not None
    repository.start_scientific_session(
        checkpointed,
        kind="inquiry",
        objective="Resolve the method question.",
        backend_adapter="copilot",
        backend_model="gpt-5.6-luna",
        backend_reasoning="high",
    )
    assert (
        runner_protocol.validate_operation_request(
            _best_known_request(candidate), checkpointed
        )
        == "model_role"
    )
