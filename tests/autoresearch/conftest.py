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
        "expected_observation": "Progress resumes under the intervention.",
        "initialization_reason": "Use the selected initialization to test this mechanism.",
        "objective_link": "Resolve a source of failure relevant to the objective.",
        "rationale": "This run distinguishes optimization progress from a plateau.",
        "scientific_model": {
            "observation": "Measured learning slows late in training.",
            "connection": "The task requires sustained stabilization; this observation alone cannot identify a physical cause.",
            "alternatives": "The learning rate or training duration might explain the plateau.",
            "diagnostic_decision": "Existing checkpoints do not resolve process variance; the proposed run tests it directly without repeating those measurements.",
        },
        "predicted_behavioral_path": (
            "Further learning may change the policy's actions near the hold boundary."
        ),
    }


@pytest.fixture
def scientific_memory(monkeypatch, tmp_path):
    """Memory with two campaigns for tests that explicitly switch campaigns."""
    source = tmp_path / "evidence.txt"
    source.write_text("Measured progression", encoding="utf-8")
    memory = tmp_path / "postmortems.md"
    body = (
        "**Current synthesis:** Investigate the plateau.\n\n"
        "**Lessons and limits:** Progress slows; evidence.txt; one training seed.\n\n"
        "**Competing explanations:** Optimization or insufficient budget?\n\n"
        "**Decision frontier:** Whether measured progression resumes under "
        "additional learning or remains flat.\n"
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
