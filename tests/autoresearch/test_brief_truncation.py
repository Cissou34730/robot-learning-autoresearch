"""Issue #52: the brief must not silently overstate truncated scientific prose.

Truncation that drops the qualifier at the end of a sentence turns a hedged
conclusion into a stronger claim. These tests pin three guarantees: the
hypothesis assessment is never truncated, any truncation that is kept announces
itself with the omitted length and a pointer to the full text, and table cells
render the recorded characters instead of silently rewriting them.
"""

import json

import pytest

from research import build_research_brief as brief
from research.build_research_brief import render_research_brief

REFERENCE = "research/results.jsonl"


def test_compact_marks_truncation_with_omitted_length_and_pointer():
    text = "first sentence is short. " + "qualification afterwards " * 20
    rendered = brief._compact(text, 60, reference=REFERENCE)
    assert rendered != text
    assert "[truncated," in rendered
    assert "more characters" in rendered
    assert f"full text in {REFERENCE}" in rendered


def test_compact_prefers_a_complete_sentence_boundary():
    text = "alpha beta gamma. delta epsilon zeta eta theta iota kappa."
    rendered = brief._compact(text, 20, reference=REFERENCE)
    assert rendered.startswith("alpha beta gamma.")


def test_compact_keeps_a_first_sentence_that_exceeds_the_limit():
    text = "a long first clause with no early stop and then. trailing words here."
    rendered = brief._compact(text, 20, reference=REFERENCE)
    assert rendered.startswith("a long first clause with no early stop and then.")


@pytest.mark.parametrize("boundary", [".", ";", ":"])
def test_compact_preserves_a_single_over_limit_sentence(boundary):
    text = (
        "one single sentence with no earlier boundary that still runs past "
        f"the limit{boundary}"
    )
    assert len(text) > 20
    rendered = brief._compact(text, 20, reference=REFERENCE)
    assert rendered == text
    assert "[truncated," not in rendered


def test_compact_preserves_over_limit_text_without_sentence_punctuation():
    text = " ".join(["qualification"] * 20)
    assert len(text) > 40
    rendered = brief._compact(text, 40, reference=REFERENCE)
    assert rendered == text
    assert "[truncated," not in rendered


def test_experiment_index_renders_hypothesis_assessment_in_full():
    assessment = (
        "partially supported on the reused panel only; the effect was not "
        "reproduced at the larger radii, so the mechanism remains uncertain"
    )
    result = {
        "index": 6,
        "kind": "training",
        "family": "f",
        "hypothesis_assessment": assessment,
    }
    text = "\n".join(brief._v4_experiment_index_section([result]))
    assert assessment in text
    assert "[truncated," not in text


def test_experiment_index_marks_and_points_at_truncated_fields():
    result = {
        "index": 6,
        "kind": "training",
        "family": "f",
        "parameter_changes": [
            {"path": "algorithm.learning_rate", "before": "0.0003", "after": "0.0001"},
            {"path": "algorithm.ent_coef", "before": "0.0", "after": "0.01"},
            {"path": "algorithm.batch_size", "before": "64", "after": "256"},
            {"path": "algorithm.n_epochs", "before": "10", "after": "4"},
        ],
    }
    text = "\n".join(brief._v4_experiment_index_section([result]))
    assert "[truncated," in text
    assert f"full text in {REFERENCE}" in text


def test_experiment_index_escapes_pipe_characters_instead_of_rewriting_them():
    result = {
        "index": 6,
        "kind": "training",
        "family": "f",
        "hypothesis_assessment": "supported | with caveats",
    }
    text = "\n".join(brief._v4_experiment_index_section([result]))
    assert "supported &#124; with caveats" in text
    assert "supported | with caveats" not in text


def test_measurement_round_question_preserves_its_line_structure():
    pending = {
        "experiment": 1,
        "evaluation_rounds": [
            {
                "round": 1,
                "question": "first line\nsecond line",
                "status": "completed",
                "results": {},
            }
        ],
    }
    text = "\n".join(brief._v4_measurement_rounds_section({}, [], pending))
    assert "- Question: first line\n  second line" in text


def test_measurement_selection_limit_accommodates_the_contract():
    selection = (
        "observed signal: the reused panel improved. "
        "why this model: it isolates the mechanism under study. "
        "decision it could change: " + "x" * 300
    )
    assert len(selection) > 300
    pending = {
        "experiment": 1,
        "evaluation_rounds": [
            {
                "round": 1,
                "question": "q",
                "status": "completed",
                "results": {
                    "research_evaluations": [
                        {
                            "candidate": "c1",
                            "selection": selection,
                        }
                    ]
                },
            }
        ],
    }
    text = "\n".join(brief._v4_measurement_rounds_section({}, [], pending))
    assert selection in text
    assert "[truncated," not in text


def test_rendered_brief_keeps_the_full_hypothesis_assessment(monkeypatch, tmp_path):
    assessment = (
        "partially supported on the reused panel only; the effect was not "
        "reproduced at the larger radii, so the mechanism remains uncertain"
    )
    state = {"schema_version": 4, "campaign": {"id": "cid", "base_commit": "base"}}
    (tmp_path / "current_params.json").write_text("{}", encoding="utf-8")
    (tmp_path / "postmortems.md").write_text("", encoding="utf-8")
    (tmp_path / "results.jsonl").write_text(
        json.dumps(
            {
                "index": 1,
                "kind": "training",
                "family": "f",
                "campaign_id": "cid",
                "hypothesis_assessment": assessment,
                "verdict": "trained",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "research_state.json").write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr("research.build_research_brief.RESEARCH_DIR", tmp_path)

    text = render_research_brief()
    assert assessment in text
