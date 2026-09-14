"""Focused tests for the isolated final-benchmark evidence bundle."""

import json
from pathlib import Path

import pytest

from research.build_research_brief import _render_v4_research_brief
from research.runner_evidence_review import (
    _copy_review_bundle,
    _parse_response,
    _review_message,
)


def _configured_bundle(monkeypatch, tmp_path, artifact_count: int):
    research_directory = tmp_path / "research"
    research_directory.mkdir()
    (research_directory / "scenario.md").write_text("objective", encoding="utf-8")
    artifacts = []
    for index in range(artifact_count):
        artifact = tmp_path / f"source-{index}.json"
        artifact.write_text(json.dumps({"index": index}), encoding="utf-8")
        artifacts.append(artifact.name)
    monkeypatch.setattr("research.runner_paths.ROOT", tmp_path)
    monkeypatch.setattr("research.runner_paths.RESEARCH_DIR", research_directory)
    return {"candidate": "best", "evaluation_artifacts": artifacts}


def test_copy_review_bundle_accepts_one_evaluation_artifact(monkeypatch, tmp_path):
    best_known = _configured_bundle(monkeypatch, tmp_path, 1)

    _, paths = _copy_review_bundle(best_known, tmp_path / "bundle")

    assert paths == ["scenario.md", "evaluations/evaluation-001.json"]
    assert (tmp_path / "bundle" / paths[1]).is_file()


@pytest.mark.parametrize("artifact_count", [2, 3])
def test_copy_review_bundle_accepts_multiple_evaluation_artifacts(
    monkeypatch, tmp_path, artifact_count
):
    best_known = _configured_bundle(monkeypatch, tmp_path, artifact_count)

    _, paths = _copy_review_bundle(best_known, tmp_path / "bundle")

    assert paths == [
        "scenario.md",
        *[f"evaluations/evaluation-{index:03}.json" for index in range(1, artifact_count + 1)],
    ]
    assert all((tmp_path / "bundle" / path).is_file() for path in paths)


def test_copy_review_bundle_rejects_an_empty_evaluation_artifact_list(
    monkeypatch, tmp_path
):
    best_known = _configured_bundle(monkeypatch, tmp_path, 0)

    with pytest.raises(ValueError, match="identify evaluation artifacts"):
        _copy_review_bundle(best_known, tmp_path / "bundle")


def test_review_message_names_every_copied_file_and_requires_view():
    paths = [
        "scenario.md",
        "evaluations/evaluation-001.json",
        "evaluations/evaluation-002.json",
        "evaluations/evaluation-003.json",
    ]

    message = _review_message("best", paths)

    assert "Read every listed file with the view tool before deciding:" in message
    assert all(path in message for path in paths)


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (
            (
                "Performance is consistent across the recorded panels.\n"
                "DECISION: APPROVE_FINAL"
            ),
            ("APPROVE_FINAL", "Performance is consistent across the recorded panels."),
        ),
        (
            (
                "Recorded failures remain structured and material.\n"
                "DECISION: REJECT_FINAL"
            ),
            ("REJECT_FINAL", "Recorded failures remain structured and material."),
        ),
        (
            (
                "Performance is high.\nUncertainty is bounded.\n\n"
                "DECISION: APPROVE_FINAL"
            ),
            ("APPROVE_FINAL", "Performance is high. Uncertainty is bounded."),
        ),
    ],
)
def test_parse_response_preserves_a_normalized_rationale(response, expected):
    assert _parse_response(response) == expected


@pytest.mark.parametrize(
    "response",
    [
        "APPROVE_FINAL",
        "REJECT_FINAL",
        "Recorded evidence is sufficient.",
        "Reason.\nDECISION: APPROVE_FINAL\nDECISION: REJECT_FINAL",
        "Reason.\nDECISION: APPROVE_FINAL\nTrailing text.",
    ],
)
def test_parse_response_rejects_missing_ambiguous_or_trailing_decisions(response):
    with pytest.raises(RuntimeError):
        _parse_response(response)


def _brief_with_review(review_fingerprint: str) -> str:
    best_known = {
        "artifact": "research/checkpoints/retained/campaign/best",
        "fingerprint": "current-fingerprint",
        "origin_experiment": 4,
        "candidate": "checkpoint-100",
        "parameters": {},
        "scientific_commit": "abc123",
        "training_steps": 100,
        "evaluation_artifacts": ["research/evaluations/panel.json"],
        "reason": "Best recorded evidence.",
    }
    state = {
        "schema_version": 4,
        "working_lineage": best_known.copy(),
        "best_known_lineage": best_known,
        "retained_lineages": [],
        "last_verdict": "final benchmark rejected by isolated evidence review",
        "final_benchmark_review": {
            "experiment": 4,
            "fingerprint": review_fingerprint,
            "decision": "REJECT_FINAL",
            "rationale": "Failures remain structured.",
        },
    }
    return _render_v4_research_brief(
        state,
        [],
        "",
        "campaign",
        "base",
        "method",
        {},
    )


def test_matching_review_is_scoped_to_the_best_known_artifact():
    brief = _brief_with_review("current-fingerprint")
    current_phase = brief.split("## Current phase and latest event", 1)[1].split(
        "## Latest experiment", 1
    )[0]
    best_known = brief.split("## Best-known model", 1)[1]

    assert "Terminal review of this artifact" not in current_phase
    assert "Review basis:" not in current_phase
    assert "- Terminal review of this artifact after experiment 4: REJECT_FINAL" in best_known
    assert "- Review basis: Failures remain structured." in best_known


def test_review_for_a_different_best_known_artifact_is_not_rendered():
    brief = _brief_with_review("old-fingerprint")

    assert "Terminal review of this artifact" not in brief
    assert "Review basis: Failures remain structured." not in brief


def test_lifecycle_documentation_describes_review_approval_and_rejection():
    root = Path(__file__).resolve().parents[2]
    program = (root / "research" / "program.md").read_text(encoding="utf-8")
    instruments = (root / "research" / "instruments.md").read_text(encoding="utf-8")

    assert "Approval runs the final benchmark" in program
    assert "rejection returns the campaign to\nresearch without exposing final-benchmark evidence" in program
    assert "requests the isolated readiness\nreview of `best_known`" in instruments
    assert "Approval executes the terminal\nofficial benchmark" in instruments
    assert "Rejection does not execute the benchmark" in instruments
    assert "Setting it to `true` requests terminal assessment" not in instruments