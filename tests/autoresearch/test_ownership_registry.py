"""Ownership classifications must match the files that exist.

Issue #41 finding 1: ownership is a hand-maintained registry. A declared path
that no longer exists silently changes which files define evaluation semantics,
so the registry is checked directly.
"""

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
