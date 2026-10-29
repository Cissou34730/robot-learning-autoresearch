"""Structured timeline reducer for the operator log.

The reducer is deliberately terminal-free: events in, a small tree of
display items out. The Textual widget only renders this tree and keeps the
user's expansion and selection state.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from runner import reporting as console
from runner.copilot.reporting import tool_detail, tool_result_lines
from runner.event_contract import (
    LAUNCH_KINDS,
    LAUNCHER_STOP_CODES,
    OFFICIAL_OPERATION,
    PREPARATION_SESSION,
    missing_identity,
)
from tui.observations import Observation
from tui.projector import training_eta_seconds

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
    "coding": "[>]",
    "file": "[~]",
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
    "training": {"training", "training_progress", "training_checkpoints"},
    "measurements": {
        "measurement",
        "eval_progress",
        "measurement_panel_started",
        "measurement_panel_completed",
    },
    "tools": {
        "tool",
        "tool_call",
        "tool_call_started",
        "tool_call_completed",
        "tool_call_failed",
        "tool_denied",
        "coding",
        "file_changed",
    },
    "pi": {"pi_message", "pi_context"},
    "roles": {"role", "role_assigned", "candidate_created", "checkpoint_saved"},
    "usage": {"usage", "usage_update", "campaign_usage", "session_usage"},
    "warnings": {
        "warning",
        "error",
        "operation_failed",
        "publication_retry",
    },
    "operations": {
        "operation",
        "operation_requested",
        "operation_started",
        "operation_completed",
        "operation_failed",
        "operation_submitted",
        "campaign_started",
        "campaign_concluded",
        "campaign_goal_review",
        "run_state",
        "scientific_model_validated",
        "notice",
    },
}


def _now() -> datetime:
    return datetime.now(tz=UTC)


_VERSIONS = itertools.count()
PROGRESS_ROW_SECONDS = {"training_progress": 30.0, "eval_progress": 15.0}


def _lower_ts(item: TimelineItem, ts: datetime | None) -> None:
    """A group starts at the earliest event it has seen."""
    if ts is not None and (item.ts is None or ts < item.ts):
        item.ts = ts


def _clock(stamp: datetime | None) -> str:
    if stamp is None:
        return ""
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


def _full_text(text: object) -> str:
    return str(text or "").strip()


def _short(value: object, limit: int = 160) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def _json_text(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except (TypeError, ValueError):
        return str(value)


def _tool_context(fields: dict, root: Path | None = None) -> str:
    text = str(
        fields.get("detail")
        or tool_detail(str(fields.get("name") or "tool"), fields.get("arguments"))
    )
    if root is not None:
        for prefix in {str(root), root.as_posix()}:
            text = text.replace(prefix + "\\", "").replace(prefix + "/", "")
    return " ".join(text.split())


def _tool_summary(
    fields: dict, status: str, seconds: float | None = None, *, root: Path | None = None
) -> str:
    state = "running" if status == "started" else status
    return " | ".join(
        part
        for part in (
            state if state not in {"ok", "completed", ""} else "",
            _tool_context(fields, root),
            console.format_duration(seconds)
            if seconds is not None and seconds >= 1
            else "",
        )
        if part
    )


def _tool_details(fields: dict) -> tuple[str, ...]:
    details = [
        text.strip()
        for text, _ in tool_result_lines(
            str(fields.get("name") or "tool"), fields.get("result")
        )
    ]
    error = fields.get("error") or fields.get("reason")
    if error:
        details.append(f"Error: {error}")
    return tuple(details)


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


def _as_percent(value: object) -> float | None:
    """A percentage as a number, or ``None`` when the event did not carry it."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


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
    # Number of events hidden in a closed group that is shown folded.
    lazy: int = 0

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

    def __init__(self, campaign_root: Path | None = None) -> None:
        self._campaign_root = campaign_root
        self._items: dict[str, TimelineItem] = {}
        self._roots: list[TimelineItem] = []
        self._seen: set[str] = set()
        self._sessions: dict[str, TimelineItem] = {}
        self._inquiries: dict[tuple[str, str], TimelineItem] = {}
        self._inquiry_question: dict[str, str] = {}
        self._operations: dict[str, TimelineItem] = {}
        self._operation_session: dict[str, str] = {}
        self._progress: dict[str, tuple[datetime | None, int | None]] = {}
        self._training_samples: dict[str, dict] = {}
        self._pi_items: dict[str, TimelineItem] = {}
        self._pi_text: dict[str, str] = {}
        self._tools: dict[str, TimelineItem] = {}
        # What is happening now. This is presentation state, derived from
        # lifecycle events; it never decides where a row is attached.
        self._current_session = ""
        self._current_inquiry: tuple[str, str] | None = None
        self._active_operation = ""
        self._run_state = ""
        self._last_campaign_aiu: float | None = None
        self._last_completed = ""
        self._last_completed_kind = ""
        self._last_completed_ts: datetime | None = None
        self._attempt = ""
        self._actor = ""
        self.version = next(_VERSIONS)
        self._running_tools: set[str] = set()
        self._leaf_counts: dict[str, tuple[tuple, int]] = {}
        self._progress_rows: dict[str, TimelineItem] = {}
        self._coding_open = False

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------

    def clear(self) -> None:
        self.__init__(self._campaign_root)

    def _diagnostic(self, event: Observation, missing: tuple[str, ...]) -> None:
        """An event that lacks a required identity is reported, never guessed."""
        leaf = TimelineItem(
            item_id=f"diagnostic:{event.event_id or len(self._seen)}",
            kind="warning",
            title="event without a required identity",
            summary=f"{event.kind} lacks {', '.join(missing)}",
            ts=event.ts,
            severity="warning",
            detail=(
                f"event id: {event.event_id or '(none)'}",
                f"kind: {event.kind}",
                f"missing: {', '.join(missing)}",
            ),
            payload=dict(event.fields or {}),
        )
        self._items[leaf.item_id] = leaf
        self._campaign_group().children.append(leaf)

    def ingest(self, event: Observation) -> None:
        event_id = event.event_id or self._fallback_id(event)
        if event_id in self._seen:
            return
        self._seen.add(event_id)
        kind = event.kind
        fields = event.fields or {}
        ts = event.ts
        if kind == "liveness":
            return
        # Any other new event may change the view; an idle tick must not.
        self.version = next(_VERSIONS)
        session_id = event.session_id
        inquiry_id = event.inquiry_id
        operation_id = event.operation_id
        missing = missing_identity(
            kind,
            session_id=session_id,
            operation_id=operation_id,
            inquiry_id=inquiry_id,
        )
        if missing:
            self._diagnostic(event, missing)
            return
        # Who spoke and in which invocation, for the handler about to run.
        self._attempt = event.attempt
        self._actor = event.actor
        self._campaign_group_follows(kind, fields, session_id)
        self._resume_interrupted(kind, operation_id, fields)
        if kind == "session_start":
            self._attempt_event(ts, session_id, fields)
            return
        if kind in {"inquiry_opened", "inquiry_closed", "inquiry_reframed"}:
            self._inquiry_event(kind, inquiry_id, session_id, ts, fields)
            return
        if kind in {
            "operation_requested",
            "operation_started",
            "operation_progress",
            "operation_completed",
            "operation_failed",
        }:
            self._operation_event(
                kind, operation_id, inquiry_id, session_id, ts, fields
            )
            return
        if kind in {"training_progress", "eval_progress"}:
            self._progress_event(kind, operation_id, inquiry_id, session_id, ts, fields)
            return
        if kind in {"session_started", "session_ended"}:
            self._session_event(kind, session_id, ts, fields)
            return
        if kind in {"pi_message"}:
            self._pi_event(ts, session_id, inquiry_id, operation_id, fields)
            return
        if kind in {
            "tool_call_started",
            "tool_call_completed",
            "tool_call_failed",
            "tool_denied",
        }:
            self._tool_lifecycle(kind, ts, session_id, inquiry_id, operation_id, fields)
            return
        if kind == "coding":
            self._coding_event(ts, session_id, inquiry_id, operation_id, fields)
            return
        if kind == "file_changed":
            self._file_event(ts, session_id, inquiry_id, operation_id, fields)
            return
        if kind == "pi_context":
            self._pi_context_event(ts, session_id, inquiry_id, operation_id, fields)
            return
        if kind in {"tool", "tool_call"}:
            self._tool_event(ts, session_id, inquiry_id, operation_id, fields)
            return
        if kind in {
            "measurement_panel_started",
            "measurement_panel_completed",
        }:
            self._panel_event(kind, ts, session_id, inquiry_id, operation_id, fields)
            return
        if kind == "training_checkpoints":
            self._training_checkpoints_event(
                ts, session_id, inquiry_id, operation_id, fields
            )
            return
        if kind in {"role_assigned", "candidate_created", "checkpoint_saved"}:
            self._simple_event(kind, ts, session_id, inquiry_id, operation_id, fields)
            return
        if kind in {
            "usage",
            "usage_update",
            "campaign_usage",
            "session_usage",
        }:
            self._usage_event(kind, ts, session_id, operation_id, fields)
            return
        if kind in {"warning", "error", "publication_retry"}:
            self._warning_event(kind, ts, session_id, inquiry_id, operation_id, fields)
            return
        if kind in {
            "campaign_started",
            "campaign_concluded",
            "campaign_goal_review",
            "run_state",
            "publication_recovered",
            "scientific_model_validated",
        }:
            self._root_event(kind, ts, fields, session_id, operation_id)
            return
        if kind == "operation_submitted":
            self._operation_submitted_event(
                ts, session_id, inquiry_id, operation_id, fields
            )
            return
        if kind == "notice":
            self._notice_event(ts, session_id, inquiry_id, operation_id, fields)
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

    def _resume_interrupted(self, kind: str, operation_id: str, fields: dict) -> None:
        """A run state "executing" for an interrupted operation means it runs again."""
        if kind != "run_state" or fields.get("state") != "executing":
            return
        item = self._operations.get(operation_id)
        if item is not None and item.status == "interrupted":
            item.status = "running"
            item.severity = "info"
            self._active_operation = operation_id
            item.summary = self._operation_summary(item)

    def _campaign_group_follows(self, kind: str, fields: dict, session_id: str) -> None:
        """Keep the Campaign group open while a launcher failure stands in it.

        A failure owned by a session shows in that session. One that belongs to
        no session (between sessions, or recorded without an owner) would
        otherwise hide in the folded Campaign group.
        """
        if kind in LAUNCH_KINDS:
            group = self._items.get("campaign:root")
            if group is not None:
                group.default_expanded = False
        elif (
            kind == "error"
            and not session_id
            and fields.get("code") in LAUNCHER_STOP_CODES
        ):
            self._campaign_group().default_expanded = True

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

    def _session_title(self, session_id: str, fields: dict) -> str:
        if session_id == PREPARATION_SESSION:
            return "Campaign preparation"
        kind = str(fields.get("kind") or "").replace("_", " ")
        return f"{session_id} {kind}".strip()

    def _session(
        self, session_id: str, ts: datetime | None, fields: dict
    ) -> TimelineItem:
        """The group of one durable session, created by its first reference."""
        item = self._sessions.get(session_id)
        if item is None:
            item = self._add_root(
                TimelineItem(
                    item_id=f"session:{session_id}",
                    kind="session",
                    title=self._session_title(session_id, fields),
                    ts=ts,
                    is_group=True,
                    default_expanded=False,
                    payload={"session_id": session_id, **fields},
                )
            )
            self._sessions[session_id] = item
        elif fields.get("kind"):
            item.title = self._session_title(session_id, fields)
            item.payload = {**item.payload, **fields}
        if ts is not None:
            item.end_ts = ts if item.end_ts is None else max(item.end_ts, ts)
        _lower_ts(item, ts)
        return item

    def _inquiry(
        self,
        inquiry_id: str,
        session_id: str,
        ts: datetime | None,
        fields: dict,
    ) -> TimelineItem:
        """An inquiry as seen from one session.

        An inquiry spans sessions, so each session shows its own group for it;
        the operations a session ran for the inquiry sit in that group.
        """
        question = _first_line(fields.get("question") or "", 90)
        if question:
            self._inquiry_question[inquiry_id] = question
        key = (session_id, inquiry_id)
        item = self._inquiries.get(key)
        if item is None:
            item = TimelineItem(
                item_id=f"inquiry:{session_id}:{inquiry_id}",
                kind="inquiry",
                title=inquiry_id,
                ts=ts,
                is_group=True,
                default_expanded=True,
                payload=dict(fields),
            )
            self._items[item.item_id] = item
            self._session(session_id, ts, {}).children.append(item)
            self._inquiries[key] = item
        item.title = (
            f"{inquiry_id} {self._inquiry_question.get(inquiry_id, '')}".strip()
        )
        if ts is not None:
            item.end_ts = ts if item.end_ts is None else max(item.end_ts, ts)
        _lower_ts(item, ts)
        return item

    def _operation(
        self,
        operation_id: str,
        inquiry_id: str,
        session_id: str,
        ts: datetime | None,
        kind: str,
    ) -> TimelineItem:
        """The group of one operation: its session's, or its own top-level group
        when it has no session (the official assessment, shown where it happened,
        after the last session)."""
        item = self._operations.get(operation_id)
        if item is None:
            official = operation_id == OFFICIAL_OPERATION
            if official:
                parent = None
            elif not session_id:
                parent = self._campaign_group()
            elif inquiry_id:
                parent = self._inquiry(inquiry_id, session_id, ts, {})
            else:
                parent = self._session(session_id, ts, {})
            item = TimelineItem(
                item_id=f"operation:{operation_id}",
                kind=kind or "operation",
                title="Official assessment"
                if official
                else f"{operation_id} {kind or 'operation'}",
                ts=ts,
                is_group=True,
                default_expanded=official,
                status="requested",
            )
            self._items[item.item_id] = item
            if parent is None:
                self._roots.append(item)
            else:
                parent.children.append(item)
            self._operations[operation_id] = item
            self._operation_session[operation_id] = session_id
        elif session_id != self._operation_session.get(operation_id, session_id):
            self._report_conflict(operation_id, session_id, ts)
        if ts is not None:
            item.end_ts = ts if item.end_ts is None else max(item.end_ts, ts)
        _lower_ts(item, ts)
        return item

    def _report_conflict(
        self, operation_id: str, session_id: str, ts: datetime | None
    ) -> None:
        """An operation named two sessions: keep the first owner, say so once."""
        key = f"conflict:{operation_id}"
        if key in self._items:
            return
        owner = self._operation_session.get(operation_id) or "the campaign"
        leaf = TimelineItem(
            item_id=key,
            kind="warning",
            title="operation named two owners",
            summary=f"{operation_id}: first {owner}, now {session_id or 'none'}",
            ts=ts,
            severity="warning",
        )
        self._items[key] = leaf
        self._campaign_group().children.append(leaf)

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
        if kind == "inquiry_closed":
            item.status = "closed"
            item.end_ts = ts or item.end_ts
            if self._current_inquiry == (session_id, inquiry_id):
                self._current_inquiry = None
        elif kind == "inquiry_reframed":
            item.status = "reframed"
            self._current_inquiry = (session_id, inquiry_id)
        else:
            self._current_inquiry = (session_id, inquiry_id)
        leaf = TimelineItem(
            item_id=f"leaf:{kind}:{session_id}:{inquiry_id}:{ts}",
            kind="inquiry",
            title=(
                "inquiry opened"
                if kind == "inquiry_opened"
                else "inquiry reframed"
                if kind == "inquiry_reframed"
                else "inquiry closed"
            ),
            summary="",
            ts=ts,
            detail=tuple(
                line
                for line in (
                    f"Question: {_full_text(fields.get('question'))}"
                    if fields.get("question")
                    else "",
                    f"Closure: {_full_text(fields.get('closure_condition'))}"
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
        status = str(fields.get("status") or "")
        if operation_id == OFFICIAL_OPERATION:
            if kind == "operation_started" and fields.get("model"):
                item.title = f"Official assessment | {fields['model']}"
            if kind == "operation_completed":
                self._official_result(item, ts, fields)
                return
        # An interrupted operation can run again: its resumed execution reports
        # a start, a run state or progress.
        finished = item.status in {"completed", "failed", "passed"}
        if kind == "operation_requested":
            item.status = item.status if finished else "requested"
            summary = "requested"
        elif kind == "operation_started":
            item.status = item.status if finished else "running"
            summary = "started"
        elif kind == "operation_failed" or status == "failed":
            item.status = "failed"
            item.severity = "error"
            summary = "failed"
        elif status == "interrupted":
            item.status = "interrupted"
            item.severity = "warning"
            summary = "interrupted"
        elif kind == "operation_completed":
            item.status = "completed"
            item.severity = "info"
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
                detail = (f"Error: {_full_text(fields.get('error'))}", *detail)
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

    def _official_result(
        self, item: TimelineItem, ts: datetime | None, fields: dict
    ) -> None:
        """The result of the official assessment, in words and figures."""
        passed = str(fields.get("status") or "") == "passed"
        success = _as_percent(fields.get("success_percent"))
        required = _as_percent(fields.get("required_success_percent"))
        episodes = fields.get("episodes")
        outcome = "goal reached" if passed else "goal not reached"
        figures = ""
        if success is not None:
            figures = f"{success:.1f}%"
            if isinstance(episodes, int):
                figures += f" over {episodes} episodes"
        margin = ""
        if success is not None and required is not None:
            gap = success - required
            margin = (
                f"{abs(gap):.1f} points {'above' if gap >= 0 else 'below'} "
                f"the {required:.1f}% required"
            )
        item.status = "passed" if passed else "failed"
        item.severity = "info" if passed else "error"
        item.payload = dict(fields)
        item.end_ts = ts or item.end_ts
        parts = (item.status, outcome, figures, margin)
        if success is None:
            parts = (item.status, str(fields.get("summary") or outcome))
        item.summary = " | ".join(part for part in parts if part)
        detail = tuple(
            line
            for line in (
                f"Model: {fields['model']}" if fields.get("model") else "",
                f"Success: {figures}" if figures else "",
                f"Required: {required:.1f}%" if required is not None else "",
                f"Margin: {margin}" if margin else "",
                f"Summary: {fields['summary']}" if fields.get("summary") else "",
            )
            if line
        )
        leaf = TimelineItem(
            item_id=f"leaf:operation_completed:official:{ts}",
            kind="result" if passed else "measurement",
            title=outcome,
            summary=" | ".join(part for part in (figures, margin) if part),
            ts=ts,
            severity=item.severity,
            detail=detail,
            payload=dict(fields),
            default_expanded=True,
        )
        item.children.append(leaf)
        self._items[leaf.item_id] = leaf
        self._last_completed = OFFICIAL_OPERATION
        self._last_completed_kind = "official assessment"
        self._last_completed_ts = ts
        if self._active_operation == OFFICIAL_OPERATION:
            self._active_operation = ""

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
        if item.status not in {"completed", "failed", "passed"}:
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
        if kind == "training_progress":
            sample = {**fields, "operation_id": operation_id}
            eta = training_eta_seconds(sample, self._training_samples.get(operation_id))
            self._training_samples[operation_id] = sample
            percent = (
                f"{100 * steps / target:.0f}%"
                if isinstance(steps, int) and isinstance(target, int) and target
                else ""
            )
            scenario_metric = str(fields.get("scenario_metric") or "")
            training_success = fields.get("training_success")
            if (
                not scenario_metric
                and isinstance(training_success, (int, float))
                and not isinstance(training_success, bool)
            ):
                scenario_metric = f"success {round(float(training_success) * 100)}%"
            parts = [
                f"{_number(steps)} / {_number(target)}",
                percent,
                interval,
                step_delta,
                f"Elapsed {console.format_duration(float(fields['elapsed_seconds']))}"
                if isinstance(fields.get("elapsed_seconds"), (int, float))
                else "Elapsed unavailable",
                f"ETA {console.format_duration(eta)}"
                if eta is not None
                else "ETA unavailable",
                f"reward {fields.get('ep_rew_mean')}"
                if fields.get("ep_rew_mean") is not None
                else "",
                scenario_metric,
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
        current_row = self._progress_rows.get(operation_id)
        if (
            current_row is not None
            and item.children
            and item.children[-1] is current_row
            and ts is not None
            and previous_ts is not None
            and (ts - previous_ts).total_seconds() < PROGRESS_ROW_SECONDS[kind]
        ):
            # Samples can arrive every second. While no other row has followed
            # it, the last progress row stands for its newest sample, values and
            # time together, so the list stays in time order.
            current_row.title = title
            current_row.payload = dict(fields)
            current_row.ts = ts
            item.end_ts = ts
            return
        self._progress[operation_id] = (ts, steps if isinstance(steps, int) else None)
        leaf = TimelineItem(
            item_id=f"leaf:{kind}:{operation_id}:{ts}",
            kind=kind,
            title=title,
            ts=ts,
            payload=dict(fields),
        )
        self._progress_rows[operation_id] = leaf
        item.children.append(leaf)
        self._items[leaf.item_id] = leaf
        item.end_ts = ts or item.end_ts

    def _attempt_event(
        self, ts: datetime | None, session_id: str, fields: dict
    ) -> None:
        """One PI invocation starting in a session (an attempt)."""
        item = self._session(session_id, ts, {})
        self._current_session = session_id
        stage = _first_line(fields.get("stage") or "")
        resumed = " | resumed" if fields.get("resumed") else ""
        leaf = TimelineItem(
            item_id=f"leaf:attempt:{session_id}:{self._attempt}:{ts}",
            kind="session",
            title="PI started",
            summary=f"{stage}{resumed}".strip(" |"),
            ts=ts,
            payload=dict(fields),
        )
        item.children.append(leaf)
        self._items[leaf.item_id] = leaf

    def _session_event(
        self, kind: str, session_id: str, ts: datetime | None, fields: dict
    ) -> None:
        sid = session_id
        item = self._session(sid, ts, fields)
        if kind == "session_started":
            item.status = "running"
            self._current_session = sid
            title = "started"
            summary = _first_line(fields.get("objective") or fields.get("kind") or "")
            detail = tuple(
                line
                for line in (
                    f"Objective: {_full_text(fields.get('objective'))}"
                    if fields.get("objective")
                    else "",
                )
                if line
            )
        else:
            item.status = "closed"
            if self._current_session == sid:
                self._current_session = ""
            title = "ended"
            summary = _first_line(fields.get("summary") or "")
            detail = tuple(
                line
                for line in (
                    f"Summary: {_full_text(fields.get('summary'))}"
                    if fields.get("summary")
                    else "",
                    f"Next question: {_full_text(fields.get('next_question'))}"
                    if fields.get("next_question")
                    else "",
                    f"Next: {_full_text(fields.get('next'))}"
                    if fields.get("next")
                    else "",
                )
                if line
            )
        leaf = TimelineItem(
            item_id=f"leaf:{kind}:{sid}:{ts}",
            kind="session",
            title=title,
            summary=summary,
            ts=ts,
            detail=detail,
            payload=dict(fields),
        )
        item.children.append(leaf)
        self._items[leaf.item_id] = leaf
        item.end_ts = ts or item.end_ts

    def _tool_lifecycle(
        self,
        kind: str,
        ts: datetime | None,
        session_id: str,
        inquiry_id: str,
        operation_id: str,
        fields: dict,
    ) -> None:
        name = str(fields.get("name") or fields.get("tool") or "tool")
        call_id = str(fields.get("tool_call_id") or "")
        key = (
            f"{self._attempt}:{call_id}"
            if call_id and self._attempt
            else (call_id or f"{name}:{ts}")
        )
        item = self._tools.get(key)
        status = str(fields.get("status") or "")
        if kind == "tool_call_started":
            item = TimelineItem(
                item_id=f"tool:{key}",
                kind="tool",
                title=name,
                summary=_tool_summary(fields, "started", root=self._campaign_root),
                ts=ts,
                status="started",
                default_expanded=True,
                detail=_tool_details(fields),
                payload=dict(fields),
            )
            self._tools[key] = item
            self._running_tools.add(key)
            self._attach(item, operation_id, inquiry_id, session_id)
        else:
            if item is None:
                item = TimelineItem(
                    item_id=f"tool:{key}",
                    kind="tool",
                    title=name,
                    ts=ts,
                    payload=dict(fields),
                    default_expanded=True,
                )
                self._tools[key] = item
                self._attach(item, operation_id, inquiry_id, session_id)
            if kind == "tool_denied":
                status = "denied"
            item.status = status or item.status
            if item.status != "started":
                self._running_tools.discard(key)
            item.end_ts = ts
            seconds = None
            if ts is not None and item.ts is not None:
                seconds = max(0.0, (ts - item.ts).total_seconds())
            item.payload = {**item.payload, **fields}
            item.summary = _tool_summary(
                item.payload, item.status, seconds, root=self._campaign_root
            )
            error = fields.get("error") or fields.get("reason")
            if error:
                item.severity = "error" if kind == "tool_call_failed" else "warning"
            item.detail = _tool_details(item.payload)
        if ts is not None:
            self._touch_groups(ts, operation_id, inquiry_id, session_id)

    def _coding_event(
        self,
        ts: datetime | None,
        session_id: str,
        inquiry_id: str,
        operation_id: str,
        fields: dict,
    ) -> None:
        phase = str(fields.get("phase") or "coding")
        status = str(fields.get("status") or "")
        if phase == "request" and status == "started":
            self._coding_open = True
        elif phase in {"result", "cancelled", "rejected"}:
            self._coding_open = False
        agent = str(fields.get("agent") or "")
        detail = fields.get("detail") if isinstance(fields.get("detail"), dict) else {}
        summary = " | ".join(
            part
            for part in (
                agent,
                status,
                _first_line(detail.get("intent") or detail.get("verdict") or ""),
            )
            if part
        )
        severity = str(fields.get("severity") or "")
        leaf = TimelineItem(
            item_id=f"leaf:coding:{phase}:{ts}:{len(self._seen)}",
            kind="coding",
            title=f"coding {phase}".strip(),
            summary=summary,
            ts=ts,
            severity="error"
            if severity == "error"
            else "warning"
            if severity == "warning"
            else "info",
            detail=(_json_text(detail),) if detail else (),
            payload=dict(fields),
        )
        self._attach(leaf, operation_id, inquiry_id, session_id)
        if ts is not None:
            self._touch_groups(ts, operation_id, inquiry_id, session_id)

    def _file_event(
        self,
        ts: datetime | None,
        session_id: str,
        inquiry_id: str,
        operation_id: str,
        fields: dict,
    ) -> None:
        path = str(fields.get("display_path") or fields.get("path") or "")
        operation = str(fields.get("operation") or "changed")
        marker = {"created": "+", "deleted": "-"}.get(operation, "~")
        suffix = (
            " | PI operation request updated" if fields.get("operation_request") else ""
        )
        leaf = TimelineItem(
            item_id=f"leaf:file:{path}:{ts}:{len(self._seen)}",
            kind="file",
            title=f"{marker} {path}",
            summary=operation + suffix,
            ts=ts,
            detail=(f"Path: {fields.get('path')}",) if fields.get("path") else (),
            payload=dict(fields),
        )
        self._attach(leaf, operation_id, inquiry_id, session_id)
        if ts is not None:
            self._touch_groups(ts, operation_id, inquiry_id, session_id)

    def _pi_context_event(
        self,
        ts: datetime | None,
        session_id: str,
        inquiry_id: str,
        operation_id: str,
        fields: dict,
    ) -> None:
        tokens = fields.get("input_tokens")
        calls = fields.get("model_calls")
        summary = " | ".join(
            part
            for part in (
                f"{_number(tokens)} tokens" if tokens is not None else "",
                f"model call {calls}" if calls is not None else "",
            )
            if part
        )
        leaf = TimelineItem(
            item_id=f"leaf:pi_context:{ts}:{len(self._seen)}",
            kind="pi",
            title="context",
            summary=summary,
            ts=ts,
            payload=dict(fields),
        )
        self._attach(leaf, operation_id, inquiry_id, session_id)
        if ts is not None:
            self._touch_groups(ts, operation_id, inquiry_id, session_id)

    def _panel_event(
        self,
        kind: str,
        ts: datetime | None,
        session_id: str,
        inquiry_id: str,
        operation_id: str,
        fields: dict,
    ) -> None:
        op_id = operation_id or "official"
        item = self._operation(op_id, inquiry_id, session_id, ts, "measurement")
        if item is None:
            return
        item.status = "running"
        artifact = str(fields.get("artifact") or fields.get("instrument") or "")
        if kind == "measurement_panel_started":
            title = f"panel {artifact}".strip()
            summary = " | ".join(
                part
                for part in (
                    f"{_number(fields.get('episodes'))} episodes"
                    if fields.get("episodes") is not None
                    else "",
                    f"seed {fields.get('seed')}"
                    if fields.get("seed") is not None
                    else "",
                    str(fields.get("instrument") or ""),
                )
                if part
            )
            severity = "info"
        else:
            title = f"panel complete {artifact}".strip()
            elapsed = fields.get("elapsed_seconds")
            summary = " | ".join(
                part
                for part in (
                    f"{_number(fields.get('episodes'))} / "
                    f"{_number(fields.get('episodes_total'))}"
                    if fields.get("episodes_total") is not None
                    else "",
                    f"success {float(fields['success_percent']):.1f}%"
                    if fields.get("success_percent") is not None
                    else "",
                    console.format_duration(float(elapsed))
                    if isinstance(elapsed, (int, float))
                    and not isinstance(elapsed, bool)
                    else "",
                )
                if part
            )
            severity = "info"
        leaf = TimelineItem(
            item_id=f"leaf:{kind}:{op_id}:{ts}",
            kind="measurement",
            title=title,
            summary=summary,
            ts=ts,
            severity=severity,
            detail=tuple(
                f"{key}: {_short(value)}"
                for key, value in fields.items()
                if key not in {"operation_id", "instrument"}
            ),
            payload=dict(fields),
        )
        item.children.append(leaf)
        self._items[leaf.item_id] = leaf
        item.end_ts = ts or item.end_ts
        self._active_operation = op_id
        item.summary = self._operation_summary(item)

    def _training_checkpoints_event(
        self,
        ts: datetime | None,
        session_id: str,
        inquiry_id: str,
        operation_id: str,
        fields: dict,
    ) -> None:
        candidates = (
            fields.get("candidates")
            if isinstance(fields.get("candidates"), list)
            else []
        )
        lines = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            if candidate.get("summary"):
                lines.append(
                    " | ".join(
                        part
                        for part in (
                            str(candidate.get("candidate") or ""),
                            str(candidate.get("summary")),
                        )
                        if part
                    )
                )
                continue
            lines.append(
                " | ".join(
                    part
                    for part in (
                        str(candidate.get("candidate") or ""),
                        f"{_number(candidate.get('steps'))} steps"
                        if candidate.get("steps") is not None
                        else "",
                        f"reward {candidate.get('ep_rew_mean')}"
                        if candidate.get("ep_rew_mean") is not None
                        else "",
                        f"success {round(float(candidate['training_success']) * 100)}%"
                        if isinstance(candidate.get("training_success"), (int, float))
                        and not isinstance(candidate.get("training_success"), bool)
                        else "",
                    )
                    if part
                )
            )
        leaf = TimelineItem(
            item_id=f"leaf:training_checkpoints:{operation_id}:{ts}",
            kind="training",
            title="training results",
            summary=f"{len(candidates)} candidates",
            ts=ts,
            detail=tuple(lines),
            payload=dict(fields),
        )
        self._attach(leaf, operation_id, inquiry_id, session_id)
        if ts is not None:
            self._touch_groups(ts, operation_id, inquiry_id, session_id)

    def _operation_submitted_event(
        self,
        ts: datetime | None,
        session_id: str,
        inquiry_id: str,
        operation_id: str,
        fields: dict,
    ) -> None:
        status = str(fields.get("status") or "")
        leaf = TimelineItem(
            item_id=f"leaf:operation_submitted:{ts}:{len(self._seen)}",
            kind="operation",
            title="submitted",
            summary=status,
            ts=ts,
            severity="error"
            if status in {"rejected", "implementation_error", "validation_fatal"}
            else "warning"
            if status
            not in {"completed", "accepted", "running", "needs_pi", "checkpointed"}
            else "info",
            detail=(f"Error: {_full_text(fields.get('error'))}",)
            if fields.get("error")
            else (),
            payload=dict(fields),
        )
        self._attach(leaf, operation_id, inquiry_id, session_id)
        if ts is not None:
            self._touch_groups(ts, operation_id, inquiry_id, session_id)

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
        who = f"{session_id}:{self._attempt}:{self._actor}"
        key = f"pi:{who}:{turn}" if turn is not None else f"pi:{who}:{ts}"
        existing = self._pi_items.get(key)
        if turn is not None and not final:
            text = self._pi_text.get(key, "") + text
        self._pi_text[key] = text
        detail = tuple(text.splitlines())
        if existing is not None:
            existing.summary = _first_line(text)
            existing.detail = detail
            existing.payload = dict(fields)
            return
        leaf = TimelineItem(
            item_id=f"leaf:pi:{who}:{ts}:{len(self._seen)}",
            kind="pi",
            title="PI",
            summary=_first_line(text),
            ts=ts,
            detail=detail,
            default_expanded=True,
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
        seconds = (
            float(duration)
            if isinstance(duration, (int, float)) and not isinstance(duration, bool)
            else None
        )
        summary = _tool_summary(
            {**fields, "name": name, "detail": detail},
            status,
            seconds,
            root=self._campaign_root,
        )
        leaf = TimelineItem(
            item_id=f"leaf:tool:{name}:{ts}:{len(self._seen)}",
            kind="tool",
            title=name,
            summary=summary,
            ts=ts,
            detail=_tool_details({**fields, "detail": detail}),
            default_expanded=True,
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
        candidate = (
            str(fields.get("candidate") or fields.get("id") or "")
            if kind == "candidate_created"
            else ""
        )
        item_id = (
            f"candidate:{candidate}"
            if candidate
            else f"leaf:{kind}:{ts}:{len(self._seen)}"
        )
        existing = self._items.get(item_id) if candidate else None
        if existing is not None:
            fields = {**existing.payload, **fields}
        title = {
            "role_assigned": f"role {fields.get('role') or ''}".strip(),
            "candidate_created": f"candidate {fields.get('candidate') or fields.get('id') or ''}".strip(),
            "checkpoint_saved": "checkpoint saved",
            "activity": f"activity {fields.get('label') or ''}".strip(),
        }.get(kind, kind.replace("_", " "))
        summary = _first_line(
            fields.get("current_synthesis")
            or fields.get("candidate")
            or fields.get("label")
            or fields.get("text")
            or fields.get("summary")
            or ""
        )
        if candidate:
            summary = _first_line(fields.get("summary") or fields.get("text") or "")
            if summary == candidate:
                summary = ""
        leaf = TimelineItem(
            item_id=item_id,
            kind={
                "role_assigned": "role",
                "candidate_created": "role",
                "checkpoint_saved": "checkpoint",
            }.get(kind, kind if kind in KIND_GLYPHS else "log"),
            title=title,
            summary=summary,
            ts=ts,
            detail=tuple(
                line
                for line in (
                    f"Current synthesis: {_full_text(fields.get('current_synthesis'))}"
                    if fields.get("current_synthesis")
                    else "",
                    f"Next question: {_full_text(fields.get('next_question'))}"
                    if fields.get("next_question")
                    else "",
                    f"Next: {_full_text(fields.get('next_direction_or_closure'))}"
                    if fields.get("next_direction_or_closure")
                    else "",
                    f"Scientific commit: {fields.get('scientific_commit')}"
                    if fields.get("scientific_commit")
                    else "",
                    f"Candidate: {fields.get('candidate')}"
                    if fields.get("candidate")
                    else "",
                    f"Role: {fields.get('role')}" if fields.get("role") else "",
                    f"Evidence: {_full_text(fields.get('evidence'))}"
                    if fields.get("evidence")
                    else "",
                    f"Steps: {_number(fields.get('training_steps'))}"
                    if fields.get("training_steps") is not None
                    else "",
                    f"Success: {round(float(fields['training_success']) * 100)}%"
                    if isinstance(fields.get("training_success"), (int, float))
                    and not isinstance(fields.get("training_success"), bool)
                    else "",
                )
                if line
            ),
            payload=dict(fields),
        )
        if existing is not None:
            existing.title = leaf.title
            existing.summary = leaf.summary
            existing.detail = leaf.detail
            existing.payload = leaf.payload
            existing.ts = existing.ts or ts
            return
        self._attach(leaf, operation_id, inquiry_id, session_id)
        if ts is not None:
            self._touch_groups(ts, operation_id, inquiry_id, session_id)

    def _usage_event(
        self,
        kind: str,
        ts: datetime | None,
        session_id: str,
        operation_id: str,
        fields: dict,
    ) -> None:
        totals = fields.get("totals") if isinstance(fields.get("totals"), dict) else {}
        if kind in {"campaign_usage", "session_usage"}:
            title = "campaign usage" if kind == "campaign_usage" else "session usage"
            summary = str(fields.get("text") or "")
            if not summary and totals:
                summary = " | ".join(
                    part
                    for part in (
                        console.format_duration(float(totals["duration_seconds"]))
                        if totals.get("duration_seconds") is not None
                        else "",
                        f"{float(totals['aiu']):.2f} AIU" if totals.get("aiu") else "",
                        f"prompt {_number(totals.get('input_tokens'))}"
                        if totals.get("input_tokens")
                        else "",
                        f"output {_number(totals.get('output_tokens'))}"
                        if totals.get("output_tokens")
                        else "",
                    )
                    if part
                )
            if kind == "campaign_usage":
                summary = self._with_aiu_change(summary, totals)
            detail = (_json_text(totals),) if totals else ()
        else:
            role = str(fields.get("role") or "usage")
            title = f"usage {role}"
            summary = " | ".join(
                part
                for part in (
                    str(fields.get("model") or ""),
                    console.format_duration(float(fields["duration_seconds"]))
                    if fields.get("duration_seconds") is not None
                    else "",
                    f"prompt {_number(fields.get('input_tokens'))}"
                    if fields.get("input_tokens") is not None
                    else "",
                    f"output {_number(fields.get('output_tokens'))}"
                    if fields.get("output_tokens") is not None
                    else "",
                    f"{fields.get('tool_calls')} tool calls"
                    if fields.get("tool_calls") is not None
                    else "",
                )
                if part
            )
            detail = (_json_text(fields),)
        leaf = TimelineItem(
            item_id=f"leaf:{kind}:{ts}:{len(self._seen)}",
            kind="usage",
            title=title,
            summary=summary,
            ts=ts,
            detail=detail,
            payload=dict(fields),
        )
        # Campaign usage totals show where they were written: in the official
        # assessment, else in the session that wrote them, else in the campaign.
        official = kind == "campaign_usage" and operation_id == OFFICIAL_OPERATION
        self._attach(leaf, OFFICIAL_OPERATION if official else "", "", session_id)
        if ts is not None:
            self._touch_groups(
                ts, OFFICIAL_OPERATION if official else "", "", session_id
            )

    def _with_aiu_change(self, summary: str, totals: dict) -> str:
        """The usage line, with how many AIU the campaign used since the last one."""
        aiu = totals.get("aiu")
        if not isinstance(aiu, (int, float)) or isinstance(aiu, bool):
            return summary
        previous, self._last_campaign_aiu = self._last_campaign_aiu, float(aiu)
        if previous is None or float(aiu) <= previous:
            return summary
        text = f"{float(aiu):.2f} AIU"
        change = f"{text} (+{float(aiu) - previous:.2f})"
        return (
            summary.replace(text, change, 1)
            if text in summary
            else (f"{summary} | {change}" if summary else change)
        )

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
            title=(f"{code} {kind}".strip() if code else kind.replace("_", " ")),
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

    def _root_event(
        self,
        kind: str,
        ts: datetime | None,
        fields: dict,
        session_id: str = "",
        operation_id: str = "",
    ) -> None:
        if kind == "run_state":
            # The state drives the "Now" line and the tab; each change repeats an
            # operation row, so it adds no row of its own.
            self._run_state = str(fields.get("state") or "")
            return
        title = {
            "campaign_started": "campaign started",
            "campaign_concluded": "campaign concluded",
            "campaign_goal_review": "campaign goal review",
            "publication_recovered": "publication recovered",
            "scientific_model_validated": "scientific model validated",
        }.get(kind, kind.replace("_", " "))
        official = kind == "campaign_concluded" and operation_id == OFFICIAL_OPERATION
        status = str(fields.get("status") or "")
        if official:
            title = f"campaign concluded | {status}".strip(" |")
        # A commit identifier is noise on the timeline; the raw event keeps it.
        shown = {key: value for key, value in fields.items() if key != "commit"}
        leaf = TimelineItem(
            item_id=f"leaf:{kind}:{ts}:{len(self._seen)}",
            kind="result"
            if kind in {"publication_recovered", "scientific_model_validated"}
            or (official and status == "passed")
            else "campaign",
            title=title,
            summary=_first_line(
                (fields.get("next") if official else None)
                or fields.get("summary")
                or fields.get("state")
                or fields.get("reason")
                or (fields.get("path") if kind == "scientific_model_validated" else "")
                or ""
            ),
            ts=ts,
            severity="error" if official and status == "failed" else "info",
            detail=tuple(f"{key}: {_short(value)}" for key, value in shown.items()),
            payload=dict(fields),
        )
        if kind == "campaign_concluded":
            # The PI's request closes its session; the official outcome closes
            # the assessment that produced it.
            self._attach(leaf, OFFICIAL_OPERATION if official else "", "", session_id)
            if ts is not None:
                self._touch_groups(
                    ts, OFFICIAL_OPERATION if official else "", "", session_id
                )
            return
        if kind in {
            "scientific_model_validated",
            "campaign_goal_review",
            "publication_recovered",
        }:
            # They belong to the session that produced them when it is named.
            self._attach(leaf, "", "", session_id)
            if kind == "scientific_model_validated" and (
                self._current_session == session_id
            ):
                self._current_session = ""
            if ts is not None:
                self._touch_groups(ts, "", "", session_id)
            return
        self._campaign_group().children.append(leaf)
        self._items[leaf.item_id] = leaf

    def _notice_event(
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
        if not title:
            title = _first_line(text)
            detail.extend(text.splitlines()[1:])
            if len(text) > len(title):
                detail.insert(0, text)
        leaf = TimelineItem(
            item_id=f"leaf:notice:{ts}:{len(self._seen)}",
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
        """Attach a row to the most specific owner its identities name.

        An operation owns it, else the session (in its inquiry group when the
        row names one), else the campaign. A named owner is created when this
        is the first reference to it. Nothing is guessed from what happened
        before.
        """
        self._items[leaf.item_id] = leaf
        if operation_id:
            parent = self._operation(
                operation_id, inquiry_id, session_id, leaf.ts, "operation"
            )
        elif session_id and inquiry_id:
            parent = self._inquiry(inquiry_id, session_id, leaf.ts, {})
        elif session_id:
            parent = self._session(session_id, leaf.ts, {})
        else:
            parent = self._campaign_group()
        parent.children.append(leaf)

    def _touch_groups(
        self,
        ts: datetime,
        operation_id: str,
        inquiry_id: str,
        session_id: str,
    ) -> None:
        for item in (
            self._operations.get(operation_id) if operation_id else None,
            self._inquiries.get((session_id, inquiry_id)) if inquiry_id else None,
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
            if latest is not None and item.status in {"running", "requested"}:
                parts.append(latest.title)
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

    def phase(self) -> str:
        """What the campaign is doing now: official, training, evaluating,
        coding, preparing, pi or none."""
        operation = (
            self._operations.get(self._active_operation)
            if self._active_operation
            else None
        )
        if operation is not None and operation.status in {"running", "requested"}:
            if self._active_operation == "official":
                return "official"
            if operation.kind == "training":
                return "training"
            if operation.kind == "measurement":
                return "evaluating"
        if self._coding_open:
            return "coding"
        session = self._sessions.get(self._current_session)
        if session is not None and session.status != "closed":
            return "preparing" if self._current_session == PREPARATION_SESSION else "pi"
        return "none"

    @property
    def now_text(self) -> str:
        if self._active_operation:
            item = self._operations.get(self._active_operation)
            if item is not None and item.status in {"running", "requested"}:
                chain = []
                if self._current_inquiry:
                    chain.append(self._current_inquiry[1])
                if self._current_session:
                    chain.append(self._current_session)
                chain.append(item.title)
                detail = f" | {item.summary}" if item.summary else ""
                return "Now: " + " / ".join(chain) + detail
        if self._last_completed:
            stamp = _clock(self._last_completed_ts)
            state = self._run_state or "idle"
            latest = (
                f"last completed {self._last_completed} {self._last_completed_kind}"
            )
            if stamp:
                latest = f"{latest} | {stamp}"
            return f"Now: {state} | {latest}"
        if self._run_state:
            return f"Now: {self._run_state}"
        if not self._seen:
            return "Now: waiting for events"
        return "Now: waiting for the first operation"

    def active_ids(self) -> set[str]:
        ids = set()
        if self._current_session:
            ids.add(f"session:{self._current_session}")
        if self._current_inquiry:
            session, inquiry = self._current_inquiry
            ids.add(f"inquiry:{session}:{inquiry}")
        if self._active_operation:
            ids.add(f"operation:{self._active_operation}")
            owner = self._operation_session.get(self._active_operation)
            if owner:
                ids.add(f"session:{owner}")
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
            lazy=item.lazy,
        )

    def live_summaries(self) -> dict[str, str]:
        """Current summary of each running tool, keyed by item id."""
        now = _now()
        summaries: dict[str, str] = {}
        for key in self._running_tools:
            tool = self._tools.get(key)
            if tool is None or tool.status != "started" or tool.ts is None:
                continue
            seconds = max(0.0, (now - tool.ts).total_seconds())
            if seconds >= 1:
                summaries[tool.item_id] = _tool_summary(
                    tool.payload, tool.status, seconds, root=self._campaign_root
                )
        return summaries

    def _live_tool(self, item: TimelineItem) -> TimelineItem:
        """A running tool shows how long it has been running."""
        if item.kind != "tool" or item.status != "started" or item.ts is None:
            return item
        seconds = max(0.0, (_now() - item.ts).total_seconds())
        if seconds < 1:
            return item
        live = self._clone(item, item.children)
        live.summary = _tool_summary(
            item.payload, item.status, seconds, root=self._campaign_root
        )
        return live

    def _deep_clone(self, item: TimelineItem) -> TimelineItem:
        if not item.is_group:
            return self._live_tool(item)
        return self._clone(item, [self._deep_clone(child) for child in item.children])

    def _leaf_count(self, item: TimelineItem) -> int:
        """Events inside a group; cached until the group itself changes."""
        key = (len(item.children), item.end_ts)
        cached = self._leaf_counts.get(item.item_id)
        if cached is not None and cached[0] == key:
            return cached[1]

        def count(node: TimelineItem) -> int:
            if not node.is_group:
                return 1
            return sum(count(child) for child in node.children)

        total = count(item)
        self._leaf_counts[item.item_id] = (key, total)
        return total

    def _fast_view(self, open_ids: set[str] | None) -> tuple[list[TimelineItem], int]:
        """The unfiltered view in one pass. A finished session that nobody has
        opened is shown folded, so the cost follows what is open, not how long
        the campaign has run."""
        active = self.active_ids()
        matches = 0

        def build(item: TimelineItem) -> TimelineItem:
            nonlocal matches
            if not item.is_group:
                matches += 1
                return self._live_tool(item)
            if (
                open_ids is not None
                and item.kind == "session"
                and item.status == "closed"
                and item.item_id not in active
                and item.item_id not in open_ids
            ):
                folded = self._clone(item, [])
                folded.lazy = self._leaf_count(item)
                matches += folded.lazy
                return folded
            return self._clone(item, [build(child) for child in item.children])

        roots = [build(root) for root in self._roots]
        return roots, matches

    def view(
        self,
        *,
        query: str = "",
        categories: set[str] | None = None,
        open_ids: set[str] | None = None,
    ) -> tuple[list[TimelineItem], int]:
        query = query.strip().casefold()
        categories = categories or set()
        if not query and not categories:
            return self._fast_view(open_ids)
        matches = 0

        def include(item: TimelineItem) -> tuple[bool, TimelineItem | None]:
            nonlocal matches
            text_match = not query or query in item.searchable()
            if not item.is_group:
                keep = text_match and self._category_match(item.kind, categories)
                if keep:
                    matches += 1
                return keep, self._live_tool(item) if keep else None
            child_items: list[TimelineItem] = []
            for child in item.children:
                keep, filtered = include(child)
                if keep and filtered is not None:
                    child_items.append(filtered)
            group_category_match = self._category_match(item.kind, categories)
            if (not query and group_category_match) or (
                query and text_match and not child_items
            ):
                child_items = [self._deep_clone(child) for child in item.children]
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
