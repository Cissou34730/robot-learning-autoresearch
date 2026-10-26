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
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.geometry import Size
from textual.widget import Widget
from textual.widgets import DataTable, Input, Static

from runner import paths
from runner import reporting as console
from tui import projector
from tui.event_log import EventLog, FilterScreen, RawEventScreen
from tui.events import (
    CampaignEventFeed,
    legacy_path_for,
    synthesize_history,
    typed_path_for,
)
from tui.observations import JsonlFeed, Observation
from tui.timeline import TimelineReducer

MIN_COLUMNS = 48
MIN_ROWS = 16
SNAPSHOT_SECONDS = 15.0
TICK_SECONDS = 15.0
FEED_SECONDS = 1.0
COMPACT_WIDTH = 100
COMPACT_HEIGHT = 30
LIVENESS_SECONDS = 300.0
PROGRESS_STALE_SECONDS = 300.0


# The log is display-only. These tokens are the single palette used by the
# report; CSS picks its structural colours from the active Textual theme.
@dataclass(frozen=True)
class Palette:
    """Semantic colour tokens for one terminal background."""

    name: str
    background: str
    log_bg: str
    column_bg: str
    text: str
    muted: str
    heading: str
    accent: str
    success: str
    warning: str
    error: str
    pi: str
    pi_text: str
    tool: str
    section: str
    result: str


PALETTES: dict[str, Palette] = {
    "dark": Palette(
        name="dark",
        background="#1e1e1e",
        log_bg="#000000",
        column_bg="#262626",
        text="#e6e6e6",
        muted="#b0b0b0",
        heading="#f0f0f0",
        accent="#7cc7ff",
        success="#6ee7a8",
        warning="#ffd166",
        error="#ff8a9b",
        pi="#e0aaff",
        pi_text="#7de3e8",
        tool="#b8c0cc",
        section="#d7d7d7",
        result="#6ee7a8",
    ),
    "light": Palette(
        name="light",
        background="#f5f5f5",
        log_bg="#ffffff",
        column_bg="#e2e2e2",
        text="#1a1a1a",
        muted="#4a4a4a",
        heading="#111111",
        accent="#0b5fa5",
        success="#0f6b3d",
        warning="#8a5a00",
        error="#b3261e",
        pi="#6b2d8f",
        pi_text="#00656b",
        tool="#3f4a5a",
        section="#2a2a2a",
        result="#0f6b3d",
    ),
}

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


def _start_time(stamp: datetime | None, now: datetime) -> str:
    if stamp is None:
        return "unavailable"
    local = stamp.astimezone()
    today = now.astimezone()
    if local.year != today.year:
        return local.strftime("%Y-%m-%d %H:%M:%S")
    return local.strftime(
        "%H:%M:%S" if local.date() == today.date() else "%d %b %H:%M:%S"
    )


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


class CampaignSources:
    """Reads the durable campaign files selected by the campaign root."""

    def __init__(self, campaign_root: Path | None = None) -> None:
        self._campaign_root = Path(campaign_root) if campaign_root else None

    def read(self) -> tuple[dict | None, list[dict], list[dict]]:
        from tui.sources import read_json, read_jsonl

        if self._campaign_root is not None:
            # Explicit per-campaign root (operator console tabs): frozen at
            # construction, never rebound through runner.paths globals.
            root = self._campaign_root
            state_path = root / "runner" / "state" / "research_state.json"
            results_path = root / "campaigns" / "results.jsonl"
            usage_dir = root / "reports" / "session_usage"
        else:
            state_path = paths.STATE_PATH
            results_path = paths.RESULTS_PATH
            usage_dir = paths.ROOT / "reports" / "session_usage"
        state = read_json(state_path)
        records = read_jsonl(results_path)
        usage_rows = []
        campaign_id = (state or {}).get("campaign", {}).get("id")
        if campaign_id:
            usage_rows = read_jsonl(usage_dir / f"{campaign_id}.jsonl")
        return state, records, usage_rows


class DemoSources:
    """Synthetic material so the demo never touches real campaign files."""

    def read(self) -> tuple[dict | None, list[dict], list[dict]]:
        args = _demo_args()
        return args


