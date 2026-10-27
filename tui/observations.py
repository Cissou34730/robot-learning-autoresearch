"""Observation records shown by the report, and the synthetic demo feed.

Live observations come only from the campaign's event journal
(``<campaign>.events.v2.jsonl``, see ``tui.journal``). The header band and the
model table also read the durable state; the log never does.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Observation:
    """One event as the reducer sees it.

    ``session_id`` is the durable session key (``S<n>`` or the constant
    preparation key). ``attempt`` names the PI invocation and ``actor`` who spoke
    (pi, coder, reviewer, runner, launcher); both only disambiguate rows.
    """

    kind: str
    ts: datetime | None
    fields: dict = field(default_factory=dict)
    event_id: str = ""
    scope: str = ""
    severity: str = ""
    operation_id: str = ""
    session_id: str = ""
    inquiry_id: str = ""
    campaign_id: str = ""
    attempt: str = ""
    actor: str = ""


def feed_age_seconds(stamp: datetime | None, now: datetime) -> float | None:
    if stamp is None:
        return None
    return (now - stamp).total_seconds()


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
