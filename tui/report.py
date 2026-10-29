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

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from rich.cells import cell_len
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.geometry import Size
from textual.widget import Widget
from textual.widgets import DataTable, Input, Static

from runner.event_contract import LAUNCH_KINDS, LAUNCHER_STOP_CODES
from tui import projector
from tui.activity import (
    LIVENESS_SECONDS,
    PROGRESS_STALE_SECONDS,
    RUNNER_HEARTBEAT_SECONDS,
    LiveActivity,
)
from tui.demo import DemoSources
from tui.event_log import EventLog, FilterScreen, RawEventScreen
from tui.journal import JournalFeed, journal_path_for
from tui.observations import Observation
from tui.report_presentation import (
    PALETTES,
    Palette,
    context_budget,
    context_lines,
    contrast_ratio,
    model_budget,
    output_min_rows,
)
from tui.report_presentation import assessment_style as _assessment_style
from tui.report_presentation import clean_text as _clean_text
from tui.report_presentation import display_text as _display_text
from tui.report_presentation import evaluation_lines as _evaluation_lines
from tui.report_presentation import fit_text as _fit_text
from tui.report_presentation import metric_cell as _metric_cell
from tui.report_presentation import progress_bar_line as _progress_bar_line
from tui.report_presentation import progress_title as _progress_title
from tui.report_presentation import relative_luminance as _relative_luminance
from tui.report_presentation import role_style as _role_style
from tui.report_presentation import training_lines as _training_lines
from tui.sources import CampaignSources
from tui.timeline import TimelineReducer

__all__ = [
    "LIVENESS_SECONDS",
    "PALETTES",
    "PROGRESS_STALE_SECONDS",
    "REPORT_CSS",
    "RUNNER_HEARTBEAT_SECONDS",
    "CampaignPanel",
    "CampaignReport",
    "CampaignSources",
    "DemoSources",
    "Palette",
    "_display_text",
    "_relative_luminance",
    "contrast_ratio",
]

MIN_COLUMNS = 48
MIN_ROWS = 16
# One master tick drives every time-based update, so the feed, the clocks and
# the log always show the same moment.
TICK_SECONDS = 1.0
# Durable files are re-read only when they change. This interval covers
# sources that cannot report a change.
DURABLE_FALLBACK_SECONDS = 15.0
# The Runner publishes progress when counters change and at least this often
# (runner.execution.STATUS_INTERVAL_SECONDS). Staleness limits derive from it.
COMPACT_WIDTH = 100
COMPACT_HEIGHT = 30


# The log is display-only. These tokens are the single palette used by the
# report; CSS picks its structural colours from the active Textual theme.


