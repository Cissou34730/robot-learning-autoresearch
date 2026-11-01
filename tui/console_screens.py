"""Settings and decision screens for the operator console."""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Select, Static

from runner.launcher.options import PHASES
from tui.controller import LaunchSettings, ResetConfig

PHASE_LABELS = {
    "analyst": ("Analyst", "max"),
    "recipe": ("Recipe development", "high"),
    "startup": ("Startup", "high"),
    "research": ("Research (goal review, inquiries)", "high"),
}


def _model_options(models: list[tuple[str, str]], value: str) -> list[tuple[str, str]]:
    """The listed models, keeping a saved value that the list does not contain."""
    if value and value not in {model for _label, model in models}:
        return [(value, value), *models]
    return list(models)


class CommandInputs:
    """Session-only shared settings; empty values preserve launcher omission."""

    FIELD_IDS = (
        "cmd-model",
        "cmd-reasoning",
        "cmd-timesteps",
        "cmd-max-timesteps",
        "cmd-max-inquiries",
        "cmd-stop-timeout",
        *(f"cmd-{phase}-{part}" for phase in PHASES for part in ("model", "reasoning")),
    )
    # Model fields are pickers over the listed models; the others are text.
    MODEL_FIELD_IDS = ("cmd-model", *(f"cmd-{phase}-model" for phase in PHASES))

    def __init__(self, values: dict | None = None) -> None:
        self.values = {field: "" for field in self.FIELD_IDS}
        self.values.update(
            {
                "reset-mode": "Fresh",
                "reset-clean": True,
                "reset-recipe": ResetConfig().recipe_ref,
                "reset-baseline": "",
                "reset-skip-recipe": False,
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
            reasoning=text("cmd-reasoning"),
            timesteps=number("cmd-timesteps"),
            max_timesteps=number("cmd-max-timesteps"),
            max_inquiries=number("cmd-max-inquiries"),
            stop_timeout_seconds=number("cmd-stop-timeout"),
            phase_models={
                phase: value
                for phase in PHASES
                if (value := text(f"cmd-{phase}-model"))
            },
            phase_reasoning={
                phase: value
                for phase in PHASES
                if (value := text(f"cmd-{phase}-reasoning"))
            },
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
            skip_recipe_development=bool(self.values["reset-skip-recipe"])
            and mode == "Fresh",
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
    #phase-heading { height: 1; margin-top: 1; text-style: bold; }
    #phase-fields { height: auto; grid-size: 2; grid-rows: 2; grid-gutter: 1 2; }
    SharedSettings.narrow #phase-fields { grid-size: 1; }
    .setting-field { height: 2; }
    .setting-field Static { height: 1; }
    .setting-field Input { height: 1; border: none; padding: 0 1; background: $boost; }
    .setting-field Input:focus { text-style: bold; background: $primary 25%; }
    .setting-field Select { height: 1; }
    .setting-field SelectCurrent { border: none; background: $boost; }
    #model-status { height: auto; color: $text-muted; }
    #reset-heading { height: 1; margin-top: 1; text-style: bold; }
    #reset-controls { height: 3; }
    #reset-mode { width: 20; }
    SharedSettings SelectCurrent { border: solid $panel; }
    #reset-clean, #reset-skip-recipe { width: auto; border: none; padding: 1 0; }
    SharedSettings.narrow #reset-controls { layout: vertical; height: 9; }
    #reset-warning { height: auto; color: $warning; margin-top: 1; }
    #settings-error { height: auto; color: $error; }
    #settings-actions { height: 3; align-horizontal: right; }
    #settings-actions Button { margin-left: 1; border: none; padding: 1 1; }
    """

    def __init__(
        self,
        values: dict,
        *,
        models: list[tuple[str, str]] | None = None,
        load_models: Callable[[], list[tuple[str, str]]] | None = None,
    ) -> None:
        super().__init__()
        self.values = dict(values)
        self._models = models
        self._load_models = load_models

    def _field(self, field: str, label: str, placeholder: str) -> ComposeResult:
        with Vertical(classes="setting-field"):
            yield Static(label)
            value = self.values[field]
            if field in CommandInputs.MODEL_FIELD_IDS:
                yield Select(
                    _model_options(self._models or [], value),
                    prompt=placeholder,
                    allow_blank=True,
                    compact=True,
                    id=field,
                    **({"value": value} if value else {}),
                )
            else:
                yield Input(value=value, placeholder=placeholder, id=field)

    def compose(self) -> ComposeResult:
        fields = (
            ("cmd-model", "Model (all phases)", "gpt-6-luna (launcher default)"),
            (
                "cmd-reasoning",
                "Reasoning (all phases)",
                "Analyst max, other phases high",
            ),
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
            yield Static("", id="model-status", markup=False)
            with VerticalScroll(id="settings-scroll"):
                with Grid(id="launch-fields"):
                    for field, label, placeholder in fields:
                        yield from self._field(field, label, placeholder)
                yield Static(
                    "Per-phase backend — overrides Model / Reasoning",
                    id="phase-heading",
                )
                with Grid(id="phase-fields"):
                    for phase in PHASES:
                        label, reasoning = PHASE_LABELS[phase]
                        for part, placeholder in (
                            ("model", "Model (all phases)"),
                            ("reasoning", f"Reasoning (all phases), else {reasoning}"),
                        ):
                            yield from self._field(
                                f"cmd-{phase}-{part}", f"{label} {part}", placeholder
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
                    yield Checkbox(
                        "Skip recipe development (Fresh)",
                        value=self.values["reset-skip-recipe"],
                        id="reset-skip-recipe",
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
        if self._models is None and self._load_models is not None:
            self.query_one("#model-status", Static).update("Loading the model list…")
            self.run_worker(self._fetch_models, thread=True, exclusive=True)

    def _fetch_models(self) -> None:
        try:
            models = self._load_models()
        except Exception as error:  # noqa: BLE001 - the operator sees the reason
            self.app.call_from_thread(
                self._model_status, f"Model list unavailable: {error}"
            )
            return
        self.app.call_from_thread(self._show_models, models)

    def _model_status(self, text: str) -> None:
        if self.is_attached:
            self.query_one("#model-status", Static).update(text)

    def _show_models(self, models: list[tuple[str, str]]) -> None:
        if not self.is_attached:
            return
        self._models = models
        for field in CommandInputs.MODEL_FIELD_IDS:
            picker = self.query_one(f"#{field}", Select)
            value = "" if picker.is_blank() else str(picker.value)
            picker.set_options(_model_options(models, value))
            if value:
                picker.value = value
        self._model_status("")

    def on_resize(self) -> None:
        self.set_class(self.size.width < 70, "narrow")
        self.set_class(70 <= self.size.width < 110, "standard")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "reset-mode" and self.is_mounted:
            self._reset_fields()

    def _reset_fields(self) -> None:
        fresh = self.query_one("#reset-mode", Select).value == "Fresh"
        self.query_one("#reset-recipe-field").display = fresh
        self.query_one("#reset-skip-recipe").display = fresh
        self.query_one("#reset-baseline-field").display = not fresh

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "settings-cancel":
            self.action_cancel()
        elif event.button.id == "settings-apply":
            values = {
                field: self.query_one(f"#{field}", Input).value
                for field in CommandInputs.FIELD_IDS
                if field not in CommandInputs.MODEL_FIELD_IDS
            }
            for field in CommandInputs.MODEL_FIELD_IDS:
                picker = self.query_one(f"#{field}", Select)
                values[field] = "" if picker.is_blank() else str(picker.value)
            values.update(
                {
                    "reset-mode": str(self.query_one("#reset-mode", Select).value),
                    "reset-clean": self.query_one("#reset-clean", Checkbox).value,
                    "reset-recipe": self.query_one("#reset-recipe", Input).value,
                    "reset-baseline": self.query_one("#reset-baseline", Input).value,
                    "reset-skip-recipe": self.query_one(
                        "#reset-skip-recipe", Checkbox
                    ).value,
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


class StopPrompt(ModalScreen[str]):
    """Ctrl+Q asked campaigns to stop and some did not: kill, leave or wait."""

    BINDINGS: ClassVar[list] = [
        ("k", "choose('kill')", "Kill"),
        ("l", "choose('leave')", "Leave"),
        ("w", "choose('wait')", "Wait"),
        ("escape", "choose('wait')", "Wait"),
    ]
    CSS = """
    StopPrompt { align: center middle; background: $background 65%; }
    #stop-prompt { width: 80; max-width: 95%; height: auto; padding: 1 2; background: $surface; }
    #stop-prompt-title { text-style: bold; color: $warning; }
    #stop-prompt-actions { height: 3; margin-top: 1; }
    #stop-prompt-actions Button { margin-right: 1; }
    """

    def __init__(self, labels: list[str], seconds: float) -> None:
        super().__init__()
        self._labels = labels
        self._seconds = seconds

    def compose(self) -> ComposeResult:
        names = ", ".join(self._labels)
        with Vertical(id="stop-prompt"):
            yield Static(f"{names} did not stop", id="stop-prompt-title")
            yield Static(
                f"The stop request was sent {self._seconds:.0f} s ago and the "
                "launcher is still running.\n"
                "k  kill it now (ends the launcher and everything it started)\n"
                "l  leave it running and exit the console\n"
                "w  keep waiting",
                markup=False,
            )
            with Horizontal(id="stop-prompt-actions"):
                yield Button("Kill now (k)", variant="error", id="stop-kill")
                yield Button("Leave running (l)", id="stop-leave")
                yield Button("Keep waiting (w)", variant="primary", id="stop-wait")

    def action_choose(self, choice: str) -> None:
        self.dismiss(choice)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(
            {"stop-kill": "kill", "stop-leave": "leave"}.get(event.button.id, "wait")
        )
