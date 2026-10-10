"""One bounded Principal Investigator session through the GitHub Copilot SDK.

The launcher owns the research protocol and decides whether a phase is complete;
this adapter owns only the Copilot runtime: session identity, the tool profile,
the command policy, and what reaches the console. Nothing printed here is read
back as a scientific fact.
"""

from __future__ import annotations

import argparse
import asyncio
import fnmatch
import json
import ntpath
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath

from runner.stop_control import stop_requested, wait_for_stop_request

ROOT = Path(__file__).resolve().parent.parent
UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
WINDOWS_PATH_PATTERN = re.compile(r"[A-Za-z]:[\\/](?:[^ \r\n:]+[\\/])*[^ \r\n:]+")
MAX_CONSOLE_POINTER_LENGTH = 96
UUID_SUFFIX_PATTERN = re.compile(
    r"(?<!\w)(?:"
    r"[0-9a-fA-F]{1,8}|"
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{0,4}|"
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{0,4}|"
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{0,4}|"
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{0,12}"
    r")$"
)
WINDOWS_PATH_SUFFIX_PATTERN = re.compile(r"[A-Za-z]:[\\/][^ \r\n:]*$")
WINDOWS_DRIVE_SUFFIX_PATTERN = re.compile(r"(?<!\w)[A-Za-z]:?$")
MAX_UNRESOLVED_CONSOLE_TOKEN = 512

EXIT_OK = 0
EXIT_SESSION_ERROR = 2
EXIT_NOT_AUTHENTICATED = 3
EXIT_MODEL_UNAVAILABLE = 4
EXIT_TIMEOUT = 5
EXIT_RUNTIME_FAILURE = 6
EXIT_INTERRUPTED = 130

SHUTDOWN_TIMEOUT_SECONDS = 30.0
FORCE_STOP_TIMEOUT_SECONDS = 10.0

_RESET = "\033[0m"
_DIM = "\033[90m"
# The model's own words: one bright block behind a matching gutter, so a line it
# writes is never mistaken for muted Runner output.
_MESSAGE = "\033[1;96m"
_PLAIN_GUTTER = "  "
_GUTTER = f"{_MESSAGE}{_PLAIN_GUTTER}│{_RESET}{_MESSAGE} "
_MARKER_COLORS = {
    ">": "\033[36m",
    "x": "\033[1;91m",
    "+": "\033[32m",
    "-": "\033[31m",
    "~": "\033[36m",
    "!": "\033[1;91m",
    "--": "\033[1;96m",
    "[session]": "\033[95m",
}


def format_duration(seconds: float) -> str:
    total = max(int(seconds), 0)
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{seconds:02d}s"
    return f"{seconds}s"


def format_console_line(text: str) -> str:
    if not sys.stdout.isatty():
        return text
    stripped = text.lstrip()
    indent = text[: len(text) - len(stripped)]
    marker, separator, remainder = stripped.partition(" ")
    color = _MARKER_COLORS.get(marker, "\033[36m")
    timestamp = f"{_DIM}[{datetime.now(UTC).astimezone():%H:%M:%S}]{_RESET}"
    if marker in {"x", "!", "--"}:
        return f"{timestamp} {indent}{color}{stripped}{_RESET}"
    return f"{timestamp} {indent}{color}{marker}{_RESET}{separator}{remainder}"


# Measured: this profile drops the runtime from 15 tools to 8 and roughly a
# third of the per-turn context, by removing tools no robotics experiment uses.
RESEARCH_TOOLS = [
    "view",
    "rg",
    "glob",
    "apply_patch",
    "powershell",
    "read_powershell",
    "stop_powershell",
    "list_powershell",
]

READ_ONLY_GIT = frozenset(
    {
        "status",
        "diff",
        "log",
        "show",
        "rev-parse",
        "ls-files",
        "ls-tree",
        "cat-file",
        "describe",
        "blame",
        "shortlog",
    }
)

GIT_DENIAL = "Mutating or unsupported Git commands are unavailable in PI sessions."

EXECUTION_DENIAL = (
    "Direct execution of reserved harness and protected entry points is unavailable."
)

SUITE_DENIAL = "Human-owned tests are unavailable for direct execution in PI sessions."

DEPENDENCY_DENIAL = (
    "Dependency installation and manifest changes are unavailable in PI sessions."
)

FILE_EDIT_DENIAL = (
    "This path is outside the editable scientific surface defined in AGENTS.md."
)

FILE_READ_DENIAL = (
    "Reserved harness, maintainer, and protected scientific files are unavailable "
    "for inspection in this phase."
)

RESERVED_SCRIPT_NAMES = (
    "run_experiment.py",
    "assessment.py",
    "final_benchmark.py",
    "migrate_policy_runtime.py",
    "reset_campaign.py",
    "run_research.ps1",
    "reset_research.ps1",
)

RESERVED_SCRIPT_PATHS = (
    "robot_learning/evaluate.py",
    "robot_learning/play.py",
    "robot_learning/train.py",
    "runner",
    "runner/*",
    "benchmark",
    "benchmark/*",
    "runner/build_brief.py",
    "runner/query_training_log.py",
    "researcher_*.py",
    "researcher_*.ps1",
    "researcher_opencode",
    "researcher_opencode/*",
    "tools",
    "tools/campaign_report.py",
    "docs",
    "docs/*",
    "tests",
    "tests/*",
)

RESERVED_MODULES = (
    "runner.run_experiment",
    "runner.assessment",
    "runner.migrate_policy_runtime",
    "runner.reset_campaign",
    "robot_learning.evaluate",
    "robot_learning.train",
    "robot_learning.play",
    "benchmark.final_benchmark",
    "benchmark.adapters.final_benchmark",
)

# These readers use the same reserved-path policy as execution.
READER_COMMANDS = frozenset(
    {
        "get-content",
        "gc",
        "cat",
        "type",
        "rg",
        "select-string",
        "sls",
        "findstr",
        "head",
        "tail",
        "more",
        "less",
        "get-childitem",
        "ls",
        "dir",
    }
)

