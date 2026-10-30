"""Reducer and journal-feed tests for the structured operator log."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from runner.event_contract import rule_for
from tui.demo import demo_schedule
from tui.journal import JournalFeed
from tui.observations import Observation
from tui.timeline import TimelineReducer


@pytest.mark.parametrize(
    ("kind", "category", "fields"),
    [
        ("pi_message", "pi", {"text": "reasoning"}),
        ("pi_context", "pi", {"input_tokens": 10}),
        ("file_changed", "tools", {"path": "train.py"}),
        ("checkpoint_saved", "roles", {"current_synthesis": "checkpoint"}),
        ("operation_failed", "warnings", {"kind": "training", "error": "failed"}),
    ],
)
def test_filters_use_source_and_display_classification(kind, category, fields):
    reducer = TimelineReducer()
    reducer.ingest(
        Observation(
            kind, None, fields, event_id="fact", session_id="S1", operation_id="T1"
        )
    )
    roots, matches = reducer.view(categories={category})
    leaves = [item for item in _walk(roots) if not item.is_group]
    assert len(leaves) == matches == 1


def test_group_search_respects_categories_and_counts_displayed_leaves():
    reducer = TimelineReducer()
    for kind, fields in (
        ("operation_started", {"kind": "training"}),
        ("pi_message", {"text": "unrelated"}),
    ):
        reducer.ingest(
            Observation(kind, None, fields, session_id="S1", operation_id="T1")
        )
    roots, matches = reducer.view(query="T1", categories={"training"})
    assert matches == 1
    assert all(item.kind != "pi" for item in _walk(roots))
    assert reducer.view(query="T1", categories={"warnings"}) == ([], 0)


@pytest.mark.parametrize(
    ("progress_kind", "operation_kind"),
    [
        ("measurement_panel_completed", "measurement"),
        ("eval_progress", "measurement"),
        ("operation_progress", "measurement"),
        ("training_progress", "training"),
    ],
)
def test_delayed_progress_does_not_reopen_completed_operation(
    progress_kind, operation_kind
):
    reducer = TimelineReducer()
    start = datetime(2026, 10, 24, tzinfo=UTC)
    for kind, seconds in (
        ("operation_started", 0),
        ("operation_completed", 20),
        (progress_kind, 10),
    ):
        reducer.ingest(
            Observation(
                kind,
                start + timedelta(seconds=seconds),
                {
                    "kind": operation_kind,
                    "episodes": 10,
                    "episodes_total": 10,
                    "steps": 10,
                    "target": 10,
                },
                session_id="S1",
                operation_id="M1",
            )
        )
    operation = next(
        item for item in _walk(reducer.view()[0]) if item.item_id == "operation:M1"
    )
    assert operation.status == "completed"
    assert reducer.phase() not in {"evaluating", "training"}
    assert operation.summary.startswith("completed")


def test_operation_placeholder_is_promoted_without_changing_owner():
    reducer = TimelineReducer()
    for kind, fields in (
        ("warning", {"message": "early reference"}),
        ("operation_started", {"kind": "training"}),
    ):
        reducer.ingest(
            Observation(kind, None, fields, session_id="S1", operation_id="T1")
        )
    operation = next(
        item for item in _walk(reducer.view()[0]) if item.item_id == "operation:T1"
    )
    assert operation.kind == "training"
    assert reducer.phase() == "training"


def test_distinct_event_ids_keep_distinct_rows_at_the_same_timestamp():
    reducer = TimelineReducer()
    for number in range(2):
        reducer.ingest(
            Observation(
                "operation_progress",
                None,
                {"kind": "training", "text": str(number)},
                event_id=f"fact-{number}",
                session_id="S1",
                operation_id="T1",
            )
        )
    leaves = [item for item in _walk(reducer.view()[0]) if not item.is_group]
    assert len({item.item_id for item in leaves}) == 2
    assert {item.event_id for item in leaves} == {"fact-0", "fact-1"}


def test_legacy_event_identity_includes_its_owner():
    reducer = TimelineReducer()
    for session in ("S1", "S2"):
        reducer.ingest(
            Observation("pi_message", None, {"text": "same"}, session_id=session)
        )
    assert sum(item.kind == "pi" for item in _walk(reducer.view()[0])) == 2


def _demo_reducer() -> TimelineReducer:
    reducer = TimelineReducer()
    for seconds, event in demo_schedule():
        if seconds == 0.0:
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
                    session_id="S1",
                )
            )
            item = next(
                item for item in _walk(reducer.view()[0]) if item.kind == "tool"
            )
            assert str(root) not in item.summary
            assert "train.py" in item.summary
            assert item.payload["arguments"]["path"] == str(path)
            reducer.clear()


def test_journal_groups_sessions_inquiries_and_operations():
    reducer = _demo_reducer()
    roots, _ = reducer.view()
    items = list(_walk(roots))
    kinds = {item.kind for item in items}
    assert "campaign" in kinds
    assert "session" in kinds
    assert "inquiry" in kinds
    assert "measurement" in kinds
    session = next(item for item in items if item.item_id == "session:S7")
    inquiry = next(item for item in items if item.item_id == "inquiry:S7:I3")
    assert session.is_group and inquiry.is_group
    assert inquiry in session.children
    closed = next(item for item in items if item.item_id == "session:S6")
    assert "operation:T4" in {item.item_id for item in _walk(closed.children)}


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
                session_id="S1",
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
            session_id="S1",
            operation_id="T9",
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
            session_id="S1",
            operation_id="T9",
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


def test_candidate_announcements_share_one_non_repeated_label():
    reducer = TimelineReducer()
    candidate = "T1:checkpoint-65536"
    stamp = datetime(2026, 10, 26, 12, tzinfo=UTC)
    reducer.ingest(
        Observation(
            "candidate_created",
            None,
            {"candidate": candidate, "artifact": "checkpoint.zip"},
            event_id="first:candidate",
        )
    )
    reducer.ingest(
        Observation(
            "candidate_created",
            stamp,
            {"candidate": candidate, "training_steps": 65536},
            event_id="later:candidate",
        )
    )
    reducer.ingest(
        Observation(
            "candidate_created",
            None,
            {"candidate": candidate},
            event_id="again:candidate",
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


def test_journal_feed_parses_the_v2_envelope_and_rejects_other_schemas(tmp_path):
    path = tmp_path / "campaign.events.v2.jsonl"
    record = {
        "schema_version": 2,
        "event_id": "evt-1",
        "campaign_id": "campaign-1",
        "ts": "2026-10-24T12:00:00+00:00",
        "kind": "training_progress",
        "scope": "training",
        "severity": "info",
        "session_id": "S2",
        "operation_id": "T4",
        "inquiry_id": "",
        "attempt": "att-1",
        "actor": "runner",
        "payload": {"steps": 10, "target": 20},
    }
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    feed = JournalFeed(path, campaign_id="campaign-1")
    (event,) = feed.poll()
    assert event.kind == "training_progress"
    assert event.event_id == "evt-1"
    assert (event.session_id, event.operation_id) == ("S2", "T4")
    assert (event.attempt, event.actor) == ("att-1", "runner")
    assert event.fields == {"steps": 10, "target": 20}

    path.write_text(
        json.dumps({**record, "schema_version": 1}) + "\n", encoding="utf-8"
    )
    feed = JournalFeed(path, campaign_id="campaign-1")
    assert feed.poll() == []
    assert feed.rejected == "unsupported journal schema"


def test_journal_feed_keeps_a_partial_tail_and_reports_a_broken_complete_line(tmp_path):
    path = tmp_path / "campaign.events.v2.jsonl"
    good = {
        "schema_version": 2,
        "event_id": "a",
        "campaign_id": "c",
        "ts": "2026-10-24T12:00:00+00:00",
        "kind": "notice",
        "payload": {},
    }
    line = json.dumps(good)
    path.write_text(line[:30], encoding="utf-8")
    feed = JournalFeed(path)
    assert feed.poll() == [] and feed.rejected is None
    path.write_text(line + "\n{not json}\n", encoding="utf-8")
    events = feed.poll()
    assert [event.event_id for event in events] == ["a"]
    assert feed.rejected == "a complete journal line could not be decoded"


def test_v2_replay_keeps_recipe_development_and_startup_as_distinct_sessions(
    tmp_path,
):
    path = tmp_path / "campaign.events.v2.jsonl"
    events = [
        ("session_started", "S4", "", {"kind": "recipe_development"}),
        ("operation_started", "S4", "T1", {"kind": "training"}),
        ("operation_completed", "S4", "T1", {"kind": "training"}),
        ("session_ended", "S4", "", {"kind": "recipe_development"}),
        ("session_started", "S5", "", {"kind": "startup"}),
        ("future_phase_metadata", "S5", "", {"campaign_phase": "startup"}),
        ("session_ended", "S5", "", {"kind": "startup"}),
        ("run_state", "", "", {"state": "paused", "campaign_phase": "research"}),
    ]
    path.write_text(
        "".join(
            json.dumps(
                {
                    "schema_version": 2,
                    "event_id": f"event-{index}",
                    "campaign_id": "phase-campaign",
                    "ts": f"2026-10-24T12:00:0{index}+00:00",
                    "kind": kind,
                    "session_id": session,
                    "operation_id": operation,
                    "payload": payload,
                }
            )
            + "\n"
            for index, (kind, session, operation, payload) in enumerate(events)
        ),
        encoding="utf-8",
    )
    feed = JournalFeed(path, campaign_id="phase-campaign")
    reducer = TimelineReducer()
    for event in feed.poll():
        reducer.ingest(event)
    assert feed.rejected is None
    assert not feed.poll()
    items = {item.item_id: item for item in _walk(reducer.view()[0])}
    recipe = items["session:S4"]
    startup = items["session:S5"]
    assert recipe.payload["kind"] == "recipe_development"
    assert startup.payload["kind"] == "startup"
    assert recipe.status == startup.status == "closed"
    assert "operation:T1" in {item.item_id for item in _walk(recipe.children)}
    assert "operation:T1" not in {item.item_id for item in _walk(startup.children)}
    assert any(item.event_kind == "future_phase_metadata" for item in items.values())
    assert not reducer.active_ids()
    assert reducer.phase() == "none"
    before = reducer.view()
    feed.reset()
    for event in feed.poll():
        reducer.ingest(event)
    assert reducer.view() == before


def _event(kind, ts, fields=None, **identity):
    """An event as the journal carries it. A kind that must name a session gets
    S1 unless the test names another."""
    if "session_id" in rule_for(kind).requires:
        identity.setdefault("session_id", "S1")
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
                session_id="S1",
                operation_id="T9",
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
                session_id="S1",
                operation_id="M9",
            )
        )
    roots, _ = reducer.view()
    items = {item.item_id: item for item in _walk(roots)}
    training = [c for c in items.values() if c.kind == "training_progress"]
    evaluation = [c for c in items.values() if c.kind == "eval_progress"]
    # Each row stands for its newest sample, so its time is that sample's time.
    assert [row.ts for row in training] == [
        start + timedelta(seconds=28),
        start + timedelta(seconds=58),
        start + timedelta(seconds=60),
    ]
    assert [row.ts for row in evaluation] == [
        start + timedelta(seconds=14),
        start + timedelta(seconds=30),
    ]
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
        _event(
            "operation_started",
            start,
            {"kind": "training"},
            session_id="S1",
            operation_id="T9",
        )
    )
    reducer.ingest(
        _event(
            "operation_submitted",
            start + timedelta(minutes=25),
            {"status": "running", "error": ""},
            session_id="S1",
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
            session_id="S1",
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
        _event(
            "inquiry_reframed",
            start,
            {"question": "Reframed?"},
            session_id="S8",
            inquiry_id="I4",
        )
    )
    reducer.ingest(
        _event(
            "inquiry_closed",
            start,
            {"outcome": "Yes."},
            session_id="S8",
            inquiry_id="I4",
        )
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
    inquiry = next(item for item in items if item.item_id == "inquiry:S8:I4")
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
    assert "reward 12.5 | success 75%" in results.children[0].summary
    assert "2,000 steps" in results.children[1].summary
    assert "reward 14" in results.children[1].summary
    assert "success 80%" in results.children[1].summary


def test_measurement_header_accumulates_unequal_panels_instead_of_resetting():
    reducer = TimelineReducer()
    start = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    identity = {"operation_id": "M7", "session_id": "S5", "inquiry_id": "I2"}
    request = {
        "measurement": {
            "measurements": [
                {"candidate": "parent", "episodes": 100},
                {"candidate": "candidate", "episodes": 400},
            ]
        }
    }
    events = [
        ("operation_requested", {"kind": "measurement", "request": request}),
        ("measurement_panel_started", {"instrument": "parent", "episodes": 100}),
        ("eval_progress", {"episodes": 100, "episodes_total": 100}),
        (
            "measurement_panel_completed",
            {"episodes": 100, "episodes_total": 100, "success_percent": 94.0},
        ),
        ("measurement_panel_started", {"instrument": "candidate", "episodes": 400}),
        ("eval_progress", {"episodes": 0, "episodes_total": 400}),
        ("eval_progress", {"episodes": 200, "episodes_total": 400}),
        (
            "measurement_panel_completed",
            {"episodes": 400, "episodes_total": 400, "success_percent": 97.0},
        ),
        ("operation_completed", {"kind": "measurement"}),
    ]
    expected = {
        0: "0 / 500",
        2: "100 / 500",
        4: "100 / 500",
        5: "100 / 500",
        6: "300 / 500",
        7: "500 / 500",
        8: "500 / 500",
    }
    for n, (kind, fields) in enumerate(events):
        reducer.ingest(_event(kind, start + timedelta(seconds=n), fields, **identity))
        if n in expected:
            operation = next(
                item
                for item in _walk(reducer.view()[0])
                if item.item_id == "operation:M7"
            )
            assert expected[n] in operation.summary
    assert "completed" in operation.summary and "100%" in operation.summary


def test_checkpoint_rows_show_metrics_without_opening_each_candidate():
    reducer = TimelineReducer()
    start = datetime(2026, 10, 24, 12, tzinfo=UTC)
    candidates = [
        {
            "candidate": "T3:checkpoint-10",
            "steps": 10,
            "ep_rew_mean": 0.0,
            "training_success": 0.0,
        },
        {
            "candidate": "T3:checkpoint-20",
            "steps": 20,
            "ep_rew_mean": 12.5,
            "summary": "reward 12.5 | success 75%",
        },
    ]
    reducer.ingest(
        _event(
            "training_checkpoints",
            start,
            {"candidates": candidates},
            session_id="S5",
            operation_id="T3",
        )
    )
    for candidate in candidates:
        reducer.ingest(
            _event(
                "candidate_created",
                start + timedelta(seconds=1),
                {
                    "candidate": candidate["candidate"],
                    "training_steps": candidate["steps"],
                },
                session_id="S5",
                operation_id="T3",
            )
        )
    rows = list(_walk(reducer.view()[0]))
    checkpoints = [item for item in rows if item.item_id.startswith("candidate:")]
    assert len(checkpoints) == 2
    assert (
        "reward 0" in checkpoints[0].summary and "success 0%" in checkpoints[0].summary
    )
    assert (
        "reward 12.5" in checkpoints[1].summary
        and "success 75%" in checkpoints[1].summary
    )
    results = next(item for item in rows if item.title == "training results")
    assert results.is_group and results.default_expanded
    assert checkpoints == results.children

    import asyncio

    from textual.app import App

    from tui.event_log import EventLog

    class _Host(App):
        def compose(self):
            yield EventLog({}, id="log")

    async def scenario():
        app = _Host()
        async with app.run_test(size=(120, 24)) as pilot:
            log = app.query_one("#log", EventLog)
            log.set_view(reducer.view()[0], active_ids={"session:S5", "operation:T3"})
            await pilot.pause()
            shown = [
                line.node.data for line in log._tree_lines if line.node.data is not None
            ]
            assert all(item in shown for item in checkpoints)
            for item in checkpoints:
                node = log._node_by_id[item.item_id]
                assert not node.is_expanded
                assert "reward" in str(node.label) and "success" in str(node.label)

    asyncio.run(scenario())


def test_measurement_counts_seeds_separately_and_does_not_recount_a_resumed_panel():
    reducer = TimelineReducer()
    start = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    identity = {"operation_id": "M1", "session_id": "S1"}
    request = {
        "measurement": {
            "measurements": [
                {"candidate": "same", "episodes": 100, "seed": 7},
                {"candidate": "same", "episodes": 100, "seed": 8},
            ]
        }
    }
    events = [
        ("operation_requested", {"kind": "measurement", "request": request}),
        (
            "measurement_panel_started",
            {"artifact": "same", "instrument": "panel", "episodes": 100, "seed": 7},
        ),
        ("eval_progress", {"episodes": 100, "episodes_total": 100}),
        (
            "measurement_panel_started",
            {"artifact": "same", "instrument": "panel", "episodes": 100, "seed": 7},
        ),
        ("measurement_panel_completed", {"episodes": 100, "episodes_total": 100}),
        (
            "measurement_panel_started",
            {"artifact": "same", "instrument": "panel", "episodes": 100, "seed": 8},
        ),
        ("eval_progress", {"episodes": 50, "episodes_total": 100}),
    ]
    for n, (kind, fields) in enumerate(events):
        reducer.ingest(_event(kind, start + timedelta(seconds=n), fields, **identity))
    operation = next(
        item for item in _walk(reducer.view()[0]) if item.item_id == "operation:M1"
    )
    assert "150 / 200 episodes" in operation.summary
    assert "75%" in operation.summary and "panel 2/2" in operation.summary


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


@pytest.mark.parametrize("session_kind", ["startup", "recipe_development"])
def test_phase_follows_the_active_work(session_kind):
    reducer = TimelineReducer()
    start = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    assert reducer.phase() == "none"
    reducer.ingest(
        _event(
            "session_start",
            start,
            {"stage": "campaign preparation"},
            session_id="preparation",
        )
    )
    assert reducer.phase() == "preparing"
    reducer.ingest(
        _event(
            "session_started",
            start,
            {"id": "S1", "kind": session_kind},
            session_id="S1",
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


def test_launch_attempt_preserves_recorded_session_kind_on_resume():
    reducer = TimelineReducer()
    start = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    for attempt in ("first", "resumed"):
        reducer.ingest(
            _event(
                "session_start",
                start,
                {"kind": "recipe_development", "resumed": attempt == "resumed"},
                session_id="S4",
                attempt=attempt,
            )
        )
    sessions = [item for item in reducer.view()[0] if item.kind == "session"]
    assert [item.item_id for item in sessions] == ["session:S4"]
    assert sessions[0].payload["kind"] == "recipe_development"
    assert {item.payload["resumed"] for item in sessions[0].children} == {False, True}
    assert reducer.active_ids() == {"session:S4"}
    assert reducer.phase() == "pi"


def test_pi_attempts_are_rows_of_their_durable_session():
    reducer = TimelineReducer()
    start = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    reducer.ingest(
        _event(
            "session_start",
            start,
            {"stage": "campaign preparation"},
            session_id="preparation",
            attempt="a-prep",
        )
    )
    reducer.ingest(
        _event(
            "pi_message",
            start,
            {"text": "prep"},
            session_id="preparation",
            attempt="a-prep",
        )
    )
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
            session_id="S1",
            attempt="a-1",
        )
    )
    reducer.ingest(
        _event(
            "pi_message",
            start + timedelta(seconds=20),
            {"text": "hi"},
            session_id="S1",
            attempt="a-1",
        )
    )
    reducer.ingest(
        _event(
            "tool_call_started",
            start + timedelta(seconds=21),
            {"tool_call_id": "t", "name": "view", "arguments": {}},
            session_id="S1",
            attempt="a-1",
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
    assert {"pi", "tool", "training"} <= {child.kind for child in scientific.children}
    attempts = [c for c in scientific.children if c.title == "PI started"]
    assert [row.summary for row in attempts] == ["S1 startup"]


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
    reducer.ingest(
        _event("publication_recovered", start, {"retry": 1}, session_id="S2")
    )
    reducer.ingest(_event("publication_recovered", start, {"retry": 2}))
    reducer.ingest(_event("run_state", start, {"state": "executing"}, session_id="S1"))
    reducer.ingest(_event("campaign_concluded", start, {"status": "done"}))
    roots, _ = reducer.view()
    items = {item.item_id: item for item in _walk(roots)}
    first = next(
        item
        for item in items.values()
        if item.kind == "session"
        and any(c.title == "campaign goal review" for c in item.children)
    )
    second = items["session:S2"]
    assert first.item_id.startswith("session:S1:continued:")
    campaign = items["campaign:root"]
    assert [c.title for c in first.children if c.title == "campaign goal review"]
    assert [c.title for c in second.children if c.title == "publication recovered"]
    kept = [child.title for child in campaign.children]
    # A recovery that names no session, and the campaign-level kinds, stay here.
    assert kept.count("publication recovered") == 1
    assert "campaign concluded" in kept
    # A run state only drives the "Now" line; it adds no row of its own.
    assert "run state executing" not in kept
    assert "campaign goal review" not in kept


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


def test_an_event_delivered_twice_shows_once_and_the_commit_stays_out_of_the_row():
    reducer = TimelineReducer()
    start = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    identity = {"session_id": "S1", "inquiry_id": "I1"}
    opened = Observation(
        "inquiry_opened",
        start + timedelta(seconds=5),
        {"question": "Does it reach?"},
        event_id="evt-1",
        **identity,
    )
    reducer.ingest(opened)
    reducer.ingest(opened)
    reducer.ingest(
        _event(
            "operation_started",
            start + timedelta(seconds=10),
            {"kind": "training"},
            operation_id="T1",
            **identity,
        )
    )
    reducer.ingest(
        _event(
            "operation_completed",
            start + timedelta(seconds=60),
            {"kind": "training"},
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
    inquiry = next(item for item in items if item.item_id == "inquiry:S1:I1")
    assert [c.title for c in inquiry.children].count("inquiry opened") == 1
    assert inquiry.default_expanded
    operation = next(item for item in items if item.item_id == "operation:T1")
    assert [child.title for child in operation.children] == ["started", "completed"]
    validated = next(
        item for item in items if item.title.startswith("scientific model")
    )
    assert "34159d3f" not in validated.summary + "".join(validated.detail)
    assert validated.payload["commit"] == "34159d3f"
    assert validated in next(i for i in items if i.item_id == "session:S1").children


def test_the_inquiry_question_is_known_to_every_session_that_continues_it():
    reducer = TimelineReducer()
    start = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    reducer.ingest(
        _event(
            "inquiry_opened",
            start,
            {"question": "Does it reach the target?"},
            session_id="S2",
            inquiry_id="I1",
        )
    )
    reducer.ingest(
        _event(
            "operation_started",
            start + timedelta(seconds=9),
            {"kind": "measurement"},
            session_id="S3",
            inquiry_id="I1",
            operation_id="M1",
        )
    )
    roots, _ = reducer.view()
    titles = {item.item_id: item.title for item in _walk(roots)}
    assert titles["inquiry:S2:I1"] == "I1 Does it reach the target?"
    assert titles["inquiry:S3:I1"] == "I1 Does it reach the target?"
