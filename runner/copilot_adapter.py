"""Bounded PI contexts on a launcher-owned persistent GitHub Copilot SDK runtime.

The launcher owns the research protocol and decides whether a phase is complete;
this adapter owns only the Copilot runtime: session identity, the tool profile,
the command policy, and what reaches the console. Nothing printed here is read
back as a scientific fact.
"""

from __future__ import annotations

import argparse
import asyncio
import difflib
import fnmatch
import json
import ntpath
import re
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from runner import protocol
from runner.stop_control import stop_request_path, stop_requested, wait_for_stop_request

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
MODEL_CALL_RETRY_LIMIT = 5
MODEL_CALL_RETRY_DELAY_SECONDS = 5.0

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


# The preliminary analyst retains its existing publication/tool contract.
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
MAIN_PI_TOOLS = ["view", "rg", "glob"]
CODING_TOOLS = ["view", "apply_patch", "scientific_api_reference"]
MAIN_WRITE_DENIAL = (
    "Ordinary PI sessions have no file-write tools. Use submit_operation for actions. "
    "Use scientific_coding for bounded scientific source changes."
)
CODING_SCOPE_DENIAL = "This action is outside this coding session's exact file scope."
CODING_PERMISSION_DENIAL = (
    "Harness authorization failure: the permission request has no matching active "
    "native-child or main-PI identity. No file access was authorized."
)
SHELL_DENIAL = "Shell tools are unavailable in this session; Runner executes checks."

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


def compact_artifact_query_spec(query: object) -> str:
    if not isinstance(query, dict):
        return "invalid query"
    path = query.get("path")
    rendered_path = (
        compact_json_pointer(str(path))
        if isinstance(path, str) and path.startswith("/")
        else "missing path"
    )
    modifiers: list[str] = []
    where = query.get("where")
    if isinstance(where, dict):
        where_path = where.get("path")
        if isinstance(where_path, str) and where_path.startswith("/"):
            equals = json.dumps(
                where.get("equals"),
                ensure_ascii=True,
                separators=(",", ":"),
            )
            modifiers.append(
                "where "
                + compact_json_pointer(where_path)
                + "="
                + compact_console_text(equals)
            )
        else:
            modifiers.append("where")
    select = query.get("select")
    if isinstance(select, str) and select:
        modifiers.append("select " + compact_json_pointer(select))
    aggregate = query.get("aggregate")
    if isinstance(aggregate, str) and aggregate:
        modifiers.append("aggregate " + aggregate)
    limit = query.get("limit")
    if isinstance(limit, int):
        modifiers.append(f"limit {limit}")
    if modifiers:
        return f"{rendered_path} [{'; '.join(modifiers)}]"
    return rendered_path


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
    from runner.copilot_scoped_search import linked_path

    if not isinstance(target, str):
        return FILE_EDIT_DENIAL
    path = Path(target)
    if not path.is_absolute():
        path = ROOT / path
    if linked_path(ROOT, path) or ":" in str(path)[len(path.anchor):]:
        return FILE_EDIT_DENIAL
    if is_pi_writable_path(target, preliminary=preliminary):
        return None
    return FILE_EDIT_DENIAL


def scoped_edit_denial(
    target: str,
    *,
    preliminary: bool = False,
    coding_paths: frozenset[str] | None = None,
) -> str | None:
    relative = _repository_relative_target(target)
    if coding_paths is not None:
        if relative not in coding_paths or file_edit_denial(target):
            return CODING_SCOPE_DENIAL
        return None
    if preliminary:
        return file_edit_denial(target, preliminary=True)
    return MAIN_WRITE_DENIAL


def scoped_tool_hook(
    *,
    coding_paths: frozenset[str] | None = None,
    read_paths: frozenset[str] = frozenset(),
    operations=None,
    coding=None,
    preliminary: bool = False,
):
    """Check every patch target, including moves, before a built-in runs."""

    def on_pre_tool_use(request, invocation):
        if coding is not None:
            return coding.pre_tool_use(request, invocation)
        name = request.get("toolName")
        arguments = request.get("toolArgs")
        allowed = (
            CODING_TOOLS
            if coding_paths is not None
            else [*(RESEARCH_TOOLS if preliminary else MAIN_PI_TOOLS),
                  "artifact_evidence_query", "training_log_query", "scientific_coding",
                  "scientific_api_reference", "submit_operation"]
        )
        reason = None
        if operations is not None and (operations.busy or operations.closed):
            reason = "Runner is executing or this bounded session has ended."
        elif name not in allowed:
            reason = CODING_SCOPE_DENIAL if coding_paths is not None else SHELL_DENIAL
        elif name == "apply_patch":
            patch = (
                arguments.get("input") or arguments.get("patch")
                if isinstance(arguments, dict)
                else arguments
            )
            prefixes = (
                "*** Add File: ",
                "*** Update File: ",
                "*** Delete File: ",
                "*** Move to: ",
            )
            targets = (
                [
                    line.split(": ", 1)[1]
                    for line in patch.splitlines()
                    if line.startswith(prefixes)
                ]
                if isinstance(patch, str)
                else []
            )
            if not targets:
                reason = (
                    CODING_SCOPE_DENIAL
                    if coding_paths is not None
                    else MAIN_WRITE_DENIAL
                )
            for target in targets:
                reason = scoped_edit_denial(
                    target, coding_paths=coding_paths, preliminary=preliminary
                )
                if reason:
                    break
        elif coding_paths is not None and name == "view":
            target = arguments.get("path") if isinstance(arguments, dict) else None
            if (
                not isinstance(target, str)
                or _repository_relative_target(target) not in read_paths
                or file_read_denial(target)
                or (ROOT / _repository_relative_target(target)).is_dir()
            ):
                reason = CODING_SCOPE_DENIAL
        elif name == "view":
            target = arguments.get("path") if isinstance(arguments, dict) else None
            if not isinstance(target, str):
                reason = FILE_READ_DENIAL
            else:
                reason = file_read_denial(target, preliminary=preliminary)
                if not reason and (ROOT / _repository_relative_target(target)).is_dir():
                    reason = "Use scoped glob for directory enumeration, not view."
        elif preliminary and name == "powershell":
            reason = command_denial(
                arguments.get("command", "") if isinstance(arguments, dict) else "",
                preliminary=True,
            )
        if reason:
            return {"permissionDecision": "deny", "permissionDecisionReason": reason}
        return None

    return on_pre_tool_use


