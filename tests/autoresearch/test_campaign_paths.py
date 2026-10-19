"""Physical repository separation preserves logical paths and ownership."""

import json
from pathlib import Path

import pytest

from runner import paths, repository, reset_campaign


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


def test_repository_paths_use_logical_ownership(split_roots):
    harness, campaign = split_roots
    assert (
        repository.resolve_repo_path("contracts/task_spec.py")
        == harness / "contracts/task_spec.py"
    )
    assert (
        repository.resolve_repo_path("robot_learning/train.py")
        == campaign / "robot_learning/train.py"
    )
    assert (
        repository.repo_relative_path(harness / "contracts/task_spec.py")
        == "contracts/task_spec.py"
    )


def test_split_campaign_publication_never_pushes(split_roots, monkeypatch):
    monkeypatch.setattr(
        repository,
        "git",
        lambda *_args: pytest.fail("No network Git operation is allowed"),
    )
    repository.push_head()


def test_split_reset_does_not_require_a_remote(split_roots, monkeypatch):
    calls = []

    def git(*args):
        calls.append(args)
        return ""

    monkeypatch.setattr(reset_campaign, "git", git)
    reset_campaign.ensure_clean_repository()
    assert not any("remote" in call for call in calls)


def test_child_python_loads_campaign_science_and_harness_packages(
    split_roots, monkeypatch
):
    from runner import execution

    _, campaign = split_roots
    # Use the actual harness for the runner and contracts packages.
    monkeypatch.setattr(paths, "HARNESS_ROOT", Path(__file__).resolve().parents[2])
    package = campaign / "robot_learning"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "probe.py").write_text(
        "import json, robot_learning, runner, contracts\n"
        "print(json.dumps([robot_learning.__file__, runner.__file__, contracts.__file__]))\n",
        encoding="utf-8",
    )
    origins = json.loads(execution.run_module("robot_learning.probe"))
    assert origins[0] == str(package / "__init__.py")
    assert all(str(paths.HARNESS_ROOT) in origin for origin in origins[1:])
