"""Restoration safety for the shared-episode paired-comparison accounting.

Issue #35: the distinct-episode accounting that a paired comparison depends on
used to live in the researcher-owned ``robot_learning/training/comparison.py``,
so restoring an older scientific recipe could silently revert it. The
accounting now lives on the protected side and these tests fail loudly if that
stops being true.
"""

from pathlib import Path

import pytest

from research import runner_protocol as protocol
from robot_learning.paired_evidence import (
    episode_outcomes,
    paired_comparison,
)

ROOT = Path(__file__).resolve().parents[2]
PROTECTED_ACCOUNTING = "robot_learning/paired_evidence.py"


def _evaluation(seed: int, outcomes: list[bool], semantics: str = "semantics") -> dict:
    return {
        "episodes": len(outcomes),
        "seed": seed,
        "evaluation_semantics": semantics,
        "episode_results": [
            {"episode": episode, "episode_seed": seed + episode, "success": success}
            for episode, success in enumerate(outcomes)
        ],
    }


def test_accounting_module_is_protected_and_never_researcher_owned():
    assert protocol.is_protected_source(PROTECTED_ACCOUNTING)
    assert protocol.is_human_owned(PROTECTED_ACCOUNTING)
    assert not protocol.is_researcher_owned(PROTECTED_ACCOUNTING)


def test_the_retired_researcher_owned_module_is_gone():
    assert not (ROOT / "robot_learning" / "training" / "comparison.py").exists()


def test_evaluator_and_runner_import_the_protected_accounting():
    for relative in (
        "research/runner_execution.py",
        "robot_learning/scenario/evaluation.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "robot_learning.training.comparison" not in source, relative
        assert "robot_learning.paired_evidence" in source, relative


def test_distinct_episode_coverage_is_counted_once_across_overlapping_panels():
    overlapping = [
        _evaluation(10, [True, False, True]),
        _evaluation(12, [True, True, True]),
    ]
    outcomes = episode_outcomes(overlapping)
    assert len(outcomes) == 5
    assert sum(outcomes.values()) == 4


def test_conflicting_deterministic_outcomes_are_rejected():
    conflicting = [
        _evaluation(10, [True, False]),
        _evaluation(10, [False, False]),
    ]
    with pytest.raises(ValueError, match="conflicting deterministic measurements"):
        episode_outcomes(conflicting)


def test_paired_comparison_rejects_panels_without_shared_episodes():
    with pytest.raises(ValueError, match="do not cover identical episodes"):
        paired_comparison(
            [_evaluation(3000, [True, False])],
            [_evaluation(4000, [True, False])],
        )
