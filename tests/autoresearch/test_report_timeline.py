"""Reducer and typed-feed tests for the structured operator log."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from tui.demo import demo_clock, demo_records, demo_state, demo_usage_rows
from tui.events import CampaignEventFeed, TypedJsonlFeed, synthesize_history
from tui.observations import Observation
from tui.timeline import TimelineReducer


def _demo_reducer() -> TimelineReducer:
    started, _, now = demo_clock()
    reducer = TimelineReducer()
    for event in synthesize_history(
        demo_state(now, started),
        demo_records(now),
        demo_usage_rows(now),
    ):
        reducer.ingest(event)
    return reducer


def _walk(items):
    for item in items:
        yield item
        yield from _walk(item.children)


def test_history_groups_sessions_inquiries_and_operations():
    reducer = _demo_reducer()
    roots, _ = reducer.view()
    items = list(_walk(roots))
    kinds = {item.kind for item in items}
    assert "campaign" in kinds
    assert "session" in kinds
    assert "inquiry" in kinds
    assert "training" in kinds
    assert "measurement" in kinds
    session = next(item for item in items if item.item_id == "session:S7")
    inquiry = next(item for item in items if item.item_id == "inquiry:I3")
    assert session.is_group and inquiry.is_group
    assert inquiry in session.children


def test_default_collapse_is_the_active_chain_only():
    reducer = _demo_reducer()
    roots, _ = reducer.view()
    items = list(_walk(roots))
    campaign = next(item for item in items if item.item_id == "campaign:root")
    old_session = next(item for item in items if item.item_id == "session:S6")
    active_session = next(item for item in items if item.item_id == "session:S7")
    assert campaign.default_expanded is False
    assert old_session.default_expanded is False
    assert active_session.item_id in reducer.active_ids()


def test_now_line_names_the_pending_operation():
    reducer = _demo_reducer()
    assert reducer.now_text.startswith("Now: I3 / S7 / M6 measurement")
    assert "requested" in reducer.now_text


def test_search_keeps_ancestors_and_counts_matches():
    reducer = _demo_reducer()
    roots, matches = reducer.view(query="measurement")
    assert matches >= 1
    items = list(_walk(roots))
    assert any(item.kind == "measurement" for item in items)
    assert any(item.kind == "inquiry" for item in items)


def test_kind_filter_keeps_the_hierarchy():
    reducer = _demo_reducer()
    roots, _ = reducer.view(categories={"training"})
    items = list(_walk(roots))
    assert any(item.kind == "training" for item in items)
    assert not any(item.kind == "pi" for item in items)


def test_pi_partials_update_one_item():
    reducer = TimelineReducer()
    now = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    for text, final in (
        ("Zebra delta one ", False),
        ("two. ", False),
        ("Zebra delta one two. Quokka final.", True),
    ):
        reducer.ingest(
            Observation(
                kind="pi_message",
                ts=now,
                fields={"text": text, "final": final, "turn": 7},
            )
        )
    roots, _ = reducer.view()
    pis = [item for item in _walk(roots) if item.kind == "pi"]
    assert len(pis) == 1
    assert pis[0].summary == "Zebra delta one two. Quokka final."


def test_training_progress_keeps_timestamp_and_interval():
    reducer = TimelineReducer()
    start = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    reducer.ingest(
        Observation(
            kind="training_progress",
            ts=start,
            fields={
                "operation_id": "T9",
                "steps": 1000,
                "target": 10000,
                "ep_rew_mean": 10.0,
                "training_success": 0.5,
            },
        )
    )
    reducer.ingest(
        Observation(
            kind="training_progress",
            ts=start + timedelta(seconds=15),
            fields={
                "operation_id": "T9",
                "steps": 2000,
                "target": 10000,
                "ep_rew_mean": 11.0,
                "training_success": 0.6,
            },
        )
    )
    roots, _ = reducer.view()
    operation = next(item for item in _walk(roots) if item.item_id == "operation:T9")
    progress = [
        child for child in operation.children if child.kind == "training_progress"
    ]
    assert len(progress) == 2
    assert progress[1].ts == start + timedelta(seconds=15)
    assert "+15s" in progress[1].title
    assert "reward 11.0" in progress[1].title
    assert "success 60%" in progress[1].title


def test_unknown_event_renders_generically():
    reducer = TimelineReducer()
    reducer.ingest(
        Observation(
            kind="custom_fact",
            ts=datetime(2026, 10, 24, 12, 0, tzinfo=UTC),
            fields={"alpha": "beta", "count": 3},
        )
    )
    roots, _ = reducer.view()
    items = list(_walk(roots))
    assert any(item.kind == "log" and item.title == "custom fact" for item in items)


def test_typed_feed_parses_envelope_and_rejects_schema(tmp_path):
    path = tmp_path / "campaign.events.jsonl"
    record = {
        "schema_version": 1,
        "event_id": "evt-1",
        "campaign_id": "campaign-1",
        "ts": "2026-10-24T12:00:00+00:00",
        "kind": "training_progress",
        "scope": "training",
        "severity": "info",
        "operation_id": "T4",
        "payload": {"steps": 10, "target": 20},
    }
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    feed = TypedJsonlFeed(path, campaign_id="campaign-1")
    (event,) = feed.poll()
    assert event.kind == "training_progress"
    assert event.event_id == "evt-1"
    assert event.operation_id == "T4"
    assert event.fields == {"steps": 10, "target": 20}

    path.write_text(
        json.dumps({**record, "schema_version": 99}) + "\n", encoding="utf-8"
    )
    feed = TypedJsonlFeed(path, campaign_id="campaign-1")
    assert feed.poll() == []
    assert feed.rejected == "unsupported typed event schema"


def test_campaign_feed_prefers_typed_file(tmp_path):
    typed = tmp_path / "campaign.events.jsonl"
    legacy = tmp_path / "campaign.jsonl"
    legacy.write_text(
        json.dumps({"kind": "liveness", "ts": "2026-10-24T12:00:00+00:00"}) + "\n",
        encoding="utf-8",
    )
    typed.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "event_id": "evt-1",
                "campaign_id": "campaign-1",
                "ts": "2026-10-24T12:00:01+00:00",
                "kind": "run_state",
                "payload": {"state": "executing"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    feed = CampaignEventFeed(typed, legacy, campaign_id="campaign-1")
    events = feed.poll()
    assert len(events) == 1
    assert events[0].kind == "run_state"
    assert feed.path == typed