def file_read_denial(target: str, *, preliminary: bool = False) -> str | None:
    from runner.copilot_scoped_search import linked_path

    relative = _repository_relative_target(target)
    path = Path(target) if isinstance(target, str) else ROOT.parent
    if not path.is_absolute():
        path = ROOT / path
    if (
        relative is None or linked_path(ROOT, path)
        or ":" in str(path)[len(path.anchor):]
        or relative.split("/", 1)[0] in {".git", ".venv", ".github"}
        or relative == ".copilot"
        or (relative.startswith(".copilot/") and not relative.startswith(".copilot/large-output/"))
    ):
        return FILE_READ_DENIAL
    if preliminary:
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
            if reader_name in {"rg", "get-childitem", "ls", "dir"}:
                return "Use scoped rg/glob tools for traversal, not shell readers."
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
                if any(character in path for character in "*?[]"):
                    return "Shell readers require exact files; use scoped rg/glob for traversal."
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
        self.coding_duration_seconds = 0.0
        self.runner_wait_seconds = 0.0

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
                        rendered_queries = [
                            compact_artifact_query_spec(query)
                            for query in queries
                            if isinstance(query, dict)
                            and isinstance(query.get("path"), str)
                            and query["path"].startswith("/")
                        ]
                        pointers.extend(rendered_queries[:3])
                        if len(rendered_queries) > 3:
                            pointers.append(f"+{len(rendered_queries) - 3} more")
                elif isinstance(arguments.get("path"), str):
                    pointers.append(compact_artifact_query_spec(arguments))
                parts = [
                    str(value)
                    for value in (
                        operation_id,
                        (
                            f"artifact {arguments.get('artifact_index', 0)}"
                            if action not in {"operations", "metadata"} else None
                        ),
                        action,
                    )
                    if isinstance(value, (str, int)) and str(value)
                ]
                if pointers:
                    parts.append(", ".join(pointers))
                detail = " | ".join(parts)
            elif name == "training_log_query":
                parts = [
                    str(arguments.get("operation_id") or ""),
                    str(arguments.get("action") or "discover"),
                ]
                for key in (
                    "attempts",
                    "from_step",
                    "to_step",
                    "metrics",
                    "all_metrics",
                    "offset",
                    "limit",
                    "max_bytes",
                ):
                    if key in arguments:
                        parts.append(f"{key}={arguments[key]}")
                detail = " | ".join(part for part in parts if part)
            elif name == "scientific_coding":
                detail = "bounded coding / PI source review required"
            elif name == "scientific_api_reference":
                detail = " | ".join(str(value) for value in (
                    arguments.get("library", "-"), arguments.get("symbol") or "library root",
                    arguments.get("action", "definition"), arguments.get("contains"),
                ) if value)
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
            if name == "artifact_evidence_query":
                target = (
                    f"{arguments.get('operation_id') or '-'} | "
                    f"artifact {arguments.get('artifact_index', 0)}"
                )
            elif name == "scientific_api_reference":
                target = (
                    f"{arguments.get('library') or '-'} | "
                    f"{arguments.get('symbol') or 'library root'}"
                )
            else:
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
    console: Console,
    finished: asyncio.Event,
    *,
    preliminary: bool = False,
    coding_paths: frozenset[str] | None = None,
    read_paths: frozenset[str] = frozenset(),
    operations=None,
    coding=None,
    child_accounting: bool = False,
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
        if coding is not None:
            coding.on_event(event)
        if getattr(event, "agent_id", None) is not None and not child_accounting:
            return
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
            for name in (
                "input_tokens", "cache_read_tokens", "cache_write_tokens", "output_tokens"
            ):
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
            if coding is None or not coding.busy:
                finished.set()

    def on_permission_request(request, invocation):
        if operations is not None and (operations.busy or operations.closed):
            return PermissionDecisionReject(
                feedback="Runner is executing or this bounded session has ended."
            )
        scope = None
        if coding is not None:
            try:
                scope = coding.permission_scope(request, invocation)
            except ValueError:
                console.denied(CODING_PERMISSION_DENIAL, getattr(request, "tool_call_id", None))
                return PermissionDecisionReject(feedback=CODING_PERMISSION_DENIAL)
        if isinstance(request, PermissionRequestRead):
            native_paths = frozenset(scope["read_paths"]) if scope is not None else read_paths
            reason = (
                CODING_SCOPE_DENIAL
                if (coding_paths is not None or scope is not None)
                and _repository_relative_target(request.path) not in native_paths
                else file_read_denial(request.path, preliminary=preliminary)
            )
            if coding is not None and coding.busy and scope is None:
                reason = CODING_SCOPE_DENIAL
            if getattr(request, "resolved_path", None):
                reason = reason or file_read_denial(request.resolved_path, preliminary=preliminary)
                if scope is not None and _repository_relative_target(request.resolved_path) not in native_paths:
                    reason = CODING_SCOPE_DENIAL
            if reason:
                console.denied(reason, getattr(request, "tool_call_id", None))
                return PermissionDecisionReject(feedback=reason)
        elif isinstance(request, PermissionRequestWrite):
            reason = scoped_edit_denial(
                request.file_name,
                preliminary=preliminary,
                coding_paths=frozenset(scope["allowed_paths"]) if scope is not None else coding_paths,
            )
            if getattr(request, "resolved_path", None):
                reason = reason or scoped_edit_denial(
                    request.resolved_path, preliminary=preliminary,
                    coding_paths=frozenset(scope["allowed_paths"]) if scope else coding_paths,
                )
            for edit in getattr(request, "file_edits", None) or []:
                for content in (edit.before, edit.after):
                    if content is not None:
                        reason = reason or scoped_edit_denial(
                            content.path, preliminary=preliminary,
                            coding_paths=frozenset(scope["allowed_paths"]) if scope else coding_paths,
                        )
            if reason:
                console.denied(reason, getattr(request, "tool_call_id", None))
                return PermissionDecisionReject(feedback=reason)
        elif isinstance(request, PermissionRequestShell):
            reason = (
                command_denial(shell_command_text(request), preliminary=True)
                if preliminary
                else SHELL_DENIAL
            )
            if reason:
                console.denied(reason, getattr(request, "tool_call_id", None))
                return PermissionDecisionReject(feedback=reason)
        return PermissionDecisionApproveOnce()

    return on_event, on_permission_request


class ScientificCodingParams(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "anyOf": [
                {
                    "required": ["allowed_paths", "verification_path"],
                    "properties": {
                        "allowed_paths": {"type": "array"},
                        "verification_path": {"type": "string"},
                        "session_handle": {"type": "null"},
                    },
                },
                {
                    "required": ["session_handle"],
                    "properties": {"session_handle": {"type": "string"}},
                },
            ]
        },
    )

    intent: str = Field(min_length=1, max_length=16_000)
    allowed_paths: list[str] | None = Field(
        default=None, min_length=1, max_length=64,
        description="Exact writable files for a new child; omit for a correction.",
    )
    read_paths: list[str] | None = Field(
        default=None, max_length=64,
        description="Additional readable files; omit to reuse correction scope.",
    )
    source_context: str = Field(default="", max_length=32_000)
    verification_path: str | None = Field(
        default=None, min_length=1,
        description="Scoped lab verification module; omit for a correction.",
    )
    session_handle: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_initial_scope(self) -> ScientificCodingParams:
        if not self.session_handle and (
            self.allowed_paths is None or self.verification_path is None
        ):
            raise ValueError(
                "A new coding call requires allowed_paths and verification_path. "
                "A correction requires the returned session_handle and intent."
            )
        return self


class CodingCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_args: list[str]
    artifact_filename: str
    check_description: str = Field(min_length=1)


class CodingReport(CodingCheck):
    summary: str
    unchecked_scope: list[str] = Field(min_length=1)
    compatibility_check: CodingCheck | None = None


class CodingConsole(Console):
    """Collect child accounting without printing its conversation or diffs."""

    def line(self, text: str) -> None:
        pass

    def delta(self, text: str) -> None:
        pass

    def message(self, text: str) -> None:
        pass


def coding_file_scope(paths: list[str], *, writable: bool) -> frozenset[str]:
    result = set()
    for target in paths:
        path = PureWindowsPath(target)
        rejection = f"Coding {'write' if writable else 'read'} scope rejected {target!r}: "
        if (
            not target.strip()
            or path.drive
            or path.root
            or ".." in path.parts
            or any(character in target for character in "*?[]:")
        ):
            raise ValueError(
                rejection + "use an exact repository-relative file path, "
                "without absolute paths, parent traversal, wildcards or streams."
            )
        relative = _repository_relative_target(target)
        if relative is None:
            raise ValueError(rejection + "the path is outside the repository.")
        if (ROOT / relative).is_dir():
            raise ValueError(
                rejection + "directories are not file scopes; select exact files. "
                "New writable files do not require an existing parent directory."
            )
        if writable:
            if relative == "pi_workspace/operation_request.json":
                raise ValueError(rejection + "operation requests are Runner exchange, not coding output.")
            reason = file_edit_denial(target)
            if reason:
                raise ValueError(rejection + reason)
        else:
            reason = file_read_denial(target)
            if reason:
                raise ValueError(rejection + reason)
            if not (
                relative.startswith(("robot_learning/", "contracts/"))
                or relative in {"agents.md", "pi_workspace/scientific_model.md"}
            ):
                raise ValueError(
                    rejection + "read_paths permits scientific sources, contracts, "
                    "AGENTS.md and the frozen scientific model only; select other "
                    "relevant context through source_context."
                )
        result.add(relative)
    return frozenset(result)


def coding_snapshot(paths: frozenset[str]) -> dict[str, bytes | None]:
    return {
        path: (ROOT / path).read_bytes() if (ROOT / path).is_file() else None
        for path in paths
    }


