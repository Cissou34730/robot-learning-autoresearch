"""Explicit scientific proposal fixtures; never alter campaign files."""

import pytest


@pytest.fixture
def scientific_reasoning():
    return {
        "evidence": [
            {
                "source": "evidence.txt",
                "observation": "Improvement slows late in training.",
            }
        ],
        "alternative": "The available training budget is insufficient.",
        "expected_observation": "Progress resumes under the intervention.",
        "contradicting_observation": "Progress remains unchanged.",
        "initialization_reason": "Use the selected initialization to test this mechanism.",
        "strategy_link": "Distinguish a plateau from insufficient training.",
    }


@pytest.fixture
def scientific_memory(monkeypatch, tmp_path):
    """Memory with two campaigns for tests that explicitly switch campaigns."""
    source = tmp_path / "evidence.txt"
    source.write_text("Measured progression", encoding="utf-8")
    memory = tmp_path / "postmortems.md"
    body = (
        "**Direction:** Investigate the plateau.\n\n"
        "**Lessons and limits:** Progress slows; evidence.txt; one training seed.\n\n"
        "**Open questions:** Optimization or insufficient budget?\n\n"
        "**Conditional next steps:** Continue if progress persists, otherwise inspect control.\n\n"
        "**Reconsider when:** No progress after the additional training.\n"
    )
    memory.write_text(
        "\n".join(
            f"## {campaign} / Scientific strategy\n\n{body}"
            for campaign in (
                "current",
                "previous",
                "00000000-0000-0000-0000-000000000001",
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.POSTMORTEM_PATH", memory)
    return memory
