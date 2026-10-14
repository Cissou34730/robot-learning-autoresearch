"""Bounded PI contexts on a launcher-owned persistent GitHub Copilot SDK runtime.

The launcher owns the research protocol and decides whether a phase is complete;
this adapter owns only the Copilot runtime: session identity, the tool profile,
the command policy, and what reaches the console. Nothing printed here is read
back as a scientific fact.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import asyncio
import difflib
import json
import re
import shutil
from runner.stop_control import stop_request_path
from runner.stop_control import stop_requested
import subprocess
import sys
import time
import uuid
from runner.stop_control import wait_for_stop_request
from runner.coding_contracts import (
    CODING_INSTRUCTIONS,
    CODING_TOOLS,
    CodingCheck,
    CodingReport,
    MAIN_PI_TOOLS,
    OperationSubmissionParams,
    RESEARCH_TOOLS,
    REVIEW_INSTRUCTIONS,
    REVIEW_MODEL,
    REVIEW_REASONING,
    REVIEW_TOOLS,
    ReviewReport,
    ScientificCodingParams,
    normalize_model,
)
from runner.command_policy import (
    DEPENDENCY_DENIAL as DEPENDENCY_DENIAL,
    EXECUTION_DENIAL as EXECUTION_DENIAL,
    GIT_DENIAL as GIT_DENIAL,
    SUITE_DENIAL as SUITE_DENIAL,
    command_denial,
    execution_target as execution_target,
    shell_command_text,
)
from runner.copilot_console import (
    CodingConsole,
    Console,
    record_usage,
)
from runner.path_policy import (
    CODING_PERMISSION_DENIAL,
    CODING_SCOPE_DENIAL,
    FILE_EDIT_DENIAL as FILE_EDIT_DENIAL,
    FILE_READ_DENIAL,
    MAIN_WRITE_DENIAL,
    _repository_relative_target,
    coding_file_scope,
    file_edit_denial as file_edit_denial,
    file_read_denial,
    scoped_edit_denial,
)


ROOT = Path(__file__).resolve().parent.parent


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


SHELL_DENIAL = "Shell tools are unavailable in this session; Runner executes checks."


# Oversized tool results are written here instead of occupying the context for
# the rest of the session. The PI still opens them on demand. The
# threshold is held above the campaign artifacts (the brief, postmortems and
# evaluation panels), so primary scientific evidence is never offloaded out of
# the session by default.
LARGE_OUTPUT_DIR = ROOT / ".copilot" / "large-output"


LARGE_OUTPUT_MAX_BYTES = 262_144


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
        self.original_requests: dict[str, dict] = {}
        self.review_handles: set[str] = set()
        self.reviewers: dict[str, str] = {}
        self.review_reports: dict[str, ReviewReport] = {}
        self.active_agent = "scientific-coder"
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
        self.child_models: set[str] = set()
        self.child_reasoning: set[str] = set()
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

    def reviewer_agent(self) -> dict:
        return {
            "name": "scientific-reviewer",
            "display_name": "Scientific rubber duck",
            "description": "Read-only scientific source and verification reviewer.",
            "prompt": REVIEW_INSTRUCTIONS,
            "tools": REVIEW_TOOLS,
            "model": REVIEW_MODEL,
            "reasoning_effort": REVIEW_REASONING,
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
                "An independent reviewer examines the initial delivery. "
                "It requests batched engineering repairs from the same coder, "
                "then checks the repair and affected regressions. "
                "You receive the final source, classified findings, repair history "
                "and proposed check, or a needs_pi reason. "
                "Scientific choices remain yours. Only Runner executes checks.\n\n"
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
            AssistantTurnStartData, AssistantUsageData,
            PermissionRequestedData,
            SubagentCompletedData, SubagentFailedData, SubagentStartedData,
        )

        data = event.data
        handle = getattr(event, "agent_id", None)
        if isinstance(data, SubagentStartedData) and self.busy:
            if data.agent_name == self.active_agent and self.active_handle is None:
                self.active_handle = handle or data.tool_call_id
        if isinstance(data, PermissionRequestedData) and not data.resolved_by_hook:
            # SDK dispatches this event before its callback, using the same request object.
            self.permission_requests[id(data.permission_request)] = (
                data.permission_request, handle,
                self.binding if self.busy and handle == self.active_handle else None,
            )
        if handle is None or handle != self.active_handle or not self.busy:
            return
        if self.child_events is not None:
            self.child_events(event)
        if isinstance(data, (AssistantTurnStartData, AssistantUsageData)):
            model = getattr(data, "model", None)
            if model:
                self.child_models.add(normalize_model(model))
            reasoning = getattr(data, "reasoning_effort", None)
            if reasoning:
                self.child_reasoning.add(reasoning)
        if isinstance(data, (SubagentCompletedData, SubagentFailedData)):
            self.native_accounting = {
                "agent_id": handle,
                "scope": "native_task_lifetime",
                "model": getattr(data, "model", None),
                "duration_seconds": data.duration.total_seconds() if data.duration else None,
                "total_tokens": data.total_tokens,
                "total_tool_calls": data.total_tool_calls,
            }
            model = getattr(data, "model", None)
            if model:
                self.child_models.add(normalize_model(model))
            self.child_error = getattr(data, "error", None)
            if getattr(data, "cancelled", False):
                self.child_error = f"Native {self.active_agent} task was cancelled."
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
                if (
                    self.active_agent == "scientific-reviewer"
                    and request.get("toolName") not in REVIEW_TOOLS
                ):
                    return {
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "The scientific reviewer is read-only.",
                    }
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
            or request.get("agentName") != self.active_agent
            or not self.busy or self.binding is None
        ):
            return {"additionalContext": "Unauthorized child: all tools are denied. Stop."}
        if self.active_agent == "scientific-reviewer":
            return {
                "additionalContext": (
                    "Installed APIs: native MuJoCo 3.12.0, Gymnasium 1.3.0, "
                    "Stable-Baselines3 2.9.0. Dependencies are fixed. "
                    "Review only the supplied change and exact readable files. "
                    "All writes, execution, delegation and operations are denied. "
                    "Do not trust coder-authored expectations without checking them. "
                    "Request complete engineering repair batches through your handoff. "
                    "Return scientific choices or blocked requirements to the PI. "
                    "No review certifies science.\n"
                    + json.dumps(self.binding, ensure_ascii=False)
                )
            }
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
            if self.active_agent == "scientific-reviewer":
                ReviewReport.model_validate_json(self.stop_response)
            else:
                self.report(self.stop_response)
        except (ValueError, OSError) as error:
            if self.stop_challenges < 2:
                self.stop_challenges += 1
                return {
                    "decision": "block",
                    "reason": (
                        "Engineering handoff is incomplete: " + str(error)
                        + ". Return the exact JSON handoff contract. "
                        "Do not execute checks, broaden scope, make a scientific "
                        "judgment, or select a research direction."
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

    async def run_child(
        self, *, agent: str, prompt: str, binding: dict, result: dict,
        handle: str | None = None,
    ) -> CodingReport | ReviewReport | None:
        from copilot.generated.rpc import TasksSendMessageRequest, TasksStartAgentRequest

        started = time.monotonic()
        child_console = CodingConsole()
        self.child_console = child_console
        self.child_events, _ = build_handlers(
            child_console, asyncio.Event(), child_accounting=True
        )
        self.active_agent = agent
        self.active_handle = handle
        self.binding = binding
        self.permission_requests.clear()
        self.completed.clear()
        self.stop_response = ""
        self.stop_challenges = 0
        self.child_error = None
        self.native_accounting = {}
        self.child_models = set()
        self.child_reasoning = set()
        self.quiescent = False
        report = None
        exit_code = EXIT_RUNTIME_FAILURE
        cancelled = False
        try:
            if handle:
                sent = await self.session.rpc.tasks.send_message(
                    TasksSendMessageRequest(id=handle, message=prompt)
                )
                if not sent.sent:
                    raise ValueError(sent.error or "Native same-child correction was not delivered.")
            else:
                child = await self.session.rpc.tasks.start_agent(TasksStartAgentRequest(
                    agent_type=agent, name=agent,
                    description=(
                        "Independent source and verification review"
                        if agent == "scientific-reviewer"
                        else "Scoped source and verification authoring"
                    ),
                    prompt=prompt,
                ))
                if self.active_handle not in (None, child.agent_id):
                    raise ValueError("Native child identity changed during dispatch.")
                self.active_handle = child.agent_id
            if agent == "scientific-reviewer":
                self.review_handles.add(self.active_handle)
            else:
                self.bindings[self.active_handle] = binding
                if handle is None:
                    self.original_requests[self.active_handle] = json.loads(prompt)
            await asyncio.wait_for(self.wait_child_idle(), self.args.timeout)
            if self.child_error or child_console.session_error:
                raise RuntimeError(self.child_error or child_console.session_error)
            if agent == "scientific-reviewer":
                if (
                    self.child_models != {REVIEW_MODEL}
                    or self.child_reasoning != {REVIEW_REASONING}
                ):
                    raise ValueError(
                        f"Requested reviewer {REVIEW_MODEL!r}/{REVIEW_REASONING!r} "
                        f"was not verified; reported models: {sorted(self.child_models)}, "
                        f"reasoning: {sorted(self.child_reasoning)}."
                    )
                report = ReviewReport.model_validate_json(self.stop_response)
                result.update(report.model_dump())
            else:
                report = self.report(self.stop_response)
            result["status"] = "completed"
            exit_code = EXIT_OK
        except asyncio.CancelledError:
            cancelled = True
            result.update(
                status="cancelled",
                error=f"{agent} cancelled; source and review require PI inspection.",
            )
            exit_code = EXIT_INTERRUPTED
        except TimeoutError:
            result.update(
                status="timeout",
                error=f"{agent} timed out; source and review require PI inspection.",
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
                        self.quiescent = True
                        break
                    except asyncio.CancelledError:
                        cancelled = True
                        result.update(
                            status="cancelled",
                            error=f"{agent} cancelled; source and review require PI inspection.",
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
            result["actual_models"] = sorted(self.child_models)
            result["actual_reasoning_efforts"] = sorted(self.child_reasoning)
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
                usage_args = self.args
                if agent == "scientific-reviewer":
                    usage_args = argparse.Namespace(**{
                        **vars(self.args), "model": REVIEW_MODEL, "reasoning": REVIEW_REASONING,
                    })
                record_usage(
                    usage_args, child_console, elapsed, exit_code,
                    role=agent.replace("-", "_"), session_id=handle,
                    parent_session_id=self.args.session_id,
                    actual_models=sorted(self.child_models),
                    actual_reasoning_efforts=sorted(self.child_reasoning),
                )
            except (OSError, ValueError) as error:
                result["usage_error"] = str(error)
                self.console.line(f"  ! {agent} usage could not be recorded: {error}")
        if cancelled:
            raise asyncio.CancelledError
        return report if result["status"] == "completed" else None

    async def invoke(self, params: ScientificCodingParams, invocation) -> str:
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
                review_handle = self.reviewers.get(params.session_handle)
                if review_handle is not None:
                    reviewer = next((item for item in tasks.tasks if item.id == review_handle), None)
                    if reviewer is None or reviewer.status.value != "idle":
                        raise ValueError(
                            "The stored reviewer is not idle in this bounded context; "
                            "a correction cannot start a replacement review."
                        )
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
        cancelled = False
        result = {
            "status": "error",
            "verification_module": verification[:-3].replace("/", "."),
            "check_executed": False,
            "review_required": True,
            "repair_history": [],
            "unchecked_scope": ["No scientific check has been executed by this tool."],
        }
        pending_repair = None
        try:
            request = {
                "intent": params.intent, **binding, "source_context": params.source_context,
            }
            coding_handle = params.session_handle
            step_before = before
            attempted_findings: set[str] = set()
            while True:
                report = await self.run_child(
                    agent="scientific-coder", prompt=json.dumps(request, ensure_ascii=False),
                    binding=binding, result=result, handle=coding_handle,
                )
                if pending_repair is not None:
                    pending_repair["coder_status"] = result["status"]
                if not isinstance(report, CodingReport):
                    break
                if pending_repair is not None:
                    pending_repair["coder_summary"] = report.summary
                result.update({
                    "summary": report.summary,
                    "proposed_check": self.check_proposal(report, result["verification_module"]),
                    "proposed_compatibility_check": (
                        self.check_proposal(report.compatibility_check, result["verification_module"])
                        if report.compatibility_check is not None else None
                    ),
                    "check_description": report.check_description,
                    "unchecked_scope": [
                        "No scientific check has been executed by this tool.",
                        *report.unchecked_scope,
                    ],
                })
                result["changes"], result["diff"] = coding_changes(step_before)
                coder_handle = result["session_handle"]
                review_handle = self.reviewers.get(coder_handle)
                review_mode = "correction" if review_handle is not None else "initial"
                review = {
                    "status": "error", "mode": review_mode,
                    "coding_session_handle": coder_handle, "check_executed": False,
                }
                result["review"] = review
                self.console.line(
                    f"  > scientific_coding: {review_mode} review ({REVIEW_MODEL}, {REVIEW_REASONING})"
                )
                review_request = {
                    "mode": review_mode,
                    "coder_summary": report.summary,
                    "coder_unchecked_scope": report.unchecked_scope,
                    "changes": result["changes"],
                    "diff": result["diff"],
                    "verification_module": result["verification_module"],
                    "proposed_check": result["proposed_check"],
                    "proposed_compatibility_check": result["proposed_compatibility_check"],
                }
                if review_handle is None:
                    review_request["request"] = self.original_requests[coder_handle]
                else:
                    previous = self.review_reports.get(coder_handle)
                    review_request.update({
                        "correction_intent": request["intent"],
                        "correction_context": request["source_context"],
                        "correction_origin": "reviewer" if pending_repair is not None else "pi",
                        "requested_changes": (
                            pending_repair["requested_changes"] if pending_repair is not None else []
                        ),
                        "previous_review": previous.model_dump() if previous is not None else None,
                    })
                try:
                    review_report = await self.run_child(
                        agent="scientific-reviewer",
                        prompt=json.dumps(review_request, ensure_ascii=False),
                        binding={**binding, "allowed_paths": []},
                        result=review,
                        handle=review_handle,
                    )
                finally:
                    if self.active_handle is not None and self.active_handle in self.review_handles:
                        self.reviewers[coder_handle] = self.active_handle
                    if pending_repair is not None:
                        pending_repair["review_status"] = review["status"]
                if isinstance(review_report, ReviewReport):
                    self.review_reports[coder_handle] = review_report
                    if pending_repair is not None:
                        pending_repair["review_decision"] = review_report.decision
                        pending_repair["review_reason"] = review_report.decision_reason
                if not isinstance(review_report, ReviewReport) or review["status"] != "completed":
                    result.update(
                        status="error",
                        error=f"Independent review did not complete: {review.get('error', review['status'])}",
                    )
                    break
                if review_report.decision == "ready_for_pi":
                    break
                if review_report.decision == "needs_pi":
                    result.update(status="needs_pi", reason=review_report.decision_reason)
                    break

                requested_ids = {change.finding_id for change in review_report.requested_changes}
                repeated = requested_ids & attempted_findings
                if repeated:
                    result.update(
                        status="needs_pi",
                        reason=f"Automatic repair request repeated finding IDs: {sorted(repeated)}.",
                    )
                    break
                if pending_repair is not None and not result["changes"]:
                    result.update(
                        status="needs_pi",
                        reason="The coder changed no source and the reviewer still requests repairs.",
                    )
                    break
                for change in review_report.requested_changes:
                    selected = coding_file_scope(change.paths, writable=True)
                    outside = selected - paths
                    if outside:
                        raise ValueError(
                            f"Reviewer repair requests files outside the coding scope: {sorted(outside)}."
                        )
                attempted_findings.update(requested_ids)
                pending_repair = {
                    "requested_changes": [
                        change.model_dump() for change in review_report.requested_changes
                    ],
                    "confirmed_findings": [
                        finding.model_dump() for finding in review_report.findings
                        if finding.category == "confirmed_defect"
                    ],
                    "decision_reason": review_report.decision_reason,
                    "coder_status": "pending",
                    "review_status": "pending",
                }
                result["repair_history"].append(pending_repair)
                request = {
                    "intent": (
                        "Resolve the complete engineering repair batch in source_context. "
                        "Preserve the original PI intent and behavior outside that batch. "
                        "Report any conflict with the contracts or installed APIs."
                    ),
                    **binding,
                    "source_context": json.dumps({
                        "requested_changes": pending_repair["requested_changes"],
                        "confirmed_findings": pending_repair["confirmed_findings"],
                        "decision_reason": review_report.decision_reason,
                    }, ensure_ascii=False),
                }
                coding_handle = coder_handle
                step_before = coding_snapshot(paths)
                result["review"] = {
                    "status": "pending", "mode": "correction",
                    "coding_session_handle": coder_handle, "check_executed": False,
                }
        except asyncio.CancelledError:
            cancelled = True
            result.update(status="cancelled", error="Coding/review cancelled; partial changes require PI review.")
        except (OSError, ValueError) as error:
            result.update(status="error", error=f"{type(error).__name__}: {error}")
        finally:
            if pending_repair is not None and pending_repair["coder_status"] == "pending":
                pending_repair["coder_status"] = result["status"]
            self.active_tasks.discard(task)
            self.busy = self.cancellation_unconfirmed

        try:
            result["changes"], result["diff"] = coding_changes(before)
        except OSError as error:
            result.update(status="error", review_error=str(error), changes=[], diff="")
            result["unchecked_scope"].append("Actual change review could not be collected.")
        handle = result.get("session_handle")
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
        for handle in (
            set(self.bindings) | self.review_handles
            | ({self.active_handle} if self.active_handle else set())
        ):
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
            raise ValueError("Only the active main PI or its authorized scientific child may read APIs.")
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
            "retrieval. Main PI and its exact-scope coding/review children can use this reader. "
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
        "custom_agents": [coding.agent(), coding.reviewer_agent()] if coding is not None else [],
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
