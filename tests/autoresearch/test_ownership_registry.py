"""Ownership classifications must match the files that exist.

Issue #41 finding 1: ownership is a hand-maintained registry. A declared path
that no longer exists silently changes which files define evaluation semantics,
so the registry is checked directly.
"""

import re
from pathlib import Path

from research import runner_protocol as protocol

ROOT = Path(__file__).resolve().parents[2]
RETIRED_SHIMS = (
    "robot_learning/environments/reach_env.py",
    "robot_learning/rewards/reach_reward.py",
    "robot_learning/training/observations.py",
    "research/benchmark_envs.py",
)


def test_every_declared_classification_exists_on_disk():
    assert protocol.declared_paths_exist() == []


def test_a_missing_declared_path_is_reported(monkeypatch):
    monkeypatch.setattr(
        protocol,
        "PROTECTED_RUNNER_PATHS",
        {"research/does_not_exist.py"},
    )
    assert protocol.declared_paths_exist() == ["research/does_not_exist.py"]


def test_retired_compatibility_shims_are_gone():
    for relative in RETIRED_SHIMS:
        assert not (ROOT / relative).exists(), relative


def test_every_documented_human_owned_path_is_enforced():
    """The AGENTS.md contract and the enforced classification must not drift.

    Issue #58: the documentation called the whole benchmark package human-owned
    while enforcement listed files by hand and omitted two. Each documented
    literal, directory and glob is resolved against the repository so that a
    typo or a moved path fails here, and every resolved path must be classified
    human-owned.
    """
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    section = text.split("## Human-owned paths", 1)[1].split("\n## ", 1)[0]
    listing = section[section.index("- ") :].split("\n\n", 1)[0]
    documented = re.findall(r"`([^`]+)`", listing)

    assert documented
    resolved: list[str] = []
    for entry in documented:
        assert not entry.startswith("/"), entry
        if any(wildcard in entry for wildcard in "*?["):
            matches = sorted(
                path.relative_to(ROOT).as_posix() for path in ROOT.glob(entry)
            )
            assert matches, f"documented glob matches nothing: {entry}"
            resolved.extend(matches)
        elif entry.endswith("/"):
            directory = ROOT / entry.rstrip("/")
            assert directory.is_dir(), f"documented directory is missing: {entry}"
            resolved.extend(
                path.relative_to(ROOT).as_posix()
                for path in directory.rglob("*")
                if path.is_file()
            )
        else:
            assert (ROOT / entry).is_file(), f"documented path is missing: {entry}"
            resolved.append(entry)

    assert resolved
    for relative in resolved:
        assert protocol.is_human_owned(relative), relative

