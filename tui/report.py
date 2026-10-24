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

import textwrap
from collections import deque
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
SNAPSHOT_SECONDS = 2.0
TICK_SECONDS = 1.0
LIVENESS_SECONDS = 300.0
PROGRESS_STALE_SECONDS = 300.0
MAX_RENDERED_ENTRIES = 100_000
EVENTS_DIR = Path("reports") / "tui_observations"


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
            break_long_words=False,
            break_on_hyphens=False,
        )
        lines.extend(wrapped or [current_prefix.rstrip()])
        current_prefix = indent
    return lines


def _status_style(status: str) -> str:
    """Pair the campaign status text with a semantic color."""
    if status.startswith("RUNNING") and "unknown" not in status:
        return "bold green"
    if status.startswith("RUNNING"):
        return "bold yellow"
    if status.startswith("ENDED"):
        return "bold yellow"
    if status == "Loading":
        return "dim"
    return ""


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
            break_long_words=False,
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


def _elapsed_text(seconds: float | None, label: str) -> str:
    if seconds is None:
        return f"{label} unavailable"
    return f"{label} {console.format_duration(float(seconds))}"


def _metric_cell(value: str, missing: str = "unavailable") -> Text:
    """Metric cell text; missing values render dim instead of invisible."""
    text = _clean_text(value)
    if value == missing or value.startswith(missing):
        return Text(text, style="dim")
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
            self.write(item, expand=False, shrink=False)
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
        color: $foreground;
        padding: 0 1;
    }
    #context {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }
    #models-heading {
        height: 1;
        color: $secondary;
    }
    #models {
        height: auto;
        max-height: 10;
        scrollbar-size-horizontal: 1;
    }
    #progress {
        display: none;
        margin-top: 1;
        height: auto;
    }
    #output-heading {
        height: 1;
        color: $secondary;
    }
    #output {
        height: 1fr;
        padding: 0;
        background: $surface;
    }
    #reading {
        height: 1;
        color: $secondary;
    }
    #too-small {
        display: none;
        layer: alert;
        width: 100%;
        height: 100%;
        content-align: center middle;
        background: $surface;
        color: $warning;
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
        self._feed = None
        self.snapshot: projector.CampaignSnapshot | None = None
        self._attached = False
        self._context_rows = 0
        self._progress_rows = 0
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
        table = DataTable(id="models", cursor_type="row", zebra_stripes=True)
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
        yield Static("", id="output-heading")
        yield OutputLog(id="output")
        yield Static("", id="reading")
        yield Static("Terminal too small - need 48x16", id="too-small")

    def on_mount(self) -> None:
        self.query_one("#output", OutputLog).on_follower(self._on_follow)
        self._make_feed()
        self.refresh_snapshot()
        self.drain_feed()
        self.set_interval(SNAPSHOT_SECONDS, self._on_snapshot_interval)
        self.set_interval(TICK_SECONDS, self.tick_clock)
        self.set_interval(TICK_SECONDS, self.drain_feed)
        self._apply_layout()

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
            style="bold red",
            width_guard=False,
        )
        self._render_context()

    def _note_source(self, message: str) -> None:
        if self._source_note_sent:
            return
        self._source_note_sent = True
        self._append(_now(), message, style="dim")

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
            return 5
        return 6

    def _context_lines(
        self, snapshot: projector.CampaignSnapshot, width: int
    ) -> list[Text]:
        from tui.projector import campaign_age, stage_elapsed

        age = campaign_age(snapshot.started_at, _now())
        elapsed = stage_elapsed(snapshot.stage_started_at, _now())

        gap = 3
        status_style = _status_style(snapshot.status)
        left = Text("Autoresearch", style="bold")
        left.append(" | ")
        left.append(snapshot.status, style=status_style)
        left.append(" | ")
        left.append("campaign ")
        left.append(snapshot.campaign_id[:13], style="dim")
        right = Text(f"Campaign age {age}", style="dim")
        right.append(" | ", style="dim")
        right.append(f"Stage elapsed {elapsed}", style="dim")
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
        stage.append("Stage: ", style="dim")
        stage.append(
            snapshot.stage_text,
            style="bold yellow" if snapshot.terminal else "bold cyan",
        )
        activity = Text()
        activity.append("Current activity: ", style="dim")
        activity.append(
            snapshot.activity_text,
            style="cyan" if "not observed" not in snapshot.activity_text else "dim",
        )
        if len(stage.plain) + gap + len(activity.plain) <= width:
            second = Text()
            second.append_text(stage)
            second.append(" " * (width - len(stage.plain) - len(activity.plain)))
            second.append_text(activity)
        else:
            second = stage
        lines.append(second)

        excerpt_rows = self._context_budget() - 3
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
                _hang_styled(prefix, question, width, "yellow", "italic")[:take]
            )
        synthesis = _clean_text(snapshot.synthesis)
        if synthesis and excerpt_rows > len(leads):
            prefix = f"PI record {snapshot.synthesis_session or 'S?'}: "
            take = 2 if width >= 120 and excerpt_rows - len(leads) >= 3 else 1
            leads.extend(_hang_styled(prefix, synthesis, width, "magenta")[:take])
        lines.extend(leads)

        usage = _clean_text(projector.usage_text(snapshot.usage))[:width]
        usage_text_obj = Text()
        usage_text_obj.append("Usage recorded", style="dim")
        usage_text_obj.append(usage[len("Usage recorded") :])
        lines.append(usage_text_obj)
        if snapshot.official_text:
            lines.append(
                Text(_clean_text(snapshot.official_text)[:width], style="bold yellow")
            )
        if self._last_error:
            lines.append(
                Text(f"Attention: {self._last_error}"[:width], style="bold red")
            )
        return lines[: self._context_budget() + 2]

    # ------------------------------------------------------------------
    # Models table
    # ------------------------------------------------------------------

    _ROLE_STYLES: ClassVar[dict] = {
        "Working": "bold cyan",
        "Best-known": "bold magenta",
    }

    def _render_models(self, rows: tuple) -> None:
        table = self.query_one("#models", DataTable)
        table.clear()
        for row in rows:
            if row.roles:
                role_cell = Text()
                for index, role in enumerate(row.roles):
                    if index:
                        role_cell.append(" + ", style="dim")
                    role_cell.append(role, style=self._ROLE_STYLES.get(role, "dim"))
            else:
                role_cell = Text("-", style="dim")
            table.add_row(
                role_cell,
                Text(row.candidate_id, style="bold"),
                _metric_cell(row.training_steps),
                _metric_cell(row.reward_training),
                _metric_cell(row.success_training),
                _metric_cell(row.success_dev, "not measured"),
            )
        heading = Text()
        if not rows:
            heading.append("PI-assigned models", style="bold")
            heading.append(" - none assigned", style="dim")
            self.query_one("#models-heading", Static).update(heading)
            return
        heading.append("PI-assigned models", style="bold")
        if self._attached:
            heading.append(f" ({len(rows)} assigned)", style="dim")
        budget = self._models_budget_rows()
        if len(rows) > budget:
            heading.append(" - scroll inside the table for every role", style="dim")
        self.query_one("#models-heading", Static).update(heading)

    def _models_budget_rows(self) -> int:
        height = self.size.height
        # context band, models heading, output heading, reading line, progress
        reserved = self._context_rows + 1 + 1 + 1 + self._progress_rows + 1
        output_min = self._output_min_rows()
        return max(2, min(20, height - reserved - output_min))

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
        title = Text(lead, style=lead_style)
        for part in parts:
            title.append(" | ", style="dim")
            title.append(part)
        if stale:
            title.append(" | ", style="dim")
            title.append("counter observation stale", style="bold red")
        return title

    def _progress_bar_line(
        self, label: str, first: int, total: int | None, width: int
    ) -> Text:
        line = Text(f"{label} {first:,}", style="bold cyan")
        if not total:
            line.append(" / target unavailable", style="dim")
            return line
        line.append(f" / {total:,}", style="dim")
        line.append("  [")
        progress = max(0.0, min(1.0, first / max(total, 1)))
        bar_width = max(8, min(width - 22, 60))
        filled = max(0, min(bar_width, round(bar_width * progress)))
        line.append("#" * filled, style="green")
        line.append("-" * (bar_width - filled), style="dim")
        line.append(f"] {round(progress * 100)}%")
        return line

    def _training_lines(
        self, training: projector.TrainingProgress, width: int
    ) -> list[Text]:
        parts = [f"Attempt {training.attempt}"]
        parts.append(_elapsed_text(training.elapsed_seconds, "Elapsed"))
        title = self._progress_title(
            f"Training {training.operation_id}", "bold cyan", parts, training.stale
        )
        lines = [title]
        if training.steps is None:
            lines.append(Text("Steps: starting - no step count yet", style="dim"))
            return lines
        lines.append(
            self._progress_bar_line("Steps", training.steps, training.target, width)
        )
        return lines

    def _evaluation_lines(
        self, evaluation: projector.EvaluationProgress, width: int
    ) -> list[Text]:
        lead_style = "bold green" if evaluation.official else "bold cyan"
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
            lines.append(Text("Running - progress unavailable", style="dim yellow"))
            return lines
        lines.append(
            self._progress_bar_line(
                "Episodes", evaluation.episodes or 0, evaluation.episodes_total, width
            )
        )
        return lines

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
        """Append pre-rendered lines."""
        self._write(stamp, lines, style)
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
        if style is not None:
            self._output().append_texts(
                [Text(_clean_text(line), style=style) for line in lines]
            )
            return
        prefix_len = (len(_ts(stamp)) + 1) if stamp is not None else 0
        texts: list[Text] = []
        for line in lines:
            if prefix_len and len(line) > prefix_len:
                item = Text(_clean_text(line))
                item.stylize("dim", 0, prefix_len)
                texts.append(item)
            else:
                texts.append(Text(_clean_text(line), style=style))
        self._output().append_texts(texts)

    def _output_width(self) -> int:
        return max(20, self.size.width - 2)

    def _attach_output(self) -> None:
        snapshot = self.snapshot
        if snapshot is None or self._attached:
            return
        self._attached = True
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
                style="bold red",
            )
        feed_ready = isinstance(self._feed, JsonlFeed) and self._feed.path.exists()
        if not self._demo and not feed_ready:
            self._append(
                now,
                "No structured observation feed is available: live PI messages and "
                "live execution progress are unavailable. Recorded campaign state, "
                "durable operational history and recorded usage follow.",
                style="dim",
            )
        question = _clean_text(snapshot.question) or _clean_text(snapshot.objective)
        if question:
            prefix = (
                f"Inquiry [{snapshot.question_source}]: "
                if snapshot.question
                else "Objective: "
            )
            self._hang_block(prefix, question, prefix_style="bold yellow")
        if snapshot.synthesis:
            self._hang_block(
                f"PI record {snapshot.synthesis_session or 'S?'}: ",
                _clean_text(snapshot.synthesis),
                prefix_style="bold magenta",
            )
        assignments = projector.role_assignment_text(snapshot)
        if assignments:
            self._append(now, "Model assignments at attachment:", style="dim")
            self._append_block(now, assignments.splitlines(), style="dim")
        self._append_timeline()

    def _append_timeline(self) -> None:
        snapshot = self.snapshot
        if snapshot is None:
            return
        for entry in snapshot.timeline:
            style = None
            if entry.kind == "error":
                style = "bold red"
            elif entry.kind == "pending":
                style = "yellow"
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
        if signature[0] != previous[0] and signature[0]:
            source = (
                f"inquiry [{snapshot.question_source}]"
                if snapshot.question
                else "objective"
            )
            self._append(now, f"Inquiry question updated ({source}):", style="dim")
            self._hang_block("", signature[0])
        if (signature[1], signature[2]) != (previous[1], previous[2]) and signature[1]:
            self._append(
                now,
                f"PI synthesis updated ({snapshot.synthesis_session}):",
                style="dim",
            )
            self._hang_block("", signature[1])
        if signature[3] != previous[3] and signature[3]:
            self._append(now, "Model assignments changed:", style="dim")
            self._append_block(now, signature[3].splitlines(), style="dim")
        if signature[4] != previous[4] and signature[4]:
            self._append(now, signature[4], style="bold yellow")
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
        self._append(_now(), f"Observation feed: {message}", style="bold red")

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
        self._append(event.ts, f"activity: {label}", style="cyan")

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
            self._hang_block(prefix, text, prefix_style="bold magenta")
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
                self._hang_block(label, addition, prefix_style="bold magenta")
        self._pi_stream[turn] = text
        if final:
            self._pi_seen.append(fingerprint)
            self._pi_stream.pop(turn, None)

    def _event_tool(self, event: Observation) -> None:
        name = _clean_text(event.fields.get("name") or "tool")
        detail = _clean_text(event.fields.get("detail") or "")
        line = f"tool {name}"
        if detail:
            line += f": {detail}"
        self._append(event.ts, line, style="dim")

    def _event_console_line(self, event: Observation) -> None:
        text = _clean_text(event.fields.get("text") or "")
        scope = _clean_text(event.fields.get("scope") or "")
        if not text:
            return
        style = None
        if scope == "error":
            style = "bold red"
        elif scope == "warning":
            style = "bold yellow"
        self._append(event.ts, text, style=style)

    def _event_training_progress(self, event: Observation) -> None:
        attempt = event.fields.get("attempt")
        self._training = {
            "operation_id": str(event.fields.get("operation_id") or ""),
            "attempt": attempt if attempt not in (None, "") else "unknown",
            "steps": event.fields.get("steps"),
            "target": event.fields.get("target"),
            "elapsed_seconds": event.fields.get("elapsed_seconds"),
            "last_ts": event.ts or _now(),
        }
        self._render_progress()

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
        style = "bold green" if status == "completed" else "bold yellow"
        self._append(event.ts, text or f"{operation} execution {status}", style=style)
        if self._training and self._training.get("operation_id") == operation:
            self._training = None
        if self._evaluation and self._evaluation.get("operation_id") == operation:
            self._evaluation = None
        self._render_progress()

    # ------------------------------------------------------------------
    # Reading status
    # ------------------------------------------------------------------

    def _on_follow(self, following: bool, missed: int) -> None:
        self._render_reading()

    def _render_reading(self) -> None:
        widget = self.query_one("#reading", Static)
        out = self._output()
        if self.size.width < 80:
            text = (
                "Following | Wheel / PgUp / PgDn | End to return"
                if out.following
                else f"Reading history - {out.missed} newer | End to return"
            )
        elif out.following:
            text = (
                "Following live output | Mouse wheel / Page Up / Page Down to read "
                "history | End to return to live output | Ctrl+Q closes the report"
            )
        else:
            text = (
                f"Reading history - {out.missed} newer entries | "
                "End to return to live output"
            )
        widget.update(text[: max(20, self.size.width - 2)])

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _apply_layout(self) -> None:
        size = self.size
        too_small = size.width < MIN_COLUMNS or size.height < MIN_ROWS
        self.query_one("#too-small", Static).display = too_small
        if too_small:
            return
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
        width = max(12, self.size.width - 2)
        heading = Text("Output", style="bold")
        heading.append(" " + "-" * (width - 8), style="dim")
        self.query_one("#output-heading", Static).update(heading[:width])

    def on_resize(self) -> None:
        if not self.is_running or self.snapshot is None:
            return
        self.refresh_snapshot()

    def refresh_and_layout(self) -> None:
        self.refresh_snapshot()
