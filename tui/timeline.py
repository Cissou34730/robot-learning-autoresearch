"""Structured timeline reducer for the operator log.

The reducer is deliberately terminal-free: events in, a small tree of
display items out. The Textual widget only renders this tree and keeps the
user's expansion and selection state.
"""

from __future__ import annotations

import itertools
import json
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from runner import reporting as console
from runner.event_contract import (
    LAUNCH_KINDS,
    LAUNCHER_STOP_CODES,
    OFFICIAL_OPERATION,
    PREPARATION_SESSION,
    missing_identity,
)
from tui.activity import LiveActivity, training_eta_seconds
from tui.observations import Observation
from tui.timeline_formatting import as_percent as _as_percent
from tui.timeline_formatting import candidate_summary as _candidate_summary
from tui.timeline_formatting import clock as _clock
from tui.timeline_formatting import first_line as _first_line
from tui.timeline_formatting import full_text as _full_text
from tui.timeline_formatting import json_text as _json_text
from tui.timeline_formatting import now as _now
from tui.timeline_formatting import number as _number
from tui.timeline_formatting import operation_detail as _operation_detail
from tui.timeline_formatting import operation_summary as _operation_summary
from tui.timeline_formatting import short as _short
from tui.timeline_formatting import tool_details as _tool_details
from tui.timeline_formatting import tool_summary as _tool_summary
from tui.timeline_items import KIND_GLYPHS, TimelineItem
from tui.timeline_view import TimelineView

_VERSIONS = itertools.count()
PROGRESS_ROW_SECONDS = {"training_progress": 30.0, "eval_progress": 15.0}


def _lower_ts(item: TimelineItem, ts: datetime | None) -> None:
    """A group starts at the earliest event it has seen."""
    if ts is not None and (item.ts is None or ts < item.ts):
        item.ts = ts


