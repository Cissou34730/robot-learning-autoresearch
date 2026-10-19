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

from runner import paths, repository


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


@pytest.mark.parametrize(
    "failure",
    [
        "remote: Internal Server Error",
        "remote: fatal error in commit_refs",
        "fatal: The requested URL returned error: 500",
        "error: RPC failed; HTTP 502 curl 22",
        "fatal: The requested URL returned error: 503",
        "fatal: The requested URL returned error: 504",
    ],
)
def test_push_retries_transient_failure_with_fixed_commit_and_branch(
    monkeypatch, failure
):
    commit = "a" * 40
    destination = "refs/heads/research"
    pushes = []
    waits = []
    resolutions = []
    head = {"commit": commit, "branch": destination}

    def git(*args):
        if args == ("rev-parse", "HEAD"):
            resolutions.append(args)
            return head["commit"] + "\n"
        if args == ("symbolic-ref", "--quiet", "HEAD"):
            resolutions.append(args)
            return head["branch"] + "\n"
        pushes.append(args)
        if len(pushes) == 1:
            raise RuntimeError(failure)
        return ""

    def sleep(seconds):
        waits.append(seconds)
        head.update(commit="b" * 40, branch="refs/heads/different")

    monkeypatch.setattr(repository, "git", git)
    monkeypatch.setattr(repository.time, "sleep", sleep)

    repository.push_head()

    assert pushes == [("push", "origin", f"{commit}:{destination}")] * 2
    assert waits == [60]
    assert resolutions == [
        ("rev-parse", "HEAD"),
        ("symbolic-ref", "--quiet", "HEAD"),
    ]


@pytest.mark.parametrize("failures", [0, 3, 4])
def test_push_retry_limit_and_error_preservation(monkeypatch, failures):
    pushes = []
    waits = []

    def git(*args):
        if args == ("rev-parse", "HEAD"):
            return "a" * 40
        if args == ("symbolic-ref", "--quiet", "HEAD"):
            return "refs/heads/research"
        pushes.append(args)
        if len(pushes) <= failures:
            raise RuntimeError(f"remote: Internal Server Error\nrequest-{len(pushes)}")
        return ""

    monkeypatch.setattr(repository, "git", git)
    monkeypatch.setattr(repository.time, "sleep", waits.append)

    if failures == 4:
        with pytest.raises(repository.PublicationError, match="request-4") as raised:
            repository.push_head()
        assert isinstance(raised.value.__cause__, RuntimeError)
    else:
        repository.push_head()

    assert len(pushes) == min(failures + 1, 4)
    assert waits == [60] * min(failures, 3)


@pytest.mark.parametrize(
    "failure",
    [
        "fatal: Authentication failed",
        "remote: GH001: Large files detected",
        "rejected (non-fast-forward)",
        "rejected (fetch first)",
        "remote: GH013: Repository rule violations found",
        "fatal: Could not resolve host: github.com",
        "remote: Internal Server Error\nfatal: Authentication failed",
    ],
)
def test_push_does_not_retry_permanent_or_unknown_errors(monkeypatch, failure):
    pushes = []
    waits = []

    def git(*args):
        if args == ("rev-parse", "HEAD"):
            return "a" * 40
        if args == ("symbolic-ref", "--quiet", "HEAD"):
            return "refs/heads/research"
        pushes.append(args)
        raise RuntimeError(failure)

    monkeypatch.setattr(repository, "git", git)
    monkeypatch.setattr(repository.time, "sleep", waits.append)

    with pytest.raises(repository.PublicationError) as raised:
        repository.push_head()

    assert failure in str(raised.value)
    assert len(pushes) == 1
    assert waits == []


def test_push_stops_retrying_when_rejection_becomes_permanent(monkeypatch):
    failures = iter(
        [
            RuntimeError("remote: Internal Server Error"),
            RuntimeError("rejected (non-fast-forward)"),
        ]
    )
    pushes = []
    waits = []

    def git(*args):
        if args == ("rev-parse", "HEAD"):
            return "a" * 40
        if args == ("symbolic-ref", "--quiet", "HEAD"):
            return "refs/heads/research"
        pushes.append(args)
        raise next(failures)

    monkeypatch.setattr(repository, "git", git)
    monkeypatch.setattr(repository.time, "sleep", waits.append)

    with pytest.raises(repository.PublicationError, match="non-fast-forward"):
        repository.push_head()

    assert len(pushes) == 2
    assert waits == [60]


def test_push_retry_wait_is_interruptible(monkeypatch):
    pushes = []

    def git(*args):
        if args == ("rev-parse", "HEAD"):
            return "a" * 40
        if args == ("symbolic-ref", "--quiet", "HEAD"):
            return "refs/heads/research"
        pushes.append(args)
        raise RuntimeError("remote: Internal Server Error")

    def sleep(seconds):
        assert seconds == 60
        raise KeyboardInterrupt

    monkeypatch.setattr(repository, "git", git)
    monkeypatch.setattr(repository.time, "sleep", sleep)

    with pytest.raises(KeyboardInterrupt):
        repository.push_head()

    assert len(pushes) == 1
