"""SDK session callbacks: console events, native permissions and model-call retries."""

from __future__ import annotations

import asyncio
import json

from runner.copilot.command_policy import command_denial, shell_command_text
from runner.copilot.constants import (
    MODEL_CALL_RETRY_DELAY_SECONDS,
    MODEL_CALL_RETRY_LIMIT,
)
from runner.copilot.copilot_console import RESULT_ISSUE_TOOLS, Console, result_issue
from runner.copilot.path_policy import (
    CODING_PERMISSION_DENIAL,
    CODING_SCOPE_DENIAL,
    _repository_relative_target,
    file_read_denial,
    scoped_edit_denial,
)
from runner.copilot.tool_policy import RUNNER_LOCKED_DENIAL, SHELL_DENIAL
from runner.stop_control import stop_requested


def event_handler(
    console: Console,
    finished: asyncio.Event,
    *,
    coding=None,
    child_accounting: bool = False,
):
    from copilot.session_events import (
        AssistantMessageData,
        AssistantMessageDeltaData,
        AssistantUsageData,
        SessionCompactionCompleteData,
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
        # Reasoning events are deliberately not shown: the console reports work done.
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
                console.tool_failed(
                    data.error, name, arguments, tool_call_id=data.tool_call_id
                )
            elif data.success and tool is not None and tool[0] in RESULT_ISSUE_TOOLS:
                content = getattr(data.result, "content", None)
                issue = result_issue(content)
                if issue:
                    console.tool_issue(tool[0], issue, tool_call_id=data.tool_call_id)
                else:
                    console.tool_result(
                        tool[0], content, tool_call_id=data.tool_call_id
                    )
            elif data.success:
                name = tool[0] if tool is not None else "tool"
                console.tool_completed(name, data.tool_call_id)
        elif isinstance(data, SessionWorkspaceFileChangedData):
            console.file_changed(data.operation, data.path)
        elif isinstance(data, AssistantUsageData):
            console.usage.add_assistant_usage(data)
            console.model_call(data.input_tokens)
        elif isinstance(data, SessionErrorData):
            console.error(data.message or "unknown session error")
        elif isinstance(data, SessionCompactionCompleteData):
            console.compaction(data)
        elif isinstance(data, SessionIdleData) and (coding is None or not coding.busy):
            finished.set()

    return on_event


def _read_denial(request, scope, coding, coding_paths, read_paths, preliminary):
    paths = frozenset(scope["read_paths"]) if scope is not None else read_paths
    scoped = coding_paths is not None or scope is not None
    if scoped and _repository_relative_target(request.path) not in paths:
        reason = CODING_SCOPE_DENIAL
    else:
        reason = file_read_denial(request.path, preliminary=preliminary)
    if coding is not None and coding.busy and scope is None:
        reason = CODING_SCOPE_DENIAL
    resolved = getattr(request, "resolved_path", None)
    if resolved:
        reason = reason or file_read_denial(resolved, preliminary=preliminary)
        if scope is not None and _repository_relative_target(resolved) not in paths:
            reason = CODING_SCOPE_DENIAL
    return reason


def _write_denial(request, scope, coding_paths, preliminary):
    paths = frozenset(scope["allowed_paths"]) if scope is not None else coding_paths
    targets = [request.file_name]
    resolved = getattr(request, "resolved_path", None)
    if resolved:
        targets.append(resolved)
    for edit in getattr(request, "file_edits", None) or []:
        targets += [
            content.path for content in (edit.before, edit.after) if content is not None
        ]
    for target in targets:
        reason = scoped_edit_denial(target, preliminary=preliminary, coding_paths=paths)
        if reason:
            return reason
    return None


def permission_handler(
    console: Console,
    *,
    preliminary: bool = False,
    coding_paths: frozenset[str] | None = None,
    read_paths: frozenset[str] = frozenset(),
    operations=None,
    coding=None,
):
    from copilot.rpc import PermissionDecisionApproveOnce, PermissionDecisionReject
    from copilot.session_events import (
        PermissionRequestRead,
        PermissionRequestShell,
        PermissionRequestWrite,
    )

    def reject(request, reason: str):
        console.denied(reason, getattr(request, "tool_call_id", None))
        return PermissionDecisionReject(feedback=reason)

    def on_permission_request(request, invocation):
        if operations is not None and operations.locked:
            return PermissionDecisionReject(feedback=RUNNER_LOCKED_DENIAL)
        scope = None
        if coding is not None:
            try:
                scope = coding.permission_scope(request, invocation)
            except ValueError:
                return reject(request, CODING_PERMISSION_DENIAL)
        reason = None
        if isinstance(request, PermissionRequestRead):
            reason = _read_denial(
                request, scope, coding, coding_paths, read_paths, preliminary
            )
        elif isinstance(request, PermissionRequestWrite):
            reason = _write_denial(request, scope, coding_paths, preliminary)
        elif isinstance(request, PermissionRequestShell):
            reason = (
                command_denial(shell_command_text(request), preliminary=True)
                if preliminary
                else SHELL_DENIAL
            )
        if reason:
            return reject(request, reason)
        return PermissionDecisionApproveOnce()

    return on_permission_request


def _is_retryable_websocket_error(request) -> bool:
    error = request.get("error")
    message = error.get("message") if isinstance(error, dict) else error
    if not isinstance(message, str):
        return False
    try:
        details = json.loads(message)
    except json.JSONDecodeError:
        return False
    return isinstance(details, dict) and (
        details.get("code") == "invalid_request_body"
        and details.get("type") == "websocket_error"
        and details.get("message") == "internal server error"
    )


class ModelCallRetry:
    """Retry the Copilot transient websocket failure a bounded number of times."""

    def __init__(self, session_id: str, console: Console, coding, operations) -> None:
        self.session_id = session_id
        self.console = console
        self.coding = coding
        self.operations = operations
        self.retries = 0

    def closed(self) -> bool:
        return (
            stop_requested()
            or (self.operations is not None and self.operations.closed)
            or (self.coding is not None and self.coding.closed)
        )

    def reset_after(self, event) -> None:
        from copilot.session_events import AssistantMessageData

        if (
            getattr(event, "agent_id", None) is None
            and isinstance(event.data, AssistantMessageData)
            and event.data.interaction_id is not None
        ):
            self.retries = 0

    async def on_error_occurred(self, request, invocation):
        if (
            invocation.get("session_id") != self.session_id
            or request.get("sessionId") != self.session_id
            or request.get("errorContext") != "model_call"
            or request.get("recoverable") is not True
            or self.closed()
            or not _is_retryable_websocket_error(request)
        ):
            return None
        if self.retries >= MODEL_CALL_RETRY_LIMIT:
            self.console.warning(
                "Copilot model request failed after five retries; stopping",
                code="model_retry_exhausted",
            )
            return {"errorHandling": "abort"}
        self.retries += 1
        self.console.warning(
            f"Copilot model request failed; retry "
            f"{self.retries}/{MODEL_CALL_RETRY_LIMIT} "
            f"in {MODEL_CALL_RETRY_DELAY_SECONDS:g}s",
            code="model_retry",
        )
        await asyncio.sleep(MODEL_CALL_RETRY_DELAY_SECONDS)
        if self.closed():
            return {"errorHandling": "abort"}
        return {"errorHandling": "retry", "retryCount": 1}
