"""Console presentation for the Runner.

The Runner formats facts the researcher already decided or the tools already
measured. It never adds a scientific conclusion of its own.
"""

import json
import re
import shutil
import sys
import textwrap
import time
from datetime import datetime
from pathlib import Path

_RESET = "\033[0m"
_DIM = "\033[90m"
_CYAN = "\033[1;96m"
_GREEN = "\033[1;92m"
_MAGENTA = "\033[1;95m"
_YELLOW = "\033[1;93m"
_RED = "\033[1;91m"
_WHITE = "\033[1;97m"
_ROOT = Path(__file__).resolve().parents[1]
_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_SEMANTIC_COLORS = {
    "campaign": _WHITE,
    "session": _MAGENTA,
    "pi": _MAGENTA,
    "inquiry": _YELLOW,
    "operation": _CYAN,
    "measurement": _CYAN,
    "training": _CYAN,
    "checkpoint": _GREEN,
    "assessment": _GREEN,
    "runner": _CYAN,
    "warning": _YELLOW,
    "error": _RED,
}
_SECTION_HEADINGS = frozenset(
    {
        "Hypothesis",
        "Experiment",
        "Training dynamics",
        "Candidates",
        "Next",
        "Question",
        "Plan",
        "Selections",
        "Reason",
        "Candidate",
        "Champion",
        "Task reference",
        "Paired comparison",
        "Continue from",
        "Scientific recipe",
        "Retained alternatives",
        "Removed retained alternatives",
        "Working lineage",
        "Best-known model",
        "Final benchmark",
        "Hypothesis assessment",
        "Frozen model",
    }
)

# A heartbeat is rewritten in place and reaches the log only on this cadence:
# long enough that a run does not become a wall of near-identical counters,
# short enough that a redirected log still shows the recent dynamics of a run.
PROGRESS_ARCHIVE_SECONDS = 20.0


def _console_width() -> int:
    return max(shutil.get_terminal_size(fallback=(100, 24)).columns, 40)


def _clip(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3].rstrip() + "..."


def compact_path(value: str | Path) -> str:
    """Keep paths useful without leaking a long machine-specific prefix."""
    path = Path(value)
    try:
        relative = path.resolve().relative_to(_ROOT.resolve())
        return relative.as_posix()
    except (OSError, ValueError):
        if not path.is_absolute():
            return path.as_posix()
        parts = path.parts[-2:]
        return (".../" + "/".join(parts)).replace("\\", "/")


def _wrap_console_text(text: str, *, initial_prefix: str = "") -> list[str]:
    width = _console_width()
    subsequent = " " * len(initial_prefix)
    lines: list[str] = []
    for index, logical_line in enumerate(text.splitlines() or [""]):
        first = initial_prefix if index == 0 else subsequent
        lines.extend(
            textwrap.wrap(
                logical_line,
                width=width,
                initial_indent=first,
                subsequent_indent=subsequent,
                break_long_words=False,
                break_on_hyphens=False,
                replace_whitespace=False,
            )
            or [first.rstrip()]
        )
    return lines


def compact_text(text: object) -> str:
    value = str(text)
    for root in (str(_ROOT), str(_ROOT).replace("\\", "/")):
        value = value.replace(root, ".")
    return _UUID.sub("<id>", value)


def _style_card_sections(text: str) -> str:
    lines = text.splitlines(keepends=True)
    return "".join(
        f"{_YELLOW}{line}{_RESET}" if line.rstrip("\r\n") in _SECTION_HEADINGS else line
        for line in lines
    )


class LiveProgress:
    """The one line that is rewritten instead of appended.

    Training and evaluation heartbeat every few seconds, and appending each one
    buries the cards that carry the scientific facts. The live line is rewritten
    where the terminal can do it, and reaches the log on a cadence. A phase
    boundary forces it, so nothing that mattered is lost.
    """

    def __init__(
        self,
        stream=None,
        archive_seconds: float = PROGRESS_ARCHIVE_SECONDS,
    ) -> None:
        self.archive_seconds = archive_seconds
        self._stream = stream
        self._live = ""
        self._archived_at = float("-inf")

    def _out(self):
        # Resolved per call: whether stdout can be rewritten is not decided here.
        return self._stream if self._stream is not None else sys.stdout

    def line(self, message: str, *, archive: bool = False) -> None:
        stream = self._out()
        timestamp_plain = (
            f"[{datetime.now():%H:%M:%S}]"  # noqa: DTZ005 - local console time
        )
        message = _clip(message, max(_console_width() - len(timestamp_plain) - 1, 20))
        timestamp = timestamp_plain
        if stream.isatty():
            # A heartbeat is superseded by the next one, so its timestamp yields
            # to the timestamps of the lines that stay in the log.
            timestamp = f"{_DIM}{timestamp}{_RESET}"
        text = f"{timestamp} {message}"
        now = time.monotonic()
        due = archive or now - self._archived_at >= self.archive_seconds
        if not stream.isatty():
            # Nothing can be rewritten, so only the archived snapshots survive.
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
        """Erase an unterminated status line so the next fact starts on its own."""
        if not self._live:
            return
        self._live = ""
        stream = self._out()
        stream.write("\r\033[K")
        stream.flush()

    def archived(self) -> None:
        """A durable line just reached the console, so the status line can wait."""
        self._archived_at = time.monotonic()


