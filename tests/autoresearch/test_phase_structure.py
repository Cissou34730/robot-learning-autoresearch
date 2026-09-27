"""Inquiry-centered lifecycle boundaries exposed by the launcher and state."""

import json
import shutil
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest

from research import reset_campaign, run_experiment, runner_paths, runner_protocol
from research import runner_repository as repository

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "run_research.ps1"
SCRIPT = SCRIPT_PATH.read_text(encoding="utf-8")
AGENTS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
powershell_only = pytest.mark.skipif(
    POWERSHELL is None, reason="no PowerShell host to run the launcher functions"
)
OPERATION_FUNCTIONS = (
    "New-LegalOperation",
    "Get-InquiryOperations",
    "Get-AnalysisOperations",
    "Format-OperationContract",
)


def _launcher_operations(
    tmp_path: Path, state: dict, *, analysis: bool = False, cap: bool = False
) -> dict:
    """Evaluate the launcher's own operation functions against one state."""
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    names = ", ".join(f"'{name}'" for name in OPERATION_FUNCTIONS)
    call = (
        "Get-AnalysisOperations -State $state"
        if analysis
        else f"Get-InquiryOperations -State $state -TrainingCapReached:${str(cap).lower()}"
    )
    script = tmp_path / "operations.ps1"
    script.write_text(
        f"""
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    '{SCRIPT_PATH}', [ref]$null, [ref]$null)
$names = @({names})
$definitions = $ast.FindAll({{
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -in $names
}}, $true)
foreach ($definition in $definitions) {{
    . ([scriptblock]::Create($definition.Extent.Text))
}}
$state = Get-Content -Raw '{state_path}' | ConvertFrom-Json
$operations = @({call})
[pscustomobject]@{{
    legal = @($operations | Where-Object {{ $_.Legal }} | ForEach-Object {{ $_.Name }})
    blocked = @($operations | Where-Object {{ -not $_.Legal }} | ForEach-Object {{ $_.Name }})
    contract = Format-OperationContract $operations
}} | ConvertTo-Json -Compress
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
    return json.loads(completed.stdout)


def _method(lifecycle: str, *, lineage: bool = True) -> dict:
    return {
        "id": "method-a",
        "inquiry_id": 1,
        "scientific_question": "Can the method learn the task?",
        "rationale": "It tests a different learning mechanism.",
        "lifecycle": lifecycle,
        "base_scientific_commit": "b" * 40,
        "current_lineage": {"artifact": "archive/method"} if lineage else None,
        "iterations": [],
    }


def _inquiry_state(method: dict | None) -> dict:
    return {
        "active_inquiry": {"id": 1, "question": "Q", "scope": "S"},
        "active_method": method,
        "pending_analysis": None,
    }


def _campaign() -> dict:
    return {"id": "campaign", "started_at": "now", "base_commit": "base"}


def _lineage() -> dict:
    return {
        "artifact": "archive/working",
        "fingerprint": "fingerprint",
        "origin_experiment": 1,
        "candidate": "checkpoint",
        "parameters": {},
        "scientific_commit": "a" * 40,
        "training_steps": 120_000,
        "evaluation_artifacts": [],
        "reason": "Selected baseline.",
        "designation_ordinal": 1,
    }


def test_researcher_context_names_the_exact_native_learning_stack():
    for distribution in ("mujoco", "gymnasium", "stable-baselines3"):
        assert f"`{distribution}=={version(distribution)}`" in AGENTS
    assert "not legacy `mujoco-py`" in AGENTS


def test_scientific_model_phase_precedes_baseline_and_does_not_repeat():
    baseline = SCRIPT.split('if (Test-Path "research\\BASELINE_PENDING") {', 1)[1]
    model_phase = baseline.index(
        "Invoke-ResearcherSession -Prompt $scientificModelPrompt"
    )
    model_status = baseline.index("Get-ScientificModelSessionStatus 1")
    baseline_runner = baseline.index("$runnerExitCode = Invoke-Runner")
    assert model_phase < model_status < baseline_runner
    assert "-Experiment 1 -Preliminary" in baseline[:baseline_runner]


def test_scientific_model_is_campaign_memory_and_protected_context():
    model = "research/scientific_model.md"
    assert (
        runner_paths.SCIENTIFIC_MODEL_PATH
        == runner_paths.RESEARCH_DIR / "scientific_model.md"
    )
    assert runner_protocol.is_protected_source(model)
    assert not runner_protocol.is_researcher_owned(model)
    assert repository.is_runner_memory(model)


def test_inquiry_session_requires_selected_baseline():
    state = repository.empty_campaign_state(campaign=_campaign(), last_verdict="fresh")
    with pytest.raises(ValueError, match="same initial baseline designation"):
        repository.ensure_inquiry_session(state)

    state["working_lineage"] = _lineage()
    with pytest.raises(ValueError, match="same initial baseline designation"):
        repository.ensure_inquiry_session(state)

    state["best_known_lineage"] = {**_lineage(), "fingerprint": "other"}
    with pytest.raises(ValueError, match="same initial baseline designation"):
        repository.ensure_inquiry_session(state)

    state["best_known_lineage"] = _lineage()
    first = repository.ensure_inquiry_session(state)
    second = repository.ensure_inquiry_session(state)
    assert first == second
    assert first["campaign_id"] == "campaign"
    assert first["inquiry_id"] == 1
    assert first["role"] == "principal_investigator"
    assert first["status"] == "allocated"


def test_inquiry_session_start_intent_is_durable_before_backend_mapping(
    monkeypatch, tmp_path
):
    state = repository.empty_campaign_state(
        campaign=_campaign(), last_verdict="baseline selected"
    )
    state["working_lineage"] = _lineage()
    state["best_known_lineage"] = _lineage()
    repository.ensure_inquiry_session(state)
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(repository.paths, "STATE_PATH", state_path)

    starting = repository.mark_inquiry_session_starting(state)
    assert starting["status"] == "starting"
    assert repository.read_state()["inquiry_session"] == starting

    started = repository.mark_inquiry_session_started(repository.read_state())
    assert started["id"] == starting["id"]
    assert started["status"] == "started"


def test_later_inquiry_allocation_allows_working_and_best_known_to_diverge():
    state = repository.empty_campaign_state(
        campaign=_campaign(), last_verdict="first inquiry closed"
    )
    state["campaign_inquiry_counters"]["campaign"] = 1
    state["last_allocated_inquiry"] = 1
    state["last_inquiry"] = 1
    state["working_lineage"] = _lineage()
    state["best_known_lineage"] = {
        **_lineage(),
        "artifact": "archive/challenger",
        "fingerprint": "challenger",
        "candidate": "challenger",
        "origin_experiment": 2,
        "designation_ordinal": 2,
    }

    session = repository.ensure_inquiry_session(state)

    assert session["inquiry_id"] == 2


def test_fresh_reset_clears_inquiry_method_and_lab_state():
    assert "research/lab" in reset_campaign.CAMPAIGN_PATHS
    state = repository.empty_campaign_state(campaign=_campaign(), last_verdict="fresh")
    assert state["schema_version"] == repository.STATE_SCHEMA_VERSION
    assert state["inquiry_session"] is None
    assert state["active_inquiry"] is None
    assert state["active_method"] is None
    assert state["campaign_lab"] is None


@pytest.mark.parametrize(
    "content,valid", [(None, False), (" \n", False), ("facts\n", True)]
)
def test_scientific_model_deliverable_preflight(
    tmp_path, monkeypatch, capsys, content, valid
):
    model = tmp_path / "scientific_model.md"
    monkeypatch.setattr(runner_paths, "SCIENTIFIC_MODEL_PATH", model)
    if content is not None:
        model.write_text(content, encoding="utf-8")
    monkeypatch.setattr(
        sys, "argv", ["run_experiment.py", "--check-scientific-model-deliverable"]
    )
    assert (run_experiment.main() == 0) is valid
    assert ("SCIENTIFIC_MODEL_DELIVERABLE_VALID" in capsys.readouterr().out) is valid


@powershell_only
def test_without_inquiry_only_opening_or_concluding_is_legal(tmp_path):
    operations = _launcher_operations(
        tmp_path, _inquiry_state(None) | {"active_inquiry": None}
    )
    assert set(operations["legal"]) == {"inquiry open", "campaign_conclusion"}
    assert "evaluation_request" in operations["blocked"]


@powershell_only
def test_inquiry_without_method_can_declare_measure_reframe_or_close(tmp_path):
    operations = _launcher_operations(tmp_path, _inquiry_state(None))
    assert {
        "method start",
        "evaluation_request",
        "inquiry reframe",
        "inquiry close",
    } <= set(operations["legal"])
    assert {"training", "campaign_conclusion"} <= set(operations["blocked"])


@powershell_only
def test_training_cap_removes_only_training_allocation(tmp_path):
    free = _launcher_operations(tmp_path, _inquiry_state(_method("development")))
    capped = _launcher_operations(
        tmp_path, _inquiry_state(_method("development")), cap=True
    )
    assert "training" in free["legal"]
    assert set(capped["legal"]) == set(free["legal"]) - {"training"}
    assert {
        "evaluation_request",
        "inquiry reframe",
        "method_decision retain",
        "method_decision abandon",
    } <= set(capped["legal"])
    assert {"training", "method_decision promote", "inquiry close"} <= set(
        capped["blocked"]
    )
    assert "method_decision continue/refine/mature" in capped["blocked"]


@powershell_only
def test_mature_method_at_cap_offers_promotion_without_pressure(tmp_path):
    operations = _launcher_operations(
        tmp_path, _inquiry_state(_method("mature")), cap=True
    )
    assert {
        "method_decision promote",
        "method_decision retain",
        "method_decision abandon",
        "evaluation_request",
    } <= set(operations["legal"])
    contract = operations["contract"].lower()
    assert "paired evidence" in contract
    assert "do not" not in contract


@powershell_only
def test_unresolved_method_without_lineage_cannot_be_retained(tmp_path):
    operations = _launcher_operations(
        tmp_path, _inquiry_state(_method("concept", lineage=False))
    )
    assert "method_decision retain" in operations["blocked"]
    assert "method_decision abandon" in operations["legal"]


@pytest.mark.parametrize("lifecycle", ["promoted", "retained", "abandoned"])
@powershell_only
def test_final_method_lets_the_inquiry_close(tmp_path, lifecycle):
    operations = _launcher_operations(tmp_path, _inquiry_state(_method(lifecycle)))
    assert "inquiry close" in operations["legal"]
    assert "training" in operations["blocked"]
    assert not any(name.startswith("method_decision") for name in operations["legal"])


@powershell_only
def test_post_training_analysis_decides_the_iteration(tmp_path):
    state = _inquiry_state(_method("development", lineage=False))
    state["pending_analysis"] = {"experiment": 4, "baseline": False}
    operations = _launcher_operations(tmp_path, state, analysis=True)
    assert {
        "evaluation_request",
        "method_decision continue",
        "method_decision refine",
        "method_decision mature",
        "method_decision abandon",
    } <= set(operations["legal"])
    assert {"method_decision promote", "method_decision retain"} <= set(
        operations["blocked"]
    )
    assert "experiment 4" in operations["contract"]
    assert (
        "candidate is required because the method has no current lineage"
        in (operations["contract"])
    )


@powershell_only
def test_post_training_promotion_requires_prior_maturity(tmp_path):
    state = _inquiry_state(_method("mature"))
    state["pending_analysis"] = {"experiment": 5, "baseline": False}
    operations = _launcher_operations(tmp_path, state, analysis=True)
    assert {"method_decision promote", "method_decision retain"} <= set(
        operations["legal"]
    )


@powershell_only
def test_baseline_analysis_allows_only_measurement_or_selection(tmp_path):
    state = {
        "active_inquiry": None,
        "active_method": None,
        "pending_analysis": {"experiment": 1, "baseline": True},
    }
    operations = _launcher_operations(tmp_path, state, analysis=True)
    assert set(operations["legal"]) == {"evaluation_request", "baseline_decision"}
    assert "inquiry open" in operations["blocked"]


def test_pending_decision_publication_resumes_before_any_session():
    loop = SCRIPT.split("try {", 1)[1]
    resume = loop.index("$null -ne $terminalState.pending_method_decision")
    runner = loop.index("Invoke-Runner", resume)
    assert runner < loop.index("Invoke-ResearcherSession", resume)
    assert "pending_analysis_operation" not in SCRIPT
