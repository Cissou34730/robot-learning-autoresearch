"""Ownership classifications must match the files that exist.

Issue #41 finding 1: ownership is a hand-maintained registry. A declared path
that no longer exists silently changes which files define evaluation semantics,
so the registry is checked directly.
"""

import re
from pathlib import Path

import pytest

from research import runner_protocol as protocol
from research.runner_protocol import validate_experiment_semantics

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
    while enforcement listed files by hand and omitted two. Parsing the
    documented list makes that disagreement fail here instead of silently
    changing what a measurement means.
    """
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    section = text.split("## Human-owned paths", 1)[1].split("\n## ", 1)[0]
    documented = re.findall(r"`([^`]+)`", section)

    assert documented
    for entry in documented:
        assert protocol.is_human_owned(entry), entry


def test_a_proposal_touching_an_immutable_benchmark_constant_is_rejected():
    with pytest.raises(
        ValueError, match="restore them to their content at the scientific parent"
    ):
        validate_experiment_semantics(
            {},
            "training",
            "transfer",
            None,
            ["robot_learning/benchmark/spec.py"],
            False,
        )