_progress = LiveProgress()


def progress(message: str, *, archive: bool = False) -> None:
    """Report a heartbeat that a later one supersedes."""
    _progress.line(message, archive=archive)


def announce(message: str) -> None:
    _progress.clear()
    _progress.archived()
    leading_break = "\n" if message.startswith("\n") else ""
    text = compact_text(message.lstrip("\n"))
    timestamp = f"[{datetime.now():%H:%M:%S}]"  # noqa: DTZ005 - local console time
    prefix = f"{timestamp} "
    wrapped = _wrap_console_text(text, initial_prefix=prefix)
    if sys.stdout.isatty() and text.startswith("[") and "]" in text:
        marker = text[1 : text.index("]")].casefold()
        color = _SEMANTIC_COLORS.get(marker, _CYAN)
        wrapped[0] = wrapped[0].replace(
            f"[{marker}]",
            f"{color}[{marker}]{_RESET}",
            1,
        )
    elif sys.stdout.isatty() and text.startswith("==="):
        wrapped = [_style_card_sections(f"{_CYAN}{line}{_RESET}") for line in wrapped]
    print(leading_break + "\n".join(wrapped), flush=True)


def boundary(scope: str, action: str, subject: str = "", detail: str = "") -> None:
    """Print one durable lifecycle boundary with a stable visual hierarchy."""
    body = " | ".join(part for part in (action.upper(), subject, detail) if part)
    announce(f"[{scope.casefold()}] {body}")


def format_duration(seconds: float) -> str:
    total = max(int(seconds), 0)
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{seconds:02d}s"
    return f"{seconds}s"


def format_count(value: float) -> str:
    count = float(value)
    for threshold, suffix in ((1_000_000, "m"), (1_000, "k")):
        if abs(count) >= threshold:
            scaled = count / threshold
            return f"{scaled:.1f}".rstrip("0").rstrip(".") + suffix
    return f"{count:g}"


def scenario_progress_metric(record: dict[str, float]) -> str | None:
    """The one live training metric the scenario owns, resolved on demand.

    Imported here rather than at module scope so presenting a card never pulls
    the training and physics stack into a validation-only command.
    """
    from robot_learning.scenario.progress import render_training_progress_metric

    return render_training_progress_metric(record)


def training_progress_suffix(record: dict[str, float] | None) -> str:
    """Append the rolling reward and the single scenario-owned live metric."""
    if not record:
        return ""
    parts: list[str] = []
    reward = record.get("ep_rew_mean")
    if reward is not None:
        parts.append(f"reward {float(reward):g}")
    scenario_fragment = scenario_progress_metric(record)
    if scenario_fragment:
        parts.append(scenario_fragment)
    return "".join(f" | {part}" for part in parts)


def training_heartbeat(
    operation_id: str,
    steps: int,
    target: int,
    elapsed: float,
    eta: float,
    fps: float,
    record: dict[str, float] | None,
) -> str:
    percent = min(100.0, 100 * steps / target) if target else 0.0
    return (
        f"TRAIN {operation_id} | {percent:.0f}% | "
        f"{format_count(steps)}/{format_count(target)} | {format_count(fps)} fps | "
        f"{format_duration(elapsed)} | ETA {format_duration(eta)}"
        + training_progress_suffix(record)
    )


def _usage_rows(campaign_id: str, session_id: str | None = None) -> list[dict]:
    usage_path = _ROOT / "reports" / "session_usage" / f"{campaign_id}.jsonl"
    if not usage_path.is_file():
        return []
    rows: list[dict] = []
    for line in usage_path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if session_id is None or row.get("session_id") == session_id:
            rows.append(row)
    return rows


def usage_summary(campaign_id: str, session_id: str | None = None) -> str:
    """Aggregate existing durable accounting without creating a new budget."""
    rows = _usage_rows(campaign_id, session_id)
    if not rows:
        return "usage unavailable"
    duration = sum(float(row.get("duration_seconds") or 0) for row in rows)
    prompt = sum(int(row.get("input_tokens") or 0) for row in rows)
    cached = sum(int(row.get("cache_read_tokens") or 0) for row in rows)
    output = sum(int(row.get("output_tokens") or 0) for row in rows)
    aiu = sum(float(row.get("aiu") or 0) for row in rows)
    cost = sum(float(row.get("reported_cost_usd") or 0) for row in rows)
    parts = [format_duration(duration)]
    if aiu:
        parts.append(f"{aiu:.2f} AIU")
    if cost:
        parts.append(f"${cost:.4f} estimated")
    if prompt:
        cache_share = round(100 * cached / prompt) if cached else 0
        parts.append(f"prompt {format_count(prompt)} ({cache_share}% cached)")
    if output:
        parts.append(f"output {format_count(output)}")
    return " | ".join(parts)
