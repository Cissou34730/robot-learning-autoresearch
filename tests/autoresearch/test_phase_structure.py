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


def test_fresh_startup_is_state_driven_and_has_no_baseline_branch():
    assert '$state.scientific_model.status -eq "pending"' in SCRIPT
    assert "--mark-scientific-model-ready" in SCRIPT
    assert "Established facts" in SCRIPT
    assert "Physical consequences" in SCRIPT
    assert "Unknowns" in SCRIPT
    assert "BASELINE_PENDING" not in SCRIPT
    assert "baseline training" not in SCRIPT.lower()


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


def test_launcher_uses_one_schema6_request_and_no_retired_flow():
    assert "research/operation_request.json" in SCRIPT
    assert "Runner resuming the existing PI operation request" in SCRIPT
    assert "--check-operation" in SCRIPT
    assert "--execute-pending" in SCRIPT
    for retired in (
        "research\\proposal.json",
        "research\\evaluation_request.json",
        "pending_analysis",
        "method_decision",
        "post-training",
        "inquiry_session",
        "ResumeOrCreate",
        "MaxExperiments",
    ):
        assert retired not in SCRIPT


def test_prompt_contains_goal_directed_imperatives_and_source_router():
    required = (
        "Human goal:",
        "Factual evidence relative to the goal:",
        "PI-interpreted gap:",
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
def test_inquiry_session_offers_peer_operations_and_checkpoint(tmp_path):
    operations = _launcher_operations(tmp_path, _state("inquiry", inquiry=True))
    assert any(item.startswith("measurement:") for item in operations)
    assert any(item.startswith("training:") for item in operations)
    assert any(item.startswith("inquiry close:") for item in operations)
    assert any(item.startswith("checkpoint:") for item in operations)
    assert not any("post-training" in item for item in operations)


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
    assert '$sessionArgs += "--resume-or-create"' in SCRIPT
    assert "--synchronize-max-inquiries" in SCRIPT


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
    assert not {"pending_analysis", "active_method", "inquiry_session"} & set(state)


def test_scientific_model_and_request_paths_remain_protected():
    assert runner_protocol.is_protected_source("research/scientific_model.md")
    assert not runner_protocol.is_researcher_owned("research/scientific_model.md")
    assert repository.is_runner_owned("research/operation_request.json")
    assert not runner_protocol.is_researcher_owned("research/operation_request.json")


def test_program_is_informative_and_instruments_are_mechanical():
    assert "The human goal" in PROGRAM
    assert "There is no mandatory baseline phase." in PROGRAM
    assert "There is no mandatory post-training phase" in PROGRAM
    assert (
        "Each Runner round trip reads `research/operation_request.json`" in INSTRUMENTS
    )
    assert '"checkpoint"' in INSTRUMENTS
    assert '"restore_recipe"' in INSTRUMENTS
    assert '"request_official_assessment"' in INSTRUMENTS
