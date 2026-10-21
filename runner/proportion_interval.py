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


class Evidence(Counts):
    label: str = Field(min_length=1, max_length=128, description="Your name for it.")


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
        description="Measured counts; pool panels yourself as a separate entry.",
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


def query_pass_probability(args: dict[str, Any]) -> str:
    """Native custom-tool handler; it reads no campaign files."""
    try:
        params = PassProbabilityParams.model_validate(args)
    except ValueError as error:
        return json.dumps({"status": "invalid_request", "error": str(error)})
    target_rate = params.target.successes / params.target.trials
    results = []
    for item in params.evidence:
        interval = wilson_interval(item.successes, item.trials, params.confidence)
        if interval["lower"] > target_rate:
            relation = "above"
        elif interval["upper"] < target_rate:
            relation = "below"
        else:
            relation = "includes"
        results.append(
            {
                **item.model_dump(),
                **interval,
                "interval_vs_target_rate": relation,
                "pass_probability": pass_probability(
                    item.successes, item.trials, params.target
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
            ],
        },
        ensure_ascii=False,
    )
