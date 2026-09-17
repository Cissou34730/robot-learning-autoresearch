"""Presentation of the two measurement instruments.

Issue #38 removed a presentation bias toward `task_reference`. The two are now
distinguished by measurement properties, neither is generally authoritative, and
the fixed reused panel is neither a privileged lineage criterion nor terminal
evidence. The documentation must still keep equal factual depth and no default.
"""

from pathlib import Path

from research import build_research_brief as brief

ROOT = Path(__file__).resolve().parents[2]
INSTRUMENTS = ROOT / "research" / "instruments.md"
CATEGORIES = (
    "Ownership:",
    "Settings:",
    "Measured task:",
    "Outputs:",
    "Artifact semantics:",
)


def _instrument_section(text: str, heading: str) -> str:
    start = text.index(heading)
    section = text[start:]
    end = section.find("\n### ", len(heading))
    return section if end == -1 else section[:end]


def test_both_instruments_are_documented_with_parallel_categories():
    text = INSTRUMENTS.read_text(encoding="utf-8")

    research = _instrument_section(text, "### `research_evaluation`")
    task = _instrument_section(text, "### `task_reference`")
    for category in CATEGORIES:
        assert category in research, f"research_evaluation lacks {category}"
        assert category in task, f"task_reference lacks {category}"


def test_instrument_documentation_recommends_neither_instrument():
    text = INSTRUMENTS.read_text(encoding="utf-8").lower()

    for wording in (
        "recommend",
        "preferred instrument",
        "default instrument",
        "by default",
        "always request",
        "should request",
    ):
        assert wording not in text, f"instrument catalog says {wording!r}"


def test_instruments_are_distinguished_by_measurement_properties():
    normalized = " ".join(INSTRUMENTS.read_text(encoding="utf-8").split())
    assert "distinguished by measurement properties, not by authority" in normalized
    assert "configurable development measurement" in normalized
    assert "fixed development panel" in normalized
    assert "must not receive automatic priority in lineage decisions" in normalized
    assert "Neither instrument is generally authoritative" in normalized
    assert "official benchmark remains the only terminal verdict" in normalized

    program = " ".join(
        (ROOT / "research" / "program.md").read_text(encoding="utf-8").split()
    )
    assert "distinguished by their properties, not by authority" in program
    assert "not a privileged lineage criterion" in program
    assert "no task-reference measurement" in program

    prompt = " ".join(
        (ROOT / "run_research.ps1").read_text(encoding="utf-8").split()
    )
    assert "reused development panel" in prompt
    assert "not a privileged lineage criterion" in prompt
    assert "disjoint panel to obtain independent evidence" in prompt


def test_brief_phase_section_names_no_instrument_or_pairing():
    text = "\n".join(
        brief._v4_phase_section({}, None, None, "none", None, "cid", "base")
    )

    assert "research_evaluation" not in text
    assert "task_reference" not in text
