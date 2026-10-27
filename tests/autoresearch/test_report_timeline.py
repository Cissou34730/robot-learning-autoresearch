"""Reducer and typed-feed tests for the structured operator log."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from tui.demo import demo_clock, demo_records, demo_state, demo_usage_rows
from tui.events import TypedJsonlFeed, synthesize_history
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


def test_tool_path_shortening_is_per_campaign_and_survives_clear(tmp_path):
    for slot in (2, 5):
        root = tmp_path / f"campaign-{slot}"
        path = root / "robot_learning" / "train.py"
        reducer = TimelineReducer(root)
        for _ in range(2):
            reducer.ingest(
                Observation(
                    "tool_call_started",
                    None,
                    {
                        "tool_call_id": "read",
                        "name": "view",
                        "arguments": {"path": str(path)},
                    },
                )
            )
            item = next(
                item for item in _walk(reducer.view()[0]) if item.kind == "tool"
            )
            assert str(root) not in item.summary
            assert "train.py" in item.summary
            assert item.payload["arguments"]["path"] == str(path)
            reducer.clear()


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
            ts=start + timedelta(seconds=30),
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
    assert progress[1].ts == start + timedelta(seconds=30)
    assert "+30s" in progress[1].title
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


def _event(kind, ts, fields=None, **identity):
    return Observation(kind=kind, ts=ts, fields=fields or {}, **identity)


def test_frequent_progress_samples_share_one_row_per_interval():
    reducer = TimelineReducer()
    start = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    for seconds in range(0, 61, 2):
        reducer.ingest(
            Observation(
                kind="training_progress",
                ts=start + timedelta(seconds=seconds),
                fields={"operation_id": "T9", "steps": 1000 + seconds, "target": 9999},
            )
        )
    for seconds in range(0, 31, 2):
        reducer.ingest(
            Observation(
                kind="eval_progress",
                ts=start + timedelta(seconds=seconds),
                fields={
                    "operation_id": "M9",
                    "episodes": seconds,
                    "episodes_total": 99,
                },
            )
        )
    roots, _ = reducer.view()
    items = {item.item_id: item for item in _walk(roots)}
    training = [
        c for c in items["operation:T9"].children if c.kind == "training_progress"
    ]
    evaluation = [
        c for c in items["operation:M9"].children if c.kind == "eval_progress"
    ]
    assert [row.ts for row in training] == [
        start,
        start + timedelta(seconds=30),
        start + timedelta(seconds=60),
    ]
    assert [row.ts for row in evaluation] == [start, start + timedelta(seconds=16)]
    assert "1,060" in training[-1].title


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


def test_tool_rows_shorten_campaign_paths_but_keep_full_arguments(tmp_path):
    reducer = TimelineReducer(tmp_path)
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


def test_phase_follows_the_active_work():
    reducer = TimelineReducer()
    start = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    assert reducer.phase() == "none"
    reducer.ingest(
        _event(
            "session_start", start, {"stage": "campaign preparation"}, session_id="u1"
        )
    )
    assert reducer.phase() == "preparing"
    reducer.ingest(
        _event(
            "session_started", start, {"id": "S1", "kind": "startup"}, session_id="S1"
        )
    )
    assert reducer.phase() == "pi"
    reducer.ingest(
        _event(
            "coding", start, {"phase": "request", "status": "started"}, session_id="S1"
        )
    )
    assert reducer.phase() == "coding"
    reducer.ingest(
        _event(
            "coding", start, {"phase": "result", "status": "completed"}, session_id="S1"
        )
    )
    assert reducer.phase() == "pi"
    reducer.ingest(
        _event(
            "operation_started",
            start,
            {"kind": "training"},
            operation_id="T1",
            session_id="S1",
        )
    )
    assert reducer.phase() == "training"
    reducer.ingest(
        _event(
            "operation_completed",
            start,
            {"kind": "training"},
            operation_id="T1",
            session_id="S1",
        )
    )
    reducer.ingest(
        _event(
            "eval_progress",
            start,
            {"operation_id": "M1", "episodes": 1},
            operation_id="M1",
            session_id="S1",
        )
    )
    assert reducer.phase() == "evaluating"
    reducer.ingest(
        _event(
            "operation_completed",
            start,
            {"kind": "measurement"},
            operation_id="M1",
            session_id="S1",
        )
    )
    reducer.ingest(_event("session_ended", start, {"summary": "done"}, session_id="S1"))
    assert reducer.phase() == "none"


def test_backend_session_id_is_an_alias_of_the_scientific_session():
    reducer = TimelineReducer()
    start = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    prep, backend = "70b0166d", "994f0144"
    reducer.ingest(
        _event(
            "session_start",
            start,
            {"stage": "campaign preparation"},
            session_id=prep,
        )
    )
    reducer.ingest(_event("pi_message", start, {"text": "prep"}, session_id=prep))
    reducer.ingest(
        _event(
            "session_started",
            start + timedelta(seconds=10),
            {"id": "S1", "kind": "startup"},
            session_id="S1",
        )
    )
    reducer.ingest(
        _event(
            "session_start",
            start + timedelta(seconds=14),
            {"stage": "S1 startup"},
            session_id=backend,
        )
    )
    reducer.ingest(
        _event(
            "pi_message",
            start + timedelta(seconds=20),
            {"text": "hi"},
            session_id=backend,
        )
    )
    reducer.ingest(
        _event(
            "tool_call_started",
            start + timedelta(seconds=21),
            {"tool_call_id": "t", "name": "view", "arguments": {}},
            session_id=backend,
        )
    )
    reducer.ingest(
        _event(
            "operation_started",
            start + timedelta(seconds=30),
            {"kind": "training"},
            operation_id="T1",
            session_id="S1",
        )
    )
    roots, _ = reducer.view()
    sessions = [item for item in roots if item.kind == "session"]
    assert [item.title for item in sessions] == ["Campaign preparation", "S1 startup"]
    scientific = sessions[1]
    kinds = {child.kind for child in scientific.children}
    assert {"pi", "tool", "training"} <= kinds
    assert not any(item.item_id.endswith(backend) for item in _walk(roots))


def test_snapshot_ids_register_the_alias_before_the_pi_events():
    reducer = TimelineReducer()
    start = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    reducer.ingest(
        Observation(
            "session_start",
            None,
            {"id": "S2", "backend_session_id": "abc", "kind": "experiment"},
            event_id="history:session:S2",
            session_id="S2",
        )
    )
    reducer.ingest(_event("pi_message", start, {"text": "hello"}, session_id="abc"))
    roots, _ = reducer.view()
    assert [item.item_id for item in roots if item.kind == "session"] == ["session:S2"]


def test_goal_review_and_publication_recovery_sit_in_their_session():
    reducer = TimelineReducer()
    start = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    for session in ("S1", "S2"):
        reducer.ingest(
            _event("session_started", start, {"id": session}, session_id=session)
        )
    reducer.ingest(
        _event(
            "campaign_goal_review",
            start + timedelta(seconds=5),
            {"summary": "inquiries 0/15"},
            session_id="S1",
        )
    )
    reducer.ingest(_event("publication_recovered", start, {"retry": 1}))
    reducer.ingest(_event("run_state", start, {"state": "executing"}))
    reducer.ingest(_event("campaign_concluded", start, {"status": "done"}))
    roots, _ = reducer.view()
    items = {item.item_id: item for item in _walk(roots)}
    first, second = items["session:S1"], items["session:S2"]
    campaign = items["campaign:root"]
    assert [c.title for c in first.children if c.title == "campaign goal review"]
    assert [c.title for c in second.children if c.title == "publication recovered"]
    kept = {child.title for child in campaign.children}
    assert {"run state executing", "campaign concluded"} <= kept
    assert not kept & {"campaign goal review", "publication recovered"}


def test_closed_sessions_are_folded_until_opened():
    reducer = TimelineReducer()
    start = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    for session in ("S1", "S2"):
        reducer.ingest(
            _event("session_started", start, {"id": session}, session_id=session)
        )
        for number in range(3):
            reducer.ingest(
                _event(
                    "checkpoint_saved",
                    start + timedelta(seconds=number),
                    {"current_synthesis": f"{session} step {number}"},
                    session_id=session,
                )
            )
        if session == "S1":
            reducer.ingest(
                _event("session_ended", start, {"summary": "done"}, session_id="S1")
            )
    unfolded, total = reducer.view()
    closed = next(item for item in unfolded if item.item_id == "session:S1")
    assert closed.children and closed.lazy == 0

    folded, folded_total = reducer.view(open_ids=set())
    shut = next(item for item in folded if item.item_id == "session:S1")
    live = next(item for item in folded if item.item_id == "session:S2")
    assert shut.children == [] and shut.lazy == len(closed.children) + sum(
        len(child.children) for child in closed.children
    )
    assert live.children and live.lazy == 0
    assert folded_total == total

    opened, _ = reducer.view(open_ids={"session:S1"})
    assert next(i for i in opened if i.item_id == "session:S1").children


def test_running_tool_summaries_stop_when_the_tool_completes():
    reducer = TimelineReducer()
    start = datetime.now(tz=UTC) - timedelta(seconds=90)
    reducer.ingest(
        _event(
            "tool_call_started",
            start,
            {"tool_call_id": "t1", "name": "submit_operation", "arguments": {}},
        )
    )
    summaries = reducer.live_summaries()
    assert list(summaries) == ["tool:t1"]
    assert "1m30s" in summaries["tool:t1"]
    reducer.ingest(
        _event(
            "tool_call_completed",
            start + timedelta(seconds=95),
            {"tool_call_id": "t1", "name": "submit_operation", "status": "completed"},
        )
    )
    assert reducer.live_summaries() == {}


def test_liveness_does_not_change_the_timeline_version():
    reducer = TimelineReducer()
    before = reducer.version
    reducer.ingest(_event("liveness", datetime(2026, 10, 24, 12, 0, tzinfo=UTC)))
    assert reducer.version == before
    reducer.ingest(_event("checkpoint_saved", None, {"current_synthesis": "x"}))
    assert reducer.version != before


def test_usage_record_updates_in_place_as_rows_change():
    usage_rows = [{"role": "pi", "model": "m1"}]
    state = {"campaign": {"id": "C1"}}
    reducer = TimelineReducer()
    first = synthesize_history(state, [], usage_rows)
    second = synthesize_history(state, [], [*usage_rows, {"role": "pi", "model": "m2"}])
    assert synthesize_history(state, [], usage_rows)[-1].event_id == first[-1].event_id
    assert second[-1].event_id != first[-1].event_id
    for event in (*first, *second):
        reducer.ingest(event)
    roots, _ = reducer.view()
    records = [item for item in _walk(roots) if item.title == "usage recorded"]
    assert len(records) == 1
    assert records[0].summary == "2 accounting rows"
    assert "m2" in records[0].detail[0]


def test_each_fact_shows_once_in_time_order_whatever_the_source_or_arrival():
    reducer = TimelineReducer()
    start = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    opened = {"question": "Does it reach?"}
    identity = {"session_id": "S1", "inquiry_id": "I1"}
    # Live copy first, then the durable record and the state snapshot.
    reducer.ingest(
        _event("inquiry_opened", start + timedelta(seconds=5), opened, **identity)
    )
    reducer.ingest(
        Observation(
            "inquiry_opened",
            start,
            opened,
            event_id="history:record:I1",
            **identity,
        )
    )
    reducer.ingest(
        Observation(
            "inquiry_opened",
            None,
            opened,
            event_id="history:inquiry:I1",
            **identity,
        )
    )
    # A later operation event arrives before an earlier one.
    for kind, offset in (("operation_completed", 60), ("operation_started", 10)):
        reducer.ingest(
            _event(
                kind,
                start + timedelta(seconds=offset),
                {"kind": "training"},
                operation_id="T1",
                **identity,
            )
        )
    reducer.ingest(
        Observation(
            "operation_completed",
            start + timedelta(seconds=61),
            {"kind": "training"},
            event_id="history:record:T1",
            operation_id="T1",
            **identity,
        )
    )
    reducer.ingest(
        _event(
            "scientific_model_validated",
            start + timedelta(seconds=90),
            {"commit": "34159d3f", "path": "pi_workspace/scientific_model.md"},
        )
    )
    roots, _ = reducer.view()
    items = list(_walk(roots))
    inquiry = next(item for item in items if item.item_id == "inquiry:I1")
    opened_leaves = [c for c in inquiry.children if c.title == "inquiry opened"]
    assert len(opened_leaves) == 1
    assert opened_leaves[0].ts == start + timedelta(seconds=5)
    assert inquiry.default_expanded
    operation = next(item for item in items if item.item_id == "operation:T1")
    assert [child.title for child in operation.children] == ["started", "completed"]
    validated = next(
        item for item in items if item.title.startswith("scientific model")
    )
    assert "34159d3f" not in validated.summary + "".join(validated.detail)
    assert validated.payload["commit"] == "34159d3f"
    assert validated in next(i for i in items if i.item_id == "session:S1").children
