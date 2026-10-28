"""The real panel against a journal written by the real writer.

A synthetic campaign is published through ``runner.typed_events`` the way the
Runner and the launcher publish it (strict contract), then followed by the real
panel in several chunk sizes. The rules are about the tree the operator sees,
not about one reducer function.
"""

import asyncio
import json

import pytest

from runner import typed_events
from runner.event_contract import PREPARATION_SESSION
from tui.demo import demo_snapshot_args
from tui.journal import JournalFeed
from tui.report import CampaignReport, DemoSources
from tui.timeline import TimelineReducer

# The panel follows only the campaign its durable state names.
CAMPAIGN = demo_snapshot_args()[0]["campaign"]["id"]


def _emit(kind, payload=None, **identity):
    typed_events.emit(kind, payload or {}, **identity)


def publish_campaign() -> None:
    """Preparation with two PI attempts, S1 and S2 sharing inquiry I1, a coder
    child, a step no component knew before, and the official assessment."""
    _emit("campaign_started", {"summary": "goal-centered research"}, scope="campaign")
    with typed_events.context(session_id=PREPARATION_SESSION):
        _emit("notice", {"text": "START | campaign preparation"}, actor="launcher")
        for attempt in ("prep-1", "prep-2"):
            _emit(
                "session_start",
                {"stage": "campaign preparation"},
                attempt=attempt,
                actor="pi",
            )
            with typed_events.context(attempt=attempt, actor="pi"):
                _emit("pi_message", {"text": f"model draft {attempt}", "final": True})
        _emit("scientific_model_validated", {"commit": "abc"}, actor="runner")

    for session, inquiry, operations in (
        ("S1", "I1", ("T1", "M1")),
        ("S2", "I1", ("M2",)),
    ):
        _emit(
            "session_started",
            {"id": session, "kind": "inquiry"},
            session_id=session,
            actor="runner",
        )
        with typed_events.context(session_id=session):
            _emit(
                "session_start",
                {"backend_session_id": f"uuid-{session}"},
                attempt=f"inv-{session}",
                actor="pi",
            )
            with typed_events.context(attempt=f"inv-{session}", actor="pi"):
                _emit("pi_message", {"text": f"{session} reasoning", "final": True})
                _emit("tool_call_started", {"name": "view", "tool_call_id": "c1"})
            _emit(
                "inquiry_opened",
                {"inquiry_id": inquiry, "question": "Does it reach the target?"},
                inquiry_id=inquiry,
                operation_id=f"Q-{session}",
            )
            for operation in operations:
                kind = "training" if operation.startswith("T") else "measurement"
                with typed_events.context(
                    operation_id=operation, inquiry_id=inquiry, actor="runner"
                ):
                    _emit("operation_requested", {"kind": kind}, scope=kind)
                    _emit("operation_started", {"kind": kind}, scope=kind)
                    if kind == "training":
                        _emit(
                            "training_progress",
                            {"steps": 10, "target": 100},
                            scope="training",
                        )
                    else:
                        _emit(
                            "eval_progress",
                            {"episodes": 5, "episodes_total": 10},
                            scope="measurement",
                        )
                    _emit(
                        "operation_completed",
                        {"kind": kind, "status": "completed"},
                        scope=kind,
                    )
            _emit(
                "usage_update",
                {"role": "coder", "input_tokens": 3},
                scope="usage",
                attempt=f"inv-{session}",
                actor="coder",
            )
            _emit(
                "calibration_step",
                {"text": "a step added after the TUI was written"},
                actor="runner",
            )
            _emit("session_ended", {"summary": "checkpoint"}, actor="runner")

    with typed_events.context(operation_id="official", actor="runner"):
        _emit("operation_started", {"kind": "measurement"}, scope="measurement")
        _emit(
            "eval_progress",
            {"episodes": 3, "episodes_total": 10, "official": True},
            scope="measurement",
        )
        _emit(
            "operation_completed",
            {"kind": "measurement", "status": "failed"},
            scope="measurement",
        )
        _emit("campaign_concluded", {"status": "failed"}, scope="campaign")


@pytest.fixture
def journal(monkeypatch, tmp_path):
    path = tmp_path / f"{CAMPAIGN}.events.v2.jsonl"
    typed_events.reset()
    monkeypatch.setenv("TUI_TYPED_EVENTS", str(path))
    monkeypatch.setattr(typed_events, "strict", True)
    typed_events.set_campaign(CAMPAIGN)
    publish_campaign()
    typed_events.reset()
    return path