def coding_changes(before: dict[str, bytes | None]) -> tuple[list[dict], str]:
    """Compare the invocation's actual bytes, including already-dirty files."""
    manifest = []
    diffs = []
    for path, previous in sorted(before.items()):
        current = (ROOT / path).read_bytes() if (ROOT / path).is_file() else None
        if previous == current:
            continue
        change = {
            "path": path,
            "change": (
                "created" if previous is None
                else "deleted" if current is None
                else "modified"
            ),
            "before_bytes": len(previous) if previous is not None else None,
            "after_bytes": len(current) if current is not None else None,
        }
        manifest.append(change)
        try:
            old_lines = (previous or b"").decode("utf-8").splitlines(keepends=True)
            new_lines = (current or b"").decode("utf-8").splitlines(keepends=True)
        except UnicodeDecodeError:
            change["text_diff_available"] = False
            diffs.append(f"Binary/non-UTF-8 file differs: {path}\n")
            continue
        change["text_diff_available"] = True
        for line in difflib.unified_diff(
            old_lines, new_lines, fromfile=f"before/{path}", tofile=f"after/{path}",
        ):
            diffs.append(
                line if line.endswith("\n")
                else line + "\n\\ No newline at end of file\n"
            )
    return manifest, "".join(diffs)


CODING_INSTRUCTIONS = """
You are a Python scientific-software engineer supporting the PI.

Implement the requested change within the authorized files. Read the relevant
sources first. Understand the supplied inputs, expected outputs and constraints.
Reuse existing code and preserve behavior the PI did not ask to change.

Use scientific_api_reference for unfamiliar library APIs.

Write a small verification module covering the changed behavior. For API or
runtime changes, include a small artifact-independent compatibility mode.
Do not claim that a mocked component has been checked against its real
implementation.

Do not execute code, install dependencies or submit operations. Runner handles
execution.

Report what changed, what the checks cover and what remains unchecked.
State that the checks have not been executed.

Return only a JSON object containing:
- summary: string
- check_args: list of module-argument strings
- artifact_filename: simple .json basename
- check_description: nonempty string
- unchecked_scope: nonempty list of strings
- compatibility_check: null, or an object containing check_args,
  artifact_filename and check_description with the same types

Use {artifact} for the output-path argument.
Use different artifact filenames for the two checks.
"""


