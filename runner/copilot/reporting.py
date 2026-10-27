"""SDK session observations, accounting and shared display descriptions.

Facts go to the campaign's typed event feed; nothing is written to a console.
"""

from __future__ import annotations

import json
import ntpath
import re
import time
from pathlib import Path, PureWindowsPath

from runner import typed_events
from runner.copilot.path_policy import ROOT
from runner.copilot.usage import SessionUsage

UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


WINDOWS_PATH_PATTERN = re.compile(r"[A-Za-z]:[\\/](?:[^ \r\n:]+[\\/])*[^ \r\n:]+")


MAX_CONSOLE_POINTER_LENGTH = 96


# How often a growing PI message is published to the observation feed.
PI_PARTIAL_SECONDS = 1.0


CONTEXT_BAND_TOKENS = 50_000


# Reader results that completed as tool calls but did not return the evidence asked for.
RESULT_ISSUE_TOOLS = {
    "artifact_evidence_query",
    "training_log_query",
    "training_series_statistics",
    "success_rate_pass_probability",
    "episode_outcome_breakdown",
}
RESULT_ISSUE_STATUSES = {
    "artifact_budget_exhausted",
    "artifact_unavailable",
    "attempt_required",
    "budget_exhausted",
    "field_absent",
    "filter_field_absent",
    "fingerprint_mismatch",
    "invalid_request",
    "logs_unavailable",
    "metric_absent",
    "no_finite_values",
    "no_logs",
    "no_matching_rows",
    "parse_budget_exhausted",
    "query_failed",
    "traversal_budget_exhausted",
}


def result_issue(content: object) -> str | None:
    if not isinstance(content, str) or not content.lstrip().startswith("{"):
        return None
    try:
        result = json.loads(content)
    except ValueError:
        return None
    status = result.get("status") if isinstance(result, dict) else None
    if status not in RESULT_ISSUE_STATUSES:
        return None
    detail = result.get("error") or result.get("recovery") or ""
    detail = " ".join(str(detail).split())[:200]
    return f"{status}: {detail}" if detail else status


# Display roles of factual result lines.
GREEN = "success"
YELLOW = "warning"
RED = "error"


_SPECIAL_TOOLS = frozenset(
    (
        "artifact_evidence_query",
        "training_log_query",
        "training_series_statistics",
        "success_rate_pass_probability",
        "episode_outcome_breakdown",
        "scientific_api_reference",
        "scientific_coding",
        "submit_operation",
    )
)


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


def _artifact_query_detail(arguments: dict) -> str:
    action = arguments.get("action")
    pointers: list[str] = []
    if action == "discover":
        pointers.append(compact_json_pointer(str(arguments.get("prefix") or "/")))
    elif action == "batch":
        queries = arguments.get("queries")
        if isinstance(queries, list):
            rendered = [
                compact_artifact_query_spec(query)
                for query in queries
                if isinstance(query, dict)
                and isinstance(query.get("path"), str)
                and query["path"].startswith("/")
            ]
            pointers.extend(rendered[:3])
            if len(rendered) > 3:
                pointers.append(f"+{len(rendered) - 3} more")
    elif isinstance(arguments.get("path"), str):
        pointers.append(compact_artifact_query_spec(arguments))
    artifact = (
        f"artifact {arguments.get('artifact_index', 0)}"
        if action not in {"operations", "metadata"}
        else None
    )
    parts = [
        str(value)
        for value in (arguments.get("operation_id"), artifact, action)
        if isinstance(value, (str, int)) and str(value)
    ]
    if pointers:
        parts.append(", ".join(pointers))
    return " | ".join(parts)


def _training_log_detail(arguments: dict) -> str:
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
    return " | ".join(part for part in parts if part)


def _training_series_detail(arguments: dict) -> str:
    window = f"steps {arguments.get('from_step', 0)}..{arguments.get('to_step', 'end')}"
    parts = [
        str(arguments.get("operation_id", "-")),
        str(arguments.get("metric", "-")),
        window,
    ]
    if "attempt" in arguments:
        parts.append(f"attempt={arguments['attempt']}")
    if arguments.get("checks"):
        parts.append(f"checks={len(arguments['checks'])}")
    return " | ".join(parts)


