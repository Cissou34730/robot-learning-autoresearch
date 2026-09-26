"""The v4 Researcher lifecycle separates inquiry, analysis, and closure roles.

The campaign PI owns inquiry and experiment preparation across restarts.
Post-training analysis may request another measurement round, closure remains a
separate phase, and evaluation design remains only for schema-v3 compatibility.
"""

import sys
from pathlib import Path

import pytest

from research import (
    reset_campaign,
    run_experiment,
    runner_paths,
    runner_protocol,
    runner_repository,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "run_research.ps1").read_text(encoding="utf-8")


def test_evaluation_design_is_only_the_legacy_compatibility_path():
    analysis_branch = (
        "schema_version -eq 4 -and $null -ne $researchState.pending_analysis"
    )
    assert analysis_branch in SCRIPT
    assert "if ($null -ne $researchState.pending_evaluation_request)" in SCRIPT


def test_scientific_model_phase_precedes_baseline_and_does_not_repeat():
    baseline = SCRIPT.split('if (Test-Path "research\\BASELINE_PENDING") {', 1)[1]
    model_phase = baseline.index(
        "Invoke-ResearcherSession -Prompt $scientificModelPrompt"
    )
    model_status = baseline.index("Get-ScientificModelSessionStatus 1")
    baseline_runner = baseline.index("$runnerExitCode = Invoke-Runner")
    assert model_phase < model_status < baseline_runner
    assert (
        'if (-not (Test-Path "research\\scientific_model.md" -PathType Leaf))'
        in baseline[:model_phase]
    )
    assert (
        "Invoke-ResearcherSession -Prompt $scientificModelRetryPrompt"
        in baseline[:baseline_runner]
    )
    assert "-Experiment 1 -Continue" in baseline[:baseline_runner]
    assert "-Experiment 1 -Preliminary" in baseline[:baseline_runner]
    assert "-Experiment 1 -Continue -Preliminary" in baseline[:baseline_runner]
    assert baseline.index("if (-not $scientificModelPhasePrompt.Trim()") < model_phase
    assert (
        "elseif (-not (Test-ScientificModelDeliverable))" in baseline[:baseline_runner]
    )


def test_scientific_model_is_campaign_memory_and_protected_context():
    model = "research/scientific_model.md"
    assert (
        runner_paths.SCIENTIFIC_MODEL_PATH
        == runner_paths.RESEARCH_DIR / "scientific_model.md"
    )
    assert runner_protocol.is_protected_source(model)
    assert not runner_protocol.is_researcher_owned(model)
    assert runner_repository.is_runner_memory(model)
    assert model not in runner_repository.RUNNER_CONTROL_PATHS


def test_measurement_rounds_resume_the_originating_researcher_session():
    analysis = SCRIPT.split(
        "if ($researchState.schema_version -eq 4 -and "
        "$null -ne $researchState.pending_analysis)",
        1,
    )[1].split("if ($null -ne $researchState.pending_evaluation_request)", 1)[0]
    assert "$script:ResumeAnalysisSession = $true" in analysis
    assert (
        "Invoke-ResearcherSession -Prompt $analysisPrompt "
        '-Phase "post-training analysis" -Experiment $analysisExperiment -Continue'
        in analysis
    )
    assert (
        "Invoke-ResearcherSession -Prompt $researchPrompt "
        '-Phase "principal investigator" -Experiment 0 '
        "-SessionId $piSession.id -Continue" in SCRIPT
    )


def test_principal_investigator_session_is_campaign_persistent():
    assert "--mark-principal-investigator-session-started" in SCRIPT
    assert "$researchState.principal_investigator_session" in SCRIPT
    assert "-SessionId $piSession.id -Continue" in SCRIPT
    assert "if (-not $SessionId)" in SCRIPT
    initial_call = SCRIPT.index(
        'Invoke-ResearcherSession -Prompt $researchPrompt '
        '-Phase "principal investigator" -Experiment 0 -SessionId $piSession.id'
    )
    mark_started = SCRIPT.index(
        'Invoke-Runner -Arguments @("--mark-principal-investigator-session-started")'
    )
    assert initial_call < mark_started
    assert (
        "continue as the campaign's principal investigator at an inquiry boundary"
        in SCRIPT
    )


