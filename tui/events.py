"""Typed presentation events and the durable history adapter.

The report consumes one campaign-scoped typed event file. Records use a small
envelope and keep their payload uncompacted; unknown kinds and fields are
rendered generically by the timeline reducer.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from tui.observations import Observation
from tui.projector import parse_timestamp

SCHEMA_VERSION = 1
_TYPED_SUFFIX = ".events.jsonl"
_ENVELOPE_KEYS = {
    "schema_version",
    "event_id",
    "campaign_id",
    "ts",
    "kind",
    "scope",
    "severity",
    "operation_id",
    "session_id",
    "inquiry_id",
    "payload",
}


def _stable_event_id(line: str) -> str:
    return "line-" + hashlib.sha1(line.encode("utf-8")).hexdigest()[:16]


@dataclass
class TypedJsonlFeed:
    """Follows one campaign's typed event file by byte offset."""

    path: Path
    campaign_id: str | None = None
    rejected: str | None = None
    _offset: int = 0

    def reset(self) -> None:
        self._offset = 0

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
            return None
        if not isinstance(record, dict):
            return None
        if record.get("schema_version") != SCHEMA_VERSION:
            self.rejected = "unsupported typed event schema"
            return None
        campaign = record.get("campaign_id")
        if self.campaign_id is not None and campaign != self.campaign_id:
            self.rejected = "foreign campaign observation"
            return None
        kind = record.get("kind")
        if not isinstance(kind, str) or not kind:
            return None
        payload = record.get("payload")
        if not isinstance(payload, dict):
            payload = {
                key: value for key, value in record.items() if key not in _ENVELOPE_KEYS
            }
        event_id = str(record.get("event_id") or _stable_event_id(line))
        return Observation(
            kind=kind,
            ts=parse_timestamp(record.get("ts")) or datetime.now(tz=UTC),
            fields=payload,
            event_id=event_id,
            scope=str(record.get("scope") or ""),
            severity=str(record.get("severity") or ""),
            operation_id=str(record.get("operation_id") or ""),
            session_id=str(record.get("session_id") or ""),
            inquiry_id=str(record.get("inquiry_id") or ""),
            campaign_id=str(campaign or ""),
        )


def typed_path_for(campaign_id: str, root: Path | None = None) -> Path:
    from runner import paths

    base = root if root is not None else paths.ROOT
    return base / "reports" / "tui_observations" / f"{campaign_id}{_TYPED_SUFFIX}"


def _history_event(
    kind: str,
    *,
    event_id: str,
    ts: datetime | None = None,
    scope: str = "",
    severity: str = "info",
    operation_id: str = "",
    session_id: str = "",
    inquiry_id: str = "",
    payload: dict | None = None,
) -> Observation:
    return Observation(
        kind=kind,
        ts=ts,
        fields=payload or {},
        event_id=event_id,
        scope=scope,
        severity=severity,
        operation_id=operation_id,
        session_id=session_id,
        inquiry_id=inquiry_id,
    )


