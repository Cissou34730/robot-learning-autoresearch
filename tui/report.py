"""The single-screen campaign report.

One vertical composition at every width:

1. Campaign context and status, including question, synthesis and usage.
2. PI-selected models (role table, scrollable when it overflows).
3. Conditional execution progress for training/evaluation.
4. Scrollable chronological output.
5. One compact reading-status line.

The report is read-only. It renders recorded facts and, when a structured
observation file is present, incoming structured observations. Scrolling and
focus changes never touch campaign execution.
"""

from __future__ import annotations

import re
import textwrap
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import DataTable, RichLog, Static

from runner import console, paths
from tui import projector
from tui.observations import JsonlFeed, Observation

MIN_COLUMNS = 48
MIN_ROWS = 16
SNAPSHOT_SECONDS = 15.0
TICK_SECONDS = 15.0
FEED_SECONDS = 1.0
COMPACT_WIDTH = 100
COMPACT_HEIGHT = 30
LIVENESS_SECONDS = 300.0
PROGRESS_STALE_SECONDS = 300.0
MAX_RENDERED_ENTRIES = 100_000
EVENTS_DIR = Path("reports") / "tui_observations"


# The log is display-only. These tokens are the single palette used by the
# report; CSS picks its structural colours from the active Textual theme.
@dataclass(frozen=True)
class Palette:
    """Semantic colour tokens for one terminal background."""

    name: str
    background: str
    text: str
    muted: str
    heading: str
    accent: str
    success: str
    warning: str
    error: str
    pi: str
    tool: str
    section: str
    result: str


PALETTES: dict[str, Palette] = {
    "dark": Palette(
        name="dark",
        background="#1e1e1e",
        text="#e6e6e6",
        muted="#b0b0b0",
        heading="#f0f0f0",
        accent="#7cc7ff",
        success="#6ee7a8",
        warning="#ffd166",
        error="#ff8a9b",
        pi="#e0aaff",
        tool="#b8c0cc",
        section="#d7d7d7",
        result="#6ee7a8",
    ),
    "light": Palette(
        name="light",
        background="#f5f5f5",
        text="#1a1a1a",
        muted="#4a4a4a",
        heading="#111111",
        accent="#0b5fa5",
        success="#0f6b3d",
        warning="#8a5a00",
        error="#b3261e",
        pi="#6b2d8f",
        tool="#3f4a5a",
        section="#2a2a2a",
        result="#0f6b3d",
    ),
}

# Card body headings already classified by the Runner console.
SECTION_HEADINGS = frozenset(getattr(console, "_SECTION_HEADINGS", ()))

_FLOAT_RE = re.compile(r"(?<![\w.])-?\d+\.\d{4,}(?![\w.])")
_PATH_RE = re.compile(
    r"(?<![\w:/])(?:[A-Za-z]:[\\/][^\s,;:)\]}\"']*|/[^\s,;:)\]}\"']*)"
)


def _relative_luminance(color: str) -> float:
    value = color.lstrip("#")
    channels = [int(value[index : index + 2], 16) / 255 for index in (0, 2, 4)]

    def linear(channel: float) -> float:
        if channel <= 0.04045:
            return channel / 12.92
        return ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast ratio between two #RRGGBB colours."""
    first = _relative_luminance(foreground)
    second = _relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def _status_style(status: str, palette: Palette) -> str:
    """Pair the campaign status text with a semantic token."""
    if status.startswith("RUNNING") and "unknown" not in status:
        return f"bold {palette.success}"
    if status.startswith("RUNNING"):
        return f"bold {palette.warning}"
    if status.startswith("ENDED") or status == "Loading":
        return palette.muted
    return palette.text


def _scope_style(scope: str, palette: Palette) -> str:
    """Map a feed scope to a semantic token, never to colour alone."""
    scope = scope.casefold()
    if scope == "error":
        return f"bold {palette.error}"
    if scope == "warning":
        return f"bold {palette.warning}"
    if scope in {"success", "assessment", "validation", "result"}:
        return f"bold {palette.success}"
    if scope in {"pi", "session"}:
        return palette.pi
    if scope == "tool":
        return palette.tool
    if scope in {"operation", "measurement", "training", "runner"}:
        return palette.accent
    if scope == "inquiry":
        return palette.warning
    if scope == "campaign":
        return f"bold {palette.heading}"
    return palette.text


def _display_text(value: str) -> str:
    """Round long floats and compact absolute paths for display only."""
    text = _clean_text(value)

    def rounded(match: re.Match) -> str:
        return f"{float(match.group(0)):.3f}"

    text = _FLOAT_RE.sub(rounded, text)

    def compact(match: re.Match) -> str:
        token = match.group(0)
        suffix = ""
        while token and token[-1] in ".,;:":
            suffix = token[-1] + suffix
            token = token[:-1]
        return f"{console.compact_path(token)}{suffix}"

    return _PATH_RE.sub(compact, text)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _clean_text(value: object) -> str:
    """Untrusted source text renders as text, never as markup or controls."""
    if value is None:
        return ""
    return str(value).replace("\r", "")


def _ts(stamp: datetime | None) -> str:
    if stamp is None:
        return "--:--"
    return f"{stamp.astimezone():%H:%M}"


def _hang(prefix: str, text: str, width: int) -> list[str]:
    """Wrap text under a fixed prefix, preserving blank paragraphs."""
    width = max(width, 20)
    lines: list[str] = []
    indent = " " * len(prefix)
    current_prefix = prefix
    paragraphs = text.split("\n") or [""]
    for paragraph in paragraphs:
        if not paragraph.strip():
            lines.append("")
            continue
        wrapped = textwrap.wrap(
            paragraph,
            width=width,
            initial_indent=current_prefix,
            subsequent_indent=indent,
            break_long_words=True,
            break_on_hyphens=False,
        )
        lines.extend(wrapped or [current_prefix.rstrip()])
        current_prefix = indent
    return lines


