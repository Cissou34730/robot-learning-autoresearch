"""The Runner side of the event journal: contract coverage and writer integrity."""

import ast
import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from runner import typed_events
from runner.event_contract import (
    PREPARATION_SESSION,
    RULES,
    validate_record,
)
from runner.launcher.events import LauncherEvents

RUNNER = Path(__file__).resolve().parents[2] / "runner"


@pytest.fixture(autouse=True)
def _journal(monkeypatch, tmp_path):
    typed_events.reset()
    monkeypatch.setenv("TUI_TYPED_EVENTS", str(tmp_path / "journal.jsonl"))
    monkeypatch.setattr(typed_events, "strict", True)
    typed_events.set_campaign("campaign-1")
    yield
    typed_events.reset()


def _records(tmp_path):
    path = tmp_path / "journal.jsonl"
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()]


def test_every_emitted_kind_is_in_the_contract():
    unknown = set()
    for source in RUNNER.rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and node.args):
                continue
            function = node.func
            name = (
                function.attr
                if isinstance(function, ast.Attribute)
                else getattr(function, "id", "")
            )
            first = node.args[0]
            if (
                name in {"emit", "_emit", "observe"}
                and isinstance(first, ast.Constant)
                and isinstance(first.value, str)
                and first.value not in RULES
            ):
                unknown.add((source.name, first.value))
    assert not unknown


def test_the_owner_reaches_emitters_running_on_other_threads():
    results = []

    def emit_elsewhere():
        try:
            typed_events.emit("tool_call_started", {})
        except typed_events.ContractViolation as error:
            results.append(error)

    with typed_events.context(session_id="S3", attempt="inv-1", actor="pi"):
        worker = threading.Thread(target=emit_elsewhere)
        worker.start()
        worker.join()
    assert not results


def test_strict_mode_rejects_an_event_without_its_owner():
    with pytest.raises(typed_events.ContractViolation):
        typed_events.emit("tool_call_started", {})


def test_launcher_events_name_their_owner(tmp_path):
    root = tmp_path / "campaign"
    state = root / "runner" / "state"
    state.mkdir(parents=True)
    events = LauncherEvents(root)
    events._campaign_id = "campaign-1"
    typed_events.configure(tmp_path / "journal.jsonl")
    events.observe(
        "session_start",
        fields={"backend_session_id": "uuid-1"},
        session_id=PREPARATION_SESSION,
        attempt="inv-1",
        actor="pi",
    )
    with typed_events.context(session_id=PREPARATION_SESSION):
        events.status("START | campaign preparation", scope="session")
    events.status("Stop requested", scope="info")
    started, notice, campaign_notice = _records(tmp_path)
    assert (started["session_id"], started["attempt"], started["actor"]) == (
        PREPARATION_SESSION,
        "inv-1",
        "pi",
    )
    assert started["payload"]["backend_session_id"] == "uuid-1"
    assert notice["session_id"] == PREPARATION_SESSION
    assert notice["actor"] == "launcher"
    assert campaign_notice["session_id"] == ""
    assert all(
        not validate_record(record) for record in (started, notice, campaign_notice)
    )


WRITER = """
import sys
from runner import typed_events

path, name, count, size = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
typed_events.configure(path)
typed_events.set_campaign("campaign-1")
for index in range(count):
    typed_events.emit(
        "notice", {"writer": name, "index": index, "filler": "x" * size}
    )
assert typed_events.failures == 0
"""


def test_concurrent_writers_never_tear_a_record(tmp_path):
    path = tmp_path / "shared.jsonl"
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", WRITER, str(path), f"w{number}", "30", "60000"],
            cwd=RUNNER.parent,
        )
        for number in range(3)
    ]
    assert [process.wait(timeout=120) for process in processes] == [0, 0, 0]
    records = [json.loads(line) for line in path.read_text("utf-8").splitlines()]
    assert len(records) == 90
    assert {(r["payload"]["writer"], r["payload"]["index"]) for r in records} == {
        (f"w{number}", index) for number in range(3) for index in range(30)
    }
