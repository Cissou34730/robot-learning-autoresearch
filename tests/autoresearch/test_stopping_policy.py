"""Terminal-readiness stopping contract and its deterministic assessment.

Issue #37: stopping evidence must be deterministic, uncertainty-aware and
non-blocking until prospectively validated. These tests pin the statistical
core, the fresh-panel requirement, and the advisory presentation.
"""

import re
from pathlib import Path

import pytest

from research import build_research_brief as brief
from research import runner_protocol as protocol
from research import stopping_policy

ROOT = Path(__file__).resolve().parents[2]
FINGERPRINT = "fingerprint"
BEST_KNOWN = {"fingerprint": FINGERPRINT, "origin_experiment": 1}


def _record(
    index: int,
    seed: int,
    episodes: int,
    success_percent: float,
    fingerprint: str = FINGERPRINT,
) -> dict:
    return {
        "index": index,
        "requested_evaluations": [
            {
                "model_fingerprint": fingerprint,
                "seed": seed,
                "episodes": episodes,
                "metrics": {
                    "model_fingerprint": fingerprint,
                    "seed": seed,
                    "episodes": episodes,
                    "success_percent": success_percent,
                },
            }
        ],
    }


def test_wilson_lower_bound_is_monotone_and_bounded():
    assert stopping_policy.wilson_lower_bound(200, 200) > stopping_policy.wilson_lower_bound(
        196, 200
    )
    assert stopping_policy.wilson_lower_bound(196, 200) <= 0.98
    assert stopping_policy.wilson_lower_bound(0, 10) <= 1e-12
    with pytest.raises(ValueError):
        stopping_policy.wilson_lower_bound(1, 0)
    with pytest.raises(ValueError):
        stopping_policy.wilson_lower_bound(3, 2)


def test_selection_panel_is_not_terminal_readiness_evidence():
    assessment = stopping_policy.assess_terminal_readiness(
        BEST_KNOWN, [_record(1, 5000, 200, 100.0)]
    )
    assert assessment["assessed"] is False
    assert "selection panel" in assessment["reason"]


def test_fresh_panel_readiness_depends_on_the_lower_bound():
    supported = stopping_policy.assess_terminal_readiness(
        BEST_KNOWN, [_record(2, 6000, 200, 100.0)]
    )
    assert supported["assessed"] is True
    assert supported["supported"] is True
    assert supported["lower_bound_percent"] >= 98.0

    unsupported = stopping_policy.assess_terminal_readiness(
        BEST_KNOWN, [_record(2, 6000, 200, 98.0)]
    )
    assert unsupported["assessed"] is True
    assert unsupported["supported"] is False


def test_reused_selection_seeds_are_not_a_fresh_panel():
    reused = stopping_policy.assess_terminal_readiness(
        BEST_KNOWN,
        [
            _record(1, 5000, 200, 99.0),
            _record(2, 5000, 200, 100.0),
        ],
    )
    assert reused["assessed"] is False

    disjoint = stopping_policy.assess_terminal_readiness(
        BEST_KNOWN,
        [
            _record(1, 5000, 200, 99.0),
            _record(2, 5000, 200, 100.0),
            _record(3, 6000, 200, 100.0),
        ],
    )
    assert disjoint["assessed"] is True
    assert disjoint["panel"]["seed"] == 6000


def test_brief_reports_terminal_readiness_as_advisory():
    text = "\n".join(
        brief._v4_terminal_readiness_section(
            {"best_known_lineage": BEST_KNOWN}, [_record(2, 6000, 200, 100.0)], None
        )
    )
    assert "## Terminal-readiness evidence" in text
    assert "does not authorize or block" in text
    assert "Contract assessment: supported." in text

    not_assessed = "\n".join(brief._v4_terminal_readiness_section({}, [], None))
    assert "not assessed" in not_assessed


def test_stopping_contract_is_human_owned_and_referenced():
    contract = ROOT / "research" / "stopping_contract.md"
    assert contract.exists()
    assert protocol.is_protected_source("research/stopping_contract.md")
    assert not protocol.is_researcher_owned("research/stopping_contract.md")
    assert "research/stopping_contract.md" in (
        ROOT / "research" / "program.md"
    ).read_text(encoding="utf-8")


def test_stopping_module_names_no_learning_algorithm():
    source = (
        ROOT / "research" / "stopping_policy.py"
    ).read_text(encoding="utf-8").lower()
    for algorithm in ("ppo", "sac", "td3", "a2c", "ddpg"):
        assert not re.search(rf"\b{algorithm}\b", source), algorithm
