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
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

import pytest

from tui import controller as control
from tui.console import CampaignConsole, ConsoleDetail, SharedSettings
from tui.report import CampaignPanel


@pytest.mark.parametrize(
    "folder",
    [
        PureWindowsPath(r"C:\a-long-workspace\robot-learning-campaigns\campaign-1"),
        PureWindowsPath("C:\\a-long-workspace\\研究-e\u0301\\campaign-1"),
    ],
)
def test_tab_folder_text_preserves_parent_and_uses_terminal_cell_width(folder):
    from rich.cells import cell_len

    from tui.phase_presentation import tab_folder_text

    compact = str(folder.with_segments("...", folder.parent.name, folder.name))
    width = cell_len(compact)
    assert tab_folder_text(folder, cell_len(str(folder))) == str(folder)
    assert tab_folder_text(folder, width) == compact
    assert tab_folder_text(folder, width - 1) == ""


def test_campaign_folder_is_flush_right_without_crowding_tabs_or_reducing_log(tmp_path):
    from textual.widgets import Static, TabbedContent, Tabs

    from tests.autoresearch.test_campaign_controller import FakeMachinery

    app, layout = _console(tmp_path, FakeMachinery())
    for slot in (3, 4, 5):
        (layout.folder(slot) / ".git").mkdir(parents=True)

    async def scenario():
        async with app.run_test(size=(160, 45)) as pilot:
            await pilot.pause()
            tabs = app.query_one(TabbedContent)
            bar = tabs.query_one(Tabs)
            location = app.query_one("#campaign-folder", Static)
            assert location.display
            assert location.region.right == bar.region.right
            assert location.region.y == tabs.get_tab(tabs.active).region.y
            assert str(layout.folder(1)) == location.tooltip

            location.display = False
            await pilot.pause()
            assert not location.display
            output = app.query_one("#panel-campaign-1 #output")
            baseline_output = output.region
            baseline_tabs = [tabs.get_tab(label).region for label in app._visible_tabs]
            app._refresh_campaign_folder()
            await pilot.pause()
            assert output.region == baseline_output
            assert [
                tabs.get_tab(label).region for label in app._visible_tabs
            ] == baseline_tabs
            assert all(tab.right <= location.region.x for tab in baseline_tabs)

            await pilot.press("tab", "tab")
            await pilot.pause()
            assert tabs.active == "campaign-3"
            assert location.tooltip == str(layout.folder(3))

            for size in ((80, 24), (60, 24), (48, 16)):
                await pilot.resize_terminal(*size)
                await pilot.pause()
                assert not location.display
                summary = app.query_one("#commands-summary")
                assert summary.region.height == 1
                assert summary.region.bottom == size[1]
                assert tabs.active == "campaign-3"
            await pilot.resize_terminal(160, 45)
            await pilot.pause()
            assert location.display
            assert location.region.right == bar.region.right

            app.submit_command("hide 1-5")
            await pilot.pause()
            assert not location.display
            app.submit_command("show 1-5")
            await pilot.pause()
            assert location.display

            await app._show_diagnostics([3])
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ConsoleDetail)
            assert str(layout.folder(3)) in screen.body_text

    asyncio.run(scenario())


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
    from tui.tab_visibility import TabIdleTracker

    layout = _workspace(tmp_path)
    app = CampaignConsole(
        harness_root=layout.harness_root,
        campaigns_root=layout.campaigns_root,
        machinery=machinery,
    )
    app._idle_tracker = TabIdleTracker(tmp_path / "tab-control")
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


async def _type(pilot, text: str) -> None:
    await pilot.press(*("space" if char == " " else char for char in text))


async def _run_from_panel(app, pilot, text: str) -> None:
    """Run a command the way the operator does: ``/``, type, Enter."""
    await pilot.press("slash")
    await _type(pilot, text)
    await pilot.press("enter")
    for _ in range(100):
        await pilot.pause()
        if not app._command_running:
            break
    await pilot.pause()


async def _run_batch(app, pilot, text: str) -> None:
    app.submit_command(text)
    for _ in range(100):
        await pilot.pause()
        if not app._command_running:
            break
    await pilot.pause()


