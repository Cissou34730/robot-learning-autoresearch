"""Launcher and prompt contracts for the strict schema-6 lifecycle."""

from __future__ import annotations

import json
import shutil
import subprocess
from importlib.metadata import version
from pathlib import Path

import pytest

from research import reset_campaign, runner_protocol
from research import runner_repository as repository

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "run_research.ps1"
SCRIPT = SCRIPT_PATH.read_text(encoding="utf-8")
TRUST_SCRIPT_PATH = ROOT / "researcher_session.ps1"
TRUST_SCRIPT = TRUST_SCRIPT_PATH.read_text(encoding="utf-8")
AGENTS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
PROGRAM = (ROOT / "research" / "program.md").read_text(encoding="utf-8")
INSTRUMENTS = (ROOT / "research" / "instruments.md").read_text(encoding="utf-8")
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
powershell_only = pytest.mark.skipif(
    POWERSHELL is None, reason="no PowerShell host to run launcher functions"
)


def _launcher_operations(tmp_path: Path, state: dict, limit: int = 15) -> list[str]:
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    script = tmp_path / "operations.ps1"
    script.write_text(
        f"""
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    '{SCRIPT_PATH}', [ref]$null, [ref]$null)
$definition = $ast.FindAll({{
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq 'Get-AvailableOperations'
}}, $true) | Select-Object -First 1
. ([scriptblock]::Create($definition.Extent.Text))
$state = Get-Content -Raw '{state_path}' | ConvertFrom-Json
@(Get-AvailableOperations -State $state -InquiryLimit {limit}) |
    ConvertTo-Json -Compress
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
    result = json.loads(completed.stdout)
    return result if isinstance(result, list) else [result]


def _launcher_prompt(tmp_path: Path, state: dict) -> str:
    state_path = tmp_path / "prompt-state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    names = (
        "Get-HumanGoalSummary",
        "Get-LatestSessionResult",
        "Get-AvailableOperations",
        "Get-ScientificSessionPhase",
        "New-ScientificSessionPrompt",
    )
    quoted_names = ", ".join(f"'{name}'" for name in names)
    script = tmp_path / "prompt.ps1"
    script.write_text(
        f"""
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    '{SCRIPT_PATH}', [ref]$null, [ref]$null)
$names = @({quoted_names})
$definitions = $ast.FindAll({{
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -in $names
}}, $true)
foreach ($definition in $definitions) {{
    . ([scriptblock]::Create($definition.Extent.Text))
}}
$piPersona = 'Multidisciplinary PI persona.'
$state = Get-Content -Raw '{state_path}' | ConvertFrom-Json
New-ScientificSessionPrompt -State $state -InquiryLimit 15 |
    ConvertTo-Json -Compress
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
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


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


def test_launcher_balances_preparation_and_leaves_terminal_end_to_runner():
    preparation_start = (
        'Write-Status "START | campaign preparation" -Color Magenta -Label session'
    )
    preparation_end = (
        'Write-Status "END | campaign preparation" -Color Magenta -Label session'
    )

    assert SCRIPT.count(preparation_start) == 1
    assert SCRIPT.count(preparation_end) == 1
    assert SCRIPT.index(preparation_start) < SCRIPT.index(preparation_end)
    assert '"END | no credible route remains | "' not in SCRIPT


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


def _state(kind: str, *, inquiry: bool) -> dict:
    active = (
        {
            "id": "I1",
            "question": "What blocks reliable hold?",
            "goal_connection": "The failure prevents the human goal.",
            "closure_condition": "Identify a route-changing result.",
            "rationale": "Resolving it changes the next decision.",
            "opened_in_session": "S0",
            "reframes": [],
        }
        if inquiry
        else None
    )
    return {
        "campaign": {"max_inquiries": 15},
        "human_goal": {
            "source": "research/scenario.md",
            "summary": "Reach and hold with at least 98% official success.",
        },
        "active_inquiry": active,
        "pi_checkpoint": None,
        "scientific_session": {
            "id": "S1",
            "kind": kind,
            "objective": "Make one bounded decision.",
            "inquiry_id": "I1" if kind == "inquiry" else None,
            "backend_session_id": "backend-S1",
            "backend_descriptor": {
                "adapter": "copilot",
                "model": "gpt-5.6-luna",
                "reasoning": "high",
            },
            "scientific_parent_commit": "a" * 40,
            "operation_ids": [],
        },
        "counters": {
            "inquiry": 0,
            "session": 1,
            "training": 0,
            "measurement": 0,
            "event": 0,
        },
        "operation_events": [],
        "model_roles": {"working": None, "best_known": None, "retained": {}},
        "candidates": {},
        "official_assessment": None,
    }


def test_native_learning_stack_and_pi_ownership_are_explicit():
    for distribution in ("mujoco", "gymnasium", "stable-baselines3"):
        assert f"`{distribution}=={version(distribution)}`" in AGENTS
    assert "not legacy `mujoco-py`" in AGENTS
    assert "## PI-owned paths" in AGENTS


