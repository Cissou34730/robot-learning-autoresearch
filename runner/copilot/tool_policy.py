"""Pre-tool-use permission policy for the PI, the preliminary analyst and coding children."""

from __future__ import annotations

from runner import paths
from runner.copilot.coding_contracts import (
    CODING_TOOLS,
    MAIN_PI_TOOLS,
    RESEARCH_TOOLS,
)
from runner.copilot.command_policy import command_denial
from runner.copilot.path_policy import (
    CODING_SCOPE_DENIAL,
    FILE_READ_DENIAL,
    MAIN_WRITE_DENIAL,
    _repository_relative_target,
    file_read_denial,
    physical_target,
    read_target,
    reference_read_denial,
    scoped_edit_denial,
)

SHELL_DENIAL = "Shell tools are unavailable in this session; Runner executes checks."
RUNNER_LOCKED_DENIAL = "Runner is executing or this bounded session has ended."
PI_CUSTOM_TOOLS = (
    "artifact_evidence_query",
    "training_log_query",
    "training_series_statistics",
    "success_rate_pass_probability",
    "episode_outcome_breakdown",
    "scientific_coding",
    "scientific_api_reference",
    "submit_operation",
)
PATCH_HEADERS = (
    "*** Add File: ",
    "*** Update File: ",
    "*** Delete File: ",
    "*** Move to: ",
)


def deny(reason: str) -> dict:
    return {"permissionDecision": "deny", "permissionDecisionReason": reason}


def patch_targets(arguments: object) -> list[str]:
    patch = (
        arguments.get("input") or arguments.get("patch")
        if isinstance(arguments, dict)
        else arguments
    )
    if not isinstance(patch, str):
        return []
    return [
        line.split(": ", 1)[1]
        for line in patch.splitlines()
        if line.startswith(PATCH_HEADERS)
    ]


def _path_argument(arguments: object):
    return arguments.get("path") if isinstance(arguments, dict) else None


def _patch_denial(arguments, coding_paths, preliminary) -> str | None:
    targets = patch_targets(arguments)
    if not targets:
        return CODING_SCOPE_DENIAL if coding_paths is not None else MAIN_WRITE_DENIAL
    for target in targets:
        reason = scoped_edit_denial(
            target, coding_paths=coding_paths, preliminary=preliminary
        )
        if reason:
            return reason
    return None


def _child_view_denial(arguments, read_paths) -> str | None:
    target = _path_argument(arguments)
    if (
        not isinstance(target, str)
        or _repository_relative_target(target) not in read_paths
        or file_read_denial(target)
        or physical_target(target).is_dir()
    ):
        return CODING_SCOPE_DENIAL
    return None


def _view_denial(arguments, preliminary) -> str | None:
    target = _path_argument(arguments)
    if not isinstance(target, str):
        return FILE_READ_DENIAL
    reason = file_read_denial(target, preliminary=preliminary)
    if not reason and physical_target(target).is_dir():
        return "Use scoped glob for directory enumeration, not view."
    return reason or reference_read_denial(target, preliminary=preliminary)


def _allowed_tools(coding_paths, preliminary, json_editors) -> list[str]:
    if coding_paths is not None:
        return CODING_TOOLS
    allowed = [*(RESEARCH_TOOLS if preliminary else MAIN_PI_TOOLS), *PI_CUSTOM_TOOLS]
    if json_editors and preliminary:
        allowed += ["create", "edit"]
    return allowed


def tool_denial(
    name: str,
    arguments: object,
    *,
    coding_paths: frozenset[str] | None = None,
    read_paths: frozenset[str] = frozenset(),
    preliminary: bool = False,
    json_editors: bool = False,
) -> str | None:
    """Return why this call is denied, or None when it may run."""
    if name not in _allowed_tools(coding_paths, preliminary, json_editors):
        return CODING_SCOPE_DENIAL if coding_paths is not None else SHELL_DENIAL
    if name == "apply_patch":
        return _patch_denial(arguments, coding_paths, preliminary)
    if name in {"create", "edit"}:
        return scoped_edit_denial(
            _path_argument(arguments),
            coding_paths=coding_paths,
            preliminary=preliminary,
        )
    if name == "view":
        if coding_paths is not None:
            return _child_view_denial(arguments, read_paths)
        return _view_denial(arguments, preliminary)
    if preliminary and name == "powershell":
        command = arguments.get("command", "") if isinstance(arguments, dict) else ""
        return command_denial(command, preliminary=True)
    return None


def scoped_tool_hook(
    *,
    coding_paths: frozenset[str] | None = None,
    read_paths: frozenset[str] = frozenset(),
    operations=None,
    coding=None,
    preliminary: bool = False,
    read_alias: bool = False,
    json_editors: bool = False,
):
    """Check every tool call, including each patch target, before it runs."""

    def on_pre_tool_use(request, invocation):
        if coding is not None:
            return coding.pre_tool_use(request, invocation)
        name = request.get("toolName")
        if (
            operations is not None
            and operations.locked
            and not (
                name == "submit_operation"
                and getattr(operations, "awaiting_result", False)
            )
        ):
            return deny(RUNNER_LOCKED_DENIAL)
        if read_alias and name == "read":
            name = "view"
        arguments = request.get("toolArgs")
        if paths.SPLIT and name == "view" and isinstance(arguments, dict):
            target = arguments.get("path")
            if isinstance(target, str):
                try:
                    arguments = {**arguments, "path": str(read_target(target))}
                except ValueError:
                    return deny(FILE_READ_DENIAL)
        reason = tool_denial(
            name,
            arguments,
            coding_paths=coding_paths,
            read_paths=read_paths,
            preliminary=preliminary,
            json_editors=json_editors,
        )
        if reason:
            return deny(reason)
        if paths.SPLIT and name == "view" and isinstance(arguments, dict):
            return {
                "modifiedArgs": {
                    **arguments,
                    "path": str(physical_target(arguments["path"])),
                }
            }
        return None

    return on_pre_tool_use
