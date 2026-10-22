"""Success-rate evidence against a target: Wilson intervals and pass probability."""

from __future__ import annotations

import json
import math
from statistics import NormalDist
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

PASS_LEVELS = (0.5, 0.8, 0.95)


class Counts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    successes: int = Field(ge=0)
    trials: int = Field(ge=1, le=100_000)

    @model_validator(mode="after")
    def validate_counts(self) -> Counts:
        if self.successes > self.trials:
            raise ValueError("successes must not exceed trials")
        return self


class RecordedReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str = Field(min_length=1, description="Completed measurement.")
    candidate: str = Field(min_length=1, description="Candidate ID or role.")
    label: str | None = Field(
        default=None, description="Measurement label when the candidate appears twice."
    )


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=128, description="Your name for it.")
    successes: int | None = Field(default=None, ge=0)
    trials: int | None = Field(default=None, ge=1, le=100_000)
    recorded: list[RecordedReference] | None = Field(
        default=None,
        min_length=1,
        max_length=20,
        description=(
            "Recorded measurements to pool instead of typed counts; Runner "
            "reads successes and episodes from the records."
        ),
    )

    @model_validator(mode="after")
    def validate_form(self) -> Evidence:
        typed = self.successes is not None or self.trials is not None
        if typed == (self.recorded is not None):
            raise ValueError("give either successes and trials, or recorded")
        if typed:
            Counts(successes=self.successes, trials=self.trials)
        return self


class Target(Counts):
    trials: int = Field(
        ge=1, le=10_000, description="Episodes in the panel that decides the goal."
    )
    successes: int = Field(ge=0, description="Successes that panel requires.")


class PassProbabilityParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: Target
    evidence: list[Evidence] = Field(
        min_length=1,
        max_length=20,
        description="Typed counts or recorded measurements; each entry is evaluated alone.",
    )
    confidence: float = Field(
        ge=0.5, le=0.999, description="Two-sided interval level that you choose."
    )


def wilson_interval(successes: int, trials: int, confidence: float) -> dict[str, float]:
    z = NormalDist().inv_cdf((1 + confidence) / 2)
    proportion = successes / trials
    denominator = 1 + z * z / trials
    centre = (proportion + z * z / (2 * trials)) / denominator
    half_width = (
        z
        * math.sqrt(proportion * (1 - proportion) / trials + z * z / (4 * trials**2))
        / denominator
    )
    return {
        "proportion": proportion,
        "lower": max(0.0, centre - half_width),
        "upper": min(1.0, centre + half_width),
    }


def _log_beta(a: float, b: float) -> float:
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def _log_choose(n: int, k: int) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def pass_probability(successes: int, trials: int, target: Target) -> float:
    """P(a new target panel reaches its required successes); uniform Beta prior."""
    a = successes + 1
    b = trials - successes + 1
    base = _log_beta(a, b)
    n = target.trials
    return min(
        1.0,
        math.fsum(
            math.exp(_log_choose(n, x) + _log_beta(x + a, n - x + b) - base)
            for x in range(target.successes, n + 1)
        ),
    )


def binomial_pass_probability(rate: float, target: Target) -> float:
    if rate >= 1.0:
        return 1.0
    if rate <= 0.0:
        return 1.0 if target.successes == 0 else 0.0
    n = target.trials
    return min(
        1.0,
        math.fsum(
            math.exp(
                _log_choose(n, x) + x * math.log(rate) + (n - x) * math.log1p(-rate)
            )
            for x in range(target.successes, n + 1)
        ),
    )


def rate_for_pass_probability(level: float, target: Target) -> float:
    low, high = 0.0, 1.0
    for _ in range(60):
        middle = (low + high) / 2
        if binomial_pass_probability(middle, target) < level:
            low = middle
        else:
            high = middle
    return high


def _candidate_id(state: dict, name: str) -> str:
    roles = state.get("model_roles") or {}
    if name in {"working", "best_known"}:
        return str(roles.get(name) or name)
    return str((roles.get("retained") or {}).get(name, name))


def _episode_identity(item: dict) -> set:
    metrics = item["metrics"]
    if item["instrument"] == "research_evaluation":
        start = int(metrics["seed"])
        return set(range(start, start + int(metrics["episodes"])))
    panel = (metrics.get("panel"), metrics.get("panel_version"))
    return {(*panel, index) for index in range(int(metrics["episodes"]))}


