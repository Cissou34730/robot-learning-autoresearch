"""Reader of a campaign's event journal (schema version 2).

The journal is one append-only JSON-lines file per campaign. Every line is one
event with an envelope of explicit identities (see ``runner.event_contract``).
The reader follows the file by byte offset: it replays from the start, then
returns only what was appended. A final line without its newline is a write in
progress and is kept for the next poll; a complete line that cannot be decoded
is reported, not skipped silently.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from runner.event_contract import ENVELOPE_FIELDS, JOURNAL_SUFFIX, SCHEMA_VERSION
from tui.observations import Observation
from tui.projector import parse_timestamp

_ENVELOPE_KEYS = frozenset(ENVELOPE_FIELDS)


def journal_path_for(campaign_id: str, root: Path | None = None) -> Path:
    from runner import paths

    base = root if root is not None else paths.ROOT
    return base / "reports" / "tui_observations" / f"{campaign_id}{JOURNAL_SUFFIX}"


def _stable_event_id(line: str) -> str:
    return "line-" + hashlib.sha1(line.encode("utf-8")).hexdigest()[:16]


@dataclass
class JournalFeed:
    """Follows one campaign's journal file."""

    path: Path
    campaign_id: str | None = None
    rejected: str | None = None
    _offset: int = 0

    def reset(self) -> None:
        self._offset = 0
        self.rejected = None

    @property
    def exists(self) -> bool:
        return self.path.exists()

    def poll(self) -> list[Observation]:
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
            self.rejected = "a complete journal line could not be decoded"
            return None
        if not isinstance(record, dict):
            self.rejected = "a journal line is not an object"
            return None
        if record.get("schema_version") != SCHEMA_VERSION:
            self.rejected = "unsupported journal schema"
            return None
        campaign = record.get("campaign_id")
        if self.campaign_id is not None and campaign != self.campaign_id:
            self.rejected = "foreign campaign event"
            return None
        kind = record.get("kind")
        if not isinstance(kind, str) or not kind:
            self.rejected = "a journal line has no kind"
            return None
        payload = record.get("payload")
        if not isinstance(payload, dict):
            payload = {
                key: value for key, value in record.items() if key not in _ENVELOPE_KEYS
            }
        return Observation(
            kind=kind,
            ts=parse_timestamp(record.get("ts")) or datetime.now(tz=UTC),
            fields=payload,
            event_id=str(record.get("event_id") or _stable_event_id(line)),
            scope=str(record.get("scope") or ""),
            severity=str(record.get("severity") or ""),
            operation_id=str(record.get("operation_id") or ""),
            session_id=str(record.get("session_id") or ""),
            inquiry_id=str(record.get("inquiry_id") or ""),
            campaign_id=str(campaign or ""),
            attempt=str(record.get("attempt") or ""),
            actor=str(record.get("actor") or ""),
        )
