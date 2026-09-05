"""Reasoning contracts and revisable memory, without executing experiments."""

import json
import re
from pathlib import Path

import pytest

from research import build_research_brief as brief
from research import runner_protocol as protocol
from research.runner_repository import compact_result_record


@pytest.fixture
def proposal(scientific_reasoning):
    return {
        "kind": "training",
        "family": "learning.plateau",
        "hypothesis": "The update schedule causes the plateau.",
        "change": "Adjust the update schedule.",
        "initialization": "fresh",
        "reasoning": scientific_reasoning,
    }


@pytest.mark.parametrize("kind", ["training", "continuation", "replication"])
def test_every_research_training_kind_requires_reasoning(proposal, kind):
    proposal["kind"] = kind
    if kind != "training":
        proposal.pop("change")
    if kind == "continuation":
        proposal.update(initialization="transfer", training_parent="accepted")
    elif kind == "replication":
        proposal.update(training_seed=2, replication_of=1)
    protocol.validate_training_proposal(proposal, baseline=False)
    proposal.pop("reasoning")
    with pytest.raises(TypeError, match="reasoning must be an object"):
        protocol.validate_training_proposal(proposal, baseline=False)


@pytest.mark.parametrize(
    "field",
    [
        "alternative",
        "expected_observation",
        "contradicting_observation",
        "initialization_reason",
        "strategy_link",
    ],
)
@pytest.mark.parametrize("value", [None, " ", 1, [], {}])
def test_reasoning_requires_explanations_not_flags(proposal, field, value):
    proposal["reasoning"][field] = value
    with pytest.raises(ValueError, match=rf"reasoning\.{field}"):
        protocol.validate_training_proposal(proposal, baseline=False)


@pytest.mark.parametrize(
    "evidence",
    [
        None,
        [],
        {},
        ["file"],
        [{"source": "file"}],
        [{"source": "", "observation": "claim"}],
    ],
)
def test_evidence_pairs_sources_with_observations(proposal, evidence):
    proposal["reasoning"]["evidence"] = evidence
    with pytest.raises((TypeError, ValueError), match="reasoning.evidence"):
        protocol.validate_training_proposal(proposal, baseline=False)


def test_preflight_reads_current_memory_without_mutation(proposal, scientific_memory):
    before = scientific_memory.read_bytes()
    assert (
        protocol.validate_proposal_against_state(
            proposal, {"campaign": {"id": "current"}}
        )
        == "training"
    )
    assert scientific_memory.read_bytes() == before


@pytest.mark.parametrize(
    "source", ["missing.json", "../outside.txt", "C:/external.txt"]
)
def test_preflight_rejects_missing_or_external_sources(
    proposal, scientific_memory, source
):
    proposal["reasoning"]["evidence"][0]["source"] = source
    with pytest.raises(ValueError, match="does not exist|outside|relative"):
        protocol.validate_proposal_against_state(
            proposal, {"campaign": {"id": "current"}}
        )


def test_old_strategy_cannot_supply_current_campaign_memory(
    proposal, scientific_memory
):
    with pytest.raises(ValueError, match="Scientific strategy section"):
        protocol.validate_proposal_against_state(proposal, {"campaign": {"id": "new"}})


def test_missing_strategy_is_reported_not_generated(proposal, scientific_memory):
    scientific_memory.unlink()
    with pytest.raises(ValueError, match="Scientific strategy section"):
        protocol.validate_proposal_against_state(
            proposal, {"campaign": {"id": "current"}}
        )
    assert not scientific_memory.exists()


@pytest.mark.parametrize(
    "label",
    [
        "Direction",
        "Lessons and limits",
        "Open questions",
        "Conditional next steps",
        "Reconsider when",
    ],
)
def test_strategy_requires_each_meaningful_entry(proposal, scientific_memory, label):
    text = scientific_memory.read_text(encoding="utf-8")
    text = text.replace(f"**{label}:**", "**Unrelated:**")
    scientific_memory.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=label):
        protocol.validate_proposal_against_state(
            proposal, {"campaign": {"id": "current"}}
        )


