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

from runner import paths, protocol, repository


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


@pytest.fixture(autouse=True)
def single_root_publication(monkeypatch):
    # Split campaign repositories never push; these tests cover the push path.
    monkeypatch.setattr(paths, "SPLIT", False)


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


def test_initialized_campaign_keeps_generated_outputs_out_of_scientific_delta(
    git_repository, monkeypatch
):
    from tools.initialize_campaign import CAMPAIGN_GITIGNORE

    root = git_repository
    (root / ".gitignore").write_text(CAMPAIGN_GITIGNORE, encoding="utf-8")
    reward = root / "robot_learning/training/reward.py"
    reward.parent.mkdir(parents=True)
    reward.write_text("VALUE = 1\n", encoding="utf-8")
    repository.git("add", "--", ".")
    repository.git("commit", "--quiet", "-m", "initial recipe")
    monkeypatch.setattr(paths, "SPLIT", True)
    ignored_outputs = [
        "campaigns/training_logs/campaign-one/t1-attempt-1.log",
        "campaigns/evaluations/campaign-one/research.json",
        "campaigns/evaluations/campaign-one/reference.json",
        "campaigns/evaluations/campaign-one/official.json",
        "campaigns/evaluations/campaign-one/research.json.progress",
        "campaigns/evaluations/campaign-one/research.json.progress.tmp",
        "campaigns/evaluations/campaign-one/module.json",
        "campaigns/evaluations/campaign-one/.module.json.pending",
        "campaigns/brief.md",
        "models/candidates/campaign-one/t1/model.zip",
        "models/candidates/campaign-one/t1/candidate_manifest.json",
        "models/candidates/campaign-one/t1/checkpoint-10/training_metrics.json",
        "runner/state/last_train_summary.md",
        "runner/state/last_evaluation.json",
        "runner/state/GOAL_REACHED",
        "runner/state/RECOVERY_PENDING",
        "runner/state/RESTART_PENDING",
        "pi_workspace/operation_request.json",
        "reports/session_usage/campaign-one.jsonl",
        ".copilot/opencode/catalogue.json",
        ".copilot/opencode/session.json",
        ".copilot/controller-stops/request.stop",
        ".copilot/large-output/review.json",
        "robot_learning/training/__pycache__/reward.pyc",
    ]
    for relative in ignored_outputs:
        output = root / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("generated output\n", encoding="utf-8")
    reward.write_text("VALUE = 2\n", encoding="utf-8")

    ignored = repository.git("check-ignore", "--", *ignored_outputs).splitlines()
    assert set(ignored) == set(ignored_outputs)
    assert all(
        paths.locate(relative) == root / relative for relative in ignored_outputs
    )
    assert repository.status_paths((".",)) == ["robot_learning/training/reward.py"]
    delta = repository.scientific_delta("HEAD")
    protocol.validate_research_delta_ownership(delta)
    assert delta == ["robot_learning/training/reward.py"]
    assert all(
        (root / relative).read_text(encoding="utf-8") == "generated output\n"
        for relative in ignored_outputs
    )


def test_campaign_memory_publication_excludes_science_and_local_artifacts(
    git_repository, monkeypatch
):
    from tools.initialize_campaign import CAMPAIGN_GITIGNORE

    root = git_repository
    (root / ".gitignore").write_text(CAMPAIGN_GITIGNORE, encoding="utf-8")
    repository.git("add", "--", ".")
    repository.git("commit", "--quiet", "-m", "initial campaign")
    parent = repository.git("rev-parse", "HEAD").strip()
    monkeypatch.setattr(paths, "SPLIT", True)
    memory = [
        "runner/state/research_state.json",
        "campaigns/results.jsonl",
        "campaigns/EXPERIMENTS.md",
        "pi_workspace/scientific_model.md",
        "campaigns/checkpoints/candidates/campaign-one/t1/checkpoint-10/model.zip",
        "campaigns/checkpoints/candidates/campaign-one/t1/checkpoint-10/artifact.json",
        "campaigns/checkpoints/candidates/campaign-one/t1/checkpoint-10/policy_runtime.pkl",
        "campaigns/checkpoints/retained/campaign-one/best/model.zip",
    ]
    science = [
        "robot_learning/training/reward.py",
        "robot_learning/lab/diagnostic.py",
    ]
    local_artifacts = [
        "campaigns/evaluations/campaign-one/panel.json",
        "campaigns/training_logs/campaign-one/t1-attempt-1.log",
    ]
    for relative in memory + science + local_artifacts:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("output\n", encoding="utf-8")

    delta = repository.scientific_delta(parent)
    protocol.validate_research_delta_ownership(delta)
    assert delta == ["robot_learning/training/reward.py"]
    assert set(repository.changed_runner_memory()) == set(memory)
    assert repository.commit_runner_memory("complete operation")
    committed = repository.committed_change_paths(parent)
    assert set(committed) == set(memory)
    assert set(repository.status_paths((".",))) == set(science)
    assert all((root / relative).is_file() for relative in local_artifacts)

    unexpected = "campaigns/unclassified.py"
    (root / unexpected).write_text("not Runner output\n", encoding="utf-8")
    with pytest.raises(ValueError, match="human-owned or unclassified"):
        protocol.validate_research_delta_ownership(repository.scientific_delta(parent))


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
