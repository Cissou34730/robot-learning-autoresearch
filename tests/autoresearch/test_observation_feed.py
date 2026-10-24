"""Tests for the one-way observation feed and its console emit points.

The feed must append presentation events, stay inert when disabled, and never
raise into the Runner.
"""

import json

import pytest

from runner import console, observation_feed
from runner.copilot.copilot_console import Console
from tui.observations import JsonlFeed


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    observation_feed.reset()
    monkeypatch.setenv("TUI_OBSERVATIONS", str(tmp_path / "events.jsonl"))
    yield
    observation_feed.reset()


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


def test_training_progress_event_carries_reward_and_success():
    from runner.execution import training_progress_event

    event = training_progress_event(
        "T4",
        72000,
        120000,
        728.0,
        {"ep_rew_mean": 86.3, "success_rate": 0.97},
    )
    assert event["kind"] == "training_progress"
    assert event["steps"] == 72000
    assert event["target"] == 120000
    assert event["ep_rew_mean"] == 86.3
    assert event["training_success"] == 0.97


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