def test_fresh_startup_waits_for_the_scientific_model():
    assert '$state.scientific_model.status -eq "pending"' in SCRIPT
    assert "--mark-scientific-model-ready" in SCRIPT
    assert "Established facts" in SCRIPT
    assert "Physical consequences" in SCRIPT
    assert "Unknowns" in SCRIPT


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


def test_launcher_uses_one_schema6_operation_request():
    assert "research/operation_request.json" in SCRIPT
    assert 'Test-Path "research\\operation_request.json" -PathType Leaf' in SCRIPT
    assert "if ($state.pending_operation)" in SCRIPT
    assert "--check-operation" in SCRIPT
    assert "--execute-pending" in SCRIPT


def test_prompt_contains_goal_directed_imperatives_and_source_router():
    required = (
        "Human goal:",
        "Factual evidence relative to the goal:",
        "PI-interpreted gap:",
        "Session phase:",
        "Active inquiry and relevance:",
        "Bounded session objective:",
        "Strategic resource summary:",
        "Available operations:",
        "Choose the operation whose result would most improve the next decision toward the human goal.",
        "Before ending this scientific session, write a durable checkpoint",
    )
    for phrase in required:
        assert phrase in SCRIPT
    assert "Read AGENTS.md, research/program.md" not in SCRIPT
    assert "campaign-long" not in SCRIPT.lower()
    assert "autonomous" not in SCRIPT.lower()


@powershell_only
def test_generated_prompt_starts_with_required_decision_context(tmp_path):
    prompt = _launcher_prompt(tmp_path, _state("inquiry", inquiry=True))
    ordered = (
        "Human goal:",
        "Factual evidence relative to the goal:",
        "PI-interpreted gap:",
        "Session phase:",
        "Active inquiry and relevance:",
        "Bounded session objective:",
        "Strategic resource summary:",
        "Available operations:",
    )
    positions = [prompt.index(label) for label in ordered]
    assert positions == sorted(positions)
    assert prompt.startswith("Human goal:")
    assert (
        "Choose the operation whose result would most improve the next decision "
        "toward the human goal."
    ) in prompt


@powershell_only
@pytest.mark.parametrize(
    ("kind", "inquiry", "expected_phase", "expected_inquiry"),
    [
        (
            "startup",
            False,
            "startup",
            "None; this is the startup scientific-design session.",
        ),
        (
            "goal_review",
            False,
            "goal_review",
            "None; this is campaign-level goal review.",
        ),
        ("inquiry", True, "inquiry", "I1: What blocks reliable hold?"),
        (
            "inquiry",
            False,
            "closed inquiry awaiting checkpoint",
            "The inquiry is closed; preserve its outcome",
        ),
    ],
)
def test_prompt_phase_matches_session_kind_and_state(
    tmp_path, kind, inquiry, expected_phase, expected_inquiry
):
    prompt = _launcher_prompt(tmp_path, _state(kind, inquiry=inquiry))
    assert f"Session phase: {expected_phase}" in prompt
    assert f"Active inquiry and relevance: {expected_inquiry}" in prompt


@powershell_only
def test_goal_review_offers_only_goal_choices_and_checkpoint(tmp_path):
    operations = _launcher_operations(tmp_path, _state("goal_review", inquiry=False))
    assert any(item.startswith("inquiry open:") for item in operations)
    assert any("request_official_assessment" in item for item in operations)
    assert any("no_credible_route" in item for item in operations)
    assert any(item.startswith("checkpoint:") for item in operations)
    assert not any(item.startswith("training:") for item in operations)


@powershell_only
def test_startup_offers_only_initial_scientific_operations_and_checkpoint(tmp_path):
    operations = _launcher_operations(tmp_path, _state("startup", inquiry=False))
    assert any(item.startswith("measurement:") for item in operations)
    assert any(item.startswith("training:") for item in operations)
    assert any(item.startswith("model_role:") for item in operations)
    assert any(item.startswith("restore_recipe:") for item in operations)
    assert any(item.startswith("checkpoint:") for item in operations)
    assert not any(item.startswith("inquiry ") for item in operations)
    assert not any(item.startswith("campaign_conclusion") for item in operations)


@powershell_only
def test_max_inquiries_only_removes_inquiry_creation(tmp_path):
    state = _state("goal_review", inquiry=False)
    state["counters"]["inquiry"] = 15
    operations = _launcher_operations(tmp_path, state, limit=15)
    assert not any(item.startswith("inquiry open:") for item in operations)
    assert any("request_official_assessment" in item for item in operations)
    assert any("no_credible_route" in item for item in operations)
    assert any(item.startswith("checkpoint:") for item in operations)


