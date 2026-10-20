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


def test_pi_contract_reads_route_to_harness_without_write_access(
    split_roots, monkeypatch
):
    from runner.copilot import path_policy
    from runner.copilot.tool_policy import scoped_tool_hook

    harness, campaign = split_roots
    monkeypatch.setattr(path_policy, "ROOT", campaign)
    contract = harness / "contracts" / "scenario.md"
    contract.parent.mkdir()
    contract.write_text("task", encoding="utf-8")
    hook = scoped_tool_hook()
    decision = hook(
        {"toolName": "view", "toolArgs": {"path": "contracts/scenario.md"}}, {}
    )
    assert decision["modifiedArgs"]["path"] == str(contract)
    assert path_policy.file_read_denial(str(contract)) is None
    assert path_policy.file_edit_denial(str(contract))
    assert path_policy.file_read_denial(str(campaign / "contracts/scenario.md"))
    assert path_policy.file_read_denial(str(harness / "runner/execution.py"))
    assert path_policy.file_edit_denial(str(harness / "robot_learning/train.py"))


def test_scoped_search_covers_both_roots_but_prunes_reserved_files(
    split_roots, monkeypatch
):
    from runner.copilot import path_policy
    from runner.copilot.copilot_scoped_search import GlobParams, ScopedSearch

    harness, campaign = split_roots
    monkeypatch.setattr(path_policy, "ROOT", campaign)
    for root, relative in (
        (harness, "AGENTS.md"),
        (harness, "contracts/scenario.md"),
        (harness, "tests/secret.py"),
        (campaign, "robot_learning/lab/probe.py"),
        (campaign, "contracts/shadow.md"),
    ):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("content", encoding="utf-8")
    search = ScopedSearch(campaign, path_policy.file_read_denial, None, lambda _i: None)
    result = search.glob(GlobParams(pattern="**/*"), None).replace("\\", "/")
    assert "contracts/scenario.md" in result
    assert "robot_learning/lab/probe.py" in result
    assert "secret" not in result
    assert "AGENTS" not in result
    assert "shadow" not in result
    assert search.target("contracts/scenario.md") == harness / "contracts/scenario.md"


@pytest.mark.parametrize("preliminary", [False, True])
@pytest.mark.parametrize(
    "relative",
    ["contracts/scenario.md", "contracts/robots/arm.xml", "contracts/authority.md"],
)
def test_campaign_absolute_contract_reads_route_before_authorization(
    split_roots, monkeypatch, preliminary, relative
):
    from runner.copilot import path_policy
    from runner.copilot.tool_policy import scoped_tool_hook

    harness, campaign = split_roots
    monkeypatch.setattr(path_policy, "ROOT", campaign)
    contract = harness / relative
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text("protected contract", encoding="utf-8")
    hook = scoped_tool_hook(preliminary=preliminary)
    decision = hook(
        {
            "toolName": "view",
            "toolArgs": {"path": str(campaign / relative), "view_range": [1, 1]},
        },
        {},
    )
    assert decision == {"modifiedArgs": {"path": str(contract), "view_range": [1, 1]}}
    assert (
        Path(decision["modifiedArgs"]["path"]).read_text(encoding="utf-8")
        == "protected contract"
    )


def test_campaign_absolute_search_paths_route_to_harness(split_roots, monkeypatch):
    from runner.copilot import path_policy
    from runner.copilot.copilot_scoped_search import GlobParams, ScopedSearch

    harness, campaign = split_roots
    monkeypatch.setattr(path_policy, "ROOT", campaign)
    contract = harness / "contracts/scenario.md"
    contract.parent.mkdir()
    contract.write_text("task", encoding="utf-8")
    search = ScopedSearch(campaign, path_policy.file_read_denial, None, lambda _i: None)
    assert search.target(str(campaign / "contracts/scenario.md")) == contract
    result = search.glob(
        GlobParams(pattern="**/*.md", paths=str(campaign / "contracts")), None
    )
    assert "scenario.md" in result


def test_absolute_read_routing_keeps_shadow_and_reserved_paths_denied(
    split_roots, monkeypatch
):
    from runner.copilot import path_policy
    from runner.copilot.tool_policy import scoped_tool_hook

    harness, campaign = split_roots
    monkeypatch.setattr(path_policy, "ROOT", campaign)
    shadow = campaign / "contracts/scenario.md"
    shadow.parent.mkdir()
    shadow.write_text("shadow", encoding="utf-8")
    hook = scoped_tool_hook(preliminary=True)
    for target in (
        shadow,
        campaign / "runner/execution.py",
        campaign / "tests/private.py",
        campaign / "docs/private.md",
        campaign / "AGENTS.md",
        campaign / "README.md",
        campaign / "contracts/../../outside.md",
    ):
        decision = hook({"toolName": "view", "toolArgs": {"path": str(target)}}, {})
        assert decision["permissionDecision"] == "deny"
    assert path_policy.file_edit_denial(str(campaign / "AGENTS.md"), preliminary=True)
    assert path_policy.file_edit_denial(str(harness / "AGENTS.md"), preliminary=True)


def test_recipe_task_identity_is_checked_against_the_current_harness(
    split_roots, monkeypatch
):
    for relative in reset_campaign.TASK_COMPATIBILITY_PATHS:
        target = paths.locate(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("task definition", encoding="utf-8")
    recorded = reset_campaign.task_contract()
    monkeypatch.setattr(reset_campaign, "git_json", lambda *_args: recorded)
    reset_campaign.verify_task_compatibility("baseline")
    paths.locate("contracts/task_spec.py").write_text(
        "different task", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="task differs"):
        reset_campaign.verify_task_compatibility("baseline")


def test_trusted_runtime_uses_each_repositories_own_head(split_roots, monkeypatch):
    selected = []
    monkeypatch.setattr(repository, "git", lambda *_args: "campaign-head")
    monkeypatch.setattr(repository, "harness_git", lambda *_args: "harness-head")
    monkeypatch.setattr(repository, "require_resolvable_commit", lambda _commit: None)
    monkeypatch.setattr(
        repository,
        "require_path_at_commit",
        lambda commit, relative: selected.append((commit, relative)),
    )
    repository.require_paths_at_head(
        ["contracts/task_spec.py", "robot_learning/__init__.py"]
    )
    assert selected == [
        ("harness-head", "contracts/task_spec.py"),
        ("campaign-head", "robot_learning/__init__.py"),
    ]