def _demo_args():
    from tui.demo import demo_snapshot_args

    return demo_snapshot_args()


REPORT_CSS = """
Screen {
    background: $surface;
    color: $text;
}
CampaignPanel {
    width: 100%;
    height: 100%;
    padding: 0 1;
}
Screen > .screen--selection {
    color: $foreground;
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
#now {
    height: 1;
    color: $text;
}
#log-search {
    display: none;
    height: 1;
    margin-bottom: 1;
    background: $surface;
    color: $text;
    border: none;
}
#output {
    height: 1fr;
    padding: 0;
    background: $background;
    color: $text;
    background-tint: transparent;
    scrollbar-size-vertical: 1;
}
EventLog > .tree--label {
    color: $text;
}
EventLog > .tree--guides,
EventLog > .tree--guides-hover,
EventLog > .tree--guides-selected {
    color: $text-muted;
}
EventLog > .tree--highlight,
EventLog > .tree--highlight-line {
    background: transparent;
    text-style: none;
}
EventLog > .tree--cursor {
    background: transparent;
    color: $text;
    text-style: none;
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


class CampaignPanel(Widget):
    """One campaign's complete read-only report view.

    ``CampaignPanel`` owns every rendering, refresh and layout behaviour so it
    can also be embedded in the multi-campaign operator console (one panel per
    campaign tab). The :class:`CampaignReport` application at the bottom of
    this module composes exactly one panel and provides the app-level keys.
    """

    def __init__(
        self,
        *,
        sources: CampaignSources | DemoSources | None = None,
        events_path: Path | None = None,
        demo: bool = False,
        campaign_root: Path | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._demo = demo
        self._campaign_root = Path(campaign_root) if campaign_root else None
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
        self._feed_campaign: str | None = None
        self._campaign_id: str | None = None
        self._timeline = TimelineReducer()
        self._history_events: list[Observation] = []
        self._feed_mode = ""
        self._log_query = ""
        self._log_categories: set[str] = set()
        self._search_visible = False
        self._now_rows = 0

    @property
    def _view_size(self) -> Size:
        """This view's on-screen footprint including its own padding.

        The panel keeps the padding that used to sit on the Screen, so adding
        it back reproduces the pre-refactor application size exactly at the
        same terminal dimensions; every layout threshold below relies on that.
        """
        padding = self.styles.padding
        return Size(
            self.size.width + padding.left + padding.right,
            self.size.height + padding.top + padding.bottom,
        )

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
        yield Static("", id="now")
        yield Input(placeholder="Search events...", id="log-search")
        yield EventLog(self._log_styles(), id="output")
        yield Static("", id="reading")
        yield Static("Terminal too small - need 48x16", id="too-small")

    def on_mount(self) -> None:
        self._palette = self._resolve_palette()
        event_log = self.query_one("#output", EventLog)
        event_log._styles = self._log_styles()
        event_log.on_follower(self._on_follow)
        self._apply_log_background()
        self._make_feed()
        self.refresh_snapshot()
        self.drain_feed()
        self.set_interval(SNAPSHOT_SECONDS, self._on_snapshot_interval)
        self.set_interval(TICK_SECONDS, self.tick_clock)
        self.set_interval(FEED_SECONDS, self.drain_feed)
        self._apply_layout()

    def _resolve_palette(self) -> Palette:
        try:
            return PALETTES["light" if not self.app.current_theme.dark else "dark"]
        except Exception:  # noqa: BLE001 - theme is not ready before mount
            return PALETTES["dark"]

    def apply_theme(self) -> None:
        """Re-resolve palette colours; the App forwards theme changes here."""
        if not self.is_mounted:
            return
        self._palette = self._resolve_palette()
        self._apply_log_background()
        if self.snapshot is not None:
            self.refresh_snapshot()

    def _apply_log_background(self) -> None:
        """Keep the reading area on its base colour and the time gutter distinct."""
        event_log = self.query_one("#output", EventLog)
        event_log.styles.background = self._palette.log_bg

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

    def _log_styles(self) -> dict[str, str]:
        palette = self._palette
        return {
            "text": palette.text,
            "muted": palette.muted,
            "heading": palette.heading,
            "accent": palette.accent,
            "success": palette.success,
            "warning": palette.warning,
            "error": palette.error,
            "pi": palette.pi_text,
            "session": palette.pi,
            "tool": palette.tool,
            "special_tool": palette.accent,
            "result": palette.pi,
            "section": palette.section,
            "column_bg": palette.column_bg,
        }

    def _switch_campaign(self, campaign_id: str | None) -> None:
        """Clear campaign-scoped display state when a new campaign appears."""
        campaign = str(campaign_id) if campaign_id else ""
        if not campaign:
            return
        previous = self._campaign_id
        if previous is not None and campaign != previous:
            self._reset_campaign_view()
        self._campaign_id = campaign

    def _reset_campaign_view(self) -> None:
        self.query_one("#output", EventLog).reset_campaign()
        self._timeline.clear()
        self._history_events = []
        self._feed_mode = ""
        self._log_query = ""
        self._log_categories = set()
        self._search_visible = False
        self._now_rows = 0
        self.query_one("#now", Static).update("")
        self.snapshot = None
        self._attached = False
        self._context_rows = 0
        self._progress_rows = 0
        self._training_rows = 0
        self._training = None
        self._evaluation = None
        self._stage_started = None
        self._last_activity = ""
        self._last_session = ""
        self._last_liveness = None
        self._observed_signature = None
        self._last_error = ""
        self._source_note_sent = False
        if not self._demo and self._events_path is None:
            self._feed = None
            self._feed_campaign = None

    def _ensure_feed(self, campaign_id: str | None) -> None:
        """Follow this campaign's own file; a reset cannot surface old events."""
        if self._demo or self._events_path is not None or not campaign_id:
            return
        campaign = str(campaign_id)
        if (
            isinstance(self._feed, CampaignEventFeed)
            and self._feed_campaign == campaign
        ):
            return
        self._feed = CampaignEventFeed(
            typed_path_for(campaign, self._campaign_root),
            legacy_path_for(campaign, self._campaign_root),
            campaign_id=campaign,
        )
        self._feed_campaign = campaign
        self._feed_mode = ""

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
        self._switch_campaign(campaign_id)
        self._ensure_feed(campaign_id)
        if isinstance(self._feed, JsonlFeed) and campaign_id:
            self._feed.campaign_id = str(campaign_id)
        if isinstance(self._feed, CampaignEventFeed) and campaign_id:
            self._feed.campaign_id = str(campaign_id)
            self._feed.typed.campaign_id = str(campaign_id)
            self._feed.legacy.campaign_id = str(campaign_id)
        self._history_events = synthesize_history(state, records, usage_rows)
        for event in self._history_events:
            self._timeline.ingest(event)

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
        self._render_log()
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
        width = max(self._view_size.width - 2, 40)
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
        width = self._view_size.width
        if width < 60:
            return 4
        if width < 120 or self._view_size.height < 40:
            return 6
        return 8

    def _context_lines(
        self, snapshot: projector.CampaignSnapshot, width: int
    ) -> list[Text]:
        from tui.projector import campaign_age, stage_elapsed

        now = _now()
        age = campaign_age(snapshot.started_at, now, snapshot.ended_at)
        elapsed = stage_elapsed(snapshot.stage_started_at, now, snapshot.ended_at)

        palette = self._palette
        gap = 3
        status_style = _status_style(snapshot.status, palette)
        left = Text("Autoresearch", style=f"bold {palette.heading}")
        left.append(" | ", style=palette.muted)
        left.append(snapshot.status, style=status_style)
        left.append(" | ", style=palette.muted)
        left.append("campaign ", style=palette.muted)
        left.append(snapshot.campaign_id[:13], style=palette.muted)
        campaign_time = Text(f"Campaign age {age} (started ", style=palette.muted)
        campaign_time.append(_start_time(snapshot.started_at, now), style=palette.text)
        campaign_time.append(")", style=palette.muted)
        stage_time = Text(f"Stage elapsed {elapsed} (started ", style=palette.muted)
        stage_time.append(
            _start_time(snapshot.stage_started_at, now), style=palette.text
        )
        stage_time.append(")", style=palette.muted)
        right = campaign_time.copy()
        right.append(" | ", style=palette.muted)
        right.append_text(stage_time)
        timing_rows: list[Text] = []
        if len(left.plain) + gap + len(right.plain) <= width:
            first = Text()
            first.append_text(left)
            first.append(" " * (width - len(left.plain) - len(right.plain)))
            first.append_text(right)
        else:
            first = left
            timing_rows = (
                [right] if len(right.plain) <= width else [campaign_time, stage_time]
            )
        lines: list[Text] = [
            first if len(first.plain) <= width else Text(first.plain[:width])
        ]
        lines.extend(_fit_text(row, width) for row in timing_rows)

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

        excerpt_rows = max(0, self._context_budget() - 4 - len(timing_rows))
        leads: list[Text] = []
        question = _clean_text(snapshot.question) or _clean_text(snapshot.objective)
        if question and excerpt_rows:
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
        if (
            self._view_size.width < COMPACT_WIDTH
            or self._view_size.height < COMPACT_HEIGHT
        ):
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
        height = self._view_size.height
        reserved = self._context_rows + 1
        if not self._output_hidden:
            reserved += 2 + self._now_rows + (1 if self._search_visible else 0)
        reserved += self._progress_rows + self._training_rows
        output_min = 0 if self._output_hidden else self._output_min_rows()
        return max(1, min(20, height - reserved - output_min))

    def _output_min_rows(self) -> int:
        height = self._view_size.height
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
        width = max(24, self._view_size.width - 2)
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
        elif isinstance(training.success, str) and training.success:
            parts.append(training.success[:1].upper() + training.success[1:])
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
        compact = (
            self._view_size.width < COMPACT_WIDTH
            or self._view_size.height < COMPACT_HEIGHT
        )
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
        widget.update(_fit_text(line, max(20, self._view_size.width - 2)))

    def _render_log(self) -> None:
        event_log = self.query_one("#output", EventLog)
        event_log._styles = self._log_styles()
        roots, matches = self._timeline.view(
            query=self._log_query,
            categories=self._log_categories,
        )
        event_log.set_view(roots, active_ids=self._timeline.active_ids())
        now = Text(self._timeline.now_text, style=self._palette.accent)
        self.query_one("#now", Static).update(
            _fit_text(now, max(20, self._view_size.width - 2))
        )
        self._now_rows = 1
        heading = Text("Events", style=f"bold {self._palette.heading}")
        if matches:
            heading.append(f" ({matches})", style=self._palette.muted)
        if self._log_query:
            heading.append(f" | search: {self._log_query}", style=self._palette.warning)
        if self._log_categories:
            heading.append(
                " | filter: " + ", ".join(sorted(self._log_categories)),
                style=self._palette.warning,
            )
        self.query_one("#output-heading", Static).update(
            _fit_text(heading, max(12, self._view_size.width - 2))
        )

    # ------------------------------------------------------------------
    # Clock-driven animations (elapsed counters and stale labels only)
    # ------------------------------------------------------------------

    def tick_clock(self) -> None:
        self.tick_clock_active = getattr(self, "tick_clock_active", 0) + 1
        if self._training or self._evaluation:
            self._render_progress()
        if self.snapshot is not None:
            self._render_context()
            self._render_log()

    # ------------------------------------------------------------------
    # Output appends
    # ------------------------------------------------------------------

    def _output(self) -> EventLog:
        return self.query_one("#output", EventLog)

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
        severity = "info"
        scope = "info"
        if style:
            if "error" in style:
                severity = scope = "error"
            elif "warning" in style:
                severity = scope = "warning"
        event = Observation(
            kind="console_line",
            ts=stamp,
            fields={"text": _display_text(_clean_text(text)), "scope": scope},
            event_id=f"internal:{stamp.isoformat()}:{hash(text)}",
            scope=scope,
            severity=severity,
        )
        self._timeline.ingest(event)
        self._render_log()
        self._render_reading()

    def _append_block(
        self, stamp: datetime | None, lines: list[str], style: str | None = None
    ) -> None:
        self._append(stamp, "\n".join(lines), style=style)

    def _hang_block(
        self,
        prefix: str,
        text: str,
        style: str | None = None,
        prefix_style: str | None = None,
    ) -> None:
        self._append(None, f"{prefix}{_clean_text(text)}", style=style)

    def _write(
        self, stamp: datetime | None, lines: list[str], style: str | None
    ) -> None:
        self._append(stamp, "\n".join(lines), style=style)

    def _output_width(self) -> int:
        # The log's real content region is narrower than the screen: the
        # screen has horizontal padding and the vertical scrollbar takes
        # columns. Derive the width from the log itself so pre-wrapped lines
        # never exceed the viewport and get clipped.
        try:
            width = self.query_one("#output", EventLog).scrollable_content_region.width
        except Exception:  # noqa: BLE001 - layout not ready yet
            width = 0
        if not width:
            width = self._view_size.width - 4
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
        feed_ready = False
        if isinstance(self._feed, CampaignEventFeed):
            feed_ready = (
                self._feed.typed_path.exists() or self._feed.legacy_path.exists()
            )
        elif isinstance(self._feed, JsonlFeed):
            feed_ready = self._feed.path.exists()
        if not self._demo and not feed_ready:
            self._append(
                now,
                "No structured observation feed is available: live PI messages and "
                "live execution progress are unavailable. Recorded campaign state, "
                "durable operational history and recorded usage follow.",
                style=palette.muted,
            )

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
        mode = getattr(feed, "mode", "")
        if mode and self._feed_mode and mode != self._feed_mode:
            self._timeline.clear()
            for event in self._history_events:
                self._timeline.ingest(event)
        if mode:
            self._feed_mode = mode
        rejected = getattr(feed, "rejected", None)
        if rejected:
            self._note_feed_error(rejected)
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
            self._timeline.ingest(event)
            handler = getattr(self, f"_event_{event.kind}", None)
            if handler is None:
                continue
            handler(event)
        self._render_log()
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

    def _event_training_progress(self, event: Observation) -> None:
        attempt = event.fields.get("attempt")
        self._training = {
            "operation_id": str(event.fields.get("operation_id") or ""),
            "attempt": attempt if attempt not in (None, "") else "unknown",
            "steps": event.fields.get("steps"),
            "target": event.fields.get("target"),
            "elapsed_seconds": event.fields.get("elapsed_seconds"),
            "reward": event.fields.get("ep_rew_mean"),
            "success": event.fields.get("scenario_metric")
            or event.fields.get("training_success"),
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

    # ------------------------------------------------------------------
    # Log actions
    # ------------------------------------------------------------------

    def action_search_log(self) -> None:
        if self._output_hidden:
            return
        self._search_visible = True
        search = self.query_one("#log-search", Input)
        search.display = True
        search.value = self._log_query
        search.focus()

    def action_filter_log(self) -> None:
        self.app.push_screen(
            FilterScreen(self._log_categories),
            callback=self._apply_filter,
        )

    def _apply_filter(self, result: set[str] | None) -> None:
        if result is None:
            return
        self._log_categories = set(result)
        self._render_log()
        self._apply_layout()

    def action_raw_event(self) -> None:
        item = self._output().selected_item()
        if item is not None:
            self.app.push_screen(RawEventScreen(item))

    def action_follow_log(self) -> None:
        self._output().action_follow()
        self._render_reading()

    def action_clear_log_filter(self) -> None:
        if self._search_visible:
            self._search_visible = False
            search = self.query_one("#log-search", Input)
            search.value = ""
            search.display = False
            self._log_query = ""
            self._render_log()
            self._apply_layout()
            self._output().focus()
            return
        if self._log_query or self._log_categories:
            self._log_query = ""
            self._log_categories = set()
            self._render_log()
            self._apply_layout()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "log-search":
            return
        self._log_query = event.value.strip()
        self._search_visible = False
        event.input.display = False
        self._render_log()
        self._apply_layout()
        self._output().focus()

    def on_key(self, event) -> None:
        if event.key == "escape" and self._search_visible:
            self._search_visible = False
            search = self.query_one("#log-search", Input)
            search.value = ""
            search.display = False
            self._log_query = ""
            self._render_log()
            self._apply_layout()
            self._output().focus()
            event.stop()

    def _render_reading(self) -> None:
        if self._output_hidden:
            return
        widget = self.query_one("#reading", Static)
        out = self._output()
        if self._view_size.width < 80:
            text = (
                "Following | Enter: open | End: live"
                if out.following
                else f"History - {out.missed} newer | End: live"
            )
        elif self._view_size.width < 110:
            text = (
                "Following live | Space: open | / search | f filter | End: live"
                if out.following
                else f"History - {out.missed} newer | End: live | Ctrl+Q: close"
            )
        elif out.following:
            text = (
                "Following live events | Enter/Space: open | / search | f filter | "
                "r raw | End: live | Ctrl+Q: close"
            )
        else:
            text = (
                f"Reading history - {out.missed} newer entries | "
                "End: live | / search | f filter | Ctrl+Q: close"
            )
        widget.update(
            Text(
                text[: max(20, self._view_size.width - 2)],
                style=self._palette.muted,
            )
        )

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _apply_layout(self) -> None:
        size = self._view_size
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
        output = self.query_one("#output", EventLog)
        output.display = not compact
        self.query_one("#output-heading", Static).display = not compact
        self.query_one("#now", Static).display = not compact
        self.query_one("#log-search", Input).display = (
            not compact and self._search_visible
        )
        self.query_one("#reading", Static).display = not compact
        self._now_rows = 0 if compact else 1
        if compact and self.app.focused is output:
            self.query_one("#models", DataTable).focus()
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
        width = max(12, self._view_size.width - 2)
        heading = Text("Output", style=f"bold {self._palette.heading}")
        heading.append(" " + "-" * (width - 8), style=self._palette.muted)
        self.query_one("#output-heading", Static).update(heading[:width])

    def on_resize(self) -> None:
        if not self.is_mounted or self.snapshot is None:
            return
        self.refresh_snapshot()

    def refresh_and_layout(self) -> None:
        self.refresh_snapshot()
        self._apply_layout()


class CampaignReport(App):
    """Single-campaign report application.

    A thin app shell around exactly one :class:`CampaignPanel`: it supplies
    the title, key bindings, global styles and screen composition. Campaign
    interactions (`snapshot`, refresh and feed plumbing) live on the panel and
    are forwarded below so tests and callers of the old class keep working.
    """

    TITLE = "Autoresearch campaign report"

    AUTO_FOCUS = "#output"

    BINDINGS: ClassVar[list] = [
        ("ctrl+c", "quit", "Close report"),
        ("ctrl+q", "quit", "Close report"),
        ("/", "search_log", "Search events"),
        ("f", "filter_log", "Filter events"),
        ("r", "raw_event", "Raw event"),
        ("escape", "clear_log_filter", "Clear filter"),
        ("end", "follow_log", "Follow live"),
    ]

    CSS = REPORT_CSS

    def __init__(
        self,
        *,
        sources: CampaignSources | DemoSources | None = None,
        events_path: Path | None = None,
        demo: bool = False,
    ) -> None:
        super().__init__()
        self._panel = CampaignPanel(
            sources=sources,
            events_path=events_path,
            demo=demo,
        )

    def compose(self) -> ComposeResult:
        yield self._panel

    def watch_theme(self, old_theme: str, new_theme: str) -> None:
        if self.is_running:
            self._panel.apply_theme()

    def __getattr__(self, name: str):
        """Forward panel state and behaviour (``snapshot``, ``_timeline``...)."""
        panel = self.__dict__.get("_panel")
        if panel is None:
            raise AttributeError(name)
        return getattr(panel, name)

    def __setattr__(self, name: str, value) -> None:
        # Tests and callers replace panel state through the facade.
        if name in {"snapshot", "_campaign_id"}:
            panel = self.__dict__.get("_panel")
            if panel is not None:
                setattr(panel, name, value)
                return
        super().__setattr__(name, value)
