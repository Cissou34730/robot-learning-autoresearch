"""Focused tests for the isolated final-benchmark evidence bundle."""

import json

import pytest

from research.runner_evidence_review import _copy_review_bundle, _review_message


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