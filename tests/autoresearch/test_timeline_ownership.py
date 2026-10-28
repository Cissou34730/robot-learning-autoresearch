"""Ownership and ordering regressions of the operator timeline.

These pin facts measured on recorded campaigns: operations belong to exactly one
session, inquiries span sessions, official assessment has no session, and a
preparation can be attempted more than once.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from textual.app import App

from tui.event_log import EventLog
from tui.observations import Observation
from tui.timeline import TimelineItem, TimelineReducer

START = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)


def _at(seconds: float) -> datetime:
    return START + timedelta(seconds=seconds)


def _event(kind, seconds, fields=None, **identity):
    return Observation(kind=kind, ts=_at(seconds), fields=fields or {}, **identity)


def _walk(items, parent=None):
    for item in items:
        yield item, parent
        yield from _walk(item.children, item)


def _find(reducer, item_id):
    roots, _ = reducer.view()
    for item, parent in _walk(roots):
        if item.item_id == item_id:
            return item, parent
    raise AssertionError(f"{item_id} is not in the timeline")


def _ancestors(reducer, item_id):
    roots, _ = reducer.view()
    chain: list[str] = []

    def search(items, path):
        for item in items:
            if item.item_id == item_id:
                chain.extend(path)
                return True
            if search(item.children, [*path, item.item_id]):
                return True
        return False

    assert search(roots, []), f"{item_id} is not in the timeline"
    return chain


def test_operation_belongs_to_the_session_that_ran_it_not_the_one_that_opened_its_inquiry():
    reducer = TimelineReducer()
    reducer.ingest(
        _event("session_started", 0, {"id": "S2", "kind": "startup"}, session_id="S2")
    )
    reducer.ingest(
        _event(
            "inquiry_opened",
            1,
            {"question": "Does it reach?"},
            session_id="S2",
            inquiry_id="I1",
        )
    )
    reducer.ingest(
        _event(
            "session_started", 10, {"id": "S3", "kind": "experiment"}, session_id="S3"
        )
    )
    reducer.ingest(
        _event(
            "operation_started",
            11,
            {"kind": "training"},
            session_id="S3",
            inquiry_id="I1",
            operation_id="T2",
        )
    )
    chain = _ancestors(reducer, "operation:T2")
    assert "session:S3" in chain
    assert "session:S2" not in chain


def test_an_operation_that_arrives_before_its_session_start_is_not_misfiled():
    reducer = TimelineReducer()
    reducer.ingest(
        _event(
            "operation_started",
            5,
            {"kind": "training"},
            session_id="S1",
            operation_id="T1",
        )
    )
    reducer.ingest(
        _event("session_started", 6, {"id": "S1", "kind": "startup"}, session_id="S1")
    )
    roots, _ = reducer.view()
    sessions = [item for item in roots if item.kind == "session"]
    assert [item.item_id for item in sessions] == ["session:S1"]
    assert sessions[0].title == "S1 startup"
    assert "operation:T1" in {child.item_id for child in sessions[0].children}


def test_a_session_group_is_never_backdated_to_the_campaign_start():
    reducer = TimelineReducer()
    reducer.ingest(
        _event(
            "tool_call_started",
            90,
            {"tool_call_id": "t", "name": "view"},
            session_id="S10",
        )
    )
    session, _ = _find(reducer, "session:S10")
    assert session.ts == _at(90)


def test_official_assessment_is_owned_by_the_campaign_not_by_a_guessed_session():
    reducer = TimelineReducer()
    reducer.ingest(
        _event(
            "session_started", 0, {"id": "S9", "kind": "experiment"}, session_id="S9"
        )
    )
    reducer.ingest(
        _event(
            "eval_progress",
            5,
            {"operation_id": "official", "episodes": 3, "episodes_total": 200},
            operation_id="official",
        )
    )
    chain = _ancestors(reducer, "operation:official")
    assert chain == ["campaign:root"]


def test_an_event_missing_a_required_identity_is_reported_not_guessed():
    reducer = TimelineReducer()
    reducer.ingest(
        _event("session_started", 0, {"id": "S1", "kind": "startup"}, session_id="S1")
    )
    reducer.ingest(
        _event("pi_message", 4, {"text": "orphan", "final": True, "turn": 1})
    )
    roots, _ = reducer.view()
    session = next(item for item in roots if item.item_id == "session:S1")
    assert not any(child.kind == "pi" for child in session.children)
    diagnostics = [
        item
        for item, _parent in _walk(roots)
        if item.kind == "warning" and "pi_message" in item.summary
    ]
    assert len(diagnostics) == 1
    assert _ancestors(reducer, diagnostics[0].item_id) == ["campaign:root"]


def test_two_preparation_attempts_keep_their_own_messages():
    reducer = TimelineReducer()
    for attempt, base in (("attempt-1", 0), ("attempt-2", 100)):
        reducer.ingest(
            _event(
                "pi_message",
                base + 1,
                {"text": f"message of {attempt}", "final": True, "turn": 1},
                session_id="preparation",
                attempt=attempt,
                actor="pi",
            )
        )
    roots, _ = reducer.view()
    texts = [item.summary for item, _parent in _walk(roots) if item.kind == "pi"]
    assert texts == ["message of attempt-1", "message of attempt-2"]


def test_a_thinned_progress_row_carries_the_time_of_its_latest_sample():
    reducer = TimelineReducer()
    for seconds, steps in ((1, 1000), (5, 5000)):
        reducer.ingest(
            _event(
                "training_progress",
                seconds,
                {"operation_id": "T9", "steps": steps, "target": 9999},
                session_id="S1",
                operation_id="T9",
            )
        )
    roots, _ = reducer.view()
    rows = [item for item, _parent in _walk(roots) if item.kind == "training_progress"]
    assert len(rows) == 1
    assert "5,000" in rows[0].title
    assert rows[0].ts == _at(5)


def test_a_failure_that_belongs_to_no_session_opens_the_campaign_group_until_a_new_launch():
    reducer = TimelineReducer()
    reducer.ingest(_event("campaign_started", 0, {"summary": "goal"}))
    reducer.ingest(
        _event(
            "error",
            5,
            {"text": "the launcher stopped", "code": "launcher_failed"},
            severity="error",
        )
    )
    assert _find(reducer, "campaign:root")[0].default_expanded is True
    reducer.ingest(
        _event("session_start", 9, {}, session_id="S2", attempt="inv-2", actor="pi")
    )
    assert _find(reducer, "campaign:root")[0].default_expanded is False


def test_the_widget_follows_a_change_of_parent_even_when_the_rows_look_equal():
    first = TimelineItem(item_id="a", kind="session", title="A", is_group=True)
    second = TimelineItem(item_id="b", kind="session", title="B", is_group=True)
    nested = TimelineItem(
        item_id="a",
        kind="session",
        title="A",
        is_group=True,
        children=[TimelineItem(item_id="b", kind="session", title="B", is_group=True)],
    )

    class _Host(App):
        def compose(self):
            yield EventLog({}, id="log")

    async def scenario():
        app = _Host()
        async with app.run_test(size=(80, 24)) as pilot:
            log = app.query_one("#log", EventLog)
            log.set_view([first, second])
            await pilot.pause()
            assert [node.data.item_id for node in log.root.children] == ["a", "b"]
            log.set_view([nested])
            await pilot.pause()
            assert [node.data.item_id for node in log.root.children] == ["a"]
            assert [n.data.item_id for n in log.root.children[0].children] == ["b"]

    asyncio.run(scenario())
