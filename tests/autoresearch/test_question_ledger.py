"""The Experiment Question and Evidence Ledger, from proposal to closure.

One persistent ledger carries the experiment's question, its expected
observation and its cited motivation. The Runner freezes and persists it, links
measurement rounds to it by identity and artifact reference, and requires a
Researcher-authored disposition at closure without judging the evidence.
"""

import pytest

from research import build_research_brief as brief
from research import runner_protocol as protocol


def _proposal() -> dict:
    return {
        "kind": "training",
        "family": "inner-radius",
        "hypothesis": "Fewer failures below 14 cm without outer regression.",
        "initialization": "fresh",
        "reasoning": {
            "evidence": [
                {"source": "a.json", "observation": "inner failures observed"}
            ],
            "expected_observation": "Inner failures fall with no outer regression.",
            "initialization_reason": "fresh training isolates the radius effect.",
            "objective_link": "Removes a failure mode relevant to the objective.",
        },
        "change": "adjust the inner radius",
    }


def _request(addresses: str | None = None) -> dict:
    request = {
        "experiment": 1,
        "question": "q",
        "reason": "r",
        "measurements": [
            {
                "instrument": "research_evaluation",
                "candidate": "checkpoint",
                "episodes": 2,
                "seed": 10,
                "selection": "useful for the current question",
            }
        ],
    }
    if addresses is not None:
        request["addresses"] = addresses
    return request


def test_question_ledger_is_derived_and_identified_by_the_proposal():
    ledger = protocol.question_ledger(_proposal(), 3, "abc")

    assert ledger["ledger_id"] == "abc"
    assert ledger["experiment"] == 3
    assert ledger["question"] == (
        "Fewer failures below 14 cm without outer regression."
    )
    assert ledger["expected_observation"].startswith("Inner failures")
    assert ledger["motivation"][0]["source"] == "a.json"
    assert ledger["revisions"] == []
    assert ledger["disposition"] is None


def test_scientific_question_also_forms_the_ledger():
    proposal = _proposal()
    proposal.pop("hypothesis")
    proposal["scientific_question"] = "Which radius removes inner failures?"

    ledger = protocol.question_ledger(proposal, 1, "id")

    assert ledger["question"] == "Which radius removes inner failures?"


def test_question_revision_is_recorded_with_provenance():
    ledger = protocol.question_ledger(_proposal(), 1, "id")
    revision = protocol.validate_question_revision(
        {
            "question": "Does the failure persist above 14 cm?",
            "reason": "The panel recorded no inner failures.",
            "evidence": [{"source": "b.json", "observation": "no inner failures"}],
        }
    )

    protocol.apply_question_revision(ledger, revision)

    assert ledger["question"] == "Does the failure persist above 14 cm?"
    assert ledger["revisions"][0]["reason"].startswith("The panel")
    assert ledger["revisions"][0]["evidence"][0]["source"] == "b.json"


@pytest.mark.parametrize(
    "revision",
    [
        {"reason": "no question"},
        {"question": "q"},
        {"question": "q", "reason": "r", "extra": 1},
        {"question": "q", "reason": "r", "evidence": [{}]},
    ],
)
def test_question_revision_requires_its_shape(revision):
    with pytest.raises((TypeError, ValueError)):
        protocol.validate_question_revision(revision)


def test_analysis_request_requires_an_address():
    with pytest.raises(ValueError, match="addresses"):
        protocol.validate_evaluation_request(
            _request(), require_experiment_address=True
        )


@pytest.mark.parametrize("addresses", ["expected_observation", "exploratory"])
def test_analysis_request_accepts_both_addresses(addresses):
    protocol.validate_evaluation_request(
        _request(addresses), require_experiment_address=True
    )


def test_analysis_request_rejects_an_unknown_address():
    with pytest.raises(ValueError, match="addresses"):
        protocol.validate_evaluation_request(
            _request("confirmatory"), require_experiment_address=True
        )


def test_preparation_request_need_not_carry_an_address():
    protocol.validate_evaluation_request(_request())


def test_disposition_must_name_an_enumerated_label_with_evidence():
    parsed = protocol.parse_expected_observation_disposition(
        "not tested - the panel recorded no inner failures for any model."
    )

    assert parsed["disposition"] == "not tested"
    assert parsed["evidence"].startswith("the panel")


@pytest.mark.parametrize("value", ["inconclusive - maybe", "supported", "supported "])
def test_disposition_rejects_unknown_or_uncited_values(value):
    with pytest.raises(ValueError):
        protocol.parse_expected_observation_disposition(value)


def test_closed_postmortem_requires_a_disposition_field(monkeypatch, tmp_path):
    postmortem = tmp_path / "postmortems.md"
    postmortem.write_text(
        "## Experiment 2 / measured\n\n"
        "**Hypothesis assessment:** partly supported.\n\n"
        "**Expected observation disposition:** supported - 199 of 200 episodes.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("research.runner_paths.POSTMORTEM_PATH", postmortem)

    assessment = protocol.validate_postmortem_evidence(
        2, [], require_disposition=True
    )

    assert assessment.startswith("partly")
    assert protocol.expected_observation_disposition(2) == {
        "disposition": "supported",
        "evidence": "199 of 200 episodes.",
    }


def test_postmortem_without_a_disposition_is_rejected(monkeypatch, tmp_path):
    postmortem = tmp_path / "postmortems.md"
    postmortem.write_text(
        "## Experiment 2 / measured\n\n"
        "**Hypothesis assessment:** partly supported.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("research.runner_paths.POSTMORTEM_PATH", postmortem)

    with pytest.raises(ValueError, match="Expected observation disposition"):
        protocol.validate_postmortem_evidence(2, [], require_disposition=True)


def test_brief_renders_the_frozen_question_before_metrics():
    result = {
        "question_ledger": {
            "question": "Fewer failures below 14 cm?",
            "expected_observation": "Inner failures fall.",
            "revisions": [],
            "disposition": None,
        }
    }

    lines = brief._question_ledger_lines(brief._question_ledger_view(result))

    assert lines[0].startswith("- Experiment question (frozen):")
    assert lines[1].startswith("- Expected observation (frozen):")


def test_brief_falls_back_to_historical_proposal_fields():
    result = {
        "hypothesis": "Older question.",
        "reasoning": {"expected_observation": "Older expected observation."},
    }

    lines = brief._question_ledger_lines(brief._question_ledger_view(result))

    assert lines[0] == "- Experiment question (frozen): Older question."
    assert lines[1].startswith("- Expected observation (frozen): Older expected")
