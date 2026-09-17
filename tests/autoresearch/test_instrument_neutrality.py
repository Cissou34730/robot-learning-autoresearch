"""Presentation of the two measurement roles.

Issue #38 removed a presentation bias toward `task_reference`. This was later
deliberately revised: `research_evaluation` is presented as the development
instrument and `task_reference` as a pre-validation preview of the final
benchmark, approximate and selection-contaminated and never terminal evidence.
The documentation must still keep equal factual depth and no default.
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


def test_task_reference_is_documented_as_a_benchmark_preview():
    normalized = " ".join(INSTRUMENTS.read_text(encoding="utf-8").split())
    assert "pre-validation preview of the final benchmark" in normalized
    assert "approximate and selection-contaminated" in normalized
    assert "never the terminal verdict" in normalized
    assert "can never be a stopping-validation panel" in normalized

    program = " ".join(
        (ROOT / "research" / "program.md").read_text(encoding="utf-8").split()
    )
    assert "previews the final benchmark" in program
    assert "never be a stopping-validation panel" in program


def test_brief_phase_section_names_no_instrument_or_pairing():
    text = "\n".join(
        brief._v4_phase_section({}, None, None, "none", None, "cid", "base")
    )

    assert "research_evaluation" not in text
    assert "task_reference" not in text
