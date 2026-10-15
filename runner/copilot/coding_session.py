"""Native coding supervision, authorization and event handlers."""

from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import time
import uuid

from runner.copilot.coding_contracts import (
    CODING_INSTRUCTIONS,
    CODING_TOOLS,
    MAIN_PI_TOOLS,
    RESEARCH_TOOLS,
    REVIEW_INSTRUCTIONS,
    REVIEW_MODEL,
    REVIEW_REASONING,
    REVIEW_TOOLS,
    CodingReport,
    ReviewReport,
    ScientificCodingParams,
    normalize_model,
)
from runner.copilot.command_policy import (
    command_denial,
    shell_command_text,
)
from runner.copilot.copilot_console import (
    CodingConsole,
    Console,
    record_usage,
)
from runner.copilot.path_policy import (
    CODING_PERMISSION_DENIAL,
    CODING_SCOPE_DENIAL,
    FILE_READ_DENIAL,
    MAIN_WRITE_DENIAL,
    ROOT,
    _repository_relative_target,
    coding_file_scope,
    file_read_denial,
    scoped_edit_denial,
)

EXIT_OK = 0


EXIT_SESSION_ERROR = 2


EXIT_TIMEOUT = 5


EXIT_RUNTIME_FAILURE = 6


EXIT_INTERRUPTED = 130