def test_memory_is_separate_from_experiment_attestations(
    monkeypatch, scientific_memory
):
    experiment = (
        "## current / Experiment 7\n\n"
        "**Result:** Measured progress.\n\n"
        "**Evidence inspected:** evidence.txt\n\n"
    )
    strategy = scientific_memory.read_text(encoding="utf-8")
    scientific_memory.write_text(experiment + strategy, encoding="utf-8")
    section = protocol.postmortem_section(7, "current")
    assert "Scientific strategy" not in section
    assert protocol.attested_evidence_paths(section) == ["evidence.txt"]
    memories = brief._postmortem_memory(experiment + strategy, "current")
    assert len(memories) == 1
    assert "Conditional next steps" not in memories[0]
    # A later revision does not alter the historical experiment section.
    scientific_memory.write_text(
        experiment
        + strategy.replace("Investigate the plateau", "Investigate capacity"),
        encoding="utf-8",
    )
    assert protocol.postmortem_section(7, "current") == section


def test_duplicate_strategy_is_ambiguous(scientific_memory):
    text = scientific_memory.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        protocol.scientific_strategy_section(text + "\n" + text, "current")


def test_brief_exposes_current_strategy_without_old_campaign_or_truncation(
    monkeypatch, tmp_path, scientific_memory
):
    monkeypatch.setattr(brief, "RESEARCH_DIR", tmp_path)
    monkeypatch.setattr(brief, "ROOT", tmp_path)
    (tmp_path / "current_params.json").write_text("{}", encoding="utf-8")
    (tmp_path / "research_state.json").write_text(
        json.dumps({"campaign": {"id": "current"}}), encoding="utf-8"
    )
    text = scientific_memory.read_text(encoding="utf-8").replace(
        "## previous / Scientific strategy",
        "## previous / Scientific strategy\n\nNEVER IMPORT THIS",
    )
    scientific_memory.write_text(text, encoding="utf-8")
    rendered = brief.render_research_brief()
    assert "Investigate the plateau" in rendered
    assert "Continue if progress persists, otherwise inspect control" in rendered
    assert "NEVER IMPORT THIS" not in rendered
    assert rendered.index("Current scientific direction") < rendered.index(
        "Current status"
    )
    # Legacy histories remain readable without fabricated scientific conclusions.
    scientific_memory.write_text("# Research postmortems\n", encoding="utf-8")
    assert "No scientific strategy recorded" in brief.render_research_brief()


def test_history_preserves_reasoning_and_strategy_without_requiring_legacy_rewrite(
    proposal,
):
    record = {
        "index": 7,
        "reasoning": proposal["reasoning"],
        "scientific_strategy": "original direction",
    }
    assert compact_result_record(record) == record
    assert compact_result_record({"index": 1, "hypothesis": "legacy"}) == {
        "index": 1,
        "hypothesis": "legacy",
    }


def test_baseline_does_not_require_scientific_memory():
    assert (
        protocol.validate_proposal_against_state(
            {
                "baseline": True,
                "change": "Fresh baseline",
                "hypothesis": "Establish initial behavior",
                "initialization": "fresh",
            },
            {},
        )
        == "training"
    )


def test_documented_training_example_and_memory_match_the_contract(
    monkeypatch, tmp_path
):
    instruments = (
        Path(__file__).resolve().parents[2] / "research/instruments.md"
    ).read_text(encoding="utf-8")
    training = instruments.split("## Request training", 1)[1].split(
        "## Record the postmortem", 1
    )[0]
    proposal = json.loads(
        re.search(r"```json\n(.*?)\n```", training, re.DOTALL).group(1)
    )
    proposal.update(kind="training", initialization="fresh")
    for conditional in ("training_parent", "training_seed", "replication_of", "params"):
        proposal.pop(conditional)
    # Placeholder text represents researcher prose; only typed fields need values.
    proposal["reasoning"]["evidence"][0]["source"] = "evidence.txt"
    protocol.validate_training_proposal(proposal, baseline=False)
    memory_docs = instruments.split("## Record the postmortem", 1)[1]
    strategy = re.search(r"```markdown\n(.*?)\n```", memory_docs, re.DOTALL).group(1)
    memory = tmp_path / "postmortems.md"
    memory.write_text(strategy.replace("<Campaign ID>", "current"), encoding="utf-8")
    (tmp_path / "evidence.txt").write_text("Observed facts", encoding="utf-8")
    monkeypatch.setattr("research.runner_paths.POSTMORTEM_PATH", memory)
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    assert (
        protocol.validate_proposal_against_state(
            proposal, {"campaign": {"id": "current"}}
        )
        == "training"
    )
