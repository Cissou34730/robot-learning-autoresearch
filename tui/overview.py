"""Read-only comparison of the five campaign slots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, Static
from textual.worker import Worker, get_current_worker

from tui import projector
from tui.phase_presentation import campaign_phase_letter
from tui.report_presentation import PALETTES
from tui.scientific_model import model_status
from tui.sources import CampaignSources

MODEL_READY = "ready · Enter"


@dataclass(frozen=True)
class OverviewCampaign:
    slot: int
    installed: bool
    phase: str
    snapshot: projector.CampaignSnapshot | None
    inquiries: int | None
    model: str | None = None


def overview_campaign(
    slot: int, state: dict | None, records: list[dict], installed: bool
) -> OverviewCampaign:
    if not installed or state is None:
        return OverviewCampaign(slot, installed, "?", None, None)
    counters = state.get("counters")
    count = counters.get("inquiry") if isinstance(counters, dict) else None
    inquiries = (
        count if isinstance(count, int) and not isinstance(count, bool) else None
    )
    return OverviewCampaign(
        slot,
        True,
        campaign_phase_letter(state),
        projector.build_snapshot(state, records, []),
        inquiries,
        model_status(state),
    )


def overview_values(
    campaign: OverviewCampaign,
    launcher: str,
    evaluation: projector.EvaluationProgress | None,
    *,
    now: datetime,
) -> tuple[str, ...]:
    if not campaign.installed:
        return ("not set up",) + ("—",) * 8
    snapshot = campaign.snapshot
    if snapshot is None:
        return ("unavailable", launcher) + ("unavailable",) * 7
    names = {
        "A": "Analyse",
        "R": "Recipe",
        "S": "Startup",
        "I": "Inquiry",
        "B": "Benchmark",
    }
    phase = names.get(campaign.phase, "unknown")
    if snapshot.started_at is None:
        elapsed = "unavailable"
    else:
        elapsed = projector.campaign_age(snapshot.started_at, snapshot.ended_at or now)
    evaluation_text = "—"
    if evaluation is not None:
        parts = []
        if evaluation.panel_index is not None and evaluation.panel_total is not None:
            parts.append(f"{evaluation.panel_index}/{evaluation.panel_total}")
        if evaluation.episodes is not None and evaluation.episodes_total is not None:
            parts.append(f"{evaluation.episodes}/{evaluation.episodes_total}")
        evaluation_text = " ".join(parts) or "running"
    best = snapshot.goal.best_percent
    target = snapshot.goal.target_percent
    goal = "unavailable"
    if best is not None or target is not None:
        best_text = f"{best:g}" if best is not None else "?"
        target_text = f"{target:g}" if target is not None else "?"
        goal = f"{best_text}/{target_text}%"
    official = {"passed": "reached", "failed": "not reached"}.get(
        snapshot.official_status, "not assessed"
    )
    return (
        phase,
        launcher,
        "unavailable",
        elapsed,
        evaluation_text,
        str(campaign.inquiries) if campaign.inquiries is not None else "unavailable",
        goal,
        official,
        {"ready": MODEL_READY, "pending": "not published"}.get(
            campaign.model or "", "unavailable"
        ),
    )


class CampaignOverview(Widget):
    can_focus = True

    class OpenCampaign(Message):
        def __init__(self, slot: int) -> None:
            super().__init__()
            self.slot = slot

    class OpenScientificModel(Message):
        def __init__(self, slot: int) -> None:
            super().__init__()
            self.slot = slot

    DEFAULT_CSS = """
    CampaignOverview { height: 100%; padding: 0 1; }
    CampaignOverview > Static { height: 1; color: $text-muted; }
    #overview-title { color: $text; text-style: bold; margin-bottom: 1; }
    CampaignOverview > DataTable { height: 1fr; }
    CampaignOverview DataTable > .datatable--header {
        background: $primary-background; color: $text; text-style: bold;
    }
    """

    ROWS = (
        ("phase", "Phase"),
        ("launcher", "Launcher"),
        ("phase-time", "Time in phase"),
        ("elapsed", "Campaign elapsed"),
        ("evaluation", "Panel / episodes"),
        ("inquiries", "Inquiries"),
        ("goal", "Dev / goal"),
        ("official", "Official"),
        ("model", "Scientific model"),
    )

    def __init__(self, folders: list[Path], *, id: str = "campaign-overview") -> None:
        super().__init__(id=id)
        self.folders = folders
        self.campaigns: tuple[OverviewCampaign, ...] = ()
        self._worker: Worker | None = None
        self._matrix: bool | None = None
        self._stamps: tuple | None = None
        self._shown: dict[tuple[int, str], str] = {}
        self._layout: tuple | None = None
        self._active_slots: tuple[int, ...] = ()
        self._source_error = ""

    def compose(self) -> ComposeResult:
        yield Static(
            "Active campaigns · Enter opens campaign or scientific model",
            id="overview-title",
        )
        yield Static("Loading campaign data...", id="overview-status")
        yield DataTable(id="overview-table", cursor_type="cell", cell_padding=1)

    def on_mount(self) -> None:
        self._configure()
        self.set_interval(2.0, self.refresh_source)

    def on_unmount(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def on_resize(self) -> None:
        if self.is_mounted:
            self._configure()

    def _configure(self) -> None:
        from tui.console import CampaignConsole

        app = self.app
        if not isinstance(app, CampaignConsole):
            return
        slots = tuple(
            slot
            for slot in range(1, 6)
            if app.query(f"#panel-campaign-{slot}")
            and app._campaign_active(app._controller.state(f"campaign-{slot}"))
        )
        matrix = self.size.width >= 78
        layout = (matrix, self.size.width, slots)
        if layout == self._layout:
            return
        self._layout = layout
        self._active_slots = slots
        self._matrix = matrix
        self._shown.clear()
        table = self.query_one(DataTable)
        table.clear(columns=True)
        table.display = bool(slots)
        if matrix:
            table.add_column("Campaign", key="field", width=16)
            width = max(9, min(48, (self.size.width - 18) // max(1, len(slots)) - 2))
            for slot in slots:
                table.add_column(f"Campaign {slot}", key=str(slot), width=width)
            for key, label in self.ROWS:
                table.add_row(label, *("" for _ in slots), key=key)
        else:
            table.add_column("Campaign", key="slot", width=8)
            table.add_column("Field", key="field", width=16)
            table.add_column("Value", key="value", width=max(10, self.size.width - 32))
            for slot in slots:
                for key, label in self.ROWS:
                    table.add_row(str(slot), label, "", key=f"{slot}:{key}")
        self._update_status()
        self.refresh_display()

    def _update_status(self) -> None:
        from tui.console import CampaignConsole

        app = self.app
        if not isinstance(app, CampaignConsole):
            return
        status = self.query_one("#overview-status", Static)
        if not app._activity_ready:
            status.update("Checking campaign activity...")
        elif not self._active_slots:
            status.update("No active campaigns.")
        elif self._source_error:
            status.update(f"Overview unavailable: {self._source_error}")
        elif not self.campaigns:
            status.update("Loading campaign data...")
        else:
            status.update("Phase start is not recorded; duration unavailable.")

    def refresh_source(self) -> None:
        if all(widget.display for widget in self.ancestors_with_self) and (
            self._worker is None or self._worker.is_finished
        ):
            self._worker = self._load()

    @work(thread=True, exclusive=True, group="campaign-overview", exit_on_error=False)
    def _load(self) -> None:
        worker = get_current_worker()
        try:
            sources = [CampaignSources(folder) for folder in self.folders]
            stamps = tuple(
                (source.stamp(), (folder / ".git").exists())
                for source, folder in zip(sources, self.folders, strict=True)
            )
            if stamps == self._stamps:
                self.app.call_from_thread(self.refresh_display)
                return
            campaigns = []
            for slot, (source, folder) in enumerate(
                zip(sources, self.folders, strict=True), 1
            ):
                installed = (folder / ".git").exists()
                state, records, _ = source.read() if installed else (None, [], [])
                if installed and source.stamp()[:2] != stamps[slot - 1][0][:2]:
                    raise RuntimeError(
                        f"Campaign {slot} changed while reading; retrying"
                    )
                campaigns.append(overview_campaign(slot, state, records, installed))
            if not worker.is_cancelled:
                self.app.call_from_thread(self._receive, tuple(campaigns), stamps)
        except (OSError, RuntimeError, ValueError) as error:
            if not worker.is_cancelled:
                self.app.call_from_thread(self._error, str(error))

    def _receive(self, campaigns: tuple[OverviewCampaign, ...], stamps: tuple) -> None:
        self.campaigns = campaigns
        self._stamps = stamps
        self._source_error = ""
        self._update_status()
        self.refresh_display()

    def _error(self, error: str) -> None:
        self.campaigns = ()
        self._stamps = None
        self._source_error = error
        self._shown.clear()
        table = self.query_one(DataTable)
        for slot in self._active_slots:
            for key, _ in self.ROWS:
                if self._matrix:
                    table.update_cell(key, str(slot), "unavailable")
                else:
                    table.update_cell(f"{slot}:{key}", "value", "unavailable")
        self.query_one("#overview-status", Static).update(
            f"Overview unavailable: {error}"
        )

    def refresh_display(self) -> None:
        if not self.is_mounted:
            return
        from tui.console import CampaignConsole
        from tui.report import CampaignPanel

        app = self.app
        if not isinstance(app, CampaignConsole):
            return
        self._configure()
        self._update_status()
        if not self.campaigns:
            return
        table = self.query_one(DataTable)
        palette = PALETTES["dark" if app.current_theme.dark else "light"]
        now = datetime.now(tz=UTC)
        for campaign in self.campaigns:
            if campaign.slot not in self._active_slots:
                continue
            label = f"campaign-{campaign.slot}"
            if campaign.installed:
                panels = app.query(f"#panel-{label}")
                if panels:
                    process = app._controller.state(label)
                    launcher = "running ext" if process.external else process.stage
                    evaluation = panels.first(CampaignPanel)._evaluation_progress()
                else:
                    launcher, evaluation = "unavailable", None
            else:
                launcher, evaluation = "not installed", None
            values = overview_values(campaign, launcher, evaluation, now=now)
            for (key, _), value in zip(self.ROWS, values, strict=True):
                cell = (campaign.slot, key)
                if self._shown.get(cell) == value:
                    continue
                self._shown[cell] = value
                color = palette.text
                if value in {"unavailable", "unknown", "—", "not assessed"}:
                    color = palette.muted
                elif key == "phase" or value == MODEL_READY:
                    color = palette.accent
                elif key == "launcher":
                    color = (
                        palette.warning
                        if launcher in {"stopping", "resetting"}
                        else palette.success
                    )
                content = Text(value, style=color)
                if self._matrix:
                    table.update_cell(key, str(campaign.slot), content)
                else:
                    table.update_cell(f"{campaign.slot}:{key}", "value", content)

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        if self._matrix:
            slot = event.cell_key.column_key.value
            row = event.cell_key.row_key.value
        else:
            key = event.cell_key.row_key.value or ""
            slot, _, row = key.partition(":")
        if slot and slot.isdigit() and 1 <= int(slot) <= 5:
            if row == "model":
                self.post_message(self.OpenScientificModel(int(slot)))
            else:
                self.post_message(self.OpenCampaign(int(slot)))
        else:
            self.notify("Select a campaign column first.", severity="warning")

    def focus_table(self) -> None:
        table = self.query_one(DataTable)
        if not table.display:
            self.focus()
            return
        if self._matrix and table.cursor_coordinate.column == 0:
            table.move_cursor(column=1)
        table.focus()