def _api_reference_detail(arguments: dict) -> str:
    values = (
        arguments.get("library", "-"),
        arguments.get("symbol") or "library root",
        arguments.get("action", "definition"),
        arguments.get("contains"),
    )
    return " | ".join(str(value) for value in values if value)


def _powershell_detail(arguments: dict) -> str:
    values = (arguments.get("description"), f"cwd {ROOT}", arguments.get("command"))
    return " | ".join(
        str(value) for value in values if isinstance(value, str) and value
    )


def _search_detail(arguments: dict) -> str:
    pattern = arguments.get("pattern") or arguments.get("query")
    paths = arguments.get("paths") or arguments.get("path")
    if isinstance(paths, str):
        rendered = [full_console_path(paths)]
    elif isinstance(paths, list):
        rendered = [full_console_path(str(path)) for path in paths]
    else:
        rendered = [str(ROOT.resolve())]
    parts = [f"pattern {pattern}"] if pattern else []
    if rendered:
        parts.append("paths " + ", ".join(rendered))
    return " | ".join(parts)


_GENERIC_DETAIL_KEYS = (
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


def _generic_detail(arguments: dict) -> str:
    for key in _GENERIC_DETAIL_KEYS:
        raw = arguments.get(key)
        if isinstance(raw, (str, int)) and raw != "":
            if isinstance(raw, str) and key in {"path", "filePath", "file_path"}:
                return full_console_path(raw)
            return str(raw)
    return ""


def _patch_detail(arguments: object) -> str:
    patch = (
        arguments.get("input") or arguments.get("patch")
        if isinstance(arguments, dict)
        else arguments
    )
    if not isinstance(patch, str):
        return ""
    # Show only file headers, never the potentially large patch body.
    prefixes = (
        "*** Update File: ",
        "*** Add File: ",
        "*** Delete File: ",
        "*** Move to: ",
    )
    return ", ".join(
        full_console_path(line.split(": ", 1)[1])
        for line in patch.splitlines()
        if line.startswith(prefixes)
    )


_TOOL_DETAIL = {
    "artifact_evidence_query": _artifact_query_detail,
    "training_log_query": _training_log_detail,
    "training_series_statistics": _training_series_detail,
    "success_rate_pass_probability": lambda arguments: (
        f"target {(arguments.get('target') or {}).get('successes', '-')}/"
        f"{(arguments.get('target') or {}).get('trials', '-')} | "
        f"evidence={len(arguments.get('evidence') or [])} | "
        f"confidence={arguments.get('confidence', '-')}"
    ),
    "episode_outcome_breakdown": lambda arguments: (
        " vs ".join(
            f"{item.get('operation_id', '-')} {item.get('candidate', '-')}"
            for item in arguments.get("measurements") or []
        )
        + (
            f" | strata {(arguments.get('strata') or {}).get('field', '-')}"
            if arguments.get("strata")
            else ""
        )
    ),
    "scientific_coding": lambda _: "bounded coding / PI source review required",
    "scientific_api_reference": _api_reference_detail,
    "powershell": _powershell_detail,
    "rg": _search_detail,
    "glob": _search_detail,
}


def tool_detail(name: str, arguments: object) -> str:
    if name == "apply_patch":
        detail = _patch_detail(arguments)
    elif isinstance(arguments, dict):
        detail = _TOOL_DETAIL.get(name, _generic_detail)(arguments)
    else:
        detail = ""
    return " ".join(detail.split())


def tool_color_role(name: str) -> str:
    """Share tool-name emphasis without exposing terminal escape sequences."""
    return "special_tool" if name in _SPECIAL_TOOLS else "tool"


def tool_result_lines(name: str, result: object) -> list[tuple[str, str | None]]:
    """Factual result lines with their display role."""
    if not isinstance(result, dict) or result.get("status") != "computed":
        return []
    lines: list[tuple[str, str | None]] = []
    if name == "success_rate_pass_probability":
        for item in result.get("evidence", []):
            chance = item.get("pass_probability", 0.0)
            bounds = item.get("pass_probability_at_interval_bounds") or {}
            color = GREEN if chance >= 0.8 else YELLOW if chance >= 0.5 else RED
            lines.append(
                (
                    (
                        f"  = {str(item.get('label'))[:70]}: {item.get('successes')}/"
                        f"{item.get('trials')} -> pass {chance:.1%} "
                        f"(at interval bounds {bounds.get('lower', 0.0):.1%}-"
                        f"{bounds.get('upper', 0.0):.1%}; "
                        f"{item.get('interval_vs_target_rate')} target rate)"
                    ),
                    color,
                )
            )
    elif name == "episode_outcome_breakdown":
        for item in result.get("measurements", []):
            lines.append(
                (
                    (
                        f"  = {item.get('operation_id')} {item.get('candidate')}: "
                        f"{item.get('successes')}/{item.get('trials')}"
                    ),
                    None,
                )
            )
        paired = result.get("paired")
        if paired:
            lines.append(
                (
                    (
                        f"  = paired: first only {paired.get('first_only_success')} | "
                        f"second only {paired.get('second_only_success')} | "
                        f"sign test p {paired.get('sign_test_p_value', 1.0):.3g}"
                    ),
                    None,
                )
            )
    elif name == "training_series_statistics":
        window = result.get("window") or {}
        lines.append(
            (
                (
                    f"  = {result.get('metric')}: {window.get('rows')} rows | "
                    f"min {window.get('min', {}).get('value')} | "
                    f"max {window.get('max', {}).get('value')} | "
                    f"last {window.get('last', {}).get('value')}"
                ),
                None,
            )
        )
        for check in result.get("checks", []):
            verdict = "holds" if check.get("holds") else "fails"
            lines.append(
                (
                    (
                        f"  = check {check.get('statistic')} {check.get('comparison')} "
                        f"{check.get('threshold')}: {verdict} (value {check.get('value')})"
                    ),
                    GREEN if check.get("holds") else RED,
                )
            )
    return lines


def tool_result_parts(name: str, result: object) -> list[tuple[str, str]]:
    """Return the existing result lines with renderer-neutral colour roles."""
    return [(text, role or "result") for text, role in tool_result_lines(name, result)]


class SessionReporter:
    """Own one session's facts and publish them to the typed event feed."""

    def __init__(self, *, session_id: str = "") -> None:
        self.usage = SessionUsage()
        self.session_id = str(session_id or "")
        self._mid_stream = False
        self._message_text = ""
        self._message_emitted = 0
        self._message_emitted_at = 0.0
        self._pi_turn = 0
        self.changed_files: dict[str, str] = {}
        self.session_error: str | None = None
        self.denied_calls: set[str] = set()
        self.active_tools: dict[str, tuple[str, object]] = {}
        self.model_calls = 0
        self.last_input_tokens = 0
        self._context_band = 0

    def _emit(
        self,
        kind: str,
        payload: dict,
        *,
        scope: str = "",
        severity: str = "info",
        event_id: str | None = None,
    ) -> None:
        """One domain fact owned by this PI session."""
        if kind != "pi_message":
            self._close_message()
        typed_events.emit(
            kind,
            payload,
            scope=scope,
            severity=severity,
            session_id=self.session_id,
            event_id=event_id,
        )

    def _close_message(self) -> None:
        """End the model's block before the next fact."""
        if not self._mid_stream:
            return
        message = self._message_text
        if message.strip():
            self._emit(
                "pi_message",
                {
                    "text": message,
                    "final": True,
                    "turn": self._pi_turn,
                },
                scope="pi",
            )
        self._message_text = ""
        self._message_emitted = 0
        self._mid_stream = False

    def delta(self, text: str) -> None:
        if not text:
            return
        if not self._mid_stream:
            self._mid_stream = True
            self._message_text = ""
            self._message_emitted = 0
            self._message_emitted_at = 0.0
            self._pi_turn += 1
        self._message_text += text
        self._maybe_emit_message_partial(force="\n\n" in text)

    def _maybe_emit_message_partial(self, *, force: bool) -> None:
        """Publish the text grown so far; whole words only, throttled."""
        now = time.monotonic()
        if not force and now - self._message_emitted_at < PI_PARTIAL_SECONDS:
            return
        snapshot = self._message_text
        cut = max(snapshot.rfind(" "), snapshot.rfind("\n"))
        if cut + 1 <= self._message_emitted:
            return
        snapshot = snapshot[: cut + 1]
        addition = snapshot[self._message_emitted :]
        self._message_emitted = len(snapshot)
        self._message_emitted_at = now
        self._emit(
            "pi_message",
            {
                "text": addition,
                "final": False,
                "turn": self._pi_turn,
            },
            scope="pi",
        )

    def message(self, text: str) -> None:
        if self._mid_stream or not text:
            return
        self.delta(text)
        self._close_message()

    def tool(
        self, name: str, arguments: object, tool_call_id: str | None = None
    ) -> None:
        self.usage.count_tool(name)
        if tool_call_id:
            self.active_tools[tool_call_id] = (name, arguments)
        detail = tool_detail(name, arguments)
        self._emit(
            "tool_call_started",
            {
                "name": name,
                "arguments": arguments,
                "tool_call_id": tool_call_id,
                "detail": detail,
                "status": "started",
            },
            scope="tool",
        )

    def tool_failed(
        self,
        error: object,
        name: str = "tool",
        arguments: object = None,
        tool_call_id: str | None = None,
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
        self._emit(
            "tool_call_failed",
            {
                "name": name,
                "arguments": arguments,
                "tool_call_id": tool_call_id,
                "target": target,
                "error": reason,
                "status": "failed",
            },
            scope="tool",
            severity="error",
        )

    def tool_completed(
        self, name: str = "tool", tool_call_id: str | None = None
    ) -> None:
        """Close a successful call whose result the console does not print."""
        self._emit(
            "tool_call_completed",
            {
                "name": name,
                "tool_call_id": tool_call_id,
                "status": "completed",
            },
            scope="tool",
        )

    def tool_issue(
        self, name: str, issue: str, tool_call_id: str | None = None
    ) -> None:
        self._emit(
            "tool_call_failed",
            {
                "name": name,
                "tool_call_id": tool_call_id,
                "error": issue,
                "status": "failed",
            },
            scope="tool",
            severity="warning",
        )

    def tool_result(
        self, name: str, content: object, tool_call_id: str | None = None
    ) -> None:
        """One line per number the PI will reason from; the full result stays in its context."""
        try:
            result = json.loads(content) if isinstance(content, str) else None
        except ValueError:
            result = None
        payload = {
            "name": name,
            "tool_call_id": tool_call_id,
            "status": "completed",
        }
        if isinstance(result, dict):
            payload["result"] = result
        elif isinstance(content, str):
            if len(content) <= 4000:
                payload["content"] = content
            else:
                payload["content_length"] = len(content)
        self._emit("tool_call_completed", payload, scope="tool")

    def model_call(self, input_tokens: int | None) -> None:
        self.model_calls += 1
        self.last_input_tokens = input_tokens or 0
        band = (input_tokens or 0) // CONTEXT_BAND_TOKENS
        if band > self._context_band:
            self._context_band = band
            self._emit(
                "pi_context",
                {
                    "input_tokens": input_tokens,
                    "model_calls": self.model_calls,
                },
                scope="pi",
            )

    def denied(self, reason: str, tool_call_id: str | None = None) -> None:
        if tool_call_id:
            self.denied_calls.add(tool_call_id)
        name, arguments = ("tool", None)
        if tool_call_id:
            name, arguments = self.active_tools.get(tool_call_id, ("tool", None))
        self._emit(
            "tool_denied",
            {
                "name": name,
                "arguments": arguments,
                "tool_call_id": tool_call_id,
                "reason": reason,
                "status": "denied",
            },
            scope="tool",
            severity="warning",
        )

    def coding(
        self,
        phase: str,
        text: str,
        *,
        agent: str = "",
        status: str = "",
        detail: dict | None = None,
        severity: str = "info",
    ) -> None:
        """Report one coding handoff fact for the operator log."""
        self._emit(
            "coding",
            {
                "phase": phase,
                "agent": agent,
                "status": status,
                "text": text.strip(),
                "detail": detail or {},
            },
            scope="tool",
            severity=severity,
        )

    def operation_submitted(self, status: str, error: str | None = None) -> None:
        self._emit(
            "operation_submitted",
            {"status": status, "error": error or ""},
            scope="operation",
            severity="error"
            if status in {"rejected", "implementation_error", "validation_fatal"}
            else "info",
        )

    def warning(self, text: str, *, code: str = "") -> None:
        self._emit(
            "warning",
            {"code": code, "message": text},
            scope="warning",
            severity="warning",
        )

    def diagnostic(self, text: str, *, code: str, severity: str = "warning") -> None:
        self._emit(
            severity, {"code": code, "message": text}, scope=severity, severity=severity
        )

    def compaction(self, data) -> None:
        if not data.success:
            self.warning(
                f"context compaction failed: {data.error or 'unknown error'}",
                code="compaction_failed",
            )
            return
        before = data.pre_compaction_tokens or 0
        after = data.post_compaction_tokens or 0
        self._context_band = after // CONTEXT_BAND_TOKENS
        self.warning(
            f"context compacted: {before / 1000:.0f}k -> {after / 1000:.0f}k tokens, "
            f"{data.messages_removed or 0} messages replaced by a summary",
            code="compaction",
        )

    def file_changed(self, operation: str, path: str) -> None:
        operation_request = (
            Path(path).as_posix().endswith("pi_workspace/operation_request.json")
        )
        path = full_console_path(path)
        marker = {"created": "+", "deleted": "-"}.get(str(operation), "~")
        if self.changed_files.get(path) != marker:
            self.changed_files[path] = marker
            self._emit(
                "file_changed",
                {
                    "operation": operation,
                    "path": path,
                    "display_path": compact_console_path(path),
                    "operation_request": operation_request,
                },
                scope="tool",
            )

    def error(self, message: str) -> None:
        self.session_error = message
        self._emit(
            "error",
            {"code": "session_error", "message": message},
            scope="error",
            severity="error",
        )

    def summary(self, changed: list[str]) -> None:
        """Expose unannounced changes; lifecycle summaries come from the Runner."""
        for path in changed:
            path = full_console_path(path)
            if path not in self.changed_files:
                self._emit(
                    "file_changed",
                    {
                        "operation": "changed",
                        "path": path,
                        "display_path": compact_console_path(path),
                    },
                    scope="tool",
                )


class CodingReporter(SessionReporter):
    """Collect child accounting; forward only file names of child patches to the parent."""

    def __init__(self, parent: SessionReporter | None = None, agent: str = "") -> None:
        super().__init__(session_id=parent.session_id if parent is not None else "")
        self.parent = parent
        self.agent = agent

    def tool(
        self, name: str, arguments: object, tool_call_id: str | None = None
    ) -> None:
        super().tool(name, arguments, tool_call_id)
        if self.parent is not None and name == "apply_patch":
            files = _patch_detail(arguments)
            if files:
                self.parent.coding(
                    "patch",
                    f"  + {self.agent} patch: {files}",
                    agent=self.agent,
                    status="changed",
                    detail={"files": files},
                )

    def model_call(self, input_tokens: int | None) -> None:
        self.model_calls += 1
        self.last_input_tokens = input_tokens or 0

    def delta(self, text: str) -> None:
        pass

    def message(self, text: str) -> None:
        pass