def test_principal_investigator_deliverables_restore_the_phase_anchor_before_validation():
    phase = SCRIPT.split(
        'Write-Status "=== Principal investigator advancing the active inquiry ==="',
        1,
    )[1]
    first_session = phase.index(
        "Invoke-ResearcherSession -Prompt $researchPrompt "
        '-Phase "principal investigator"'
    )
    first_reanchor = phase.index(
        "Invoke-HypothesisAnchor -ConclusionOnly:$budgetReached",
        first_session,
    )
    first_validation = phase.index(
        'Get-ProposalSessionStatus "principal investigator" 1',
        first_session,
    )
    retry_session = phase.index(
        "Invoke-ResearcherSession -Prompt $retryPrompt "
        '-Phase "principal investigator"',
        first_validation,
    )
    retry_reanchor = phase.index(
        "Invoke-HypothesisAnchor -ConclusionOnly:$budgetReached",
        retry_session,
    )
    retry_validation = phase.index(
        'Get-ProposalSessionStatus "principal investigator" 2',
        retry_session,
    )

    assert first_session < first_reanchor < first_validation
    assert retry_session < retry_reanchor < retry_validation


def test_principal_investigator_identity_is_allocated_once():
    state = {
        "campaign": {
            "id": "campaign",
            "started_at": "now",
            "base_commit": "base",
        },
        "principal_investigator_session": None,
    }

    first = runner_repository.ensure_principal_investigator_session(state)
    second = runner_repository.ensure_principal_investigator_session(state)

    assert first == second
    assert first["campaign_id"] == "campaign"
    assert first["role"] == "principal_investigator"
    assert first["status"] == "allocated"


def test_fresh_reset_clears_campaign_lab_and_pi_state():
    assert "research/lab" in reset_campaign.CAMPAIGN_PATHS
    state = runner_repository.empty_v4_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        last_verdict="fresh",
    )
    assert state["principal_investigator_session"] is None
    assert state["campaign_lab"] is None


def test_principal_investigator_persona_reaches_every_researcher_phase():
    persona = (
        "You are the principal investigator responsible for leading this campaign "
        "toward a learned policy that satisfies the human objective"
    )
    prompts = (
        SCRIPT.split("$analysisPrompt = @(", 1)[1].split(") -join", 1)[0],
        SCRIPT.split("$evaluationPrompt = @(", 1)[1].split(") -join", 1)[0],
        SCRIPT.split("$decisionPrompt = @(", 1)[1].split(") -join", 1)[0],
        SCRIPT.split("$researchPrompt = @(", 1)[1].split(") -join", 1)[0],
    )

    assert persona in SCRIPT
    assert all("$researcherPersonaGuidance" in prompt for prompt in prompts)
    scientific_model_prompt = SCRIPT.split("$scientificModelPhasePrompt = @'", 1)[
        1
    ].split("'@", 1)[0]
    assert persona in scientific_model_prompt
    assert "autonomous principal scientist" not in SCRIPT
    assert "autonomous robotics research engineer" not in SCRIPT


def test_research_funnel_guidance_is_injected_at_decision_points():
    analysis = SCRIPT.split("$analysisPrompt = @(", 1)[1].split(") -join", 1)[0]
    analysis_retry = SCRIPT.split("$analysisRetryPrompt = @(", 1)[1].split(
        ") -join", 1
    )[0]
    decision = SCRIPT.split("$decisionPrompt = @(", 1)[1].split(") -join", 1)[0]
    decision_retry = SCRIPT.split("$decisionRetryPrompt = @(", 1)[1].split(
        ") -join", 1
    )[0]
    preparation = SCRIPT.split("$researchPrompt = @(", 1)[1].split(") -join", 1)[0]
    preparation_retry = SCRIPT.split("$retryPrompt = @(", 1)[1].split(
        ") -join", 1
    )[0]

    for prompt in (analysis, analysis_retry, decision, decision_retry, preparation):
        assert "$developingMethodGuidance" in prompt
    for prompt in (preparation, preparation_retry):
        assert "$openBehaviorQuestionGuidance" in prompt
        assert "$laboratoryReuseGuidance" in prompt
    assert "$laboratoryReuseGuidance" in analysis
    assert "$laboratoryReuseGuidance" in decision


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
