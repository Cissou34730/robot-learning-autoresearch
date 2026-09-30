"""Scoped Git publication without oversized process arguments."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from research import runner_paths as paths
from research import runner_repository as repository


def _remove_readonly(function, value, error):
    path = Path(value)
    if (
        os.name != "nt"
        or not isinstance(error[1], PermissionError)
        or not path.is_file()
        or not path.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY
    ):
        raise error[1]
    path.chmod(stat.S_IWRITE)
    function(value)


@pytest.fixture
def git_repository(monkeypatch):
    # Windows Git cannot access pytest's mode-0o700 temporary directories.
    root = Path(tempfile.gettempdir()) / f"robot-learning-git-test-{uuid4().hex}"
    root.mkdir()
    monkeypatch.setattr(paths, "ROOT", root)
    count = int(os.environ.get("GIT_CONFIG_COUNT", "0"))
    monkeypatch.setenv("GIT_CONFIG_COUNT", str(count + 1))
    monkeypatch.setenv(f"GIT_CONFIG_KEY_{count}", "safe.directory")
    monkeypatch.setenv(f"GIT_CONFIG_VALUE_{count}", str(root))
    try:
        repository.git("init", "--quiet")
        repository.git("config", "user.name", "Tests")
        repository.git("config", "user.email", "tests@example.invalid")
        repository.git("config", "commit.gpgsign", "false")
        monkeypatch.setattr(repository, "push_head", lambda: None)
        yield root
    finally:
        shutil.rmtree(root, onerror=_remove_readonly)


def test_large_publication_commits_only_requested_paths(git_repository):
    root = git_repository
    for name in ("unrelated.txt", "literal-a.txt", "obsolete[ab].txt"):
        (root / name).write_text("original", encoding="utf-8")
    repository.git("add", "--", ".")
    repository.git("commit", "--quiet", "-m", "baseline")
    (root / "unrelated.txt").write_text("unrelated staged edit", encoding="utf-8")
    (root / "literal-a.txt").write_text("unrelated unstaged edit", encoding="utf-8")
    repository.git("add", "--", "unrelated.txt")
    (root / "obsolete[ab].txt").unlink()
    scope = [
        "obsolete[ab].txt",
        "literal-[ab].txt",
        "space name.txt",
        "unicode-\u00e9.txt",
    ]
    for name in scope[1:]:
        (root / name).write_text("requested", encoding="utf-8")
    for index in range(400):
        name = f"checkpoint-{index:04d}-{'x' * 80}.json"
        (root / name).write_text("{}", encoding="utf-8")
        scope.append(name)
    expanded = subprocess.list2cmdline(["git", "add", "-A", "--", *scope])
    assert len(expanded.encode("utf-16-le")) // 2 + 1 > (
        repository.WINDOWS_COMMAND_LINE_LIMIT
    )

    assert repository.commit_paths("scoped publication", scope)

    committed = set(
        repository.git("diff-tree", "--no-commit-id", "--name-only", "-r", "-z", "HEAD")
        .rstrip("\0")
        .split("\0")
    )
    assert committed == set(scope)
    assert repository.git("show", "HEAD:unrelated.txt") == "original"
    assert repository.git("show", "HEAD:literal-a.txt") == "original"
    assert repository.git("diff", "--cached", "--name-only").strip() == "unrelated.txt"
    assert not repository.commit_paths("unchanged scope", scope[1:])
    assert repository.git("log", "-1", "--format=%s").strip() == "scoped publication"


def test_publication_accepts_a_literal_directory_scope(git_repository):
    root = git_repository
    directory = root / "bundle[1]"
    directory.mkdir()
    (directory / "model.zip").write_bytes(b"model")
    (root / "outside.txt").write_text("outside", encoding="utf-8")

    assert repository.commit_paths("directory publication", ["bundle[1]"])
    assert repository.git("ls-tree", "-r", "--name-only", "HEAD").strip() == (
        "bundle[1]/model.zip"
    )
    assert repository.git("status", "--porcelain", "--", "outside.txt").strip() == (
        "?? outside.txt"
    )


def test_staged_scope_checks_respect_windows_command_limit(monkeypatch):
    scope = [f"artifact {index:04d} {'x' * 80}-\U0001f680.json" for index in range(400)]
    observed: list[str] = []

    def git(*args):
        command = subprocess.list2cmdline(["git", *args])
        assert len(command.encode("utf-16-le")) // 2 + 1 <= (
            repository.WINDOWS_COMMAND_LINE_LIMIT
        )
        assert args[:6] == (
            "--literal-pathspecs",
            "diff",
            "--cached",
            "--name-only",
            "-z",
            "--",
        )
        observed.extend(args[6:])
        return ""

    monkeypatch.setattr(repository, "git", git)
    assert not repository.has_staged_changes(scope)
    assert observed == scope


def test_staged_scope_check_finds_changes_in_later_batch(monkeypatch):
    scope = [f"artifact-{index:04d}-{'x' * 80}.json" for index in range(400)]

    def git(*args):
        return f"{scope[-1]}\0" if scope[-1] in args[6:] else ""

    monkeypatch.setattr(repository, "git", git)
    assert repository.has_staged_changes(scope)


def test_git_pathspec_batches_reject_an_unrepresentable_single_path():
    with pytest.raises(ValueError, match="process-command limit"):
        list(
            repository._git_pathspec_batches(
                ("diff", "--"), ["x" * repository.WINDOWS_COMMAND_LINE_LIMIT]
            )
        )


@pytest.mark.parametrize("fail", [False, True])
def test_pathspec_file_preserves_literal_paths_and_is_removed(monkeypatch, fail):
    scope = ["literal[ab].txt", "space name.txt", "unicode-\u00e9.txt"]
    observed: list[Path] = []

    def git(*args):
        assert args[:3] == ("--literal-pathspecs", "add", "-A")
        assert args[-1] == "--pathspec-file-nul"
        path = Path(args[-2].removeprefix("--pathspec-from-file="))
        observed.append(path)
        assert path.read_bytes() == b"".join(
            name.encode("utf-8") + b"\0" for name in scope
        )
        if fail:
            raise RuntimeError("injected Git failure")
        return ""

    monkeypatch.setattr(repository, "git", git)
    if fail:
        with pytest.raises(RuntimeError, match="injected Git failure"):
            repository.git_with_pathspecs("add", "-A", scope=scope)
    else:
        repository.git_with_pathspecs("add", "-A", scope=scope)
    assert observed
    assert all(not path.exists() for path in observed)
