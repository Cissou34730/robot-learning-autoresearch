"""Maintainer-only typed event feed for the structured operator log.

The feed is a sibling of ``observation_feed``: one JSON object per line, one
file per campaign, best-effort and one-way. It carries full payloads before
console formatting shortens them. The campaign state, results and console
stdout are never modified.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from pathlib import Path

FEED_ENV = "TUI_TYPED_EVENTS"
SCHEMA_VERSION = 1
_FEED_DIR = Path("reports") / "tui_observations"
_DISABLED_VALUES = frozenset({"", "0", "off", "none", "false"})

_path: Path | None = None
_resolved = False
_campaign_id: str | None = None
_context: ContextVar[dict[str, str] | None] = ContextVar(
    "typed_event_context", default=None
)
failures = 0


def feed_directory() -> Path:
    from runner import paths

    return paths.ROOT / _FEED_DIR


def default_path(campaign_id: str) -> Path:
    return feed_directory() / f"{campaign_id}.events.jsonl"


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
    _context.set(None)


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
) -> Iterator[None]:
    """Attach the current operation to every event emitted in this scope.

    Handlers call this around one operation so console fallbacks and domain
    events share the same identity without threading it through presentation
    functions. Non-empty values override the enclosing scope; empty values
    inherit it, so an operation inside a session keeps both identities.
    """
    token = bind(
        operation_id=operation_id, session_id=session_id, inquiry_id=inquiry_id
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
) -> Token:
    """Return a token for a caller that cannot wrap the scope in ``with``."""
    current = dict(_context.get() or {})
    for key, value in (
        ("operation_id", operation_id),
        ("session_id", session_id),
        ("inquiry_id", inquiry_id),
    ):
        text = str(value or "").strip()
        if text:
            current[key] = text
        current.setdefault(key, "")
    return _context.set(current)


def reset_context(token: Token) -> None:
    _context.reset(token)


def current_context() -> dict[str, str]:
    return dict(_context.get() or {})


def emit(
    kind: str,
    payload: dict | None = None,
    *,
    scope: str = "",
    severity: str = "info",
    operation_id: str = "",
    session_id: str = "",
    inquiry_id: str = "",
    event_id: str | None = None,
) -> None:
    """Append one typed event; never raise, never block, never answer."""
    global failures
    try:
        if not _resolved:
            configure()
        if _path is None:
            return
        current = _context.get() or {}
        record = {
            "schema_version": SCHEMA_VERSION,
            "event_id": event_id or str(uuid.uuid4()),
            "campaign_id": _campaign_id,
            "ts": datetime.now(UTC).isoformat(),
            "kind": kind,
            "scope": scope,
            "severity": severity,
            "operation_id": operation_id or current.get("operation_id", ""),
            "session_id": session_id or current.get("session_id", ""),
            "inquiry_id": inquiry_id or current.get("inquiry_id", ""),
            "payload": payload or {},
        }
        line = json.dumps(record, ensure_ascii=False, default=str)
        with open(_path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:  # noqa: BLE001 - presentation must not affect execution
        failures += 1
