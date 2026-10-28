"""The console's commands, defined once.

The registry drives the parser, the ``/`` list with its filter, the help text and
the "unknown command" message, so a command added here shows up everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass


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