def _hang_styled(
    prefix: str,
    text: str,
    width: int,
    prefix_style: str = "dim",
    body_style: str | None = None,
) -> list[Text]:
    """Wrap text under a fixed prefix, styling the prefix and the body."""
    width = max(width, 20)
    out: list[Text] = []
    indent = " " * len(prefix)
    current_prefix = prefix
    for paragraph in text.split("\n") or [""]:
        if not paragraph.strip():
            out.append(Text(""))
            current_prefix = indent
            continue
        wrapped = textwrap.wrap(
            paragraph,
            width=width,
            initial_indent=current_prefix,
            subsequent_indent=indent,
            break_long_words=True,
            break_on_hyphens=False,
        )
        segments = wrapped or [current_prefix.rstrip()]
        for index, line in enumerate(segments):
            piece = Text()
            if index == 0 and current_prefix and len(line) >= len(current_prefix):
                piece.append(line[: len(current_prefix)], style=prefix_style)
                body = line[len(current_prefix) :]
            else:
                body = line
            if body:
                piece.append(body, style=body_style or "")
            out.append(piece)
        current_prefix = indent
    return out


def _fit_text(text: Text, width: int) -> Text:
    if len(text.plain) <= width:
        return text
    clipped = text.copy()
    clipped.truncate(max(1, width))
    return clipped


def _elapsed_text(seconds: float | None, label: str) -> str:
    if seconds is None:
        return f"{label} unavailable"
    return f"{label} {console.format_duration(float(seconds))}"


def _metric_cell(value: str, missing: str = "unavailable", muted: str = "dim") -> Text:
    """Metric cell text; missing values render muted instead of invisible."""
    text = _clean_text(value)
    if value == missing or value.startswith(missing):
        return Text(text, style=muted)
    return Text(text)


class OutputLog(RichLog):
    """Scrollable output that follows only while the reader is at the bottom."""

    can_focus = True

    def __init__(self, **kwargs) -> None:
        super().__init__(
            wrap=True,
            highlight=False,
            markup=False,
            auto_scroll=False,
            max_lines=MAX_RENDERED_ENTRIES,
            **kwargs,
        )
        self._following = True
        self._missed = 0
        self._follow_listeners: list = []

    @property
    def following(self) -> bool:
        return self._following

    @property
    def missed(self) -> int:
        return self._missed

    def on_follower(self, listener) -> None:
        self._follow_listeners.append(listener)

    def _at_bottom(self) -> bool:
        try:
            return self.scroll_offset.y >= self.max_scroll_y - 0.5
        except Exception:  # noqa: BLE001 - layout not ready yet
            return True

    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        try:
            super().watch_scroll_y(old_value, new_value)
        except AttributeError:  # pragma: no cover - base class variants
            pass
        bottom = self._at_bottom()
        if bottom != self._following:
            self._following = bottom
            if bottom:
                self._missed = 0
            for listener in self._follow_listeners:
                listener(bottom, self._missed)

    def append_texts(self, items: list) -> None:
        """Append pre-built Text display lines, honoring the follow state."""
        was_bottom = self._at_bottom()
        wrote = False
        for item in items:
            if isinstance(item, str):
                item = Text(_clean_text(item))
            # Render each pre-wrapped line at its own length so RichLog does not
            # pad short lines or clip long ones against the console's default
            # width.
            self.write(
                item,
                width=max(1, len(item.plain)),
                expand=False,
                shrink=False,
            )
            wrote = True
        if not wrote:
            return
        if was_bottom:
            self.scroll_end(animate=False)
        else:
            self._missed += 1
            for listener in self._follow_listeners:
                listener(self._following, self._missed)


class CampaignSources:
    """Reads the durable campaign files selected by the campaign root."""

    def read(self) -> tuple[dict | None, list[dict], list[dict]]:
        from tui.sources import read_json, read_jsonl

        state = read_json(paths.STATE_PATH)
        records = read_jsonl(paths.RESULTS_PATH)
        usage_rows = []
        campaign_id = (state or {}).get("campaign", {}).get("id")
        if campaign_id:
            usage_rows = read_jsonl(
                paths.ROOT / "reports" / "session_usage" / f"{campaign_id}.jsonl"
            )
        return state, records, usage_rows


class DemoSources:
    """Synthetic material so the demo never touches real campaign files."""

    def read(self) -> tuple[dict | None, list[dict], list[dict]]:
        args = _demo_args()
        return args


def _demo_args():
    from tui.demo import demo_snapshot_args

    return demo_snapshot_args()


