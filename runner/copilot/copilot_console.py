"""What the human sees of a Copilot session; nothing here is read back."""

from __future__ import annotations

import json
import ntpath
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath

from runner.copilot.path_policy import ROOT
from runner.copilot.usage import SessionUsage

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


def _console_width() -> int:
    return max(shutil.get_terminal_size(fallback=(100, 24)).columns, 40)


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
    "wilson_proportion_interval": lambda arguments: (
        f"{arguments.get('successes', '-')}/{arguments.get('trials', '-')}"
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


class Console:
    """Everything the human sees, and nothing the protocol reads back."""

    def __init__(self, columns: int | None = None) -> None:
        self.usage = SessionUsage()
        self._mid_stream = False
        self._at_line_start = True
        self._message_width = max((columns or _console_width()) - 4, 20)
        self._compact_buffer = ""
        self._message_buffer = ""
        self._message_spacing = ""
        self._message_column = 0
        self._message_continues_word = False
        self.changed_files: dict[str, str] = {}
        self.session_error: str | None = None
        self.denied_calls: set[str] = set()
        self.active_tools: dict[str, tuple[str, object]] = {}

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
        self.usage.count_tool(name)
        if tool_call_id:
            self.active_tools[tool_call_id] = (name, arguments)
        detail = tool_detail(name, arguments)
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
            suffix = " | PI operation request updated" if operation_request else ""
            self.line(f"  {marker} {path}{suffix}")

    def error(self, message: str) -> None:
        self.session_error = message
        self.line(f"  ! session error: {message}")

    def summary(self, changed: list[str]) -> None:
        """Expose unannounced changes; lifecycle summaries come from the Runner."""
        for path in changed:
            path = full_console_path(path)
            if path not in self.changed_files:
                self.line(f"  ~ {path}")


class CodingConsole(Console):
    """Collect child accounting without printing its conversation or diffs."""

    def line(self, text: str) -> None:
        pass

    def delta(self, text: str) -> None:
        pass

    def message(self, text: str) -> None:
        pass
