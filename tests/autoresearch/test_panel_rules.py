"""Research-evaluation panel independence and removal of the stopping machinery.

A panel is the half-open interval ``[seed, seed + episodes)``. An identical panel
may be reused deliberately, a disjoint panel is always allowed, and partial
overlap is rejected; overlaps with the protected benchmark episodes are
rejected. The separate terminal-validation protocol no longer exists.
"""

from pathlib import Path

import pytest

from research import runner_protocol as protocol
from robot_learning.benchmark import final_contract

ROOT = Path(__file__).resolve().parents[2]


def _request(panels: list[tuple[int, int]], *, instrument: str = "research_evaluation") -> dict:
    measurements = []
    for index, (seed, episodes) in enumerate(panels):
        entry: dict = {
            "instrument": instrument,
            "candidate": f"candidate-{index}",
            "selection": "observed signal",
            "omitted_alternative": None,
        }
        if instrument == "research_evaluation":
            entry.update({"seed": seed, "episodes": episodes})
        measurements.append(entry)
    return {"experiment": 1, "question": "q", "reason": "r", "measurements": measurements}


def test_official_panel_overlap_is_rejected():
    request = _request([(final_contract.EVALUATION_SEED, 10)])
    protocol.validate_evaluation_request(request)
    with pytest.raises(ValueError, match="protected benchmark evidence"):
        protocol.validate_panel_independence(request, [])


def test_partial_overlap_with_a_prior_research_panel_is_rejected():
    with pytest.raises(ValueError, match="previously recorded research panel"):
        protocol.validate_panel_independence(_request([(100, 200)]), [(150, 200)])


def test_exact_panel_reuse_is_accepted():
    protocol.validate_panel_independence(_request([(100, 200)]), [(100, 200)])


def test_disjoint_panels_are_accepted():
    protocol.validate_panel_independence(_request([(100, 200)]), [(500, 200)])


def test_several_candidates_on_one_identical_panel_are_accepted():
    protocol.validate_panel_independence(
        _request([(100, 200), (100, 200), (100, 200)]), []
    )


def test_partial_overlap_within_one_request_is_rejected():
    with pytest.raises(ValueError, match="within one request"):
        protocol.validate_panel_independence(_request([(100, 200), (150, 200)]), [])


def test_task_reference_panel_is_not_checked():
    protocol.validate_panel_independence(
        _request([(0, 0)], instrument="task_reference"), [(100, 200)]
    )


def test_request_without_purpose_is_accepted():
    protocol.validate_evaluation_request(_request([(100, 200)]))


def test_terminal_validation_machinery_is_removed():
    assert not hasattr(protocol, "validate_terminal_validation_request")
    assert not hasattr(protocol, "normalize_measurement_purposes")
    assert not hasattr(protocol, "MEASUREMENT_PURPOSES")
    assert not (ROOT / "research" / "stopping_policy.py").exists()
    assert not (ROOT / "research" / "stopping_contract.md").exists()


def test_no_obsolete_stopping_language_in_researcher_surfaces():
    forbidden = (
        "terminal_validation",
        "stopping-validation",
        "stopping_contract",
        "stopping-validation panel",
    )
    for relative in ("research/program.md", "research/instruments.md", "run_research.ps1"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        for wording in forbidden:
            assert wording not in text, f"{relative} still says {wording!r}"

    brief_source = (ROOT / "research" / "build_research_brief.py").read_text(
        encoding="utf-8"
    )
    assert "Terminal-readiness" not in brief_source
    assert "stopping_policy" not in brief_source
