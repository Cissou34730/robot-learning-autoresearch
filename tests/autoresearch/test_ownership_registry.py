"""Ownership classifications must match the files that exist.

Issue #41 finding 1: ownership is a hand-maintained registry. A declared path
that no longer exists silently changes which files define evaluation semantics,
so the registry is checked directly.
"""

import re
from pathlib import Path

import pytest

from runner import paths, protocol

ROOT = Path(__file__).resolve().parents[2]


def test_every_declared_classification_exists_on_disk(monkeypatch):
    monkeypatch.setattr(paths, "SPLIT", paths.ROOT != paths.HARNESS_ROOT)
    assert protocol.declared_paths_exist() == []


def test_a_missing_declared_path_is_reported(monkeypatch):
    monkeypatch.setattr(paths, "SPLIT", paths.ROOT != paths.HARNESS_ROOT)
    monkeypatch.setattr(
        protocol,
        "PROTECTED_RUNNER_PATHS",
        {"research/does_not_exist.py"},
    )
    assert protocol.declared_paths_exist() == ["research/does_not_exist.py"]


def test_campaign_lab_is_owned_but_not_part_of_recipe_identity():
    path = "robot_learning/lab/diagnose.py"
    assert protocol.is_researcher_owned(path)
    assert protocol.is_campaign_lab(path)
    from runner import repository

    assert repository.scientific_change_paths([path]) == []
    assert repository.researcher_change_paths([path]) == [path]


@pytest.mark.parametrize(
    ("path", "owned"),
    [
        ("robot_learning/scenario/new.py", True),
        ("robot_learning/training/new.py", True),
        ("robot_learning/lab/new.py", True),
        ("robot_learning/train.py", True),
        ("robot_learning/evaluate.py", True),
        ("robot_learning/play.py", True),
        ("robot_learning/training/current_params.json", True),
        ("robot_learning/training/__init__.py", True),
        ("robot_learning/training/__INIT__.py", True),
        ("robot_learning/scenario/__init__.py", False),
        ("robot_learning/scenario/__INIT__.py", False),
        ("robot_learning/ScEnArIo/__iNiT__.Py", False),
        ("robot_learning/__init__.py", False),
        ("robot_learning/__INIT__.py", False),
        ("robot_learning/extra.py", False),
        ("contracts/authority.md", False),
        ("benchmark/adapters/final_benchmark.py", False),
        ("runner/protocol.py", False),
        ("pi_workspace/operation_request.json", False),
    ],
)
@pytest.mark.parametrize("variant", [None, "pd_servo", "pd_abs"])
def test_runner_and_copilot_agree_on_scientific_file_ownership(path, owned, variant):
    from runner.copilot.path_policy import coding_file_scope, is_pi_writable_path
    from runner.launcher.trust import is_pi_writable

    if path == "pi_workspace/operation_request.json" and not variant:
        owned = True
    if variant:
        path = f"robot_learning/variants/{variant}/" + path.removeprefix(
            "robot_learning/"
        )

    assert protocol.is_researcher_owned(path) is owned
    assert is_pi_writable_path(path) is owned
    assert is_pi_writable(path, preliminary=False) is owned
    assert not is_pi_writable_path(path, preliminary=True)
    assert not is_pi_writable(path, preliminary=True)
    if owned and path != "pi_workspace/operation_request.json":
        assert coding_file_scope([path], writable=True) == frozenset({path.casefold()})
    else:
        with pytest.raises(ValueError):
            coding_file_scope([path], writable=True)


@pytest.mark.parametrize("path", ["AGENTS.md", "agents.md", "AgEnTs.Md"])
def test_mixed_case_context_paths_remain_protected(path):
    assert protocol.is_protected_source(path)
    assert protocol.is_human_owned(path)


@pytest.mark.parametrize(
    "path",
    [
        "robot_learning/variants/PD/scenario/policy_io.py",
        "Robot_Learning/Variants/PD/scenario/policy_io.py",
        "robot_learning/variants/1pd/scenario/policy_io.py",
        "robot_learning/variants/pd-servo/scenario/policy_io.py",
        "robot_learning/variants/abcdefghijklmnopq/scenario/policy_io.py",
        "robot_learning/variants//scenario/policy_io.py",
        "robot_learning/variants/pd/variants/other/scenario/policy_io.py",
        "Robot_Learning/Variants/pd/Variants/other/scenario/policy_io.py",
        "robot_learning/variants/../scenario/policy_io.py",
        "Robot_Learning/Variants/../scenario/policy_io.py",
        "robot_learning/variants/pd/scenario/../__init__.py",
        "robot_learning/variants/pd/../../pi_workspace/operation_request.json",
        "robot_learning/variants/pd/../../../pi_workspace/scientific_model.md",
    ],
)
def test_invalid_variant_paths_are_not_authorized(path):
    from runner.copilot.path_policy import (
        coding_file_scope,
        file_edit_denial,
        is_pi_writable_path,
    )
    from runner.launcher.trust import is_pi_writable

    assert not protocol.is_researcher_owned(path)
    assert not is_pi_writable(path, preliminary=False)
    assert not is_pi_writable_path(path)
    assert not is_pi_writable_path(path, preliminary=True)
    assert not is_pi_writable(path, preliminary=True)
    assert file_edit_denial(path)
    assert file_edit_denial(path, preliminary=True)
    with pytest.raises(ValueError):
        coding_file_scope([path], writable=True)


