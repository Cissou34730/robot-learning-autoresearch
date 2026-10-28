"""Trust gate between PI work and the next load of mutable Runner or adapter code.

Before the launcher runs Runner or adapter code again, every file outside the
PI-owned paths of ``contracts/authority.md`` must match the snapshot taken
after the last trusted invocation. In a separate harness only the files a
campaign loads are compared, so maintainer documents and commits do not stop it.
"""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

from runner.paths import is_harness_runtime

_PROTECTED_INSIDE_PI_AREA = frozenset(
    {
        "robot_learning/scenario/__init__.py",
        "benchmark/adapters/final_benchmark.py",
        "benchmark/adapters/task_reference.py",
    }
)
_PI_FILES = frozenset(
    {
        "robot_learning/train.py",
        "robot_learning/evaluate.py",
        "robot_learning/play.py",
        "robot_learning/training/current_params.json",
        "pi_workspace/operation_request.json",
    }
)
_PI_PREFIXES = (
    "robot_learning/scenario/",
    "robot_learning/training/",
    "robot_learning/lab/",
)
_PRELIMINARY_FILE = "pi_workspace/scientific_model.md"
_EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        ".copilot",
        ".py-git-probe",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".pyre",
        ".pytype",
        ".hypothesis",
        ".tox",
        ".nox",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        "node_modules",
        "build",
        "dist",
        "wheels",
        "htmlcov",
        "reports",
    }
)
_RUNNER_STATE_FILES = frozenset(
    {
        "runner/state/research_state.json",
        "campaigns/results.jsonl",
        "campaigns/experiments.md",
        "runner/state/goal_reached",
        "runner/state/recovery_pending",
        "runner/state/restart_pending",
        "campaigns/brief.md",
        "runner/state/last_train_summary.md",
        "runner/state/last_evaluation.json",
    }
)
_RUNNER_STATE_PREFIXES = (
    "campaigns/training_logs/",
    "campaigns/evaluations/",
    "campaigns/checkpoints/candidates/",
    "campaigns/checkpoints/retained/",
    "models/candidates/",
)


class TrustViolation(RuntimeError):
    """Content outside the PI-owned paths changed; mutable code must not load."""

    def __init__(self, message: str, *, pi_message: str | None = None) -> None:
        super().__init__(message)
        self.pi_message = pi_message or message


def is_pi_writable(relative: str, *, preliminary: bool) -> bool:
    relative = relative.replace("\\", "/").lstrip("/").lower()
    if relative in _PROTECTED_INSIDE_PI_AREA:
        return False
    if preliminary:
        return relative == _PRELIMINARY_FILE
    return relative in _PI_FILES or relative.startswith(_PI_PREFIXES)


def is_excluded(relative: str) -> bool:
    """Generated, administrative and Runner-written paths outside the gate."""
    relative = relative.replace("\\", "/").lstrip("/").lower()
    for part in (part for part in relative.split("/") if part):
        if (
            part in _EXCLUDED_DIRECTORIES
            or part.startswith(".pytest-")
            or part.endswith(".egg-info")
        ):
            return True
    if (
        relative == ".coverage"
        or relative.startswith(".coverage.")
        or relative == "coverage.xml"
        or relative.endswith(".pyc")
    ):
        return True
    return relative in _RUNNER_STATE_FILES or relative.startswith(
        _RUNNER_STATE_PREFIXES
    )


def head_identity(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Could not resolve repository HEAD for the launcher trust snapshot."
        )
    identity = (result.stdout + result.stderr).strip()
    if not identity:
        raise RuntimeError("Repository HEAD is empty in the launcher trust snapshot.")
    return identity


def _is_reparse_point(entry: os.DirEntry) -> bool:
    attributes = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT) or entry.is_symlink()


def _link_identity(entry: os.DirEntry) -> str:
    kind = (
        "Junction"
        if entry.is_junction()
        else "SymbolicLink"
        if entry.is_symlink()
        else ""
    )
    try:
        target = os.readlink(entry.path)
    except OSError:
        target = ""
    return f"link|{kind}|{target}"


