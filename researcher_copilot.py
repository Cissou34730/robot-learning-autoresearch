"""One bounded Researcher session, executed through the GitHub Copilot SDK.

The launcher owns the research protocol and decides whether a phase is complete;
this adapter owns only the Copilot runtime: session identity, the tool profile,
the command policy, and what reaches the console. Nothing printed here is read
back as a scientific fact.
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent

EXIT_OK = 0
EXIT_SESSION_ERROR = 2
EXIT_NOT_AUTHENTICATED = 3
EXIT_MODEL_UNAVAILABLE = 4
EXIT_TIMEOUT = 5
EXIT_RUNTIME_FAILURE = 6
EXIT_INTERRUPTED = 130

_RESET = "\033[0m"
_DIM = "\033[90m"
_MARKER_COLORS = {
    ">": "\033[36m",
    "x": "\033[31m",
    "+": "\033[32m",
    "-": "\033[31m",
    "~": "\033[36m",
    "!": "\033[33m",
    "--": "\033[36m",
}


def format_console_line(text: str) -> str:
    if not sys.stdout.isatty():
        return text
    stripped = text.lstrip()
    indent = text[: len(text) - len(stripped)]
    marker, separator, remainder = stripped.partition(" ")
    color = _MARKER_COLORS.get(marker, "\033[36m")
    timestamp = f"{_DIM}[{datetime.now(UTC).astimezone():%H:%M:%S}]{_RESET}"
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

# Temporary diagnostic visibility for issue #20. Repopulate this set after the
# diagnostic campaigns to quiet selected tool starts again; outputs stay hidden.
SILENT_TOOLS: frozenset[str] = frozenset()

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

GIT_DENIAL = (
    "Denied by the harness: the runner owns mutating Git operations and "
    "restoration. Read-only git is available for code provenance and code "
    "inspection when the current task requires it. To "
    'revert this experiment\'s code, set "code": {"action": "revert", '
    '"reason": "..."} in the lineage proposal and the runner restores it.'
)

EXECUTION_DENIAL = (
    "Denied by the harness: the launcher executes experiments, not the "
    "researcher. Write this phase's deliverable and the launcher will validate "
    "and run it."
)

SUITE_DENIAL = (
    "Denied by the harness: a repository-wide pytest run belongs to the runner. "
    "Run the specific suite you need, for example `uv run pytest tests/scenario`."
)

DEPENDENCY_DENIAL = (
    "Denied by the harness: the project dependency set is human-owned. Use the "
    "installed environment without installing, removing, syncing or locking packages."
)

RESERVED_SCRIPT_NAMES = (
    "run_experiment.py",
    "final_benchmark.py",
    "migrate_policy_runtime.py",
)

RESERVED_SCRIPT_PATHS = (
    "robot_learning/evaluate.py",
    "robot_learning/play.py",
    "robot_learning/train.py",
)

RESERVED_MODULES = (
    "research.migrate_policy_runtime",
    "robot_learning.evaluate",
    "robot_learning.train",
    "robot_learning.play",
    "robot_learning.benchmark.final_benchmark",
)

# Commands that only ever read. Naming a protected path to one of these is
# research, not execution.
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

SEPARATORS = (";", "&&", "||", "|", "\n", "\r")

# Oversized tool results are written here instead of occupying the context for
# the rest of the session. The researcher still opens them on demand.
LARGE_OUTPUT_DIR = ROOT / ".copilot" / "large-output"
LARGE_OUTPUT_MAX_BYTES = 32_768

POLICY = f"""
<harness_policy>
This session runs inside the repository worktree {ROOT}. The harness enforces
the rules below at the tool boundary, so a rejected call fails rather than
succeeding silently. A rejection names the sanctioned alternative; follow it
instead of retrying the same command.

- The launcher executes experiments. Never invoke research/run_experiment.py,
  training, the viewer, or the final benchmark.
- Use research/brief.md and the campaign artifacts as the authoritative
    scientific context. Do not use Git history as scientific evidence or as a
    routine workspace-discovery step.
