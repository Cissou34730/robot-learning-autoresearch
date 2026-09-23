"""The v4 Researcher lifecycle exposes three phases.

Issue #33: consolidation into Investigation / Closure / Experiment design is
resolved at the existing PowerShell/Python boundary. The v4 lifecycle already
runs experiment design, investigation (which may request another measurement
round) and closure; the separate evaluation-design session remains only as a
legacy schema-v3-compatibility path.
"""

import sys
from pathlib import Path

import pytest

from research import run_experiment, runner_paths, runner_protocol, runner_repository

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "run_research.ps1").read_text(encoding="utf-8")


def test_v4_researcher_phases_are_design_investigation_and_closure():
    assert 'Phase "new hypothesis"' in SCRIPT
    assert 'Phase "post-training analysis"' in SCRIPT
    assert 'Phase "lineage decision"' in SCRIPT


def test_investigation_can_request_another_measurement_round():
    assert "research/evaluation_request.json for another measurement round" in SCRIPT


def test_evaluation_design_is_only_the_legacy_compatibility_path():
    analysis_branch = "schema_version -eq 4 -and $null -ne $researchState.pending_analysis"
    assert analysis_branch in SCRIPT
    assert "if ($null -ne $researchState.pending_evaluation_request)" in SCRIPT


def test_scientific_model_phase_precedes_baseline_and_does_not_repeat():
    baseline = SCRIPT.split('if (Test-Path "research\\BASELINE_PENDING") {', 1)[1]
    model_phase = baseline.index("Invoke-ResearcherSession -Prompt $scientificModelPrompt")
    model_status = baseline.index("Get-ScientificModelSessionStatus 1")
    baseline_runner = baseline.index("$runnerExitCode = Invoke-Runner")
    assert model_phase < model_status < baseline_runner
    assert "if (-not (Test-Path \"research\\scientific_model.md\" -PathType Leaf))" in baseline[:model_phase]
    assert "Invoke-ResearcherSession -Prompt $scientificModelRetryPrompt" in baseline[:baseline_runner]
    assert "-Experiment 1 -Continue" in baseline[:baseline_runner]
    assert "-Experiment 1 -Preliminary" in baseline[:baseline_runner]
    assert "-Experiment 1 -Continue -Preliminary" in baseline[:baseline_runner]
    assert baseline.index("if (-not $scientificModelPhasePrompt.Trim()") < model_phase
    assert baseline.index("Baseline completed without research/scientific_model.md") > baseline_runner
    assert "elseif (-not (Test-ScientificModelDeliverable))" in baseline[:baseline_runner]


def test_scientific_model_phase_prompt_is_configured():
    prompt = SCRIPT.split("$scientificModelPhasePrompt = @'", 1)[1].split("\n'@", 1)[0]
    assert prompt.strip()
    assert "PLACEHOLDER" not in prompt


def test_preliminary_reading_material_excludes_campaign_context():
    corpus = SCRIPT.split("$scientificModelPrompt = @(", 1)[1].split(') -join "`n`n"', 1)[0]
    assert "Read AGENTS.md and research/scenario.md" in corpus
    assert "Do not read research/program.md or research/instruments.md" in corpus
    assert "research/brief.md" not in corpus
    assert "Write the final output to research/scientific_model.md." in corpus


def test_subsequent_phase_prompts_read_the_frozen_model():
    guidance = SCRIPT.split('$scientificModelUseGuidance = "', 1)[1].split('"', 1)[0]
    assert "use it when relevant" in guidance
    assert "training, parameter choices, and policy performance" in guidance
    assert "current campaign configuration, logs, and measurements" in guidance
    assert "do not infer training outcomes from the scientific model" in guidance
    for prompt in ("analysisPrompt", "evaluationPrompt", "decisionPrompt", "researchPrompt"):
        corpus = SCRIPT.split(f"${prompt} = @(", 1)[1].split(") -join", 1)[0]
        assert "research/scientific_model.md" in corpus
        assert "research/brief.md" in corpus
        assert "$scientificModelUseGuidance" in corpus


def test_scientific_model_is_campaign_memory_and_protected_context():
    model = "research/scientific_model.md"
    assert runner_paths.SCIENTIFIC_MODEL_PATH == runner_paths.RESEARCH_DIR / "scientific_model.md"
    assert runner_protocol.is_protected_source(model)
    assert not runner_protocol.is_researcher_owned(model)
    assert runner_repository.is_runner_memory(model)
    assert model not in runner_repository.RUNNER_CONTROL_PATHS


@pytest.mark.parametrize("content,valid", [(None, False), (" \n", False), ("facts\n", True)])
def test_scientific_model_deliverable_preflight(tmp_path, monkeypatch, capsys, content, valid):
    model = tmp_path / "scientific_model.md"
    monkeypatch.setattr(runner_paths, "SCIENTIFIC_MODEL_PATH", model)
    if content is not None:
        model.write_text(content, encoding="utf-8")
    monkeypatch.setattr(
        sys, "argv", ["run_experiment.py", "--check-scientific-model-deliverable"]
    )
    assert (run_experiment.main() == 0) is valid
    assert ("SCIENTIFIC_MODEL_DELIVERABLE_VALID" in capsys.readouterr().out) is valid