@powershell_only
def test_bounded_session_offers_peer_inquiry_operations_and_checkpoint(tmp_path):
    operations = _launcher_operations(tmp_path, _state("inquiry", inquiry=True))
    assert any(item.startswith("measurement:") for item in operations)
    assert any(item.startswith("training:") for item in operations)
    assert any(item.startswith("inquiry close:") for item in operations)
    assert any(item.startswith("checkpoint:") for item in operations)
    assert not any("post-training" in item for item in operations)


@powershell_only
def test_launcher_summary_separates_completed_evidence_from_failed_history(tmp_path):
    state = _state("inquiry", inquiry=True)
    state["scientific_session"]["operation_ids"] = ["M2"]
    state["operation_events"] = [
        {
            "id": "M1",
            "kind": "measurement",
            "status": "failed",
            "error": "instrument failed",
            "superseded_by": "M2",
            "result": {"status": "failed", "error": "instrument failed"},
        },
        {
            "id": "M2",
            "kind": "measurement",
            "status": "completed",
            "error": None,
            "superseded_by": None,
            "result": {"status": "completed", "measurements": []},
        },
    ]
    state["counters"]["measurement"] = 2

    prompt = _launcher_prompt(tmp_path, state)

    assert "1 completed measurement operations" in prompt
    assert "1 completed operations" in prompt
    assert "2 measurement operations" not in prompt
    assert "Execution history (not evidence): 1 failed attempts" in prompt
    assert "including 1 superseded attempts" in prompt
    assert "Operation M2 (measurement)" in prompt
    assert "Operation M1 (measurement)" not in prompt


@powershell_only
def test_reframed_inquiry_offers_only_checkpoint(tmp_path):
    state = _state("inquiry", inquiry=True)
    state["scientific_session"]["operation_ids"] = ["E1"]
    state["operation_events"] = [
        {"id": "E1", "kind": "inquiry", "result": {"action": "reframe"}}
    ]
    assert _launcher_operations(tmp_path, state) == [
        "checkpoint: preserve the goal-level or inquiry decision and end this bounded session"
    ]


def test_launcher_persists_and_reuses_bounded_backend_session_identity():
    assert '"--backend-session-id", ([guid]::NewGuid().ToString())' in SCRIPT
    assert "$state.scientific_session.backend_session_id" in SCRIPT
    assert "--backend-adapter" in SCRIPT
    assert "--backend-model" in SCRIPT
    assert "--backend-reasoning" in SCRIPT
    assert '$sessionArgs += "--resume-or-create"' in SCRIPT
    assert "--synchronize-max-inquiries" in SCRIPT


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


def test_every_post_pi_mutable_entry_point_uses_the_launcher_gate():
    runner = SCRIPT.split("function Invoke-Runner", 1)[1].split(
        "function Test-StopAfterOperation", 1
    )[0]
    pi = SCRIPT.split("function Invoke-PISession", 1)[1].split(
        "function Update-ResearchBrief", 1
    )[0]
    operation_check = SCRIPT.split("function Test-OperationRequest", 1)[1].split(
        "function Test-ScientificModelRegisters", 1
    )[0]
    model_check = SCRIPT.split("function Test-ScientificModelDeliverable", 1)[1].split(
        "function Invoke-ScientificModelPhase", 1
    )[0]
    brief_update = SCRIPT.split("function Update-ResearchBrief", 1)[1].split(
        "function Get-HumanGoalSummary", 1
    )[0]

    for entry_point in (runner, pi, brief_update, operation_check, model_check):
        assert "Enter-TrustedMutableInvocation" in entry_point
    assert "$exitCode -eq 0" in runner
    assert "New-PITrustSnapshot" in runner
    assert "git status" not in TRUST_SCRIPT
    assert "git diff" not in TRUST_SCRIPT
    assert "git ls-files" not in TRUST_SCRIPT


@powershell_only
@pytest.mark.parametrize(
    ("kind", "inquiry"),
    [("goal_review", True), ("inquiry", False)],
)
def test_goal_or_inquiry_boundary_requires_checkpoint(tmp_path, kind, inquiry):
    operations = _launcher_operations(tmp_path, _state(kind, inquiry=inquiry))
    assert operations == [
        "checkpoint: preserve the goal-level or inquiry decision and end this bounded session"
    ]


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


def test_program_is_informative_and_instruments_are_mechanical():
    assert "The human goal" in PROGRAM
    assert "There is no mandatory post-training phase" in PROGRAM
    assert (
        "Each Runner round trip reads `research/operation_request.json`" in INSTRUMENTS
    )
    assert '"checkpoint"' in INSTRUMENTS
    assert '"restore_recipe"' in INSTRUMENTS
    assert '"request_official_assessment"' in INSTRUMENTS
    assert (
        "Every evidence reference is the ID of an operation event whose status is"
        in INSTRUMENTS
    )
    assert '"research/evaluations/<campaign>/detail.json"' not in INSTRUMENTS