def _now() -> datetime:
    return datetime.now(tz=UTC)


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
        show_hints: bool = True,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._demo = demo
        # The console shows its own keys on one line; it hides this row.
        self._show_hints = show_hints
        self._campaign_root = Path(campaign_root) if campaign_root else None
        if self._campaign_root is None and not demo:
            from runner import paths

            self._campaign_root = paths.ROOT
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
        self._models_key: tuple | None = None
        self._output_hidden = False
        self._last_session: str = ""
        self._last_error: str = ""
        self._launcher_stopped = False
        self._identity_stamp: tuple | None = None
        self._feed_campaign: str | None = None
        self._campaign_id: str | None = None
        self._timeline = TimelineReducer(self._campaign_root)
        self._timeline.activity.clock = lambda: _now()
        self._log_query = ""
        self._log_categories: set[str] = set()
        self._search_visible = False
        self._now_rows = 0
        self._hidden = False
        self._durable_stamp: tuple | None = None
        self._durable_read_at = float("-inf")
        self._layout_key: tuple | None = None
        self._shown_text: dict[str, Text | str] = {}
        self._log_key: tuple | None = None

    @property
    def activity(self) -> LiveActivity:
        return self._timeline.activity

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
        event_log.on_open_folded(self._render_log)
        self._apply_log_background()
        self._make_feed()
        self.refresh_snapshot()
        self.drain_feed()
        self.set_interval(TICK_SECONDS, self._master_tick)
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

    def _is_shown(self) -> bool:
        return all(widget.display for widget in self.ancestors_with_self)

    def _master_tick(self) -> None:
        """The one periodic update: feed, durable changes, then one render."""
        if not self._is_shown():
            # An inactive console tab keeps its state current (so its tab can
            # show the phase) but draws nothing; it catches up when shown.
            self._hidden = True
            self._follow_campaign()
            self.drain_feed(render=False)
            return
        if self._hidden:
            self._hidden = False
            self.refresh_snapshot()
        self.drain_feed(render=False)
        self._refresh_durable_if_changed()
        self.tick_clock()

    def _follow_campaign(self) -> None:
        """Keep a hidden tab on its folder's current campaign.

        A reset or a new run gives the folder a new campaign with its own
        journal. A shown tab learns it from the durable refresh; a hidden tab
        reads only the campaign identity, and only when a durable file changed.
        """
        stamp_of = getattr(self._sources, "stamp", None)
        identity_of = getattr(self._sources, "campaign_id", None)
        if stamp_of is None or identity_of is None:
            return
        stamp = stamp_of()
        if stamp == self._identity_stamp:
            return
        self._identity_stamp = stamp
        campaign = identity_of()
        self._switch_campaign(campaign)
        self._ensure_feed(campaign)
        if isinstance(self._feed, JournalFeed) and campaign:
            self._feed.campaign_id = campaign

    def _refresh_durable_if_changed(self) -> None:
        stamp_of = getattr(self._sources, "stamp", None)
        if stamp_of is not None:
            changed = stamp_of() != self._durable_stamp
        else:
            changed = (
                time.monotonic() - self._durable_read_at >= DURABLE_FALLBACK_SECONDS
            )
        if changed:
            self.refresh_snapshot()

    def _make_feed(self) -> None:
        if self._demo:
            from tui.demo import demo_schedule
            from tui.observations import SyntheticFeed

            self._feed = SyntheticFeed(demo_schedule())
            return
        if self._events_path is not None:
            self._feed = JournalFeed(self._events_path)
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
        self._log_query = ""
        self._log_categories = set()
        self._search_visible = False
        self._now_rows = 0
        self._shown_text.clear()
        self._layout_key = None
        self._models_key = None
        self._log_key = None
        self.query_one("#now", Static).update("")
        self._attached = False
        self._context_rows = 0
        self._progress_rows = 0
        self._training_rows = 0
        self._last_session = ""
        self._last_error = ""
        self._launcher_stopped = False
        if not self._demo and self._events_path is None:
            self._feed = None
            self._feed_campaign = None

    def _ensure_feed(self, campaign_id: str | None) -> None:
        """Follow this campaign's own journal; a reset cannot surface old events."""
        if self._demo or self._events_path is not None or not campaign_id:
            return
        campaign = str(campaign_id)
        if isinstance(self._feed, JournalFeed) and self._feed_campaign == campaign:
            return
        self._feed = JournalFeed(
            journal_path_for(campaign, self._campaign_root), campaign_id=campaign
        )
        self._feed_campaign = campaign

    # ------------------------------------------------------------------
    # Snapshot refresh
    # ------------------------------------------------------------------

    def refresh_snapshot(self) -> None:
        """Re-read the durable files for the header band and the model table.

        The log does not use them: it shows only what the journal says.
        """
        stamp_of = getattr(self._sources, "stamp", None)
        self._durable_stamp = stamp_of() if stamp_of is not None else None
        self._durable_read_at = time.monotonic()
        state, records, usage_rows = self._sources.read()
        if state is None and records:
            self._note("Campaign state file unavailable")
        campaign_id = (state or {}).get("campaign", {}).get("id")
        self._switch_campaign(campaign_id)
        self._ensure_feed(campaign_id)
        if isinstance(self._feed, JournalFeed) and campaign_id:
            self._feed.campaign_id = str(campaign_id)

        snapshot = projector.build_snapshot(
            state,
            records,
            usage_rows,
            training=self._training_progress(),
            evaluation=self._evaluation_progress(),
            activity=self.activity.last_activity or None,
            stage_started_at=self.activity.stage_started,
            process_observed_recently=self._process_observed(),
        )
        self.snapshot = snapshot
        self.activity.ended_at = snapshot.ended_at
        self._mark_attached()
        self._render_context()
        self._render_models(snapshot.model_rows)
        self._render_progress()
        self._render_training_status()
        self._render_log()
        self._apply_layout()

    def _process_observed(self) -> bool:
        return self.activity.process_observed()

    def _report_source_error(self, message: str) -> None:
        self._note(f"Campaign source problem: {message}")

    # -- live progress objects -----------------------------------------

    def set_process_running(self, running: bool) -> None:
        if not self.activity.set_process_running(running):
            return
        if self.snapshot is not None:
            self._render_context()
            self._render_progress()
            self._render_training_status()
            self._apply_layout()

    def _clock_end(self, started_at: datetime | None) -> datetime:
        return self.activity.clock_end(
            started_at, self.snapshot.ended_at if self.snapshot else None
        )

    def _advance(self, state: dict) -> float:
        return self.activity.advance(state)

    def _training_progress(self) -> projector.TrainingProgress | None:
        return self.activity.training_progress()

    def _evaluation_progress(self) -> projector.EvaluationProgress | None:
        return self.activity.evaluation_progress()

    def phase(self) -> str:
        return self._timeline.phase()

    def official_outcome(self) -> str:
        """``passed`` or ``failed`` once the final benchmark has a result, from the
        durable state, so it holds after a restart and for any way of starting."""
        status = self.snapshot.official_status if self.snapshot is not None else ""
        return status if status in {"passed", "failed"} else ""

    def progress_stalled(self) -> bool:
        """True while a live training or evaluation counter has stopped advancing."""
        if self.activity.paused_at is not None:
            return False
        return any(
            state and self._progress_stale(state)
            for state in (self.activity.training, self.activity.evaluation)
        )

    def _progress_stale(self, state: dict) -> bool:
        return self.activity.progress_stale(state)

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
        self._set_text(self.query_one("#context", Static), rendered)

    def _set_text(self, widget: Static, content: Text) -> None:
        """Repaint a Static only when its content changed, and re-lay it out
        only when its size can change, so quiet ticks cost nothing."""
        key = widget.id or ""
        previous = self._shown_text.get(key)
        if previous == content:
            return
        self._shown_text[key] = content
        lines = content.plain.split("\n")
        width = widget.size.width
        same_shape = (
            isinstance(previous, Text)
            and width > 0
            and len(previous.plain.split("\n")) == len(lines)
            and max(cell_len(line) for line in lines) <= width
        )
        widget.update(content, layout=not same_shape)

    def _context_budget(self) -> int:
        return context_budget(self._view_size.width, self._view_size.height)

    def _context_lines(
        self, snapshot: projector.CampaignSnapshot, width: int
    ) -> list[Text]:
        return context_lines(
            snapshot,
            width,
            palette=self._palette,
            now=_now(),
            campaign_end=self._clock_end(snapshot.started_at),
            stage_end=self._clock_end(snapshot.stage_started_at),
            paused=self.activity.paused_at is not None,
            owned=self.activity.process_running is not None,
            budget=self._context_budget(),
            last_error=self._last_error,
        )

    # ------------------------------------------------------------------
    # Models table
    # ------------------------------------------------------------------

    def _role_style(self, role: str) -> str:
        return _role_style(self._palette, role)

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
        budget = self._models_budget_rows()
        key = (rows, layout, palette, self._attached, len(rows) > budget)
        if key == self._models_key:
            # The same rows in the same form: leave the table alone.
            return
        self._models_key = key
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
            self._set_text(self.query_one("#models-heading", Static), heading)
            return
        heading.append("PI-assigned models", style=f"bold {palette.heading}")
        if self._attached:
            heading.append(f" ({len(rows)} assigned)", style=palette.muted)
        if layout == "compact":
            heading.append(
                " - compact: steps and training metrics hidden", style=palette.muted
            )
        if len(rows) > budget:
            heading.append(
                " - scroll inside the table for every role", style=palette.muted
            )
        self._set_text(self.query_one("#models-heading", Static), heading)

    def _models_budget_rows(self) -> int:
        return model_budget(
            self._view_size.height,
            context_rows=self._context_rows,
            progress_rows=self._progress_rows,
            training_rows=self._training_rows,
            output_hidden=self._output_hidden,
            show_hints=self._show_hints,
            now_rows=self._now_rows,
            search_visible=self._search_visible,
        )

    def _output_min_rows(self) -> int:
        return output_min_rows(self._view_size.height)

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
            self._set_text(widget, Text(""))
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
        self._set_text(widget, rendered)

    def _progress_title(
        self, lead: str, lead_style: str, parts: list[str], stale: bool
    ) -> Text:
        return _progress_title(self._palette, lead, lead_style, parts, stale)

    def _progress_bar_line(
        self, label: str, first: int, total: int | None, width: int
    ) -> Text:
        return _progress_bar_line(self._palette, label, first, total, width)

    def _training_lines(
        self, training: projector.TrainingProgress, width: int
    ) -> list[Text]:
        return _training_lines(
            self._palette, training, width, paused=self.activity.paused_at is not None
        )

    def _evaluation_lines(
        self, evaluation: projector.EvaluationProgress, width: int
    ) -> list[Text]:
        return _evaluation_lines(self._palette, evaluation, width)

    def _render_training_status(self) -> None:
        widget = self.query_one("#training", Static)
        snapshot = self.snapshot
        if (
            self.activity.training is not None
            or snapshot is None
            or snapshot.last_training is None
        ):
            self._training_rows = 0
            widget.display = False
            self._set_text(widget, Text(""))
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
        self._set_text(widget, _fit_text(line, max(20, self._view_size.width - 2)))

    def _render_log(self) -> None:
        event_log = self.query_one("#output", EventLog)
        styles = self._log_styles()
        event_log._styles = styles
        key = (
            self._timeline.version,
            self._log_query,
            frozenset(self._log_categories),
            tuple(sorted(styles.items())),
            frozenset(event_log.open_group_ids()),
            frozenset(self._timeline.active_ids()),
            self._view_size.width,
        )
        if key == self._log_key:
            # Nothing new since the last draw: only running tools change.
            event_log.patch_summaries(self._timeline.live_summaries())
            return
        self._log_key = key
        roots, matches = self._timeline.view(
            query=self._log_query,
            categories=self._log_categories,
            open_ids=event_log.open_group_ids(),
        )
        event_log.set_view(roots, active_ids=self._timeline.active_ids())
        now = Text(self._timeline.now_text, style=self._palette.accent)
        self._set_text(
            self.query_one("#now", Static),
            _fit_text(now, max(20, self._view_size.width - 2)),
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
        self._set_text(
            self.query_one("#output-heading", Static),
            _fit_text(heading, max(12, self._view_size.width - 2)),
        )

    # ------------------------------------------------------------------
    # Clock-driven animations (elapsed counters and stale labels only)
    # ------------------------------------------------------------------

    def tick_clock(self) -> None:
        self.tick_clock_active = getattr(self, "tick_clock_active", 0) + 1
        if self.activity.training or self.activity.evaluation:
            self._render_progress()
        if self.snapshot is not None:
            self._render_context()
            self._render_log()

    # ------------------------------------------------------------------
    # Output appends
    # ------------------------------------------------------------------

    def _output(self) -> EventLog:
        return self.query_one("#output", EventLog)

    def _assessment_style(self, status: str) -> str:
        return _assessment_style(self._palette, status)

    def _note(self, message: str) -> None:
        """Say something about the TUI's own sources.

        The log shows only what the campaign did, so these messages go to the
        attention line of the header band, never into the log.
        """
        if self._last_error == message:
            return
        self._last_error = message
        self._render_context()

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

    def _mark_attached(self) -> None:
        self._attached = True

    # ------------------------------------------------------------------
    # Observation feed
    # ------------------------------------------------------------------

    def drain_feed(self, render: bool = True) -> None:
        feed = self._feed
        if feed is None:
            return
        events = feed.poll()
        rejected = getattr(feed, "rejected", None)
        if rejected:
            self._note(f"Journal: {rejected}")
        self._process_events(events, render=render)

    def _process_events(self, events: list[Observation], render: bool = True) -> None:
        for event in events:
            self._timeline.ingest(event)
            if self._launcher_stopped and event.kind in LAUNCH_KINDS:
                # A new launch began after the stop: its failure no longer stands.
                self._launcher_stopped = False
                self._note("")
            handler = getattr(self, f"_event_{event.kind}", None)
            if handler is None:
                continue
            handler(event)
        if render:
            self._render_log()
            self._apply_layout()

    def _event_error(self, event: Observation) -> None:
        if event.fields.get("code") not in LAUNCHER_STOP_CODES:
            return
        reason = _clean_text(
            str(event.fields.get("text") or event.fields.get("message") or "")
        )
        self._launcher_stopped = True
        self._note(f"The launcher stopped: {reason}")

    def _event_session_start(self, event: Observation) -> None:
        if self.snapshot is not None:
            self.snapshot.stage_started_at = self.activity.stage_started

    def _event_training_progress(self, event: Observation) -> None:
        self._redraw_live()

    def _redraw_live(self) -> None:
        """Redraw the progress area; a hidden tab only keeps its state."""
        if self._hidden:
            return
        self._render_progress()
        self._render_training_status()
        self._apply_layout()

    def _event_eval_progress(self, event: Observation) -> None:
        self._redraw_live()

    def _event_operation_completed(self, event: Observation) -> None:
        self._redraw_live()

    _event_operation_failed = _event_operation_completed

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
        if self._output_hidden or not self._show_hints:
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
        self._set_text(
            widget,
            Text(
                text[: max(20, self._view_size.width - 2)],
                style=self._palette.muted,
            ),
        )

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _apply_layout(self) -> None:
        size = self._view_size
        key = (
            size.width,
            size.height,
            self.app.size,
            self._context_rows,
            self._progress_rows,
            self._training_rows,
            self._search_visible,
            len(self.query_one("#models", DataTable).rows),
        )
        if key == self._layout_key:
            # Nothing that sizes the panels changed: leave them untouched.
            self._render_reading()
            return
        self._layout_key = key
        too_small = size.width < MIN_COLUMNS or size.height < MIN_ROWS
        overlay = self.query_one("#too-small", Static)
        overlay.display = too_small
        if too_small:
            # The console reserves rows for tabs and commands. Name the actual
            # window size needed, not just this embedded report area's minimum.
            columns = MIN_COLUMNS + max(0, self.app.size.width - size.width)
            rows = MIN_ROWS + max(0, self.app.size.height - size.height)
            overlay.update(
                Text(
                    f"Terminal too small - need {columns}x{rows}",
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
        self.query_one("#reading", Static).display = not compact and self._show_hints
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
        Binding("ctrl+c", "copy_selection", "Copy", priority=True),
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

    def action_copy_selection(self) -> None:
        text = self.screen.get_selected_text()
        if text:
            self.copy_to_clipboard(text)

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
