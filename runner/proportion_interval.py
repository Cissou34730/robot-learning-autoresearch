"""Wilson score intervals for success proportions from counts the PI supplies."""

from __future__ import annotations

import json
import math
from statistics import NormalDist
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Proportion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=128, description="Your name for it.")
    successes: int = Field(ge=0)
    trials: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_counts(self) -> Proportion:
        if self.successes > self.trials:
            raise ValueError("successes must not exceed trials")
        return self


class WilsonParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confidence: float = Field(
        ge=0.5, le=0.999, description="Two-sided confidence level that you choose."
    )
    proportions: list[Proportion] = Field(min_length=1, max_length=20)
    threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional rate to compare with each interval.",
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


def relation_to_threshold(lower: float, upper: float, threshold: float) -> str:
    if lower > threshold:
        return "above"
    if upper < threshold:
        return "below"
    return "includes"


def query_wilson_interval(args: dict[str, Any]) -> str:
    """Native custom-tool handler; it reads no campaign files."""
    try:
        params = WilsonParams.model_validate(args)
    except ValueError as error:
        return json.dumps({"status": "invalid_request", "error": str(error)})
    intervals = []
    for item in params.proportions:
        interval = {
            **item.model_dump(),
            **wilson_interval(item.successes, item.trials, params.confidence),
        }
        if params.threshold is not None:
            interval["threshold_relation"] = relation_to_threshold(
                interval["lower"], interval["upper"], params.threshold
            )
        intervals.append(interval)
    return json.dumps(
        {
            "status": "computed",
            "method": "wilson_score",
            "confidence": params.confidence,
            "threshold": params.threshold,
            "assumption": "independent trials with one common success probability",
            "intervals": intervals,
        },
        ensure_ascii=False,
    )
