"""The console's commands, defined once.

The registry drives the parser, the ``/`` list with its filter, the help text and
the "unknown command" message, so a command added here shows up everywhere.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

MAX_SLOTS = 5


@dataclass(frozen=True)
class Command:
    """One console command."""

    name: str
    summary: str
    # What may follow the name: shown beside it in the list.
    argument: str = ""
    # A campaign command acts on campaigns (1, 1-3, campaign-2, all) and, with no
    # target, on the active tab. The others act on the console or on the log.
    campaign: bool = False

    @property
    def takes_argument(self) -> bool:
        """Picking it from the list fills in its name so a target can follow."""
        return self.campaign


COMMANDS: tuple[Command, ...] = (
    Command("start", "start or resume (keeps the work)", "1-5", campaign=True),
    Command("run", "reset, then start (wipes measurements and logs)", "1-5", True),
    Command("stop", "ask the launcher to stop cleanly", "1-5 | all", campaign=True),
    Command("kill", "end the launcher and everything it started", "1-5 | all", True),
    Command("reset", "reset without starting (wipes)", "1-5", campaign=True),
    Command(
        "show", "show a tab for this console session (does not start it)", "1-5", True
    ),
    Command(
        "hide", "hide a tab for this console session (does not stop it)", "1-5", True
    ),
    Command("settings", "launch and reset options (F2)"),
    Command("models", "list the available models"),
    Command("diagnostics", "raw console logs of a launch", "1-5", campaign=True),
    Command("history", "recent commands (F3)"),
    Command("search", "search the event log (Ctrl+F)"),
    Command("filter", "filter the event log by kind"),
    Command("help", "commands and keys (F1)"),
    Command(
        "quit",
        "leave, the campaigns keep running  (quit stop: stop them first)",
        "stop",
    ),
)

NAMES: tuple[str, ...] = tuple(command.name for command in COMMANDS)
_BY_NAME = {command.name: command for command in COMMANDS}


def find(name: str) -> Command | None:
    return _BY_NAME.get(name.lower())


def matching(prefix: str) -> list[Command]:
    """The commands to list for what was typed: names that start with it first,
    then names that contain it; every command for an empty prefix."""
    typed = prefix.strip().lstrip("/").lower()
    if not typed:
        return list(COMMANDS)
    starts = [c for c in COMMANDS if c.name.startswith(typed)]
    contains = [c for c in COMMANDS if typed in c.name and c not in starts]
    return [*starts, *contains]


def help_lines() -> list[str]:
    """One line per command, for the help screen."""
    width = max(len(c.name) for c in COMMANDS)
    lines = []
    for command in COMMANDS:
        name = f"/{command.name}".ljust(width + 1)
        argument = f" {command.argument}" if command.argument else ""
        lines.append(f"{name}{argument:<12} {command.summary}")
    return lines


class CommandError(ValueError):
    """Invalid command text; the operator sees the message."""


def _unknown_command_message(word: str) -> str:
    """Name the valid commands, and the one the word was probably meant to be."""
    close = difflib.get_close_matches(word.lower(), NAMES, n=1, cutoff=0.6)
    guess = f" Did you mean {close[0]}?" if close else ""
    return f"Unknown command: {word!r}.{guess} Commands: {', '.join(NAMES)}."


def parse_command(text: str) -> tuple[str, list[int]]:
    """Parse one command line into ``(verb, slots)``.

    A leading ``/`` is allowed. A bare number selects that campaign; ``1-3``
    selects an inclusive range. ``campaign-k`` tokens also select explicit
    folders. Campaign actions without a target are allowed only inside a campaign
    tab, where the caller supplies that campaign. A command that is not about
    campaigns (``settings``, ``search``, ``quit`` ...) keeps its words for the
    caller and selects none.
    """
    tokens = text.strip().lstrip("/").split()
    if not tokens:
        raise CommandError("Empty command.")
    verb = tokens[0].lower()
    command = find(verb)
    if command is None:
        raise CommandError(_unknown_command_message(tokens[0]))
    if not command.campaign:
        return verb, []
    if len(tokens) == 1:
        return verb, []
    selection = tokens[1:]
    if selection == ["all"]:
        if verb not in {"stop", "kill"}:
            raise CommandError(
                "Use campaign numbers, ranges or folder names; all is for stop and kill only."
            )
        return verb, list(range(1, MAX_SLOTS + 1))
    slots: list[int] = []
    for token in selection:
        lowered = token.lower()
        if lowered.startswith("campaign-"):
            identity = lowered[len("campaign-") :]
            if identity not in {str(slot) for slot in range(1, MAX_SLOTS + 1)}:
                raise CommandError(f"Invalid campaign folder: {token!r}")
            selected = [int(identity)]
        else:
            match = re.fullmatch(r"([1-5])(?:-([1-5]))?", lowered)
            if match is None:
                raise CommandError(
                    f"Invalid target {token!r}; use a campaign number 1–5, a range such as 1-3, or a folder name."
                )
            first = int(match[1])
            last = int(match[2] or match[1])
            if first > last:
                raise CommandError(f"Invalid descending range: {token!r}")
            selected = range(first, last + 1)
        for slot in selected:
            if slot in slots:
                raise CommandError(f"Duplicate target: campaign-{slot}")
            slots.append(slot)
    return verb, sorted(slots)
