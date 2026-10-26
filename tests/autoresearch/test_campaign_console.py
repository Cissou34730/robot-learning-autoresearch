"""Headless checks for the operator console.

Nothing real is launched, reset or stopped: the console drives the same fake
machinery used for the controller tests, so only UI wiring and lifecycle
behavior are validated. Campaign-2-style scientific folders are never touched.
"""

from __future__ import annotations

import asyncio
import subprocess
import time
from pathlib import Path

import pytest

from tui import controller as control
from tui.console import CampaignConsole, ConsoleDetail
from tui.report import CampaignPanel


def _workspace(tmp_path: Path) -> control.WorkspaceLayout:
    root = tmp_path / "robot-learning-campaigns"
    root.mkdir()
    for slot in (1, 2):
        campaign = root / f"campaign-{slot}"
        (campaign / ".git").mkdir(parents=True)
    harness = tmp_path / "harness"
    harness.mkdir()
    (harness / "run_research.ps1").write_text("param() ", encoding="utf-8")
    (harness / "reset_research.ps1").write_text("param() ", encoding="utf-8")
    return control.WorkspaceLayout(harness, root)


def _console(tmp_path: Path, machinery):
    layout = _workspace(tmp_path)
    app = CampaignConsole(
        harness_root=layout.harness_root,
        campaigns_root=layout.campaigns_root,
        machinery=machinery,
    )
    # A non-repository test harness must not fail the launcher preflight.
    app._controller._preflight = control.HarnessPreflight(
        layout.harness_root,
        lambda arguments: subprocess.CompletedProcess(
            arguments, 0, stdout="", stderr=""
        ),
    )
    return app, layout


def _clean(machinery) -> None:
    """Loosen the fake machinery defaults used by the controller batch."""
    machinery.next_exit_code = 0
    machinery.wait_exit_code = 130


async def _run_batch(app, pilot, text: str) -> None:
    app.submit_command(text)
    for _ in range(100):
        await pilot.pause()
        if not app._command_running:
            break
    await pilot.pause()


def test_console_shows_commands_tab_and_campaign_tabs_with_panels(tmp_path):
    from tests.autoresearch.test_campaign_controller import FakeMachinery

    machinery = FakeMachinery()
    app, layout = _console(tmp_path, machinery)

    async def scenario():
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            from textual.widgets import TabbedContent

            tabs = app.query_one(TabbedContent)
            pane_ids = [pane.id for pane in tabs.query("TabPane")]
            assert pane_ids == ["commands", "campaign-1", "campaign-2"]
            for slot in (1, 2):
                panel = app.query_one(f"#panel-campaign-{slot}", CampaignPanel)
                assert panel._campaign_root == layout.folder(slot)
            assert app.submit_command("deploy 2") is None
            await _run_batch(app, pilot, "run 9")
            log_text = ""
            log = app.query_one("#commands-log")
            for line in log.lines:
                log_text += "".join(segment.text for segment in line) + "\n"
            assert "campaign-9" in log_text or "Count" in log_text
            # Ctrl+C must copy or do nothing; it must never quit or shut down.
            await pilot.press("ctrl+c")
            await pilot.pause()
            assert app.is_running
            assert not app._shutting_down

    asyncio.run(scenario())


def test_console_start_command_launches_and_stop_command_stops(tmp_path):
    from tests.autoresearch.test_campaign_controller import FakeMachinery

    machinery = FakeMachinery()
    app, layout = _console(tmp_path, machinery)

    async def scenario():
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            await _run_batch(app, pilot, "start 1")
            assert machinery.started, "the start command must reach the launcher"
            started_folder, started_arguments = machinery.started[-1]
            assert started_folder == layout.folder(1)
            joined = " ".join(started_arguments)
            assert "-CampaignRoot" in joined
            assert "-StopRequestPath" in joined
            assert app._controller.state("campaign-1").stage == "running"

            await _run_batch(app, pilot, "stop all")
            child = machinery.children[layout.folder(1)]
            assert child.stop_requests == 1
            assert app._controller.state("campaign-1").stage == "stopping"

    asyncio.run(scenario())


