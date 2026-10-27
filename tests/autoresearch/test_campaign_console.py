"""Headless checks for the operator console.

Nothing real is launched, reset or stopped: the console drives the same fake
machinery used for the controller tests, so only UI wiring and lifecycle
behavior are validated. Campaign-2-style scientific folders are never touched.
"""

from __future__ import annotations

import asyncio
import subprocess
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from tui import controller as control
from tui.console import CampaignConsole, ConsoleDetail, SharedSettings
from tui.report import CampaignPanel


def _workspace(tmp_path: Path) -> control.WorkspaceLayout:
    root = tmp_path / "robot-learning-campaigns"
    root.mkdir()
    for slot in (1, 2):
        campaign = root / f"campaign-{slot}"
        (campaign / ".git").mkdir(parents=True)
    harness = tmp_path / "harness"
    harness.mkdir()
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


def test_console_opens_first_campaign_with_report_and_visible_command_composer(
    tmp_path,
):
    from tests.autoresearch.test_campaign_controller import FakeMachinery

    machinery = FakeMachinery()
    app, layout = _console(tmp_path, machinery)

    async def scenario():
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            from textual.widgets import TabbedContent

            tabs = app.query_one(TabbedContent)
            pane_ids = [pane.id for pane in tabs.query("TabPane")]
            assert pane_ids == ["campaign-1", "campaign-2"]
            assert tabs.active == "campaign-1"
            first_panel = app.query_one("#panel-campaign-1", CampaignPanel)
            assert first_panel.content_region.height >= 30
            assert (
                first_panel.query_one("#context").region.bottom
                <= first_panel.region.bottom
            )
            for slot in (1, 2):
                panel = app.query_one(f"#panel-campaign-{slot}", CampaignPanel)
                assert panel._campaign_root == layout.folder(slot)
            assert app.submit_command("deploy 2") is None
            await _run_batch(app, pilot, "run 9")
            log_text = "\n".join(app._command_history)
            assert "run 9" in log_text
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
            assert started_arguments[:2] == ["--campaign-root", str(layout.folder(1))]
            assert app._controller.state("campaign-1").stage == "running"

            await _run_batch(app, pilot, "stop all")
            child = machinery.children[layout.folder(1)]
            assert child.stop_requests == 1
            assert app._controller.state("campaign-1").stage == "stopping"

    asyncio.run(scenario())


def test_campaign_tabs_carry_a_state_colour(tmp_path):
    from textual.widgets import TabbedContent

    from tests.autoresearch.test_campaign_controller import FakeMachinery
    from tui.console import TAB_TAG_COLOURS, tab_tag

    machinery = FakeMachinery()
    app, _ = _console(tmp_path, machinery)

    def dot(tab):
        label = tab.label
        assert label.plain == f"● {tab.id.removeprefix('--content-tab-')}"
        return str(label.spans[0].style)

    async def scenario():
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            tabs = app.query_one(TabbedContent)
            first, second = tabs.get_tab("campaign-1"), tabs.get_tab("campaign-2")
            assert dot(first) == dot(second) == TAB_TAG_COLOURS["quiet"]
            await _run_batch(app, pilot, "start 1")
            await pilot.pause()
            assert dot(first) == TAB_TAG_COLOURS["running"]
            assert dot(second) == TAB_TAG_COLOURS["quiet"]
            app._controller.state("campaign-1").stage = "failed"
            app._refresh_status_now()
            assert dot(first) == TAB_TAG_COLOURS["failed"]

    asyncio.run(scenario())
    assert tab_tag("running", stalled=True) == "attention"
    assert tab_tag("stopping", stalled=False) == "attention"
    assert tab_tag("completed", stalled=False) == "completed"
    assert tab_tag("idle", stalled=True) == "quiet"


