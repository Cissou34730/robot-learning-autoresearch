"""Deterministic terminal-readiness evidence for the frozen best-known model.

The statistical and scientific contract is written in
`research/stopping_contract.md`. This module computes facts only: it neither
blocks nor authorizes a terminal official-assessment request.
"""

from __future__ import annotations

import math
import random
from statistics import NormalDist

from robot_learning.benchmark.final_contract import (
    EVALUATION_EPISODES,
    FINAL_SUCCESS_PERCENT,
)

# The one-sided confidence used for the stopping-validation lower bound. It is a
# human-owned tradeoff between premature assessment and delayed assessment; see
# the contract before changing it.
STOPPING_CONFIDENCE = 0.80
# The official rule passes only when at least this many of its episodes succeed.
OFFICIAL_PASSES_REQUIRED = math.ceil(
    FINAL_SUCCESS_PERCENT * EVALUATION_EPISODES / 100
)
# Predeclared performance range for the simulation study. These are fixed before
# running the study; the study characterizes the rule and does not select it.
SIMULATION_TRUE_SUCCESS_RATES = (0.98, 0.99, 0.995, 0.999)
SIMULATION_TRIALS = 2_000
SIMULATION_EPISODES = 200


def wilson_lower_bound(
    successes: int,
    episodes: int,
    *,
    confidence: float = STOPPING_CONFIDENCE,
) -> float:
    """One-sided Wilson score lower bound on the success probability."""
    if episodes <= 0:
        raise ValueError("a stopping-validation panel needs at least one episode")
    if not 0 <= successes <= episodes:
        raise ValueError("successes must be between zero and the episode count")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be strictly between zero and one")
    z = NormalDist().inv_cdf(confidence)
    proportion = successes / episodes
    denominator = 1.0 + z * z / episodes
    center = (proportion + z * z / (2 * episodes)) / denominator
    spread = (
        z
        * math.sqrt(proportion * (1 - proportion) / episodes + z * z / (4 * episodes * episodes))
        / denominator
    )
    return max(0.0, center - spread)


def _terminal_validation_panel(
    best_known: dict, experiment_records: list[dict]
) -> dict | None:
    """The eligible predeclared stopping-validation panel, if one exists.

    Eligibility is read from recorded facts only: the measurement must declare
    ``purpose = terminal_validation``, its designation snapshot must match the
    current best-known tenure, it must carry integer successes, and its episodes
    must be disjoint from every earlier measurement of the same artifact.
    """
    fingerprint = best_known.get("fingerprint")
    current_ordinal = best_known.get("designation_ordinal")
    used_seeds: set[int] = set()
    eligible: dict | None = None
    for record in experiment_records:
        if not isinstance(record, dict):
            continue
        experiment = int(record.get("index", 0) or 0)
        for entry in record.get("requested_evaluations") or []:
            if not isinstance(entry, dict):
                continue
            metrics = entry.get("metrics") or {}
            recorded_fingerprint = entry.get("model_fingerprint") or metrics.get(
                "model_fingerprint"
            )
            if fingerprint and recorded_fingerprint != fingerprint:
                continue
            seed = int(entry.get("seed", metrics.get("seed", 0)) or 0)
            episodes = int(entry.get("episodes", metrics.get("episodes", 0)) or 0)
            if episodes <= 0:
                continue
            panel_seeds = set(range(seed, seed + episodes))
            successes = entry.get("successes", metrics.get("successes"))
            if str(entry.get("purpose", "selection")) == "terminal_validation":
                snapshot = entry.get("terminal_validation_snapshot") or {}
                if (
                    snapshot.get("fingerprint") == fingerprint
                    and snapshot.get("designation_ordinal") == current_ordinal
                    and successes is not None
                    and not (panel_seeds & used_seeds)
                ):
                    eligible = {
                        "experiment": experiment,
                        "seed": seed,
                        "episodes": episodes,
                        "successes": int(successes),
                    }
            used_seeds |= panel_seeds
    return eligible


def assess_terminal_readiness(
    best_known: dict | None,
    experiment_records: list[dict],
) -> dict:
    """Return factual terminal-readiness evidence for the best-known model.

    Deterministic: it reads the declared purpose, the designation snapshot and
    integer successes only. It never infers intent from prose, never uses
    ``origin_experiment`` as a designation boundary, and never inspects the
    official panel.
    """
    if not isinstance(best_known, dict):
        return {"assessed": False, "reason": "no best-known lineage"}
    if not isinstance(best_known.get("designation_ordinal"), int):
        return {
            "assessed": False,
            "reason": "no recorded best-known designation ordinal",
        }
    panel = _terminal_validation_panel(best_known, experiment_records)
    if panel is None:
        return {
            "assessed": False,
            "reason": (
                "no predeclared terminal-validation panel for the current "
                "best-known tenure; selection evidence is not terminal-readiness "
                "evidence"
            ),
        }
    lower = wilson_lower_bound(panel["successes"], panel["episodes"])
    success_percent = 100 * panel["successes"] / panel["episodes"]
    lower_percent = 100 * lower
    return {
        "assessed": True,
        "reason": "predeclared terminal-validation panel recorded",
        "panel": panel,
        "episodes": panel["episodes"],
        "successes": panel["successes"],
        "success_percent": success_percent,
        "confidence": STOPPING_CONFIDENCE,
        "objective_percent": FINAL_SUCCESS_PERCENT,
        "lower_bound_percent": lower_percent,
        "supported": lower_percent >= FINAL_SUCCESS_PERCENT,
    }


def simulate_stopping_policy(
    true_success: float,
    *,
    trials: int = SIMULATION_TRIALS,
    episodes: int = SIMULATION_EPISODES,
    seed: int = 0,
    confidence: float = STOPPING_CONFIDENCE,
) -> dict:
    """Characterize the stopping rule against a predeclared true success rate.

    Prospective validation by simulation: each trial draws one stopping-validation
    panel and one independent official panel from the same true success
    probability. It reports how often the rule approves while the official panel
    would fail (false terminal) and how often it withholds approval while the
    official panel would pass (delayed terminal). The study characterizes the
    predeclared rule; it does not choose its parameters.
    """
    rng = random.Random(seed)
    passes_required = math.ceil(FINAL_SUCCESS_PERCENT * episodes / 100)
    false_terminal = 0
    delayed_terminal = 0
    approvals = 0
    for _ in range(trials):
        validation_successes = sum(
            rng.random() < true_success for _ in range(episodes)
        )
        official_successes = sum(rng.random() < true_success for _ in range(episodes))
        approved = (
            100
            * wilson_lower_bound(
                validation_successes, episodes, confidence=confidence
            )
            >= FINAL_SUCCESS_PERCENT
        )
        official_pass = official_successes >= passes_required
        approvals += int(approved)
        false_terminal += int(approved and not official_pass)
        delayed_terminal += int((not approved) and official_pass)
    return {
        "true_success": true_success,
        "trials": trials,
        "episodes": episodes,
        "confidence": confidence,
        "approval_rate": approvals / trials,
        "false_terminal_rate": false_terminal / trials,
        "delayed_terminal_rate": delayed_terminal / trials,
    }