def synthesize_history(
    state: dict | None,
    records: list[dict],
    usage_rows: list[dict],
) -> list[Observation]:
    """Fold durable records into the same event shape as the live feed.

    The history is authoritative and complete. Live typed events add detail;
    the reducer deduplicates by event id.
    """
    state = state or {}
    events: list[Observation] = []
    campaign = state.get("campaign") if isinstance(state.get("campaign"), dict) else {}
    campaign_id = str(campaign.get("id") or "")
    started = parse_timestamp(campaign.get("started_at"))
    if campaign_id:
        events.append(
            _history_event(
                "campaign_started",
                event_id=f"history:campaign:{campaign_id}",
                ts=started,
                scope="campaign",
                payload={"campaign_id": campaign_id},
            )
        )

    session = state.get("scientific_session")
    if isinstance(session, dict) and session.get("id"):
        events.append(
            _history_event(
                "session_start",
                event_id=f"history:session:{session.get('id')}",
                ts=parse_timestamp(session.get("started_at")) or started,
                session_id=str(session.get("id") or ""),
                payload=dict(session),
            )
        )

    inquiry = state.get("active_inquiry")
    if isinstance(inquiry, dict):
        inquiry_id = str(inquiry.get("id") or "")
        if inquiry_id:
            events.append(
                _history_event(
                    "inquiry_opened",
                    event_id=f"history:inquiry:{inquiry_id}",
                    scope="inquiry",
                    session_id=str(session.get("id") or "")
                    if isinstance(session, dict)
                    else "",
                    inquiry_id=inquiry_id,
                    payload=dict(inquiry),
                )
            )

    candidates = state.get("candidates")
    if not isinstance(candidates, dict):
        candidates = {}
    for candidate_id, candidate in candidates.items():
        if not isinstance(candidate_id, str) or not isinstance(candidate, dict):
            continue
        events.append(
            _history_event(
                "candidate_created",
                event_id=f"history:candidate:{candidate_id}",
                scope="training",
                operation_id=str(candidate.get("origin_operation") or ""),
                payload={"candidate": candidate_id, **candidate},
            )
        )

    roles = state.get("model_roles")
    if isinstance(roles, dict):
        for role, candidate in roles.items():
            if role == "retained" and isinstance(candidate, dict):
                for label, retained in candidate.items():
                    if isinstance(retained, str) and retained:
                        events.append(
                            _history_event(
                                "role_assigned",
                                event_id=f"history:role:{retained}:retained:{label}",
                                scope="pi",
                                payload={
                                    "candidate": retained,
                                    "role": f"Retained: {label}",
                                },
                            )
                        )
                continue
            if isinstance(candidate, str) and candidate:
                events.append(
                    _history_event(
                        "role_assigned",
                        event_id=f"history:role:{candidate}:{role}",
                        scope="pi",
                        payload={
                            "candidate": candidate,
                            "role": role.replace("_", " ").title(),
                        },
                    )
                )

    for index, record in enumerate(records):
        kind = str(record.get("kind") or "operation")
        identity = str(record.get("id") or f"{kind}-{index}")
        stamp = parse_timestamp(record.get("completed_at"))
        status = str(record.get("status") or "")
        request = (
            record.get("request") if isinstance(record.get("request"), dict) else {}
        )
        result = record.get("result") if isinstance(record.get("result"), dict) else {}
        session_id = str(record.get("session_id") or "")
        inquiry_id = str(record.get("inquiry_id") or "")
        if kind == "inquiry":
            action = str(request.get("action") or "").lower()
            events.append(
                _history_event(
                    "inquiry_opened" if action == "open" else "inquiry_closed",
                    event_id=f"history:record:{identity}",
                    ts=stamp,
                    scope="inquiry",
                    session_id=session_id,
                    inquiry_id=str(record.get("inquiry_id") or inquiry_id),
                    payload={"id": identity, **request, **result},
                )
            )
            continue
        if kind == "model_role":
            candidate = request.get("candidate") or result.get("candidate")
            action = str(request.get("action") or result.get("action") or "role")
            events.append(
                _history_event(
                    "role_assigned",
                    event_id=f"history:record:{identity}",
                    ts=stamp,
                    scope="pi",
                    session_id=session_id,
                    inquiry_id=inquiry_id,
                    payload={
                        "candidate": candidate,
                        "role": action.replace("set_", "").replace("_", " ").title(),
                        "evidence": request.get("evidence") or result.get("evidence"),
                        "id": identity,
                    },
                )
            )
            continue
        if kind == "checkpoint":
            events.append(
                _history_event(
                    "checkpoint_saved",
                    event_id=f"history:record:{identity}",
                    ts=stamp,
                    scope="session",
                    session_id=session_id,
                    inquiry_id=inquiry_id,
                    payload={"id": identity, "session_id": session_id, **result},
                )
            )
            continue
        if kind == "campaign_conclusion":
            events.append(
                _history_event(
                    "campaign_concluded",
                    event_id=f"history:record:{identity}",
                    ts=stamp,
                    scope="campaign",
                    payload={"id": identity, **result},
                )
            )
            continue
        if status == "failed":
            events.append(
                _history_event(
                    "operation_failed",
                    event_id=f"history:record:{identity}",
                    ts=stamp,
                    scope="error",
                    severity="error",
                    operation_id=identity,
                    session_id=session_id,
                    inquiry_id=inquiry_id,
                    payload={
                        "id": identity,
                        "kind": kind,
                        "error": record.get("error"),
                        "request": request,
                        "result": result,
                    },
                )
            )
            continue
        if status != "completed":
            continue
        events.append(
            _history_event(
                "operation_completed",
                event_id=f"history:record:{identity}",
                ts=stamp,
                scope=kind,
                operation_id=identity,
                session_id=session_id,
                inquiry_id=inquiry_id,
                payload={
                    "id": identity,
                    "kind": kind,
                    "request": request,
                    "result": result,
                },
            )
        )

    pending = state.get("pending_operation")
    if isinstance(pending, dict) and pending.get("id"):
        events.append(
            _history_event(
                "operation_requested",
                event_id=f"history:pending:{pending.get('id')}",
                scope="operation",
                operation_id=str(pending.get("id") or ""),
                session_id=str(pending.get("session_id") or ""),
                inquiry_id=str(pending.get("inquiry_id") or ""),
                payload=dict(pending),
            )
        )

    if usage_rows:
        # The id follows the data, so a changed record reaches the timeline.
        digest = hashlib.sha1(
            json.dumps(usage_rows, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:12]
        events.append(
            _history_event(
                "usage_update",
                event_id=f"history:usage:{campaign_id}:{digest}",
                scope="usage",
                payload={"rows": usage_rows},
            )
        )

    return events