def test_tab_phase_dot_follows_a_hidden_tab_and_pulses(tmp_path):
    from textual.widgets import TabbedContent

    from tests.autoresearch.test_campaign_controller import FakeMachinery
    from tui.console import PULSING_TAGS, TAB_TAG_COLOURS, tab_tag
    from tui.observations import Observation

    class _Feed:
        rejected = None

        def __init__(self) -> None:
            self.events: list = []

        def poll(self):
            events, self.events = self.events, []
            return events

    machinery = FakeMachinery()
    app, _ = _console(tmp_path, machinery)

    def label_of(tab):
        return tab.label.plain, str(tab.label.spans[0].style)

    async def scenario():
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            tabs = app.query_one(TabbedContent)
            assert tabs.active == "campaign-1"
            hidden = app.query_one("#panel-campaign-2", CampaignPanel)
            feed = _Feed()
            hidden._feed = feed
            app._controller.state("campaign-2").stage = "running"
            feed.events = [
                Observation(
                    "operation_started",
                    datetime.now(tz=UTC),
                    {"kind": "training"},
                    operation_id="T1",
                    session_id="S1",
                )
            ]
            hidden._master_tick()
            assert hidden._hidden, "campaign-2 must be treated as a hidden tab"
            assert hidden.phase() == "training"
            tab = tabs.get_tab("campaign-2")
            app._pulse_on = True
            app._refresh_tab_tags()
            assert label_of(tab) == ("● campaign-2", TAB_TAG_COLOURS["training"])
            app._pulse_tabs()
            assert label_of(tab)[0] == "◐ campaign-2"
            app._pulse_tabs()
            assert label_of(tab)[0] == "● campaign-2"
            first = tabs.get_tab("campaign-1")
            assert label_of(first)[0] == "● campaign-1"

    asyncio.run(scenario())
    assert tab_tag("running", False, "training") == "training"
    assert tab_tag("running", True, "training") == "attention"
    assert tab_tag("failed", False, "training") == "failed"
    assert tab_tag("idle", False, "training") == "quiet"
    assert tab_tag("running", False, "pi") == "running"
    assert tab_tag("completed", False, "none") == "completed"
    assert PULSING_TAGS == {"training", "evaluating", "coding", "official"}


def test_stop_is_not_queued_behind_an_unrelated_reset(tmp_path):
    from textual.widgets import Button, Input

    from tests.autoresearch.test_campaign_controller import FakeMachinery

    machinery = FakeMachinery()
    app, _ = _console(tmp_path, machinery)
    entered, release = threading.Event(), threading.Event()

    def reset(arguments):
        entered.set()
        assert release.wait(10)
        return subprocess.CompletedProcess(arguments, 0, stdout="", stderr="")

    app._controller._runner = reset

    async def scenario():
        async with app.run_test(size=(80, 24)) as pilot:
            await _run_batch(app, pilot, "start 1")
            app.submit_command("reset 2")
            try:
                assert await asyncio.to_thread(entered.wait, 5)
                worker = app._command_thread
                app.query_one("#commands-input", Input).value = "stop 1"
                await pilot.pause()
                assert not app.query_one("#execute-command", Button).disabled
                await pilot.click("#execute-command")
                await pilot.pause()
                assert next(iter(machinery.children.values())).stop_requests == 1
                assert app._command_thread is worker
                assert app._command_running
            finally:
                release.set()
                for _ in range(100):
                    await pilot.pause()
                    if not app._command_running:
                        break

    asyncio.run(scenario())


def test_shutdown_interrupts_reset_with_separate_grace(tmp_path, monkeypatch):
    from tests.autoresearch.test_campaign_controller import FakeMachinery
    from tui import console

    machinery = FakeMachinery()
    entered, release = threading.Event(), threading.Event()
    stopped = []
    app, _ = _console(tmp_path, machinery)
    monkeypatch.setattr(console, "HELPER_SHUTDOWN_GRACE_SECONDS", 0)
    app._last_stop_timeout = 3600

    def reset(arguments):
        entered.set()
        assert release.wait(10)
        return subprocess.CompletedProcess(
            arguments, 1, stdout="", stderr="reset interrupted"
        )

    def stop_helpers():
        stopped.append(True)
        release.set()

    machinery.stop_helpers = stop_helpers
    app._controller._runner = reset

    async def scenario():
        async with app.run_test(size=(80, 24)) as pilot:
            app.submit_command("reset 2")
            try:
                assert await asyncio.to_thread(entered.wait, 5)
                await pilot.press("ctrl+q")
                for _ in range(100):
                    await pilot.pause()
                    if not app.is_running:
                        break
                assert not app.is_running
                assert stopped == [True]
                assert not machinery.started
                assert app._controller.state("campaign-2").stage == "failed"
            finally:
                release.set()

    asyncio.run(scenario())


