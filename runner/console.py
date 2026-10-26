"""Optional terminal renderer. Observation production lives in runner.reporting."""

import sys
import time
from datetime import datetime

from runner import reporting as presentation


class LiveProgress:
    """Render the current heartbeat and archive it on the existing cadence."""

    def __init__(
        self, stream=None, archive_seconds=presentation.PROGRESS_ARCHIVE_SECONDS
    ):
        self.archive_seconds = archive_seconds
        self._stream = stream
        self._live = ""
        self._archived_at = float("-inf")

    def _out(self):
        return self._stream if self._stream is not None else sys.stdout

    def line(self, message: str, *, archive: bool = False) -> None:
        stream = self._out()
        timestamp_plain = f"[{datetime.now():%H:%M:%S}]"  # noqa: DTZ005
        message = presentation._clip(
            message, max(presentation._console_width() - len(timestamp_plain) - 1, 20)
        )
        timestamp = timestamp_plain
        if stream.isatty():
            timestamp = f"{presentation._DIM}{timestamp}{presentation._RESET}"
        text = f"{timestamp} {message}"
        now = time.monotonic()
        due = archive or now - self._archived_at >= self.archive_seconds
        if not stream.isatty():
            if due:
                self._archived_at = now
                print(text, file=stream, flush=True)
            return
        if due:
            self._archived_at = now
            self._live = ""
            stream.write(f"\r\033[K{text}\n")
        else:
            self._live = text
            stream.write(f"\r\033[K{text}")
        stream.flush()

    def clear(self) -> None:
        if not self._live:
            return
        self._live = ""
        stream = self._out()
        stream.write("\r\033[K")
        stream.flush()

    def archived(self) -> None:
        self._archived_at = time.monotonic()


_progress = LiveProgress()


def progress(message: str, *, archive: bool = False) -> None:
    _progress.line(message, archive=archive)


def diagnostic(message: str, *, stderr: bool = False) -> None:
    print(message, file=sys.stderr if stderr else sys.stdout)


def announce(message: str) -> None:
    _progress.clear()
    _progress.archived()
    leading_break = "\n" if message.startswith("\n") else ""
    text = presentation.compact_text(message.lstrip("\n"))
    timestamp = f"[{datetime.now():%H:%M:%S}]"  # noqa: DTZ005
    prefix = f"{timestamp} "
    if not sys.stdout.isatty():
        first, *rest = text.splitlines() or [""]
        indent = " " * len(prefix)
        print(
            leading_break
            + prefix
            + " ".join(first.split())
            + "".join(f"\n{indent}{line.rstrip()}" for line in rest),
            flush=True,
        )
        return
    wrapped = presentation._wrap_console_text(text, initial_prefix=prefix)
    if text.startswith("[") and "]" in text:
        marker = text[1 : text.index("]")].casefold()
        color = presentation._SEMANTIC_COLORS.get(marker, presentation._CYAN)
        wrapped[0] = wrapped[0].replace(
            f"[{marker}]", f"{color}[{marker}]{presentation._RESET}", 1
        )
    elif text.startswith("==="):
        wrapped = [
            presentation._style_card_sections(
                f"{presentation._CYAN}{line}{presentation._RESET}"
            )
            for line in wrapped
        ]
    print(leading_break + "\n".join(wrapped), flush=True)


def card(scope: str, title: str, lines=()) -> None:
    _progress.clear()
    _progress.archived()
    scope = scope.casefold()
    color = presentation._SEMANTIC_COLORS.get(scope, presentation._CYAN)
    body_color = color if scope in {"error", "warning"} else presentation._WHITE
    timestamp = f"[{datetime.now():%H:%M:%S}]"  # noqa: DTZ005
    title = presentation.compact_text(title)
    body = [presentation.compact_text(line) for line in lines]
    print(flush=True)
    if not sys.stdout.isatty():
        print(f"{timestamp} === {title} ===", flush=True)
        for line in body:
            print(f"  {' '.join(line.split())}", flush=True)
        print(flush=True)
        return
    print(f"{timestamp} {color}=== {title} ==={presentation._RESET}", flush=True)
    for line in body:
        line_color = (
            presentation._YELLOW
            if line in presentation._SECTION_HEADINGS
            else presentation._CONTEXT
            if line.startswith(presentation._CONTEXT_PREFIXES)
            else body_color
        )
        wrapped = presentation._wrap_console_text(line, initial_prefix="  ")
        print(
            "\n".join(f"{line_color}{part}{presentation._RESET}" for part in wrapped),
            flush=True,
        )
    print(flush=True)
