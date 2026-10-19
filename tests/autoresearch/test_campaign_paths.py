"""Physical repository separation preserves logical paths and ownership."""

import pytest

from runner import paths


@pytest.fixture
def split_roots(monkeypatch, tmp_path):
    harness = tmp_path / "harness"
    campaign = tmp_path / "campaign"
    harness.mkdir()
    campaign.mkdir()
    monkeypatch.setattr(paths, "HARNESS_ROOT", harness)
    monkeypatch.setattr(paths, "ROOT", campaign)
    monkeypatch.setattr(paths, "SPLIT", True)
    return harness, campaign


def test_paths_resolve_to_their_owning_repository(split_roots):
    harness, campaign = split_roots
    for relative in ("contracts/program.md", "runner/execution.py", "tests/test.py"):
        assert paths.locate(relative) == harness / relative
        assert paths.logical_path(harness / relative) == relative
    for relative in (
        "robot_learning/train.py",
        "campaigns/results.jsonl",
        "runner/state/research_state.json",
        "pi_workspace/scientific_model.md",
        "models/candidates/model.zip",
        "reports/usage.json",
    ):
        assert paths.locate(relative) == campaign / relative
        assert paths.logical_path(campaign / relative) == relative


def test_shadow_copies_and_outside_paths_are_rejected(split_roots, tmp_path):
    harness, campaign = split_roots
    for target in (
        campaign / "contracts/program.md",
        harness / "robot_learning/train.py",
        tmp_path / "outside.py",
    ):
        with pytest.raises(ValueError, match="owning repository"):
            paths.logical_path(target)


@pytest.mark.parametrize(
    "relative",
    ["../outside", r"contracts\..\outside", r"C:\outside", "/outside", "file:stream"],
)
def test_logical_paths_cannot_escape_their_root(split_roots, relative):
    with pytest.raises(ValueError, match="must be relative"):
        paths.locate(relative)


def test_single_folder_mode_keeps_the_existing_layout(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "SPLIT", False)
    assert paths.locate("contracts/program.md") == tmp_path / "contracts/program.md"
    assert (
        paths.logical_path(tmp_path / "robot_learning/train.py")
        == "robot_learning/train.py"
    )
