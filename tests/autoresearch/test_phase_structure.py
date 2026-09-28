"""Launcher and prompt contracts for the strict schema-6 lifecycle."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from research import reset_campaign, runner_protocol
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
    assert not runner_protocol.is_researcher_owned("research/operation_request.json")
