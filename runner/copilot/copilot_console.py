"""Optional SDK terminal renderer. It never produces campaign observations."""

import re
import sys
from datetime import UTC, datetime

from runner.copilot import reporting as presentation


def format_console_line(text: str, color: str | None = None) -> str:
    if not sys.stdout.isatty():
        return text
    stripped = text.lstrip()
    indent = text[: len(text) - len(stripped)]
    marker, separator, remainder = stripped.partition(" ")
    timestamp = f"{presentation._DIM}[{datetime.now(UTC).astimezone():%H:%M:%S}]{presentation._RESET}"
    if color is not None:
        return f"{timestamp} {indent}{color}{stripped}{presentation._RESET}"
    marker_color = presentation._MARKER_COLORS.get(marker, "\033[36m")
    if marker in {"x", "!", "--"}:
        return f"{timestamp} {indent}{marker_color}{stripped}{presentation._RESET}"
    if marker == ">":
        remainder = presentation._colored_tool_remainder(remainder)
    return f"{timestamp} {indent}{marker_color}{marker}{presentation._RESET}{separator}{remainder}"


class Console:
    def __init__(self, columns: int | None = None) -> None:
        self._mid_stream = False
        self._at_line_start = True
        self._message_width = max((columns or presentation._console_width()) - 4, 20)
        self._compact_buffer = ""
        self._message_buffer = ""
        self._message_spacing = ""
        self._message_column = 0
        self._message_continues_word = False

    def line(self, text: str, color: str | None = None) -> None:
        self._close_message()
        print(format_console_line(text, color), flush=True)

    def diagnostic(self, text: str) -> None:
        print(text, file=sys.stderr)

    def _close_message(self) -> None:
        if not self._mid_stream:
            return
        self._buffer_console_text("", final=True)
        self._flush_message(final=True)
        if sys.stdout.isatty():
            sys.stdout.write(presentation._RESET)
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
            sys.stdout.write(
                presentation._GUTTER
                if sys.stdout.isatty()
                else presentation._PLAIN_GUTTER
            )
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
        split_at = (
            len(self._compact_buffer)
            if final
            else presentation.unresolved_console_suffix_start(self._compact_buffer)
        )
        if (
            len(self._compact_buffer) - split_at
            > presentation.MAX_UNRESOLVED_CONSOLE_TOKEN
        ):
            split_at = len(self._compact_buffer)
        if split_at == 0:
            return
        ready = self._compact_buffer[:split_at]
        self._compact_buffer = self._compact_buffer[split_at:]
        self._message_buffer += presentation.compact_console_text(ready)

    def delta(self, text: str) -> None:
        if not text:
            return
        if not self._mid_stream:
            self._mid_stream = True
            self._at_line_start = True
            if sys.stdout.isatty():
                sys.stdout.write(presentation._MESSAGE)
        self._buffer_console_text(text, final=False)
        self._flush_message(final=False)

    def message(self, text: str) -> None:
        if self._mid_stream:
            self._buffer_console_text("", final=True)
            self._flush_message(final=True)
            return
        if text:
            self.delta(text)
            self._close_message()
