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

import hashlib
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
    """Re-reads an observation JSONL file across reconnects.

    The file is treated as append-only content; a replayed line is rejected
    by fingerprint and a foreign campaign by its identity. That keeps the
    cursor trivial across atomic replacement and reconnects.
    """

    path: Path
    campaign_id: str | None = None
    max_dedupe: int = 4096

    _seen: dict = field(default_factory=dict)
    rejected: str | None = None

    def poll(self) -> list[Observation]:
        """All complete new events in the file, in file order."""
        try:
            text = self.path.read_text(encoding="utf-8")
        except OSError:
            return []
        events: list[Observation] = []
        lines = text.splitlines()
        complete = lines if text.endswith("\n") else lines[:-1]
        for line in complete:
            stripped = line.strip()
            if not stripped:
                continue
            event = self._event(stripped)
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
        if kind != "liveness" and kind not in KNOWN_KINDS:
            return None
        if self.campaign_id and record.get("campaign_id") not in (
            None,
            self.campaign_id,
        ):
            self.rejected = "foreign campaign observation"
            return None
        fingerprint = hashlib.sha1(line.encode()).hexdigest()
        if fingerprint in self._seen:
            return None
        self._seen[fingerprint] = True
        if len(self._seen) > self.max_dedupe:
            for stale in list(self._seen)[: self.max_dedupe // 2]:
                del self._seen[stale]
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
