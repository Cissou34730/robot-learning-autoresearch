"""Wilson score interval for a success proportion from counts the PI supplies."""

from __future__ import annotations

import json
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

Z_95 = 1.959963984540054


class WilsonParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    successes: int = Field(ge=0, description="Number of successful trials.")
    trials: int = Field(ge=1, description="Total number of trials.")

    @model_validator(mode="after")
    def validate_counts(self) -> WilsonParams:
        if self.successes > self.trials:
            raise ValueError("successes must not exceed trials")
        return self


def wilson_interval(successes: int, trials: int) -> dict[str, Any]:
    proportion = successes / trials
    z_squared = Z_95 * Z_95
    denominator = 1 + z_squared / trials
    centre = (proportion + z_squared / (2 * trials)) / denominator
    half_width = (
        Z_95
        * math.sqrt(
            proportion * (1 - proportion) / trials + z_squared / (4 * trials**2)
        )
        / denominator
    )
    return {
        "status": "computed",
        "successes": successes,
        "trials": trials,
        "proportion": proportion,
        "confidence": 0.95,
        "method": "wilson_score",
        "lower": max(0.0, centre - half_width),
        "upper": min(1.0, centre + half_width),
        "assumption": "independent trials with one common success probability",
    }


def query_wilson_interval(args: dict[str, Any]) -> str:
    """Native custom-tool handler; it reads no campaign files."""
    try:
        params = WilsonParams.model_validate(args)
    except ValueError as error:
        return json.dumps({"status": "invalid_counts", "error": str(error)})
    return json.dumps(wilson_interval(params.successes, params.trials))