class TimelineReducer:
    """Events in, grouped timeline out. No terminal and no campaign writes."""

    def __init__(self, campaign_root: Path | None = None) -> None:
        self._campaign_root = campaign_root
        self.activity = LiveActivity()
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
        self._event_id = ""
        self._event_kind = ""
        self.version = next(_VERSIONS)
        self._running_tools: set[str] = set()
        self._progress_rows: dict[str, TimelineItem] = {}
        self._coding_open = False
        self._last_fact: tuple[str, str] | None = None
        self._coalesce_progress = False
        self._view = TimelineView(self._roots, self._items, campaign_root)
        self._view_version = self.version

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------

    def clear(self) -> None:
        clock = self.activity.clock
        self.__init__(self._campaign_root)
        self.activity.clock = clock

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
            event_id=self._event_id,
            event_kind=self._event_kind,
        )
        self._items[leaf.item_id] = leaf
        self._campaign_group().children.append(leaf)

    def ingest(self, event: Observation) -> None:
        event_id = event.event_id or self._fallback_id(event)
        if event_id in self._seen:
            return
        self._seen.add(event_id)
        self._event_id = event_id
        self._event_kind = event.kind
        kind = event.kind
        fields = event.fields or {}
        ts = event.ts
        if kind == "liveness":
            self.activity.ingest(event)
            return
        self._coalesce_progress = self._last_fact == (kind, event.operation_id)
        self._last_fact = (kind, event.operation_id)
        # Any other new event may change the view; an idle tick must not.
        self.version = next(_VERSIONS)
        if kind != "run_state":
            self._view_version = self.version
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
        self.activity.ingest(event)
        # Who spoke and in which invocation, for the handler about to run.
        self._attempt = event.attempt
        self._actor = event.actor
        self._campaign_group_follows(kind, fields, session_id)
        if self._resume_interrupted(kind, operation_id, fields):
            self._view_version = self.version
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
        identity = (
            event.kind,
            event.ts,
            event.session_id,
            event.inquiry_id,
            event.operation_id,
            event.campaign_id,
            event.attempt,
            event.actor,
            event.fields,
        )
        encoded = json.dumps(identity, default=str, sort_keys=True).encode("utf-8")
        return "legacy:" + sha256(encoded).hexdigest()

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------

    def _add_root(self, item: TimelineItem) -> TimelineItem:
        self._items[item.item_id] = item
        self._roots.append(item)
        return item

    def _resume_interrupted(self, kind: str, operation_id: str, fields: dict) -> bool:
        """A run state "executing" for an interrupted operation means it runs again."""
        if kind != "run_state" or fields.get("state") != "executing":
            return False
        item = self._operations.get(operation_id)
        if item is not None and item.status == "interrupted":
            item.status = "running"
            item.severity = "info"
            self._active_operation = operation_id
            item.summary = _operation_summary(item)
            return True
        return False

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
                event_id=self._event_id,
                event_kind=self._event_kind,
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
                    event_id=self._event_id,
                    event_kind=self._event_kind,
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
                event_id=self._event_id,
                event_kind=self._event_kind,
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
                event_id=self._event_id,
                event_kind=self._event_kind,
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
        if item.kind == "operation" and kind and kind != "operation":
            item.kind = kind
            if operation_id != OFFICIAL_OPERATION:
                item.title = f"{operation_id} {kind}"
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
            event_id=self._event_id,
            event_kind=self._event_kind,
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
            item_id=f"leaf:{self._event_kind}:{self._event_id}",
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
            event_id=self._event_id,
            event_kind=self._event_kind,
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
            if not finished:
                item.status = "running"
            summary = _first_line(fields.get("text") or "running")
        if kind in {
            "operation_completed",
            "operation_failed",
            "operation_requested",
            "operation_started",
        }:
            detail = _operation_detail(fields)
            if fields.get("error"):
                detail = (f"Error: {_full_text(fields.get('error'))}", *detail)
            leaf = TimelineItem(
                item_id=f"leaf:{self._event_kind}:{self._event_id}",
                kind=operation_kind,
                title=summary,
                summary="",
                ts=ts,
                severity=item.severity,
                detail=detail,
                payload=dict(fields),
                event_id=self._event_id,
                event_kind=self._event_kind,
            )
        else:
            text = _first_line(fields.get("text") or summary)
            leaf = TimelineItem(
                item_id=f"leaf:{self._event_kind}:{self._event_id}",
                kind=operation_kind,
                title=text,
                ts=ts,
                severity=item.severity,
                payload=dict(fields),
                event_id=self._event_id,
                event_kind=self._event_kind,
            )
        item.children.append(leaf)
        self._items[leaf.item_id] = leaf
        item.end_ts = ts or item.end_ts
        if item.status in {"running", "requested"}:
            self._active_operation = operation_id
        item.summary = _operation_summary(item)

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
            item_id=f"leaf:{self._event_kind}:{self._event_id}",
            kind="result" if passed else "measurement",
            title=outcome,
            summary=" | ".join(part for part in (figures, margin) if part),
            ts=ts,
            severity=item.severity,
            detail=detail,
            payload=dict(fields),
            default_expanded=True,
            event_id=self._event_id,
            event_kind=self._event_kind,
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
            item.summary = (
                _operation_summary(item)
                if item.status in {"completed", "failed", "passed"}
                else summary
            )
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
            item.summary = (
                _operation_summary(item)
                if item.status in {"completed", "failed", "passed"}
                else summary
            )
            title = summary
        current_row = self._progress_rows.get(operation_id)
        if (
            current_row is not None
            and self._coalesce_progress
            and item.children
            and item.children[-1] is current_row
            and ts is not None
            and previous_ts is not None
            and (current_row.ts is None or ts >= current_row.ts)
            and (ts - previous_ts).total_seconds() < PROGRESS_ROW_SECONDS[kind]
        ):
            # Samples can arrive every second. While no other row has followed
            # it, the last progress row stands for its newest sample, values and
            # time together, so the list stays in time order.
            current_row.title = title
            current_row.payload = dict(fields)
            current_row.ts = ts
            item.end_ts = ts
            if kind == "eval_progress":
                item.summary = _operation_summary(item)
            return
        self._progress[operation_id] = (ts, steps if isinstance(steps, int) else None)
        leaf = TimelineItem(
            item_id=f"leaf:{self._event_kind}:{self._event_id}",
            kind=kind,
            title=title,
            ts=ts,
            payload=dict(fields),
            event_id=self._event_id,
            event_kind=self._event_kind,
        )
        self._progress_rows[operation_id] = leaf
        item.children.append(leaf)
        self._items[leaf.item_id] = leaf
        item.end_ts = ts or item.end_ts
        if kind == "eval_progress":
            item.summary = _operation_summary(item)

    def _attempt_event(
        self, ts: datetime | None, session_id: str, fields: dict
    ) -> None:
        """One PI invocation starting in a session (an attempt)."""
        item = self._session(session_id, ts, fields)
        self._current_session = session_id
        stage = _first_line(fields.get("stage") or "")
        resumed = " | resumed" if fields.get("resumed") else ""
        leaf = TimelineItem(
            item_id=f"leaf:{self._event_kind}:{self._event_id}",
            kind="session",
            title="PI started",
            summary=f"{stage}{resumed}".strip(" |"),
            ts=ts,
            payload=dict(fields),
            event_id=self._event_id,
            event_kind=self._event_kind,
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
            item_id=f"leaf:{self._event_kind}:{self._event_id}",
            kind="session",
            title=title,
            summary=summary,
            ts=ts,
            detail=detail,
            payload=dict(fields),
            event_id=self._event_id,
            event_kind=self._event_kind,
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
                event_id=self._event_id,
                event_kind=self._event_kind,
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
                    event_id=self._event_id,
                    event_kind=self._event_kind,
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
            item_id=f"leaf:{self._event_kind}:{self._event_id}",
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
            event_id=self._event_id,
            event_kind=self._event_kind,
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
            item_id=f"leaf:{self._event_kind}:{self._event_id}",
            kind="file",
            title=f"{marker} {path}",
            summary=operation + suffix,
            ts=ts,
            detail=(f"Path: {fields.get('path')}",) if fields.get("path") else (),
            payload=dict(fields),
            event_id=self._event_id,
            event_kind=self._event_kind,
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
            item_id=f"leaf:{self._event_kind}:{self._event_id}",
            kind="pi",
            title="context",
            summary=summary,
            ts=ts,
            payload=dict(fields),
            event_id=self._event_id,
            event_kind=self._event_kind,
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
        if item.status not in {"completed", "failed", "passed"}:
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
            item_id=f"leaf:{self._event_kind}:{self._event_id}",
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
            event_id=self._event_id,
            event_kind=self._event_kind,
        )
        item.children.append(leaf)
        self._items[leaf.item_id] = leaf
        item.end_ts = ts or item.end_ts
        if item.status == "running":
            self._active_operation = op_id
        item.summary = _operation_summary(item)

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
        leaf = TimelineItem(
            item_id=f"leaf:{self._event_kind}:{self._event_id}",
            kind="training",
            title="training results",
            summary=f"{len(candidates)} candidates",
            ts=ts,
            is_group=True,
            default_expanded=True,
            payload=dict(fields),
            event_id=self._event_id,
            event_kind=self._event_kind,
        )
        self._attach(leaf, operation_id, inquiry_id, session_id)
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            name = str(candidate.get("candidate") or candidate.get("checkpoint") or "")
            item_id = f"candidate:{name}"
            existing = self._items.get(item_id)
            if existing is not None:
                existing.payload = {**existing.payload, **candidate}
                existing.summary = _candidate_summary(existing.payload)
                continue
            checkpoint = TimelineItem(
                item_id=item_id,
                kind="role",
                title=f"candidate {name}",
                summary=_candidate_summary(candidate),
                ts=ts,
                payload=dict(candidate),
                event_id=self._event_id,
                event_kind=self._event_kind,
            )
            leaf.children.append(checkpoint)
            self._items[item_id] = checkpoint
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
            item_id=f"leaf:{self._event_kind}:{self._event_id}",
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
            event_id=self._event_id,
            event_kind=self._event_kind,
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
            item_id=f"leaf:{self._event_kind}:{self._event_id}",
            kind="pi",
            title="PI",
            summary=_first_line(text),
            ts=ts,
            detail=detail,
            default_expanded=True,
            payload=dict(fields),
            event_id=self._event_id,
            event_kind=self._event_kind,
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
            item_id=f"leaf:{self._event_kind}:{self._event_id}",
            kind="tool",
            title=name,
            summary=summary,
            ts=ts,
            detail=_tool_details({**fields, "detail": detail}),
            default_expanded=True,
            payload=dict(fields),
            event_id=self._event_id,
            event_kind=self._event_kind,
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
            else f"leaf:{self._event_kind}:{self._event_id}"
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
            summary = _candidate_summary(fields) or _first_line(
                fields.get("text") or ""
            )
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
            event_id=self._event_id,
            event_kind=self._event_kind,
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
            item_id=f"leaf:{self._event_kind}:{self._event_id}",
            kind="usage",
            title=title,
            summary=summary,
            ts=ts,
            detail=detail,
            payload=dict(fields),
            event_id=self._event_id,
            event_kind=self._event_kind,
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
            item_id=f"leaf:{self._event_kind}:{self._event_id}",
            kind="error" if kind == "error" else "warning",
            title=(f"{code} {kind}".strip() if code else kind.replace("_", " ")),
            summary=_first_line(message),
            ts=ts,
            severity="error" if kind == "error" else "warning",
            detail=(_json_text(fields),),
            default_expanded=True,
            payload=dict(fields),
            event_id=self._event_id,
            event_kind=self._event_kind,
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
            item_id=f"leaf:{self._event_kind}:{self._event_id}",
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
            event_id=self._event_id,
            event_kind=self._event_kind,
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
            item_id=f"leaf:{self._event_kind}:{self._event_id}",
            kind=kind,
            title=title or "log",
            summary="",
            ts=ts,
            severity=severity,
            detail=tuple(line for line in detail if line.strip()),
            payload=dict(fields),
            event_id=self._event_id,
            event_kind=self._event_kind,
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

    # ------------------------------------------------------------------
    # View
    # ------------------------------------------------------------------

    def phase(self) -> str:
        operation = self._operations.get(self._active_operation)
        session = self._sessions.get(self._current_session)
        return self.activity.phase(
            self._active_operation,
            operation.kind if operation else "",
            operation.status if operation else "",
            self._current_session if session is not None else "",
            session.status == "closed" if session else True,
            self._coding_open,
        )

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

    def _active_ids(self) -> set[str]:
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

    def active_ids(self) -> set[str]:
        return self._view.expand_active(self._view_version, self._active_ids())

    def view(
        self,
        *,
        query: str = "",
        categories: set[str] | None = None,
        open_ids: set[str] | None = None,
    ) -> tuple[list[TimelineItem], int]:
        return self._view.project(
            self._view_version,
            self._active_ids(),
            query=query,
            categories=categories,
            open_ids=open_ids,
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