class CampaignReport(App):
    TITLE = "Autoresearch campaign report"

    AUTO_FOCUS = "#output"

    BINDINGS: ClassVar[list] = [
        ("ctrl+c", "quit", "Close report"),
        ("ctrl+q", "quit", "Close report"),
    ]

    CSS = """
    Screen {
        background: $surface;
        color: $text;
        padding: 0 1;
    }
    #context {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }
    #models-heading {
        height: 1;
        color: $text;
    }
    #models {
        height: auto;
        max-height: 10;
        background: $surface;
        color: $text;
        scrollbar-size-horizontal: 1;
    }
    #models > .datatable--header {
        background: $surface;
        color: $text;
        text-style: bold;
    }
    #models > .datatable--header-cursor,
    #models > .datatable--cursor,
    #models > .datatable--hover,
    #models > .datatable--even-row,
    #models > .datatable--odd-row,
    #models > .datatable--fixed,
    #models > .datatable--fixed-cursor {
        background: $surface;
        color: $text;
    }
    #models:focus {
        background-tint: transparent;
    }
    #models:focus > .datatable--header {
        text-style: bold underline;
    }
    #progress {
        display: none;
        margin-top: 1;
        height: auto;
    }
    #training {
        display: none;
        margin-top: 1;
        height: auto;
    }
    #output-heading {
        height: 1;
        color: $text;
    }
    #output {
        height: 1fr;
        padding: 0;
        background: $surface;
    }
    #reading {
        height: 1;
        color: $text-muted;
    }
    #too-small {
        display: none;
        layer: alert;
        width: 100%;
        height: 100%;
        content-align: center middle;
        background: $surface;
        color: $text;
    }
    """

    def __init__(
        self,
        *,
        sources: CampaignSources | DemoSources | None = None,
        events_path: Path | None = None,
        demo: bool = False,
    ) -> None:
        super().__init__()
        self._demo = demo
        self._sources = sources or (DemoSources() if demo else CampaignSources())
        self._events_path = Path(events_path) if events_path else None
        self._palette = PALETTES["dark"]
        self._feed = None
        self.snapshot: projector.CampaignSnapshot | None = None
        self._attached = False
        self._context_rows = 0
        self._progress_rows = 0
        self._training_rows = 0
        self._models_layout_key = ""
        self._output_hidden = False
        self._training: dict | None = None
        self._evaluation: dict | None = None
        self._stage_started: datetime | None = None
        self._last_activity: str = ""
        self._last_session: str = ""
        self._last_liveness: datetime | None = None
        self._observed_signature: tuple | None = None
        self._last_error: str = ""
        self._source_note_sent: bool = False
        self._pi_seen: deque = deque(maxlen=256)
        self._pi_stream: dict = {}
        self._feed_campaign: str | None = None

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static("Loading campaign report...", id="context")
        yield Static("PI-assigned models", id="models-heading")
        table = DataTable(
            id="models",
            cursor_type="none",
            zebra_stripes=False,
            show_row_labels=False,
        )
        table.add_columns(
            "PI-assigned role",
            "Candidate",
            "Training steps",
            "Reward (tr)",
            "Success (tr)",
            "Success (development) / source",
        )
        yield table
        yield Static("", id="progress")
        yield Static("", id="training")
        yield Static("", id="output-heading")
        yield OutputLog(id="output")
        yield Static("", id="reading")
        yield Static("Terminal too small - need 48x16", id="too-small")

    def on_mount(self) -> None:
        self._palette = self._resolve_palette()
        self.query_one("#output", OutputLog).on_follower(self._on_follow)
        self._make_feed()
        self.refresh_snapshot()
        self.drain_feed()
        self.set_interval(SNAPSHOT_SECONDS, self._on_snapshot_interval)
        self.set_interval(TICK_SECONDS, self.tick_clock)
        self.set_interval(FEED_SECONDS, self.drain_feed)
        self._apply_layout()

    def _resolve_palette(self) -> Palette:
        try:
            return PALETTES["light" if not self.current_theme.dark else "dark"]
        except Exception:  # noqa: BLE001 - theme is not ready before mount
            return PALETTES["dark"]

    def watch_theme(self, old_theme: str, new_theme: str) -> None:
        if not self.is_running:
            return
        self._palette = self._resolve_palette()
        if self.snapshot is not None:
            self.refresh_snapshot()

    def _on_snapshot_interval(self) -> None:
        self.refresh_snapshot()

    def _make_feed(self) -> None:
        if self._demo:
            from tui.demo import demo_schedule
            from tui.observations import SyntheticFeed

            self._feed = SyntheticFeed(demo_schedule())
            return
        if self._events_path is not None:
            self._feed = JsonlFeed(self._events_path)
            return
        # The per-campaign file is known only once the campaign identity is read.
        self._feed = None

    def _ensure_feed(self, campaign_id: str | None) -> None:
        """Follow this campaign's own file; a reset cannot surface old events."""
        if self._demo or self._events_path is not None or not campaign_id:
            return
        campaign = str(campaign_id)
        if isinstance(self._feed, JsonlFeed) and self._feed_campaign == campaign:
            return
        source = paths.ROOT / EVENTS_DIR / f"{campaign}.jsonl"
        self._feed = JsonlFeed(source, campaign_id=campaign)
        self._feed_campaign = campaign

    # ------------------------------------------------------------------
    # Snapshot refresh
    # ------------------------------------------------------------------

    def refresh_snapshot(self) -> None:
        state, records, usage_rows = self._sources.read()
        if state is None and records:
            self._note_source(
                "Campaign state file unavailable - recorded operations shown without state-derived roles"
            )
        campaign_id = (state or {}).get("campaign", {}).get("id")
        self._ensure_feed(campaign_id)
        if isinstance(self._feed, JsonlFeed) and campaign_id:
            self._feed.campaign_id = str(campaign_id)

        snapshot = projector.build_snapshot(
            state,
            records,
            usage_rows,
            training=self._training_progress(),
            evaluation=self._evaluation_progress(),
            activity=self._last_activity or None,
            stage_started_at=self._stage_started,
            process_observed_recently=self._process_observed(),
        )
        self.snapshot = snapshot
        self._render_context()
        self._render_models(snapshot.model_rows)
        self._render_progress()
        self._render_training_status()
        self._apply_layout()
        self._detect_context_changes(snapshot)

    def _process_observed(self) -> bool:
        stamp = self._last_liveness
        if stamp is None:
            return False
        return (_now() - stamp).total_seconds() <= LIVENESS_SECONDS

    def _report_source_error(self, message: str) -> None:
        if self._last_error == message:
            return
        self._last_error = message
        self._append(
            _now(),
            f"Campaign source problem: {message}",
            style=f"bold {self._palette.error}",
            width_guard=False,
        )
        self._render_context()

    def _note_source(self, message: str) -> None:
        if self._source_note_sent:
            return
        self._source_note_sent = True
        self._append(_now(), message, style=self._palette.muted)

    # -- live progress objects -----------------------------------------

    def _training_progress(self) -> projector.TrainingProgress | None:
        state = self._training
        if not state:
            return None
        return projector.TrainingProgress(
            operation_id=state.get("operation_id") or "training",
            attempt=str(state.get("attempt") or "unknown"),
            steps=state.get("steps"),
            target=state.get("target"),
            elapsed_seconds=state.get("elapsed_seconds"),
            reward=state.get("reward"),
            success=state.get("success"),
            stale=self._progress_stale(state),
        )

    def _evaluation_progress(self) -> projector.EvaluationProgress | None:
        state = self._evaluation
        if not state:
            return None
        return projector.EvaluationProgress(
            operation_id=state.get("operation_id") or "evaluation",
            instrument=state.get("instrument") or "",
            official=bool(state.get("official")),
            panel_index=state.get("panel_index"),
            panel_total=state.get("panel_total"),
            completed_panels=state.get("completed_panels") or 0,
            episodes=state.get("episodes"),
            episodes_total=state.get("episodes_total"),
            elapsed_seconds=state.get("elapsed_seconds"),
            stale=self._progress_stale(state),
        )

    def _progress_stale(self, state: dict) -> bool:
        last = state.get("last_ts")
        if not isinstance(last, datetime):
            return True
        return (_now() - last).total_seconds() > PROGRESS_STALE_SECONDS

    # ------------------------------------------------------------------
    # Context band
    # ------------------------------------------------------------------

    def _render_context(self) -> None:
        snapshot = self.snapshot or projector.build_snapshot(None, [], [])
        width = max(self.size.width - 2, 40)
        lines = self._context_lines(snapshot, width)
        self._context_rows = len(lines)
        rendered = Text()
        for index, line in enumerate(lines):
            if index:
                rendered.append("\n")
            if isinstance(line, Text):
                rendered.append(line)
            else:
                rendered.append(_clean_text(line))
        self.query_one("#context", Static).update(rendered)

    def _context_budget(self) -> int:
        width = self.size.width
        if width < 60:
            return 4
        if width < 120 or self.size.height < 40:
            return 6
        return 8

    def _context_lines(
        self, snapshot: projector.CampaignSnapshot, width: int
    ) -> list[Text]:
        from tui.projector import campaign_age, stage_elapsed

        age = campaign_age(snapshot.started_at, _now())
        elapsed = stage_elapsed(snapshot.stage_started_at, _now())

        palette = self._palette
        gap = 3
        status_style = _status_style(snapshot.status, palette)
        left = Text("Autoresearch", style=f"bold {palette.heading}")
        left.append(" | ", style=palette.muted)
        left.append(snapshot.status, style=status_style)
        left.append(" | ", style=palette.muted)
        left.append("campaign ", style=palette.muted)
        left.append(snapshot.campaign_id[:13], style=palette.muted)
        right = Text(f"Campaign age {age}", style=palette.muted)
        right.append(" | ", style=palette.muted)
        right.append(f"Stage elapsed {elapsed}", style=palette.muted)
        if len(left.plain) + gap + len(right.plain) <= width:
            first = Text()
            first.append_text(left)
            first.append(" " * (width - len(left.plain) - len(right.plain)))
            first.append_text(right)
        else:
            first = left
        lines: list[Text] = [
            first if len(first.plain) <= width else Text(first.plain[:width])
        ]

        stage = Text()
        stage.append("Stage: ", style=palette.muted)
        if snapshot.stage_ids:
            stage.append(snapshot.stage_ids, style=f"bold {palette.accent}")
            stage.append(" | ", style=palette.muted)
        stage.append(
            snapshot.stage_text,
            style=f"bold {palette.warning}"
            if snapshot.terminal
            else f"bold {palette.accent}",
        )
        activity = Text()
        activity.append("Current activity: ", style=palette.muted)
        activity.append(
            snapshot.activity_text,
            style=palette.accent
            if "not observed" not in snapshot.activity_text
            else palette.muted,
        )
        if len(stage.plain) + gap + len(activity.plain) <= width:
            second = Text()
            second.append_text(stage)
            second.append(" " * (width - len(stage.plain) - len(activity.plain)))
            second.append_text(activity)
        else:
            second = stage
        lines.append(_fit_text(second, width))

        goal = snapshot.goal
        goal_line = Text()
        goal_line.append("Goal", style=palette.muted)
        if goal.target_percent is not None:
            goal_line.append(" >=", style=palette.muted)
            goal_line.append(
                f"{goal.target_percent:g}%", style=f"bold {palette.heading}"
            )
        elif goal.text:
            goal_line.append(f": {goal.text}", style=palette.text)
        else:
            goal_line.append(" unavailable", style=palette.muted)
        if goal.best_percent is not None:
            goal_line.append(" | best ", style=palette.muted)
            goal_line.append(f"{goal.best_percent:g}%", style=palette.text)
        else:
            goal_line.append(" | best not measured", style=palette.muted)
        if goal.gap_points is not None:
            gap_style = palette.error if goal.gap_points < 0 else palette.success
            goal_line.append(
                f" | {goal.gap_points:+.1f} pts", style=f"bold {gap_style}"
            )
        elif goal.gap_text:
            goal_line.append(f" | {goal.gap_text}", style=palette.muted)
        lines.append(_fit_text(goal_line, width))

        counters_line = Text()
        if snapshot.pending_text:
            counters_line.append(snapshot.pending_text, style=f"bold {palette.warning}")
            if snapshot.counters_text:
                counters_line.append(" | ", style=palette.muted)
        if snapshot.counters_text:
            counters_line.append(snapshot.counters_text, style=palette.muted)
        if counters_line.plain:
            lines.append(_fit_text(counters_line, width))

        excerpt_rows = self._context_budget() - 4
        leads: list[Text] = []
        question = _clean_text(snapshot.question) or _clean_text(snapshot.objective)
        if question:
            prefix = (
                f"Inquiry [{snapshot.question_source}]: "
                if snapshot.question
                else "Objective: "
            )
            take = 2 if width >= 120 and excerpt_rows >= 4 else 1
            leads.extend(
                _hang_styled(prefix, question, width, palette.warning, palette.text)[
                    :take
                ]
            )
        synthesis = _clean_text(snapshot.synthesis)
        if synthesis and excerpt_rows > len(leads):
            prefix = f"PI record {snapshot.synthesis_session or 'S?'}: "
            take = 2 if width >= 120 and excerpt_rows - len(leads) >= 3 else 1
            leads.extend(
                _hang_styled(prefix, synthesis, width, palette.pi, palette.text)[:take]
            )
        lines.extend(leads)

        usage = _clean_text(projector.usage_text(snapshot.usage))[:width]
        usage_text_obj = Text()
        usage_text_obj.append("Usage recorded", style=palette.muted)
        usage_text_obj.append(usage[len("Usage recorded") :], style=palette.text)
        lines.append(usage_text_obj)
        if snapshot.official_text:
            lines.append(
                Text(
                    _clean_text(snapshot.official_text)[:width],
                    style=f"bold {palette.success}",
                )
            )
        if self._last_error:
            lines.append(
                Text(
                    f"Attention: {self._last_error}"[:width],
                    style=f"bold {palette.error}",
                )
            )
        return lines[: self._context_budget() + 2]

    # ------------------------------------------------------------------
    # Models table
    # ------------------------------------------------------------------

    def _role_style(self, role: str) -> str:
        if role == "Working":
            return f"bold {self._palette.accent}"
        if role == "Best-known":
            return f"bold {self._palette.pi}"
        return self._palette.muted

    def _models_layout(self) -> str:
        if self.size.width < COMPACT_WIDTH or self.size.height < COMPACT_HEIGHT:
            return "compact"
        return "full"

    def _ensure_model_columns(self, table: DataTable, layout: str) -> None:
        if self._models_layout_key == layout:
            return
        self._models_layout_key = layout
        table.clear(columns=True)
        if layout == "full":
            table.add_columns(
                "PI-assigned role",
                "Candidate",
                "Training steps",
                "Reward (tr)",
                "Success (tr)",
                "Success (development) / source",
            )
        else:
            table.add_column("PI-assigned role", width=15)
            table.add_column("Candidate", width=24)
            table.add_column("Success (development) / source", width=30)

    def _render_models(self, rows: tuple) -> None:
        palette = self._palette
        table = self.query_one("#models", DataTable)
        layout = self._models_layout()
        self._ensure_model_columns(table, layout)
        table.clear()
        for row in rows:
            if row.roles:
                role_cell = Text()
                for index, role in enumerate(row.roles):
                    if index:
                        role_cell.append(" + ", style=palette.muted)
                    role_cell.append(role, style=self._role_style(role))
            else:
                role_cell = Text("-", style=palette.muted)
            if layout == "full":
                table.add_row(
                    role_cell,
                    Text(row.candidate_id, style=f"bold {palette.text}"),
                    _metric_cell(row.training_steps, "unavailable", palette.muted),
                    _metric_cell(row.reward_training, "unavailable", palette.muted),
                    _metric_cell(row.success_training, "unavailable", palette.muted),
                    _metric_cell(row.success_dev, "not measured", palette.muted),
                )
            else:
                table.add_row(
                    role_cell,
                    Text(row.candidate_id, style=f"bold {palette.text}"),
                    _metric_cell(row.success_dev, "not measured", palette.muted),
                )
        heading = Text()
        if not rows:
            heading.append("PI-assigned models", style=f"bold {palette.heading}")
            heading.append(" - none assigned", style=palette.muted)
            self.query_one("#models-heading", Static).update(heading)
            return
        heading.append("PI-assigned models", style=f"bold {palette.heading}")
        if self._attached:
            heading.append(f" ({len(rows)} assigned)", style=palette.muted)
        if layout == "compact":
            heading.append(
                " - compact: steps and training metrics hidden", style=palette.muted
            )
        budget = self._models_budget_rows()
        if len(rows) > budget:
            heading.append(
                " - scroll inside the table for every role", style=palette.muted
            )
        self.query_one("#models-heading", Static).update(heading)

    def _models_budget_rows(self) -> int:
        height = self.size.height
        reserved = self._context_rows + 1
        if not self._output_hidden:
            reserved += 2
        reserved += self._progress_rows + self._training_rows
        output_min = 0 if self._output_hidden else self._output_min_rows()
        return max(1, min(20, height - reserved - output_min))

    def _output_min_rows(self) -> int:
        height = self.size.height
        if height >= 40:
            return max(5, int(height * 0.55))
        return max(4, height // 2)

    # ------------------------------------------------------------------
    # Progress panel
    # ------------------------------------------------------------------

    def _render_progress(self) -> None:
        widget = self.query_one("#progress", Static)
        training = self._training_progress()
        evaluation = self._evaluation_progress()
        if training is None and evaluation is None:
            self._progress_rows = 0
            widget.display = False
            widget.update("")
            return
        width = max(24, self.size.width - 2)
        if training is not None:
            lines = self._training_lines(training, width)
        else:
            lines = self._evaluation_lines(evaluation, width)
        self._progress_rows = len(lines)
        widget.display = True
        rendered = Text()
        for index, line in enumerate(lines):
            if index:
                rendered.append("\n")
            if isinstance(line, Text):
                rendered.append_text(line)
            else:
                rendered.append(_clean_text(line))
        widget.update(rendered)

    def _progress_title(
        self, lead: str, lead_style: str, parts: list[str], stale: bool
    ) -> Text:
        palette = self._palette
        title = Text(lead, style=lead_style)
        for part in parts:
            title.append(" | ", style=palette.muted)
            title.append(part, style=palette.text)
        if stale:
            title.append(" | ", style=palette.muted)
            title.append("counter observation stale", style=f"bold {palette.error}")
        return title

    def _progress_bar_line(
        self, label: str, first: int, total: int | None, width: int
    ) -> Text:
        palette = self._palette
        line = Text(f"{label} {first:,}", style=f"bold {palette.accent}")
        if not total:
            line.append(" / target unavailable", style=palette.muted)
            return line
        line.append(f" / {total:,}", style=palette.muted)
        line.append("  [", style=palette.muted)
        progress = max(0.0, min(1.0, first / max(total, 1)))
        bar_width = max(8, min(width - 22, 60))
        filled = max(0, min(bar_width, round(bar_width * progress)))
        line.append("#" * filled, style=palette.success)
        line.append("-" * (bar_width - filled), style=palette.muted)
        line.append(f"] {round(progress * 100)}%", style=palette.text)
        return line

    def _training_lines(
        self, training: projector.TrainingProgress, width: int
    ) -> list[Text]:
        palette = self._palette
        parts = [f"Attempt {training.attempt}"]
        parts.append(_elapsed_text(training.elapsed_seconds, "Elapsed"))
        if isinstance(training.reward, (int, float)) and not isinstance(
            training.reward, bool
        ):
            parts.append(f"Reward {training.reward:.1f}")
        if isinstance(training.success, (int, float)) and not isinstance(
            training.success, bool
        ):
            parts.append(f"Success {round(training.success * 100)}%")
        title = self._progress_title(
            f"Training {training.operation_id}",
            f"bold {palette.accent}",
            parts,
            training.stale,
        )
        lines = [title]
        if training.steps is None:
            lines.append(
                Text("Steps: starting - no step count yet", style=palette.muted)
            )
            return lines
        lines.append(
            self._progress_bar_line("Steps", training.steps, training.target, width)
        )
        return lines

    def _evaluation_lines(
        self, evaluation: projector.EvaluationProgress, width: int
    ) -> list[Text]:
        palette = self._palette
        lead_style = (
            f"bold {palette.success}"
            if evaluation.official
            else f"bold {palette.accent}"
        )
        lead = (
            "Official assessment"
            if evaluation.official
            else f"Evaluation {evaluation.operation_id}"
        )
        parts: list[str] = []
        if evaluation.instrument:
            parts.append(evaluation.instrument)
        if evaluation.panel_total:
            parts.append(
                f"Panel {evaluation.panel_index or '?'}/{evaluation.panel_total}"
            )
        if evaluation.completed_panels:
            parts.append(
                "Completed panels "
                + (
                    f"{evaluation.completed_panels}/{evaluation.panel_total}"
                    if evaluation.panel_total
                    else str(evaluation.completed_panels)
                )
            )
        parts.append(
            _elapsed_text(
                evaluation.elapsed_seconds,
                "Panel elapsed" if evaluation.panel_total else "Elapsed",
            )
        )
        title = self._progress_title(lead, lead_style, parts, evaluation.stale)
        lines = [title]
        if evaluation.episodes is None and evaluation.episodes_total is None:
            lines.append(Text("Running - progress unavailable", style=palette.warning))
            return lines
        lines.append(
            self._progress_bar_line(
                "Episodes", evaluation.episodes or 0, evaluation.episodes_total, width
            )
        )
        return lines

    def _render_training_status(self) -> None:
        widget = self.query_one("#training", Static)
        snapshot = self.snapshot
        if (
            self._training is not None
            or snapshot is None
            or snapshot.last_training is None
        ):
            self._training_rows = 0
            widget.display = False
            widget.update("")
            return
        palette = self._palette
        proxy = snapshot.last_training
        line = Text()
        compact = self.size.width < COMPACT_WIDTH or self.size.height < COMPACT_HEIGHT
        line.append("Last " if compact else "Last training ", style=palette.muted)
        line.append(proxy.operation_id, style=f"bold {palette.accent}")
        line.append(" | proxy " if compact else " | best proxy ", style=palette.muted)
        line.append(proxy.candidate, style=palette.text)
        if not compact:
            line.append(" | steps ", style=palette.muted)
            line.append(proxy.steps, style=palette.text)
        line.append(" | rwd " if compact else " | reward ", style=palette.muted)
        line.append(proxy.reward, style=palette.text)
        line.append(" | succ " if compact else " | success ", style=palette.muted)
        line.append(proxy.success, style=palette.text)
        self._training_rows = 1
        widget.display = True
        widget.update(_fit_text(line, max(20, self.size.width - 2)))

    # ------------------------------------------------------------------
    # Clock-driven animations (elapsed counters and stale labels only)
    # ------------------------------------------------------------------

    def tick_clock(self) -> None:
        self.tick_clock_active = getattr(self, "tick_clock_active", 0) + 1
        if self._training or self._evaluation:
            self._render_progress()
        if self.snapshot is not None:
            self._render_context()

    # ------------------------------------------------------------------
    # Output appends
    # ------------------------------------------------------------------

    def _output(self) -> OutputLog:
        return self.query_one("#output", OutputLog)

    def _append(
        self,
        stamp: datetime | None,
        text: str,
        *,
        style: str | None = None,
        width_guard: bool = True,
    ) -> None:
        if stamp is None:
            stamp = _now()
        prefix = f"{_ts(stamp)} "
        width = self._output_width()
        if width_guard and len(prefix) + len(text) > width:
            lines = _hang(prefix, _clean_text(text), width)
        else:
            lines = [f"{prefix}{_clean_text(text)}"]
        self._write(stamp, lines, style)
        self._render_reading()

    def _append_block(
        self, stamp: datetime | None, lines: list[str], style: str | None = None
    ) -> None:
        """Append pre-rendered lines, wrapped to the log width."""
        width = self._output_width()
        wrapped: list[str] = []
        for line in lines:
            wrapped.extend(_hang("", _clean_text(line), width))
        self._write(stamp, wrapped or [""], style)
        self._render_reading()

    def _hang_block(
        self,
        prefix: str,
        text: str,
        style: str | None = None,
        prefix_style: str | None = None,
    ) -> None:
        lines = _hang(prefix, _clean_text(text), self._output_width())
        if style is None and prefix_style:
            texts: list[Text] = []
            for index, line in enumerate(lines):
                item = Text(_clean_text(line))
                if index == 0 and len(line) >= len(prefix):
                    item.stylize(prefix_style, 0, len(prefix))
                texts.append(item)
            self._output().append_texts(texts)
            self._render_reading()
            return
        self._write(None, lines, style)
        self._render_reading()

    def _write(
        self, stamp: datetime | None, lines: list[str], style: str | None
    ) -> None:
        palette = self._palette
        stamp_text = _ts(stamp) if stamp is not None else ""
        prefix_len = len(stamp_text) + 1 if stamp_text else 0
        texts: list[Text] = []
        for line in lines:
            text = _clean_text(line)
            item = Text(text)
            if prefix_len and text.startswith(f"{stamp_text} "):
                item.stylize(palette.muted, 0, prefix_len)
                if style:
                    item.stylize(style, prefix_len, len(text))
            elif style:
                item.stylize(style, 0, len(text))
            texts.append(item)
        self._output().append_texts(texts)

    def _output_width(self) -> int:
        # The log's real content region is narrower than the screen: the
        # screen has horizontal padding and the vertical scrollbar takes
        # columns. Derive the width from the log itself so pre-wrapped lines
        # never exceed the viewport and get clipped.
        try:
            width = self.query_one("#output", OutputLog).scrollable_content_region.width
        except Exception:  # noqa: BLE001 - layout not ready yet
            width = 0
        if not width:
            width = self.size.width - 4
        return max(20, width)

    def _attach_output(self) -> None:
        snapshot = self.snapshot
        if snapshot is None or self._attached:
            return
        self._attached = True
        palette = self._palette
        now = _now()
        self._append(
            now,
            f"Autoresearch report attached to campaign {snapshot.campaign_id} "
            f"- {snapshot.status}",
        )
        if self._demo:
            self._append(
                now,
                "Demonstration mode: every value here is synthetic.",
                style=f"bold {palette.error}",
            )
        feed_ready = isinstance(self._feed, JsonlFeed) and self._feed.path.exists()
        if not self._demo and not feed_ready:
            self._append(
                now,
                "No structured observation feed is available: live PI messages and "
                "live execution progress are unavailable. Recorded campaign state, "
                "durable operational history and recorded usage follow.",
                style=palette.muted,
            )
        question = _clean_text(snapshot.question) or _clean_text(snapshot.objective)
        if question:
            prefix = (
                f"Inquiry [{snapshot.question_source}]: "
                if snapshot.question
                else "Objective: "
            )
            self._hang_block(prefix, question, prefix_style=f"bold {palette.warning}")
        if snapshot.synthesis:
            self._hang_block(
                f"PI record {snapshot.synthesis_session or 'S?'}: ",
                _clean_text(snapshot.synthesis),
                prefix_style=f"bold {palette.pi}",
            )
        assignments = projector.role_assignment_text(snapshot)
        if assignments:
            self._append(now, "Model assignments at attachment:", style=palette.muted)
            self._append_block(now, assignments.splitlines(), style=palette.muted)
        self._append_timeline()

    def _append_timeline(self) -> None:
        snapshot = self.snapshot
        if snapshot is None:
            return
        palette = self._palette
        for entry in snapshot.timeline:
            style = None
            if entry.kind == "error":
                style = f"bold {palette.error}"
            elif entry.kind == "pending":
                style = palette.warning
            elif entry.kind in {"assessment", "validation"}:
                style = palette.success
            prefix = "pending" if entry.timestamp is None else _ts(entry.timestamp)
            self._append_block(None, [f"[{prefix}] {entry.text}"], style=style)

    def _detect_context_changes(self, snapshot: projector.CampaignSnapshot) -> None:
        self._attach_output()
        signature = (
            snapshot.question,
            snapshot.synthesis,
            snapshot.synthesis_session,
            projector.role_assignment_text(snapshot),
            snapshot.official_text,
            snapshot.status,
        )
        previous = self._observed_signature
        self._observed_signature = signature
        if previous is None:
            return
        now = _now()
        palette = self._palette
        if signature[0] != previous[0] and signature[0]:
            source = (
                f"inquiry [{snapshot.question_source}]"
                if snapshot.question
                else "objective"
            )
            self._append(
                now, f"Inquiry question updated ({source}):", style=palette.muted
            )
            self._hang_block("", signature[0])
        if (signature[1], signature[2]) != (previous[1], previous[2]) and signature[1]:
            self._append(
                now,
                f"PI synthesis updated ({snapshot.synthesis_session}):",
                style=palette.muted,
            )
            self._hang_block("", signature[1])
        if signature[3] != previous[3] and signature[3]:
            self._append(now, "Model assignments changed:", style=palette.muted)
            self._append_block(now, signature[3].splitlines(), style=palette.muted)
        if signature[4] != previous[4] and signature[4]:
            self._append(now, signature[4], style=f"bold {palette.success}")
        if not snapshot.terminal and previous[5] == snapshot.status:
            return

    # ------------------------------------------------------------------
    # Observation feed
    # ------------------------------------------------------------------

    def drain_feed(self) -> None:
        feed = self._feed
        if feed is None:
            return
        events = feed.poll()
        if isinstance(feed, JsonlFeed) and feed.rejected:
            self._note_feed_error(feed.rejected)
        self._process_events(events)

    def _note_feed_error(self, message: str) -> None:
        if self._last_error == message:
            return
        self._last_error = message
        self._append(
            _now(),
            f"Observation feed: {message}",
            style=f"bold {self._palette.error}",
        )

    def _process_events(self, events: list[Observation]) -> None:
        for event in events:
            handler = getattr(self, f"_event_{event.kind}", None)
            if handler is None:
                continue
            handler(event)
        self._apply_layout()

    def _event_liveness(self, event: Observation) -> None:
        self._last_liveness = event.ts or _now()

    def _event_session_start(self, event: Observation) -> None:
        stamp = event.ts
        started = event.fields.get("stage_started_at")
        if isinstance(started, str):
            stamp = projector.parse_timestamp(started) or stamp
        self._stage_started = stamp
        if self.snapshot is not None:
            self.snapshot.stage_started_at = stamp

    def _event_activity(self, event: Observation) -> None:
        label = _clean_text(event.fields.get("label") or "")
        if not label or label == self._last_activity:
            return
        self._last_activity = label
        self._append(event.ts, f"activity: {label}", style=self._palette.accent)

    def _event_pi_message(self, event: Observation) -> None:
        raw = _clean_text(event.fields.get("text") or "")
        if not raw:
            return
        session = _clean_text(event.fields.get("session_id") or "")
        turn = event.fields.get("turn")
        final = bool(event.fields.get("final", True))
        shown = self._pi_stream.get(turn, "") if turn is not None else ""
        # A partial carries only the text added since the previous partial.
        text = raw if final or turn is None else shown + raw
        fingerprint = (session, text)
        if turn is None:
            # Whole-message events (demo fixtures and replayed finals).
            if fingerprint in self._pi_seen:
                return
            self._pi_seen.append(fingerprint)
            stamp = event.ts or _now()
            prefix = (
                f"{_ts(stamp)} PI ({session}): " if session else f"{_ts(stamp)} PI: "
            )
            self._hang_block(prefix, text, prefix_style=f"bold {self._palette.pi}")
            return
        if final and fingerprint in self._pi_seen:
            return
        stamp = event.ts or _now()
        label = f"{_ts(stamp)} PI ({session}): " if session else f"{_ts(stamp)} PI: "
        if not text.startswith(shown):
            shown = ""
        addition = text[len(shown) :]
        if shown:
            addition = addition.lstrip()
        if addition.strip():
            if shown:
                # Continue the message under the same gutter, no repeated stamp.
                self._hang_block(" " * len(label), addition)
            else:
                self._hang_block(
                    label, addition, prefix_style=f"bold {self._palette.pi}"
                )
        self._pi_stream[turn] = text
        if final:
            self._pi_seen.append(fingerprint)
            self._pi_stream.pop(turn, None)

    def _event_tool(self, event: Observation) -> None:
        name = _clean_text(event.fields.get("name") or "tool")
        detail = _display_text(_clean_text(event.fields.get("detail") or ""))
        line = f"tool {name}"
        if detail:
            line += f": {detail}"
        self._append(event.ts, line, style=self._palette.tool)

    def _append_console(self, stamp: datetime | None, text: str, scope: str) -> None:
        """Render one console card or line with per-line semantic styles."""
        palette = self._palette
        width = self._output_width()
        stamp_text = _ts(stamp) if stamp is not None else ""
        first_prefix = f"{stamp_text} " if stamp_text else ""
        indent = " " * len(first_prefix)
        base_style = _scope_style(scope, palette)
        lines = _display_text(text).splitlines() or [""]
        is_card = lines[0].strip().startswith("===") and lines[0].strip().endswith(
            "==="
        )
        rendered: list[Text] = []
        for index, raw in enumerate(lines):
            stripped = raw.strip()
            if stripped.startswith("===") and stripped.endswith("==="):
                body_style = (
                    base_style
                    if scope.casefold() in {"error", "warning"}
                    else f"bold {palette.accent}"
                )
            elif stripped in SECTION_HEADINGS:
                body_style = f"bold {palette.section}"
            elif raw.startswith(("Phase: ", "Campaign: ")):
                body_style = palette.accent
            elif is_card:
                body_style = (
                    base_style
                    if scope.casefold() in {"error", "warning"}
                    else palette.text
                )
            else:
                body_style = base_style
            prefix = first_prefix if index == 0 else indent
            rendered.extend(
                _hang_styled(
                    prefix,
                    raw,
                    width,
                    prefix_style=palette.muted,
                    body_style=body_style,
                )
            )
        if rendered:
            self._output().append_texts(rendered)
            self._render_reading()

    def _event_console_line(self, event: Observation) -> None:
        text = _clean_text(event.fields.get("text") or "")
        scope = _clean_text(event.fields.get("scope") or "")
        if not text:
            return
        self._append_console(event.ts, text, scope)

    def _event_training_progress(self, event: Observation) -> None:
        attempt = event.fields.get("attempt")
        self._training = {
            "operation_id": str(event.fields.get("operation_id") or ""),
            "attempt": attempt if attempt not in (None, "") else "unknown",
            "steps": event.fields.get("steps"),
            "target": event.fields.get("target"),
            "elapsed_seconds": event.fields.get("elapsed_seconds"),
            "reward": event.fields.get("ep_rew_mean"),
            "success": event.fields.get("training_success"),
            "last_ts": event.ts or _now(),
        }
        self._render_progress()
        self._render_training_status()
        self._apply_layout()

    def _event_eval_progress(self, event: Observation) -> None:
        self._evaluation = {
            "operation_id": str(event.fields.get("operation_id") or ""),
            "instrument": str(event.fields.get("instrument") or ""),
            "official": bool(event.fields.get("official")),
            "panel_index": event.fields.get("panel_index"),
            "panel_total": event.fields.get("panel_total"),
            "completed_panels": int(event.fields.get("completed_panels") or 0),
            "episodes": event.fields.get("episodes"),
            "episodes_total": event.fields.get("episodes_total"),
            "elapsed_seconds": event.fields.get("elapsed_seconds"),
            "last_ts": event.ts or _now(),
        }
        self._render_progress()

    def _event_execution_end(self, event: Observation) -> None:
        operation = _clean_text(event.fields.get("operation_id") or "")
        status = _clean_text(event.fields.get("status") or "ended")
        text = _clean_text(event.fields.get("text") or "")
        style = (
            f"bold {self._palette.success}"
            if status == "completed"
            else f"bold {self._palette.warning}"
        )
        self._append(event.ts, text or f"{operation} execution {status}", style=style)
        if self._training and self._training.get("operation_id") == operation:
            self._training = None
        if self._evaluation and self._evaluation.get("operation_id") == operation:
            self._evaluation = None
        self._render_progress()
        self._render_training_status()
        self._apply_layout()

    # ------------------------------------------------------------------
    # Reading status
    # ------------------------------------------------------------------

    def _on_follow(self, following: bool, missed: int) -> None:
        self._render_reading()

    def _render_reading(self) -> None:
        if self._output_hidden:
            return
        widget = self.query_one("#reading", Static)
        out = self._output()
        if self.size.width < 80:
            text = (
                "Following | Tab: models | End: live"
                if out.following
                else f"Reading history - {out.missed} newer | End: live"
            )
        elif self.size.width < 110:
            text = (
                "Following live | Wheel/PgUp/PgDn: history | Tab: models | End: live"
                if out.following
                else f"Reading history - {out.missed} newer | End: live | Ctrl+Q: close"
            )
        elif out.following:
            text = (
                "Following live output | Wheel / PgUp / PgDn: history | "
                "Tab: model table | End: live | Ctrl+Q: close"
            )
        else:
            text = (
                f"Reading history - {out.missed} newer entries | "
                "End: live | Ctrl+Q: close"
            )
        widget.update(
            Text(
                text[: max(20, self.size.width - 2)],
                style=self._palette.muted,
            )
        )

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _apply_layout(self) -> None:
        size = self.size
        too_small = size.width < MIN_COLUMNS or size.height < MIN_ROWS
        overlay = self.query_one("#too-small", Static)
        overlay.display = too_small
        if too_small:
            overlay.update(
                Text(
                    f"Terminal too small - need {MIN_COLUMNS}x{MIN_ROWS}",
                    style=f"bold {self._palette.warning}",
                )
            )
            return
        compact = size.width < COMPACT_WIDTH or size.height < COMPACT_HEIGHT
        self._output_hidden = compact
        output = self.query_one("#output", OutputLog)
        output.display = not compact
        self.query_one("#output-heading", Static).display = not compact
        self.query_one("#reading", Static).display = not compact
        if compact and self.focused is output:
            self.query_one("#models", DataTable).focus()
        self._render_output_heading()
        table = self.query_one("#models", DataTable)
        rows = len(table.rows)
        budget = self._models_budget_rows()
        # The DataTable renders its column header inside this height, so the
        # viewport needs the header row plus the visible data rows.
        visible_rows = max(1, min(budget, rows)) if rows else 0
        table.styles.max_height = visible_rows + 1
        self._render_reading()

    def _render_output_heading(self) -> None:
        if self._output_hidden:
            return
        width = max(12, self.size.width - 2)
        heading = Text("Output", style=f"bold {self._palette.heading}")
        heading.append(" " + "-" * (width - 8), style=self._palette.muted)
        self.query_one("#output-heading", Static).update(heading[:width])

    def on_resize(self) -> None:
        if not self.is_running or self.snapshot is None:
            return
        self.refresh_snapshot()

    def refresh_and_layout(self) -> None:
        self.refresh_snapshot()
