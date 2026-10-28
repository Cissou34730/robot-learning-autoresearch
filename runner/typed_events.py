"""Writer of the campaign event journal (schema version 2).

The journal is one append-only JSON-lines file per campaign. Every event names
its owners explicitly (``runner.event_contract``); components bind their
identity once with ``context``/``bind`` instead of repeating it at each call.
Writing is best effort and one way: it never raises into the research code and
never changes campaign state. Each record is appended with one binary write.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from runner.event_contract import JOURNAL_SUFFIX, SCHEMA_VERSION, validate_record

FEED_ENV = "TUI_TYPED_EVENTS"
_FEED_DIR = Path("reports") / "tui_observations"
_DISABLED_VALUES = frozenset({"", "0", "off", "none", "false"})
_IDENTITY_KEYS = ("operation_id", "session_id", "inquiry_id", "attempt", "actor")

_path: Path | None = None
_resolved = False
_campaign_id: str | None = None
# Each process owns one piece of work at a time (one PI invocation, one
# operation). The owner is process-wide, not task-local: the Copilot SDK calls
# its handlers from its own tasks, which would not see a task-local value.
_owner: dict[str, str] = {}
failures = 0
# Tests set this so an emitter that breaks the identity contract fails loudly.
# In a campaign the event is still written and the reader reports it.
strict = False


class ContractViolation(Exception):
    """An event does not carry the identities its kind requires."""


def feed_directory() -> Path:
    from runner import paths

    return paths.ROOT / _FEED_DIR


def default_path(campaign_id: str) -> Path:
    return feed_directory() / f"{campaign_id}{JOURNAL_SUFFIX}"


def _state_campaign_id() -> str | None:
    from runner import paths

    try:
        state = json.loads(paths.STATE_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    campaign = state.get("campaign")
    value = campaign.get("id") if isinstance(campaign, dict) else None
    return str(value) if value else None


def configure(path: Path | None = None) -> None:
    global _path, _resolved, _campaign_id, failures
    if path is None:
        override = os.environ.get(FEED_ENV)
        if override is not None and override.strip().casefold() in _DISABLED_VALUES:
            _path = None
            _resolved = True
            return
        campaign = _campaign_id or _state_campaign_id()
        if campaign:
            _campaign_id = campaign
        if override:
            path = Path(override)
        else:
            if not campaign:
                return
            path = default_path(campaign)
    _path = Path(path)
    _resolved = True
    try:
        _path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        _path = None
        failures += 1


def reset() -> None:
    global _path, _resolved, _campaign_id
    _path = None
    _resolved = False
    _campaign_id = None
    _owner.clear()


def set_campaign(campaign_id: object) -> None:
    global _campaign_id
    text = str(campaign_id or "").strip()
    _campaign_id = text or None


@contextmanager
def context(
    *,
    operation_id: object = "",
    session_id: object = "",
    inquiry_id: object = "",
    attempt: object = "",
    actor: object = "",
) -> Iterator[None]:
    """Attach identities to every event emitted in this scope.

    A component calls this once where it takes ownership of a piece of work (a
    PI invocation, an operation) so every event it emits names its owners
    without threading them through presentation functions. Non-empty values
    override the enclosing scope; empty values inherit it.
    """
    token = bind(
        operation_id=operation_id,
        session_id=session_id,
        inquiry_id=inquiry_id,
        attempt=attempt,
        actor=actor,
    )
    try:
        yield
    finally:
        reset_context(token)


def bind(
    *,
    operation_id: object = "",
    session_id: object = "",
    inquiry_id: object = "",
    attempt: object = "",
    actor: object = "",
) -> dict[str, str]:
    """Bind identities until ``reset_context``; returns the previous owner."""
    previous = dict(_owner)
    for key, value in (
        ("operation_id", operation_id),
        ("session_id", session_id),
        ("inquiry_id", inquiry_id),
        ("attempt", attempt),
        ("actor", actor),
    ):
        text = str(value or "").strip()
        if text:
            _owner[key] = text
    return previous


def reset_context(previous: dict[str, str]) -> None:
    _owner.clear()
    _owner.update(previous)


def current_context() -> dict[str, str]:
    return dict(_owner)


def _append(path: Path, data: bytes) -> None:
    """Append one whole record with a single binary write."""
    descriptor = os.open(
        path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o666
    )
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(descriptor, view) :]
    finally:
        os.close(descriptor)


def emit(
    kind: str,
    payload: dict | None = None,
    *,
    scope: str = "",
    severity: str = "info",
    operation_id: str = "",
    session_id: str = "",
    inquiry_id: str = "",
    attempt: str = "",
    actor: str = "",
    event_id: str | None = None,
) -> None:
    """Append one event; never raise, never block, never answer."""
    global failures
    try:
        if not _resolved:
            configure()
        if _path is None:
            return
        current = _owner
        explicit = {
            "operation_id": operation_id,
            "session_id": session_id,
            "inquiry_id": inquiry_id,
            "attempt": attempt,
            "actor": actor,
        }
        record = {
            "schema_version": SCHEMA_VERSION,
            "event_id": event_id or str(uuid.uuid4()),
            "campaign_id": _campaign_id,
            "ts": datetime.now(UTC).isoformat(),
            "kind": kind,
            "scope": scope,
            "severity": severity,
            **{key: explicit[key] or current.get(key, "") for key in _IDENTITY_KEYS},
            "payload": payload or {},
        }
        if strict:
            problems = validate_record(record)
            if problems:
                raise ContractViolation("; ".join(problems))
        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
        _append(_path, line.encode("utf-8"))
    except ContractViolation:
        if strict:
            raise
        failures += 1
    except Exception:  # noqa: BLE001 - presentation must not affect execution
        failures += 1