def signature(items, parent=""):
    rows = []
    for item in items:
        # A running row's summary carries a live clock; it is not part of the fold.
        summary = item.summary
        if summary.startswith("running"):
            summary = "running"
        rows.append((parent, item.item_id, item.kind, item.title, summary, item.ts))
        rows.extend(signature(item.children, item.item_id))
    return rows


def walk(items):
    for item in items:
        yield item
        yield from walk(item.children)


def fold(path):
    reducer = TimelineReducer()
    for event in JournalFeed(path).poll():
        reducer.ingest(event)
    return reducer.view()[0]


async def follow(path, tmp_path, chunk):
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    live = tmp_path / f"live-{chunk}.events.v2.jsonl"
    app = CampaignReport(demo=False, sources=DemoSources(), events_path=live)
    async with app.run_test(size=(170, 50)) as pilot:
        await pilot.pause()
        for start in range(0, len(lines), chunk):
            with live.open("a", encoding="utf-8") as handle:
                handle.write("".join(lines[start : start + chunk]))
            app._master_tick()
            await pilot.pause()
        app._master_tick()
        await pilot.pause()
        roots, _ = app._timeline.view()
        return signature(roots), roots


def panel_tree(path, tmp_path, chunk):
    return asyncio.run(follow(path, tmp_path, chunk))


def test_every_event_of_the_scenario_obeys_the_contract(journal):
    from runner.event_contract import validate_record

    records = [json.loads(line) for line in journal.read_text("utf-8").splitlines()]
    assert len(records) > 30
    assert not [r["kind"] for r in records if validate_record(r)]


def test_the_panel_shows_one_owner_per_fact(journal, tmp_path):
    _, roots = panel_tree(journal, tmp_path, chunk=7)
    sessions = [item for item in roots if item.item_id.startswith("session:")]
    keys = [item.item_id for item in sessions]
    # One group per session, the preparation once for its two attempts.
    assert keys == [
        f"session:{PREPARATION_SESSION}",
        "session:S1",
        "session:S2",
    ]
    stamps = [item.ts for item in sessions]
    assert stamps == sorted(stamps)

    def operations_under(item):
        return {
            child.item_id.split(":")[-1]
            for child in walk(item.children)
            if child.item_id.startswith("operation:")
        }

    by_session = {item.item_id: operations_under(item) for item in sessions}
    assert by_session["session:S1"] == {"T1", "M1"}
    assert by_session["session:S2"] == {"M2"}
    assert not by_session[f"session:{PREPARATION_SESSION}"]
    campaign = next(item for item in roots if not item.item_id.startswith("session:"))
    assert operations_under(campaign) == {"official"}
    prep = next(item for item in sessions if item.item_id.endswith(PREPARATION_SESSION))
    drafts = [
        child.summary
        for child in walk(prep.children)
        if child.kind == "pi" and "model draft" in child.summary
    ]
    assert sorted(drafts) == ["model draft prep-1", "model draft prep-2"]


def test_every_row_has_a_time_and_a_unique_identity(journal, tmp_path):
    _, roots = panel_tree(journal, tmp_path, chunk=11)
    rows = list(walk(roots))
    # The Campaign group is a pinned header; every event row has a time.
    assert [
        row.item_id for row in rows if row.ts is None and row.item_id != "campaign:root"
    ] == []
    identities = [row.item_id for row in rows]
    assert len(identities) == len(set(identities))


def test_a_step_unknown_to_the_panel_still_renders_under_its_session(journal, tmp_path):
    _, roots = panel_tree(journal, tmp_path, chunk=500)
    session = next(item for item in roots if item.item_id == "session:S2")
    assert any(
        "after the TUI was written" in " ".join((row.summary, *row.detail))
        for row in walk(session.children)
    )


def test_the_panel_equals_a_fresh_fold_whatever_the_chunking(journal, tmp_path):
    expected = signature(fold(journal))
    assert signature(fold(journal)) == expected
    for chunk in (1, 13, 500):
        live, _ = panel_tree(journal, tmp_path, chunk)
        assert live == expected


def test_an_incomplete_tail_waits_and_is_not_corruption(journal, tmp_path):
    lines = journal.read_text(encoding="utf-8").splitlines(keepends=True)
    live = tmp_path / "tail.events.v2.jsonl"
    live.write_text("".join(lines[:-1]) + lines[-1][:30], encoding="utf-8")
    feed = JournalFeed(live, campaign_id=CAMPAIGN)
    first = feed.poll()
    assert len(first) == len(lines) - 1 and feed.rejected is None
    with live.open("a", encoding="utf-8") as handle:
        handle.write(lines[-1][30:])
    assert len(feed.poll()) == 1 and feed.rejected is None