def test_stopped_campaign_clocks_freeze_and_resume_without_counting_the_pause(
    tmp_path, monkeypatch
):
    from tests.autoresearch.test_campaign_controller import FakeMachinery
    from tui import report

    clock = [datetime(2026, 10, 26, 12, tzinfo=UTC)]
    monkeypatch.setattr(report, "_now", lambda: clock[0])
    app, _ = _console(tmp_path, FakeMachinery())

    async def scenario():
        async with app.run_test(size=(160, 45)) as pilot:
            await pilot.pause()
            first = app.query_one("#panel-campaign-1", CampaignPanel)
            second = app.query_one("#panel-campaign-2", CampaignPanel)
            started = clock[0] - timedelta(minutes=10)
            stage = clock[0] - timedelta(minutes=2)
            for slot, panel in enumerate((first, second), start=1):
                state = {
                    "campaign": {
                        "id": f"campaign-{slot}",
                        "started_at": started.isoformat(),
                    }
                }
                panel._sources = SimpleNamespace(
                    read=lambda state=state: (state, [], [])
                )
                panel._stage_started = stage
                panel.refresh_snapshot()
            await _run_batch(app, pilot, "start 1")
            await _run_batch(app, pilot, "start 2")
            await _run_batch(app, pilot, "stop 1")
            app._controller.reap("campaign-1")
            app._refresh_status_now()
            frozen = first._clock_end(started)
            clock[0] += timedelta(minutes=20)
            first.tick_clock()
            first.refresh_snapshot()
            assert first._clock_end(started) == frozen
            assert second._clock_end(started) == clock[0]
            await _run_batch(app, pilot, "start 1")
            assert first._clock_end(started) == frozen
            clock[0] += timedelta(seconds=30)
            assert first._clock_end(started) == frozen + timedelta(seconds=30)
            assert first.snapshot.started_at == started
            assert first._clock_end(clock[0] - timedelta(seconds=10)) == clock[0]

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


@pytest.mark.parametrize("size", [(160, 45), (178, 33), (80, 24), (60, 24), (48, 16)])
def test_compact_console_contextual_command_and_copy_only(tmp_path, size):
    from textual.widgets import Footer, Input, TabbedContent

    from tests.autoresearch.test_campaign_controller import FakeMachinery

    machinery = FakeMachinery()
    app, layout = _console(tmp_path, machinery)

    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            assert not machinery.started
            command = app.query_one("#commands-input", Input)
            assert command.content_region.height >= 1
            assert command.content_region.width >= 8
            assert command.region.bottom <= size[1]
            assert command.region.y >= 0
            summary = app.query_one("#commands-summary")
            footer = app.query_one(Footer)
            assert summary.region.bottom <= command.region.y
            assert command.region.bottom <= footer.region.y
            for selector in ("#execute-command", "#show-settings"):
                button = app.query_one(selector)
                assert button.region.height >= 1
                assert 0 <= button.region.y < button.region.bottom <= size[1]
                assert button.region.right <= size[0]
            await pilot.press("tab")
            assert app.query_one(TabbedContent).active == "campaign-2"
            await _run_batch(app, pilot, "start")
            assert machinery.started[0][0] == layout.folder(2)
            app._settings_reader.values["cmd-max-inquiries"] = "invalid"
            await _run_batch(app, pilot, "stop")
            assert app._controller.state("campaign-2").stage == "stopping"
            await pilot.press("ctrl+c")
            assert app.is_running and not app._shutting_down
            assert machinery.forced == []
            if size == (48, 16):
                panel = app.query_one("#panel-campaign-2", CampaignPanel)
                assert panel.query_one("#too-small").display
                await pilot.resize_terminal(48, 23)
                await pilot.pause()
                assert not panel.query_one("#too-small").display

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
            await pilot.press("f2")
            await pilot.pause()
            assert isinstance(app.screen, SharedSettings)
            settings = app.screen
            settings.query_one("#reset-mode", Select).value = "Baseline"
            settings.query_one("#reset-baseline", Input).value = "selected-baseline"
            settings.query_one("#reset-clean", Checkbox).value = False
            await pilot.pause()
            assert not settings.query_one("#reset-recipe-field").display
            assert settings.query_one("#reset-baseline-field").display
            await pilot.click("#settings-apply")
            await pilot.pause()
            await _run_batch(app, pilot, "run 1-2")
            assert len(calls) == 2
            assert "baseline" in calls[0] and "selected-baseline" in calls[0]
            assert "--recipe-ref" not in calls[0] and "--clean" not in calls[0]
            assert "--force" in calls[0]
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
            await _run_batch(app, pilot, "run 1-3")
            panes = [p.id for p in app.query_one(TabbedContent).query("TabPane")]
            assert panes == ["campaign-1", "campaign-2", "campaign-3"]
            assert len(machinery.started) == 3
            assert all(
                panel._campaign_root == layout.folder(slot)
                for slot in (1, 2, 3)
                for panel in [app.query_one(f"#panel-campaign-{slot}", CampaignPanel)]
            )

    asyncio.run(scenario())