def test_console_ctrl_q_stops_everything_then_exits(tmp_path):
    from tests.autoresearch.test_campaign_controller import FakeMachinery

    machinery = FakeMachinery()
    app, layout = _console(tmp_path, machinery)

    async def scenario():
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            await _run_batch(app, pilot, "start campaign-1")
            await _run_batch(app, pilot, "start campaign-2")
            await pilot.press("ctrl+q")
            for _ in range(100):
                await pilot.pause()
                if not app._shutting_down:
                    break
            # The shutdown thread still needs to settle and call exit.
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                await pilot.pause()
                if not app.is_running:
                    break
            for slot in (1, 2):
                state = app._controller.state(f"campaign-{slot}")
                assert state.child is None
                assert state.stage == "stopped"
                child = machinery.children[layout.folder(slot)]
                assert child.stop_requests == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("size", [(80, 24), (60, 24)])
def test_compact_console_contextual_command_and_copy_only(tmp_path, size):
    from textual.widgets import Input, TabbedContent

    from tests.autoresearch.test_campaign_controller import FakeMachinery

    machinery = FakeMachinery()
    app, layout = _console(tmp_path, machinery)

    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            assert not machinery.started
            command = app.query_one("#commands-input", Input)
            assert command.region.bottom <= size[1]
            await pilot.press("ctrl+tab")
            assert app.query_one(TabbedContent).active == "campaign-1"
            await _run_batch(app, pilot, "start")
            assert machinery.started[0][0] == layout.folder(1)
            app.query_one("#cmd-max-inquiries", Input).value = "invalid"
            await _run_batch(app, pilot, "stop")
            assert app._controller.state("campaign-1").stage == "stopping"
            await pilot.press("ctrl+c")
            assert app.is_running and not app._shutting_down
            assert machinery.forced == []

    asyncio.run(scenario())


def test_reset_options_failure_popup_and_persistent_details(tmp_path):
    from textual.widgets import Checkbox, Input, Select

    from tests.autoresearch.test_campaign_controller import FakeMachinery

    machinery = FakeMachinery()
    app, _layout = _console(tmp_path, machinery)
    calls = []

    def fail(arguments):
        calls.append(arguments)
        return subprocess.CompletedProcess(
            arguments, 7, stdout="", stderr="synthetic reset failure"
        )

    app._controller._runner = fail

    async def scenario():
        async with app.run_test(size=(120, 45)) as pilot:
            app.query_one("#reset-mode", Select).value = "Baseline"
            app.query_one("#reset-baseline", Input).value = "selected-baseline"
            app.query_one("#reset-clean", Checkbox).value = False
            await _run_batch(app, pilot, "run 2")
            assert len(calls) == 1
            assert "Baseline" in calls[0] and "selected-baseline" in calls[0]
            assert "-RecipeRef" not in calls[0] and "-Clean" not in calls[0]
            assert "-Force" in calls[0]
            assert machinery.started == []
            assert isinstance(app.screen, ConsoleDetail)
            assert "synthetic reset failure" in app.screen.body_text
            await pilot.press("escape")
            state = app._controller.state("campaign-1")
            assert state.stage == "failed"
            assert "synthetic reset failure" in state.detail

    asyncio.run(scenario())


def test_initialized_campaign_gets_one_real_tab(tmp_path):
    from textual.widgets import TabbedContent

    from tests.autoresearch.test_campaign_controller import FakeMachinery

    machinery = FakeMachinery()
    app, layout = _console(tmp_path, machinery)

    def run(arguments):
        if "tools.initialize_campaign" in arguments:
            (layout.folder(3) / ".git").mkdir(parents=True)
        return subprocess.CompletedProcess(arguments, 0, stdout="", stderr="")

    app._controller._runner = run

    async def scenario():
        async with app.run_test(size=(120, 45)) as pilot:
            await _run_batch(app, pilot, "run 3")
            panes = [p.id for p in app.query_one(TabbedContent).query("TabPane")]
            assert panes == ["commands", "campaign-1", "campaign-2", "campaign-3"]
            assert len(machinery.started) == 3
            assert all(
                panel._campaign_root == layout.folder(slot)
                for slot in (1, 2, 3)
                for panel in [app.query_one(f"#panel-campaign-{slot}", CampaignPanel)]
            )

    asyncio.run(scenario())