def _file_hash(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return f"file|{digest.hexdigest().upper()}"


def protected_files(root: Path, *, preliminary: bool) -> dict[str, str]:
    """Every gated file and link with its content identity; fails closed."""
    base = os.path.abspath(root).rstrip("\\/")
    pending = [base]
    files: dict[str, str] = {}
    while pending:
        directory = pending.pop(0)
        with os.scandir(directory) as entries:
            for entry in entries:
                relative = entry.path[len(base) :].lstrip("\\/").replace("\\", "/")
                if is_excluded(relative):
                    continue
                key = relative.lower()
                reparse = _is_reparse_point(entry)
                if entry.is_dir() or entry.is_junction():
                    if reparse:
                        files[key] = _link_identity(entry)
                    else:
                        pending.append(entry.path)
                    continue
                if is_pi_writable(relative, preliminary=preliminary):
                    continue
                files[key] = (
                    _link_identity(entry) if reparse else _file_hash(entry.path)
                )
    return files


def harness_runtime_files(root: Path, *, preliminary: bool) -> dict[str, str]:
    return {
        relative: identity
        for relative, identity in protected_files(root, preliminary=preliminary).items()
        if is_harness_runtime(relative)
    }


@dataclass(frozen=True)
class TrustSnapshot:
    root: Path
    head: str | None
    files: dict[str, str]
    preliminary: bool
    harness: TrustSnapshot | None = None

    @classmethod
    def capture(
        cls, root: Path, *, preliminary: bool, harness_root: Path | None = None
    ) -> TrustSnapshot:
        separate = harness_root is not None and os.path.abspath(
            harness_root
        ) != os.path.abspath(root)
        return cls(
            root=root,
            head=head_identity(root),
            files=protected_files(root, preliminary=preliminary),
            preliminary=preliminary,
            harness=cls(
                root=harness_root,
                head=None,
                files=harness_runtime_files(harness_root, preliminary=preliminary),
                preliminary=preliminary,
            )
            if separate
            else None,
        )

    def verify(self) -> None:
        if self.harness is not None:
            self.harness.verify()
        violations = set()
        if self.head is not None and head_identity(self.root) != self.head:
            violations.add("HEAD")
        current = (
            protected_files(self.root, preliminary=self.preliminary)
            if self.head is not None
            else harness_runtime_files(self.root, preliminary=self.preliminary)
        )
        for relative, identity in current.items():
            if self.files.get(relative) != identity:
                violations.add(relative)
        violations.update(
            relative for relative in self.files if relative not in current
        )
        if violations:
            listed = ", ".join(sorted(violations, key=str.lower))
            if self.head is None:
                raise TrustViolation(
                    f"Harness runtime files changed during the campaign: {listed}. "
                    "Refusing to load mutable Runner or adapter code.",
                    pi_message=(
                        "The Runner changed during the session. You cannot "
                        "restore its files. It cannot execute operations until "
                        "they are restored."
                    ),
                )
            raise TrustViolation(
                "PI work changed repository content outside the PI-owned paths "
                f"in contracts/authority.md: {listed}. "
                "Refusing to load mutable Runner or adapter code."
            )


class TrustGuard:
    """The current snapshot and the session kind it was taken for."""

    def __init__(self, campaign_root: Path, harness_root: Path) -> None:
        self._campaign_root = campaign_root
        self._harness_root = harness_root
        self._snapshot: TrustSnapshot | None = None
        self.preliminary = False

    def verify(self) -> None:
        if self._snapshot is not None:
            self._snapshot.verify()

    def capture(self, *, preliminary: bool) -> None:
        self.preliminary = preliminary
        self.refresh()

    def refresh(self) -> None:
        self._snapshot = TrustSnapshot.capture(
            self._campaign_root,
            preliminary=self.preliminary,
            harness_root=self._harness_root,
        )
