"""Observation production must work with the terminal renderers absent."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from runner import observation_feed, reporting, typed_events
from runner.copilot.reporting import CodingReporter, SessionReporter

ROOT = Path(__file__).resolve().parents[2]


def _records(path):
    return [
        {
            key: value
            for key, value in json.loads(line).items()
            if key not in {"ts", "event_id"}
        }
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def test_python_facts_and_accounting_survive_absent_renderers(
    monkeypatch, tmp_path, capsys
):
    from runner import execution, run_experiment

    monkeypatch.setattr("runner.copilot.reporting.time.monotonic", lambda: 100.0)

    def exercise(name, enabled):
        typed = tmp_path / f"{name}.events.jsonl"
        legacy = tmp_path / f"{name}.jsonl"
        monkeypatch.setenv("TUI_TYPED_EVENTS", str(typed))
        monkeypatch.setenv("TUI_OBSERVATIONS", str(legacy))
        typed_events.reset()
        observation_feed.reset()
        typed_events.set_campaign("campaign")
        observation_feed.set_campaign("campaign")
        session = (
            SessionReporter(session_id="backend")
            if enabled
            else SessionReporter(session_id="backend", renderer=None)
        )
        renderer = reporting._DEFAULT_RENDERER if enabled else None
        with reporting.rendering(renderer):
            reporting.announce("[runner] complete unshortened observation")
            reporting.card(
                "campaign", "Campaign resource facts", ["full resource description"]
            )
            reporting.diagnostic("Runner diagnostic", stderr=True)
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
                {
                    "kind": "training_progress",
                    "operation_id": "T1",
                    "steps": 100,
                    "target": 200,
                }
            )
            session.delta("An unshortened PI observation.\n\n")
            session.tool(
                "view", {"path": "robot_learning/scenario/environment.py"}, "call"
            )
            session.denied("Full denial reason", "call")
            session.tool_completed("view", "call")
            session.file_changed("created", "robot_learning/scenario/check.py")
            session.model_call(60000)
            session.operation_submitted("running")
            session.coding(
                "request",
                "  > scientific_coding: request",
                status="started",
                detail={"scope": "scenario"},
            )
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
        state = (
            session.usage.tool_calls,
            session.model_calls,
            session.session_error,
            session.changed_files,
        )
        return _records(typed), _records(legacy), state, captured.out, captured.err

    enabled = exercise("enabled", True)
    import runner
    import runner.copilot

    monkeypatch.delattr(runner, "console", raising=False)
    monkeypatch.delattr(runner.copilot, "copilot_console", raising=False)
    monkeypatch.setitem(sys.modules, "runner.console", None)
    monkeypatch.setitem(sys.modules, "runner.copilot.copilot_console", None)
    disabled = exercise("disabled", False)
    assert enabled[:3] == disabled[:3]
    assert enabled[3]
    assert disabled[3] == ""
    assert enabled[4] == "Runner diagnostic\nSDK diagnostic\n"
    assert disabled[4] == ""


def test_tui_can_start_when_console_modules_cannot_be_imported():
    code = """
import asyncio
import builtins
original = builtins.__import__
def importing(name, globals=None, locals=None, fromlist=(), level=0):
    blocked = {'runner.console', 'runner.copilot.copilot_console'}
    if name in blocked or (name == 'runner' and 'console' in (fromlist or ())) or (name == 'runner.copilot' and 'copilot_console' in (fromlist or ())):
        raise AssertionError('TUI imported a console renderer: ' + name)
    return original(name, globals, locals, fromlist, level)
builtins.__import__ = importing
from tui.report import CampaignReport
async def run():
    app = CampaignReport(demo=True)
    async with app.run_test(size=(160,45)) as pilot:
        await pilot.pause()
        assert app.snapshot is not None
        assert app.query_one('#output').text_lines()
asyncio.run(run())
"""
    result = subprocess.run(
        ["uv", "run", "python", "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("legacy", ["enabled", "disabled", "broken"])
def test_launcher_observations_survive_absent_renderers_and_legacy_feed(
    tmp_path, legacy
):
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("PowerShell is unavailable")
    broken = tmp_path / "legacy-directory"
    broken.mkdir()
    paths = []
    outputs = []
    for enabled in (True, False):
        feed = tmp_path / f"{enabled}.events.jsonl"
        legacy_path = (
            str(tmp_path / f"{enabled}.jsonl")
            if legacy == "enabled"
            else "off"
            if legacy == "disabled"
            else str(broken)
        )
        exercise = tmp_path / f"exercise-{enabled}.ps1"
        exercise.write_text(
            f"""
$ErrorActionPreference = 'Stop'
. '{ROOT / "researcher_session.ps1"}'
$script:TuiCampaignRoot = '{tmp_path}'
$script:TuiCampaignId = 'campaign'
$script:ConsoleRenderingEnabled = ${str(enabled).lower()}
$env:TUI_TYPED_EVENTS = '{feed}'
$env:TUI_OBSERVATIONS = '{legacy_path}'
if (-not $script:ConsoleRenderingEnabled) {{
    function Write-ConsoleStatus {{ throw 'Console status renderer was called' }}
    function Write-ConsoleCard {{ throw 'Console card renderer was called' }}
    function Write-ConsoleResearcherSessionStatus {{ throw 'Console session renderer was called' }}
}}
Write-Status -Message 'START | complete campaign resources' -Color Magenta -Label session
Write-Card -Title 'PI | campaign preparation' -Lines @('A complete description')
$status = New-ResearcherSessionStatus -Phase preparation -Attempt 1 -ExitCode 7 -Deliverable scientific_model.md -Present $true -Valid $false -Reason 'FULL_VALIDATION_REASON'
Write-ResearcherSessionStatus -Status $status
Write-TuiObservation -Kind session_start -Fields @{{session_id='backend'; stage='preparation'}}
""",
            encoding="utf-8",
        )
        result = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-File", str(exercise)],
            cwd=tmp_path,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        paths.append(feed)
        outputs.append(result.stdout)
    assert _records(paths[0]) == _records(paths[1])
    assert any(
        row["payload"].get("reason") == "FULL_VALIDATION_REASON"
        for row in _records(paths[1])
    )
    assert "FULL_VALIDATION_REASON" in outputs[0]
    assert outputs[1] == ""
