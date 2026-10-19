"""Generic parsing of Stable-Baselines3 metric blocks from a training log.

Both the research brief and the live console progress read the same snapshots,
so the parsing lives here instead of being duplicated by either caller.
"""

from __future__ import annotations

import re

_SECTION_PATTERN = re.compile(r"\|\s+(rollout|time|train)/\s+\|")
_VALUE_PATTERN = re.compile(
    r"\|\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+\|\s+"
    r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?)\s+\|",
    flags=re.IGNORECASE,
)


def parse_training_records(text: str) -> list[dict[str, float]]:
    """Return every metric snapshot found in a Stable-Baselines3 log."""
    records: list[dict[str, float]] = []
    current: dict[str, float] = {}
    section = ""

    for line in text.splitlines():
        section_match = _SECTION_PATTERN.match(line)
        if section_match:
            next_section = section_match.group(1)
            if next_section == "rollout" and "total_timesteps" in current:
                records.append(current)
                current = {}
            section = next_section
            continue

        value_match = _VALUE_PATTERN.match(line)
        if value_match and section:
            key = value_match.group(1)
            try:
                current[key] = float(value_match.group(2))
            except ValueError:
                continue

    if current:
        records.append(current)
    return records


def latest_training_record(text: str) -> dict[str, float] | None:
    """Return the most recent snapshot that already reached the step counter."""
    for record in reversed(parse_training_records(text)):
        if "total_timesteps" in record:
            return record
    return None