def test_linked_variant_file_cannot_enter_the_coding_scope(monkeypatch, tmp_path):
    from runner.copilot import path_policy
    from runner.launcher.trust import protected_files

    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(path_policy, "ROOT", tmp_path)
    original = tmp_path / "original.py"
    original.write_text("VALUE = 1\n", encoding="utf-8")
    relative = "robot_learning/variants/pd_servo/scenario/policy_io.py"
    linked = tmp_path / relative
    linked.parent.mkdir(parents=True)
    linked.hardlink_to(original)

    assert path_policy.file_edit_denial(relative)
    with pytest.raises(ValueError):
        path_policy.coding_file_scope([relative], writable=True)
    assert relative in protected_files(tmp_path, preliminary=False)


def test_internal_operation_exchange_is_not_a_coding_child_write():
    from runner.copilot.path_policy import coding_file_scope

    path = "pi_workspace/operation_request.json"
    assert protocol.is_researcher_owned(path)
    with pytest.raises(ValueError):
        coding_file_scope([path], writable=True)


def test_campaign_lab_publication_has_separate_provenance(monkeypatch, tmp_path):
    from runner import repository

    lab = tmp_path / "robot_learning" / "lab"
    lab.mkdir(parents=True)
    (lab / "diagnose.py").write_text("VALUE = 1\n", encoding="utf-8")
    committed = []
    validated = []
    monkeypatch.setattr("runner.paths.ROOT", tmp_path)
    monkeypatch.setattr(
        repository,
        "status_paths",
        lambda scope: ["robot_learning/lab/diagnose.py"],
    )
    monkeypatch.setattr(
        repository,
        "commit_paths",
        lambda message, scope: committed.append((message, scope)) or True,
    )
    monkeypatch.setattr(
        "runner.execution.validate_changed_sources",
        lambda scope: validated.append(scope),
    )
    monkeypatch.setattr(repository, "git", lambda *args: "lab-commit\n")

    provenance = repository.publish_campaign_laboratory("M2")

    assert validated == [["robot_learning/lab/diagnose.py"]]
    assert committed == [
        ("camp: M2 measurement tools", ["robot_learning/lab/diagnose.py"])
    ]
    assert provenance["commit"] == "lab-commit"
    assert provenance["manifest"][0]["path"] == "robot_learning/lab/diagnose.py"


def test_campaign_lab_is_validated_before_it_is_committed(monkeypatch, tmp_path):
    from runner import repository

    lab = tmp_path / "robot_learning" / "lab"
    lab.mkdir(parents=True)
    (lab / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    committed = []
    monkeypatch.setattr("runner.paths.ROOT", tmp_path)
    monkeypatch.setattr(
        repository,
        "status_paths",
        lambda scope: ["robot_learning/lab/broken.py"],
    )
    monkeypatch.setattr(
        repository,
        "commit_paths",
        lambda message, scope: committed.append((message, scope)) or True,
    )

    with pytest.raises(RuntimeError, match="invalid Python syntax"):
        repository.publish_campaign_laboratory("M2")

    assert committed == []


def test_every_documented_human_owned_path_is_enforced(monkeypatch):
    """The authority contract and the enforced classification must not drift.

    Issue #58: the documentation called the whole benchmark package human-owned
    while enforcement listed files by hand and omitted two. Each documented
    literal, directory and glob is resolved against the repository so that a
    typo or a moved path fails here, and every resolved path must be classified
    human-owned.
    """
    monkeypatch.setattr(paths, "SPLIT", paths.ROOT != paths.HARNESS_ROOT)
    text = (ROOT / "contracts" / "authority.md").read_text(encoding="utf-8")
    section = text.split("## Human-owned paths", 1)[1].split("\n## ", 1)[0]
    listing = section[section.index("- ") :].split("\n\n", 1)[0]
    documented = re.findall(r"`([^`]+)`", listing)

    assert documented
    resolved: list[str] = []
    for entry in documented:
        assert not entry.startswith("/"), entry
        if any(wildcard in entry for wildcard in "*?["):
            matches = sorted(
                paths.logical_path(path)
                for path in paths.locate(Path(entry).parent).glob(Path(entry).name)
            )
            assert matches, f"documented glob matches nothing: {entry}"
            resolved.extend(matches)
        elif entry.endswith("/"):
            directory = paths.locate(entry.rstrip("/"))
            assert directory.is_dir(), f"documented directory is missing: {entry}"
            resolved.extend(
                paths.logical_path(path)
                for path in directory.rglob("*")
                if path.is_file()
            )
        else:
            if entry not in protocol.CAMPAIGN_SCOPED_PROTECTED_CONTEXT_PATHS:
                assert paths.locate(entry).is_file(), (
                    f"documented path is missing: {entry}"
                )
            resolved.append(entry)

    assert resolved
    for relative in resolved:
        assert protocol.is_human_owned(relative), relative
