"""Existing preliminary shell parsing and command authorization."""

from __future__ import annotations

import shlex
from pathlib import Path

from runner.path_policy import (
    FILE_READ_DENIAL,
    ROOT,
    file_read_denial,
    is_reserved_execution,
)

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