class ScientificCoding:
    def __init__(self, client, args, console: Console) -> None:
        self.args = args
        self.console = console
        self.active_tasks: set[asyncio.Task] = set()
        self.busy = False
        self.closed = False
        self.operations = None
        self.session = None
        self.bindings: dict[str, dict] = {}
        self.active_handle: str | None = None
        self.binding: dict | None = None
        self.child_console = None
        self.child_events = None
        self.completed = asyncio.Event()
        self.stop_response = ""
        self.stop_challenges = 0
        self.child_error = None
        self.permission_requests: dict[int, tuple[object, str | None, dict | None]] = {}
        self.native_accounting: dict = {}
        self.cancellation_unconfirmed = False
        self.quiescent = False

    def agent(self) -> dict:
        return {
            "name": "scientific-coder",
            "description": "Bounded scientific source and verification author.",
            "prompt": CODING_INSTRUCTIONS,
            "tools": CODING_TOOLS,
            "infer": False,
            "mcp_servers": {},
        }

    def tool(self):
        from copilot import define_tool

        return define_tool(
            "scientific_coding",
            description=(
                "Use scientific_coding for scientific source changes.\n\n"
                "In intent, state what to build, its actual inputs and expected "
                "outputs, and what must stay unchanged.\n\n"
                "Select writable files in allowed_paths, additional readable files "
                "in read_paths, and the check module in verification_path.\n\n"
                "Put necessary background in source_context. The child does not "
                "receive your conversation.\n\n"
                "Inspect the returned code and proposed check. Only Runner "
                "executes checks.\n\n"
                "Continue the same change using session_handle; its file "
                "permissions remain unchanged."
            ),
            handler=self.invoke,
            params_type=ScientificCodingParams,
            defer="auto",
            skip_permission=True,
        )

    def authorize_parent(self, invocation) -> None:
        if (
            invocation.session_id != self.args.session_id
            or getattr(invocation, "agent_id", None) is not None
            or self.closed or self.busy
            or (self.operations is not None and (self.operations.busy or self.operations.closed))
        ):
            raise ValueError("Only the active, unlocked main PI may use this tool.")

    def on_event(self, event) -> None:
        from copilot.session_events import (
            PermissionRequestedData,
            SubagentCompletedData, SubagentFailedData, SubagentStartedData,
        )

        data = event.data
        handle = getattr(event, "agent_id", None)
        if isinstance(data, SubagentStartedData) and self.busy:
            if data.agent_name == "scientific-coder" and self.active_handle is None:
                self.active_handle = handle or data.tool_call_id
        if isinstance(data, PermissionRequestedData) and not data.resolved_by_hook:
            # SDK dispatches this event before its callback, using the same request object.
            self.permission_requests[id(data.permission_request)] = (
                data.permission_request, handle,
                self.binding if self.busy and handle == self.active_handle else None,
            )
        if handle != self.active_handle or not self.busy:
            return
        if self.child_events is not None:
            self.child_events(event)
        if isinstance(data, (SubagentCompletedData, SubagentFailedData)):
            self.native_accounting = {
                "agent_id": handle,
                "scope": "native_task_lifetime",
                "model": getattr(data, "model", None),
                "duration_seconds": data.duration.total_seconds() if data.duration else None,
                "total_tokens": data.total_tokens,
                "total_tool_calls": data.total_tool_calls,
            }
            self.child_error = getattr(data, "error", None)
            if getattr(data, "cancelled", False):
                self.child_error = "Native coding task was cancelled."
            self.completed.set()

    def pre_tool_use(self, request, invocation):
        """Native hooks identify the child in request.sessionId, not invocation."""
        try:
            if self.closed:
                return {
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "This coding/PI context has ended.",
                }
            handle = request.get("sessionId")
            if handle == self.active_handle and self.busy and self.binding is not None:
                return scoped_tool_hook(
                    coding_paths=frozenset(self.binding["allowed_paths"]),
                    read_paths=frozenset(self.binding["read_paths"]),
                    operations=self.operations,
                )(request, invocation)
            if handle != self.args.session_id or self.busy or self.closed:
                return {
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "Unknown child or coding/Runner context is locked.",
                }
            return scoped_tool_hook(operations=self.operations)(request, invocation)
        except Exception:
            # SDK hook exceptions otherwise fail open. Malformed calls must not.
            return {"permissionDecision": "deny", "permissionDecisionReason": CODING_SCOPE_DENIAL}

    def permission_scope(self, request, invocation) -> dict | None:
        record = self.permission_requests.pop(id(request), None)
        if (
            record is None or record[0] is not request or self.closed
            or not isinstance(invocation, dict)
            or invocation.get("session_id") != self.args.session_id
        ):
            raise ValueError(CODING_PERMISSION_DENIAL)
        _, handle, binding = record
        if handle is None and not self.busy:
            return None
        if (
            self.busy and self.binding is not None
            and handle is not None and handle == self.active_handle
            and binding is self.binding
        ):
            return self.binding
        raise ValueError(CODING_PERMISSION_DENIAL)

    def start_hook(self, request, invocation):
        if (
            invocation.get("session_id") != self.args.session_id
            or request.get("agentName") != "scientific-coder"
            or not self.busy or self.binding is None
        ):
            return {"additionalContext": "Unauthorized child: all tools are denied. Stop."}
        return {
            "additionalContext": (
                "Installed scientific APIs: native MuJoCo 3.12.0, NOT mujoco-py; "
                "Gymnasium 1.3.0; Stable-Baselines3 2.9.0. Dependencies and manifests "
                "are fixed and human-owned. SDK 1.0.19 is a harness runtime detail, "
                "not permission to edit the harness. Author scoped source and a "
                "defect-sensitive laboratory verification proposal only; execute nothing. "
                "Use scientific_api_reference for unfamiliar installed APIs. "
                "Changed integration needs a small artifact-independent production-path "
                "compatibility proposal, not just an import or saved-JSON check. "
                "The parent PI must review actual diffs and executable checks. "
                "No engineering handoff certifies science or Runner acceptance.\n"
                + json.dumps(self.binding, ensure_ascii=False)
            )
        }

    def report(self, response: str) -> CodingReport:
        report = CodingReport.model_validate_json(response)
        if (
            self.binding is None
            or not (ROOT / self.binding["verification_path"]).is_file()
        ):
            raise ValueError("Missing scoped verification module.")
        checks: list[CodingCheck] = [report]
        if report.compatibility_check is not None:
            checks.append(report.compatibility_check)
        for check in checks:
            if (
                not re.fullmatch(r"[A-Za-z0-9_-]+\.json", check.artifact_filename)
                or not any("{artifact}" in argument for argument in check.check_args)
            ):
                raise ValueError("Invalid executable check proposal or artifact basename.")
        if len({check.artifact_filename for check in checks}) != len(checks):
            raise ValueError("Compatibility and behavioral checks need distinct artifact basenames.")
        return report

    def check_proposal(self, check: CodingCheck, module: str) -> dict:
        artifact = f"campaigns/evaluations/{self.args.campaign_id}/{check.artifact_filename}"
        return {
            "instrument": "python_module", "module": module,
            "args": [argument.replace("{artifact}", artifact) for argument in check.check_args],
            "artifact": artifact,
        }

    def stop_hook(self, request, invocation):
        if (
            invocation.get("session_id") != self.args.session_id
            or request.get("agentId") != self.active_handle or not self.busy or self.closed
        ):
            return None
        self.stop_response = request.get("response", "")
        try:
            self.report(self.stop_response)
        except (ValueError, OSError) as error:
            if self.stop_challenges < 2:
                self.stop_challenges += 1
                return {
                    "decision": "block",
                    "reason": (
                        "Engineering handoff is incomplete: " + str(error)
                        + ". Finish the scoped laboratory check and return the exact "
                        "JSON handoff contract. Do not execute checks, broaden scope, "
                        "make a scientific judgment, or select a research direction."
                    ),
                }
        self.completed.set()
        return None

    async def wait_child_idle(self) -> None:
        # Native stop hooks run on every correction; subagent.completed is not
        # repeated on every idle transition. Do not unlock operations at the
        # hook itself: the native task must have actually settled first.
        await self.completed.wait()
        while True:
            tasks = await self.session.rpc.tasks.list()
            child = next((item for item in tasks.tasks if item.id == self.active_handle), None)
            if child is None:
                raise ValueError("Native coding child disappeared before its handoff.")
            if child.status.value in {"idle", "completed", "failed", "cancelled"}:
                self.quiescent = True
                if child.status.value in {"failed", "cancelled"}:
                    raise ValueError(child.error or f"Native child is {child.status.value}.")
                self.native_accounting["active_time_ms"] = child.active_time_ms
                self.native_accounting["scope"] = "native_task_lifetime"
                if not self.stop_response:
                    self.stop_response = child.latest_response or child.result or ""
                return
            await asyncio.sleep(0.05)

    def resolve_binding(self, params: ScientificCodingParams) -> dict:
        previous = None
        if params.session_handle:
            previous = self.bindings.get(params.session_handle)
            if previous is None:
                raise ValueError(
                    "Unknown native coding handle in this bounded context; "
                    "a handle from another context cannot authorize a correction."
                )
        supplied = params.model_dump(
            include={"allowed_paths", "read_paths", "verification_path"},
            exclude_none=True,
        )
        scope = {**(previous or {}), **supplied}
        if "allowed_paths" not in scope or "verification_path" not in scope:
            raise ValueError("A new coding call requires allowed_paths and verification_path.")
        paths = coding_file_scope(scope["allowed_paths"], writable=True)
        reads = paths | coding_file_scope(scope.get("read_paths", []), writable=False)
        verification = next(iter(
            coding_file_scope([scope["verification_path"]], writable=True)
        ))
        if (
            verification not in paths
            or not verification.startswith("robot_learning/lab/")
            or not verification.endswith(".py")
            or any(not part.isidentifier() for part in verification[:-3].split("/"))
        ):
            raise ValueError(
                "verification_path must be a scoped robot_learning/lab Python module."
            )
        binding = {
            "allowed_paths": sorted(paths),
            "read_paths": sorted(reads),
            "verification_path": verification,
        }
        if previous is not None:
            changed = [field for field in binding if binding[field] != previous[field]]
            if changed:
                raise ValueError(
                    f"Coding correction changes immutable scope fields: {changed}. "
                    "Omit scope fields to reuse the stored binding. "
                    "A new scope requires a new PI-directed call without session_handle."
                )
        return binding

    async def invoke(self, params: ScientificCodingParams, invocation) -> str:
        from copilot.generated.rpc import TasksSendMessageRequest, TasksStartAgentRequest

        if self.closed or self.busy or (
            self.operations is not None
            and (self.operations.busy or self.operations.closed)
        ):
            return json.dumps({
                "status": "error", "error": "Coding is closed or already active."
            })
        try:
            self.authorize_parent(invocation)
            if self.session is None or not invocation.tool_call_id:
                raise ValueError("Native coding requires the bound parent SDK session.")
            await self.session.rpc.tools.initialize_and_validate()
            if self.args.preliminary:
                raise ValueError("Coding is unavailable during preliminary publication.")
            if not self.args.campaign_id:
                raise ValueError("Coding requires an explicit campaign identity.")
            uuid.UUID(self.args.campaign_id)
            binding = self.resolve_binding(params)
            paths = frozenset(binding["allowed_paths"])
            verification = binding["verification_path"]
            if params.session_handle:
                tasks = await self.session.rpc.tasks.list()
                child = next((item for item in tasks.tasks if item.id == params.session_handle), None)
                if child is None or child.status.value != "idle":
                    raise ValueError("Only this context's idle native child accepts corrections.")
            before = coding_snapshot(paths)
        except (OSError, ValueError) as error:
            self.console.line(f"  > scientific_coding: rejected; {error}")
            return json.dumps({"status": "error", "error": str(error)})

        if self.closed or self.busy or (
            self.operations is not None and (self.operations.busy or self.operations.closed)
        ):
            return json.dumps({"status": "error", "error": "Coding/Runner lock changed during validation."})
        self.busy = True
        task = asyncio.current_task()
        self.active_tasks.add(task)
        started = time.monotonic()
        child_console = CodingConsole()
        self.child_console = child_console
        self.child_events, _ = build_handlers(
            child_console, asyncio.Event(), child_accounting=True
        )
        self.active_handle = params.session_handle
        self.binding = binding
        self.permission_requests.clear()
        self.completed.clear()
        self.stop_response = ""
        self.stop_challenges = 0
        self.child_error = None
        self.native_accounting = {}
        self.quiescent = False
        result = {
            "status": "error",
            "verification_module": verification[:-3].replace("/", "."),
            "check_executed": False,
            "review_required": True,
            "unchecked_scope": ["No scientific check has been executed by this tool."],
        }
        exit_code = EXIT_RUNTIME_FAILURE
        cancelled = False
        try:
            prompt = json.dumps({
                "intent": params.intent,
                **binding,
                "source_context": params.source_context,
            }, ensure_ascii=False)
            if params.session_handle:
                sent = await self.session.rpc.tasks.send_message(
                    TasksSendMessageRequest(id=params.session_handle, message=prompt)
                )
                if not sent.sent:
                    raise ValueError(sent.error or "Native same-child correction was not delivered.")
            else:
                child = await self.session.rpc.tasks.start_agent(TasksStartAgentRequest(
                    agent_type="scientific-coder", name="scientific-coder",
                    description="Scoped source and verification authoring", prompt=prompt,
                ))
                if self.active_handle not in (None, child.agent_id):
                    raise ValueError("Native child identity changed during dispatch.")
                self.active_handle = child.agent_id
            self.bindings[self.active_handle] = binding
            await asyncio.wait_for(self.wait_child_idle(), self.args.timeout)
            if self.child_error or child_console.session_error:
                raise RuntimeError(self.child_error or child_console.session_error)
            report = self.report(self.stop_response)
            result.update({
                "status": "completed", "summary": report.summary,
                "proposed_check": self.check_proposal(report, result["verification_module"]),
                "proposed_compatibility_check": (
                    self.check_proposal(report.compatibility_check, result["verification_module"])
                    if report.compatibility_check is not None else None
                ),
                "check_description": report.check_description,
                "unchecked_scope": [*result["unchecked_scope"], *report.unchecked_scope],
            })
            exit_code = EXIT_OK
        except asyncio.CancelledError:
            cancelled = True
            result.update(
                status="cancelled",
                error="Coding cancelled; partial edits require PI review.",
            )
            exit_code = EXIT_INTERRUPTED
        except TimeoutError:
            result.update(
                status="timeout",
                error="Coding timed out; partial edits require PI review.",
            )
            exit_code = EXIT_TIMEOUT
        except Exception as error:  # noqa: BLE001 - return partial edits, not an assurance
            result["error"] = f"{type(error).__name__}: {error}"
            exit_code = EXIT_SESSION_ERROR
        finally:
            if not self.quiescent:
                cleanup = asyncio.create_task(self.cancel_child())
                while True:
                    try:
                        await asyncio.shield(cleanup)
                        break
                    except asyncio.CancelledError:
                        cancelled = True
                        result.update(
                            status="cancelled",
                            error="Coding cancelled; partial edits require PI review.",
                        )
                        exit_code = EXIT_INTERRUPTED
                        if cleanup.cancelled():
                            self.closed = True
                            self.cancellation_unconfirmed = True
                            break
                    except Exception as error:  # noqa: BLE001 - shutdown must still follow
                        result.update(
                            status="error", cleanup_error=f"{type(error).__name__}: {error}"
                        )
                        exit_code = EXIT_RUNTIME_FAILURE
                        break
            elapsed = time.monotonic() - started
            self.console.coding_duration_seconds += elapsed
            handle = self.active_handle
            result["session_handle"] = handle
            self.native_accounting["agent_id"] = handle
            result["native_accounting"] = self.native_accounting
            result["usage"] = {
                "wall_duration_seconds": round(elapsed, 3),
                "input_tokens": child_console.prompt_tokens
                if "input_tokens" in child_console.reported_usage else None,
                "output_tokens": child_console.output_tokens
                if "output_tokens" in child_console.reported_usage else None,
                "cache_read_tokens": child_console.cache_read_tokens
                if "cache_read_tokens" in child_console.reported_usage else None,
                "cache_write_tokens": child_console.cache_write_tokens
                if "cache_write_tokens" in child_console.reported_usage else None,
                "aiu": child_console.nano_aiu / 1e9
                if "aiu" in child_console.reported_usage else None,
                "tool_calls": child_console.tool_calls,
            }
            try:
                record_usage(
                    self.args, child_console, elapsed, exit_code,
                    role="scientific_coder", session_id=handle,
                    parent_session_id=self.args.session_id,
                )
            except (OSError, ValueError) as error:
                result["usage_error"] = str(error)
                self.console.line("  ! Coding usage could not be recorded.")
            self.active_tasks.discard(task)
            self.busy = self.cancellation_unconfirmed

        try:
            result["changes"], result["diff"] = coding_changes(before)
        except OSError as error:
            result.update(status="error", review_error=str(error), changes=[], diff="")
            result["unchecked_scope"].append("Actual change review could not be collected.")
        encoded = json.dumps(result, ensure_ascii=False)
        if cancelled or len(encoded.encode("utf-8")) > LARGE_OUTPUT_MAX_BYTES:
            LARGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            output = LARGE_OUTPUT_DIR / f"coding-{handle}-{uuid.uuid4()}.json"
            output.write_text(encoded, encoding="utf-8")
            result.pop("diff", None)
            result["review_output_path"] = str(output)
            encoded = json.dumps(result, ensure_ascii=False)
        self.console.line(f"  > scientific_coding: {result['status']}; source/check review required")
        if cancelled:
            self.console.line(
                f"  ! Coding cancelled; partial-change review: {result['review_output_path']}"
            )
            raise asyncio.CancelledError
        return encoded

    async def close(self) -> None:
        self.closed = True
        tasks = list(self.active_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for handle in set(self.bindings) | ({self.active_handle} if self.active_handle else set()):
            await self.cancel_child(handle)

    async def cancel_child(self, handle: str | None = None) -> None:
        from copilot.generated.rpc import TasksCancelRequest

        handle = handle or self.active_handle
        if self.session is None:
            return
        try:
            if handle is None:
                if not self.busy:
                    return
                await self.session.rpc.cancel_all_background_agents(timeout=SHUTDOWN_TIMEOUT_SECONDS)
                async with asyncio.timeout(SHUTDOWN_TIMEOUT_SECONDS):
                    while any(
                        item.status.value == "running"
                        for item in (await self.session.rpc.tasks.list()).tasks
                    ):
                        await asyncio.sleep(0.05)
                return
            await self.session.rpc.tasks.cancel(
                TasksCancelRequest(id=handle), timeout=SHUTDOWN_TIMEOUT_SECONDS
            )
            async with asyncio.timeout(SHUTDOWN_TIMEOUT_SECONDS):
                while True:
                    tasks = await self.session.rpc.tasks.list()
                    child = next((item for item in tasks.tasks if item.id == handle), None)
                    if child is None or child.status.value in {"cancelled", "completed", "failed"}:
                        return
                    await asyncio.sleep(0.05)
        except Exception:
            self.cancellation_unconfirmed = True
            self.closed = True
            if self.operations is not None:
                self.operations.closed = True
            raise


class OperationSubmissionParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: dict[str, object] | None = Field(
        description=(
            "One existing contracts/instruments.md operation envelope. "
            "Use null only to reaccept a failed pending operation after repair."
        ),
        json_schema_extra={
            "anyOf": [protocol.operation_envelope_schema(), {"type": "null"}],
        },
    )

    @field_validator("request")
    @classmethod
    def validate_envelope(cls, request: dict[str, object] | None) -> dict[str, object] | None:
        if request is not None:
            try:
                protocol.validate_operation_envelope(request)
            except TypeError as error:
                raise ValueError(str(error)) from error
        return request


class ControllerChannel:
    def __init__(self, reader, writer) -> None:
        self.reader = reader
        self.writer = writer

    async def send(self, message: dict) -> None:
        self.writer.write((json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8"))
        await self.writer.drain()

    async def receive(self) -> dict:
        line = await self.reader.readline()
        if not line:
            raise ConnectionError(
                "Launcher channel closed; recover durable Runner state, never resubmit blindly."
            )
        message = json.loads(line)
        if not isinstance(message, dict):
            raise ValueError("Controller message must be an object.")
        return message


class OperationSubmission:
    def __init__(self, channel, binding: dict, console: Console, coding) -> None:
        self.channel = channel
        self.binding = binding
        self.console = console
        self.coding = coding
        self.state = binding["state"]
        self.busy = False
        self.closed = False
        self.status = None
        self.error = None
        self.wait_started = None
        self.responses: dict[str, str] = {}
        self.rejections = 0
        self.active_tasks: set[asyncio.Task] = set()
        self.closing = False

    def tool(self):
        from copilot import define_tool

        return define_tool(
            "submit_operation",
            description=(
                "Submit one existing typed operation envelope from contracts/instruments.md "
                "in request. Do not write pi_workspace/operation_request.json; it is internal "
                "Runner exchange. The trusted controller validates and executes it using "
                "existing Runner permissions and allocation, then returns compact factual "
                "result/errors and current state directly to this conversation. Detailed "
                "evidence remains available through artifact_evidence_query. Continue here "
                "after ordinary results or implementation errors; the latter are execution "
                "history, not scientific evidence. Correct source through scientific_coding "
                "and review actual changes before submitting a replacement request, or "
                "request=null to reaccept a failed pending action after repair. Inquiry "
                "open/reframe/close requires checkpoint next. Use actual completed_operations "
                "metadata, not invented IDs; preserve your scientific content. Checkpoint "
                "or terminal commitment ends this bounded context. Do not submit again after "
                "session_ended, validation_fatal, controller_fatal, publication_fatal, "
                "recovery_required or interruption. Do not query evidence after context closure. "
                "No submission result certifies scientific validity."
            ),
            handler=self.invoke,
            params_type=OperationSubmissionParams,
            defer="never",
            skip_permission=True,
        )

    def request_stop(self) -> None:
        path = stop_request_path()
        if path is not None:
            path.write_text("Copilot operation wait interrupted.\n", encoding="utf-8")

    async def invoke(self, params: OperationSubmissionParams, invocation) -> str:
        if (
            invocation.session_id != self.binding["session_id"]
            or not invocation.tool_call_id
            or getattr(invocation, "agent_id", None) is not None
        ):
            return json.dumps({"status": "rejected", "error": "Invalid SDK session binding."})
        call_id = invocation.tool_call_id
        if call_id in self.responses:
            return self.responses[call_id]
        if self.busy or self.closed or (self.coding is not None and self.coding.busy):
            return json.dumps({
                "status": "rejected",
                "error": "Another operation/coding call is active or this session has ended.",
            })
        self.busy = True
        task = asyncio.current_task()
        self.active_tasks.add(task)
        self.wait_started = time.monotonic()
        try:
            await self.channel.send(
                {
                    "type": "operation",
                    "invocation_id": self.binding["invocation_id"],
                    "session_id": self.binding["session_id"],
                    "campaign_id": self.binding["campaign_id"],
                    "event_count": self.state["operation_event_count"],
                    "call_id": call_id,
                    "request": params.request,
                }
            )
            response = await self.channel.receive()
            if (
                response.get("type") != "operation_result"
                or response.get("invocation_id") != self.binding["invocation_id"]
                or response.get("call_id") != call_id
            ):
                raise ValueError(
                    "Operation response binding does not match this submission."
                )
            self.status = response["status"]
            self.error = response.get("error")
            if isinstance(response.get("state"), dict):
                self.state = response["state"]
            self.closed = self.closing or self.status not in {
                "completed",
                "rejected",
                "implementation_error",
            }
            if self.status == "rejected":
                self.rejections += 1
                if self.rejections >= 2:
                    self.closed = True
                    self.status = "validation_fatal"
                    response["status"] = self.status
            else:
                self.rejections = 0
            result = {
                key: value
                for key, value in response.items()
                if key not in {"type", "invocation_id", "call_id"}
            }
            encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
            self.responses[call_id] = encoded
            self.console.line(f"  > submit_operation: {self.status}")
            return encoded
        except asyncio.CancelledError:
            self.closed = True
            self.status = "interrupted"
            self.request_stop()
            raise
        except (OSError, ValueError) as error:
            self.closed = True
            self.status = "recovery_required"
            self.error = str(error)
            self.request_stop()
            return json.dumps({"status": self.status, "error": self.error})
        finally:
            self.console.runner_wait_seconds += time.monotonic() - self.wait_started
            self.wait_started = None
            self.busy = False
            self.active_tasks.discard(task)

    def current_wait_seconds(self) -> float:
        return self.console.runner_wait_seconds + (
            time.monotonic() - self.wait_started if self.wait_started is not None else 0.0
        )

    async def close(self) -> None:
        self.closing = True
        self.closed = True
        tasks = list(self.active_tasks)
        if tasks:
            self.request_stop()
            # Runner owns the cooperative-stop deadline and durable transaction.
            # Consume its response before the shared channel receives another command.
            await asyncio.gather(*tasks, return_exceptions=True)


def session_options(
    args,
    console: Console,
    finished: asyncio.Event,
    coding=None,
    operations=None,
    client=None,
) -> dict:
    from copilot import ToolSet, define_tool
    from copilot.session_events import AssistantMessageData
    from runner.artifact_evidence_query import (
        ArtifactEvidenceQueryParams,
        query_artifact,
    )
    from runner.copilot_scoped_search import ScopedSearch
    from runner.query_training_log import TrainingLogQueryParams, query_training_log
    from runner.scientific_api_reference import ScientificAPIReferenceParams, read_reference

    def authorize_reader(invocation) -> None:
        if (
            invocation.session_id != args.session_id
            or getattr(invocation, "agent_id", None) is not None
            or (coding is not None and (coding.busy or coding.closed))
            or (operations is not None and (operations.busy or operations.closed))
        ):
            raise ValueError("Only the active, unlocked main/preliminary PI may query.")

    model_call_retries = 0

    async def on_error_occurred(request, invocation):
        nonlocal model_call_retries
        if (
            invocation.get("session_id") != args.session_id
            or request.get("sessionId") != args.session_id
            or request.get("errorContext") != "model_call"
            or request.get("recoverable") is not True
            or (operations is not None and operations.closed)
            or (coding is not None and coding.closed)
            or stop_requested()
        ):
            return None
        error = request.get("error")
        message = error.get("message") if isinstance(error, dict) else error
        if not isinstance(message, str):
            return None
        try:
            details = json.loads(message)
        except json.JSONDecodeError:
            return None
        if not isinstance(details, dict) or (
            details.get("code") != "invalid_request_body"
            or details.get("type") != "websocket_error"
            or details.get("message") != "internal server error"
        ):
            return None
        if model_call_retries >= MODEL_CALL_RETRY_LIMIT:
            console.line("  ! Copilot model request failed after five retries; stopping")
            return {"errorHandling": "abort"}
        model_call_retries += 1
        console.line(
            f"  ! Copilot model request failed; retry "
            f"{model_call_retries}/{MODEL_CALL_RETRY_LIMIT} "
            f"in {MODEL_CALL_RETRY_DELAY_SECONDS:g}s"
        )
        await asyncio.sleep(MODEL_CALL_RETRY_DELAY_SECONDS)
        if (
            stop_requested()
            or (operations is not None and operations.closed)
            or (coding is not None and coding.closed)
        ):
            return {"errorHandling": "abort"}
        return {"errorHandling": "retry", "retryCount": 1}

    async def artifact_evidence_query(params, invocation) -> str:
        authorize_reader(invocation)
        return await asyncio.to_thread(
            query_artifact,
            params.model_dump(),
            campaign_id=str(args.campaign_id or ""),
        )

    artifact_evidence_tool = define_tool(
        "artifact_evidence_query",
        description=(
            "Read-only campaign-bound JSON evidence. Provide operation identity, "
            "not a filesystem path. operations pages the operation index; metadata "
            "selects an operation's record, artifact references or checkpoint metadata "
            "without loading artifact contents. Metadata paths are /operation, /record, "
            "/artifacts/* and /checkpoints/*. Use recorded operation_id/artifact_index "
            "as named python_module inputs instead of transcribing filenames. "
            "YOU choose full original content (action=read) "
            "or any selected subsets (query/batch path/where/select), including "
            "several distinct subsets; no summary or projection is compulsory. "
            "discover helps learn shape; aggregates are optional. Array paths expand "
            "to rows when selecting/filtering/aggregating. Missing filter fields are "
            "reported separately from zero matches. Page limits are small by default; "
            "increase limit explicitly for more rows. Set max_bytes on the request. "
            "All batch items share that selected-value budget. Query items reject max_bytes. "
            "Omit select for complete rows; a supplied pointer cannot be empty. Filtering occurs "
            "before data enters PI context. Full reads use byte offset/max_bytes, "
            "UTF-8 content or explicit base64, and fingerprint-bound continuation. "
            "query/batch raw and value_counts use offset paging after selection. "
            "Follow reported next offsets/fingerprints; report transport/traversal "
            "limits honestly and never mistake one truncated page for full retrieval."
        ),
        handler=artifact_evidence_query,
        params_type=ArtifactEvidenceQueryParams,
        defer="auto",
        skip_permission=True,
    )

    def training_log_query(params, invocation) -> str:
        authorize_reader(invocation)
        return query_training_log(
            params.model_dump(exclude_none=True), campaign_id=str(args.campaign_id or "")
        )

    training_log_tool = define_tool(
        "training_log_query",
        description=(
            "Read-only training execution logs by operation_id in this campaign. "
            "Omitting action discovers attempt/step/metric metadata without log values. "
            "YOU choose detailed records, any attempt/time-step/metric subsets "
            "(action=records, attempts/from_step/to_step/metrics), or full original "
            "logs (action=raw); request several distinct subsets if useful. No "
            "forced summary. Records require exact metrics or explicit all_metrics=true; "
            "small row/byte pages are the default, not full trajectories. Filtering "
            "occurs before data enters PI context. "
            "Records have offset/limit with expected_log_fingerprints on continuation; "
            "raw pages have byte offset/max_bytes/expected_fingerprint, readable "
            "UTF-8 by default or explicit base64. Follow provenance and continuation, "
            "and report limits rather than claim incomplete transport is complete. "
            "Failed/pending-failure logs are execution history, NOT scientific evidence."
        ),
        handler=training_log_query,
        params_type=TrainingLogQueryParams,
        defer="auto",
        skip_permission=True,
    )

    async def scientific_api_reference(params, invocation) -> str:
        if getattr(invocation, "agent_id", None) is None:
            authorize_reader(invocation)
        elif (
            invocation.session_id != args.session_id or coding is None
            or not coding.busy or coding.closed or coding.binding is None
            or invocation.agent_id != coding.active_handle
            or (operations is not None and (operations.busy or operations.closed))
        ):
            raise ValueError("Only the active main PI or its authorized coding child may read APIs.")
        return json.dumps(await asyncio.to_thread(read_reference, params), ensure_ascii=False)

    api_reference_tool = define_tool(
        "scientific_api_reference",
        description=(
            "Read-only installed API definitions for mujoco, gymnasium or stable_baselines3. "
            "Select library and a public dotted symbol relative to that library. "
            "No filesystem paths, private attributes, arbitrary code, constructors, "
            "or scientific API calls are accepted. Imports load only the fixed library roots. "
            "action=members lists public names with optional contains filtering; "
            "offset/limit page member rows. action=definition returns installed signature, "
            "documentation, available Python source and native MuJoCo declaration; "
            "offset/max_bytes page UTF-8 definition bytes. Missing symbols and unavailable "
            "source/signatures are explicit, not guessed. Follow next_offset for complete "
            "retrieval. Main PI and its exact-scope coding child can both use this reader. "
            "Reference availability is not proof that a production integration executes."
        ),
        handler=scientific_api_reference,
        params_type=ScientificAPIReferenceParams,
        defer="auto",
        skip_permission=True,
    )
    # The pinned SDK exposes the actual spawned runtime connection. Locate its
    # bundled rg, rather than invoking a model-controlled shell or directory search.
    runtime_path = getattr(getattr(client, "_connection", None), "path", None)
    runtime_directory = Path(runtime_path).parent if runtime_path else None
    candidates = (
        sorted(runtime_directory.glob("ripgrep\\bin\\*\\rg.exe"))
        if runtime_directory is not None else []
    )
    rg_path = Path(shutil.which("rg")) if shutil.which("rg") else next(iter(candidates), None)
    search = ScopedSearch(
        ROOT, lambda path: file_read_denial(path, preliminary=args.preliminary),
        rg_path, authorize_reader,
    )

    handle_event, on_permission_request = build_handlers(
        console, finished, preliminary=args.preliminary, operations=operations, coding=coding
    )

    def on_event(event) -> None:
        nonlocal model_call_retries
        if (
            getattr(event, "agent_id", None) is None
            and isinstance(event.data, AssistantMessageData)
            and event.data.interaction_id is not None
        ):
            model_call_retries = 0
        handle_event(event)

    tools = [*search.tools(), artifact_evidence_tool, training_log_tool, api_reference_tool]
    available = (
        ToolSet()
        .add_builtin([
            name for name in (RESEARCH_TOOLS if args.preliminary else MAIN_PI_TOOLS)
            if name not in {"rg", "glob"}
        ])
        .add_custom("rg").add_custom("glob")
        .add_custom("artifact_evidence_query")
        .add_custom("training_log_query")
        .add_custom("scientific_api_reference")
    )
    if not args.preliminary and coding is not None:
        tools.append(coding.tool())
        available.add_custom("scientific_coding")
        available.add_builtin("apply_patch")
    if not args.preliminary and operations is not None:
        tools.append(operations.tool())
        available.add_custom("submit_operation")
    options = {
        "model": normalize_model(args.model),
        "reasoning_effort": args.reasoning,
        "on_event": on_event,
        "on_permission_request": on_permission_request,
        "tools": tools,
        "available_tools": available,
        "working_directory": str(ROOT),
        "streaming": True,
        "enable_file_change_tracking": True,
        "enable_skills": False,
        "enable_session_store": False,
        "skip_embedding_retrieval": True,
        "enable_mcp_apps": False,
        "skip_custom_instructions": True,
        "enable_config_discovery": False,
        "enable_on_demand_instruction_discovery": False,
        "mcp_servers": {},
        "custom_agents": [coding.agent()] if coding is not None else [],
        "memory": {"enabled": False},
        "large_output": {
            "enabled": True,
            "max_size_bytes": LARGE_OUTPUT_MAX_BYTES,
            "output_directory": str(LARGE_OUTPUT_DIR),
        },
    }
    options["hooks"] = {
        "on_pre_tool_use": scoped_tool_hook(
            operations=operations, coding=coding, preliminary=args.preliminary
        ),
        "on_error_occurred": on_error_occurred,
    }
    if not args.preliminary:
        options["include_sub_agent_streaming_events"] = True
        options["default_agent"] = {"excluded_tools": ["apply_patch"]}
        if coding is not None:
            options["hooks"]["on_subagent_start"] = coding.start_hook
            options["hooks"]["on_subagent_stop"] = coding.stop_hook
        options["enable_file_hooks"] = False
        options["enable_host_git_operations"] = False
        options["request_extensions"] = False
    return options


async def open_session(client, args, options: dict):
    args.resumed_session = bool(args.resume)
    if args.resume:
        try:
            # The new controller has no prior tool-response cache. Never replay
            # unfinished SDK work against already advanced durable Runner state.
            return await client.resume_session(
                args.session_id, continue_pending_work=False, **options
            )
        except Exception as error:
            raise RuntimeError(
                "could not resume the persisted researcher session "
                f"{args.session_id!r}; refusing to create a replacement"
            ) from error
    if args.resume_or_create:
        metadata = await client.get_session_metadata(args.session_id)
        if metadata is not None:
            args.resumed_session = True
            return await client.resume_session(
                args.session_id, continue_pending_work=False, **options
            )
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


async def run(args, *, client=None, channel=None, binding=None) -> int:
    from copilot import CopilotClient

    console = getattr(args, "usage_console", None) or Console()
    finished = asyncio.Event()
    model = normalize_model(args.model)

    if stop_requested():
        return EXIT_INTERRUPTED

    owned_client = client is None
    if not args.preliminary and channel is None:
        raise ValueError("Ordinary Copilot PI sessions require the trusted launcher controller.")
    client = client or CopilotClient(working_directory=str(ROOT))
    coding = ScientificCoding(client, args, console) if not args.preliminary else None
    operations = (
        OperationSubmission(channel, binding, console, coding)
        if not args.preliminary else None
    )
    if coding is not None:
        coding.operations = operations
    args.operation_submission = operations
    session = None
    abort_session = False
    try:
        if owned_client:
            await client.start()
        status = await client.get_auth_status() if owned_client else None
        if owned_client and not getattr(status, "isAuthenticated", False):
            print(
                "Copilot is not authenticated. Run `copilot` once and sign in.",
                file=sys.stderr,
            )
            return EXIT_NOT_AUTHENTICATED

        available = [entry.id for entry in await client.list_models()] if owned_client else []
        if owned_client and model not in available:
            print(
                f"Model '{model}' is not available to this Copilot account. "
                f"Available: {', '.join(available)}",
                file=sys.stderr,
            )
            return EXIT_MODEL_UNAVAILABLE

        session = await open_session(
            client, args, session_options(args, console, finished, coding, operations, client)
        )
        if coding is not None:
            coding.session = session
        before = worktree_status()
        before_offload = offload_snapshot()
        started = time.monotonic()
        finished_task = asyncio.create_task(finished.wait())
        stop_task = asyncio.create_task(wait_for_stop_request())
        async def active_timeout() -> None:
            while True:
                waited = operations.current_wait_seconds() if operations is not None else 0.0
                if time.monotonic() - started - waited >= args.timeout:
                    return
                await asyncio.sleep(0.25)

        timeout_task = asyncio.create_task(active_timeout())
        try:
            prompt = args.prompt
            if operations is not None and args.resumed_session:
                prompt += (
                    "\n\nRecovered current Runner state (factual metadata, not new "
                    "scientific evidence). Automatic pending-work replay is disabled; "
                    "continue from this durable state, not an unfinished old tool call:\n"
                    + json.dumps(operations.state, ensure_ascii=False)
                )
            await session.send(prompt)
            for attempt in range(2):
                done, _ = await asyncio.wait(
                    (finished_task, stop_task, timeout_task),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if (
                    stop_task in done or timeout_task in done
                    or args.preliminary or console.session_error
                    or (operations is not None and operations.closed)
                ):
                    break
                if attempt == 0:
                    finished.clear()
                    finished_task = asyncio.create_task(finished.wait())
                    await session.send(
                        "This bounded session is still active. Continue from the actual "
                        "operation results in this conversation. Submit the next supported "
                        "action or the scientific checkpoint through submit_operation. "
                        "Current factual state: " + json.dumps(operations.state)
                    )
            if stop_task in done:
                abort_session = True
                console.line("  ! session interrupted")
                return EXIT_INTERRUPTED
            if timeout_task in done:
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
            timeout_task.cancel()
            await asyncio.gather(
                finished_task, stop_task, timeout_task, return_exceptions=True
            )

        console.summary(
            session.session_id,
            changed_since(before),
            offloaded_since(before_offload),
            elapsed_seconds=time.monotonic() - started,
        )
        if operations is not None and operations.status != "session_ended":
            return EXIT_SESSION_ERROR
        return EXIT_SESSION_ERROR if console.session_error else EXIT_OK
    finally:
        try:
            if operations is not None:
                await operations.close()
            if coding is not None:
                await coding.close()
        finally:
            if owned_client:
                await shutdown_runtime(client, session, console, abort=abort_session)
            elif session is not None:
                if abort_session:
                    await asyncio.wait_for(session.abort(), SHUTDOWN_TIMEOUT_SECONDS)
                await asyncio.wait_for(session.disconnect(), SHUTDOWN_TIMEOUT_SECONDS)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", nargs="?")
    parser.add_argument("--session-id")
    parser.add_argument("--controller-port", type=int)
    parser.add_argument("--controller-token")
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
    args = parser.parse_args(argv)
    if args.controller_port:
        if not args.controller_token or args.session_id or args.prompt:
            parser.error("controller mode requires a token and no direct session/prompt")
    elif not args.session_id or args.prompt is None:
        parser.error("a bounded invocation requires session-id and prompt")
    return args


def console_label(args) -> str:
    """The bounded phase a session belongs to, for the console only."""
    return str(args.phase or "")


def record_usage(
    args,
    console: Console,
    elapsed: float,
    exit_code: int,
    *,
    role: str = "pi",
    session_id: str | None = None,
    parent_session_id: str | None = None,
) -> None:
    """Append aggregate usage, never conversation content or tool arguments."""
    if not args.campaign_id:
        return  # Standalone invocations are not attributed to an arbitrary campaign.
    # Campaign IDs are path components, not filenames supplied by the model.
    campaign_id = str(uuid.UUID(args.campaign_id))
    directory = ROOT / "reports" / "session_usage"
    directory.mkdir(parents=True, exist_ok=True)
    row = {
        "campaign_id": campaign_id,
        "phase": args.phase,
        "attempt": args.attempt,
        "session_id": session_id or args.session_id,
        "role": role,
        "parent_session_id": parent_session_id,
        "recorded_at": datetime.now(UTC).isoformat(),
        "model": normalize_model(args.model),
        "reasoning": args.reasoning,
        # Child time is reported in its own row, not again in the PI row.
        "duration_seconds": round(
            max(
                0.0,
                elapsed - console.coding_duration_seconds - console.runner_wait_seconds,
            ), 3
        ),
        "wall_duration_seconds": round(elapsed, 3),
        "runner_wait_seconds": round(console.runner_wait_seconds, 3),
        "exit_code": exit_code,
        "input_tokens": console.prompt_tokens
        if "input_tokens" in console.reported_usage
        else None,
        "cache_read_tokens": console.cache_read_tokens
        if "cache_read_tokens" in console.reported_usage
        else None,
        "cache_write_tokens": console.cache_write_tokens
        if "cache_write_tokens" in console.reported_usage
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


async def serve(args) -> int:
    from copilot import CopilotClient

    reader, writer = await asyncio.open_connection(
        "127.0.0.1", args.controller_port, limit=4 * 1024 * 1024
    )
    channel = ControllerChannel(reader, writer)
    client = CopilotClient(working_directory=str(ROOT))
    console = Console()
    try:
        await client.start()
        status = await client.get_auth_status()
        if not getattr(status, "isAuthenticated", False):
            raise RuntimeError("Copilot is not authenticated.")
        available = [entry.id for entry in await client.list_models()]
        if normalize_model(args.model) not in available:
            raise RuntimeError(f"Configured model {args.model!r} is unavailable.")
        await channel.send({"type": "ready", "token": args.controller_token})
        while not stop_requested():
            command = await channel.receive()
            if command.get("type") == "shutdown":
                break
            if command.get("type") != "session":
                raise ValueError("Unexpected controller command.")
            invocation_args = parse_args(command["arguments"])
            if (
                invocation_args.session_id != command["session_id"]
                or invocation_args.campaign_id != command["campaign_id"]
                or normalize_model(invocation_args.model) != normalize_model(args.model)
                or invocation_args.reasoning != args.reasoning
            ):
                raise ValueError("Controller invocation binding/configuration mismatch.")
            invocation_args.usage_console = Console(console_label(invocation_args))
            started = time.monotonic()
            exit_code = EXIT_RUNTIME_FAILURE
            error = None
            try:
                exit_code = await run(
                    invocation_args, client=client, channel=channel, binding=command
                )
            except Exception as exc:  # noqa: BLE001 - preserve bounded runtime failure
                error = f"{type(exc).__name__}: {exc}"
            finally:
                try:
                    record_usage(
                        invocation_args, invocation_args.usage_console,
                        time.monotonic() - started, exit_code,
                    )
                except (OSError, ValueError) as exc:
                    print(f"Session usage could not be recorded: {exc}", file=sys.stderr)
            operations = getattr(invocation_args, "operation_submission", None)
            outcome_status = operations.status if operations is not None else "preliminary"
            outcome_error = (
                error
                or (operations.error if operations is not None else None)
                or invocation_args.usage_console.session_error
            )
            if exit_code == EXIT_TIMEOUT:
                outcome_status = "controller_fatal"
                outcome_error = (
                    f"Copilot bounded session timed out after {invocation_args.timeout}s."
                )
            elif exit_code == EXIT_INTERRUPTED:
                outcome_status = "interrupted"
                outcome_error = "Copilot bounded session interrupted."
            elif exit_code != EXIT_OK and outcome_status in {
                None, "preliminary", "completed", "rejected",
                "implementation_error", "session_ended",
            }:
                outcome_status = "controller_fatal"
                outcome_error = outcome_error or (
                    f"Copilot bounded session exited with code {exit_code} "
                    "without a successful session outcome."
                )
            await channel.send({
                "type": "session_result",
                "invocation_id": command["invocation_id"],
                "exit_code": exit_code,
                "status": outcome_status,
                "error": outcome_error,
            })
            if exit_code not in {EXIT_OK, EXIT_SESSION_ERROR}:
                break
        return EXIT_OK
    finally:
        try:
            await shutdown_runtime(client, None, console, abort=False)
        finally:
            writer.close()
            await writer.wait_closed()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.usage_console = Console(console_label(args))
    started = time.monotonic()
    exit_code = EXIT_RUNTIME_FAILURE
    try:
        exit_code = asyncio.run(serve(args) if args.controller_port else run(args))
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