- The runner owns mutating Git operations, provenance and restoration.
    Read-only Git is available only when the current task specifically requires
    inspecting the experiment's current code state or delta. To revert this
    experiment's code, use the lineage proposal's "code" decision.
- A repository-wide pytest run belongs to the runner; run a specific suite.
- Every tool call resends the whole conversation, so prefer one aggregation over
  the same command repeated per file, and read what you need rather than whole
  artifacts.
  When the same extraction or analysis is needed across several artifacts, prefer
  one aggregated tool call when practical and when the combined result remains
  compact. Separate calls remain appropriate when the scientific question differs
  between artifacts or aggregation would make the analysis less clear.
- Use targeted tests, linting, parsing or analysis while developing the phase
  deliverable when they resolve uncertainty introduced by the work. Once the
  deliverable is complete, do not perform a separate final validation pass solely
  to reconfirm the deliverable or repository state; the Runner owns final contract
  and execution validation. The phase ends when its deliverable has been written.
</harness_policy>
""".strip()


def normalize_model(model: str) -> str:
    """OpenCode named the provider inside the model; the SDK names only the model."""
    return model.split("/", 1)[1] if "/" in model else model


def thousands(count: int) -> str:
    return f"{count / 1000:.0f}k" if count >= 1000 else str(count)


def command_segments(command: str) -> list[list[str]]:
    text = command
    for separator in SEPARATORS:
        text = text.replace(separator, "\x00")
    return [segment.split() for segment in text.split("\x00") if segment.split()]


def strip_launcher_prefix(tokens: list[str]) -> list[str]:
    """Drop a leading `uv run [--flag value]` so the real invocation is visible."""
    if not tokens or tokens[0].lower() not in {"uv", "uvx"}:
        return tokens
    index = 1
    if index < len(tokens) and tokens[index].lower() == "run":
        index += 1
    while index < len(tokens) and tokens[index].startswith("-"):
        index += 1
        if index < len(tokens) and not tokens[index].startswith("-"):
            index += 1
    return tokens[index:]


def execution_target(tokens: list[str]) -> str | None:
    """What this segment would actually run, ignoring anything it merely names."""
    if not tokens:
        return None
    if tokens[0].lower().strip("&.") in READER_COMMANDS:
        return None
    tokens = strip_launcher_prefix(tokens)
    if not tokens:
        return None
    if Path(tokens[0]).name.lower() not in INTERPRETERS:
        return tokens[0]
    arguments = tokens[1:]
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "-m" and index + 1 < len(arguments):
            return arguments[index + 1]
        if argument in {"-c", "--command"}:
            # Inline code names no target; the guardrail stops here by design.
            return None
        if argument.startswith("-"):
            index += 1
            continue
        return argument
    return None


def is_reserved_execution(target: str | None) -> bool:
    if not target:
        return False
    normalized = target.replace("\\", "/").lstrip("./").lower()
    if Path(normalized).name in RESERVED_SCRIPT_NAMES:
        return True
    if any(normalized.endswith(path) for path in RESERVED_SCRIPT_PATHS):
        return True
    return normalized in RESERVED_MODULES


def denied_git_subcommand(tokens: list[str]) -> str | None:
    """The subcommand when it is not a read-only one, so unknown verbs deny."""
    if "git" not in tokens:
        return None
    for token in tokens[tokens.index("git") + 1 :]:
        if token.startswith("-"):
            continue
        return None if token in READ_ONLY_GIT else token
    return "git"


def is_repository_wide_pytest(tokens: list[str]) -> bool:
    if "pytest" not in tokens:
        return False
    return not any(
        not token.startswith("-") for token in tokens[tokens.index("pytest") + 1 :]
    )


def is_dependency_management(tokens: list[str]) -> bool:
    """Whether a command changes or extends the fixed project dependency set."""
    if not tokens:
        return False
    lowered = [token.lower() for token in tokens]
    executable = Path(lowered[0].strip("&.")).name.removesuffix(".exe")
    if executable == "uvx":
        return True
    if executable == "uv":
        if len(lowered) < 2:
            return False
        operation = lowered[1]
        if operation in {"add", "remove", "sync", "lock", "pip", "tool"}:
            return True
        if operation == "run":
            if any(token.startswith("--with") for token in lowered[2:]):
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


def command_denial(command: str) -> str | None:
    """The reason this command is refused, or None when it may run.

    Only what a segment executes is judged, never what it mentions: reading or
    grepping a protected path is ordinary research. A guardrail against the
    failures that have actually broken research runs, not a sandbox --
    `uv run python -c` can still do anything the researcher could.
    """
    for tokens in command_segments(command):
        if is_dependency_management(tokens):
            return DEPENDENCY_DENIAL
        target = execution_target(tokens)
        if not target:
            continue
        name = Path(target).name.lower().removesuffix(".exe")
        if is_reserved_execution(target):
            return EXECUTION_DENIAL
        if name == "git" and denied_git_subcommand(tokens):
            return GIT_DENIAL
        if name == "pytest" and is_repository_wide_pytest(tokens):
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


class Console:
    """Everything the human sees, and nothing the protocol reads back."""

    def __init__(self) -> None:
        self._mid_stream = False
        self.changed_files: dict[str, str] = {}
        self.prompt_tokens = 0
        self.cache_read_tokens = 0
        self.cache_write_tokens = 0
        self.output_tokens = 0
        self.nano_aiu = 0.0
        self.nano_aiu_by_type: dict[str, float] = {}
        self.session_error: str | None = None
        self.denials = 0
        self.tool_calls = 0
        self.denied_calls: set[str] = set()
        self.active_tools: dict[str, tuple[str, object]] = {}

    def line(self, text: str) -> None:
        if self._mid_stream:
            print(flush=True)
            self._mid_stream = False
        print(format_console_line(text), flush=True)

    def delta(self, text: str) -> None:
        if not text:
            return
        print(text, end="", flush=True)
        self._mid_stream = True

    def message(self, text: str) -> None:
        if self._mid_stream or not text:
            return
        print(text, flush=True)

    def tool(
        self, name: str, arguments: object, tool_call_id: str | None = None
    ) -> None:
        self.tool_calls += 1
        if tool_call_id:
            self.active_tools[tool_call_id] = (name, arguments)
        if name in SILENT_TOOLS:
            return
        detail = ""
        if isinstance(arguments, dict):
            keys = (
                ("query", "pattern", "path")
                if name in {"rg", "glob"}
                else (
                    "command",
                    "commandLine",
                    "path",
                    "filePath",
                    "query",
                    "pattern",
                    "shellId",
                    "shell_id",
                    "session_id",
                )
            )
            raw = next(
                (
                    arguments[key]
                    for key in keys
                    if isinstance(arguments.get(key), (str, int))
                    and arguments[key] != ""
                ),
                "",
            )
            detail = str(raw)
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
                        targets.append(line.split(": ", 1)[1])
                        if len(targets) == 3:
                            break
                if targets:
                    detail = ", ".join(targets)
        detail = " ".join(detail.split())
        if len(detail) > 110:
            detail = detail[:107] + "..."
        self.line(f"  > {name}: {detail}" if detail else f"  > {name}")

    def tool_failed(
        self, error: object, name: str = "tool", arguments: object = None
    ) -> None:
        target = ""
        if isinstance(arguments, dict):
            raw = next(
                (
                    arguments[key]
                    for key in ("path", "filePath", "query", "command", "commandLine")
                    if arguments.get(key)
                ),
                "",
            )
            target = " ".join(str(raw).split())
        if len(target) > 100:
            target = target[:97] + "..."
        reason = " ".join(str(error or "").split())
        if len(reason) > 160:
            reason = reason[:157] + "..."
        operation = f"{name} ({target})" if target else name
        self.line(f"  x {operation} failed: {reason}")

    def denied(self, reason: str, tool_call_id: str | None = None) -> None:
        self.denials += 1
        if tool_call_id:
            self.denied_calls.add(tool_call_id)
        self.line(f"  x {reason.splitlines()[0]}")

    def file_changed(self, operation: str, path: str) -> None:
        marker = {"created": "+", "deleted": "-"}.get(str(operation), "~")
        if self.changed_files.get(path) != marker:
            self.changed_files[path] = marker
            self.line(f"  {marker} {path}")

    def error(self, message: str) -> None:
        self.session_error = message
        self.line(f"  ! session error: {message}")

    def summary(
        self, session_id: str, changed: list[str], offloaded: tuple[int, int] = (0, 0)
    ) -> None:
        for path in changed:
            if path not in self.changed_files:
                self.line(f"  ~ {path}")
        files = f"{len(changed)} file(s) changed"
        denials = f", {self.denials} denied" if self.denials else ""
        self.line(
            f"-- session {session_id[:8]}: {files}, {self.usage()}"
            f", {self.work(offloaded)}{denials}"
        )

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


def build_handlers(console: Console, finished: asyncio.Event):
    from copilot.rpc import PermissionDecisionApproveOnce, PermissionDecisionReject
    from copilot.session_events import (
        AssistantMessageData,
        AssistantMessageDeltaData,
        AssistantUsageData,
        PermissionRequestShell,
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
            console.prompt_tokens += data.input_tokens or 0
            console.cache_read_tokens += data.cache_read_tokens or 0
            console.cache_write_tokens += data.cache_write_tokens or 0
            console.output_tokens += data.output_tokens or 0
            usage = getattr(data, "copilot_usage", None)
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
            finished.set()

    def on_permission_request(request, invocation):
        del invocation
        if isinstance(request, PermissionRequestShell):
            reason = command_denial(shell_command_text(request))
            if reason:
                console.denied(reason, getattr(request, "tool_call_id", None))
                return PermissionDecisionReject(feedback=reason)
        return PermissionDecisionApproveOnce()

    return on_event, on_permission_request


def session_options(args, console: Console, finished: asyncio.Event) -> dict:
    from copilot import ToolSet

    on_event, on_permission_request = build_handlers(console, finished)
    return {
        "model": normalize_model(args.model),
        "reasoning_effort": args.reasoning,
        "on_event": on_event,
        "on_permission_request": on_permission_request,
        "available_tools": ToolSet().add_builtin(RESEARCH_TOOLS),
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
        "system_message": {"mode": "append", "content": POLICY},
    }


async def open_session(client, args, options: dict):
    if args.resume:
        return await client.resume_session(args.session_id, **options)
    return await client.create_session(session_id=args.session_id, **options)


async def run(args) -> int:
    from copilot import CopilotClient

    console = Console()
    finished = asyncio.Event()
    model = normalize_model(args.model)

    async with CopilotClient(working_directory=str(ROOT)) as client:
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
        try:
            await session.send(args.prompt)
            await asyncio.wait_for(finished.wait(), timeout=args.timeout)
        except TimeoutError:
            await session.abort()
            console.line(f"  ! session timed out after {args.timeout}s")
            console.summary(
                session.session_id,
                changed_since(before),
                offloaded_since(before_offload),
            )
            return EXIT_TIMEOUT
        except KeyboardInterrupt:
            await session.abort()
            console.line("  ! session interrupted")
            return EXIT_INTERRUPTED
        finally:
            await session.disconnect()

        console.summary(
            session.session_id, changed_since(before), offloaded_since(before_offload)
        )
        return EXIT_SESSION_ERROR if console.session_error else EXIT_OK


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
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--timeout", type=float, default=1800.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
    except Exception as error:  # noqa: BLE001 - the launcher needs a code, not a traceback
        print(f"Copilot runtime failure: {error}", file=sys.stderr)
        return EXIT_RUNTIME_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
