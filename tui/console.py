"""The multi-campaign operator console (issue #68).

One Textual application with report tabs for active or recently idle campaigns
(campaign-1 .. campaign-5) and a command panel that ``/`` opens. The console
never starts anything on its own: campaigns run only when the operator submits a
run, reset, start or stop command. Every lifecycle action is delegated to
:class:`tui.controller.CampaignController`, which in turn reuses the existing
launch, reset and cooperative-stop entry points.

Process ownership follows ``docs/external-campaign-stop.md``:

- each launcher invocation runs inside a Job Object that does not kill on close,
  so the console can leave campaigns running (``/quit``, ``Alt+Q``) and closing
  or crashing the console does not stop them. Short helpers (reset, initialize)
  run in kill-on-close jobs. Each launcher's process is recorded outside the
  campaign, so ``/kill`` can end it from any console;
- stop requests are cooperative files;
- ``Ctrl+C`` copies the current selection (or does nothing); it never
  stops campaigns. ``Ctrl+Q`` asks every owned launcher to stop concurrently,
  waits, and offers to kill, leave or keep waiting for any that has not stopped
  after 30 s; it kills nothing the operator did not choose.
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from typing import ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import (
    Input,
    Static,
    TabbedContent,
    TabPane,
)

from tui import commands
from tui.command_panel import CommandPanel
from tui.commands import Command
from tui.console_screens import CommandInputs, ConsoleDetail, SharedSettings, StopPrompt
from tui.controller import (
    DEFAULT_STOP_TIMEOUT,
    CampaignController,
    CampaignFolderState,
    CommandError,
    LaunchSettings,
    ResetConfig,
    WorkspaceLayout,
    parse_command,
)
from tui.phase_presentation import (
    OUTCOME_TAGS,
    PULSING_TAGS,
    TAB_PHASE_COLOURS,
    TAB_STATE_COLOURS,
    TAB_TAG_COLOURS,
    tab_tag,
)
from tui.process import LauncherMachinery
from tui.report import REPORT_CSS, CampaignPanel, CampaignSources
from tui.shutdown import ShutdownCoordinator
from tui.tab_visibility import IDLE_TAB_SECONDS, TabIdleTracker

HELPER_SHUTDOWN_GRACE_SECONDS = 15.0
# After Ctrl+Q, a campaign that has not stopped by then is put to the operator.
STOP_PROMPT_SECONDS = 30.0
# What "keep waiting" adds before the prompt comes back.
STOP_WAIT_MORE_SECONDS = 60.0
# How long a command's result replaces the key hints on the info line.
FEEDBACK_SECONDS = 8.0
KEY_HINTS = (
    "/ commands · Alt+Q leave running · Ctrl+Q stop & exit · F1 help · "
    "F2 settings · Tab campaign"
)
PANEL_HINTS = "Enter run · Tab complete · Up/Down choose · Esc close"

# Colour of the dot in front of each campaign tab label. State colours come
# from the theme; phase colours are fixed (dark, light) because the theme has
# too few distinct colours.
# These phases show a dot that pulses once a second.
# A diamond, not a dot, so the outcome differs from a running dot without colour.


def help_text() -> str:
    """The help screen: the commands from the registry, then the keys."""
    return (
        "Press / to open the command list: type to filter, Up/Down to choose,\n"
        "Tab to complete, Enter to run, Esc to close.\n\n"
        + "\n".join(commands.help_lines())
        + "\n\n"
        "Numbers select one campaign: start 2 starts only campaign-2.\n"
        "Ranges are inclusive: start 1-2 | start 2-3 | run 1-3.\n"
        "Explicit folders also work: start campaign-1 campaign-3.\n"
        "Without a target, a campaign command acts on the active campaign tab.\n"
        "Tabs hide automatically after two hours with no running launcher.\n"
        "show / hide change visibility for this console session, never execution.\n"
        "start / run restore automatic visibility. Hidden campaigns still take\n"
        "stop all, kill all and the usual shutdown actions.\n"
        "run and reset may delete measurements and logs. There is no reset backup.\n"
        "kill ends the launcher of a campaign any console started (stop is the "
        "clean way).\n\n"
        "F2 Settings: shared launch parameters and Fresh/Baseline reset options.\n"
        "Empty launch fields use launcher defaults, including high reasoning,\n"
        "120000 timesteps, 360000 max timesteps, 15 inquiries and 180s stop timeout.\n"
        "Model/provider remain launcher-selected unless explicitly supplied.\n\n"
        "F1 Help | F2 Settings | F3 Recent commands | Ctrl+L open the commands\n"
        "Ctrl+F search the log | f filter | r raw event | End follow live\n"
        "Tab / Shift+Tab: next/previous campaign; move focus inside dialogs\n"
        "Ctrl+Tab: next campaign if the terminal passes it through\n"
        "F6 / Shift+F6: move focus between report controls | Ctrl+C: copy only\n"
        "Alt+Q (or /quit): leave the console; the campaigns keep running\n"
        "Ctrl+Q (or /quit stop): stop all owned campaigns and exit. A campaign that\n"
        "has not stopped after 30 s is offered a kill, or is left running."
    )


HELP_TEXT = help_text()


class CampaignConsole(App):
    """Command console for up to five standard campaign folders."""

    TITLE = "Autoresearch campaign console"

    BINDINGS: ClassVar[list] = [
        Binding("ctrl+q", "shutdown_all", "Stop & exit", priority=True),
        Binding("alt+q", "detach", "Leave running", priority=True),
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
        Binding("slash", "open_commands", "Commands", show=False),
        Binding("ctrl+f", "search_log", "Search events", show=False),
        Binding("f", "filter_log", "Filter events", show=False),
        Binding("r", "raw_event", "Raw event", show=False),
        Binding("escape", "clear_log_filter", "Clear filter", show=False),
        Binding("end", "follow_log", "Follow live", show=False),
        Binding("down", "command_next", "Next command", show=False),
        Binding("up", "command_previous", "Previous command", show=False),
    ]

    CSS = (
        REPORT_CSS
        + """
    Screen { layout: vertical; overflow: hidden; }
    #console-controls { dock: bottom; height: auto; }
    #command-panel { display: none; height: auto; max-height: 12; padding: 0 1; background: $boost; }
    #command-panel.open { display: block; }
    #command-prompt { height: 1; }
    #command-slash { width: 2; color: $accent; text-style: bold; }
    #commands-input { width: 1fr; min-width: 8; height: 1; border: none; padding: 0; background: $boost; }
    #commands-input:focus { border: none; }
    #command-list { height: auto; max-height: 10; border: none; padding: 0; background: $boost; }
    #commands-summary { height: 1; padding: 0 1; color: $text-muted; }
    #commands-floor { display: none; height: 1fr; content-align: center middle; }
    #empty-campaigns { display: none; height: 1fr; padding: 1 2; }
    TabbedContent { height: 1fr; min-height: 0; }
    TabbedContent > ContentSwitcher { height: 1fr; }
    TabPane { height: 100%; padding: 0; }
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
        self._detached: list[str] = []
        self._status_refreshing = False
        self._command_history: list[str] = []
        self._feedback = ""
        self._feedback_at = 0.0
        self._summary = ""
        self._tab_tags: dict[str, tuple] = {}
        self._pulse_on = True
        self._panel_open = False
        self._return_focus = None
        self._idle_tracker = TabIdleTracker()
        self._tab_idle_since: dict[str, float | None] = {}
        self._tab_overrides: dict[str, bool] = {}
        self._visible_tabs: list[str] = []
        self._tab_visibility_applied = False
        self._activity_ready = False
        self._activity_errors: tuple[str, ...] = ()
        self._activity_poll_lock = threading.Lock()
        self._empty_message = "Checking campaign activity..."

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        # Docked controls reserve real rows; the report cannot push them off-screen.
        with Vertical(id="console-controls"):
            yield CommandPanel(id="command-panel")
            yield Static("", id="commands-summary", markup=False)
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
                        show_hints=False,
                        id=f"panel-campaign-{slot}",
                    )
        yield Static("Terminal too small - need 48x16", id="commands-floor")
        yield Static(
            "Checking campaign activity...",
            id="empty-campaigns",
        )

    async def on_mount(self) -> None:
        self.set_interval(2.0, self._refresh_status)
        self.set_interval(1.0, self._pulse_tabs)
        for label in self._layout.installed():
            self._controller.state(label)
        await self._refresh_status()
        self._focus_campaign()

    # ------------------------------------------------------------------
    # Console log
    # ------------------------------------------------------------------

    def _log(self, message: str) -> None:
        self._command_history.append(message)
        del self._command_history[:-100]
        lines = message.splitlines()
        self._feedback = " ".join(lines[:2])
        self._feedback_at = time.monotonic()
        self._refresh_status_now()

    async def _refresh_status(self) -> None:
        if self._shutting_down or self._status_refreshing:
            return
        self._status_refreshing = True
        try:
            idle_since, errors = await asyncio.to_thread(self._poll_tab_activity)
            await self._ensure_campaign_tabs(list(idle_since))
            self._tab_idle_since = idle_since
            self._activity_ready = True
            self._refresh_status_now()
            self._report_activity_errors(errors)
        except (OSError, RuntimeError) as error:
            self._tab_idle_since = {}
            self._activity_ready = True
            self._log(f"Process cleanup failed: {error}")
        finally:
            self._status_refreshing = False

    @staticmethod
    def _campaign_active(target: CampaignFolderState) -> bool:
        return target.busy or target.child is not None or target.external

    def _poll_tab_activity(self) -> tuple[dict[str, float | None], tuple[str, ...]]:
        """Check processes and persist idle deadlines off the UI thread."""
        idle_since: dict[str, float | None] = {}
        errors: list[str] = []
        with self._activity_poll_lock:
            for label in self._layout.installed():
                idle_since[label] = None  # an unknown process state never auto-hides
                try:
                    target = self._controller.reap(label)
                    idle_since[label] = self._idle_tracker.observe(
                        target.folder, active=self._campaign_active(target)
                    )
                except (OSError, RuntimeError, ValueError) as error:
                    errors.append(f"{label}: cannot establish tab idle time: {error}")
        return idle_since, tuple(errors)

    def _report_activity_errors(self, errors: tuple[str, ...]) -> None:
        if errors != self._activity_errors:
            self._activity_errors = errors
            if errors:
                self._log("\n".join(errors))

    def _log_updatable(self, message: str) -> None:
        if message != self._summary:
            self._summary = message
            self.query_one("#commands-summary", Static).update(
                Text(message, no_wrap=True, overflow="ellipsis")
            )

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    @staticmethod
    def _panel_text(value: str) -> str:
        return value.strip().lstrip("/").strip()

    # ------------------------------------------------------------------
    # The command panel
    # ------------------------------------------------------------------

    @property
    def _listed(self) -> list[Command]:
        return self.query_one(CommandPanel).listed

    def on_command_panel_submitted(self, event: CommandPanel.Submitted) -> None:
        text = event.text
        self._close_commands(
            restore_focus=not text or text.split()[0].lower() != "hide"
        )
        self.submit_command(text)

    def on_command_panel_preview_changed(
        self, event: CommandPanel.PreviewChanged
    ) -> None:
        self._refresh_status_now()

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        """The panel's arrow keys exist only while it is open, so the log keeps its own."""
        if action in {"command_next", "command_previous"}:
            return self._panel_open
        return True

    def action_open_commands(self, text: str = "") -> None:
        """``/`` and Ctrl+L: open the panel, ready to type a command."""
        if isinstance(self.screen, ModalScreen) or self._shutting_down:
            return
        if not self._panel_open:
            self._return_focus = self.focused
        self._panel_open = True
        self.query_one("#command-panel").add_class("open")
        self.query_one(CommandPanel).open(text)
        self._refresh_status_now()

    def _close_commands(self, *, restore_focus: bool = True) -> None:
        if not self._panel_open:
            return
        self._panel_open = False
        self.query_one("#command-panel").remove_class("open")
        self.query_one(CommandPanel).reset()
        previous, self._return_focus = self._return_focus, None
        if not restore_focus:
            self.screen.set_focus(None)
        elif (
            previous is not None
            and previous.is_attached
            and all(widget.display for widget in previous.ancestors_with_self)
        ):
            previous.focus()
        else:
            self._focus_campaign()
        self._refresh_status_now()

    def action_command_next(self) -> None:
        self.query_one(CommandPanel).move(1)

    def action_command_previous(self) -> None:
        self.query_one(CommandPanel).move(-1)

    def _complete_command(self) -> bool:
        return self.query_one(CommandPanel).complete()

    def submit_command(self, text: str) -> None:
        text = self._panel_text(text)
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
        if self._command_running and verb not in {"stop", "kill"}:
            if verb in {
                "help",
                "settings",
                "history",
                "search",
                "filter",
                "show",
                "hide",
            }:
                pass  # they only open a view
            else:
                self._log(
                    "> " + text + "\nrefused: a previous command is still running"
                )
                return
        argument = text.split(None, 1)[1].strip() if " " in text else ""
        if verb == "help":
            self.action_help()
            return
        if verb == "settings":
            self.action_settings()
            return
        if verb == "history":
            self.action_command_history()
            return
        if verb == "search":
            self.action_search_log()
            return
        if verb == "filter":
            self.action_filter_log()
            return
        if verb == "quit":
            if argument.lower() == "stop":
                self.action_shutdown_all()
            elif argument:
                self._log(f"> {text}\nerror: quit takes no argument, or stop.")
            else:
                self.action_detach()
            return
        active = self.query_one(TabbedContent).active
        if not slots and active:
            slots = [self._layout.slot_for(active)]
        if not slots and verb not in {"models"}:
            self._log(
                f"> {text}\nerror: {verb} requires a campaign number, range or folder name."
            )
            return
        if verb in {"show", "hide"}:
            missing = [
                f"campaign-{slot}"
                for slot in slots
                if not self.query(f"#panel-campaign-{slot}")
            ]
            if missing:
                self._log(
                    f"> {text}\nerror: {', '.join(missing)} not initialized; use run to create it."
                )
                if not self._panel_open:
                    self._focus_campaign()
                return
            for slot in slots:
                self._tab_overrides[f"campaign-{slot}"] = verb == "show"
            outcome = "shown" if verb == "show" else "hidden"
            self._log(
                f"> {text}\nTabs {outcome} for this session; execution is unchanged."
            )
            if not self._panel_open:
                self._focus_campaign()
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
            except (OSError, RuntimeError, ValueError) as error:
                self._log(f"> {text}\nstop failed: {error}")
            return
        if verb == "kill":
            threading.Thread(
                target=self._kill_worker,
                args=(slots, text),
                daemon=True,
                name="console-kill",
            ).start()
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
        if verb in {"start", "run"}:
            for slot in slots:
                label = f"campaign-{slot}"
                self._tab_overrides.pop(label, None)
                self._tab_idle_since[label] = None
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

    def _kill_worker(self, slots: list[int], text: str) -> None:
        """End campaigns off the UI thread: a kill waits for the process tree."""
        try:
            outcome = self._controller.execute("kill", slots, settings=LaunchSettings())
            message = "> " + text + "\n" + outcome.summary()
            for step in outcome.steps:
                if step.detail:
                    message += "\n  " + step.target + ": " + step.detail
        except Exception as error:  # noqa: BLE001 - every refusal reaches the log
            message = f"> {text}\nkill failed: {error}"
        try:
            self.call_from_thread(self._log, message)
        except RuntimeError:
            pass  # the console closed first

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
                result = self._controller.list_models(settings)
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
            if target.stage in {"launching", "running", "stopping"} or target.external:
                panel.set_process_running(True)
            elif target.stage in {"stopped", "failed", "completed", "idle"}:
                panel.set_process_running(False)
        self._sync_tab_visibility()
        self._refresh_tab_tags()
        hidden_running = sum(
            self._campaign_active(self._controller.state(pane.id))
            for pane in self.query(TabPane)
            if pane.id not in self._visible_tabs
        )
        warning = (
            f"{hidden_running} running campaign{'s' if hidden_running != 1 else ''} hidden | "
            if hidden_running
            else ""
        )
        if self._panel_open:
            preview = self._command_preview(
                self.query_one("#commands-input", Input).value
            )
            self._log_updatable(warning + (preview or PANEL_HINTS))
            return
        status = self._status_line()
        fresh = (
            self._feedback and time.monotonic() - self._feedback_at < FEEDBACK_SECONDS
        )
        self._log_updatable(
            warning
            + (f"{status} | {self._feedback}" if fresh else f"{status} · {KEY_HINTS}")
        )

    def _command_preview(self, value: str) -> str:
        """What the command being typed would do, before it is run."""
        text = self._panel_text(value)
        if not text:
            return ""
        try:
            verb, slots = parse_command(text)
        except CommandError:
            return ""  # do not flash validation errors while a command is incomplete
        active = self.query_one(TabbedContent).active
        if not slots and active:
            slots = [self._layout.slot_for(active)]
        targets = ", ".join(f"campaign-{slot}" for slot in slots)
        command = commands.find(verb)
        if command is None or not command.campaign or not targets:
            return command.summary if command is not None else ""
        if verb in {"run", "reset"}:
            reset = self._settings_reader.reset_config()
            action = "reset + start" if verb == "run" else "reset only"
            return f"DESTRUCTIVE {action} (no backup): {targets} | {reset.mode}"
        return f"{command.summary}: {targets}"

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
            stage = "running" if state.external else state.stage
            tag = tab_tag(
                stage, panel.progress_stalled(), panel.phase(), panel.official_outcome()
            )
            self._tag_tab(tabs, label, tag)

    def _pulse_tabs(self) -> None:
        if self._shutting_down:
            return
        self._pulse_on = not self._pulse_on
        self._refresh_tab_tags()

    def _tag_tab(self, tabs: TabbedContent, label: str, tag: str) -> None:
        """Colour the dot in front of a tab label; relabel only on a change."""
        glyph = "◆" if tag in OUTCOME_TAGS else "●"
        if tag in PULSING_TAGS and not self._pulse_on:
            glyph = "◐"
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

    def _official_note(self, label: str, stage: str) -> str:
        """The final benchmark's outcome, for a campaign that is not running."""
        if stage in {"launching", "running", "stopping", "resetting"}:
            return ""
        try:
            outcome = self.query_one(
                f"#panel-{label}", CampaignPanel
            ).official_outcome()
        except Exception:  # noqa: BLE001 - the tab is not mounted yet
            return ""
        return {
            "passed": " | official assessment: goal reached",
            "failed": " | official assessment: goal not reached",
        }.get(outcome, "")

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
            return f"{active}: {stage}{self._official_note(active, state.stage)}"
        return "no visible campaigns"

    async def _ensure_campaign_tabs(self, labels: list[str]) -> None:
        tabs = self.query_one(TabbedContent)
        known = {pane.id for pane in tabs.query(TabPane)}
        for label in labels:
            if label not in known:
                folder = self._layout.folder(self._layout.slot_for(label))
                before = next((name for name in sorted(known) if name > label), None)
                await tabs.add_pane(
                    TabPane(
                        label,
                        CampaignPanel(
                            sources=CampaignSources(campaign_root=folder),
                            campaign_root=folder,
                            show_hints=False,
                            id=f"panel-{label}",
                        ),
                        id=label,
                    ),
                    before=before,
                )
                known.add(label)

    async def _batch_finished(self) -> None:
        await self._ensure_campaign_tabs(self._layout.installed())
        await self._refresh_status()
        self._command_running = False
        self._command_thread = None

    def action_help(self) -> None:
        self.push_screen(ConsoleDetail("Campaign commands", help_text()))

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
        if self._panel_open:
            self.query_one("#commands-input", Input).focus()
        else:
            self._focus_campaign()

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
        """Ctrl+L opens the command panel, or closes it when it is open."""
        if isinstance(self.screen, ModalScreen):
            return
        if self._panel_open:
            self._close_commands()
        else:
            self.action_open_commands()

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
        if self._panel_open:
            self._close_commands()
            return
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
        tabs = self.query_one(TabbedContent)
        tabs.display = bool(self._visible_tabs) and not small
        empty = self.query_one("#empty-campaigns", Static)
        empty.display = not self._visible_tabs and not small
        if not self._activity_ready:
            message = "Checking campaign activity..."
        elif self.query(TabPane):
            message = "No active campaigns are displayed.\nUse /show 1 to inspect a campaign, /start 1 to resume, or /run 1 for a fresh run.\nPress / for commands. Nothing runs automatically."
        else:
            message = "No campaign folders are installed.\nUse /run 1 to initialize, reset and start campaign-1 from an existing recipe source.\nPress / for commands, F2 for settings. Nothing runs automatically."
        if message != self._empty_message:
            self._empty_message = message
            empty.update(message)
        self.query_one("#commands-floor").display = small

    def _sync_tab_visibility(self) -> None:
        if not self._activity_ready:
            return
        tabs = self.query_one(TabbedContent)
        labels = sorted(pane.id for pane in tabs.query(TabPane))
        now = time.time()
        visible = []
        for label in labels:
            since = self._tab_idle_since.get(label)
            automatic = (
                self._campaign_active(self._controller.state(label))
                or since is None
                or now - since < IDLE_TAB_SECONDS
            )
            if self._tab_overrides.get(label, automatic):
                visible.append(label)
        if visible != self._visible_tabs or not self._tab_visibility_applied:
            self._tab_visibility_applied = True
            previous = tabs.active
            self._visible_tabs = visible
            for label in visible:
                if not tabs.get_tab(label).display:
                    tabs.show_tab(label)
            selected = previous if previous in visible else ""
            if not selected and visible:
                index = labels.index(previous) if previous in labels else -1
                selected = next(
                    (label for label in labels[index + 1 :] if label in visible),
                    visible[0],
                )
            tabs.active = selected
            for label in labels:
                if label not in visible and tabs.get_tab(label).display:
                    tabs.hide_tab(label)
            if previous != selected and not self._panel_open:
                self.call_after_refresh(self._focus_campaign)
        self._update_campaign_visibility()

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
        elif self._panel_open:
            self._complete_command()
        else:
            self._cycle_campaign(1)

    def action_previous_tab(self) -> None:
        if isinstance(self.screen, ModalScreen):
            self.action_focus_previous()
        elif not self._panel_open:
            self._cycle_campaign(-1)

    def _cycle_campaign(self, direction: int) -> None:
        if isinstance(self.screen, ModalScreen):
            return
        tabs = self.query_one(TabbedContent)
        panes = self._visible_tabs
        if not panes:
            return
        if tabs.active not in panes or len(panes) == 1:
            tabs.active = panes[0]
            return
        index = (panes.index(tabs.active) + direction) % len(panes)
        self.screen.set_focus(None)
        tabs.active = panes[index]
        self.call_after_refresh(self._focus_campaign)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def action_shutdown_all(self) -> None:
        """Ctrl+Q: ask every owned campaign to stop, then exit.

        A campaign that has not stopped after ``STOP_PROMPT_SECONDS`` is put to the
        operator: kill it, leave it running, or keep waiting. Nothing is killed
        unless the operator says so.
        """
        if self._shutting_down:
            return
        self._shutting_down = True
        if self._panel_open:
            self._close_commands()
        controller = self._controller
        controller.latch_shutdown()
        self._log("Shutting down: stop requests sent to all owned campaigns...")

        def job() -> None:
            try:
                coordinator = ShutdownCoordinator(
                    controller,
                    lambda message: self.call_from_thread(self._log, message),
                    self._ask_after_stop,
                )
                outcome = coordinator.stop(
                    self._command_thread,
                    helper_grace=HELPER_SHUTDOWN_GRACE_SECONDS,
                    prompt_seconds=STOP_PROMPT_SECONDS,
                    wait_more_seconds=STOP_WAIT_MORE_SECONDS,
                )
                self._detached = list(outcome.detached)
                controller.reap_all()
                _, activity_errors = self._poll_tab_activity()
                self.call_from_thread(self._report_activity_errors, activity_errors)
                self._shutdown_complete = outcome.complete
            except (OSError, RuntimeError) as error:
                self.call_from_thread(self._log, f"Shutdown cleanup failed: {error}")
            finally:
                try:
                    self.call_from_thread(self.exit)
                except Exception:  # noqa: S110,BLE001 - the process exit must not hang
                    pass

        threading.Thread(target=job, daemon=True, name="console-shutdown").start()

    def _ask_after_stop(self, labels: list[str]) -> str:
        """Put stuck campaigns to the operator; block this worker for the answer."""
        answer: dict[str, str] = {}
        answered = threading.Event()

        def done(choice: str | None) -> None:
            answer["choice"] = choice or "wait"
            answered.set()

        self.call_from_thread(
            self.push_screen, StopPrompt(labels, STOP_PROMPT_SECONDS), done
        )
        answered.wait()
        return answer["choice"]

    def action_detach(self) -> None:
        """Alt+Q and /quit: leave the console, the campaigns keep running."""
        if self._shutting_down:
            return
        if self._command_running:
            self._log("quit refused: a reset or start is still running")
            return
        if self._panel_open:
            self._close_commands()
        self._shutting_down = True
        try:
            self._detached = self._controller.detach_all()
        except (OSError, RuntimeError) as error:
            self._shutting_down = False
            self._log(f"quit failed: {error}")
            return
        # Nothing is left for the exit path to stop.
        self._shutdown_complete = True
        self.exit()

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
    if "app" in locals() and app._detached:
        print(
            "Left running without this console: "
            + ", ".join(app._detached)
            + ". Open the console again to watch them, /stop to stop them, "
            "/kill to end them."
        )
    return 0


__all__ = [
    "HELP_TEXT",
    "TAB_TAG_COLOURS",
    "CampaignConsole",
    "CommandInputs",
    "ConsoleDetail",
    "SharedSettings",
    "StopPrompt",
    "run_console",
    "tab_tag",
]