def test_console_opens_first_campaign_with_report_and_one_info_line(
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


def test_a_hidden_tab_follows_a_new_campaign_in_its_folder(tmp_path):
    import json

    from tests.autoresearch.test_campaign_controller import FakeMachinery
    from tui.journal import journal_path_for

    machinery = FakeMachinery()
    app, layout = _console(tmp_path, machinery)
    folder = layout.folder(2)

    def publish_state(campaign_id: str) -> None:
        path = folder / "runner" / "state" / "research_state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"campaign": {"id": campaign_id}}), "utf-8")

    def publish_event(campaign_id: str, event_kind: str, **fields) -> None:
        path = journal_path_for(campaign_id, folder)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "schema_version": 2,
            "event_id": f"{event_kind}-{campaign_id}",
            "campaign_id": campaign_id,
            "ts": datetime.now(tz=UTC).isoformat(),
            "kind": event_kind,
            "scope": "",
            "severity": "info",
            "session_id": "S1",
            "operation_id": "T1",
            "inquiry_id": "",
            "attempt": "",
            "actor": "runner",
            "payload": fields,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    publish_state("old-campaign")

    async def scenario():
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            hidden = app.query_one("#panel-campaign-2", CampaignPanel)
            hidden._master_tick()
            assert hidden._hidden and hidden.phase() == "none"
            # A new run gives the folder a new campaign while this tab is hidden.
            publish_state("new-campaign")
            publish_event("new-campaign", "operation_started", kind="training")
            hidden._master_tick()
            assert hidden.phase() == "training"

    asyncio.run(scenario())


def test_a_campaign_started_elsewhere_still_colours_and_pulses_its_tab(tmp_path):
    from textual.widgets import TabbedContent

    from tests.autoresearch.test_campaign_controller import FakeMachinery
    from tui.console import TAB_TAG_COLOURS
    from tui.observations import Observation

    class _Feed:
        rejected = None

        def __init__(self, events) -> None:
            self.events = events

        def poll(self):
            events, self.events = self.events, []
            return events

    app, _ = _console(tmp_path, FakeMachinery())
    app._controller._external = SimpleNamespace(running=lambda folder: True)

    def label_of(tab):
        return tab.label.plain, str(tab.label.spans[0].style)

    async def scenario():
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            tabs = app.query_one(TabbedContent)
            hidden = app.query_one("#panel-campaign-2", CampaignPanel)
            hidden._feed = _Feed(
                [
                    Observation(
                        "operation_started",
                        datetime.now(tz=UTC),
                        {"kind": "training"},
                        operation_id="T1",
                        session_id="S1",
                    )
                ]
            )
            hidden._master_tick()
            state = app._controller.state("campaign-2")
            assert state.stage == "idle"
            app._controller.reap("campaign-2")
            assert state.external
            app._pulse_on = True
            app._refresh_tab_tags()
            tab = tabs.get_tab("campaign-2")
            assert label_of(tab) == ("● campaign-2", TAB_TAG_COLOURS["training"])
            app._pulse_tabs()
            assert label_of(tab)[0] == "◐ campaign-2"

    asyncio.run(scenario())


def test_the_tab_shows_the_final_benchmark_outcome_once_the_campaign_stopped(tmp_path):
    from textual.widgets import TabbedContent

    from tests.autoresearch.test_campaign_controller import FakeMachinery
    from tui import projector
    from tui.console import OUTCOME_TAGS, TAB_TAG_COLOURS, tab_tag
    from tui.demo import demo_snapshot_args

    assert tab_tag("completed", False, "none", "passed") == "official_passed"
    assert tab_tag("idle", False, "none", "failed") == "official_failed"
    assert tab_tag("stopped", False, "none", "failed") == "official_failed"
    # A running campaign shows its phase; a failed launcher keeps its red dot.
    assert tab_tag("running", False, "training", "failed") == "training"
    assert tab_tag("failed", False, "none", "passed") == "failed"
    assert tab_tag("completed", False, "none", "") == "completed"
    assert OUTCOME_TAGS == {"official_passed", "official_failed"}

    app, _ = _console(tmp_path, FakeMachinery())

    def label_of(tab):
        return tab.label.plain, str(tab.label.spans[0].style)

    def with_outcome(status):
        state, records, usage = demo_snapshot_args()
        state["official_assessment"] = {
            "status": status,
            "model": "T1:checkpoint-10",
            "summary": "goal not reached; success 97.5%; 200 episodes",
        }
        return projector.build_snapshot(state, records, usage)

    async def scenario():
        async with app.run_test(size=(120, 45)) as pilot:
            await pilot.pause()
            tabs = app.query_one(TabbedContent)
            for label, status in (("campaign-1", "passed"), ("campaign-2", "failed")):
                panel = app.query_one(f"#panel-{label}", CampaignPanel)
                panel.snapshot = with_outcome(status)
                app._controller.state(label).stage = "completed"
            app._pulse_on = False
            app._refresh_tab_tags()
            assert label_of(tabs.get_tab("campaign-1")) == (
                "◆ campaign-1",
                TAB_TAG_COLOURS["official_passed"],
            )
            assert label_of(tabs.get_tab("campaign-2")) == (
                "◆ campaign-2",
                TAB_TAG_COLOURS["official_failed"],
            )
            assert "official assessment: goal not reached" in app._status_line() or (
                "official assessment: goal reached" in app._status_line()
            )
            app._pulse_tabs()
            assert label_of(tabs.get_tab("campaign-2"))[0] == "◆ campaign-2"

    asyncio.run(scenario())


def test_stop_is_not_queued_behind_an_unrelated_reset(tmp_path):
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
                await pilot.press("slash")
                await _type(pilot, "stop 1")
                await pilot.press("enter")
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
                panel.activity.stage_started = stage
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
def test_compact_console_one_info_line_and_copy_only(tmp_path, size):
    from textual.widgets import Input, TabbedContent

    from tests.autoresearch.test_campaign_controller import FakeMachinery

    machinery = FakeMachinery()
    app, layout = _console(tmp_path, machinery)

    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            assert not machinery.started
            summary = app.query_one("#commands-summary")
            assert summary.region.height == 1
            assert summary.region.bottom == size[1]
            assert app.query_one("#command-panel").region.height == 0
            assert not app.query("#execute-command") and not app.query("#show-settings")
            await pilot.press("slash")
            await pilot.pause()
            command = app.query_one("#commands-input", Input)
            assert command.content_region.height >= 1
            assert command.content_region.width >= 8
            assert 0 <= command.region.y and command.region.bottom <= summary.region.y
            assert app.focused is command
            await pilot.press("escape", "tab")
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


def test_a_new_external_slot_is_inserted_in_order_without_changing_selection(tmp_path):
    from textual.widgets import TabbedContent

    from tests.autoresearch.test_campaign_controller import FakeMachinery

    app, layout = _console(tmp_path, FakeMachinery())
    # Begin with only slot 2 installed; slot 1 is installed elsewhere later.
    (layout.folder(1) / ".git").rmdir()
    app._controller._external = SimpleNamespace(
        running=lambda folder: folder == layout.folder(1)
    )

    async def scenario():
        async with app.run_test(size=(80, 24)) as pilot:
            tabs = app.query_one(TabbedContent)
            assert tabs.active == "campaign-2"
            (layout.folder(1) / ".git").mkdir()
            await app._refresh_status()
            await pilot.pause()
            assert app._visible_tabs == ["campaign-1", "campaign-2"]
            assert tabs.active == "campaign-2"
            assert (
                tabs.get_tab("campaign-1").region.x
                < tabs.get_tab("campaign-2").region.x
            )
            assert not app._controller._machinery.started

    asyncio.run(scenario())


def test_settings_cancel_is_read_only_and_a_command_uses_applied_settings(
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
            await _run_from_panel(app, pilot, "settings")
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
            await _run_from_panel(app, pilot, "start")
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
            assert app.query_one("#empty-campaigns").content_region.height > 0
            assert app.query_one("#commands-summary").region.height == 1
            assert not app._command_running
            await pilot.press("ctrl+l")
            await pilot.pause()
            assert app.focused is app.query_one("#commands-input", Input)
            assert app.query_one("#command-panel").region.height > 1
            await pilot.press("escape")
            await pilot.pause()
            assert app.query_one("#command-panel").region.height == 0
            assert not app._command_running

    asyncio.run(scenario())


@pytest.mark.parametrize("size", [(160, 45), (80, 24), (60, 24), (48, 16)])
def test_idle_tabs_hide_at_two_hours_and_show_hide_are_session_only(
    tmp_path, monkeypatch, size
):
    from textual.widgets import TabbedContent

    from tests.autoresearch.test_campaign_controller import FakeMachinery
    from tui import console
    from tui.tab_visibility import IDLE_TAB_SECONDS

    now = [1000.0]
    monkeypatch.setattr(console.time, "time", lambda: now[0])
    machinery = FakeMachinery()
    app, layout = _console(tmp_path, machinery)

    async def scenario():
        async with app.run_test(size=size) as pilot:
            tabs = app.query_one(TabbedContent)
            await pilot.pause()
            now[0] += IDLE_TAB_SECONDS - 1
            await app._refresh_status()
            assert app._visible_tabs == ["campaign-1", "campaign-2"]
            now[0] += 1
            await app._refresh_status()
            await pilot.pause()
            assert app._visible_tabs == [] and tabs.active == ""
            assert all(
                tabs.get_tab(f"campaign-{n}").has_class("-hidden") for n in (1, 2)
            )
            assert app.query_one("#empty-campaigns").display
            await _run_from_panel(app, pilot, "show 2")
            assert tabs.active == "campaign-2"
            assert app._visible_tabs == ["campaign-2"]
            now[0] += IDLE_TAB_SECONDS
            await app._refresh_status()
            assert app._visible_tabs == ["campaign-2"]
            await _run_from_panel(app, pilot, "show 1")
            assert (
                tabs.active == "campaign-2"
            )  # showing another tab does not steal focus
            await pilot.press("tab")
            assert tabs.active == "campaign-1"
            await _run_from_panel(app, pilot, "hide")
            assert tabs.active == "campaign-2"
            assert machinery.started == [] and machinery.forced == []
            assert not app._controller.shutting_down
            await _run_from_panel(app, pilot, "show 5")
            assert app._visible_tabs == ["campaign-2"]
            assert "not initialized" in app._command_history[-1]
            await _run_from_panel(app, pilot, "hide 5")
            panel = app.query_one("#panel-campaign-2", CampaignPanel)
            assert app.focused in list(panel.query("*"))

    asyncio.run(scenario())

    reopened = CampaignConsole(
        harness_root=layout.harness_root,
        campaigns_root=layout.campaigns_root,
        machinery=FakeMachinery(),
    )
    reopened._idle_tracker = app._idle_tracker

    async def restart():
        async with reopened.run_test(size=size) as pilot:
            await pilot.pause()
            assert reopened._visible_tabs == []  # the deadline persists, /show does not

    asyncio.run(restart())


def test_hidden_running_tabs_remain_controlled_and_start_shows_them_again(
    tmp_path, monkeypatch
):
    from textual.widgets import TabbedContent

    from tests.autoresearch.test_campaign_controller import FakeMachinery
    from tui import console
    from tui.tab_visibility import IDLE_TAB_SECONDS

    now = [1000.0]
    monkeypatch.setattr(console.time, "time", lambda: now[0])
    machinery = FakeMachinery()
    app, layout = _console(tmp_path, machinery)

    async def scenario():
        async with app.run_test(size=(80, 24)) as pilot:
            await _run_batch(app, pilot, "start 1-2")
            now[0] += 3 * IDLE_TAB_SECONDS
            await app._refresh_status()
            assert app._visible_tabs == ["campaign-1", "campaign-2"]
            await _run_from_panel(app, pilot, "hide 1")
            child = machinery.children[layout.folder(1)]
            assert child.stop_requests == 0 and not child.forced
            assert "1 running campaign hidden" in app._summary
            await app._refresh_status()
            assert app._visible_tabs == ["campaign-2"]
            await pilot.press("tab")
            assert app.query_one(TabbedContent).active == "campaign-2"
            await _run_batch(app, pilot, "stop all")
            assert all(
                child.stop_requests == 1 for child in machinery.children.values()
            )
            await app._refresh_status()
            await _run_batch(app, pilot, "start 1")
            assert app._visible_tabs == ["campaign-1", "campaign-2"]
            app._controller._runner = lambda args: subprocess.CompletedProcess(
                args, 0, stdout="", stderr=""
            )
            await _run_from_panel(app, pilot, "hide 2")
            await _run_batch(app, pilot, "run 2")
            assert app._visible_tabs == ["campaign-1", "campaign-2"]
            await _run_from_panel(app, pilot, "hide 1-2")
            assert app._visible_tabs == []
            await pilot.press("ctrl+q")
            deadline = time.monotonic() + 5
            while app.is_running and time.monotonic() < deadline:
                await pilot.pause()
            assert not app.is_running
            assert machinery.children[layout.folder(1)].stop_requests == 1
            assert app._controller.state("campaign-1").child is None

    asyncio.run(scenario())


def test_kill_all_includes_hidden_launchers(tmp_path):
    from tests.autoresearch.test_campaign_controller import FakeMachinery

    machinery = FakeMachinery()
    app, _ = _console(tmp_path, machinery)

    async def scenario():
        async with app.run_test(size=(80, 24)) as pilot:
            await _run_batch(app, pilot, "start 1-2")
            await _run_from_panel(app, pilot, "hide 1-2")
            await _run_from_panel(app, pilot, "kill all")
            deadline = time.monotonic() + 5
            while len(machinery.forced) != 2 and time.monotonic() < deadline:
                await pilot.pause()
            assert len(machinery.forced) == 2
            assert all(
                app._controller.state(f"campaign-{n}").child is None for n in (1, 2)
            )
            assert app._visible_tabs == []

    asyncio.run(scenario())


def test_unreadable_idle_metadata_keeps_the_tab_visible_and_reports_the_error(
    tmp_path, monkeypatch
):
    from tests.autoresearch.test_campaign_controller import FakeMachinery
    from tui import console
    from tui.tab_visibility import IDLE_TAB_SECONDS

    now = [1000.0]
    monkeypatch.setattr(console.time, "time", lambda: now[0])
    app, _ = _console(tmp_path, FakeMachinery())

    async def scenario():
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            for record in app._idle_tracker.directory.glob("*.json"):
                record.write_text("invalid", encoding="utf-8")
            now[0] += IDLE_TAB_SECONDS
            await app._refresh_status()
            assert app._visible_tabs == ["campaign-1", "campaign-2"]
            assert "cannot establish tab idle time" in app._command_history[-1]
            count = len(app._command_history)
            await app._refresh_status()
            assert len(app._command_history) == count  # no warning on every refresh

    asyncio.run(scenario())


def test_an_external_campaign_reappears_without_a_recent_log_or_focus_change(
    tmp_path, monkeypatch
):
    from textual.widgets import TabbedContent

    from tests.autoresearch.test_campaign_controller import FakeMachinery
    from tui import console
    from tui.tab_visibility import IDLE_TAB_SECONDS

    now = [1000.0]
    monkeypatch.setattr(console.time, "time", lambda: now[0])
    app, layout = _console(tmp_path, FakeMachinery())
    external = set()
    app._controller._external = SimpleNamespace(
        running=lambda folder: folder in external
    )

    async def scenario():
        async with app.run_test(size=(80, 24)) as pilot:
            now[0] += IDLE_TAB_SECONDS
            await app._refresh_status()
            assert not app._visible_tabs
            app.submit_command("show 1")
            tabs = app.query_one(TabbedContent)
            external.add(layout.folder(2))
            await app._refresh_status()
            await pilot.pause()
            assert app._visible_tabs == ["campaign-1", "campaign-2"]
            assert tabs.active == "campaign-1"
            now[0] += 5 * IDLE_TAB_SECONDS
            await app._refresh_status()
            assert "campaign-2" in app._visible_tabs
            app._controller._external.request_stop = lambda folder: None
            await _run_batch(app, pilot, "stop 2")
            assert "campaign-2" in app._visible_tabs
            external.clear()
            await app._refresh_status()
            assert not app._controller.state("campaign-2").external
            now[0] += IDLE_TAB_SECONDS
            await app._refresh_status()
            assert app._visible_tabs == ["campaign-1"]

    asyncio.run(scenario())


def test_tab_switches_campaigns_completes_in_the_panel_and_navigates_settings(
    tmp_path,
):
    from textual.widgets import Input, TabbedContent

    from tests.autoresearch.test_campaign_controller import FakeMachinery

    machinery = FakeMachinery()
    app, _ = _console(tmp_path, machinery)

    async def scenario():
        async with app.run_test(size=(160, 45)) as pilot:
            tabs = app.query_one(TabbedContent)
            await pilot.press("tab")
            assert tabs.active == "campaign-2"
            await pilot.press("shift+tab")
            assert tabs.active == "campaign-1"
            app.query_one("#panel-campaign-1 #output").focus()
            await pilot.pause()
            await pilot.press("tab")
            await pilot.pause()
            assert tabs.active == "campaign-2"
            await pilot.press("shift+tab")
            await pilot.pause()
            assert tabs.active == "campaign-1"
            # In the panel, Tab completes the highlighted command and keeps the tab.
            await pilot.press("slash", "s", "t", "tab")
            await pilot.pause()
            command = app.query_one("#commands-input", Input)
            assert command.value == "start "
            assert tabs.active == "campaign-1"
            await pilot.press("escape")
            await pilot.pause()
            await pilot.press("f2")
            await pilot.pause()
            settings = app.screen
            assert isinstance(settings, SharedSettings)
            focused = app.focused
            await pilot.press("tab")
            assert app.screen is settings and app.focused is not focused
            assert tabs.active == "campaign-1"
            await pilot.press("shift+tab")
            assert app.focused is focused
            await pilot.press("escape", "tab")
            await pilot.pause()
            assert tabs.active == "campaign-2"
            assert not machinery.started

    asyncio.run(scenario())


@pytest.mark.parametrize("size", [(160, 45), (60, 24)])
def test_the_command_panel_opens_closes_and_returns_the_space_and_focus(tmp_path, size):
    from textual.widgets import Input

    from tests.autoresearch.test_campaign_controller import FakeMachinery

    machinery = FakeMachinery()
    app, _ = _console(tmp_path, machinery)

    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            panel = app.query_one("#panel-campaign-1", CampaignPanel)
            closed_height = panel.region.height
            before = app.focused
            await pilot.press("slash")
            await pilot.pause()
            command = app.query_one("#commands-input", Input)
            assert app.focused is command
            assert panel.region.height < closed_height
            # "/" typed inside the open panel is text, not a second open.
            await pilot.press("slash")
            assert command.value == "/"
            await pilot.press("escape")
            await pilot.pause()
            assert app.query_one("#command-panel").region.height == 0
            assert panel.region.height == closed_height
            assert app.focused is before
            assert command.value == ""
            await pilot.press("ctrl+l", "ctrl+l")
            await pilot.pause()
            assert app.query_one("#command-panel").region.height == 0
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


def test_the_list_filters_and_enter_completes_a_name_or_runs_a_command(tmp_path):
    from textual.widgets import Input, OptionList

    from tests.autoresearch.test_campaign_controller import FakeMachinery

    machinery = FakeMachinery()
    app, layout = _console(tmp_path, machinery)

    async def scenario():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("slash")
            options = app.query_one("#command-list", OptionList)
            assert [c.name for c in app._listed][:2] == ["start", "run"]
            await pilot.press("k", "i")
            assert [c.name for c in app._listed] == ["kill"]
            await pilot.press("backspace", "backspace", "s", "t")
            assert [c.name for c in app._listed][:2] == ["start", "stop"]
            await pilot.press("down")
            assert options.highlighted == 1
            await pilot.press("up", "enter")
            command = app.query_one("#commands-input", Input)
            # A part of a name completes; nothing runs yet.
            assert command.value == "start "
            assert app._panel_open and machinery.started == []
            await pilot.press("enter")
            for _ in range(100):
                await pilot.pause()
                if not app._command_running:
                    break
            assert not app._panel_open
            assert machinery.started[-1][0] == layout.folder(1)

    asyncio.run(scenario())


def test_slash_search_opens_the_log_search_and_help_lists_the_commands(tmp_path):
    from tests.autoresearch.test_campaign_controller import FakeMachinery
    from tui.console import help_text

    app, _ = _console(tmp_path, FakeMachinery())

    async def scenario():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            panel = app.query_one("#panel-campaign-1", CampaignPanel)
            assert not panel._search_visible
            await _run_from_panel(app, pilot, "search")
            assert panel._search_visible
            await pilot.press("escape")
            await pilot.press("ctrl+f")
            await pilot.pause()
            assert panel._search_visible
            await pilot.press("escape")
            for name in control.COMMANDS:
                assert f"/{name}" in help_text()

    asyncio.run(scenario())


def test_quit_leaves_the_campaigns_running(tmp_path):
    from tests.autoresearch.test_campaign_controller import FakeMachinery

    machinery = FakeMachinery()
    app, layout = _console(tmp_path, machinery)

    async def scenario():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await _run_batch(app, pilot, "start 1")
            child = machinery.children[layout.folder(1)]
            await _run_from_panel(app, pilot, "quit")
            await pilot.pause()
            assert not app.is_running
            assert machinery.detached == [child]
            assert child.stop_requests == 0 and not child.forced
            assert app._shutdown_complete
            assert app._detached == ["campaign-1"]

    asyncio.run(scenario())


def test_alt_q_leaves_the_campaigns_running_and_quit_stop_stops_them(tmp_path):
    from tests.autoresearch.test_campaign_controller import FakeMachinery

    machinery = FakeMachinery()
    app, layout = _console(tmp_path, machinery)

    async def scenario():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await _run_batch(app, pilot, "start 1")
            await pilot.press("alt+q")
            await pilot.pause()
            assert not app.is_running
            assert len(machinery.detached) == 1

    asyncio.run(scenario())

    machinery = FakeMachinery()
    (tmp_path / "second").mkdir()
    app, layout = _console(tmp_path / "second", machinery)

    async def stopping():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await _run_batch(app, pilot, "start 1")
            await _run_from_panel(app, pilot, "quit stop")
            deadline = time.monotonic() + 5
            while app.is_running and time.monotonic() < deadline:
                await pilot.pause()
            assert machinery.children[layout.folder(1)].stop_requests == 1
            assert machinery.detached == []

    asyncio.run(stopping())


def test_a_quit_is_refused_while_a_start_or_reset_runs(tmp_path):
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
        async with app.run_test(size=(120, 40)) as pilot:
            app.submit_command("reset 2")
            try:
                assert await asyncio.to_thread(entered.wait, 5)
                await pilot.press("alt+q")
                await pilot.pause()
                assert app.is_running and not app._shutting_down
                assert machinery.detached == []
            finally:
                release.set()
                for _ in range(100):
                    await pilot.pause()
                    if not app._command_running:
                        break

    asyncio.run(scenario())


def test_kill_ends_an_external_launcher_and_an_owned_one(tmp_path):
    from tests.autoresearch.test_campaign_controller import FakeMachinery

    machinery = FakeMachinery()
    app, layout = _console(tmp_path, machinery)

    async def scenario():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await _run_batch(app, pilot, "start 1")
            child = machinery.children[layout.folder(1)]
            await _run_from_panel(app, pilot, "kill 1")
            deadline = time.monotonic() + 5
            while not child.forced and time.monotonic() < deadline:
                await pilot.pause()
            assert child.forced
            assert app._controller.state("campaign-1").child is None

    asyncio.run(scenario())


def test_ctrl_q_asks_what_to_do_with_a_campaign_that_did_not_stop(
    tmp_path, monkeypatch
):
    from tests.autoresearch.test_campaign_controller import FakeMachinery
    from tui import console as console_module

    monkeypatch.setattr(console_module, "STOP_PROMPT_SECONDS", 0.2)
    monkeypatch.setattr(console_module, "STOP_WAIT_MORE_SECONDS", 0.2)

    async def ask(key: str, expect: str):
        machinery = FakeMachinery()
        machinery.wait_exit_code = None  # the launcher never stops by itself
        (tmp_path / key).mkdir()
        app, layout = _console(tmp_path / key, machinery)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await _run_batch(app, pilot, "start 1")
            await pilot.press("ctrl+q")
            deadline = time.monotonic() + 5
            while not isinstance(app.screen, console_module.StopPrompt):
                assert time.monotonic() < deadline, "the prompt never opened"
                await pilot.pause(0.05)
            assert machinery.forced == [] and machinery.detached == []
            child = machinery.children[layout.folder(1)]
            await pilot.press(key)
            deadline = time.monotonic() + 5
            while app.is_running and time.monotonic() < deadline:
                await pilot.pause(0.05)
            assert not app.is_running
        assert (child.forced, bool(machinery.detached)) == {
            "k": (True, False),
            "l": (False, True),
        }[key], expect

    asyncio.run(ask("k", "kill"))
    asyncio.run(ask("l", "leave"))
