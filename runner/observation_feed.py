"""One-way observation feed for the read-only terminal report.

The report follows a JSONL file of presentation events. This module appends
those events and does nothing else: no acks, no control channel, no state.
Every failure is counted and swallowed, so presenting can never alter
operation acceptance, execution, publication or recovery.

The feed writes to ``reports/tui_observations/<campaign>.jsonl`` under the
campaign root (that directory is presentation-only, ignored by campaign Git,
and refused to the PI and analyst). Set ``TUI_OBSERVATIONS`` to another path
to move it, or to ``off`` to disable it.

Each record is one JSON object per line::

    {"campaign_id": "...", "ts": "<RFC3339>", "kind": "...", ...}

Kinds emitted by the Runner:

- ``console_line``       {scope, text}                visible Runner output
- ``pi_message``         {session_id?, text}          one complete PI message
- ``training_progress``  {operation_id, steps, target, elapsed_seconds}
- ``eval_progress``      {operation_id, instrument, official, episodes,
                          episodes_total, elapsed_seconds}
- ``execution_end``      {operation_id, status, text?}
- ``liveness``           {}                           publisher is current
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

FEED_ENV = "TUI_OBSERVATIONS"
_FEED_DIR = Path("reports") / "tui_observations"
_DISABLED_VALUES = frozenset({"", "0", "off", "none", "false"})

_path: Path | None = None
_resolved = False
_campaign_id: str | None = None
failures = 0


def feed_directory() -> Path:
    """The campaign-scoped presentation archive folder for the report."""
    from runner import paths

    return paths.ROOT / _FEED_DIR


def default_path(campaign_id: str) -> Path:
    """One feed file per campaign, so a reset cannot surface old events."""
    return feed_directory() / f"{campaign_id}.jsonl"


def _state_campaign_id() -> str | None:
    """Read the campaign identity from durable state; the feed never invents it."""
    from runner import paths

    try:
        state = json.loads(paths.STATE_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    campaign = state.get("campaign")
    value = campaign.get("id") if isinstance(campaign, dict) else None
    return str(value) if value else None


def configure(path: Path | None = None) -> None:
    """Resolve the feed target once.

    Without an explicit path the ``TUI_OBSERVATIONS`` environment variable
    selects the file; unset means ``reports/tui_observations/<campaign>.jsonl``
    for the campaign named by durable state. A disabled value (``off``,
    ``0``, empty, ...) turns the feed off. Until the campaign identity exists,
    the feed stays unresolved and events are skipped.
    """
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
    """Forget the resolved target; the next emit resolves it again."""
    global _path, _resolved, _campaign_id
    _path = None
    _resolved = False
    _campaign_id = None


def set_campaign(campaign_id: object) -> None:
    """Bind events to the campaign that owns them."""
    global _campaign_id
    text = str(campaign_id or "").strip()
    _campaign_id = text or None


def emit(payload: dict) -> None:
    """Append one event; never raise, never block, never answer."""
    global failures
    try:
        if not _resolved:
            configure()
        if _path is None:
            return
        record = {"campaign_id": _campaign_id, "ts": datetime.now(UTC).isoformat()}
        record.update(payload)
        line = json.dumps(record, ensure_ascii=False, default=str)
        with open(_path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:  # noqa: BLE001 - presentation must not affect execution
        failures += 1
