"""The v4 Researcher lifecycle exposes three phases.

Issue #33: consolidation into Investigation / Closure / Experiment design is
resolved at the existing PowerShell/Python boundary. The v4 lifecycle already
runs experiment design, investigation (which may request another measurement
round) and closure; the separate evaluation-design session remains only as a
legacy schema-v3-compatibility path.
"""

from pathlib import Path

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