INTERPRETERS = frozenset({"python", "python.exe", "python3", "py", "py.exe"})
POWERSHELL_HOSTS = frozenset({"powershell", "powershell.exe", "pwsh", "pwsh.exe"})
GIT_GLOBAL_VALUE_OPTIONS = frozenset(
    {
        "-c",
        "-C",
        "--config-env",
        "--exec-path",
        "--git-dir",
        "--namespace",
        "--super-prefix",
        "--work-tree",
    }
)
UV_GLOBAL_FLAG_OPTIONS = frozenset(
    {
        "-V",
        "-h",
        "-n",
        "-q",
        "-v",
        "--help",
        "--managed-python",
        "--no-cache",
        "--no-config",
        "--no-managed-python",
        "--no-progress",
        "--no-python-downloads",
        "--offline",
        "--quiet",
        "--system-certs",
        "--verbose",
        "--version",
    }
)
UV_RUN_FLAG_OPTIONS = frozenset(
    {
        "-U",
        "-h",
        "-m",
        "-n",
        "-q",
        "-s",
        "-v",
        "--active",
        "--all-extras",
        "--all-groups",
        "--all-packages",
        "--compile-bytecode",
        "--exact",
        "--frozen",
        "--gui-script",
        "--help",
        "--isolated",
        "--locked",
        "--managed-python",
        "--module",
        "--no-binary",
        "--no-build",
        "--no-build-isolation",
        "--no-cache",
        "--no-config",
        "--no-default-groups",
        "--no-dev",
        "--no-editable",
        "--no-env-file",
        "--no-index",
        "--no-managed-python",
        "--no-progress",
        "--no-project",
        "--no-python-downloads",
        "--no-sources",
        "--no-sync",
        "--offline",
        "--only-dev",
        "--quiet",
        "--refresh",
        "--reinstall",
        "--script",
        "--system-certs",
        "--upgrade",
        "--verbose",
    }
)

SEPARATORS = (";", "&&", "||", "|", "\n", "\r")

# Oversized tool results are written here instead of occupying the context for
# the rest of the session. The PI still opens them on demand. The
# threshold is held above the campaign artifacts (the brief, postmortems and
# evaluation panels), so primary scientific evidence is never offloaded out of
# the session by default.
LARGE_OUTPUT_DIR = ROOT / ".copilot" / "large-output"
LARGE_OUTPUT_MAX_BYTES = 262_144


def normalize_model(model: str) -> str:
    """OpenCode named the provider inside the model; the SDK names only the model."""
    return model.split("/", 1)[1] if "/" in model else model


def _repository_relative_target(target: str) -> str | None:
    if not isinstance(target, str) or not target.strip():
        return None
    path = Path(target.strip())
    if not path.is_absolute():
        path = ROOT / path
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix().casefold()
    except ValueError:
        return None


def compact_console_path(target: str) -> str:
    raw = str(target).strip()
    if re.match(r"^[A-Za-z]:[\\/]", raw):
        normalized = ntpath.normpath(raw).replace("\\", "/")
        root = ntpath.normpath(str(ROOT.resolve())).replace("\\", "/").rstrip("/")
        if normalized.casefold().startswith(root.casefold() + "/"):
            return normalized[len(root) + 1 :]
        parts = PureWindowsPath(raw).parts[-2:]
        return ".../" + "/".join(parts)
    path = Path(raw)
    if not path.is_absolute():
        return raw.replace("\\", "/")
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return ".../" + "/".join(path.parts[-2:])


def full_console_path(target: str) -> str:
    path = Path(str(target).strip())
    if not path.is_absolute():
        path = ROOT / path
    return str(path.resolve())


def compact_json_pointer(pointer: str) -> str:
    if len(pointer) <= MAX_CONSOLE_POINTER_LENGTH:
        return pointer
    tail_length = 24
    return (
        pointer[: MAX_CONSOLE_POINTER_LENGTH - tail_length - 3]
        + "..."
        + pointer[-tail_length:]
    )


def compact_console_text(text: object) -> str:
    value = UUID_PATTERN.sub("<id>", str(text or ""))
    return WINDOWS_PATH_PATTERN.sub(
        lambda match: compact_console_path(match.group(0)),
        value,
    )


def unresolved_console_suffix_start(text: str) -> int:
    start = len(text)
    for pattern in (
        UUID_SUFFIX_PATTERN,
        WINDOWS_PATH_SUFFIX_PATTERN,
        WINDOWS_DRIVE_SUFFIX_PATTERN,
    ):
        match = pattern.search(text)
        if match:
            start = min(start, match.start())
    return start


def is_pi_writable_path(target: str, *, preliminary: bool = False) -> bool:
    relative = _repository_relative_target(target)
    if relative is None:
        return False
    protected_scenario = {
        "robot_learning/scenario/__init__.py",
        "benchmark/adapters/final_benchmark.py",
        "benchmark/adapters/task_reference.py",
    }
    if relative in protected_scenario:
        return False
    if preliminary:
        return relative == "pi_workspace/scientific_model.md"
    return relative in {
        "robot_learning/train.py",
        "robot_learning/evaluate.py",
        "robot_learning/play.py",
        "robot_learning/training/current_params.json",
        "pi_workspace/operation_request.json",
    } or relative.startswith(
        (
            "robot_learning/scenario/",
            "robot_learning/training/",
            "robot_learning/lab/",
        )
    )


def file_edit_denial(target: str, *, preliminary: bool = False) -> str | None:
    if is_pi_writable_path(target, preliminary=preliminary):
        return None
    return FILE_EDIT_DENIAL


def file_read_denial(target: str, *, preliminary: bool = False) -> str | None:
    if preliminary:
        relative = _repository_relative_target(target)
        if relative is not None and relative.startswith("robot_learning/"):
            return None
    if is_pi_writable_path(target):
        return None
    if is_reserved_execution(target):
        return FILE_READ_DENIAL
    return None


def thousands(count: int) -> str:
    return f"{count / 1000:.0f}k" if count >= 1000 else str(count)


def command_segments(command: str) -> list[list[str]]:
    text = command
    for separator in SEPARATORS:
        text = text.replace(separator, "\x00")
    segments = []
    for segment in text.split("\x00"):
        try:
            tokens = shlex.split(segment, posix=False)
        except ValueError:
            tokens = segment.split()
        if tokens:
            segments.append(tokens)
    return segments


def clean_command_token(token: str) -> str:
    value = token.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value


def _uv_option_span(token: str, flag_options: frozenset[str]) -> int:
    """How many tokens a uv option consumes, including any separate value."""
    option = token.split("=", 1)[0]
    if "=" in token or option in flag_options:
        return 1
    if token.startswith("--"):
        return 2
    for position, character in enumerate(token[1:], start=1):
        if f"-{character}" in flag_options:
            continue
        return 1 if position + 1 < len(token) else 2
    return 1


def _command_name(token: str) -> str:
    return (
        Path(clean_command_token(token).strip("&.")).name.lower().removesuffix(".exe")
    )


def _uv_subcommand_index(tokens: list[str]) -> int | None:
    """Locate uv's subcommand after its global options."""
    index = 0
    while index < len(tokens) and tokens[index] == "&":
        index += 1
    if index >= len(tokens) or _command_name(tokens[index]) != "uv":
        return None
    index += 1
    while index < len(tokens):
        token = clean_command_token(tokens[index])
        if not token.startswith("-") or token == "-":
            return index
        if token == "--":
            return None
        index += _uv_option_span(token, UV_GLOBAL_FLAG_OPTIONS)
    return None


