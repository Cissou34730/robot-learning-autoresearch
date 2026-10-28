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


def test_official_assessment_is_a_top_level_group_not_under_a_guessed_session():
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
    assert _ancestors(reducer, "operation:official") == []
    roots, _ = reducer.view()
    assert [root.item_id for root in roots] == ["session:S9", "operation:official"]


def _official_run(passed: bool, *, figures: bool = True):
    reducer = TimelineReducer()
    reducer.ingest(
        _event(
            "session_started", 0, {"id": "S12", "kind": "goal_review"}, session_id="S12"
        )
    )
    reducer.ingest(
        _event(
            "campaign_concluded",
            10,
            {"status": "official_assessment_requested", "reason": "Request it"},
            session_id="S12",
            operation_id="E26",
        )
    )
    reducer.ingest(
        _event(
            "operation_started",
            20,
            {"id": "official", "kind": "measurement", "model": "T4:checkpoint-95232"},
            operation_id="official",
        )
    )
    reducer.ingest(
        _event(
            "eval_progress",
            25,
            {"operation_id": "official", "episodes": 100, "episodes_total": 200},
            operation_id="official",
        )
    )
    result = {
        "id": "official",
        "kind": "measurement",
        "status": "passed" if passed else "failed",
        "model": "T4:checkpoint-95232",
        "summary": "goal reached" if passed else "goal not reached; success 97.5%",
    }
    if figures:
        result |= {
            "success_percent": 98.5 if passed else 97.5,
            "episodes": 200,
            "required_success_percent": 98.0,
        }
    reducer.ingest(_event("operation_completed", 40, result, operation_id="official"))
    reducer.ingest(
        _event(
            "campaign_concluded",
            41,
            {
                "status": result["status"],
                "reason": result["summary"],
                "next": "End the campaign.",
            },
            operation_id="official",
        )
    )
    reducer.ingest(
        _event(
            "campaign_usage",
            42,
            {"totals": {"aiu": 35.33}, "text": "56m20s | 35.33 AIU | prompt 9.3m"},
            operation_id="official",
        )
    )
    return reducer


def test_a_failed_official_assessment_is_visible_with_its_figures():
    reducer = _official_run(passed=False)
    roots, _ = reducer.view()
    # The group sits last, where the events happened, and is open.
    assert [root.item_id for root in roots] == ["session:S12", "operation:official"]
    official = roots[-1]
    assert official.default_expanded and official.title.endswith("T4:checkpoint-95232")
    assert official.severity == "error" and official.status == "failed"
    assert "97.5% over 200 episodes" in official.summary
    assert "0.5 points below the 98.0% required" in official.summary
    rows = {child.title: child for child in official.children}
    assert rows["goal not reached"].severity == "error"
    assert "Required: 98.0%" in rows["goal not reached"].detail
    concluded = next(
        c for c in official.children if c.title.startswith("campaign concluded")
    )
    assert (
        concluded.title == "campaign concluded | failed"
        and concluded.severity == "error"
    )
    assert any(child.kind == "usage" for child in official.children)
    # The PI's request stays in the session that made it, not in a pinned group.
    session = roots[0]
    assert [c.title for c in session.children if c.title == "campaign concluded"]
    assert not [root for root in roots if root.item_id == "campaign:root"]


def test_a_passed_official_assessment_reads_as_a_success():
    roots, _ = _official_run(passed=True).view()
    official = roots[-1]
    assert official.severity == "info" and official.status == "passed"
    assert official.summary.startswith("passed | goal reached | 98.5%")
    assert "0.5 points above the 98.0% required" in official.summary
    result = next(c for c in official.children if c.title == "goal reached")
    assert result.kind == "result" and result.severity == "info"


def test_an_official_result_without_figures_still_shows_its_summary():
    roots, _ = _official_run(passed=False, figures=False).view()
    official = roots[-1]
    assert official.summary == "failed | goal not reached; success 97.5%"


def test_campaign_usage_shows_the_aiu_change_in_the_session_that_wrote_it():
    reducer = TimelineReducer()
    for number, (session, aiu) in enumerate((("S2", 4.15), ("S4", 8.79))):
        reducer.ingest(
            _event("session_started", number * 10, {"id": session}, session_id=session)
        )
        reducer.ingest(
            _event(
                "campaign_usage",
                number * 10 + 5,
                {
                    "totals": {"aiu": aiu},
                    "text": f"7m12s | {aiu:.2f} AIU | prompt 567k",
                },
                session_id=session,
                operation_id=f"session:{session}",
            )
        )
    roots, _ = reducer.view()
    first, second = (
        next(c for c in root.children if c.kind == "usage") for root in roots
    )
    assert first.summary == "7m12s | 4.15 AIU | prompt 567k"
    assert second.summary == "7m12s | 8.79 AIU (+4.64) | prompt 567k"


def test_a_run_state_adds_no_row_but_still_drives_the_now_line():
    reducer = TimelineReducer()
    reducer.ingest(_event("campaign_started", 0, {"summary": "goal"}))
    reducer.ingest(_event("run_state", 5, {"state": "executing"}, session_id="S1"))
    roots, _ = reducer.view()
    assert [child.title for child in roots[0].children] == ["campaign started"]
    assert reducer.now_text == "Now: executing"


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


def test_a_resumed_operation_is_running_again_and_a_completed_one_is_not_a_warning():
    reducer = TimelineReducer()
    ids = {"session_id": "S1", "operation_id": "T1"}
    reducer.ingest(_event("operation_requested", 0, {"kind": "training"}, **ids))
    reducer.ingest(_event("operation_started", 1, {"kind": "training"}, **ids))
    reducer.ingest(
        _event(
            "operation_completed",
            5,
            {"kind": "training", "status": "interrupted"},
            severity="warning",
            **ids,
        )
    )
    assert reducer.phase() != "training"
    # The resumed execution reports itself with a run state, not a second start.
    reducer.ingest(_event("run_state", 9, {"state": "executing"}, **ids))
    assert reducer.phase() == "training"
    assert _find(reducer, "operation:T1")[0].status == "running"
    reducer.ingest(
        _event(
            "operation_completed",
            20,
            {"kind": "training", "status": "completed"},
            **ids,
        )
    )
    item = _find(reducer, "operation:T1")[0]
    assert item.status == "completed"
    assert item.severity == "info"
    assert reducer.phase() != "training"


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
