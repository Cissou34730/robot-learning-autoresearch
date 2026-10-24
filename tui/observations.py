"""One-way observation feed for the report.

Producer-side instrumentation is intentionally out of this pass: the report
consumes a structured JSONL event file when one exists and stays fully
readable from durable state when it does not.

Expected record shape (one JSON object per line):

    {"campaign_id": "...", "ts": "<RFC3339>", "kind": "...", ...}

Preliminary kinds:

- `session_start`  {session_id, stage}
- `activity`       {label}
- `pi_message`     {session_id, text}      full PI message text, once
- `tool`           {agent, name, detail}   routine quiet entries
- `console_line`   {scope, text}           durable runner output lines
- `training_progress` {operation_id, attempt, steps, target, elapsed_seconds}
- `eval_progress`  {operation_id, instrument, official, panel_index,
                    panel_total, completed_panels, episodes, episodes_total,
                    elapsed_seconds}
- `execution_end`  {operation_id, status, text}
- `liveness`       {}                      publisher is current

The feed keeps only dedupe fingerprints in memory. It never writes, never
answers, and cannot influence execution; a foreign-campaign event is rejected
rather than rendered, and a streamed/final duplicate is rendered once.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from tui.projector import parse_timestamp


@dataclass(frozen=True)
class Observation:
    kind: str
    ts: datetime | None
    fields: dict = field(default_factory=dict)


TRAINING_KIND = "training_progress"
EVAL_KIND = "eval_progress"

KNOWN_KINDS = frozenset(
    {
        "session_start",
        "activity",
        "pi_message",
        "tool",
        "console_line",
        TRAINING_KIND,
        EVAL_KIND,
        "execution_end",
        "liveness",
    }
)


def feed_age_seconds(stamp: datetime | None, now: datetime) -> float | None:
    if stamp is None:
        return None
    return (now - stamp).total_seconds()


@dataclass
class JsonlFeed:
    """Follows one campaign's observation file by byte offset.

    Only new complete lines are read, so polling cost is proportional to what
    was appended, not to the file size, and replayed lines cannot resurface.
    A shrunken or replaced file restarts from the beginning.
    """

    path: Path
    campaign_id: str | None = None
    rejected: str | None = None
    _offset: int = 0

    def reset(self) -> None:
        """Read the file from the beginning on the next poll."""
        self._offset = 0

    def poll(self) -> list[Observation]:
        """All complete new events in the file, in file order."""
        try:
            size = self.path.stat().st_size
        except OSError:
            return []
        if size < self._offset:
            self._offset = 0
        if size == self._offset:
            return []
        try:
            with self.path.open("rb") as handle:
                handle.seek(self._offset)
                chunk = handle.read()
        except OSError:
            return []
        newline = chunk.rfind(b"\n")
        if newline < 0:
            # A partial trailing line; it is read once it is complete.
            return []
        complete = chunk[: newline + 1]
        self._offset += len(complete)
        events: list[Observation] = []
        for raw in complete.splitlines():
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            event = self._event(line)
            if event is not None:
                events.append(event)
        return events

    def _event(self, line: str) -> Observation | None:
        try:
            record = json.loads(line)
        except ValueError:
            return None
        if not isinstance(record, dict):
            return None
        kind = record.get("kind")
        if kind not in KNOWN_KINDS:
            return None
        if (
            self.campaign_id is not None
            and record.get("campaign_id") != self.campaign_id
        ):
            self.rejected = "foreign campaign observation"
            return None
        stamp = parse_timestamp(record.get("ts")) or datetime.now(tz=UTC)
        return Observation(
            kind=str(kind),
            ts=stamp,
            fields={
                k: v
                for k, v in record.items()
                if k not in {"kind", "ts", "campaign_id"}
            },
        )


class SyntheticFeed:
    """Scripted events advancing on a clock, for demos and headless tests."""

    def __init__(self, schedule: list[tuple[float, Observation]]) -> None:
        self._schedule = list(schedule)
        self._elapsed = 0.0
        self._index = 0

    def advance(self, seconds: float) -> None:
        self._elapsed += seconds

    def poll(self) -> list[Observation]:
        due: list[Observation] = []
        while self._index < len(self._schedule):
            at, event = self._schedule[self._index]
            if at > self._elapsed:
                break
            due.append(event)
            self._index += 1
        return due

    def reset(self) -> None:
        """Restart from the beginning without firing any event."""
        self._index = 0
        self._elapsed = 0.0

    @property
    def exhausted(self) -> bool:
        return self._index >= len(self._schedule)


def iter_jsonl(path: Path) -> Iterator[dict]:  # pragma: no cover - helper for tests
    from tui.sources import read_jsonl

    return iter(read_jsonl(path))