def strip_launcher_prefix(tokens: list[str]) -> list[str]:
    """Drop a leading `uv [global flags] run [run flags]` by option arity."""
    subcommand_index = _uv_subcommand_index(tokens)
    if (
        subcommand_index is None
        or clean_command_token(tokens[subcommand_index]).lower() != "run"
    ):
        return tokens
    index = subcommand_index + 1
    while index < len(tokens) and tokens[index].startswith("-"):
        if tokens[index] == "--":
            index += 1
            break
        index += _uv_option_span(tokens[index], UV_RUN_FLAG_OPTIONS)
    return tokens[index:]


def uv_run_options(tokens: list[str]) -> list[str]:
    """Return only uv run's options, stopping before the launched command."""
    subcommand_index = _uv_subcommand_index(tokens)
    if (
        subcommand_index is None
        or clean_command_token(tokens[subcommand_index]).lower() != "run"
    ):
        return []
    options: list[str] = []
    index = subcommand_index + 1
    while index < len(tokens) and tokens[index].startswith("-"):
        if tokens[index] == "--":
            break
        span = _uv_option_span(tokens[index], UV_RUN_FLAG_OPTIONS)
        options.append(tokens[index])
        index += span
    return options


def execution_target(tokens: list[str]) -> str | None:
    """What this segment would actually run, ignoring anything it merely names."""
    while tokens and tokens[0] == "&":
        tokens = tokens[1:]
    if not tokens:
        return None
    if tokens[0].lower().strip("&.") in READER_COMMANDS:
        return None
    tokens = strip_launcher_prefix(tokens)
    if not tokens:
        return None
    executable = Path(clean_command_token(tokens[0])).name.lower()
    if executable in POWERSHELL_HOSTS:
        arguments = tokens[1:]
        for index, argument in enumerate(arguments):
            if argument.lower() in {"-file", "-f"} and index + 1 < len(arguments):
                return clean_command_token(arguments[index + 1])
            if argument.lower() in {"-command", "-c"}:
                return None
        return clean_command_token(tokens[0])
    if executable not in INTERPRETERS:
        return clean_command_token(tokens[0])
    arguments = tokens[1:]
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "-m" and index + 1 < len(arguments):
            return clean_command_token(arguments[index + 1])
        if argument in {"-c", "--command"}:
            # Inline code names no target; the guardrail stops here by design.
            return None
        if argument.startswith("-"):
            index += 1
            continue
        return clean_command_token(argument)
    return None


def is_reserved_execution(target: str | None) -> bool:
    if not target:
        return False
    relative = _repository_relative_target(target)
    normalized = (relative or target).replace("\\", "/").lstrip("./").lower()
    if Path(normalized).name in RESERVED_SCRIPT_NAMES:
        return True
    if any(
        fnmatch.fnmatchcase(normalized, path) or normalized.endswith("/" + path)
        for path in RESERVED_SCRIPT_PATHS
    ):
        return True
    return normalized in RESERVED_MODULES


def denied_git_subcommand(tokens: list[str]) -> str | None:
    """The subcommand when it is not a read-only one, so unknown verbs deny."""
    executable_index = next(
        (
            index
            for index, token in enumerate(tokens)
            if Path(clean_command_token(token).strip("&."))
            .name.lower()
            .removesuffix(".exe")
            == "git"
        ),
        None,
    )
    if executable_index is None:
        return None
    index = executable_index + 1
    while index < len(tokens):
        token = clean_command_token(tokens[index])
        option = token.split("=", 1)[0]
        if option in GIT_GLOBAL_VALUE_OPTIONS:
            index += 1 if "=" in token else 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        subcommand = Path(token).name.lower().removesuffix(".exe")
        return None if subcommand in READ_ONLY_GIT else subcommand
    return "git"


