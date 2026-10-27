"""Runner and session producers publish facts without writing to a console."""

import json
from types import SimpleNamespace

from runner import reporting, typed_events
from runner.copilot.reporting import CodingReporter, SessionReporter


def test_producers_write_only_the_typed_feed(monkeypatch, tmp_path, capsys):
    from runner import execution, run_experiment

    feed = tmp_path / "campaign.events.jsonl"
    monkeypatch.setenv("TUI_TYPED_EVENTS", str(feed))
    typed_events.reset()
    typed_events.set_campaign("campaign")
    monkeypatch.setattr("runner.copilot.reporting.time.monotonic", lambda: 100.0)
    reporting.announce("[runner] complete unshortened observation")
    reporting.card("campaign", "Campaign resource facts", ["full resource description"])
    reporting.diagnostic("Runner diagnostic")
    run_experiment._announce_consequential_completion(
        {
            "kind": "inquiry",
            "context": "I1 / S1",
            "session_id": "S1",
            "pending": {
                "id": "I1",
                "kind": "inquiry",
                "session_id": "S1",
                "inquiry_id": "I1",
                "data": {"result": {"action": "OPEN", "inquiry_id": "I1"}},
                "request": {
                    "inquiry": {
                        "question": "A scientific question",
                        "goal_connection": "Goal",
                        "closure_condition": "Closure",
                    }
                },
            },
        }
    )
    execution._emit_progress(
        {"kind": "training_progress", "operation_id": "T1", "steps": 100, "target": 200}
    )
    session = SessionReporter(session_id="backend")
    session.delta("An unshortened PI observation.\n\n")
    session.tool("view", {"path": "robot_learning/scenario/environment.py"}, "call")
    session.denied("Full denial reason", "call")
    session.tool_completed("view", "call")
    session.file_changed("created", "robot_learning/scenario/check.py")
    session.model_call(60000)
    session.operation_submitted("running")
    child = CodingReporter(session, "scientific-coder")
    child.tool(
        "apply_patch",
        "*** Begin Patch\n*** Add File: robot_learning/scenario/x.py\n+x = 1\n*** End Patch",
        "patch",
    )
    session.compaction(
        SimpleNamespace(
            success=True,
            pre_compaction_tokens=10000,
            post_compaction_tokens=5000,
            messages_removed=3,
        )
    )
    session.warning("Full warning", code="test_warning")
    session.error("Full error")
    session.diagnostic("SDK diagnostic", code="test_diagnostic")
    session.summary(["robot_learning/scenario/other.py"])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert session.model_calls == 1
    assert session.session_error == "Full error"
    assert any(
        path.replace("\\", "/").endswith("robot_learning/scenario/check.py")
        for path in session.changed_files
    )
    kinds = {
        json.loads(line)["kind"]
        for line in feed.read_text(encoding="utf-8").splitlines()
    }
    assert {
        "notice",
        "error",
        "inquiry_opened",
        "training_progress",
        "pi_message",
        "tool_call_started",
        "file_changed",
        "operation_submitted",
        "warning",
    } <= kinds
