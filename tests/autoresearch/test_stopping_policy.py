"""Terminal-readiness stopping contract and its deterministic assessment.

Audit findings 2 and 3: stopping evidence must be declared, must belong to the
current best-known tenure, must use integer successes, and must remain
non-blocking until prospectively validated.
"""

import re
from pathlib import Path

import pytest

from research import build_research_brief as brief
from research import runner_protocol as protocol
from research import stopping_policy

ROOT = Path(__file__).resolve().parents[2]
FINGERPRINT = "fingerprint"
BEST_KNOWN = {"fingerprint": FINGERPRINT, "designation_ordinal": 2}


def _measurement(
    index: int,
    *,
    candidate: str = "c1",
    seed: int = 4200,
    episodes: int = 160,
    successes: int = 160,
    purpose: str = "selection",
    snapshot: dict | None = None,
    fingerprint: str = FINGERPRINT,
) -> dict:
    return {
        "index": index,
        "requested_evaluations": [
            {
                "candidate": candidate,
                "seed": seed,
                "episodes": episodes,
                "purpose": purpose,
                "terminal_validation_snapshot": snapshot,
                "model_fingerprint": fingerprint,
                "metrics": {
                    "seed": seed,
                    "episodes": episodes,
                    "successes": successes,
                    "model_fingerprint": fingerprint,
                },
            }
        ],
    }


def _snapshot(ordinal: int = 2, fingerprint: str = FINGERPRINT) -> dict:
    return {"fingerprint": fingerprint, "designation_ordinal": ordinal}


def test_wilson_lower_bound_is_monotone_and_bounded():
    assert stopping_policy.wilson_lower_bound(
        200, 200
    ) > stopping_policy.wilson_lower_bound(196, 200)
    assert stopping_policy.wilson_lower_bound(196, 200) <= 0.98
    assert stopping_policy.wilson_lower_bound(0, 10) <= 1e-12
    with pytest.raises(ValueError):
        stopping_policy.wilson_lower_bound(1, 0)
    with pytest.raises(ValueError):
        stopping_policy.wilson_lower_bound(3, 2)


def test_missing_designation_provenance_is_not_assessed():
    assert stopping_policy.assess_terminal_readiness(None, [])["assessed"] is False
    no_ordinal = {"fingerprint": FINGERPRINT}
    assessment = stopping_policy.assess_terminal_readiness(no_ordinal, [])
    assert assessment["assessed"] is False
    assert "designation ordinal" in assessment["reason"]


def test_selection_measurements_are_not_terminal_readiness_evidence():
    assessment = stopping_policy.assess_terminal_readiness(
        BEST_KNOWN, [_measurement(2, seed=6000, successes=160)]
    )
    assert assessment["assessed"] is False
    assert "selection evidence" in assessment["reason"]


def test_declared_terminal_validation_uses_integer_successes():
    supported = stopping_policy.assess_terminal_readiness(
        BEST_KNOWN,
        [
            _measurement(
                2,
                seed=6000,
                successes=160,
                purpose="terminal_validation",
                snapshot=_snapshot(),
            )
        ],
    )
    assert supported["assessed"] is True
    assert supported["supported"] is True
    assert supported["lower_bound_percent"] >= 98.0

    unsupported = stopping_policy.assess_terminal_readiness(
        BEST_KNOWN,
        [
            _measurement(
                2,
                seed=6000,
                successes=156,
                purpose="terminal_validation",
                snapshot=_snapshot(),
            )
        ],
    )
    assert unsupported["assessed"] is True
    assert unsupported["supported"] is False


def test_terminal_validation_from_an_earlier_tenure_is_rejected():
    stale = stopping_policy.assess_terminal_readiness(
        BEST_KNOWN,
        [
            _measurement(
                2,
                seed=6000,
                successes=160,
                purpose="terminal_validation",
                snapshot=_snapshot(ordinal=1),
            )
        ],
    )
    assert stale["assessed"] is False


def test_terminal_validation_reusing_selection_episodes_is_rejected():
    reused = stopping_policy.assess_terminal_readiness(
        BEST_KNOWN,
        [
            _measurement(1, seed=6000, successes=150),
            _measurement(
                2,
                seed=6000,
                successes=160,
                purpose="terminal_validation",
                snapshot=_snapshot(),
            ),
        ],
    )
    assert reused["assessed"] is False


def test_brief_reports_terminal_readiness_as_advisory():
    state = {"best_known_lineage": BEST_KNOWN}
    records = [
        _measurement(
            2,
            seed=6000,
            successes=160,
            purpose="terminal_validation",
            snapshot=_snapshot(),
        )
    ]
    text = "\n".join(brief._v4_terminal_readiness_section(state, records, None))
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


def test_simulated_policy_is_non_pathological_across_predeclared_rates():
    results = [
        stopping_policy.simulate_stopping_policy(true_success, trials=600, seed=7)
        for true_success in stopping_policy.SIMULATION_TRUE_SUCCESS_RATES
    ]
    approvals = [result["approval_rate"] for result in results]
    # Approval is monotone in the true success rate.
    assert approvals == sorted(approvals)
    # At the objective the rule approves only a minority of the time.
    assert results[0]["approval_rate"] <= 0.25
    assert results[0]["false_terminal_rate"] <= 0.1
    # A near-certain policy is approved.
    assert results[-1]["approval_rate"] >= 0.9
    # At the objective the cost is delay, not premature assessment.
    assert results[0]["delayed_terminal_rate"] > results[0]["approval_rate"]