def names_targeted_test_file(token: str) -> bool:
    """Whether a pytest argument selects a specific test file in the worktree.

    A selector is an existing file, or a node id inside one, never a directory:
    `pytest tests` runs the whole tree, so it stays repository-wide.
    """
    path = Path(token.split("::", 1)[0])
    resolved = (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    return resolved.is_file() and resolved.is_relative_to(ROOT)


# Pytest options that consume no value. The live set is derived from pytest's
# own parser declarations; this frozen set is only the conservative fallback
# for a worktree where pytest cannot be introspected. An option absent from
# whichever set is active is treated as value-taking, so an unknown option
# cannot expose its value as a selector and a repository-wide run stays denied.
PYTEST_FALLBACK_FLAG_OPTIONS = frozenset(
    {
        "-V",
        "-h",
        "-l",
        "-q",
        "-s",
        "-v",
        "-x",
        "--cache-clear",
        "--co",
        "--collect-in-virtualenv",
        "--collect-only",
        "--collectonly",
        "--continue-on-collection-errors",
        "--disable-plugin-autoload",
        "--disable-pytest-warnings",
        "--disable-warnings",
        "--doctest-continue-on-failure",
        "--doctest-ignore-import-errors",
        "--doctest-modules",
        "--exitfirst",
        "--failed-first",
        "--ff",
        "--fixtures",
        "--fixtures-per-test",
        "--force-short-summary",
        "--full-trace",
        "--fulltrace",
        "--funcargs",
        "--help",
        "--keep-duplicates",
        "--keepduplicates",
        "--last-failed",
        "--lf",
        "--lsof",
        "--markers",
        "--new-first",
        "--nf",
        "--no-fold-skipped",
        "--no-header",
        "--no-showlocals",
        "--no-summary",
        "--noconftest",
        "--pdb",
        "--pyargs",
        "--quiet",
        "--runxfail",
        "--setup-only",
        "--setup-plan",
        "--setup-show",
        "--setuponly",
        "--setupplan",
        "--setupshow",
        "--showlocals",
        "--stepwise",
        "--stepwise-reset",
        "--stepwise-skip",
        "--strict-config",
        "--strict-markers",
        "--strict",
        "--sw",
        "--sw-reset",
        "--sw-skip",
        "--trace",
        "--trace-config",
        "--traceconfig",
        "--verbose",
        "--version",
        "--xfail-tb",
    }
)

_PYTEST_FLAG_OPTIONS: frozenset[str] | None = None


def _declared_pytest_flag_options() -> frozenset[str]:
    """The value-less options the installed pytest itself declares.

    Pytest registers its options when its plugins run `pytest_addoption` on a
    parser; calling those declarations on a fresh parser reproduces the option
    knowledge without configuring or parsing a session. An empty result lets
    the caller fall back conservatively.
    """
    try:
        import importlib
        import pkgutil

        import _pytest
        from _pytest.config.argparsing import Parser

        parser = Parser(_ispytest=True)
    except Exception:  # noqa: BLE001 - pytest is best-effort optional here
        return frozenset()
    for info in pkgutil.walk_packages(_pytest.__path__, prefix="_pytest."):
        try:
            module = importlib.import_module(info.name)
            addoption = getattr(module, "pytest_addoption", None)
            if addoption is not None:
                addoption(parser)
        except Exception:  # noqa: BLE001, S112 - one broken module must not stop the rest
            continue
    options: set[str] = set()
    for group in parser._groups:
        for action in group._arggroup._actions:
            if action.nargs == 0:
                options.update(action.option_strings)
    return frozenset(options)


def pytest_flag_options() -> frozenset[str]:
    """Value-less pytest options, derived from pytest's own declarations."""
    global _PYTEST_FLAG_OPTIONS
    if _PYTEST_FLAG_OPTIONS is None:
        declared = _declared_pytest_flag_options()
        _PYTEST_FLAG_OPTIONS = declared or PYTEST_FALLBACK_FLAG_OPTIONS
    return _PYTEST_FLAG_OPTIONS


def _short_option_span(token: str, flag_options: frozenset[str]) -> int:
    """How many tokens a short-option token consumes, its value included.

    A combined or repeated short flag such as `-qx` carries only value-less
    options, so it consumes nothing beyond itself. The first unknown or
    value-taking short option consumes the rest of the token as its inline
    value, or the following token when the token ends there.
    """
    for position, character in enumerate(token[1:], start=1):
        if f"-{character}" in flag_options:
            continue
        return 1 if position + 1 < len(token) else 2
    return 1


def is_repository_wide_pytest(tokens: list[str]) -> bool:
    executable_index = next(
        (
            index
            for index, token in enumerate(tokens)
            if Path(clean_command_token(token)).name.lower().removesuffix(".exe")
            == "pytest"
        ),
        None,
    )
    if executable_index is None:
        return False
    flag_options = pytest_flag_options()
    rest = tokens[executable_index + 1 :]
    index = 0
    positional_only = False
    while index < len(rest):
        token = rest[index]
        if positional_only:
            if names_targeted_test_file(token):
                return False
            index += 1
            continue
        if token == "--":
            positional_only = True
            index += 1
            continue
        if token.startswith("--"):
            # `--option=value` carries its value inline. A flag-only option
            # consumes nothing, so a selector that follows it stays visible;
            # an option pytest does not declare is assumed to take a value.
            if "=" in token or token in flag_options:
                index += 1
            else:
                index += 2
            continue
        if token.startswith("-") and len(token) > 1:
            index += _short_option_span(token, flag_options)
            continue
        if names_targeted_test_file(token):
            return False
        index += 1
    return True


def is_dependency_management(tokens: list[str]) -> bool:
    """Whether a command changes or extends the fixed project dependency set."""
    if not tokens:
        return False
    executable_index = 0
    while executable_index < len(tokens) and tokens[executable_index] == "&":
        executable_index += 1
    if executable_index >= len(tokens):
        return False
    lowered = [token.lower() for token in tokens]
    executable = _command_name(tokens[executable_index])
    if executable == "uvx":
        return True
    if executable == "uv":
        subcommand_index = _uv_subcommand_index(tokens)
        if subcommand_index is None:
            return False
        operation = clean_command_token(tokens[subcommand_index]).lower()
        if operation in {"add", "remove", "sync", "lock", "pip", "tool"}:
            return True
        if operation == "run":
            run_options = [token.lower() for token in uv_run_options(tokens)]
            if any(token.startswith(("--with", "-w")) for token in run_options):
                return True
            return is_dependency_management(strip_launcher_prefix(tokens))
    if executable in {"pip", "pip3", "pipx"}:
        return any(operation in lowered[1:] for operation in ("install", "uninstall"))
    if executable in INTERPRETERS and "-m" in lowered:
        module_index = lowered.index("-m") + 1
        if module_index < len(lowered) and lowered[module_index] == "pip":
            return any(
                operation in lowered[module_index + 1 :]
                for operation in ("install", "uninstall")
            )
    return executable in {"install-module", "install-package"}


def command_denial(command: str, *, preliminary: bool = False) -> str | None:
    """The reason this command is refused, or None when it may run.

    Explicit readers use the current phase's reserved-read policy.
    Direct execution stays restricted in every phase.
    This is a tool boundary, not a sandbox --
    `uv run python -c` can still do anything the researcher could.
    """
    for tokens in command_segments(command):
        if is_dependency_management(tokens):
            return DEPENDENCY_DENIAL
        reader_tokens = tokens
        while reader_tokens and reader_tokens[0] == "&":
            reader_tokens = reader_tokens[1:]
        reader_name = (
            Path(clean_command_token(reader_tokens[0]))
            .name.lower()
            .removesuffix(".exe")
            if reader_tokens
            else ""
        )
        if reader_name in READER_COMMANDS:
            pattern_pending = reader_name in {"rg", "select-string", "sls", "findstr"}
            skip_pattern_value = False
            for token in reader_tokens[1:]:
                path = clean_command_token(token)
                if skip_pattern_value:
                    skip_pattern_value = False
                    continue
                if path.lower() in {"-e", "--regexp", "-pattern"}:
                    skip_pattern_value = True
                    pattern_pending = False
                    continue
                if path.lower().startswith(("--regexp=", "-pattern=")):
                    pattern_pending = False
                    continue
                if path.lower() in {"-path", "-literalpath"}:
                    pattern_pending = False
                    continue
                if path.startswith("-") and "=" in path:
                    path = clean_command_token(path.split("=", 1)[1])
                elif path.startswith("-"):
                    continue
                if pattern_pending:
                    pattern_pending = False
                    continue
                if file_read_denial(path, preliminary=preliminary):
                    return FILE_READ_DENIAL
        target = execution_target(tokens)
        if not target:
            continue
        name = Path(target).name.lower().removesuffix(".exe")
        if is_reserved_execution(target):
            return EXECUTION_DENIAL
        if name == "git" and denied_git_subcommand(tokens):
            return GIT_DENIAL
        if name == "pytest":
            return SUITE_DENIAL
    return None


def shell_command_text(request: object) -> str:
    segments = [
        getattr(segment, "full_command_text", "") or ""
        for segment in (getattr(request, "command_segments", None) or [])
    ]
    return "\n".join([getattr(request, "full_command_text", "") or "", *segments])


def worktree_status() -> dict[str, str]:
    """Path to Git status, so a file written by any means is still observed.

    The runtime's own change events only cover its edit tools, and this
    researcher writes most files through the shell.
    """
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    entries = {}
    for line in completed.stdout.splitlines():
        if len(line) > 3:
            entries[line[3:].strip().strip('"')] = line[:2].strip()
    return entries


def changed_since(before: dict[str, str]) -> list[str]:
    after = worktree_status()
    return sorted(
        path for path in set(before) | set(after) if before.get(path) != after.get(path)
    )


def offload_snapshot() -> set[str]:
    if not LARGE_OUTPUT_DIR.is_dir():
        return set()
    return {entry.name for entry in LARGE_OUTPUT_DIR.iterdir() if entry.is_file()}


def offloaded_since(before: set[str]) -> tuple[int, int]:
    """How much tool output never entered the context, as count and bytes.

    Per-session cost tracks how much work the researcher chose to do, so only a
    direct measure of the mechanism can say whether offloading is doing anything.
    """
    if not LARGE_OUTPUT_DIR.is_dir():
        return (0, 0)
    written = [
        entry
        for entry in LARGE_OUTPUT_DIR.iterdir()
        if entry.is_file() and entry.name not in before
    ]
    return (len(written), sum(entry.stat().st_size for entry in written))


def _console_width() -> int:
    return max(shutil.get_terminal_size(fallback=(100, 24)).columns, 40)


class Console:
    """Everything the human sees, and nothing the protocol reads back."""

    def __init__(self, label: str = "", columns: int | None = None) -> None:
        # Which experiment and phase this session is, so one long console log
        # stays attributable without reading backwards for the last banner.
        self.label = label
        self._mid_stream = False
        self._at_line_start = True
        self._message_width = max((columns or _console_width()) - 4, 20)
        self._compact_buffer = ""
        self._message_buffer = ""
        self._message_spacing = ""
        self._message_column = 0
        self._message_continues_word = False
        self._turn = 0
        self._turn_started_at: float | None = None
        self._turn_model = ""
        self._turn_tools = 0
        self._turn_files = 0
        self._turn_prompt_at_start = 0
        self._turn_cache_read_at_start = 0
        self._turn_output_at_start = 0
        self.changed_files: dict[str, str] = {}
        self.prompt_tokens = 0
        self.cache_read_tokens = 0
        self.cache_write_tokens = 0
        self.output_tokens = 0
        self.reported_usage: set[str] = set()
        self.nano_aiu = 0.0
        self.nano_aiu_by_type: dict[str, float] = {}
        self.session_error: str | None = None
        self.denials = 0
        self.tool_calls = 0
        self.tool_counts: dict[str, int] = {}
        self.denied_calls: set[str] = set()
        self.active_tools: dict[str, tuple[str, object]] = {}

    def tagged(self, text: str) -> str:
        return f"[{self.label}] {text}" if self.label else text

    def turn_start(self, model: str | None = None) -> None:
        """Reset per-turn counters without narrating runtime turns."""
        self._turn += 1
        self._turn_started_at = time.monotonic()
        self._turn_model = model or ""
        self._turn_tools = 0
        self._turn_files = 0
        self._turn_prompt_at_start = self.prompt_tokens
        self._turn_cache_read_at_start = self.cache_read_tokens
        self._turn_output_at_start = self.output_tokens

    def turn_end(self) -> None:
        """Close per-turn accounting without narrating runtime turns."""
        if self._turn_started_at is None:
            return
        self._turn_started_at = None

    def line(self, text: str) -> None:
        self._close_message()
        print(format_console_line(text), flush=True)

    def _close_message(self) -> None:
        """End the model's block, so the next fact starts at column zero."""
        if not self._mid_stream:
            return
        self._buffer_console_text("", final=True)
        self._flush_message(final=True)
        if sys.stdout.isatty():
            sys.stdout.write(_RESET)
        if not self._at_line_start:
            print(flush=True)
        self._mid_stream = False
        self._at_line_start = True
        self._compact_buffer = ""
        self._message_buffer = ""
        self._message_spacing = ""
        self._message_column = 0
        self._message_continues_word = False

    def _message_newline(self) -> None:
        print(flush=True)
        self._at_line_start = True
        self._message_spacing = ""
        self._message_column = 0
        self._message_continues_word = False

    def _write_message_word(self, word: str) -> None:
        spacing = self._message_spacing
        if (
            not self._at_line_start
            and self._message_column + len(spacing) + len(word) > self._message_width
        ):
            self._message_newline()
            spacing = ""
        if self._at_line_start:
            sys.stdout.write(_GUTTER if sys.stdout.isatty() else _PLAIN_GUTTER)
            self._at_line_start = False
        elif spacing:
            sys.stdout.write(spacing)
            self._message_column += len(spacing)
        sys.stdout.write(word)
        self._message_column += len(word)
        self._message_spacing = ""
        sys.stdout.flush()

    def _flush_message(self, *, final: bool) -> None:
        tokens = re.findall(r"\n|[^\S\n]+|\S+", self._message_buffer)
        for token in tokens:
            if token == "\n":
                self._message_newline()
            elif token.isspace():
                self._message_spacing += token
                self._message_continues_word = False
            elif self._message_continues_word and not self._message_spacing:
                sys.stdout.write(token)
                sys.stdout.flush()
                self._message_column += len(token)
            else:
                self._write_message_word(token)
                self._message_continues_word = True
        self._message_buffer = ""
        if final and self._message_spacing and not self._at_line_start:
            sys.stdout.write(self._message_spacing)
            sys.stdout.flush()
            self._message_column += len(self._message_spacing)
            self._message_spacing = ""

    def _buffer_console_text(self, text: str, *, final: bool) -> None:
        self._compact_buffer += text
        if final:
            split_at = len(self._compact_buffer)
        else:
            split_at = unresolved_console_suffix_start(self._compact_buffer)
            if len(self._compact_buffer) - split_at > MAX_UNRESOLVED_CONSOLE_TOKEN:
                split_at = len(self._compact_buffer)
        if split_at == 0:
            return
        ready = self._compact_buffer[:split_at]
        self._compact_buffer = self._compact_buffer[split_at:]
        self._message_buffer += compact_console_text(ready)

    def delta(self, text: str) -> None:
        if not text:
            return
        if not self._mid_stream:
            self._mid_stream = True
            self._at_line_start = True
            if sys.stdout.isatty():
                sys.stdout.write(_MESSAGE)
        self._buffer_console_text(text, final=False)
        self._flush_message(final=False)

    def message(self, text: str) -> None:
        if self._mid_stream:
            self._buffer_console_text("", final=True)
            self._flush_message(final=True)
            return
        if not text:
            return
        self.delta(text)
        self._close_message()

    def tool(
        self, name: str, arguments: object, tool_call_id: str | None = None
    ) -> None:
        self.tool_calls += 1
        self.tool_counts[name] = self.tool_counts.get(name, 0) + 1
        self._turn_tools += 1
        if tool_call_id:
            self.active_tools[tool_call_id] = (name, arguments)
        detail = ""
        if isinstance(arguments, dict):
            if name == "artifact_evidence_query":
                operation_id = arguments.get("operation_id")
                action = arguments.get("action")
                pointers: list[str] = []
                if action == "discover":
                    pointers.append(
                        compact_json_pointer(str(arguments.get("prefix") or "/"))
                    )
                elif action == "batch":
                    queries = arguments.get("queries")
                    if isinstance(queries, list):
                        valid_pointers = [
                            query["path"]
                            for query in queries
                            if isinstance(query, dict)
                            and isinstance(query.get("path"), str)
                            and query["path"].startswith("/")
                        ]
                        pointers.extend(
                            compact_json_pointer(pointer)
                            for pointer in valid_pointers[:3]
                        )
                        if len(valid_pointers) > 3:
                            pointers.append(
                                f"+{len(valid_pointers) - 3} more"
                            )
                elif isinstance(arguments.get("path"), str):
                    pointers.append(
                        compact_json_pointer(str(arguments["path"]))
                    )
                parts = [
                    str(value)
                    for value in (operation_id, action)
                    if isinstance(value, (str, int)) and str(value)
                ]
                if pointers:
                    parts.append(", ".join(pointers))
                detail = " | ".join(parts)
            elif name == "powershell":
                description = arguments.get("description")
                command = arguments.get("command")
                detail = " | ".join(
                    str(value)
                    for value in (description, f"cwd {ROOT}", command)
                    if isinstance(value, str) and value
                )
            elif name in {"rg", "glob"}:
                pattern = arguments.get("pattern") or arguments.get("query")
                paths = arguments.get("paths") or arguments.get("path")
                rendered_paths = []
                if isinstance(paths, str):
                    rendered_paths = [full_console_path(paths)]
                elif isinstance(paths, list):
                    rendered_paths = [full_console_path(str(path)) for path in paths]
                else:
                    rendered_paths = [str(ROOT.resolve())]
                parts = []
                if pattern:
                    parts.append(f"pattern {pattern}")
                if rendered_paths:
                    parts.append("paths " + ", ".join(rendered_paths))
                detail = " | ".join(parts)
            else:
                raw = next(
                    (
                        arguments[key]
                        for key in (
                            "description",
                            "path",
                            "filePath",
                            "file_path",
                            "command",
                            "commandLine",
                            "query",
                            "pattern",
                            "shellId",
                            "shell_id",
                            "session_id",
                        )
                        if isinstance(arguments.get(key), (str, int))
                        and arguments[key] != ""
                    ),
                    "",
                )
                detail = str(raw)
                if isinstance(raw, str) and any(
                    key in arguments and arguments.get(key) == raw
                    for key in ("path", "filePath", "file_path")
                ):
                    detail = full_console_path(raw)
        if name == "apply_patch":
            patch = (
                arguments.get("input") or arguments.get("patch")
                if isinstance(arguments, dict)
                else arguments
            )
            if isinstance(patch, str):
                # Show only file headers, never the potentially large patch body.
                prefixes = (
                    "*** Update File: ",
                    "*** Add File: ",
                    "*** Delete File: ",
                    "*** Move to: ",
                )
                targets = []
                for line in patch.splitlines():
                    if line.startswith(prefixes):
                        targets.append(full_console_path(line.split(": ", 1)[1]))
                if targets:
                    detail = ", ".join(targets)
        detail = " ".join(detail.split())
        self.line(f"  > {name}: {detail}" if detail else f"  > {name}")

    def tool_failed(
        self, error: object, name: str = "tool", arguments: object = None
    ) -> None:
        target = ""
        if isinstance(arguments, dict):
            for key in ("path", "filePath", "query", "command", "commandLine"):
                raw = arguments.get(key)
                if raw:
                    target = (
                        full_console_path(str(raw))
                        if key in {"path", "filePath"}
                        else str(raw)
                    )
                    break
            target = " ".join(target.split())
        reason = " ".join(compact_console_text(error).split())
        operation = f"{name} ({target})" if target else name
        self.line(f"  x {operation} failed: {reason}")

    def denied(self, reason: str, tool_call_id: str | None = None) -> None:
        self.denials += 1
        if tool_call_id:
            self.denied_calls.add(tool_call_id)
        self.line(f"  x {reason.splitlines()[0]}")

    def file_changed(self, operation: str, path: str) -> None:
        operation_request = (
            Path(path).as_posix().endswith("pi_workspace/operation_request.json")
        )
        path = full_console_path(path)
        marker = {"created": "+", "deleted": "-"}.get(str(operation), "~")
        if self.changed_files.get(path) != marker:
            self.changed_files[path] = marker
            self._turn_files += 1
            suffix = " | PI operation request updated" if operation_request else ""
            self.line(f"  {marker} {path}{suffix}")

    def error(self, message: str) -> None:
        self.session_error = message
        self.line(f"  ! session error: {message}")

    def summary(
        self,
        session_id: str,
        changed: list[str],
        offloaded: tuple[int, int] = (0, 0),
        elapsed_seconds: float = 0.0,
    ) -> None:
        """Expose unannounced changes; lifecycle summaries come from the Runner."""
        del session_id, offloaded, elapsed_seconds
        for path in changed:
            path = full_console_path(path)
            if path not in self.changed_files:
                self.line(f"  ~ {path}")

    def work(self, offloaded: tuple[int, int]) -> str:
        count, size = offloaded
        offload = f", offloaded {count} ({size // 1024} KB)" if count else ""
        return f"tools {self.tool_calls}{offload}"

    def usage(self) -> str:
        """Cost as billed: cached prompt tokens are a tenth the price of fresh ones,
        so a single token total would hide most of what a session actually costs."""
        prompt = f"prompt {thousands(self.prompt_tokens)}"
        if self.prompt_tokens:
            share = round(100 * self.cache_read_tokens / self.prompt_tokens)
            prompt += f" ({share}% cached)"
        return f"{self.nano_aiu / 1e9:.2f} AIU{self.cost_split()}, {prompt}"

    def cost_split(self) -> str:
        """Admitting new context costs over ten times re-reading it, so the split
        says whether to shrink what enters the session or what it replies."""
        by_type = self.nano_aiu_by_type
        new = by_type.get("input", 0.0) + by_type.get("cache_write", 0.0)
        read = by_type.get("cache_read", 0.0)
        output = by_type.get("output", 0.0)
        if not (new or read or output):
            return ""
        return (
            f" (new {new / 1e9:.2f} / read {read / 1e9:.2f} / out {output / 1e9:.2f})"
        )


def build_handlers(
    console: Console, finished: asyncio.Event, *, preliminary: bool = False
):
    from copilot.rpc import PermissionDecisionApproveOnce, PermissionDecisionReject
    from copilot.session_events import (
        AssistantMessageData,
        AssistantMessageDeltaData,
        AssistantTurnEndData,
        AssistantTurnStartData,
        AssistantUsageData,
        PermissionRequestRead,
        PermissionRequestShell,
        PermissionRequestWrite,
        SessionErrorData,
        SessionIdleData,
        SessionWorkspaceFileChangedData,
        ToolExecutionCompleteData,
        ToolExecutionStartData,
    )

    def on_event(event) -> None:
        data = event.data
        if isinstance(data, AssistantMessageDeltaData):
            console.delta(data.delta_content or "")
        elif isinstance(data, AssistantMessageData):
            console.message(data.content or "")
        elif isinstance(data, AssistantTurnStartData):
            console.turn_start(getattr(data, "model", None))
        elif isinstance(data, AssistantTurnEndData):
            console.turn_end()
        # AssistantReasoningData and AssistantReasoningDeltaData are deliberately
        # not routed: the console reports the work a session did, not the text it
        # thought through on the way there.
        elif isinstance(data, ToolExecutionStartData):
            console.tool(data.tool_name, data.arguments, data.tool_call_id)
        elif isinstance(data, ToolExecutionCompleteData):
            tool = console.active_tools.pop(data.tool_call_id, None)
            # A call this harness rejected already reported its reason.
            if (
                not data.success
                and data.error
                and data.tool_call_id not in console.denied_calls
            ):
                name, arguments = tool or ("tool", None)
                console.tool_failed(data.error, name, arguments)
        elif isinstance(data, SessionWorkspaceFileChangedData):
            console.file_changed(data.operation, data.path)
        elif isinstance(data, AssistantUsageData):
            for name in ("input_tokens", "cache_read_tokens", "output_tokens"):
                if getattr(data, name, None) is not None:
                    console.reported_usage.add(name)
            console.prompt_tokens += data.input_tokens or 0
            console.cache_read_tokens += data.cache_read_tokens or 0
            console.cache_write_tokens += data.cache_write_tokens or 0
            console.output_tokens += data.output_tokens or 0
            usage = getattr(data, "copilot_usage", None)
            if getattr(usage, "total_nano_aiu", None) is not None:
                console.reported_usage.add("aiu")
            console.nano_aiu += getattr(usage, "total_nano_aiu", 0) or 0
            # Priced by the runtime rather than by a rate table copied in here.
            for detail in getattr(usage, "_token_details", None) or []:
                batch = getattr(detail, "batch_size", 0) or 0
                if not batch:
                    continue
                nano = (detail.token_count or 0) * (detail.cost_per_batch or 0) / batch
                console.nano_aiu_by_type[detail.token_type] = (
                    console.nano_aiu_by_type.get(detail.token_type, 0.0) + nano
                )
        elif isinstance(data, SessionErrorData):
            console.error(data.message or "unknown session error")
        elif isinstance(data, SessionIdleData):
            # A turn the runtime never closed still reports what it contained.
            console.turn_end()
            finished.set()

    def on_permission_request(request, invocation):
        del invocation
        if isinstance(request, PermissionRequestRead):
            reason = file_read_denial(request.path, preliminary=preliminary)
            if reason:
                console.denied(reason, getattr(request, "tool_call_id", None))
                return PermissionDecisionReject(feedback=reason)
        elif isinstance(request, PermissionRequestWrite):
            reason = file_edit_denial(
                request.file_name,
                preliminary=preliminary,
            )
            if reason:
                console.denied(reason, getattr(request, "tool_call_id", None))
                return PermissionDecisionReject(feedback=reason)
        elif isinstance(request, PermissionRequestShell):
            reason = command_denial(
                shell_command_text(request), preliminary=preliminary
            )
            if reason:
                console.denied(reason, getattr(request, "tool_call_id", None))
                return PermissionDecisionReject(feedback=reason)
        return PermissionDecisionApproveOnce()

    return on_event, on_permission_request


def session_options(args, console: Console, finished: asyncio.Event) -> dict:
    from copilot import ToolSet, define_tool
    from runner.artifact_evidence_query import (
        ArtifactEvidenceQueryParams,
        query_artifact,
    )

    def artifact_evidence_query(params) -> str:
        return query_artifact(
            params.model_dump(exclude_none=True),
            campaign_id=str(args.campaign_id or ""),
        )

    artifact_evidence_tool = define_tool(
        "artifact_evidence_query",
        description=(
            "Read-only discovery and bounded querying of nested JSON evidence "
            "recorded by one completed measurement operation in this campaign. "
            "Provide the operation ID, never a filesystem path. For related "
            "fields, strongly prefer action=batch with up to 16 query "
            "specifications (each has path and optional where/select/aggregate/"
            "limit): the artifact is resolved and fingerprint-verified once, "
            "and provenance is returned once. Use action=query only for a "
            "single isolated query. Discovery is bounded and reports explicit "
            "truncation."
        ),
        handler=artifact_evidence_query,
        params_type=ArtifactEvidenceQueryParams,
        defer="auto",
    )

    on_event, on_permission_request = build_handlers(
        console, finished, preliminary=args.preliminary
    )
    return {
        "model": normalize_model(args.model),
        "reasoning_effort": args.reasoning,
        "on_event": on_event,
        "on_permission_request": on_permission_request,
        "tools": [artifact_evidence_tool],
        "available_tools": (
            ToolSet()
            .add_builtin(RESEARCH_TOOLS)
            .add_custom("artifact_evidence_query")
        ),
        "working_directory": str(ROOT),
        "streaming": True,
        "enable_file_change_tracking": True,
        "enable_skills": False,
        "enable_session_store": False,
        "skip_embedding_retrieval": True,
        "enable_mcp_apps": False,
        "large_output": {
            "enabled": True,
            "max_size_bytes": LARGE_OUTPUT_MAX_BYTES,
            "output_directory": str(LARGE_OUTPUT_DIR),
        },
    }


async def open_session(client, args, options: dict):
    if args.resume:
        try:
            return await client.resume_session(args.session_id, **options)
        except Exception as error:
            raise RuntimeError(
                "could not resume the persisted researcher session "
                f"{args.session_id!r}; refusing to create a replacement"
            ) from error
    if args.resume_or_create:
        metadata = await client.get_session_metadata(args.session_id)
        if metadata is not None:
            return await client.resume_session(args.session_id, **options)
        return await client.create_session(session_id=args.session_id, **options)
    return await client.create_session(session_id=args.session_id, **options)


async def shutdown_runtime(client, session, console: Console, *, abort: bool) -> None:
    interruption = None

    async def graceful_shutdown() -> None:
        if session is not None:
            if abort:
                await session.abort()
            await session.disconnect()
        await client.stop()

    try:
        await asyncio.wait_for(graceful_shutdown(), timeout=SHUTDOWN_TIMEOUT_SECONDS)
    except TimeoutError:
        console.line(
            f"  ! Copilot shutdown timed out after {SHUTDOWN_TIMEOUT_SECONDS:g}s; "
            "forcing the adapter-owned runtime to stop"
        )
    except asyncio.CancelledError as error:
        interruption = error
        console.line(
            "  ! Copilot shutdown interrupted; "
            "forcing the adapter-owned runtime to stop"
        )
    except Exception as error:  # noqa: BLE001 - SDK cleanup needs owned-runtime recovery
        console.line(
            f"  ! Copilot shutdown failed: {error}; "
            "forcing the adapter-owned runtime to stop"
        )
    else:
        return

    try:
        await asyncio.wait_for(client.force_stop(), timeout=FORCE_STOP_TIMEOUT_SECONDS)
    except TimeoutError as error:
        raise RuntimeError(
            f"Copilot forced shutdown timed out after {FORCE_STOP_TIMEOUT_SECONDS:g}s"
        ) from error
    console.line("  ! Copilot owned runtime force-stopped; session data preserved")
    if interruption is not None:
        raise interruption


async def run(args) -> int:
    from copilot import CopilotClient

    console = getattr(args, "usage_console", None) or Console()
    finished = asyncio.Event()
    model = normalize_model(args.model)

    if stop_requested():
        return EXIT_INTERRUPTED

    client = CopilotClient(working_directory=str(ROOT))
    session = None
    abort_session = False
    try:
        await client.start()
        status = await client.get_auth_status()
        if not getattr(status, "isAuthenticated", False):
            print(
                "Copilot is not authenticated. Run `copilot` once and sign in.",
                file=sys.stderr,
            )
            return EXIT_NOT_AUTHENTICATED

        available = [entry.id for entry in await client.list_models()]
        if model not in available:
            print(
                f"Model '{model}' is not available to this Copilot account. "
                f"Available: {', '.join(available)}",
                file=sys.stderr,
            )
            return EXIT_MODEL_UNAVAILABLE

        session = await open_session(
            client, args, session_options(args, console, finished)
        )
        before = worktree_status()
        before_offload = offload_snapshot()
        started = time.monotonic()
        finished_task = asyncio.create_task(finished.wait())
        stop_task = asyncio.create_task(wait_for_stop_request())
        try:
            await session.send(args.prompt)
            done, _ = await asyncio.wait(
                (finished_task, stop_task),
                timeout=args.timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if stop_task in done:
                abort_session = True
                console.line("  ! session interrupted")
                return EXIT_INTERRUPTED
            if finished_task not in done:
                abort_session = True
                console.line(f"  ! session timed out after {args.timeout}s")
                console.summary(
                    session.session_id,
                    changed_since(before),
                    offloaded_since(before_offload),
                    elapsed_seconds=time.monotonic() - started,
                )
                return EXIT_TIMEOUT
        except TimeoutError:
            abort_session = True
            console.line(f"  ! session timed out after {args.timeout}s")
            console.summary(
                session.session_id,
                changed_since(before),
                offloaded_since(before_offload),
                elapsed_seconds=time.monotonic() - started,
            )
            return EXIT_TIMEOUT
        except KeyboardInterrupt:
            abort_session = True
            console.line("  ! session interrupted")
            return EXIT_INTERRUPTED
        except asyncio.CancelledError:
            abort_session = True
            raise
        finally:
            finished_task.cancel()
            stop_task.cancel()
            await asyncio.gather(finished_task, stop_task, return_exceptions=True)

        console.summary(
            session.session_id,
            changed_since(before),
            offloaded_since(before_offload),
            elapsed_seconds=time.monotonic() - started,
        )
        return EXIT_SESSION_ERROR if console.session_error else EXIT_OK
    finally:
        await shutdown_runtime(client, session, console, abort=abort_session)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument(
        "--reasoning", default="high", choices=["low", "medium", "high", "xhigh", "max"]
    )
    # Continuation is explicit: a retry resumes this phase's own session and can
    # never inherit whatever session happened to run last on this machine.
    continuation = parser.add_mutually_exclusive_group()
    continuation.add_argument("--resume", action="store_true")
    continuation.add_argument("--resume-or-create", action="store_true")
    parser.add_argument("--timeout", type=float, default=1800.0)
    # Accounting metadata only; these values never enter the model prompt.
    parser.add_argument("--campaign-id")
    parser.add_argument("--phase")
    parser.add_argument("--preliminary", action="store_true")
    parser.add_argument("--attempt", type=int, default=1)
    return parser.parse_args(argv)


def console_label(args) -> str:
    """The bounded phase a session belongs to, for the console only."""
    return str(args.phase or "")


def record_usage(args, console: Console, elapsed: float, exit_code: int) -> None:
    """Append aggregate usage, never conversation content or tool arguments."""
    if not args.campaign_id:
        return  # Standalone invocations are not attributed to an arbitrary campaign.
    # Campaign IDs are path components, not filenames supplied by the model.
    import uuid

    campaign_id = str(uuid.UUID(args.campaign_id))
    directory = ROOT / "reports" / "session_usage"
    directory.mkdir(parents=True, exist_ok=True)
    row = {
        "campaign_id": campaign_id,
        "phase": args.phase,
        "attempt": args.attempt,
        "session_id": args.session_id,
        "recorded_at": datetime.now(UTC).isoformat(),
        "model": normalize_model(args.model),
        "reasoning": args.reasoning,
        "duration_seconds": round(elapsed, 3),
        "exit_code": exit_code,
        "input_tokens": console.prompt_tokens
        if "input_tokens" in console.reported_usage
        else None,
        "cache_read_tokens": console.cache_read_tokens
        if "cache_read_tokens" in console.reported_usage
        else None,
        "output_tokens": console.output_tokens
        if "output_tokens" in console.reported_usage
        else None,
        "aiu": console.nano_aiu / 1e9 if "aiu" in console.reported_usage else None,
        "tool_calls": console.tool_calls,
        "tools_by_name": console.tool_counts,
    }
    with (directory / f"{campaign_id}.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.usage_console = Console(console_label(args))
    started = time.monotonic()
    exit_code = EXIT_RUNTIME_FAILURE
    try:
        exit_code = asyncio.run(run(args))
    except KeyboardInterrupt:
        exit_code = EXIT_INTERRUPTED
    except Exception as error:  # noqa: BLE001 - the launcher needs a code, not a traceback
        print(f"Copilot runtime failure: {error}", file=sys.stderr)
    finally:
        try:
            record_usage(
                args, args.usage_console, time.monotonic() - started, exit_code
            )
        except (OSError, ValueError) as error:
            # Accounting failure must not invalidate a scientific deliverable.
            print(f"Session usage could not be recorded: {error}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