def test_execute_button_submits_from_first_campaign_and_settings_cancel_is_read_only(
    tmp_path,
):
    from textual.widgets import Input, TabbedContent

    from tests.autoresearch.test_campaign_controller import FakeMachinery

    machinery = FakeMachinery()
    app, layout = _console(tmp_path, machinery)

    async def scenario():
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "campaign-1"
            await pilot.click("#show-settings")
            await pilot.pause()
            app.screen.query_one("#cmd-model", Input).value = "must-not-apply"
            await pilot.press("escape")
            await pilot.pause()
            assert app._settings_reader.settings().model is None
            assert machinery.started == []
            await pilot.press("f2")
            await pilot.pause()
            app.screen.query_one("#cmd-model", Input).value = "selected-model"
            await pilot.click("#settings-apply")
            await pilot.pause()
            assert machinery.started == []
            app.query_one("#commands-input", Input).value = "start"
            await pilot.click("#execute-command")
            for _ in range(100):
                await pilot.pause()
                if not app._command_running:
                    break
            assert len(machinery.started) == 1
            assert machinery.started[0][0] == layout.folder(1)
            assert "must-not-apply" not in machinery.started[0][1]
            assert "selected-model" in machinery.started[0][1]
            assert "-MaxInquiries" not in machinery.started[0][1]

    asyncio.run(scenario())


def test_empty_console_has_no_fake_campaign_or_commands_tab(tmp_path):
    from textual.widgets import Input, TabbedContent

    from tests.autoresearch.test_campaign_controller import FakeMachinery

    app, layout = _console(tmp_path, FakeMachinery())
    app._layout = control.WorkspaceLayout(layout.harness_root, tmp_path / "empty")
    app._controller._layout = app._layout

    async def scenario():
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            assert not list(app.query_one(TabbedContent).query("TabPane"))
            assert app.query_one("#empty-campaigns").display
            assert app.query_one("#commands-input", Input).content_region.height >= 1
            assert not app._command_running
            await pilot.press("ctrl+l", "ctrl+l")
            await pilot.pause()
            assert app.focused is app.query_one("#commands-input", Input)
            assert not app._command_running

    asyncio.run(scenario())


