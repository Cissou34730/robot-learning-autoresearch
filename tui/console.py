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

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Checkbox,
    Input,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

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
    "  models lists models; diagnostics <target> opens console logs.\n"
    "  Ctrl+L: command | Ctrl+Tab: tab | Ctrl+C: copy | Ctrl+Q: stop and exit"
)


class ConsoleDetail(ModalScreen):
    """An error or raw diagnostic, separate from the scientific report."""

    BINDINGS: ClassVar[list] = [("escape", "dismiss", "Close")]
    CSS = """
    ConsoleDetail { align: center middle; }
    ConsoleDetail > VerticalScroll {
        width: 90%; height: 85%; padding: 1 2;
        background: $surface;
    }
    """

    def __init__(self, title: str, body: str) -> None:
        super().__init__()
        self.title_text = title
        self.body_text = body

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(self.title_text, markup=False)
            yield Static(self.body_text, markup=False)
            yield Static("Esc: close")


class CampaignConsole(App):
    """Command console for up to five standard campaign folders."""

    TITLE = "Autoresearch campaign console"

    BINDINGS: ClassVar[list] = [
        Binding(
            "ctrl+q", "shutdown_all", "Stop owned campaigns and exit", priority=True
        ),
        Binding("ctrl+tab", "next_tab", "Next tab", priority=True),
        Binding("ctrl+c", "copy_selection", "Copy", priority=True),
        Binding("ctrl+l", "command", "Command", priority=True),
        ("/", "search_log", "Search events"),
        ("f", "filter_log", "Filter events"),
        ("r", "raw_event", "Raw event"),
        ("escape", "clear_log_filter", "Clear filter"),
        ("end", "follow_log", "Follow live"),
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
        height: auto;
        margin-bottom: 1;
    }
    #commands-summary { height: auto; max-height: 5; color: $text-muted; }
    #reset-mode { width: 20; height: 3; }
    #reset-clean { width: 18; height: 3; }
    #commands-floor { display: none; height: auto; }
    .compact #commands-help { display: none; }
    .compact .command-settings { margin-bottom: 0; }
    .compact #commands-summary { max-height: 4; }
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
        self._shutdown_complete = False
        self._status_refreshing = False

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with TabbedContent(initial="commands"):
            with TabPane("Commands", id="commands"):
                yield Static(HELP_TEXT, id="commands-help")
                with Horizontal(classes="command-settings"):
                    yield Input(placeholder="Model", id="cmd-model")
                    yield Input(placeholder="Provider", id="cmd-provider")
                    yield Input(placeholder="Reasoning (high)", id="cmd-reasoning")
                with Horizontal(classes="command-settings"):
                    yield Input(placeholder="Timesteps (120000)", id="cmd-timesteps")
                    yield Input(
                        placeholder="MaxTimesteps (360000)", id="cmd-max-timesteps"
                    )
                    yield Input(placeholder="MaxInquiries (15)", id="cmd-max-inquiries")
                    yield Input(
                        placeholder="StopTimeoutSeconds (180)", id="cmd-stop-timeout"
                    )
                with Horizontal(classes="command-settings"):
                    yield Select(
                        [("Fresh", "Fresh"), ("Baseline", "Baseline")],
                        value="Fresh",
                        allow_blank=False,
                        id="reset-mode",
                    )
                    yield Checkbox("Clean logs", value=True, id="reset-clean")
                with Horizontal(classes="command-settings"):
                    yield Input(
                        value=ResetConfig().recipe_ref,
                        placeholder="RecipeRef (Fresh)",
                        id="reset-recipe",
                    )
                    yield Input(
                        placeholder="BaselineRef (Baseline)", id="reset-baseline"
                    )
                yield Static("", id="commands-summary")
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
        yield Static("Terminal too small - need 48x16", id="commands-floor")
        yield Input(
            placeholder="Command: run 3 | start 3 | stop all | help",
            id="commands-input",
        )

    def on_mount(self) -> None:
        self._settings_reader = CommandInputs(
            {
                field: self.query_one(f"#{field}", Input)
                for field in CommandInputs.FIELD_IDS
            }
        )
        self.set_interval(2.0, self._refresh_status)
        for label in self._layout.installed():
            self._controller.state(label)
        self._refresh_status_now()
        self.action_command()
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

    async def _refresh_status(self) -> None:
        if self._shutting_down or self._status_refreshing:
            return
        self._status_refreshing = True
        try:
            await asyncio.to_thread(self._controller.reap_all)
            self._refresh_status_now()
        except (OSError, RuntimeError) as error:
            self._log(f"Process cleanup failed: {error}")
        finally:
            self._status_refreshing = False

    def _log_updatable(self, message: str) -> None:
        # A compact one-line campaign status is easier to reuse than to
        # rewrite: it is written as a plain line each poll.
        self.query_one("#commands-summary", Static).update(message)

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
        active = self.query_one(TabbedContent).active
        if not slots and active != "commands":
            slots = [self._layout.slot_for(active)]
        if not slots and verb not in {"models"}:
            self._log(f"> {text}\nerror: {verb} requires a target on Commands.")
            return
        if verb == "diagnostics":
            asyncio.create_task(self._show_diagnostics(slots))
            return
        try:
            settings = (
                self._settings_reader.settings()
                if verb in {"run", "start", "models"}
                else LaunchSettings()
            )
            settings.launcher_arguments()
            mode = str(self.query_one("#reset-mode", Select).value)
            reset = (
                ResetConfig(
                    mode=mode,
                    clean=self.query_one("#reset-clean", Checkbox).value,
                    recipe_ref=self.query_one("#reset-recipe", Input).value.strip()
                    or None
                    if mode == "Fresh"
                    else None,
                    baseline_ref=self.query_one("#reset-baseline", Input).value.strip()
                    or None
                    if mode == "Baseline"
                    else None,
                )
                if verb in {"run", "reset"}
                else None
            )
            if reset is not None:
                reset.arguments()
        except (ValueError, RuntimeError) as error:
            self._log(f"> {text}\nerror in launch parameters: {error}")
            return
        if settings.stop_timeout_seconds:
            self._last_stop_timeout = settings.stop_timeout_seconds
        self._log(
            f"> {text}\nTargets: "
            + ", ".join(str(self._layout.folder(s)) for s in slots)
        )
        self._log(
            "Launcher options: "
            + (
                " ".join(settings.launcher_arguments())
                or "launcher defaults (including 180s stop timeout)"
            )
        )
        if reset is not None:
            self._log(
                "Reset options: "
                + " ".join(reset.arguments())
                + "\nDestructive reset: measurements/logs may be deleted; no reset backup."
            )
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
            if verb == "models":
                args = [
                    "pwsh",
                    "-NoProfile",
                    "-File",
                    str(self._layout.harness_root / "run_research.ps1"),
                    "-ListModels",
                ]
                if settings.provider:
                    args += ["-Provider", settings.provider]
                result = self._controller._runner(args)
                message = result.stdout + result.stderr
                if result.returncode:
                    self.call_from_thread(
                        self.push_screen, ConsoleDetail("Model listing failed", message)
                    )
            else:
                outcome = self._controller.execute(
                    verb,
                    slots,
                    settings=settings,
                    reset=reset,
                )
                message = "> " + text + "\n" + outcome.summary()
                for step in outcome.steps:
                    if step.detail:
                        message += "\n  " + step.target + ": " + step.detail[:400]
                if not outcome.ok:
                    self.call_from_thread(
                        self.push_screen, ConsoleDetail("Command failed", message)
                    )
        except Exception as error:  # noqa: BLE001 - every refusal reaches the log
            message = "> " + text + "\nrefused: " + str(error)
        try:
            self.call_from_thread(self._log, message)
            self.call_from_thread(self._refresh_status_now)
        except RuntimeError:
            pass
        finally:
            self.call_from_thread(self._batch_finished)

    def _refresh_status_now(self) -> None:
        self._log_updatable(self._status_line())

    def _status_line(self) -> str:
        parts = []
        for state in self._controller.folder_states():
            detail = state.detail[:60]
            if state.stage == "stopping" and state.stop_started is not None:
                elapsed = time.monotonic() - state.stop_started
                detail = f"{elapsed:.0f}s elapsed, {max(0, state.stop_timeout + 5 - elapsed):.0f}s remaining"
            parts.append(
                f"{state.label}: {state.stage}" + (f" ({detail})" if detail else "")
            )
        return " | ".join(parts) if parts else "no campaigns installed"

    async def _batch_finished(self) -> None:
        tabs = self.query_one(TabbedContent)
        known = {pane.id for pane in tabs.query(TabPane)}
        for label in self._layout.installed():
            if label not in known:
                folder = self._layout.folder(self._layout.slot_for(label))
                await tabs.add_pane(
                    TabPane(
                        label,
                        CampaignPanel(
                            sources=CampaignSources(campaign_root=folder),
                            campaign_root=folder,
                            id=f"panel-{label}",
                        ),
                        id=label,
                    )
                )
        self._command_running = False
        self._command_thread = None

    async def _show_diagnostics(self, slots: list[int]) -> None:
        def read() -> str:
            chunks = []
            for slot in slots:
                state = self._controller.state(f"campaign-{slot}")
                chunks.append(
                    f"{state.label}: {state.control_directory or 'no TUI-owned invocation'}"
                )
                if state.control_directory:
                    for name in ("console.out.log", "console.err.log"):
                        path = state.control_directory / name
                        if path.is_file():
                            with path.open("rb") as source:
                                source.seek(max(0, path.stat().st_size - 65536))
                                chunks.append(
                                    name
                                    + " (last 64 KiB)\n"
                                    + source.read().decode(
                                        "utf-8-sig", errors="replace"
                                    )
                                )
            return "\n\n".join(chunks)

        self.push_screen(
            ConsoleDetail(
                "Raw console diagnostics (not scientific evidence)",
                await asyncio.to_thread(read),
            )
        )

    def action_copy_selection(self) -> None:
        text = self.screen.get_selected_text()
        if text:
            self.copy_to_clipboard(text)

    def action_command(self) -> None:
        self.query_one("#commands-input", Input).focus()

    def action_search_log(self) -> None:
        self._panel_action("action_search_log")

    def action_filter_log(self) -> None:
        self._panel_action("action_filter_log")

    def action_raw_event(self) -> None:
        self._panel_action("action_raw_event")

    def action_clear_log_filter(self) -> None:
        self._panel_action("action_clear_log_filter")

    def action_follow_log(self) -> None:
        self._panel_action("action_follow_log")

    def _panel_action(self, action: str) -> None:
        label = self.query_one(TabbedContent).active
        if label and label != "commands":
            getattr(self.query_one(f"#panel-{label}", CampaignPanel), action)()

    def on_resize(self) -> None:
        if self.is_mounted:
            small = self.size.width < 48 or self.size.height < 16
            self.set_class(self.size.width < 110 or self.size.height < 32, "compact")
            self.query_one(TabbedContent).display = not small
            self.query_one("#commands-floor").display = small

    def watch_theme(self) -> None:
        for panel in self.query(CampaignPanel):
            panel.apply_theme()

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

        def job() -> None:
            try:
                thread = self._command_thread
                if thread is not None:
                    thread.join(self._last_stop_timeout + 5)
                    if thread.is_alive():
                        controller.stop_helpers()
                        thread.join(5)
                busy = [
                    state.label
                    for state in controller.folder_states()
                    if state.child is not None
                ]

                def settle(label):
                    state = controller.state(label)
                    remaining = max(
                        0.0,
                        (state.stop_started or time.monotonic())
                        + state.stop_timeout
                        + 5
                        - time.monotonic(),
                    )
                    return controller.settle(label, remaining)

                if busy:
                    with ThreadPoolExecutor(max_workers=len(busy)) as pool:
                        list(
                            pool.map(
                                settle,
                                busy,
                            )
                        )
                # A missed cooperative deadline must never survive the console.
                controller.force_all(timeout=15.0)
                controller.reap_all()
                self._shutdown_complete = True
            except (OSError, RuntimeError) as error:
                self.call_from_thread(self._log, f"Shutdown cleanup failed: {error}")
            finally:
                try:
                    self.call_from_thread(self.exit)
                except Exception:  # noqa: S110,BLE001 - the process exit must not hang
                    pass

        threading.Thread(target=job, daemon=True, name="console-shutdown").start()

    def action_quit(self) -> None:
        self.action_shutdown_all()


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
        try:
            if "app" in locals() and not app._shutdown_complete:
                app._controller.latch_shutdown()
                app._controller.stop_helpers()
                app._controller.force_all()
        finally:
            lock.release()
    return 0


__all__ = ["HELP_TEXT", "CampaignConsole", "CommandInputs", "run_console"]
