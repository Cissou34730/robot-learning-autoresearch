"""Bounded numeric summary of one preserved training metric, with optional checks."""

from __future__ import annotations

import json
import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from runner import repository
from runner.query_training_log import (
    MAX_PARSE_BYTES,
    _log_bytes,
    _training_operation,
    selected_records,
    training_log_paths,
)


class SeriesCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statistic: Literal["min", "max", "mean", "first", "last"] = Field(
        description="Window statistic to compare with threshold."
    )
    comparison: Literal[">=", "<="]
    threshold: float = Field(allow_inf_nan=False, description="Value that you choose.")


class TrainingSeriesParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str = Field(
        pattern=r"^T[1-9]\d*$",
        description="Training operation in the active campaign.",
    )
    attempt: int | None = Field(
        default=None,
        ge=1,
        description="Attempt number. Required when the operation has several logs.",
    )
    metric: str = Field(
        min_length=1,
        max_length=256,
        description="Exact metric name, as listed by training_log_query discover.",
    )
    from_step: int = Field(default=0, ge=0, description="Inclusive lower timestep.")
    to_step: int | None = Field(
        default=None, ge=0, description="Inclusive upper timestep; omit for the end."
    )
    checks: list[SeriesCheck] = Field(
        default_factory=list,
        max_length=20,
        description="Optional comparisons evaluated over the same window.",
    )

    @model_validator(mode="after")
    def validate_window(self) -> TrainingSeriesParams:
        if self.to_step is not None and self.to_step < self.from_step:
            raise ValueError("timestep bounds must satisfy from_step <= to_step")
        return self


def window_statistics(points: list[tuple[int, float]]) -> dict[str, Any]:
    values = [value for _, value in points]
    count = len(points)
    mean = math.fsum(values) / count
    sample_sd = (
        math.sqrt(math.fsum((value - mean) ** 2 for value in values) / (count - 1))
        if count > 1
        else None
    )
    lowest = min(values)
    highest = max(values)
    return {
        "rows": count,
        "first": {"step": points[0][0], "value": points[0][1]},
        "last": {"step": points[-1][0], "value": points[-1][1]},
        "min": {
            "value": lowest,
            "first_step": next(step for step, value in points if value == lowest),
            "rows_at_value": values.count(lowest),
        },
        "max": {
            "value": highest,
            "first_step": next(step for step, value in points if value == highest),
            "rows_at_value": values.count(highest),
        },
        "mean": mean,
        "sample_sd": sample_sd,
    }


def evaluate_check(
    check: SeriesCheck, summary: dict[str, Any], points: list[tuple[int, float]]
) -> dict[str, Any]:
    statistic = summary[check.statistic]
    value = statistic if check.statistic == "mean" else statistic["value"]

    def meets(candidate: float) -> bool:
        return (
            candidate >= check.threshold
            if check.comparison == ">="
            else candidate <= check.threshold
        )

    result: dict[str, Any] = {
        **check.model_dump(),
        "value": value,
        "holds": meets(value),
    }
    if check.statistic in {"min", "max"}:
        # For min/max, the rows that fail the comparison are the counterexamples.
        failing = [step for step, candidate in points if not meets(candidate)]
        result["rows_not_meeting"] = len(failing)
        result["first_step_not_meeting"] = failing[0] if failing else None
        result["last_step_not_meeting"] = failing[-1] if failing else None
    return result


def query_training_series(args: dict[str, Any], campaign_id: str) -> str:
    """Native custom-tool handler; it never executes commands or accepts paths."""
    provenance: dict[str, Any] = {"campaign_id": campaign_id}
    try:
        params = TrainingSeriesParams.model_validate(args)
        state = repository.load_state(allow_missing_artifact=True)
        if not campaign_id or repository.current_campaign_id(state) != campaign_id:
            raise ValueError("tool campaign does not match the active Runner state")
        provenance.update(
            operation_id=params.operation_id,
            operation_kind="training",
            **_training_operation(state, params.operation_id),
        )
        logs = training_log_paths(params.operation_id, state=state)
        provenance["available_attempts"] = [attempt for attempt, _ in logs]
        if not logs:
            return json.dumps({"status": "no_logs", "provenance": provenance})
        if params.attempt is None and len(logs) > 1:
            return json.dumps(
                {
                    "status": "attempt_required",
                    "provenance": provenance,
                    "recovery": "Set attempt to one of available_attempts.",
                }
            )
        selected = [item for item in logs if params.attempt in {None, item[0]}]
        if not selected:
            return json.dumps(
                {
                    "status": "logs_unavailable",
                    "missing_attempts": [params.attempt],
                    "provenance": provenance,
                }
            )
        attempt, path = selected[0]
        content, identity = _log_bytes(path)
        provenance["log"] = {"attempt": attempt, **identity}
        if identity["total_bytes"] > MAX_PARSE_BYTES:
            return json.dumps(
                {
                    "status": "parse_budget_exhausted",
                    "provenance": provenance,
                    "max_parse_bytes": MAX_PARSE_BYTES,
                    "recovery": "Use training_log_query raw pages for this log.",
                }
            )
        records = [
            record
            for _, record in selected_records(
                params.operation_id,
                params.from_step,
                params.to_step,
                logs=[(attempt, path)],
                texts={attempt: content.decode("utf-8")},
            )
        ]
        base: dict[str, Any] = {
            "provenance": provenance,
            "metric": params.metric,
            "from_step": params.from_step,
            "to_step": params.to_step,
            "rows_in_window": len(records),
        }
        if not any(params.metric in record for record in records):
            available = sorted(
                {name for record in records for name in record} - {"total_timesteps"}
            )
            return json.dumps(
                {
                    "status": "metric_absent" if records else "no_matching_rows",
                    **base,
                    "available_metrics": available[:50],
                    "available_metric_count": len(available),
                },
                ensure_ascii=False,
            )
        points = sorted(
            (int(record["total_timesteps"]), float(record[params.metric]))
            for record in records
            if params.metric in record and math.isfinite(record[params.metric])
        )
        base["rows_without_finite_value"] = len(records) - len(points)
        if not points:
            return json.dumps(
                {"status": "no_finite_values", **base}, ensure_ascii=False
            )
        summary = window_statistics(points)
        payload: dict[str, Any] = {"status": "computed", **base, "window": summary}
        if params.checks:
            payload["checks"] = [
                evaluate_check(check, summary, points) for check in params.checks
            ]
        return json.dumps(payload, ensure_ascii=False)
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        return json.dumps(
            {"status": "query_failed", "error": str(error), "provenance": provenance}
        )
