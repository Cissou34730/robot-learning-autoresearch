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
                "elapsed_seconds": 10,
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
                "elapsed_seconds": 20,
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
    assert "Elapsed 20s" in progress[1].title
    assert "ETA 1m" in progress[1].title


def test_live_and_durable_candidate_announcements_share_one_non_repeated_label():
    reducer = TimelineReducer()
    candidate = "T1:checkpoint-65536"
    stamp = datetime(2026, 10, 26, 12, tzinfo=UTC)
    reducer.ingest(
        Observation(
            "candidate_created",
            None,
            {"candidate": candidate, "artifact": "checkpoint.zip"},
            event_id="history:candidate",
        )
    )
    reducer.ingest(
        Observation(
            "candidate_created",
            stamp,
            {"candidate": candidate, "training_steps": 65536},
            event_id="live:candidate",
        )
    )
    reducer.ingest(
        Observation(
            "candidate_created",
            None,
            {"candidate": candidate},
            event_id="history:again",
        )
    )
    candidates = [
        item
        for item in _walk(reducer.view()[0])
        if item.item_id == f"candidate:{candidate}"
    ]
    assert len(candidates) == 1
    item = candidates[0]
    assert (item.title + item.summary).count(candidate) == 1
    assert item.ts == stamp
    assert item.payload["artifact"] == "checkpoint.zip"
    assert item.payload["training_steps"] == 65536


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


def _event(kind, ts, fields=None, **identity):
    return Observation(kind=kind, ts=ts, fields=fields or {}, **identity)


def test_liveness_keeps_the_timeline_quiet():
    reducer = _demo_reducer()
    before = len(list(_walk(reducer.view()[0])))
    reducer.ingest(_event("liveness", datetime(2026, 10, 24, 12, 0, tzinfo=UTC)))
    assert len(list(_walk(reducer.view()[0]))) == before


def test_sliced_wait_is_informational_and_keeps_the_operation_active():
    reducer = TimelineReducer()
    start = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
    reducer.ingest(
        _event("operation_started", start, {"kind": "training"}, operation_id="T9")
    )
    reducer.ingest(
        _event(
            "operation_submitted",
            start + timedelta(minutes=25),
            {"status": "running", "error": ""},
            operation_id="T9",
        )
    )
    items = list(_walk(reducer.view()[0]))
    waiting = next(item for item in items if item.title == "submitted")
    operation = next(item for item in items if item.item_id == "operation:T9")
    assert waiting.severity == "info"
    assert waiting.summary == "running"
    assert operation.status == "running"
    assert "operation:T9" in reducer.active_ids()
    reducer.ingest(
        _event(
            "operation_completed",
            start + timedelta(minutes=30),
            {"kind": "training"},
            operation_id="T9",
        )
    )
    completed = next(
        item for item in _walk(reducer.view()[0]) if item.item_id == "operation:T9"
    )
    assert completed.status == "completed"
    assert "operation:T9" not in reducer.active_ids()


def test_tool_lifecycle_pairs_by_call_id_and_reports_duration():
    reducer = TimelineReducer()
    start = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    reducer.ingest(
        _event(
            "tool_call_started",
            start,
            {
                "name": "artifact_evidence_query",
                "tool_call_id": "call-1",
                "detail": "M6 artifact 0",
                "arguments": {"operation_id": "M6", "artifact_index": 0},
            },
        )
    )
    reducer.ingest(
        _event(
            "tool_call_completed",
            start + timedelta(seconds=3),
            {
                "name": "artifact_evidence_query",
                "tool_call_id": "call-1",
                "status": "completed",
                "result": {
                    "status": "computed",
                    "value": 3,
                    "trace": "x" * 1000 + "END_TOOL_RESULT",
                },
            },
        )
    )
    roots, _ = reducer.view()
    tools = [item for item in _walk(roots) if item.kind == "tool"]
    assert len(tools) == 1
    assert tools[0].status == "completed"
    assert "M6 artifact 0" in tools[0].summary
    assert "3s" in tools[0].summary
    assert tools[0].payload["arguments"]["operation_id"] == "M6"
    assert tools[0].payload["result"]["value"] == 3
    assert tools[0].payload["result"]["trace"].endswith("END_TOOL_RESULT")
    assert not any("END_TOOL_RESULT" in line for line in tools[0].detail)


def test_tool_rows_shorten_campaign_paths_but_keep_full_arguments(
    monkeypatch, tmp_path
):
    from runner import paths

    monkeypatch.setattr(paths, "ROOT", tmp_path)
    reducer = TimelineReducer()
    stamp = datetime(2026, 10, 26, 9, 8, 24, tzinfo=UTC)
    for name in ("environment.py", "observations.py"):
        path = str(tmp_path / "robot_learning" / "scenario" / name)
        reducer.ingest(
            _event(
                "tool_call_started",
                stamp,
                {
                    "name": "view",
                    "tool_call_id": name,
                    "detail": path,
                    "arguments": {"path": path},
                },
            )
        )
        reducer.ingest(
            _event(
                "tool_call_completed",
                stamp,
                {"name": "view", "tool_call_id": name, "status": "completed"},
            )
        )
    tools = [item for item in _walk(reducer.view()[0]) if item.kind == "tool"]
    assert len(tools) == 2
    for item, name in zip(tools, ("environment.py", "observations.py"), strict=True):
        assert name in item.summary
        assert "robot_learning" in item.summary
        assert str(tmp_path) not in item.summary
        assert item.payload["arguments"]["path"] == str(
            tmp_path / "robot_learning" / "scenario" / name
        )


