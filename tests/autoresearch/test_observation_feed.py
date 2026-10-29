"""Tests for the typed event feed and the facts the Runner publishes to it.

The feed must append events, stay inert when disabled, never raise into the
Runner, and be the only output: nothing is written to a console.
"""

import json

import pytest

from runner import invocation_result, typed_events
from runner import reporting as console
from runner.copilot.reporting import SessionReporter, tool_result_lines
from tui.journal import JournalFeed


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    typed_events.reset()
    monkeypatch.setenv("TUI_TYPED_EVENTS", str(tmp_path / "typed.events.jsonl"))
    monkeypatch.setattr(typed_events, "strict", True)
    typed_events.set_campaign("campaign-1")
    yield
    typed_events.reset()


def _events(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def test_training_progress_event_carries_reward_and_scenario_metric(monkeypatch):
    from runner import execution

    monkeypatch.setattr(
        console, "scenario_progress_metric", lambda record: "success 97%"
    )
    event = execution.training_progress_event(
        "T4",
        72000,
        120000,
        728.0,
        {"ep_rew_mean": 86.3},
        eta_seconds=44.5,
    )
    assert event["kind"] == "training_progress"
    assert event["steps"] == 72000
    assert event["target"] == 120000
    assert event["ep_rew_mean"] == 86.3
    assert event["scenario_metric"] == "success 97%"
    assert event["elapsed_seconds"] == 728.0
    assert event["eta_seconds"] == 44.5
    assert "training_success" not in event


def test_typed_emit_writes_schema_and_full_payload(tmp_path):
    typed_events.emit(
        "notice",
        {"title": "OPERATION | T4", "body": ["full detail", "second line"]},
        scope="operation",
        operation_id="T4",
    )
    (event,) = _events(tmp_path / "typed.events.jsonl")
    assert event["schema_version"] == 2
    assert event["event_id"]
    assert event["campaign_id"] == "campaign-1"
    assert event["kind"] == "notice"
    assert event["operation_id"] == "T4"
    assert event["payload"]["body"] == ["full detail", "second line"]


def test_notices_reach_the_feed_and_nothing_reaches_a_console(tmp_path, capsys):
    message = "[pi] The full PI text is not shortened here. " * 4
    console.announce(message)
    console.card("operation", "Operation REQUEST", ["T4 accepted"])
    console.boundary("warning", "OPERATION PAUSED", "T4")
    invocation_result.configure(None)
    console.diagnostic("ERROR: example", code="example")
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
    events = _events(tmp_path / "typed.events.jsonl")
    assert [event["kind"] for event in events] == [
        "notice",
        "notice",
        "notice",
        "error",
    ]
    assert events[0]["payload"]["text"] == message
    assert events[0]["scope"] == "pi"
    assert events[1]["payload"] == {
        "title": "Operation REQUEST",
        "body": ["T4 accepted"],
        "scope": "operation",
    }
    assert events[2]["severity"] == "warning"
    assert events[3]["payload"] == {"code": "example", "message": "ERROR: example"}


def test_diagnostics_reach_the_launcher_result(tmp_path):
    result = tmp_path / "result.json"
    invocation_result.configure(result)
    console.diagnostic("ERROR: pi_workspace/operation_request.json not found")
    invocation_result.write(1)
    assert json.loads(result.read_text(encoding="utf-8")) == {
        "exit_code": 1,
        "errors": ["ERROR: pi_workspace/operation_request.json not found"],
    }


def test_typed_disabled_feed_writes_nothing(monkeypatch, tmp_path):
    monkeypatch.setenv("TUI_TYPED_EVENTS", "off")
    typed_events.reset()
    typed_events.emit("run_state", {"state": "idle"})
    assert not (tmp_path / "typed.events.jsonl").exists()


def test_write_failure_is_swallowed(monkeypatch, tmp_path):
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("TUI_TYPED_EVENTS", str(blocker / "events.jsonl"))
    typed_events.reset()
    before = typed_events.failures
    typed_events.emit("liveness", {})
    assert typed_events.failures > before


def test_context_merges_session_and_operation_identity():
    with typed_events.context(session_id="S7"):
        with typed_events.context(operation_id="T4"):
            assert typed_events.current_context() == {
                "operation_id": "T4",
                "session_id": "S7",
            }
        assert "operation_id" not in typed_events.current_context()
    assert typed_events.current_context() == {}


def test_session_domain_events_carry_the_bound_session(tmp_path, capsys):
    session = SessionReporter(session_id="backend-1")
    with typed_events.context(session_id="S7", attempt="inv-1", actor="pi"):
        session.tool("read_file", {"path": "robot_learning/x.py"}, "call-1")
        session.tool_result(
            "artifact_evidence_query",
            json.dumps({"status": "computed", "value": 3}),
            tool_call_id="call-1",
        )
        session.file_changed("created", "robot_learning/x.py")
        session.coding(
            "request",
            "  > scientific_coding: request | scope | intent",
            status="started",
            detail={"scope": "x"},
        )
        session.operation_submitted("accepted")
        session.warning("context compacted", code="compaction")
    assert capsys.readouterr().out == ""
    events = _events(tmp_path / "typed.events.jsonl")
    kinds = [event["kind"] for event in events]
    assert {
        "tool_call_started",
        "tool_call_completed",
        "file_changed",
        "coding",
        "operation_submitted",
        "warning",
    } <= set(kinds)
    assert {event["session_id"] for event in events} == {"S7"}
    assert {event["attempt"] for event in events} == {"inv-1"}
    assert {event["actor"] for event in events} == {"pi"}
    completed = next(
        event for event in events if event["kind"] == "tool_call_completed"
    )
    assert completed["payload"]["tool_call_id"] == "call-1"
    assert completed["payload"]["result"]["value"] == 3
    coding = next(event for event in events if event["kind"] == "coding")
    assert coding["payload"]["text"] == "> scientific_coding: request | scope | intent"


@pytest.mark.parametrize(
    ("name", "result", "number"),
    [
        (
            "success_rate_pass_probability",
            {
                "status": "computed",
                "evidence": [
                    {
                        "label": "M6",
                        "successes": 9,
                        "trials": 10,
                        "pass_probability": 0.9,
                    }
                ],
            },
            "9/10 -> pass 90.0%",
        ),
        (
            "training_series_statistics",
            {
                "status": "computed",
                "metric": "reward",
                "window": {
                    "rows": 3,
                    "min": {"value": 1},
                    "max": {"value": 3},
                    "last": {"value": 2},
                },
                "checks": [
                    {
                        "statistic": "mean",
                        "comparison": ">=",
                        "threshold": 2,
                        "holds": True,
                        "value": 2,
                    }
                ],
            },
            "3 rows | min 1 | max 3 | last 2",
        ),
    ],
)
def test_tool_result_numbers_reach_the_timeline(tmp_path, name, result, number):
    from tui.timeline import TimelineReducer

    session = SessionReporter(session_id="backend-1")
    with typed_events.context(session_id="S1", attempt="inv-1", actor="pi"):
        session.tool(name, {}, "result-call")
        session.tool_result(name, json.dumps(result), tool_call_id="result-call")
    reducer = TimelineReducer()
    for event in JournalFeed(
        tmp_path / "typed.events.jsonl", campaign_id="campaign-1"
    ).poll():
        reducer.ingest(event)
    tool = next(
        child
        for root in reducer.view()[0]
        for child in root.children
        if child.kind == "tool"
    )
    expected = tuple(text.strip() for text, _ in tool_result_lines(name, result))
    assert tool.detail == expected
    assert any(number in line for line in tool.detail)
    assert tool.payload["result"] == result


def test_domain_event_closes_the_pi_message_first(tmp_path):
    session = SessionReporter(session_id="backend-1")
    with typed_events.context(session_id="S1"):
        session.delta("PI answer\n\n")
        session.warning("context compacted", code="compaction")
    events = _events(tmp_path / "typed.events.jsonl")
    final_message = next(
        index
        for index, event in enumerate(events)
        if event["kind"] == "pi_message" and event["payload"].get("final")
    )
    warning = next(
        index for index, event in enumerate(events) if event["kind"] == "warning"
    )
    assert final_message < warning


def test_the_sdk_message_ends_and_labels_each_pi_message_once(tmp_path):
    session = SessionReporter(session_id="backend-1")
    with typed_events.context(session_id="S1"):
        session.delta("Radius results ", "m1")
        session.model_call(10**9)
        session.message("Radius results point to a gap.", "m1", "note")
        session.tool("view", {"path": "x"}, "call-1")
        session.delta("Early ", "m2")
        session.warning("context compacted", code="compaction")
        session.message("Early text.", "m2", "end")
        session.message("Session done.", "m3", "end")
    events = _events(tmp_path / "typed.events.jsonl")
    finals = [
        (event["payload"]["text"], event["payload"].get("message_kind"))
        for event in events
        if event["kind"] == "pi_message" and event["payload"]["final"]
    ]
    assert finals == [
        ("Radius results point to a gap.", "note"),
        ("Early ", None),
        ("Session done.", "end"),
    ]
    assert any(event["kind"] == "pi_context" for event in events)


def test_lifecycle_facts_are_domain_events(tmp_path):
    from runner import run_experiment

    presentation = {
        "campaign_id": "campaign-1",
        "context": "campaign context",
        "kind": "inquiry",
        "session_id": "S8",
        "pending": {
            "id": "I9",
            "kind": "inquiry",
            "session_id": "S8",
            "inquiry_id": "I9",
            "data": {"result": {"action": "OPEN", "inquiry_id": "I9"}},
            "request": {
                "inquiry": {
                    "question": "Does the policy reach the target?",
                    "goal_connection": "It tests the campaign objective.",
                    "closure_condition": "A measured success rate.",
                }
            },
        },
    }
    run_experiment._announce_consequential_completion(presentation)
    events = _events(tmp_path / "typed.events.jsonl")
    assert [event["kind"] for event in events] == ["inquiry_opened"]
    assert events[0]["inquiry_id"] == "I9"
    assert events[0]["payload"]["question"] == "Does the policy reach the target?"


def test_training_results_are_a_domain_event(monkeypatch, tmp_path):
    from runner import execution

    checkpoint = tmp_path / "candidate_pool" / "checkpoint-1000"
    checkpoint.mkdir(parents=True)
    (checkpoint / "training_metrics.json").write_text(
        json.dumps({"timesteps": 1000, "ep_rew_mean": 12.5, "success_rate": 0.75}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        execution.console,
        "training_progress_suffix",
        lambda record: " | reward 12.5 | success 75%",
    )
    announced: set[str] = set()
    with typed_events.context(session_id="S1"):
        execution.announce_training_checkpoints(tmp_path, "T9", announced)
    events = _events(tmp_path / "typed.events.jsonl")
    assert [event["kind"] for event in events] == ["training_checkpoints"]
    (candidate,) = events[0]["payload"]["candidates"]
    assert candidate["candidate"] == "T9:checkpoint-1000"
    assert candidate["steps"] == 1000
    assert candidate["ep_rew_mean"] == 12.5
    assert candidate["summary"] == "reward 12.5 | success 75%"
    assert announced == {"checkpoint-1000"}


def test_pi_message_is_published_before_the_turn_ends(tmp_path):
    session = SessionReporter(session_id="backend-1")
    with typed_events.context(session_id="S1"):
        session.delta("First paragraph is ready.\n\n")
        session.delta("Second paragraph continues ")
        session.delta("to the end.")
        session.warning("context compacted", code="compaction")
    messages = [
        event["payload"]
        for event in _events(tmp_path / "typed.events.jsonl")
        if event["kind"] == "pi_message"
    ]
    partials = [event for event in messages if not event["final"]]
    finals = [event for event in messages if event["final"]]
    assert partials, "a growing message must reach the feed before turn end"
    complete = finals[-1]["text"].strip()
    assert (
        complete
        == "First paragraph is ready.\n\nSecond paragraph continues to the end."
    )
    assert complete.startswith("".join(event["text"] for event in partials))
    assert {event["turn"] for event in messages} == {1}


def test_default_feed_is_one_file_per_campaign(monkeypatch, tmp_path):
    from runner import paths

    monkeypatch.setattr(paths, "ROOT", tmp_path)
    path = typed_events.default_path("campaign-abc")
    assert (
        path
        == tmp_path / "reports" / "tui_observations" / "campaign-abc.events.v2.jsonl"
    )


def _write_feed(path, campaign_id, count, start=0):
    with path.open("a", encoding="utf-8") as handle:
        for index in range(start, start + count):
            handle.write(
                json.dumps(
                    {
                        "schema_version": 2,
                        "event_id": f"event-{index}",
                        "campaign_id": campaign_id,
                        "ts": f"2026-10-24T12:00:{index % 60:02d}.{index:06d}+00:00",
                        "kind": "liveness",
                        "payload": {},
                    }
                )
                + "\n"
            )


def test_feed_follows_by_offset_without_replaying(tmp_path):
    path = tmp_path / "feed.events.v2.jsonl"
    _write_feed(path, "campaign-1", 5000)
    feed = JournalFeed(path, campaign_id="campaign-1")
    assert len(feed.poll()) == 5000
    assert feed.poll() == []
    _write_feed(path, "campaign-1", 2, start=5000)
    assert len(feed.poll()) == 2
    assert feed.poll() == []


def test_feed_restarts_when_the_file_shrinks(tmp_path):
    path = tmp_path / "feed.events.v2.jsonl"
    _write_feed(path, "campaign-1", 5)
    feed = JournalFeed(path, campaign_id="campaign-1")
    assert len(feed.poll()) == 5
    path.write_text("", encoding="utf-8")
    _write_feed(path, "campaign-1", 1)
    assert len(feed.poll()) == 1


def test_feed_rejects_missing_and_foreign_campaign_identity(tmp_path):
    path = tmp_path / "feed.events.v2.jsonl"
    _write_feed(path, None, 1)
    _write_feed(path, "other-campaign", 1)
    _write_feed(path, "campaign-1", 1)
    feed = JournalFeed(path, campaign_id="campaign-1")
    events = feed.poll()
    assert len(events) == 1
    assert feed.rejected
