"""One bounded Researcher session, executed through the GitHub Copilot SDK.

The launcher owns the research protocol and decides whether a phase is complete;
this adapter owns only the Copilot runtime: session identity, the tool profile,
the command policy, and what reaches the console. Nothing printed here is read
back as a scientific fact.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

EXIT_OK = 0
EXIT_SESSION_ERROR = 2
EXIT_NOT_AUTHENTICATED = 3
EXIT_MODEL_UNAVAILABLE = 4
EXIT_TIMEOUT = 5
EXIT_RUNTIME_FAILURE = 6
EXIT_INTERRUPTED = 130

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

# Reading, searching and patching are how the researcher works; announcing each
# one buries the few events that carry meaning. Edits surface as file changes.
SILENT_TOOLS = frozenset(
    {
        "view",
        "rg",
        "glob",
        "apply_patch",
        "read_powershell",
        "list_powershell",
        "stop_powershell",
    }
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

GIT_DENIAL = (
    "Denied by the harness: the runner owns Git history. Read-only git is "
    "available (status, diff, log, show, rev-parse, ls-files, cat-file). To "
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

RESERVED_EXECUTION = (
    "run_experiment.py",
    "robot_learning.train",
    "robot_learning/train.py",
    "robot_learning.play",
    "robot_learning/play.py",
    "final_benchmark",
)

SEPARATORS = (";", "&&", "||", "|", "\n", "\r")

POLICY = f"""
<harness_policy>
This session runs inside the repository worktree {ROOT}. The harness enforces
the rules below at the tool boundary, so a rejected call fails rather than
succeeding silently. A rejection names the sanctioned alternative; follow it
instead of retrying the same command.

- The launcher executes experiments. Never invoke research/run_experiment.py,
  training, the viewer, or the final benchmark.
- The runner owns Git history. Read-only git is allowed. To revert this
  experiment's code, use the lineage proposal's "code" decision.
- A repository-wide pytest run belongs to the runner; run a specific suite.
- The phase ends when its deliverable file is written, not when you have
  finished explaining. Write the file.
</harness_policy>
""".strip()


def normalize_model(model: str) -> str:
    """OpenCode named the provider inside the model; the SDK names only the model."""
    return model.split("/", 1)[1] if "/" in model else model


def command_segments(command: str) -> list[list[str]]:
    text = command
    for separator in SEPARATORS:
        text = text.replace(separator, "\x00")
    return [segment.split() for segment in text.split("\x00") if segment.split()]


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


def command_denial(command: str) -> str | None:
    """The reason this command is refused, or None when it may run.

    A guardrail against the failures that have actually broken research runs,
    not a sandbox: `uv run python -c` can still do anything the researcher could.
    """
    for tokens in command_segments(command):
        segment = " ".join(tokens)
        if any(reserved in segment for reserved in RESERVED_EXECUTION):
            return EXECUTION_DENIAL
        if denied_git_subcommand(tokens):
            return GIT_DENIAL
        if is_repository_wide_pytest(tokens):
            return SUITE_DENIAL
    return None


def shell_command_text(request: object) -> str:
    segments = [
        getattr(segment, "full_command_text", "") or ""
        for segment in (getattr(request, "command_segments", None) or [])
    ]
    return "\n".join([getattr(request, "full_command_text", "") or "", *segments])


class Console:
    """Everything the human sees, and nothing the protocol reads back."""

    def __init__(self) -> None:
        self._mid_stream = False
        self.changed_files: dict[str, str] = {}
        self.input_tokens = 0
        self.output_tokens = 0
        self.session_error: str | None = None
        self.denials = 0
        self.denied_calls: set[str] = set()

    def line(self, text: str) -> None:
        if self._mid_stream:
            print(flush=True)
            self._mid_stream = False
        print(text, flush=True)

    def delta(self, text: str) -> None:
        if not text:
            return
        print(text, end="", flush=True)
        self._mid_stream = True

    def message(self, text: str) -> None:
        if self._mid_stream or not text:
            return
        print(text, flush=True)

    def tool(self, name: str, arguments: object) -> None:
        if name in SILENT_TOOLS:
            return
        detail = ""
        if isinstance(arguments, dict):
            raw = arguments.get("command") or arguments.get("commandLine") or ""
            detail = " ".join(str(raw).split())
        if len(detail) > 110:
            detail = detail[:107] + "..."
        self.line(f"  > {name}: {detail}" if detail else f"  > {name}")

    def tool_failed(self, error: str) -> None:
        detail = " ".join(str(error or "").split())
        if len(detail) > 160:
            detail = detail[:157] + "..."
        self.line(f"  x tool failed: {detail}")

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

    def summary(self, session_id: str) -> None:
        files = f"{len(self.changed_files)} file(s) changed"
        tokens = f"{self.input_tokens} in / {self.output_tokens} out tokens"
        denials = f", {self.denials} denied" if self.denials else ""
        self.line(f"-- session {session_id[:8]}: {files}, {tokens}{denials}")


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
            console.tool(data.tool_name, data.arguments)
        elif isinstance(data, ToolExecutionCompleteData):
            # A call this harness rejected already reported its reason.
            if (
                not data.success
                and data.error
                and data.tool_call_id not in console.denied_calls
            ):
                console.tool_failed(data.error)
        elif isinstance(data, SessionWorkspaceFileChangedData):
            console.file_changed(data.operation, data.path)
        elif isinstance(data, AssistantUsageData):
            console.input_tokens += data.input_tokens or 0
            console.output_tokens += data.output_tokens or 0
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
        try:
            await session.send(args.prompt)
            await asyncio.wait_for(finished.wait(), timeout=args.timeout)
        except TimeoutError:
            await session.abort()
            console.line(f"  ! session timed out after {args.timeout}s")
            console.summary(session.session_id)
            return EXIT_TIMEOUT
        except KeyboardInterrupt:
            await session.abort()
            console.line("  ! session interrupted")
            return EXIT_INTERRUPTED
        finally:
            await session.disconnect()

        console.summary(session.session_id)
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