def recorded_counts(state: dict, references: list[RecordedReference]) -> dict:
    """Pool successes and episodes of recorded candidate measurements."""
    events = {event.get("id"): event for event in state.get("operation_events", [])}
    sources, seen, shared = [], set(), 0
    for reference in references:
        candidate = _candidate_id(state, reference.candidate.strip())
        event = events.get(reference.operation_id.strip())
        if (
            not event
            or event.get("kind") != "measurement"
            or event.get("status") != "completed"
        ):
            raise ValueError(f"{reference.operation_id} is not a completed measurement")
        items = [
            item
            for item in event["result"]["measurements"]
            if item.get("instrument") in {"research_evaluation", "task_reference"}
        ]
        matches = [
            item
            for item in items
            if item.get("candidate") == candidate
            and (reference.label is None or item.get("label") == reference.label)
        ]
        if len(matches) != 1:
            recorded = [(item.get("candidate"), item.get("label")) for item in items]
            raise ValueError(
                f"{reference.operation_id} has {len(matches)} measurements of "
                f"{candidate}"
                + (f" labelled {reference.label!r}" if reference.label else "")
                + f"; recorded candidate measurements: {recorded}"
            )
        item = matches[0]
        metrics = item["metrics"]
        trials = int(metrics["episodes"])
        successes = metrics.get("successes")
        if successes is None:
            successes = round(float(metrics["success_percent"]) * trials / 100)
        identity = _episode_identity(item)
        shared += len(identity & seen)
        seen |= identity
        sources.append(
            {
                "operation_id": event["id"],
                "candidate": candidate,
                "instrument": item["instrument"],
                "label": item.get("label"),
                "successes": int(successes),
                "trials": trials,
            }
        )
    return {
        "successes": sum(source["successes"] for source in sources),
        "trials": sum(source["trials"] for source in sources),
        "sources": sources,
        "episodes_shared_between_sources": shared,
    }


def query_pass_probability(args: dict[str, Any], campaign_id: str = "") -> str:
    """Native custom-tool handler; reads recorded measurements only when referenced."""
    try:
        params = PassProbabilityParams.model_validate(args)
        state = None
        if any(item.recorded for item in params.evidence):
            from runner import repository

            state = repository.load_state(allow_missing_artifact=True)
            if not campaign_id or repository.current_campaign_id(state) != campaign_id:
                raise ValueError("tool campaign does not match the active Runner state")
        entries = []
        for item in params.evidence:
            if item.recorded:
                pooled = recorded_counts(state, item.recorded)
                if pooled["trials"] > 100_000:
                    raise ValueError(f"{item.label}: pooled trials exceed 100000")
                entries.append({"label": item.label, **pooled})
            else:
                entries.append(
                    {
                        "label": item.label,
                        "successes": item.successes,
                        "trials": item.trials,
                    }
                )
    except (OSError, TypeError, ValueError) as error:
        return json.dumps({"status": "invalid_request", "error": str(error)})
    target_rate = params.target.successes / params.target.trials
    results = []
    for entry in entries:
        interval = wilson_interval(
            entry["successes"], entry["trials"], params.confidence
        )
        if interval["lower"] > target_rate:
            relation = "above"
        elif interval["upper"] < target_rate:
            relation = "below"
        else:
            relation = "includes"
        results.append(
            {
                **entry,
                **interval,
                "interval_vs_target_rate": relation,
                "pass_probability": pass_probability(
                    entry["successes"], entry["trials"], params.target
                ),
            }
        )
    return json.dumps(
        {
            "status": "computed",
            "target": params.target.model_dump(),
            "target_rate": target_rate,
            "confidence": params.confidence,
            "true_rate_for_pass_probability": {
                str(level): rate_for_pass_probability(level, params.target)
                for level in PASS_LEVELS
            },
            "evidence": results,
            "assumptions": [
                "episodes are independent with one common success probability",
                "the evidence panels represent the target panel's distribution",
                (
                    "uniform prior; selecting the best of several candidates "
                    "makes its counts optimistic"
                ),
                "pooled sources that share episodes are not independent samples",
            ],
        },
        ensure_ascii=False,
    )
