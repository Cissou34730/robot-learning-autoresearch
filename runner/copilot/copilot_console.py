"""Copilot console rendering and existing session usage accounting."""

from __future__ import annotations

import json
import ntpath
import re
import shutil
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath

from runner.copilot.coding_contracts import (
    normalize_model,
)
from runner.copilot.opencode_provider import provider_of
from runner.copilot.path_policy import (
    ROOT,
)

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


def thousands(count: int) -> str:
    return f"{count / 1000:.0f}k" if count >= 1000 else str(count)


def _console_width() -> int:
    return max(shutil.get_terminal_size(fallback=(100, 24)).columns, 40)


class Console:
    """Everything the human sees, and nothing the protocol reads back."""

    def __init__(self, label: str = "", columns: int | None = None) -> None:
        # Which experiment and phase this session is, so one long console log
        # stays attributable without reading backwards for the last banner.
        self.label = label
        self.provider = "github-copilot"
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
                            if action not in {"operations", "metadata"}
                            else None
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
                detail = " | ".join(
                    str(value)
                    for value in (
                        arguments.get("library", "-"),
                        arguments.get("symbol") or "library root",
                        arguments.get("action", "definition"),
                        arguments.get("contains"),
                    )
                    if value
                )
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
        if self.provider != "github-copilot":
            return f"provider cost unavailable, {prompt}"
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


class CodingConsole(Console):
    """Collect child accounting without printing its conversation or diffs."""

    def line(self, text: str) -> None:
        pass

    def delta(self, text: str) -> None:
        pass

    def message(self, text: str) -> None:
        pass


def record_usage(
    args,
    console: Console,
    elapsed: float,
    exit_code: int,
    *,
    role: str = "pi",
    session_id: str | None = None,
    parent_session_id: str | None = None,
    actual_models: list[str] | None = None,
    actual_reasoning_efforts: list[str] | None = None,
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
        "provider": provider_of(args.model),
        "reasoning": getattr(args, "effective_reasoning", args.reasoning),
        # Child time is reported in its own row, not again in the PI row.
        "duration_seconds": round(
            max(
                0.0,
                elapsed - console.coding_duration_seconds - console.runner_wait_seconds,
            ),
            3,
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
        "aiu": console.nano_aiu / 1e9
        if provider_of(args.model) == "github-copilot" and "aiu" in console.reported_usage
        else None,
        "tool_calls": console.tool_calls,
        "tools_by_name": console.tool_counts,
    }
    external = getattr(args, "provider_model", None)
    if external is not None:
        row["provider_token_prices_per_million"] = external.cost
    if actual_models is not None:
        row["actual_models"] = actual_models
    if actual_reasoning_efforts is not None:
        row["actual_reasoning_efforts"] = actual_reasoning_efforts
    with (directory / f"{campaign_id}.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