def test_session_inquiry_and_checkpoint_domain_events_build_groups():
    reducer = TimelineReducer()
    start = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    reducer.ingest(
        _event(
            "session_started",
            start,
            {"id": "S8", "kind": "experiment", "objective": "Test the policy."},
            session_id="S8",
        )
    )
    reducer.ingest(
        _event(
            "inquiry_opened",
            start,
            {"question": "Does the policy reach the target?"},
            session_id="S8",
            inquiry_id="I4",
        )
    )
    reducer.ingest(
        _event("inquiry_reframed", start, {"question": "Reframed?"}, inquiry_id="I4")
    )
    reducer.ingest(
        _event("inquiry_closed", start, {"outcome": "Yes."}, inquiry_id="I4")
    )
    reducer.ingest(
        _event(
            "checkpoint_saved",
            start,
            {"current_synthesis": "It reaches the target."},
            session_id="S8",
        )
    )
    reducer.ingest(
        _event(
            "session_ended",
            start,
            {"summary": "It reaches the target.", "next_question": "At what speed?"},
            session_id="S8",
        )
    )
    roots, _ = reducer.view()
    items = list(_walk(roots))
    session = next(item for item in items if item.item_id == "session:S8")
    inquiry = next(item for item in items if item.item_id == "inquiry:I4")
    assert session.status == "closed"
    assert inquiry in session.children
    titles = [item.title for item in items]
    assert "started" in titles
    assert "inquiry reframed" in titles
    assert "inquiry closed" in titles
    assert "ended" in titles
    checkpoint = next(item for item in items if item.title == "checkpoint saved")
    assert checkpoint.kind == "checkpoint"
    assert "It reaches the target." in checkpoint.detail[0]


def test_panel_and_training_checkpoints_keep_console_numbers():
    reducer = TimelineReducer()
    start = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    reducer.ingest(
        _event(
            "measurement_panel_started",
            start,
            {
                "operation_id": "M9",
                "instrument": "official",
                "artifact": "candidate-a",
                "episodes": 100,
                "seed": 7,
            },
            operation_id="M9",
        )
    )
    reducer.ingest(
        _event(
            "measurement_panel_completed",
            start + timedelta(seconds=42),
            {
                "operation_id": "M9",
                "instrument": "official",
                "artifact": "candidate-a",
                "episodes": 100,
                "episodes_total": 100,
                "elapsed_seconds": 42.0,
                "success_percent": 97.5,
            },
            operation_id="M9",
        )
    )
    reducer.ingest(
        _event(
            "training_checkpoints",
            start,
            {
                "operation_id": "T9",
                "candidates": [
                    {
                        "candidate": "T9:checkpoint-1000",
                        "steps": 1000,
                        "ep_rew_mean": 12.5,
                        "summary": "reward 12.5 | success 75%",
                    },
                    {
                        "candidate": "T9:checkpoint-2000",
                        "steps": 2000,
                        "ep_rew_mean": 14.0,
                        "training_success": 0.8,
                    },
                ],
            },
            operation_id="T9",
        )
    )
    roots, _ = reducer.view()
    items = list(_walk(roots))
    panels = [item for item in items if item.title.startswith("panel complete")]
    assert panels
    assert "100 / 100" in panels[0].summary
    assert "97.5%" in panels[0].summary
    assert "42s" in panels[0].summary
    results = next(item for item in items if item.title == "training results")
    assert "reward 12.5 | success 75%" in results.detail[0]
    assert "2,000 steps" in results.detail[1]
    assert "reward 14.0" in results.detail[1]
    assert "success 80%" in results.detail[1]


def test_usage_and_publication_events_render_structured_numbers():
    reducer = TimelineReducer()
    start = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    reducer.ingest(
        _event(
            "usage_update",
            start,
            {
                "role": "pi",
                "model": "gpt-test",
                "duration_seconds": 90.0,
                "input_tokens": 12000,
                "output_tokens": 3000,
                "tool_calls": 5,
            },
            session_id="S8",
        )
    )
    reducer.ingest(
        _event(
            "campaign_usage",
            start,
            {
                "totals": {
                    "duration_seconds": 3600.0,
                    "input_tokens": 50000,
                    "output_tokens": 9000,
                    "aiu": 1.5,
                },
                "text": "1h00m | 1.50 AIU | prompt 50k | output 9k",
            },
        )
    )
    reducer.ingest(
        _event(
            "publication_retry",
            start,
            {"retry": 1, "limit": 3, "delay_seconds": 5, "error": "remote error"},
        )
    )
    roots, _ = reducer.view()
    items = list(_walk(roots))
    usage = next(item for item in items if item.title == "usage pi")
    assert "1m30s" in usage.summary
    assert "prompt 12,000" in usage.summary
    assert "5 tool calls" in usage.summary
    campaign_usage = next(item for item in items if item.title == "campaign usage")
    assert "1.50 AIU" in campaign_usage.summary
    retry = next(item for item in items if item.kind == "warning")
    assert retry.title == "publication retry"
    assert "remote error" in retry.detail[0]
