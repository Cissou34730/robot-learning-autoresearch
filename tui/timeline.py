"""Structured timeline reducer for the operator log.

The reducer is deliberately terminal-free: events in, a small tree of
display items out. The Textual widget only renders this tree and keeps the
user's expansion and selection state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from runner import console
from tui.observations import Observation

KIND_GLYPHS = {
    "campaign": "[C]",
    "session": "[S]",
    "inquiry": "[I]",
    "training": "[T]",
    "measurement": "[M]",
    "event": "[E]",
    "operation": "[E]",
    "pi": "[P]",
    "tool": "[>]",
    "result": "[=]",
    "checkpoint": "[#]",
    "role": "[R]",
    "warning": "[!]",
    "error": "[x]",
    "usage": "[U]",
    "log": "[.]",
}

FILTER_CATEGORIES = {
    "sessions": {"session"},
    "inquiries": {"inquiry"},
    "training": {"training", "training_progress"},
    "measurements": {"measurement", "eval_progress"},
    "tools": {"tool", "tool_call"},
    "pi": {"pi_message"},
    "roles": {"role", "role_assigned", "candidate_created", "checkpoint_saved"},
    "usage": {"usage", "usage_update"},
    "warnings": {"warning", "error", "operation_failed"},
    "operations": {
        "operation",
        "operation_requested",
        "operation_started",
        "operation_completed",
        "operation_failed",
        "execution_end",
        "campaign_started",
        "campaign_concluded",
        "run_state",
        "console_line",
        "console_card",
    },
}


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _clock(stamp: datetime | None) -> str:
    if stamp is None:
        return "--:--:--"
    return f"{stamp.astimezone():%H:%M:%S}"


def _duration(start: datetime | None, end: datetime | None) -> str:
    if start is None:
        return ""
    finish = end or _now()
    seconds = max(0.0, (finish - start).total_seconds())
    return console.format_duration(seconds)


def _first_line(text: object, limit: int = 120) -> str:
    value = " ".join(str(text or "").split())
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "..."


def _short(value: object, limit: int = 160) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def _json_text(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except (TypeError, ValueError):
        return str(value)


def _number(value: object) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.1f}"
    return "unavailable"


def _percent(value: object) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{float(value):g}%"
    return "unavailable"


@dataclass
class TimelineItem:
    """One group or leaf in the operator timeline."""

    item_id: str
    kind: str
    title: str
    summary: str = ""
    ts: datetime | None = None
    end_ts: datetime | None = None
    severity: str = "info"
    detail: tuple[str, ...] = ()
    children: list[TimelineItem] = field(default_factory=list)
    default_expanded: bool = False
    is_group: bool = False
    event_id: str = ""
    payload: dict = field(default_factory=dict)
    status: str = ""
    role: str = ""

    @property
    def glyph(self) -> str:
        return KIND_GLYPHS.get(self.kind, "[.]")

    def duration_text(self) -> str:
        return _duration(self.ts, self.end_ts) if self.is_group else ""

    def searchable(self) -> str:
        parts = [self.title, self.summary, self.kind, self.status, *self.detail]
        if self.payload:
            parts.append(_json_text(self.payload))
        return "\n".join(parts).casefold()


class TimelineReducer:
    """Events in, grouped timeline out. No terminal and no campaign writes."""

    def __init__(self) -> None:
        self._items: dict[str, TimelineItem] = {}
        self._roots: list[TimelineItem] = []
        self._seen: set[str] = set()
        self._sessions: dict[str, TimelineItem] = {}
        self._inquiries: dict[str, TimelineItem] = {}
        self._operations: dict[str, TimelineItem] = {}
        self._progress: dict[str, tuple[datetime | None, int | None]] = {}
        self._pi_items: dict[str, TimelineItem] = {}
        self._pi_text: dict[str, str] = {}
        self._current_session = ""
        self._current_inquiry = ""
        self._active_operation = ""
        self._run_state = ""
        self._last_completed = ""
        self._last_completed_kind = ""
        self._last_completed_ts: datetime | None = None

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------

    def clear(self) -> None:
        self.__init__()

    def ingest(self, event: Observation) -> None:
        event_id = event.event_id or self._fallback_id(event)
        if event_id in self._seen:
            return
        self._seen.add(event_id)
        kind = event.kind
        fields = event.fields or {}
        ts = event.ts
        session_id = event.session_id or str(fields.get("session_id") or "")
        inquiry_id = event.inquiry_id or str(fields.get("inquiry_id") or "")
        operation_id = event.operation_id or str(
            fields.get("operation_id") or fields.get("id") or ""
        )
        if kind == "session_start":
            self._session(session_id or str(fields.get("id") or ""), ts, fields)
            return
        if kind in {"inquiry_opened", "inquiry_closed"}:
            self._inquiry_event(kind, inquiry_id, session_id, ts, fields)
            return
        if kind in {
            "operation_requested",
            "operation_started",
            "operation_progress",
            "operation_completed",
            "operation_failed",
            "execution_end",
        }:
            self._operation_event(
                kind, operation_id, inquiry_id, session_id, ts, fields
            )
            return
        if kind in {"training_progress", "eval_progress"}:
            self._progress_event(kind, operation_id, inquiry_id, session_id, ts, fields)
            return
        if kind in {"pi_message"}:
            self._pi_event(ts, session_id, inquiry_id, operation_id, fields)
            return
        if kind in {"tool", "tool_call"}:
            self._tool_event(ts, session_id, inquiry_id, operation_id, fields)
            return
        if kind in {"role_assigned", "candidate_created", "checkpoint_saved"}:
            self._simple_event(kind, ts, session_id, inquiry_id, operation_id, fields)
            return
        if kind in {"usage", "usage_update"}:
            self._usage_event(ts, session_id, fields)
            return
        if kind in {"warning", "error"}:
            self._warning_event(kind, ts, session_id, inquiry_id, operation_id, fields)
            return
        if kind in {"campaign_started", "campaign_concluded", "run_state"}:
            self._root_event(kind, ts, fields)
            return
        if kind in {"console_line", "console_card"}:
            self._console_event(ts, session_id, inquiry_id, operation_id, fields)
            return
        if kind in {"activity"}:
            self._simple_event(
                "activity", ts, session_id, inquiry_id, operation_id, fields
            )
            return
        self._simple_event(kind, ts, session_id, inquiry_id, operation_id, fields)

    @staticmethod
    def _fallback_id(event: Observation) -> str:
        return f"legacy:{event.kind}:{event.ts}:{hash(json.dumps(event.fields, default=str))}"

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------

    def _add_root(self, item: TimelineItem) -> TimelineItem:
        self._items[item.item_id] = item
        self._roots.append(item)
        return item

    def _campaign_group(self) -> TimelineItem:
        item = self._items.get("campaign:root")
        if item is None:
            item = TimelineItem(
                item_id="campaign:root",
                kind="campaign",
                title="Campaign",
                is_group=True,
                default_expanded=False,
            )
            self._items[item.item_id] = item
            self._roots.insert(0, item)
        return item

    def _session(
        self, session_id: str, ts: datetime | None, fields: dict
    ) -> TimelineItem | None:
        if not session_id:
            return None
        item = self._sessions.get(session_id)
        if item is None:
            kind = str(fields.get("kind") or "session").replace("_", " ")
            title = f"{session_id} {kind}".strip()
            item = self._add_root(
                TimelineItem(
                    item_id=f"session:{session_id}",
                    kind="session",
                    title=title,
                    ts=ts,
                    is_group=True,
                    default_expanded=False,
                    payload=dict(fields),
                )
            )
            self._sessions[session_id] = item
        if ts is not None:
            item.end_ts = ts if item.end_ts is None else max(item.end_ts, ts)
        self._current_session = session_id
        return item

    def _inquiry(
        self,
        inquiry_id: str,
        session_id: str,
        ts: datetime | None,
        fields: dict,
    ) -> TimelineItem | None:
        if not inquiry_id:
            return None
        item = self._inquiries.get(inquiry_id)
        if item is None:
            question = _first_line(
                fields.get("question") or fields.get("summary") or "", 90
            )
            title = f"{inquiry_id} {question}".strip()
            item = TimelineItem(
                item_id=f"inquiry:{inquiry_id}",
                kind="inquiry",
                title=title,
                ts=ts,
                is_group=True,
                default_expanded=False,
                payload=dict(fields),
            )
            self._items[item.item_id] = item
            parent = self._session(session_id, ts, {})
            if parent is not None:
                parent.children.append(item)
            else:
                self._roots.append(item)
            self._inquiries[inquiry_id] = item
        if ts is not None:
            item.end_ts = ts if item.end_ts is None else max(item.end_ts, ts)
        self._current_inquiry = inquiry_id
        return item

    def _operation(
        self,
        operation_id: str,
        inquiry_id: str,
        session_id: str,
        ts: datetime | None,
        kind: str,
    ) -> TimelineItem | None:
        if not operation_id:
            return None
        item = self._operations.get(operation_id)
        if item is None:
            item = TimelineItem(
                item_id=f"operation:{operation_id}",
                kind=kind or "operation",
                title=f"{operation_id} {kind or 'operation'}",
                ts=ts,
                is_group=True,
                default_expanded=False,
                status="requested",
            )
            self._items[item.item_id] = item
            parent = self._inquiry(inquiry_id, session_id, ts, {})
            if parent is None:
                parent = self._session(session_id, ts, {})
            if parent is not None:
                parent.children.append(item)
            else:
                self._roots.append(item)
            self._operations[operation_id] = item
        if ts is not None:
            item.end_ts = ts if item.end_ts is None else max(item.end_ts, ts)
        return item

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _inquiry_event(
        self,
        kind: str,
        inquiry_id: str,
        session_id: str,
        ts: datetime | None,
        fields: dict,
    ) -> None:
        item = self._inquiry(inquiry_id, session_id, ts, fields)
        if item is None:
            return
        if kind == "inquiry_closed":
            item.status = "closed"
            item.end_ts = ts or item.end_ts
        leaf = TimelineItem(
            item_id=f"leaf:{kind}:{inquiry_id}:{ts}",
            kind="inquiry",
            title="inquiry opened" if kind == "inquiry_opened" else "inquiry closed",
            summary="",
            ts=ts,
            detail=tuple(
                line
                for line in (
                    f"Question: {_first_line(fields.get('question'))}"
                    if fields.get("question")
                    else "",
                    f"Closure: {_first_line(fields.get('closure_condition'))}"
                    if fields.get("closure_condition")
                    else "",
                )
                if line
            ),
            payload=dict(fields),
        )
        item.children.append(leaf)
        self._items[leaf.item_id] = leaf

    def _operation_event(
        self,
        kind: str,
        operation_id: str,
        inquiry_id: str,
        session_id: str,
        ts: datetime | None,
        fields: dict,
    ) -> None:
        operation_kind = str(fields.get("kind") or fields.get("scope") or "operation")
        item = self._operation(operation_id, inquiry_id, session_id, ts, operation_kind)
        if item is None:
            return
        status = str(fields.get("status") or "")
        if kind == "operation_requested":
            item.status = "requested"
            summary = "requested"
        elif kind == "operation_started":
            item.status = "running"
            summary = "started"
        elif (
            kind == "operation_failed"
            or status == "failed"
            or (kind == "execution_end" and status == "failed")
        ):
            item.status = "failed"
            item.severity = "error"
            summary = "failed"
        elif status == "interrupted" or (
            kind == "execution_end" and status == "interrupted"
        ):
            item.status = "interrupted"
            item.severity = "warning"
            summary = "interrupted"
        elif kind == "operation_completed" or (
            kind == "execution_end" and status == "completed"
        ):
            item.status = "completed"
            summary = "completed"
            self._last_completed = operation_id
            self._last_completed_kind = operation_kind
            self._last_completed_ts = ts
            if self._active_operation == operation_id:
                self._active_operation = ""
        else:
            item.status = "running"
            summary = _first_line(fields.get("text") or "running")
        if kind in {
            "operation_completed",
            "operation_failed",
            "operation_requested",
            "operation_started",
        }:
            detail = self._operation_detail(fields)
            if fields.get("error"):
                detail = (f"Error: {_first_line(fields.get('error'))}", *detail)
            leaf = TimelineItem(
                item_id=f"leaf:{kind}:{operation_id}:{ts}",
                kind=operation_kind,
                title=summary,
                summary="",
                ts=ts,
                severity=item.severity,
                detail=detail,
                payload=dict(fields),
            )
        else:
            text = _first_line(fields.get("text") or summary)
            leaf = TimelineItem(
                item_id=f"leaf:{kind}:{operation_id}:{ts}",
                kind=operation_kind,
                title=text,
                ts=ts,
                severity=item.severity,
                payload=dict(fields),
            )
        item.children.append(leaf)
        self._items[leaf.item_id] = leaf
        item.end_ts = ts or item.end_ts
        if item.status in {"running", "requested"}:
            self._active_operation = operation_id
        item.summary = self._operation_summary(item)

    def _progress_event(
        self,
        kind: str,
        operation_id: str,
        inquiry_id: str,
        session_id: str,
        ts: datetime | None,
        fields: dict,
    ) -> None:
        operation_kind = "training" if kind == "training_progress" else "measurement"
        item = self._operation(operation_id, inquiry_id, session_id, ts, operation_kind)
        if item is None:
            return
        item.status = "running"
        self._active_operation = operation_id
        previous_ts, previous_steps = self._progress.get(operation_id, (None, None))
        steps = fields.get("steps")
        target = fields.get("target")
        interval = ""
        if ts is not None and previous_ts is not None:
            interval = f"+{console.format_duration((ts - previous_ts).total_seconds())}"
        step_delta = ""
        if (
            isinstance(steps, int)
            and isinstance(previous_steps, int)
            and ts is not None
            and previous_ts is not None
        ):
            elapsed = max((ts - previous_ts).total_seconds(), 1.0)
            step_delta = f"+{_number(steps - previous_steps)}"
            step_delta += f" ({max(0.0, (steps - previous_steps) / elapsed):,.0f}/s)"
        self._progress[operation_id] = (ts, steps if isinstance(steps, int) else None)
        if kind == "training_progress":
            percent = (
                f"{100 * steps / target:.0f}%"
                if isinstance(steps, int) and isinstance(target, int) and target
                else ""
            )
            parts = [
                f"{_number(steps)} / {_number(target)}",
                percent,
                interval,
                step_delta,
                f"reward {fields.get('ep_rew_mean')}"
                if fields.get("ep_rew_mean") is not None
                else "",
                f"success {round(float(fields['training_success']) * 100)}%"
                if isinstance(fields.get("training_success"), (int, float))
                and not isinstance(fields.get("training_success"), bool)
                else "",
            ]
            summary = "  ".join(part for part in parts if part)
            item.summary = summary
            title = summary
        else:
            episodes = fields.get("episodes")
            total = fields.get("episodes_total")
            percent = (
                f"{100 * episodes / total:.0f}%"
                if isinstance(episodes, int) and isinstance(total, int) and total
                else ""
            )
            parts = [
                str(fields.get("instrument") or ""),
                f"panel {fields.get('panel_index')}/{fields.get('panel_total')}"
                if fields.get("panel_total")
                else "",
                f"{_number(episodes)} / {_number(total)}",
                percent,
                interval,
            ]
            summary = "  ".join(part for part in parts if part)
            item.summary = summary
            title = summary
        leaf = TimelineItem(
            item_id=f"leaf:{kind}:{operation_id}:{ts}",
            kind=kind,
            title=title,
            ts=ts,
            payload=dict(fields),
        )
        item.children.append(leaf)
        self._items[leaf.item_id] = leaf
        item.end_ts = ts or item.end_ts

    def _pi_event(
        self,
        ts: datetime | None,
        session_id: str,
        inquiry_id: str,
        operation_id: str,
        fields: dict,
    ) -> None:
        text = str(fields.get("text") or "")
        if not text:
            return
        turn = fields.get("turn")
        final = bool(fields.get("final", True))
        key = f"pi:{session_id}:{turn}" if turn is not None else f"pi:{session_id}:{ts}"
        existing = self._pi_items.get(key)
        if turn is not None and not final:
            text = self._pi_text.get(key, "") + text
        self._pi_text[key] = text
        detail = tuple(line for line in text.splitlines() if line.strip())
        if existing is not None:
            existing.summary = _first_line(text)
            existing.detail = detail
            existing.payload = dict(fields)
            return
        title = f"PI ({session_id}):" if session_id else "PI:"
        leaf = TimelineItem(
            item_id=f"leaf:pi:{session_id}:{ts}:{len(self._seen)}",
            kind="pi",
            title=title,
            summary=_first_line(text),
            ts=ts,
            detail=detail,
            payload=dict(fields),
        )
        self._pi_items[key] = leaf
        self._attach(leaf, operation_id, inquiry_id, session_id)
        if ts is not None:
            self._touch_groups(ts, operation_id, inquiry_id, session_id)

    def _tool_event(
        self,
        ts: datetime | None,
        session_id: str,
        inquiry_id: str,
        operation_id: str,
        fields: dict,
    ) -> None:
        text = str(fields.get("text") or "")
        name = str(fields.get("name") or fields.get("tool") or "")
        if not name and text:
            stripped = text.lstrip("> ").strip()
            name = stripped.split(":", 1)[0].split(" ", 1)[0] if stripped else "tool"
        name = name or "tool"
        detail = (
            fields.get("detail")
            or fields.get("arguments")
            or fields.get("result")
            or (text if text and text.strip() != name else "")
        )
        status = str(fields.get("status") or "ok")
        duration = fields.get("duration_seconds")
        duration_text = (
            console.format_duration(float(duration))
            if isinstance(duration, (int, float)) and not isinstance(duration, bool)
            else ""
        )
        summary = " | ".join(part for part in (status, duration_text) if part)
        leaf = TimelineItem(
            item_id=f"leaf:tool:{name}:{ts}:{len(self._seen)}",
            kind="tool",
            title=f"> {name}",
            summary=summary,
            ts=ts,
            detail=(_json_text(detail),) if detail not in (None, "") else (),
            payload=dict(fields),
        )
        self._attach(leaf, operation_id, inquiry_id, session_id)
        if ts is not None:
            self._touch_groups(ts, operation_id, inquiry_id, session_id)

    def _simple_event(
        self,
        kind: str,
        ts: datetime | None,
        session_id: str,
        inquiry_id: str,
        operation_id: str,
        fields: dict,
    ) -> None:
        title = {
            "role_assigned": f"role {fields.get('role') or ''}".strip(),
            "candidate_created": f"candidate {fields.get('candidate') or fields.get('id') or ''}".strip(),
            "checkpoint_saved": "checkpoint saved",
            "activity": f"activity {fields.get('label') or ''}".strip(),
        }.get(kind, kind.replace("_", " "))
        summary = _first_line(
            fields.get("candidate")
            or fields.get("label")
            or fields.get("text")
            or fields.get("summary")
            or ""
        )
        leaf = TimelineItem(
            item_id=f"leaf:{kind}:{ts}:{len(self._seen)}",
            kind=kind if kind in KIND_GLYPHS else "log",
            title=title,
            summary=summary,
            ts=ts,
            detail=tuple(
                line
                for line in (
                    f"Candidate: {fields.get('candidate')}"
                    if fields.get("candidate")
                    else "",
                    f"Role: {fields.get('role')}" if fields.get("role") else "",
                    f"Evidence: {_first_line(fields.get('evidence'))}"
                    if fields.get("evidence")
                    else "",
                )
                if line
            ),
            payload=dict(fields),
        )
        self._attach(leaf, operation_id, inquiry_id, session_id)
        if ts is not None:
            self._touch_groups(ts, operation_id, inquiry_id, session_id)

    def _usage_event(self, ts: datetime | None, session_id: str, fields: dict) -> None:
        rows = fields.get("rows")
        leaf = TimelineItem(
            item_id=f"leaf:usage:{ts}:{len(self._seen)}",
            kind="usage",
            title="usage recorded",
            summary=f"{len(rows)} accounting rows" if isinstance(rows, list) else "",
            ts=ts,
            detail=(_json_text(rows),) if rows else (),
            payload=dict(fields),
        )
        self._attach(leaf, "", "", session_id)
        if ts is not None:
            self._touch_groups(ts, "", "", session_id)

    def _warning_event(
        self,
        kind: str,
        ts: datetime | None,
        session_id: str,
        inquiry_id: str,
        operation_id: str,
        fields: dict,
    ) -> None:
        code = fields.get("code") or fields.get("id") or ""
        message = fields.get("message") or fields.get("text") or ""
        leaf = TimelineItem(
            item_id=f"leaf:{kind}:{ts}:{len(self._seen)}",
            kind="error" if kind == "error" else "warning",
            title=f"{code} {kind}".strip(),
            summary=_first_line(message),
            ts=ts,
            severity="error" if kind == "error" else "warning",
            detail=(_json_text(fields),),
            default_expanded=True,
            payload=dict(fields),
        )
        self._attach(leaf, operation_id, inquiry_id, session_id)
        if ts is not None:
            self._touch_groups(ts, operation_id, inquiry_id, session_id)

    def _root_event(self, kind: str, ts: datetime | None, fields: dict) -> None:
        if kind == "run_state":
            self._run_state = str(fields.get("state") or "")
        title = {
            "campaign_started": "campaign started",
            "campaign_concluded": "campaign concluded",
            "run_state": f"run state {fields.get('state') or ''}".strip(),
        }.get(kind, kind.replace("_", " "))
        leaf = TimelineItem(
            item_id=f"leaf:{kind}:{ts}:{len(self._seen)}",
            kind="campaign",
            title=title,
            summary=_first_line(fields.get("summary") or fields.get("state") or ""),
            ts=ts,
            detail=tuple(f"{key}: {_short(value)}" for key, value in fields.items()),
            payload=dict(fields),
        )
        self._campaign_group().children.append(leaf)
        self._items[leaf.item_id] = leaf

    def _console_event(
        self,
        ts: datetime | None,
        session_id: str,
        inquiry_id: str,
        operation_id: str,
        fields: dict,
    ) -> None:
        text = str(fields.get("text") or "")
        title = str(fields.get("title") or "")
        scope = str(fields.get("scope") or "").casefold()
        if scope and text.startswith("[") and "]" in text:
            marker = text[1 : text.index("]")].casefold()
            if marker == scope:
                text = text[text.index("]") + 1 :].strip()
        kind = {
            "tool": "tool",
            "error": "error",
            "warning": "warning",
            "pi": "pi",
            "result": "result",
            "success": "result",
            "operation": "operation",
            "measurement": "measurement",
            "training": "training",
            "assessment": "result",
        }.get(scope, "log")
        severity = (
            "error" if kind == "error" else "warning" if kind == "warning" else "info"
        )
        body = fields.get("body")
        detail: list[str] = []
        if isinstance(body, list):
            detail.extend(str(line) for line in body)
        elif isinstance(body, str):
            detail.extend(body.splitlines())
        if not title and text.startswith("==="):
            first, _, rest = text.partition("\n")
            title = first.strip("= ").strip()
            detail.extend(rest.splitlines())
        elif not title:
            title = _first_line(text)
            detail.extend(text.splitlines()[1:])
            if len(text) > len(title):
                detail.insert(0, text)
        leaf = TimelineItem(
            item_id=f"leaf:console:{ts}:{len(self._seen)}",
            kind=kind,
            title=title or "log",
            summary="",
            ts=ts,
            severity=severity,
            detail=tuple(line for line in detail if line.strip()),
            payload=dict(fields),
        )
        self._attach(leaf, operation_id, inquiry_id, session_id)
        if ts is not None:
            self._touch_groups(ts, operation_id, inquiry_id, session_id)

    # ------------------------------------------------------------------
    # Attachment and summaries
    # ------------------------------------------------------------------

    def _attach(
        self,
        leaf: TimelineItem,
        operation_id: str,
        inquiry_id: str,
        session_id: str,
    ) -> None:
        self._items[leaf.item_id] = leaf
        parent = self._operations.get(operation_id) if operation_id else None
        if parent is None and inquiry_id:
            parent = self._inquiries.get(inquiry_id)
        if parent is None and session_id:
            parent = self._sessions.get(session_id)
        if parent is None and self._active_operation:
            parent = self._operations.get(self._active_operation)
        if parent is not None:
            parent.children.append(leaf)
        elif leaf.kind in {
            "role",
            "usage",
            "campaign",
            "log",
            "pi",
            "tool",
            "warning",
            "error",
        }:
            self._campaign_group().children.append(leaf)
        else:
            self._roots.append(leaf)

    def _touch_groups(
        self,
        ts: datetime,
        operation_id: str,
        inquiry_id: str,
        session_id: str,
    ) -> None:
        for item in (
            self._operations.get(operation_id) if operation_id else None,
            self._inquiries.get(inquiry_id) if inquiry_id else None,
            self._sessions.get(session_id) if session_id else None,
        ):
            if item is not None:
                item.end_ts = ts if item.end_ts is None else max(item.end_ts, ts)

    def _operation_summary(self, item: TimelineItem) -> str:
        parts = [item.status] if item.status else []
        if item.kind == "training":
            latest = next(
                (
                    child
                    for child in reversed(item.children)
                    if child.kind == "training_progress"
                ),
                None,
            )
            if latest is not None:
                parts.append(latest.summary)
            else:
                completed = next(
                    (
                        child
                        for child in reversed(item.children)
                        if child.kind == "training"
                    ),
                    None,
                )
                if completed is not None:
                    result = (
                        completed.payload.get("result")
                        if isinstance(completed.payload.get("result"), dict)
                        else {}
                    )
                    steps = result.get("completed_steps", result.get("requested_steps"))
                    dynamics = result.get("learning_dynamics")
                    if isinstance(steps, int):
                        parts.append(f"{_number(steps)} steps")
                    if isinstance(dynamics, list) and dynamics:
                        last = dynamics[-1] if isinstance(dynamics[-1], dict) else {}
                        if last.get("ep_rew_mean") is not None:
                            parts.append(f"reward {last.get('ep_rew_mean')}")
                        if last.get("training_success") is not None:
                            parts.append(
                                f"success {round(float(last['training_success']) * 100)}%"
                            )
        elif item.kind in {"measurement", "measurement_progress"}:
            latest = next(
                (
                    child
                    for child in reversed(item.children)
                    if child.kind == "eval_progress"
                ),
                None,
            )
            if latest is not None:
                parts.append(latest.summary)
            else:
                completed = next(
                    (
                        child
                        for child in reversed(item.children)
                        if child.kind == "measurement"
                    ),
                    None,
                )
                if completed is not None:
                    result = (
                        completed.payload.get("result")
                        if isinstance(completed.payload.get("result"), dict)
                        else {}
                    )
                    panels = result.get("measurements")
                    if isinstance(panels, list) and panels:
                        best = max(
                            (
                                panel
                                for panel in panels
                                if isinstance(panel, dict)
                                and isinstance(panel.get("metrics"), dict)
                            ),
                            key=lambda panel: float(
                                panel["metrics"].get("success_percent") or 0
                            ),
                            default=None,
                        )
                        if best is not None:
                            metrics = best["metrics"]
                            parts.append(_percent(metrics.get("success_percent")))
                            if metrics.get("episodes") is not None:
                                parts.append(f"{metrics.get('episodes')} episodes")
        return " | ".join(part for part in parts if part)

    def _operation_detail(self, fields: dict) -> tuple[str, ...]:
        request = (
            fields.get("request") if isinstance(fields.get("request"), dict) else {}
        )
        result = fields.get("result") if isinstance(fields.get("result"), dict) else {}
        lines: list[str] = []
        for key in (
            "description",
            "rationale",
            "seed",
            "parent",
            "steps",
            "initialization",
        ):
            if request.get(key) not in (None, ""):
                lines.append(f"{key.title()}: {_short(request[key])}")
        for key in (
            "status",
            "completed_steps",
            "requested_steps",
            "instrument",
            "summary",
        ):
            if result.get(key) not in (None, ""):
                lines.append(f"{key.replace('_', ' ').title()}: {_short(result[key])}")
        candidates = result.get("candidates")
        if isinstance(candidates, list) and candidates:
            lines.append("Candidates: " + ", ".join(str(item) for item in candidates))
        dynamics = result.get("learning_dynamics")
        if isinstance(dynamics, list):
            for packet in dynamics:
                if not isinstance(packet, dict):
                    continue
                lines.append(
                    "Learning: "
                    + " | ".join(
                        part
                        for part in (
                            str(packet.get("candidate") or ""),
                            f"steps {_number(packet.get('training_steps'))}"
                            if packet.get("training_steps") is not None
                            else "",
                            f"reward {packet.get('ep_rew_mean')}"
                            if packet.get("ep_rew_mean") is not None
                            else "",
                            f"success {round(float(packet['training_success']) * 100)}%"
                            if isinstance(packet.get("training_success"), (int, float))
                            and not isinstance(packet.get("training_success"), bool)
                            else "",
                        )
                        if part
                    )
                )
        measurements = result.get("measurements")
        if isinstance(measurements, list):
            for panel in measurements:
                if not isinstance(panel, dict):
                    continue
                metrics = (
                    panel.get("metrics")
                    if isinstance(panel.get("metrics"), dict)
                    else {}
                )
                lines.append(
                    "Panel: "
                    + " | ".join(
                        part
                        for part in (
                            str(
                                panel.get("candidate")
                                or panel.get("candidate_id")
                                or ""
                            ),
                            str(panel.get("instrument") or ""),
                            _percent(metrics.get("success_percent")),
                            f"{metrics.get('episodes')} episodes"
                            if metrics.get("episodes") is not None
                            else "",
                        )
                        if part
                    )
                )
        if not lines:
            lines.append(_short(_json_text(fields), 400))
        return tuple(lines)

    # ------------------------------------------------------------------
    # View
    # ------------------------------------------------------------------

    @property
    def now_text(self) -> str:
        if self._active_operation:
            item = self._operations.get(self._active_operation)
            if item is not None and item.status in {"running", "requested"}:
                chain = []
                if self._current_inquiry:
                    chain.append(self._current_inquiry)
                if self._current_session:
                    chain.append(self._current_session)
                chain.append(item.title)
                detail = f" | {item.summary}" if item.summary else ""
                return "Now: " + " / ".join(chain) + detail
        if self._last_completed:
            stamp = _clock(self._last_completed_ts)
            state = self._run_state or "idle"
            return (
                f"Now: {state} | last completed {self._last_completed} "
                f"{self._last_completed_kind} | {stamp}"
            )
        if self._run_state:
            return f"Now: {self._run_state}"
        return "Now: waiting for the first operation"

    def active_ids(self) -> set[str]:
        ids = set()
        if self._current_session:
            ids.add(f"session:{self._current_session}")
        if self._current_inquiry:
            ids.add(f"inquiry:{self._current_inquiry}")
        if self._active_operation:
            ids.add(f"operation:{self._active_operation}")
        return ids

    @staticmethod
    def _category_match(kind: str, categories: set[str]) -> bool:
        if not categories:
            return True
        return any(
            kind in FILTER_CATEGORIES.get(category, set()) for category in categories
        )

    @staticmethod
    def _clone(item: TimelineItem, children: list[TimelineItem]) -> TimelineItem:
        return TimelineItem(
            item_id=item.item_id,
            kind=item.kind,
            title=item.title,
            summary=item.summary,
            ts=item.ts,
            end_ts=item.end_ts,
            severity=item.severity,
            detail=item.detail,
            children=children,
            default_expanded=item.default_expanded,
            is_group=item.is_group,
            event_id=item.event_id,
            payload=item.payload,
            status=item.status,
            role=item.role,
        )

    def view(
        self,
        *,
        query: str = "",
        categories: set[str] | None = None,
    ) -> tuple[list[TimelineItem], int]:
        query = query.strip().casefold()
        categories = categories or set()
        matches = 0

        def include(item: TimelineItem) -> tuple[bool, TimelineItem | None]:
            nonlocal matches
            text_match = not query or query in item.searchable()
            if not item.is_group:
                keep = text_match and self._category_match(item.kind, categories)
                if keep:
                    matches += 1
                return keep, item if keep else None
            child_items: list[TimelineItem] = []
            for child in item.children:
                keep, filtered = include(child)
                if keep and filtered is not None:
                    child_items.append(filtered)
            group_category_match = self._category_match(item.kind, categories)
            if (not query and group_category_match) or (
                query and text_match and not child_items
            ):
                child_items = [
                    self._clone(child, child.children) for child in item.children
                ]
            keep = bool(child_items) or (
                not query and group_category_match and not item.children
            )
            if not keep:
                return False, None
            return True, self._clone(item, child_items)

        roots: list[TimelineItem] = []
        for root in self._roots:
            keep, filtered = include(root)
            if keep and filtered is not None:
                roots.append(filtered)
        return roots, matches
