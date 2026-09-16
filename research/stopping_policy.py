"""Deterministic terminal-readiness evidence for the frozen best-known model.

The statistical and scientific contract is written in
`research/stopping_contract.md`. This module computes facts only: it neither
blocks nor authorizes a terminal official-assessment request.
"""

from __future__ import annotations

import math
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


def _measurement_panels(best_known: dict, experiment_records: list[dict]) -> list[dict]:
    """Recorded research-evaluation panels for the best-known model, in order."""
    fingerprint = best_known.get("fingerprint")
    panels: list[dict] = []
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
            episodes = int(entry.get("episodes", metrics.get("episodes", 0)) or 0)
            success_percent = metrics.get("success_percent")
            if episodes <= 0 or success_percent is None:
                continue
            panels.append(
                {
                    "experiment": experiment,
                    "seed": int(entry.get("seed", metrics.get("seed", 0)) or 0),
                    "episodes": episodes,
                    "successes": round(float(success_percent) * episodes / 100),
                }
            )
    return panels


def assess_terminal_readiness(
    best_known: dict | None,
    experiment_records: list[dict],
) -> dict:
    """Return factual terminal-readiness evidence for the best-known model.

    Deterministic: it reads structured seeds, episode counts and recorded
    success only. It never infers intent from prose and never inspects the
    official panel.
    """
    if not isinstance(best_known, dict):
        return {"assessed": False, "reason": "no best-known lineage"}
    origin_experiment = int(best_known.get("origin_experiment") or 0)
    panels = _measurement_panels(best_known, experiment_records)

    used_seeds: set[int] = set()
    fresh: list[dict] = []
    for panel in panels:
        panel_seeds = set(range(panel["seed"], panel["seed"] + panel["episodes"]))
        if panel["experiment"] > origin_experiment and not (panel_seeds & used_seeds):
            fresh.append(panel)
        used_seeds |= panel_seeds

    if not fresh:
        return {
            "assessed": False,
            "reason": (
                "no fresh measurement after the best-known designation; "
                "a selection panel is not terminal-readiness evidence"
            ),
            "panels": panels,
        }
    panel = max(fresh, key=lambda item: (item["episodes"], item["experiment"]))
    lower = wilson_lower_bound(panel["successes"], panel["episodes"])
    success_percent = 100 * panel["successes"] / panel["episodes"]
    lower_percent = 100 * lower
    return {
        "assessed": True,
        "reason": "fresh stopping-validation panel recorded",
        "panel": panel,
        "episodes": panel["episodes"],
        "successes": panel["successes"],
        "success_percent": success_percent,
        "confidence": STOPPING_CONFIDENCE,
        "objective_percent": FINAL_SUCCESS_PERCENT,
        "lower_bound_percent": lower_percent,
        "supported": lower_percent >= FINAL_SUCCESS_PERCENT,
        "panels": panels,
    }