def test_tab_switches_campaigns_but_navigates_fields_inside_settings(tmp_path):
    from textual.widgets import Input, TabbedContent

    from tests.autoresearch.test_campaign_controller import FakeMachinery

    machinery = FakeMachinery()
    app, _ = _console(tmp_path, machinery)

    async def scenario():
        async with app.run_test(size=(160, 45)) as pilot:
            tabs = app.query_one(TabbedContent)
            command = app.query_one("#commands-input", Input)
            command.value = "start 2"
            await pilot.press("tab")
            assert tabs.active == "campaign-2"
            await pilot.press("shift+tab")
            assert tabs.active == "campaign-1"
            assert command.value == "start 2"
            app.query_one("#panel-campaign-1 #output").focus()
            await pilot.pause()
            await pilot.press("tab")
            await pilot.pause()
            assert tabs.active == "campaign-2"
            await pilot.press("shift+tab")
            await pilot.pause()
            assert tabs.active == "campaign-1"
            await pilot.press("ctrl+l", "tab")
            await pilot.pause()
            assert tabs.active == "campaign-2"
            assert app.query_one("#console-controls").has_class("collapsed")
            await pilot.press("f2")
            await pilot.pause()
            settings = app.screen
            assert isinstance(settings, SharedSettings)
            focused = app.focused
            await pilot.press("tab")
            assert app.screen is settings and app.focused is not focused
            assert tabs.active == "campaign-2"
            await pilot.press("shift+tab")
            assert app.focused is focused
            await pilot.press("escape", "shift+tab")
            await pilot.pause()
            assert tabs.active == "campaign-1"
            assert not machinery.started

    asyncio.run(scenario())


@pytest.mark.parametrize("size", [(160, 45), (60, 24)])
def test_ctrl_l_toggles_commands_preserves_draft_and_reclaims_report_space(
    tmp_path, size
):
    from textual.widgets import Footer, Input, TabbedContent

    from tests.autoresearch.test_campaign_controller import FakeMachinery

    machinery = FakeMachinery()
    app, _ = _console(tmp_path, machinery)

    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            command = app.query_one("#commands-input", Input)
            command.value = "start campaign-2"
            panel = app.query_one("#panel-campaign-1", CampaignPanel)
            expanded_height = panel.region.height
            await pilot.press("ctrl+l")
            await pilot.pause()
            assert app.query_one("#console-controls").has_class("collapsed")
            assert app.query_one("#command-row").region.height == 0
            assert app.query_one(Footer).region.height == 1
            assert panel.region.height == expanded_height + 4
            assert app.focused is not command
            assert app.focused in list(panel.query("*"))

            # A tab change or settings dialog must not reopen a hidden composer.
            await pilot.press("ctrl+tab")
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "campaign-2"
            await pilot.press("f2")
            await pilot.pause()
            app.screen.query_one("#cmd-model", Input).value = "future-model"
            await pilot.click("#settings-apply")
            await pilot.pause()
            assert app.query_one("#console-controls").has_class("collapsed")
            assert app._settings_reader.settings().model == "future-model"
            await pilot.press("f2", "escape")
            await pilot.pause()
            assert app.query_one("#console-controls").has_class("collapsed")

            await pilot.press("ctrl+l")
            await pilot.pause()
            assert not app.query_one("#console-controls").has_class("collapsed")
            assert app.focused is command
            assert command.value == "start campaign-2"
            assert (
                app.query_one("#panel-campaign-2", CampaignPanel).region.height
                == expanded_height
            )
            assert machinery.started == []

    asyncio.run(scenario())


@pytest.mark.parametrize("size", [(60, 24), (48, 16)])
def test_settings_remain_scrollable_with_visible_apply_and_cancel_at_the_floor(
    tmp_path, size
):
    from tests.autoresearch.test_campaign_controller import FakeMachinery

    machinery = FakeMachinery()
    app, _ = _console(tmp_path, machinery)

    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.press("f2")
            await pilot.pause()
            settings = app.screen
            assert isinstance(settings, SharedSettings)
            for selector in ("#settings-apply", "#settings-cancel"):
                button = settings.query_one(selector)
                assert button.content_region.height >= 1
                assert 0 <= button.region.y < button.region.bottom <= size[1]
            settings.query_one("#reset-recipe").focus()
            await pilot.pause(0.5)
            field = settings.query_one("#reset-recipe")
            viewport = settings.query_one("#settings-scroll")
            assert viewport.content_region.contains_region(field.content_region)
            await pilot.press("escape")
            assert machinery.started == []

    asyncio.run(scenario())