SHUTDOWN_TIMEOUT_SECONDS = 30.0


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
            else [
                *(RESEARCH_TOOLS if preliminary else MAIN_PI_TOOLS),
                "artifact_evidence_query",
                "training_log_query",
                "scientific_coding",
                "scientific_api_reference",
                "submit_operation",
            ]
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
                "input_tokens",
                "cache_read_tokens",
                "cache_write_tokens",
                "output_tokens",
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
                console.denied(
                    CODING_PERMISSION_DENIAL, getattr(request, "tool_call_id", None)
                )
                return PermissionDecisionReject(feedback=CODING_PERMISSION_DENIAL)
        if isinstance(request, PermissionRequestRead):
            native_paths = (
                frozenset(scope["read_paths"]) if scope is not None else read_paths
            )
            reason = (
                CODING_SCOPE_DENIAL
                if (coding_paths is not None or scope is not None)
                and _repository_relative_target(request.path) not in native_paths
                else file_read_denial(request.path, preliminary=preliminary)
            )
            if coding is not None and coding.busy and scope is None:
                reason = CODING_SCOPE_DENIAL
            if getattr(request, "resolved_path", None):
                reason = reason or file_read_denial(
                    request.resolved_path, preliminary=preliminary
                )
                if (
                    scope is not None
                    and _repository_relative_target(request.resolved_path)
                    not in native_paths
                ):
                    reason = CODING_SCOPE_DENIAL
            if reason:
                console.denied(reason, getattr(request, "tool_call_id", None))
                return PermissionDecisionReject(feedback=reason)
        elif isinstance(request, PermissionRequestWrite):
            reason = scoped_edit_denial(
                request.file_name,
                preliminary=preliminary,
                coding_paths=frozenset(scope["allowed_paths"])
                if scope is not None
                else coding_paths,
            )
            if getattr(request, "resolved_path", None):
                reason = reason or scoped_edit_denial(
                    request.resolved_path,
                    preliminary=preliminary,
                    coding_paths=frozenset(scope["allowed_paths"])
                    if scope
                    else coding_paths,
                )
            for edit in getattr(request, "file_edits", None) or []:
                for content in (edit.before, edit.after):
                    if content is not None:
                        reason = reason or scoped_edit_denial(
                            content.path,
                            preliminary=preliminary,
                            coding_paths=frozenset(scope["allowed_paths"])
                            if scope
                            else coding_paths,
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
                "created"
                if previous is None
                else "deleted"
                if current is None
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
            old_lines,
            new_lines,
            fromfile=f"before/{path}",
            tofile=f"after/{path}",
        ):
            diffs.append(
                line
                if line.endswith("\n")
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
            "description": "Bounded scientific source author.",
            "prompt": CODING_INSTRUCTIONS,
            "tools": CODING_TOOLS,
            "infer": False,
            "mcp_servers": {},
        }

    def reviewer_agent(self) -> dict:
        return {
            "name": "scientific-reviewer",
            "display_name": "Scientific rubber duck",
            "description": "Read-only implementation and logic reviewer.",
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
                "In intent, state the expected output precisely. "
                "The coder chooses how to implement it, not what the output means.\n\n"
                "Select exact writable files in allowed_paths and additional "
                "readable source and caller files in read_paths.\n\n"
                "Put supporting facts, caller context and observed errors "
                "in source_context. The child "
                "does not receive your conversation. The harness supplies current "
                "scenario, authority and operation-contract text to both authors "
                "and reviewers, without expanding their file permissions.\n\n"
                "An independent reviewer examines the initial delivery. "
                "A failed review goes unchanged to the same coder. "
                "The same reviewer checks the correction. "
                "You receive the final source, review, repair history "
                "or a needs_pi reason. No verification module or executable check "
                "proposal is required. Scientific choices and operation requests "
                "remain yours. Only Runner executes scientific operations.\n\n"
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
            or self.closed
            or self.busy
            or (
                self.operations is not None
                and (self.operations.busy or self.operations.closed)
            )
        ):
            raise ValueError("Only the active, unlocked main PI may use this tool.")

    def on_event(self, event) -> None:
        from copilot.session_events import (
            AssistantTurnStartData,
            AssistantUsageData,
            PermissionRequestedData,
            SubagentCompletedData,
            SubagentFailedData,
            SubagentStartedData,
        )

        data = event.data
        handle = getattr(event, "agent_id", None)
        if isinstance(data, SubagentStartedData) and self.busy:
            if data.agent_name == self.active_agent and self.active_handle is None:
                self.active_handle = handle or data.tool_call_id
        if isinstance(data, PermissionRequestedData) and not data.resolved_by_hook:
            # SDK dispatches this event before its callback, using the same request object.
            self.permission_requests[id(data.permission_request)] = (
                data.permission_request,
                handle,
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
                "duration_seconds": data.duration.total_seconds()
                if data.duration
                else None,
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
            return {
                "permissionDecision": "deny",
                "permissionDecisionReason": CODING_SCOPE_DENIAL,
            }

    def permission_scope(self, request, invocation) -> dict | None:
        record = self.permission_requests.pop(id(request), None)
        if (
            record is None
            or record[0] is not request
            or self.closed
            or not isinstance(invocation, dict)
            or invocation.get("session_id") != self.args.session_id
        ):
            raise ValueError(CODING_PERMISSION_DENIAL)
        _, handle, binding = record
        if handle is None and not self.busy:
            return None
        if (
            self.busy
            and self.binding is not None
            and handle is not None
            and handle == self.active_handle
            and binding is self.binding
        ):
            return self.binding
        raise ValueError(CODING_PERMISSION_DENIAL)

    def start_hook(self, request, invocation):
        if (
            invocation.get("session_id") != self.args.session_id
            or request.get("agentName") != self.active_agent
            or not self.busy
            or self.binding is None
        ):
            return {
                "additionalContext": "Unauthorized child: all tools are denied. Stop."
            }
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
                "not permission to edit the harness. Author only the requested "
                "scoped source; execute nothing. Read the supplied task_context "
                "and relevant authorized source and callers before editing. "
                "Use scientific_api_reference for unfamiliar installed APIs. "
                "Do not add mandatory check modules or execution proposals. "
                "The reviewer checks implementation errors and logic. "
                "The parent PI must review actual diffs. "
                "No engineering handoff certifies science or Runner acceptance.\n"
                + json.dumps(self.binding, ensure_ascii=False)
            )
        }

    def report(self, response: str) -> CodingReport:
        return CodingReport.model_validate_json(response)

    def task_context(self) -> dict[str, str]:
        authority = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        instruments = (ROOT / "contracts" / "instruments.md").read_text(
            encoding="utf-8"
        )

        def excerpt(text: str, start: str, end: str) -> str:
            _, found, tail = text.partition(start)
            if not found:
                raise ValueError(f"Required coding-context section is missing: {start}")
            selected, found, _ = tail.partition(end)
            if not found:
                raise ValueError(f"Required coding-context boundary is missing: {end}")
            return start + selected

        return {
            "authority": excerpt(authority, "## Environment", "## Layout"),
            "scenario": (ROOT / "contracts" / "scenario.md").read_text(
                encoding="utf-8"
            ),
            "operation_envelope": excerpt(
                instruments,
                "## Operation request envelope",
                "## Scientific coding interface",
            ),
            "python_module": excerpt(
                instruments, "A `python_module` entry", "A paired-comparison entry"
            ),
        }

    def stop_hook(self, request, invocation):
        if (
            invocation.get("session_id") != self.args.session_id
            or request.get("agentId") != self.active_handle
            or not self.busy
            or self.closed
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
                        "Engineering handoff is incomplete: "
                        + str(error)
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
            child = next(
                (item for item in tasks.tasks if item.id == self.active_handle), None
            )
            if child is None:
                raise ValueError("Native coding child disappeared before its handoff.")
            if child.status.value in {"idle", "completed", "failed", "cancelled"}:
                self.quiescent = True
                if child.status.value in {"failed", "cancelled"}:
                    raise ValueError(
                        child.error or f"Native child is {child.status.value}."
                    )
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
            include={"allowed_paths", "read_paths"},
            exclude_none=True,
        )
        scope = {**(previous or {}), **supplied}
        if "allowed_paths" not in scope:
            raise ValueError("A new coding call requires allowed_paths.")
        paths = coding_file_scope(scope["allowed_paths"], writable=True)
        reads = paths | coding_file_scope(scope.get("read_paths", []), writable=False)
        binding = {
            "allowed_paths": sorted(paths),
            "read_paths": sorted(reads),
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
        self,
        *,
        agent: str,
        prompt: str,
        binding: dict,
        result: dict,
        handle: str | None = None,
    ) -> CodingReport | ReviewReport | None:
        from copilot.generated.rpc import (
            TasksSendMessageRequest,
            TasksStartAgentRequest,
        )

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
                    raise ValueError(
                        sent.error or "Native same-child correction was not delivered."
                    )
            else:
                child = await self.session.rpc.tasks.start_agent(
                    TasksStartAgentRequest(
                        agent_type=agent,
                        name=agent,
                        description=(
                            "Independent implementation and logic review"
                            if agent == "scientific-reviewer"
                            else "Scoped source authoring"
                        ),
                        prompt=prompt,
                    )
                )
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
                if self.child_models != {REVIEW_MODEL} or self.child_reasoning != {
                    REVIEW_REASONING
                }:
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
                            status="error",
                            cleanup_error=f"{type(error).__name__}: {error}",
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
                if "input_tokens" in child_console.reported_usage
                else None,
                "output_tokens": child_console.output_tokens
                if "output_tokens" in child_console.reported_usage
                else None,
                "cache_read_tokens": child_console.cache_read_tokens
                if "cache_read_tokens" in child_console.reported_usage
                else None,
                "cache_write_tokens": child_console.cache_write_tokens
                if "cache_write_tokens" in child_console.reported_usage
                else None,
                "aiu": child_console.nano_aiu / 1e9
                if "aiu" in child_console.reported_usage
                else None,
                "tool_calls": child_console.tool_calls,
            }
            try:
                usage_args = self.args
                if agent == "scientific-reviewer":
                    usage_args = argparse.Namespace(
                        **{
                            **vars(self.args),
                            "model": REVIEW_MODEL,
                            "reasoning": REVIEW_REASONING,
                        }
                    )
                record_usage(
                    usage_args,
                    child_console,
                    elapsed,
                    exit_code,
                    role=agent.replace("-", "_"),
                    session_id=handle,
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
        if (
            self.closed
            or self.busy
            or (
                self.operations is not None
                and (self.operations.busy or self.operations.closed)
            )
        ):
            return json.dumps(
                {"status": "error", "error": "Coding is closed or already active."}
            )
        try:
            self.authorize_parent(invocation)
            if self.session is None or not invocation.tool_call_id:
                raise ValueError("Native coding requires the bound parent SDK session.")
            await self.session.rpc.tools.initialize_and_validate()
            if self.args.preliminary:
                raise ValueError(
                    "Coding is unavailable during preliminary publication."
                )
            if not self.args.campaign_id:
                raise ValueError("Coding requires an explicit campaign identity.")
            uuid.UUID(self.args.campaign_id)
            binding = self.resolve_binding(params)
            paths = frozenset(binding["allowed_paths"])
            context = (
                self.original_requests[params.session_handle]["task_context"]
                if params.session_handle
                else self.task_context()
            )
            if params.session_handle:
                tasks = await self.session.rpc.tasks.list()
                child = next(
                    (item for item in tasks.tasks if item.id == params.session_handle),
                    None,
                )
                if child is None or child.status.value != "idle":
                    raise ValueError(
                        "Only this context's idle native child accepts corrections."
                    )
                review_handle = self.reviewers.get(params.session_handle)
                if review_handle is not None:
                    reviewer = next(
                        (item for item in tasks.tasks if item.id == review_handle), None
                    )
                    if reviewer is None or reviewer.status.value != "idle":
                        raise ValueError(
                            "The stored reviewer is not idle in this bounded context; "
                            "a correction cannot start a replacement review."
                        )
            before = coding_snapshot(paths)
        except (OSError, ValueError) as error:
            self.console.line(f"  > scientific_coding: rejected; {error}")
            return json.dumps({"status": "error", "error": str(error)})

        if (
            self.closed
            or self.busy
            or (
                self.operations is not None
                and (self.operations.busy or self.operations.closed)
            )
        ):
            return json.dumps(
                {
                    "status": "error",
                    "error": "Coding/Runner lock changed during validation.",
                }
            )
        self.busy = True
        task = asyncio.current_task()
        self.active_tasks.add(task)
        cancelled = False
        result = {
            "status": "error",
            "review_required": True,
            "repair_history": [],
            "unchecked_scope": ["No scientific check has been executed by this tool."],
        }
        pending_repair = None
        try:
            request = {
                "intent": params.intent,
                **binding,
                "source_context": params.source_context,
                "task_context": context,
            }
            coding_handle = params.session_handle
            step_before = before
            while True:
                report = await self.run_child(
                    agent="scientific-coder",
                    prompt=json.dumps(request, ensure_ascii=False),
                    binding=binding,
                    result=result,
                    handle=coding_handle,
                )
                if pending_repair is not None:
                    pending_repair["coder_status"] = result["status"]
                if not isinstance(report, CodingReport):
                    break
                if pending_repair is not None:
                    pending_repair["coder_summary"] = report.summary
                result.update(
                    {
                        "summary": report.summary,
                        "unchecked_scope": [
                            "No scientific check has been executed by this tool.",
                            *report.unchecked_scope,
                        ],
                    }
                )
                result["changes"], result["diff"] = coding_changes(step_before)
                coder_handle = result["session_handle"]
                review_handle = self.reviewers.get(coder_handle)
                review_mode = "correction" if review_handle is not None else "initial"
                review = {
                    "status": "error",
                    "mode": review_mode,
                    "coding_session_handle": coder_handle,
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
                }
                if review_handle is None:
                    review_request["request"] = self.original_requests[coder_handle]
                else:
                    previous = self.review_reports.get(coder_handle)
                    review_request.update(
                        {
                            "previous_review": previous.model_dump()
                            if previous is not None
                            else None,
                        }
                    )
                    if pending_repair is None:
                        review_request["correction_intent"] = request["intent"]
                        review_request["correction_context"] = request["source_context"]
                try:
                    review_report = await self.run_child(
                        agent="scientific-reviewer",
                        prompt=json.dumps(review_request, ensure_ascii=False),
                        binding={**binding, "allowed_paths": []},
                        result=review,
                        handle=review_handle,
                    )
                finally:
                    if (
                        self.active_handle is not None
                        and self.active_handle in self.review_handles
                    ):
                        self.reviewers[coder_handle] = self.active_handle
                    if pending_repair is not None:
                        pending_repair["review_status"] = review["status"]
                if isinstance(review_report, ReviewReport):
                    self.review_reports[coder_handle] = review_report
                    if pending_repair is not None:
                        pending_repair["follow_up_review"] = review_report.model_dump()
                if (
                    not isinstance(review_report, ReviewReport)
                    or review["status"] != "completed"
                ):
                    result.update(
                        status="error",
                        error=f"Independent review did not complete: {review.get('error', review['status'])}",
                    )
                    break
                if review_report.validation:
                    break

                if pending_repair is not None and not result["changes"]:
                    result.update(
                        status="needs_pi",
                        reason="The coder changed no source and review validation still failed.",
                    )
                    break
                pending_repair = {
                    "review": review_report.model_dump(),
                    "coder_status": "pending",
                    "review_status": "pending",
                }
                result["repair_history"].append(pending_repair)
                request = {
                    "intent": (
                        "Correct the problems described by the reviewer in source_context. "
                        "Preserve the PI's requested output and authorized file scope. "
                        "Report unclear requirements instead of guessing."
                    ),
                    "source_context": json.dumps(
                        review_report.model_dump(), ensure_ascii=False
                    ),
                }
                coding_handle = coder_handle
                step_before = coding_snapshot(paths)
                result["review"] = {
                    "status": "pending",
                    "mode": "correction",
                    "coding_session_handle": coder_handle,
                }
        except asyncio.CancelledError:
            cancelled = True
            result.update(
                status="cancelled",
                error="Coding/review cancelled; partial changes require PI review.",
            )
        except (OSError, ValueError) as error:
            result.update(status="error", error=f"{type(error).__name__}: {error}")
        finally:
            if (
                pending_repair is not None
                and pending_repair["coder_status"] == "pending"
            ):
                pending_repair["coder_status"] = result["status"]
            self.active_tasks.discard(task)
            self.busy = self.cancellation_unconfirmed

        try:
            result["changes"], result["diff"] = coding_changes(before)
        except OSError as error:
            result.update(status="error", review_error=str(error), changes=[], diff="")
            result["unchecked_scope"].append(
                "Actual change review could not be collected."
            )
        handle = result.get("session_handle")
        encoded = json.dumps(result, ensure_ascii=False)
        if cancelled or len(encoded.encode("utf-8")) > LARGE_OUTPUT_MAX_BYTES:
            LARGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            output = LARGE_OUTPUT_DIR / f"coding-{handle}-{uuid.uuid4()}.json"
            output.write_text(encoded, encoding="utf-8")
            result.pop("diff", None)
            result["review_output_path"] = str(output)
            encoded = json.dumps(result, ensure_ascii=False)
        self.console.line(
            f"  > scientific_coding: {result['status']}; source review required"
        )
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
            set(self.bindings)
            | self.review_handles
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
                await self.session.rpc.cancel_all_background_agents(
                    timeout=SHUTDOWN_TIMEOUT_SECONDS
                )
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
                    child = next(
                        (item for item in tasks.tasks if item.id == handle), None
                    )
                    if child is None or child.status.value in {
                        "cancelled",
                        "completed",
                        "failed",
                    }:
                        return
                    await asyncio.sleep(0.05)
        except Exception:
            self.cancellation_unconfirmed = True
            self.closed = True
            if self.operations is not None:
                self.operations.closed = True
            raise
