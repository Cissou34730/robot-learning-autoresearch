"""Command selection and completion without campaign execution."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from tui import commands
from tui.commands import Command


class CommandPanel(Vertical):
    class Submitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class PreviewChanged(Message):
        pass

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.listed: list[Command] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="command-prompt"):
            yield Static("/", id="command-slash")
            yield Input(placeholder="type a command", id="commands-input")
        yield OptionList(id="command-list")

    def open(self, text: str) -> None:
        field = self.query_one(Input)
        field.value = text
        self.fill(text)
        field.focus()
        field.cursor_position = len(text)

    def reset(self) -> None:
        self.query_one(Input).value = ""
        self.listed = []

    def fill(self, value: str) -> None:
        text = value.strip().lstrip("/").strip()
        word = text.split()[0] if text else ""
        if " " in text.strip():
            command = commands.find(word)
            self.listed = [command] if command is not None else []
        else:
            self.listed = commands.matching(word)
        options = self.query_one(OptionList)
        options.clear_options()
        width = max((len(command.name) for command in commands.COMMANDS), default=8)
        options.add_options(
            [
                Option(
                    Text.assemble(
                        (f"/{command.name:<{width}}", "bold"),
                        (
                            f" {command.argument:<9}" if command.argument else " " * 10,
                            "dim",
                        ),
                        f" {command.summary}",
                    ),
                    id=command.name,
                )
                for command in self.listed
            ]
        )
        if self.listed:
            options.highlighted = 0

    def highlighted(self) -> Command | None:
        index = self.query_one(OptionList).highlighted
        if index is None or not 0 <= index < len(self.listed):
            return None
        return self.listed[index]

    def move(self, direction: int) -> None:
        options = self.query_one(OptionList)
        if direction > 0:
            options.action_cursor_down()
        else:
            options.action_cursor_up()

    def complete(self) -> bool:
        chosen = self.highlighted()
        if chosen is None:
            return False
        field = self.query_one(Input)
        field.value = chosen.name + " "
        field.cursor_position = len(field.value)
        return True

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        text = event.value.strip().lstrip("/").strip()
        exact = commands.find(text.split()[0]) if text else None
        if exact is None:
            chosen = self.highlighted()
            if chosen is not None:
                if chosen.takes_argument:
                    self.complete()
                    return
                text = chosen.name
        self.post_message(self.Submitted(text))

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        if self.is_mounted:
            self.fill(event.value)
            self.post_message(self.PreviewChanged())

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        chosen = self.listed[event.option_index]
        if chosen.takes_argument:
            field = self.query_one(Input)
            field.value = chosen.name + " "
            field.focus()
            field.cursor_position = len(field.value)
        else:
            self.post_message(self.Submitted(chosen.name))
