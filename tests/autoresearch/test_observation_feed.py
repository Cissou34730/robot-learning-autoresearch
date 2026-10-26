"""Tests for the one-way observation feed and its console emit points.

The feed must append presentation events, stay inert when disabled, and never
raise into the Runner.
"""

import json

import pytest

from runner import observation_feed, typed_events
from runner import reporting as console
from runner.copilot.reporting import SessionReporter as Console
from tui.observations import JsonlFeed


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    observation_feed.reset()
    typed_events.reset()
    monkeypatch.setenv("TUI_OBSERVATIONS", str(tmp_path / "events.jsonl"))
    monkeypatch.setenv("TUI_TYPED_EVENTS", str(tmp_path / "typed.events.jsonl"))
    yield
    observation_feed.reset()
    typed_events.reset()


def _events(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def test_emit_writes_identity_and_payload(tmp_path):
    path = tmp_path / "events.jsonl"
    observation_feed.set_campaign("campaign-1")
    observation_feed.emit(
        {
            "kind": "training_progress",
            "operation_id": "T4",
            "steps": 72000,
            "target": 120000,
            "elapsed_seconds": 728.0,
        }
    )
    (event,) = _events(path)
    assert event["campaign_id"] == "campaign-1"
    assert event["kind"] == "training_progress"
    assert event["operation_id"] == "T4"
    assert event["steps"] == 72000
    assert event["ts"]


def test_training_progress_event_carries_reward_and_scenario_metric(monkeypatch):
    from runner import execution
    from runner import reporting as console

    monkeypatch.setattr(
        console, "scenario_progress_metric", lambda record: "success 97%"
    )
    event = execution.training_progress_event(
        "T4",
        72000,
        120000,
        728.0,
        {"ep_rew_mean": 86.3},
    )
    assert event["kind"] == "training_progress"
    assert event["steps"] == 72000
    assert event["target"] == 120000
    assert event["ep_rew_mean"] == 86.3
    assert event["scenario_metric"] == "success 97%"
    assert "training_success" not in event


def test_typed_emit_writes_schema_and_full_payload(tmp_path):
    path = tmp_path / "typed.events.jsonl"
    typed_events.reset()
    typed_events.set_campaign("campaign-1")
    typed_events.emit(
        "console_card",
        {"title": "OPERATION | T4", "body": ["full detail", "second line"]},
        scope="operation",
        operation_id="T4",
    )
    (event,) = _events(path)
    assert event["schema_version"] == 1
    assert event["event_id"]
    assert event["campaign_id"] == "campaign-1"
    assert event["kind"] == "console_card"
    assert event["operation_id"] == "T4"
    assert event["payload"]["body"] == ["full detail", "second line"]


def test_console_announce_keeps_full_text_in_typed_feed(tmp_path, capsys):
    path = tmp_path / "typed.events.jsonl"
    typed_events.reset()
    typed_events.set_campaign("campaign-1")
    message = "[pi] The full PI text is not shortened here. " * 4
    console.announce(message)
    capsys.readouterr()
    (event,) = _events(path)
    assert event["kind"] == "console_line"
    assert event["payload"]["text"] == message
    assert event["scope"] == "pi"


def test_typed_emitter_does_not_change_console_stdout(monkeypatch, tmp_path, capsys):
    import re

    message = "[pi] identical console text"
    monkeypatch.setenv("TUI_TYPED_EVENTS", str(tmp_path / "on.events.jsonl"))
    typed_events.reset()
    console.announce(message)
    with_typed = capsys.readouterr().out
    monkeypatch.setenv("TUI_TYPED_EVENTS", "off")
    typed_events.reset()
    console.announce(message)
    without_typed = capsys.readouterr().out
    pattern = re.compile(r"^\[[^\]]+\] ", re.MULTILINE)
    assert pattern.sub("", with_typed) == pattern.sub("", without_typed)


def test_typed_disabled_feed_writes_nothing(monkeypatch, tmp_path):
    path = tmp_path / "typed.events.jsonl"
    monkeypatch.setenv("TUI_TYPED_EVENTS", "off")
    typed_events.reset()
    typed_events.emit("run_state", {"state": "idle"})
    assert not path.exists()


def test_disabled_feed_writes_nothing(monkeypatch, tmp_path):
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("TUI_OBSERVATIONS", "off")
    observation_feed.reset()
    observation_feed.emit({"kind": "liveness"})
    assert not path.exists()


def test_write_failure_is_swallowed(monkeypatch, tmp_path):
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("TUI_OBSERVATIONS", str(blocker / "events.jsonl"))
    observation_feed.reset()
    before = observation_feed.failures
    observation_feed.emit({"kind": "liveness"})
    assert observation_feed.failures == before + 1


def test_console_funnels_emit_classified_lines(tmp_path, capsys):
    path = tmp_path / "events.jsonl"
    observation_feed.reset()
    console.card("operation", "Operation REQUEST", ["T4 accepted"])
    console.announce("[pi] The policy reaches the target.")
    capsys.readouterr()
    events = _events(path)
    scopes = [event["scope"] for event in events]
    assert scopes == ["operation", "pi"]
    assert events[0]["text"].startswith("=== Operation REQUEST ===")
    assert events[1]["text"] == "The policy reaches the target."


def test_context_merges_session_and_operation_identity():
    typed_events.reset()
    with typed_events.context(session_id="S7"):
        with typed_events.context(operation_id="T4"):
            assert typed_events.current_context() == {
                "operation_id": "T4",
                "session_id": "S7",
                "inquiry_id": "",
            }
        assert typed_events.current_context()["operation_id"] == ""
    assert typed_events.current_context() == {}


def test_console_domain_events_carry_session_identity(tmp_path, capsys):
    path = tmp_path / "typed.events.jsonl"
    typed_events.reset()
    typed_events.set_campaign("campaign-1")
    session = Console(columns=200, session_id="backend-1")
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
    capsys.readouterr()
    events = _events(path)
    kinds = [event["kind"] for event in events]
    assert "tool_call_started" in kinds
    assert "tool_call_completed" in kinds
    assert "file_changed" in kinds
    assert "coding" in kinds
    assert "operation_submitted" in kinds
    assert "warning" in kinds
    assert "console_line" not in kinds
    assert {event["session_id"] for event in events} == {"backend-1"}
    completed = next(
        event for event in events if event["kind"] == "tool_call_completed"
    )
    assert completed["payload"]["tool_call_id"] == "call-1"
    assert completed["payload"]["result"]["value"] == 3


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
            "episode_outcome_breakdown",
            {
                "status": "computed",
                "measurements": [
                    {
                        "operation_id": "M6",
                        "candidate": "T4",
                        "successes": 9,
                        "trials": 10,
                    }
                ],
                "paired": {
                    "first_only_success": 2,
                    "second_only_success": 0,
                    "sign_test_p_value": 0.5,
                },
            },
            "sign test p 0.5",
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
def test_tui_and_console_share_factual_tool_result_lines(
    tmp_path, capsys, name, result, number
):
    from tui.events import TypedJsonlFeed
    from tui.timeline import TimelineReducer

    typed_events.set_campaign("campaign-1")
    session = Console(columns=300, session_id="backend-1")
    session.tool(name, {}, "result-call")
    capsys.readouterr()
    session.tool_result(name, json.dumps(result), tool_call_id="result-call")
    output = capsys.readouterr().out
    assert number in output
    reducer = TimelineReducer()
    for event in TypedJsonlFeed(
        tmp_path / "typed.events.jsonl", campaign_id="campaign-1"
    ).poll():
        reducer.ingest(event)
    tool = next(
        child
        for root in reducer.view()[0]
        for child in root.children
        if child.kind == "tool"
    )
    assert tool.detail == tuple(line.strip() for line in output.splitlines())
    assert tool.payload["result"] == result


def test_domain_event_closes_the_pi_message_first(tmp_path, capsys):
    path = tmp_path / "typed.events.jsonl"
    typed_events.reset()
    typed_events.set_campaign("campaign-1")
    session = Console(columns=200, session_id="backend-1")
    session.delta("PI answer\n\n")
    session.warning("context compacted", code="compaction")
    capsys.readouterr()
    events = _events(path)
    final_message = next(
        index
        for index, event in enumerate(events)
        if event["kind"] == "pi_message" and event["payload"].get("final")
    )
    warning = next(
        index for index, event in enumerate(events) if event["kind"] == "warning"
    )
    assert final_message < warning


def test_typed_false_funnels_keep_stdout_and_skip_typed(tmp_path, capsys):
    import re

    path = tmp_path / "typed.events.jsonl"
    typed_events.reset()
    typed_events.set_campaign("campaign-1")

    def run(*, typed: bool) -> str:
        console.card("operation", "Operation REQUEST", ["T4 accepted"], typed=typed)
        console.boundary("warning", "OPERATION PAUSED", "T4", typed=typed)
        console.announce("[pi] no typed copy", typed=typed)
        return capsys.readouterr().out

    untracked = run(typed=False)
    assert not path.exists()
    tracked = run(typed=True)
    pattern = re.compile(r"^\[[^\]]+\] ", re.MULTILINE)
    assert pattern.sub("", untracked) == pattern.sub("", tracked)
    assert _events(path)


def test_lifecycle_cards_are_owned_by_domain_events(tmp_path, capsys):
    from runner import run_experiment

    typed_events.reset()
    typed_events.set_campaign("campaign-1")
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
    capsys.readouterr()
    events = _events(tmp_path / "typed.events.jsonl")
    assert [event["kind"] for event in events] == ["inquiry_opened"]
    assert events[0]["inquiry_id"] == "I9"
    assert events[0]["payload"]["question"] == "Does the policy reach the target?"
    assert "console_card" not in {event["kind"] for event in events}


def test_training_results_card_is_owned_by_a_domain_event(
    monkeypatch, tmp_path, capsys
):
    from runner import execution

    typed_events.reset()
    typed_events.set_campaign("campaign-1")
    checkpoint = tmp_path / "candidate_pool" / "checkpoint-1000"
    checkpoint.mkdir(parents=True)
    (checkpoint / "training_metrics.json").write_text(
        json.dumps(
            {
                "timesteps": 1000,
                "ep_rew_mean": 12.5,
                "success_rate": 0.75,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        execution.console,
        "training_progress_suffix",
        lambda record: " | reward 12.5 | success 75%",
    )
    announced: set[str] = set()
    execution.announce_training_checkpoints(tmp_path, "T9", announced)
    capsys.readouterr()
    events = _events(tmp_path / "typed.events.jsonl")
    assert [event["kind"] for event in events] == ["training_checkpoints"]
    (candidate,) = events[0]["payload"]["candidates"]
    assert candidate["candidate"] == "T9:checkpoint-1000"
    assert candidate["steps"] == 1000
    assert candidate["ep_rew_mean"] == 12.5
    assert "training_success" not in candidate
    assert candidate["summary"] == "reward 12.5 | success 75%"
    assert announced == {"checkpoint-1000"}


def test_copilot_console_emits_one_pi_message_and_tool_line(tmp_path, capsys):
    path = tmp_path / "events.jsonl"
    observation_feed.reset()
    session = Console(columns=200)
    session.delta("The policy ")
    session.delta("reaches the target.")
    session.line("  > artifact_evidence_query: M6 artifact 0")
    capsys.readouterr()
    events = _events(path)
    messages = [event for event in events if event["kind"] == "pi_message"]
    finals = [event for event in messages if event["final"]]
    assert finals and finals[-1]["text"] == "The policy reaches the target."
    console_lines = [event for event in events if event["kind"] == "console_line"]
    assert [event["scope"] for event in console_lines] == ["tool"]


def test_pi_message_is_published_before_the_turn_ends(tmp_path, capsys):
    path = tmp_path / "events.jsonl"
    observation_feed.reset()
    session = Console(columns=200)
    session.delta("First paragraph is ready.\n\n")
    session.delta("Second paragraph continues ")
    session.delta("to the end.")
    session.line("  > artifact_evidence_query: M6 artifact 0")
    capsys.readouterr()
    messages = [event for event in _events(path) if event["kind"] == "pi_message"]
    partials = [event for event in messages if not event["final"]]
    finals = [event for event in messages if event["final"]]
    assert partials, "a growing message must reach the feed before turn end"
    assert finals
    complete = finals[-1]["text"].strip()
    assert (
        complete
        == "First paragraph is ready.\n\nSecond paragraph continues to the end."
    )
    assert complete.startswith("".join(event["text"] for event in partials))
    assert {event["turn"] for event in messages} == {1}


def test_override_path_still_carries_the_campaign_identity(monkeypatch, tmp_path):
    from runner import paths

    state = tmp_path / "research_state.json"
    state.write_text(json.dumps({"campaign": {"id": "campaign-9"}}), encoding="utf-8")
    monkeypatch.setattr(paths, "STATE_PATH", state)
    observation_feed.reset()
    observation_feed.emit({"kind": "liveness"})
    path = tmp_path / "events.jsonl"
    (event,) = _events(path)
    assert event["campaign_id"] == "campaign-9"
    assert len(JsonlFeed(path, campaign_id="campaign-9").poll()) == 1


def test_default_feed_is_one_file_per_campaign(monkeypatch, tmp_path):
    from runner import paths

    monkeypatch.setattr(paths, "ROOT", tmp_path)
    path = observation_feed.default_path("campaign-abc")
    assert path == tmp_path / "reports" / "tui_observations" / "campaign-abc.jsonl"


def _write_feed(path, campaign_id, count, start=0):
    with path.open("a", encoding="utf-8") as handle:
        for index in range(start, start + count):
            handle.write(
                json.dumps(
                    {
                        "campaign_id": campaign_id,
                        "ts": f"2026-10-24T12:00:{index % 60:02d}.{index:06d}+00:00",
                        "kind": "liveness",
                    }
                )
                + "\n"
            )


def test_feed_follows_by_offset_without_replaying(tmp_path):
    path = tmp_path / "feed.jsonl"
    _write_feed(path, "campaign-1", 5000)
    feed = JsonlFeed(path, campaign_id="campaign-1")
    assert len(feed.poll()) == 5000
    assert feed.poll() == []
    _write_feed(path, "campaign-1", 2, start=5000)
    assert len(feed.poll()) == 2
    assert feed.poll() == []


def test_feed_restarts_when_the_file_shrinks(tmp_path):
    path = tmp_path / "feed.jsonl"
    _write_feed(path, "campaign-1", 5)
    feed = JsonlFeed(path, campaign_id="campaign-1")
    assert len(feed.poll()) == 5
    path.write_text("", encoding="utf-8")
    _write_feed(path, "campaign-1", 1)
    assert len(feed.poll()) == 1


def test_feed_rejects_missing_and_foreign_campaign_identity(tmp_path):
    path = tmp_path / "feed.jsonl"
    _write_feed(path, None, 1)
    _write_feed(path, "other-campaign", 1)
    _write_feed(path, "campaign-1", 1)
    feed = JsonlFeed(path, campaign_id="campaign-1")
    events = feed.poll()
    assert len(events) == 1
    assert feed.rejected
