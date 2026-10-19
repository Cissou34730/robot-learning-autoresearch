"""Scenario-owned live training signal for the generic console.

The runner appends the returned fragment verbatim and never learns what it
measures; another scenario returns its own phrase or nothing at all.
"""

from collections.abc import Mapping


def render_training_progress_metric(metrics: Mapping[str, float]) -> str | None:
    value = metrics.get("success_rate", metrics.get("training_success"))
    if value is None:
        return None
    try:
        rate = float(value)
    except (TypeError, ValueError):
        return None
    return f"success {100 * rate:.0f}%"
