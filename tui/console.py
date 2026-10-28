"""The multi-campaign operator console (issue #68).

One Textual application with one report tab per installed campaign folder
(campaign-1 .. campaign-5) and a persistent command composer. The console never starts
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

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Input,
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

HELPER_SHUTDOWN_GRACE_SECONDS = 15.0

# Colour of the dot in front of each campaign tab label. State colours come
# from the theme; phase colours are fixed (dark, light) because the theme has
# too few distinct colours.
TAB_STATE_COLOURS = {
    "failed": "$error",
    "attention": "$warning",
    "running": "$success",
    "quiet": "$text-muted",
}
TAB_PHASE_COLOURS = {
    "training": ("#5aa9ff", "#0b5cc4"),
    "evaluating": ("#4ed8e0", "#00747d"),
    "coding": ("#e07cf0", "#8b1fa0"),
    "official": ("#ffd54a", "#946b00"),
    "preparing": ("#a58bff", "#5b3fc7"),
    "completed": ("#8aa4c8", "#4b6584"),
}
TAB_TAG_COLOURS = {
    **TAB_STATE_COLOURS,
    **{tag: pair[0] for tag, pair in TAB_PHASE_COLOURS.items()},
}
# These phases show a dot that pulses once a second.
PULSING_TAGS = frozenset({"training", "evaluating", "coding", "official"})


def tab_tag(stage: str, stalled: bool, phase: str = "none") -> str:
    """The tag for one campaign tab. State beats phase: a failed or stalled
    campaign keeps its warning colour whatever it was doing."""
    if stage == "failed":
        return "failed"
    if stage in {"stopping", "resetting"}:
        return "attention"
    if stage in {"launching", "running"}:
        if stalled:
            return "attention"
        return phase if phase in TAB_PHASE_COLOURS else "running"
    if stage == "completed":
        return "completed"
    return "quiet"


class CommandInputs:
    """Session-only shared settings; empty values preserve launcher omission."""

    FIELD_IDS = (
        "cmd-model",
        "cmd-provider",
        "cmd-reasoning",
        "cmd-timesteps",
        "cmd-max-timesteps",
        "cmd-max-inquiries",
        "cmd-stop-timeout",
    )

    def __init__(self, values: dict | None = None) -> None:
        self.values = {field: "" for field in self.FIELD_IDS}
        self.values.update(
            {
                "reset-mode": "Fresh",
                "reset-clean": True,
                "reset-recipe": ResetConfig().recipe_ref,
                "reset-baseline": "",
            }
        )
        self.values.update(values or {})

    def settings(self) -> LaunchSettings:
        def text(field: str) -> str | None:
            value = str(self.values[field]).strip()
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

    def reset_config(self) -> ResetConfig:
        mode = self.values["reset-mode"]
        return ResetConfig(
            mode=mode,
            clean=self.values["reset-clean"],
            recipe_ref=str(self.values["reset-recipe"]).strip() or None
            if mode == "Fresh"
            else None,
            baseline_ref=str(self.values["reset-baseline"]).strip() or None
            if mode == "Baseline"
            else None,
        )


HELP_TEXT = (
    "Start / resume (preserves work): start 1\n"
    "Fresh reset and start (destructive): run 1\n"
    "Stop cooperatively: stop 1 | stop all\n"
    "Reset without starting (destructive): reset 1\n\n"
    "Numbers select one campaign: start 2 starts only campaign-2.\n"
    "Ranges are inclusive: start 1-2 | start 2-3 | run 1-3.\n"
    "Explicit folders also work: start campaign-1 campaign-3.\n"
    "Without a target, start/run/reset/stop selects the active campaign tab.\n"
    "Reset/run may delete measurements and logs. There is no reset backup.\n\n"
    "F2 Settings: shared launch parameters and Fresh/Baseline reset options.\n"
    "Empty launch fields use launcher defaults, including high reasoning,\n"
    "120000 timesteps, 360000 max timesteps, 15 inquiries and 180s stop timeout.\n"
    "Model/provider remain launcher-selected unless explicitly supplied.\n"
    "models: list available models | diagnostics: this campaign's console logs | help: this text\n\n"
    "F1 Help | F2 Settings | F3 Recent commands | Ctrl+L show/hide commands\n"
    "Tab / Shift+Tab: next/previous campaign; move focus inside dialogs\n"
    "Ctrl+Tab: next campaign if the terminal passes it through\n"
    "F6 / Shift+F6: move focus between report controls | Ctrl+C: copy only\n"
    "Ctrl+Q: stop all owned campaigns and exit"
)


class SharedSettings(ModalScreen[dict | None]):
    """One labelled, scrollable form; opening/editing it never runs a command."""

    BINDINGS: ClassVar[list] = [("escape", "cancel", "Cancel")]
    CSS = """
    SharedSettings { align: center middle; background: $background 65%; }
    #settings-dialog { width: 90%; max-width: 110; height: 28; max-height: 90%; padding: 1 2; background: $surface; }
    #settings-title { height: 1; text-style: bold; }
    #settings-note { height: auto; color: $text-muted; margin-bottom: 1; }
    #settings-scroll { height: 1fr; }
    #launch-fields { height: auto; grid-size: 3; grid-rows: 2; grid-gutter: 1 2; }
    SharedSettings.narrow #launch-fields { grid-size: 1; }
    SharedSettings.standard #launch-fields { grid-size: 2; }
    .setting-field { height: 2; }
    .setting-field Static { height: 1; }
    .setting-field Input { height: 1; border: none; padding: 0 1; background: $boost; }
    .setting-field Input:focus { text-style: bold; background: $primary 25%; }
    #reset-heading { height: 1; margin-top: 1; text-style: bold; }
    #reset-controls { height: 3; }
    #reset-mode { width: 20; }
    SharedSettings SelectCurrent { border: solid $panel; }
    #reset-clean { width: auto; border: none; padding: 1 0; }
    SharedSettings.narrow #reset-controls { layout: vertical; height: 6; }
    #reset-warning { height: auto; color: $warning; margin-top: 1; }
    #settings-error { height: auto; color: $error; }
    #settings-actions { height: 3; align-horizontal: right; }
    #settings-actions Button { margin-left: 1; border: none; padding: 1 1; }
    """

    def __init__(self, values: dict) -> None:
        super().__init__()
        self.values = dict(values)

    def compose(self) -> ComposeResult:
        fields = (
            ("cmd-model", "Model", "Launcher-selected model"),
            (
                "cmd-provider",
                "Provider",
                "Auto / github-copilot / opencode / opencode-go",
            ),
            ("cmd-reasoning", "Reasoning", "high (launcher default)"),
            ("cmd-timesteps", "Training timesteps", "120000 (launcher default)"),
            ("cmd-max-timesteps", "Maximum timesteps", "360000 (launcher default)"),
            (
                "cmd-max-inquiries",
                "Maximum inquiries",
                "15 (omitted on resume unless set)",
            ),
            ("cmd-stop-timeout", "Stop timeout (seconds)", "180 (launcher default)"),
        )
        with Vertical(id="settings-dialog"):
            yield Static("Shared campaign settings", id="settings-title")
            yield Static(
                "Applies to future commands, not active runs. Empty fields keep launcher defaults.",
                id="settings-note",
            )
            with VerticalScroll(id="settings-scroll"):
                with Grid(id="launch-fields"):
                    for field, label, placeholder in fields:
                        with Vertical(classes="setting-field"):
                            yield Static(label)
                            yield Input(
                                value=self.values[field],
                                placeholder=placeholder,
                                id=field,
                            )
                yield Static(
                    "Reset options — used only by run / reset", id="reset-heading"
                )
                with Horizontal(id="reset-controls"):
                    yield Select(
                        [("Fresh", "Fresh"), ("Baseline", "Baseline")],
                        value=self.values["reset-mode"],
                        allow_blank=False,
                        id="reset-mode",
                    )
                    yield Checkbox(
                        "Clean eligible changes (--clean)",
                        value=self.values["reset-clean"],
                        id="reset-clean",
                    )
                with Vertical(classes="setting-field", id="reset-recipe-field"):
                    yield Static("Recipe ref (Fresh)")
                    yield Input(value=self.values["reset-recipe"], id="reset-recipe")
                with Vertical(classes="setting-field", id="reset-baseline-field"):
                    yield Static("Baseline ref (required for Baseline)")
                    yield Input(
                        value=self.values["reset-baseline"],
                        placeholder="Existing baseline ref",
                        id="reset-baseline",
                    )
                yield Static(
                    "Reset may delete measurements and logs. No reset backup.",
                    id="reset-warning",
                )
            yield Static("", id="settings-error", markup=False)
            with Horizontal(id="settings-actions"):
                yield Button("Cancel", id="settings-cancel")
                yield Button("Apply", variant="primary", id="settings-apply")

    def on_mount(self) -> None:
        self.on_resize()
        self._reset_fields()

    def on_resize(self) -> None:
        self.set_class(self.size.width < 70, "narrow")
        self.set_class(70 <= self.size.width < 110, "standard")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "reset-mode" and self.is_mounted:
            self._reset_fields()

    def _reset_fields(self) -> None:
        fresh = self.query_one("#reset-mode", Select).value == "Fresh"
        self.query_one("#reset-recipe-field").display = fresh
        self.query_one("#reset-baseline-field").display = not fresh

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "settings-cancel":
            self.action_cancel()
        elif event.button.id == "settings-apply":
            values = {
                field: self.query_one(f"#{field}", Input).value
                for field in CommandInputs.FIELD_IDS
            }
            values.update(
                {
                    "reset-mode": str(self.query_one("#reset-mode", Select).value),
                    "reset-clean": self.query_one("#reset-clean", Checkbox).value,
                    "reset-recipe": self.query_one("#reset-recipe", Input).value,
                    "reset-baseline": self.query_one("#reset-baseline", Input).value,
                }
            )
            try:
                reader = CommandInputs(values)
                reader.settings().launcher_arguments()
                reader.reset_config().arguments()
            except (ValueError, RuntimeError) as error:
                self.query_one("#settings-error", Static).update(str(error))
                return
            self.dismiss(values)

    def action_cancel(self) -> None:
        self.dismiss(None)


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
        Binding("ctrl+q", "shutdown_all", "Stop & exit", priority=True),
        Binding("ctrl+l", "command", "Commands", priority=True),
        Binding("f1", "help", "Help", priority=True),
        Binding("f2", "settings", "Settings", priority=True),
        Binding("f3", "command_history", "Recent commands", priority=True, show=False),
        Binding("ctrl+tab", "next_tab", "Next tab", priority=True, show=False),
        Binding("tab", "next_tab", "Campaign", priority=True),
        Binding(
            "shift+tab", "previous_tab", "Previous campaign", priority=True, show=False
        ),
        Binding("f6", "focus_next", "Focus next control", show=False),
        Binding("shift+f6", "focus_previous", "Focus previous control", show=False),
        Binding("ctrl+c", "copy_selection", "Copy", priority=True, show=False),
        Binding("/", "search_log", "Search events", show=False),
        Binding("f", "filter_log", "Filter events", show=False),
        Binding("r", "raw_event", "Raw event", show=False),
        Binding("escape", "clear_log_filter", "Clear filter", show=False),
        Binding("end", "follow_log", "Follow live", show=False),
    ]

    CSS = (
        REPORT_CSS
        + """
    Screen { layout: vertical; overflow: hidden; }
    #console-controls { dock: bottom; height: 5; }
    #console-controls.collapsed { height: 1; }
    #console-controls.collapsed #command-row,
    #console-controls.collapsed #commands-summary { display: none; }
    #command-row { height: 3; padding: 0 1; }
    #command-label { width: 8; height: 3; content-align: left middle; text-style: bold; }
    #commands-input { width: 1fr; min-width: 8; height: 3; border: solid $panel; }
    #commands-input:focus { border: solid $accent; }
    #command-row Button { min-width: 0; height: 3; margin-left: 1; border: none; padding: 1 0; }
    #execute-command { width: 9; }
    #show-settings { width: 10; }
    #commands-summary { height: 1; padding: 0 1; color: $text-muted; }
    #commands-floor { display: none; height: 1fr; content-align: center middle; }
    #empty-campaigns { display: none; height: 1fr; padding: 1 2; }
    TabbedContent { height: 1fr; min-height: 0; }
    TabbedContent > ContentSwitcher { height: 1fr; }
    TabPane { height: 100%; padding: 0; }
    #console-controls Footer { dock: none; height: 1; background: $surface; }
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
        self._settings_reader = CommandInputs()
        self._last_stop_timeout: int = DEFAULT_STOP_TIMEOUT
        self._command_thread: threading.Thread | None = None
        self._command_running = False
        self._shutting_down = False
        self._shutdown_complete = False
        self._status_refreshing = False
        self._command_history: list[str] = []
        self._feedback = ""
        self._summary = ""
        self._tab_tags: dict[str, tuple] = {}
        self._pulse_on = True

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        # Docked controls reserve real rows; the report cannot push them off-screen.
        with Vertical(id="console-controls"):
            yield Static("", id="commands-summary", markup=False)
            with Horizontal(id="command-row"):
                yield Static("Command", id="command-label")
                yield Input(
                    placeholder="start (resume) | run (fresh) | stop | reset | models | diagnostics | help",
                    id="commands-input",
                )
                yield Button("Execute", variant="primary", id="execute-command")
                yield Button("Settings", id="show-settings")
            yield Footer(show_command_palette=False)
        installed = self._layout.installed()
        with TabbedContent(initial=installed[0] if installed else ""):
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
        yield Static(
            "No campaign folders are installed.\nUse run 1 to initialize, reset and start campaign-1 from an existing recipe source.\nF2: shared settings | F1: command help. Nothing runs automatically.",
            id="empty-campaigns",
        )

    def on_mount(self) -> None:
        self.set_interval(2.0, self._refresh_status)
        self.set_interval(1.0, self._pulse_tabs)
        for label in self._layout.installed():
            self._controller.state(label)
        self._refresh_status_now()
        self.query_one("#commands-input", Input).focus()
        self._update_campaign_visibility()

    # ------------------------------------------------------------------
    # Console log
    # ------------------------------------------------------------------

    def _log(self, message: str) -> None:
        self._command_history.append(message)
        del self._command_history[:-100]
        lines = message.splitlines()
        self._feedback = " ".join(lines[:2])
        self._refresh_status_now()

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
        if message != self._summary:
            self._summary = message
            self.query_one("#commands-summary", Static).update(
                Text(message, no_wrap=True, overflow="ellipsis")
            )

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "commands-input":
            return  # panel-local search inputs handle themselves
        text = event.value.strip()
        self.submit_command(text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "execute-command":
            self.submit_command(self.query_one("#commands-input", Input).value.strip())
        elif event.button.id == "show-settings":
            self.action_settings()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "commands-input" and self.is_mounted:
            self._refresh_status_now()
            self._update_execute_state()

    def _update_execute_state(self) -> None:
        try:
            verb, _ = parse_command(self.query_one("#commands-input", Input).value)
        except CommandError:
            verb = None
        self.query_one("#execute-command", Button).disabled = self._shutting_down or (
            self._command_running and verb != "stop"
        )

    def submit_command(self, text: str) -> None:
        if not text:
            return
        if self._shutting_down:
            self._log("> " + text + "\nrefused: the console is shutting down")
            return
        try:
            verb, slots = parse_command(text)
        except CommandError as error:
            self._log(f"> {text}\nerror: {error}")
            return
        if self._command_running and verb != "stop":
            self._log("> " + text + "\nrefused: a previous command is still running")
            return
        if verb == "help":
            self.action_help()
            return
        active = self.query_one(TabbedContent).active
        if not slots and active:
            slots = [self._layout.slot_for(active)]
        if not slots and verb not in {"models"}:
            self._log(
                f"> {text}\nerror: {verb} requires a campaign number, range or folder name."
            )
            return
        if verb == "diagnostics":
            asyncio.create_task(self._show_diagnostics(slots))
            return
        if verb == "stop":
            # Stop requests only create private local files; never queue them
            # behind a reset/model-listing worker or replace that worker handle.
            try:
                outcome = self._controller.execute(
                    verb, slots, settings=LaunchSettings()
                )
                message = "> " + text + "\n" + outcome.summary()
                for step in outcome.steps:
                    if step.detail:
                        message += "\n  " + step.target + ": " + step.detail
                self._log(message)
                self.query_one("#commands-input", Input).value = ""
            except (OSError, RuntimeError, ValueError) as error:
                self._log(f"> {text}\nstop failed: {error}")
            return
        try:
            settings = (
                self._settings_reader.settings()
                if verb in {"run", "start", "models"}
                else LaunchSettings()
            )
            settings.launcher_arguments()
            reset = (
                self._settings_reader.reset_config()
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
        self.query_one("#commands-input", Input).value = ""
        self._update_execute_state()
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
                    "uv",
                    "run",
                    "--project",
                    str(self._layout.harness_root),
                    "python",
                    "-m",
                    "runner.launcher",
                    "--list-models",
                ]
                if settings.provider:
                    args += ["--provider", settings.provider]
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
        for panel in self.query(CampaignPanel):
            target = self._controller.state(panel.id.removeprefix("panel-"))
            if target.stage in {"launching", "running", "stopping"} or (
                target.stage == "idle" and target.external
            ):
                panel.set_process_running(True)
            elif target.stage in {"stopped", "failed", "completed", "idle"}:
                panel.set_process_running(False)
        self._refresh_tab_tags()
        command = self.query_one("#commands-input", Input)
        active = self.query_one(TabbedContent).active
        command.border_title = active or "Explicit target required"
        if command.value.strip():
            try:
                verb, slots = parse_command(command.value)
                if not slots and active:
                    slots = [self._layout.slot_for(active)]
                targets = ", ".join(f"campaign-{slot}" for slot in slots)
                if verb in {"run", "reset"} and targets:
                    reset = self._settings_reader.reset_config()
                    action = "reset + start" if verb == "run" else "reset only"
                    self._log_updatable(
                        f"DESTRUCTIVE {action} (no backup): {targets} | {reset.mode}"
                    )
                    return
                if verb in {"start", "stop"} and targets:
                    action = (
                        "Start/resume (preserve work)"
                        if verb == "start"
                        else "Cooperative stop"
                    )
                    self._log_updatable(f"{action}: {targets}")
                    return
            except CommandError:
                pass  # Do not flash validation errors while a command is incomplete.
        status = self._status_line()
        self._log_updatable(
            status
            + " | "
            + (self._feedback or "start resumes; run resets + starts; F1 help")
        )

    def _tag_colour(self, tag: str) -> str:
        pair = TAB_PHASE_COLOURS.get(tag)
        if pair is None:
            return TAB_STATE_COLOURS[tag]
        try:
            dark = self.current_theme.dark
        except Exception:  # noqa: BLE001 - the theme is not ready yet
            dark = True
        return pair[0] if dark else pair[1]

    def _refresh_tab_tags(self) -> None:
        """Tag every campaign tab, visible or not, from its stage and phase."""
        found = self.query(TabbedContent)
        if not found:
            return
        tabs = found.first()
        for panel in self.query(CampaignPanel):
            label = panel.id.removeprefix("panel-")
            state = self._controller.state(label)
            stage = (
                "running" if state.stage == "idle" and state.external else state.stage
            )
            tag = tab_tag(stage, panel.progress_stalled(), panel.phase())
            self._tag_tab(tabs, label, tag)

    def _pulse_tabs(self) -> None:
        if self._shutting_down:
            return
        self._pulse_on = not self._pulse_on
        self._refresh_tab_tags()

    def _tag_tab(self, tabs: TabbedContent, label: str, tag: str) -> None:
        """Colour the dot in front of a tab label; relabel only on a change."""
        glyph = "●" if tag not in PULSING_TAGS or self._pulse_on else "◐"
        colour = self._tag_colour(tag)
        shown = (tag, glyph, colour)
        if self._tab_tags.get(label) == shown:
            return
        try:
            tab = tabs.get_tab(label)
        except Exception:  # noqa: BLE001 - the tab is not mounted yet
            return
        self._tab_tags[label] = shown
        tab.label = Content.from_markup(f"[{colour}]{glyph}[/] $name", name=label)

    def _status_line(self) -> str:
        active = self.query_one(TabbedContent).active
        if active:
            state = self._controller.state(active)
            if state.stage == "idle":
                stage = (
                    "running (started elsewhere)"
                    if state.external
                    else "not started here"
                )
            else:
                stage = state.stage
            if state.stage == "stopping" and state.stop_started is not None:
                elapsed = time.monotonic() - state.stop_started
                return f"{active}: stopping, {elapsed:.0f}s elapsed, {max(0, state.stop_timeout + 5 - elapsed):.0f}s remaining"
            if state.stage == "failed" and state.detail:
                return f"{active}: failed ({state.detail[:240]})"
            return f"{active}: {stage}"
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
        self._update_execute_state()
        self._update_campaign_visibility()

    def action_help(self) -> None:
        self.push_screen(ConsoleDetail("Campaign commands", HELP_TEXT))

    def action_settings(self) -> None:
        if not isinstance(self.screen, SharedSettings):
            self.push_screen(
                SharedSettings(self._settings_reader.values), self._settings_saved
            )

    def _settings_saved(self, values: dict | None) -> None:
        if values is not None:
            self._settings_reader = CommandInputs(values)
            self._log(
                "Shared settings updated for future commands. Active runs are unchanged."
            )
        if self.query_one("#console-controls").has_class("collapsed"):
            self._focus_campaign()
        else:
            self.query_one("#commands-input", Input).focus()

    def action_command_history(self) -> None:
        self.push_screen(
            ConsoleDetail(
                "Recent campaign commands",
                "\n\n".join(self._command_history)
                or "No commands submitted in this TUI session.",
            )
        )

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
        """Ctrl+L toggles the command area without discarding its draft."""
        if isinstance(self.screen, ModalScreen):
            return
        controls = self.query_one("#console-controls")
        controls.toggle_class("collapsed")
        if controls.has_class("collapsed"):
            self._focus_campaign()
        else:
            self.query_one("#commands-input", Input).focus()

    def _focus_campaign(self) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        tabs = self.query_one(TabbedContent)
        if tabs.display and tabs.active:
            panel = self.query_one(f"#panel-{tabs.active}", CampaignPanel)
            output = panel.query_one("#output")
            (output if output.display else panel.query_one("#models")).focus()
        else:
            self.screen.set_focus(None)

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
        if label:
            getattr(self.query_one(f"#panel-{label}", CampaignPanel), action)()

    def on_resize(self) -> None:
        if self.is_mounted:
            self._update_campaign_visibility()

    def _update_campaign_visibility(self) -> None:
        small = self.size.width < 48 or self.size.height < 16
        installed = bool(self._layout.installed())
        tabs = self.query_one(TabbedContent)
        tabs.display = installed and not small
        if installed and not tabs.active:
            tabs.active = self._layout.installed()[0]
        self.query_one("#empty-campaigns").display = not installed and not small
        self.query_one("#commands-floor").display = small

    def on_tabbed_content_tab_activated(self) -> None:
        if self.is_mounted:
            self._refresh_status_now()

    def watch_theme(self) -> None:
        for panel in self.query(CampaignPanel):
            panel.apply_theme()

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------

    def action_next_tab(self) -> None:
        if isinstance(self.screen, ModalScreen):
            self.action_focus_next()
        else:
            self._cycle_campaign(1)

    def action_previous_tab(self) -> None:
        if isinstance(self.screen, ModalScreen):
            self.action_focus_previous()
        else:
            self._cycle_campaign(-1)

    def _cycle_campaign(self, direction: int) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        tabs = self.query_one(TabbedContent)
        panes = [pane.id for pane in tabs.query(TabPane)]
        if not panes:
            return
        if tabs.active is None or len(panes) == 1:
            tabs.active = panes[0]
            return
        index = (panes.index(tabs.active) + direction) % len(panes)
        controls = self.query_one("#console-controls")
        focus_report = controls.has_class(
            "collapsed"
        ) or self.focused not in controls.query("*")
        if focus_report:
            self.screen.set_focus(None)
        tabs.active = panes[index]
        if focus_report:
            self.call_after_refresh(self._focus_campaign)

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
            cleanup_failed = False
            try:
                thread = self._command_thread
                if thread is not None:
                    thread.join(HELPER_SHUTDOWN_GRACE_SECONDS)
                    if thread.is_alive():
                        try:
                            controller.stop_helpers()
                        except (OSError, RuntimeError) as error:
                            cleanup_failed = True
                            self.call_from_thread(
                                self._log, f"Helper cleanup failed: {error}"
                            )
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
                        for future in [pool.submit(settle, label) for label in busy]:
                            try:
                                future.result()
                            except (OSError, RuntimeError) as error:
                                cleanup_failed = True
                                self.call_from_thread(
                                    self._log, f"Campaign cleanup failed: {error}"
                                )
                # A missed cooperative deadline must never survive the console.
                controller.force_all(timeout=15.0)
                controller.reap_all()
                self._shutdown_complete = not cleanup_failed
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
                try:
                    app._controller.latch_shutdown()
                finally:
                    try:
                        app._controller.stop_helpers()
                    finally:
                        app._controller.force_all()
        finally:
            lock.release()
    return 0


__all__ = [
    "HELP_TEXT",
    "CampaignConsole",
    "CommandInputs",
    "SharedSettings",
    "run_console",
]
