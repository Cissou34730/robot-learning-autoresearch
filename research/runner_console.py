"""Console presentation for the Runner.

The Runner formats facts the researcher already decided or the tools already
measured. It never adds a scientific conclusion of its own.
"""

import sys
import time
from datetime import datetime

_RESET = "\033[0m"
_DIM = "\033[90m"
_CYAN = "\033[1;96m"
_YELLOW = "\033[1;93m"
_RED = "\033[1;91m"
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
        timestamp = f"[{datetime.now():%H:%M:%S}]"  # noqa: DTZ005 - local console time
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
    text = message.lstrip("\n")
    timestamp = f"[{datetime.now():%H:%M:%S}]"  # noqa: DTZ005 - local console time
    if sys.stdout.isatty() and text.startswith("==="):
        title, separator, remainder = text.partition("\n")
        text = f"{_CYAN}{timestamp} {title}{_RESET}{separator}{_style_card_sections(remainder)}"
        timestamp = ""
    elif sys.stdout.isatty() and text.startswith("[") and "]" in text:
        prefix, _, remainder = text.partition("]")
        color = _RED if prefix == "[error" else _CYAN
        # A durable line keeps a full-brightness timestamp: it is the one a
        # reader returns to, unlike the heartbeat it replaced.
        text = f"{color}{prefix}]{_RESET}{remainder}"
    separator = " " if timestamp else ""
    print(f"{leading_break}{timestamp}{separator}{text}", flush=True)


def format_duration(seconds: float) -> str:
    total = max(int(seconds), 0)
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{seconds:02d}s"
    return f"{seconds}s"


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
        parts.append(f"{float(reward):g}")
    scenario_fragment = scenario_progress_metric(record)
    if scenario_fragment:
        _, _, value = scenario_fragment.partition(" ")
        parts.append(value or scenario_fragment)
    return "".join(f" | {part}" for part in parts)
