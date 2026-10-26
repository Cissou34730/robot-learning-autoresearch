"""The multi-campaign operator console (issue #68).

One Textual application with a Commands tab plus one tab per installed
campaign folder (campaign-1 .. campaign-5). The console never starts
anything on its own: campaigns run only when the operator submits a run,
reset, start or stop command. Every lifecycle action is delegated to
:class:`tui.controller.CampaignController`, which in turn reuses the
existing launch, reset and cooperative-stop entry points.

Process ownership follows ``docs/external-campaign-stop.md``:

- each launcher invocation runs inside a kill-on-close Job Object
  (:class:`tui.process.LauncherMachinery`), so closing or crashing the
  console cannot leave campaign descendants behind;
- stop requests are cooperative files, and a missed cooperative deadline
  escalates to a forced job termination;
- ``Ctrl+C`` copies the current selection (or does nothing); it never
  stops campaigns. ``Ctrl+Q`` asks every owned launcher to stop
  concurrently, waits up to the configured stop timeout, escalates to a
  forced stop, and only then exits.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Input, RichLog, Static, TabbedContent, TabPane

from tui.controller import (
    DEFAULT_STOP_TIMEOUT,
    CampaignController,
    CommandError,
    LaunchSettings,
    ResetConfig,
    WorkspaceLayout,
    parse_command,
)
from tui.process import LauncherMachinery
from tui.report import REPORT_CSS, CampaignPanel, CampaignSources


class CommandInputs:
    """Reads the global launch parameters shared by every batch."""

    FIELD_IDS = (
        "cmd-model",
        "cmd-provider",
        "cmd-reasoning",
        "cmd-timesteps",
        "cmd-max-timesteps",
        "cmd-max-inquiries",
        "cmd-stop-timeout",
    )

    def __init__(self, inputs: dict[str, Input]) -> None:
        self._inputs = inputs

    def settings(self) -> LaunchSettings:
        def text(field: str) -> str | None:
            value = self._inputs[field].value.strip()
            return value or None

        def number(field: str) -> int | None:
            raw = text(field)
            return int(raw) if raw is not None else None

        return LaunchSettings(
            model=text("cmd-model"),
            provider=text("cmd-provider"),
            reasoning=text("cmd-reasoning"),
            timesteps=number("cmd-timesteps"),
            max_timesteps=number("cmd-max-timesteps"),
            max_inquiries=number("cmd-max-inquiries"),
            stop_timeout_seconds=number("cmd-stop-timeout"),
        )


HELP_TEXT = (
    "Commands  (targets: count or list, e.g. `run 3`, `reset campaign-2`, `stop all`)\n"
    "  run N | reset N | start N | stop N | stop all\n"
    "  run = initialize missing folder + reset + launch; start = launch only.\n"
    "  Launch parameters above are shared by every campaign in the batch;\n"
    "  leave a field empty to use the launcher's own default.\n"
    "  Ctrl+C copies selection only. Ctrl+Q stops owned campaigns, then exits."
)


class CampaignConsole(App):
    """Command console for up to five standard campaign folders."""

    TITLE = "Autoresearch campaign console"

    BINDINGS: ClassVar[list] = [
        Binding(
            "ctrl+q", "shutdown_all", "Stop owned campaigns and exit", priority=True
        ),
        ("ctrl+tab", "next_tab", "Next tab"),
    ]

    CSS = (
        REPORT_CSS
        + """
    #commands-input {
        height: 1;
        margin-bottom: 1;
        border: none;
    }
    .command-settings {
        height: auto;
        margin-bottom: 1;
    }
    .command-settings > Input {
        height: 1;
        width: 1fr;
        border: none;
    }
    #commands-help {
        color: $text-muted;
        height: 5;
        margin-bottom: 1;
    }
    #commands-log {
        height: 1fr;
        border: none;
    }
    TabbedContent {
        height: 1fr;
    }
    """
    )

    def __init__(
        self,
        *,
        harness_root: Path | None = None,
        campaigns_root: Path | None = None,
        machinery: object | None = None,
    ) -> None:
        super().__init__()
        from runner import paths

        harness = Path(harness_root) if harness_root else paths.HARNESS_ROOT
        if campaigns_root is not None:
            layout = WorkspaceLayout(harness, Path(campaigns_root))
        else:
            layout = WorkspaceLayout.discover(harness)
        self._layout = layout
        self._controller = CampaignController(
            layout, machinery if machinery is not None else LauncherMachinery(harness)
        )
        self._settings_reader = CommandInputs({})
        self._last_stop_timeout: int = DEFAULT_STOP_TIMEOUT
        self._command_thread: threading.Thread | None = None
        self._command_running = False
        self._shutting_down = False
        self._app = None

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with TabbedContent(initial="commands"):
            with TabPane("Commands", id="commands"):
                yield Static(HELP_TEXT, id="commands-help")
                from textual.containers import Horizontal

                with Horizontal(classes="command-settings"):
                    yield Input(placeholder="Model", id="cmd-model")
                    yield Input(placeholder="Provider", id="cmd-provider")
                    yield Input(placeholder="Reasoning", id="cmd-reasoning")
                with Horizontal(classes="command-settings"):
                    yield Input(placeholder="Timesteps", id="cmd-timesteps")
                    yield Input(placeholder="MaxTimesteps", id="cmd-max-timesteps")
                    yield Input(placeholder="MaxInquiries", id="cmd-max-inquiries")
                    yield Input(placeholder="StopTimeoutSeconds", id="cmd-stop-timeout")
                yield Input(
                    placeholder="Command: run 3 | reset campaign-2 | start campaign-2 | stop all",
                    id="commands-input",
                )
                yield RichLog(id="commands-log")
            for slot in range(1, 6):
                if not self._layout.is_installed(slot):
                    continue
                folder = self._layout.folder(slot)
                with TabPane(f"campaign-{slot}", id=f"campaign-{slot}"):
                    yield CampaignPanel(
                        sources=CampaignSources(campaign_root=folder),
                        campaign_root=folder,
                        id=f"panel-campaign-{slot}",
                    )

    def on_mount(self) -> None:
        self._settings_reader = CommandInputs(
            {
                field: self.query_one(f"#{field}", Input)
                for field in CommandInputs.FIELD_IDS
            }
        )
        self.set_interval(2.0, self._refresh_status)
        self._log(HELP_TEXT.splitlines()[0])
        self._log(
            "Console ready. Type a command and press Enter. Nothing runs until you ask."
        )

    # ------------------------------------------------------------------
    # Console log
    # ------------------------------------------------------------------

    def _log(self, message: str) -> None:
        try:
            self.query_one("#commands-log", RichLog).write(message)
        except Exception:  # noqa: S110,BLE001 - logging must never break shutdown
            pass

    def _refresh_status(self) -> None:
        if self._shutting_down:
            return
        self._controller.reap_all()
        parts = [
            f"{state.label}: {state.stage}{f' ({state.detail[:60]})' if state.detail else ''}"
            for state in self._controller.folder_states()
        ]
        if parts:
            self._log_updatable(" | ".join(parts))

    def _log_updatable(self, message: str) -> None:
        # A compact one-line campaign status is easier to reuse than to
        # rewrite: it is written as a plain line each poll.
        self._log(message)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "commands-input":
            return  # panel-local search inputs handle themselves
        text = event.value.strip()
        event.input.value = ""
        self.submit_command(text)

    def submit_command(self, text: str) -> None:
        if not text:
            return
        if self._shutting_down:
            self._log("> " + text + "\nrefused: the console is shutting down")
            return
        if self._command_running:
            self._log("> " + text + "\nrefused: a previous command is still running")
            return
        try:
            verb, slots = parse_command(text)
        except CommandError as error:
            self._log(f"> {text}\nerror: {error}")
            return
        if verb == "help":
            for line in HELP_TEXT.splitlines():
                self._log(line)
            return
        try:
            settings = self._settings_reader.settings()
        except ValueError as error:
            self._log(f"> {text}\nerror in launch parameters: {error}")
            return
        if settings.stop_timeout_seconds:
            self._last_stop_timeout = settings.stop_timeout_seconds
        reset = ResetConfig() if verb in {"run", "reset"} else None
        self._command_running = True
        self._command_thread = threading.Thread(
            target=self._execute_batch,
            args=(verb, slots, settings, reset, text),
            daemon=True,
            name=f"console-command-{verb}",
        )
        self._command_thread.start()

    def _execute_batch(
        self,
        verb: str,
        slots: list[int],
        settings: LaunchSettings,
        reset: ResetConfig | None,
        text: str,
    ) -> None:
        try:
            outcome = self._controller.execute(
                verb,
                slots,
                settings=settings,
                reset=reset,
            )
            message: str = "> " + text + "\n" + outcome.summary()
            for step in outcome.steps:
                if step.status == "failed" and step.detail:
                    message += "\n  " + step.target + ": " + step.detail[:400]
        except Exception as error:  # noqa: BLE001 - every refusal reaches the log
            message = "> " + text + "\nrefused: " + str(error)
        try:
            self.call_from_thread(self._log, message)
            self.call_from_thread(self._refresh_status_now)
        finally:
            self.call_from_thread(self._batch_finished)

    def _refresh_status_now(self) -> None:
        self._log_updatable(self._status_line())

    def _status_line(self) -> str:
        parts = [
            f"{state.label}: {state.stage}{f' ({state.detail[:60]})' if state.detail else ''}"
            for state in self._controller.folder_states()
        ]
        return " | ".join(parts) if parts else "no campaigns installed"

    def _batch_finished(self) -> None:
        self._command_running = False
        self._command_thread = None

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------

    def action_next_tab(self) -> None:
        tabs = self.query_one(TabbedContent)
        panes = [pane.id for pane in tabs.query(TabPane)]
        if not panes:
            return
        if tabs.active is None or len(panes) == 1:
            tabs.active = panes[0]
            return
        index = (panes.index(tabs.active) + 1) % len(panes)
        tabs.active = panes[index]

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def action_shutdown_all(self) -> None:
        """Ctrl+Q: stop every owned campaign, wait, then exit."""
        if self._shutting_down:
            return
        self._shutting_down = True
        controller = self._controller
        controller.latch_shutdown()
        self._log("Shutting down: stop requests sent to all owned campaigns...")
        busy = [
            state.label
            for state in controller.folder_states()
            if state.child is not None
        ]
        timeout = self._last_stop_timeout

        def job() -> None:
            try:
                if busy:
                    with ThreadPoolExecutor(max_workers=len(busy)) as pool:
                        list(
                            pool.map(
                                lambda label: controller.settle(label, timeout),
                                busy,
                            )
                        )
                # A missed cooperative deadline must never survive the console.
                controller.force_all(timeout=15.0)
                controller.reap_all()
            finally:
                try:
                    self.call_from_thread(self.exit)
                except Exception:  # noqa: S110,BLE001 - the process exit must not hang
                    pass

        threading.Thread(target=job, daemon=True, name="console-shutdown").start()


def run_console(light: bool = False) -> int:
    """Entry point for the console mode of ``python -m tui``."""
    import sys

    from runner import paths
    from tui.process import acquire_instance_lock

    harness_root = paths.HARNESS_ROOT
    lock = acquire_instance_lock(harness_root)
    if lock is None:
        print(
            "Another campaign console is already running for this harness "
            "directory. Close it first - one console owns the campaigns.",
            file=sys.stderr,
        )
        return 2
    try:
        app = CampaignConsole(harness_root=harness_root)
        if light:
            app.theme = "textual-light"
        app.run()
    finally:
        lock.release()
    return 0


__all__ = ["HELP_TEXT", "CampaignConsole", "CommandInputs", "run_console"]
