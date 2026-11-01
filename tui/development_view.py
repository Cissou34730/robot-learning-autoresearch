"""Read-only recipe-development inspector with worker-owned file access."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from typing import ClassVar

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import DataTable, Select, Static
from textual.worker import get_current_worker

from tui.development import (
    ComparisonSnapshot,
    DevelopmentSnapshot,
    VariantSnapshot,
    build_development_snapshot,
)
from tui.report_presentation import PALETTES, fit_text


def _value(value: object) -> str:
    return "unavailable" if value is None else str(value)


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _json(value: object) -> str:
    return (
        "unavailable"
        if value is None
        else json.dumps(_plain(value), indent=2, default=str)
    )


def _measurement(measurement, *, full: bool = False) -> str:
    if measurement is None:
        return "not measured"
    text = f"{measurement.success_percent:g}% (n={_value(measurement.episodes)})"
    if full:
        text += (
            f" | {_value(measurement.instrument)} | Dev:{measurement.operation_id}"
            f" | seed {_value(measurement.seed)}"
            f"\nCandidate Dev:{measurement.candidate_id}"
            f" | label {_value(measurement.label)}"
            f"\nArtifact: {_value(measurement.artifact)}"
        )
    return text


def _percent(fraction: float | None) -> str:
    return "unavailable" if fraction is None else f"{fraction * 100:g}%"


class DevelopmentDetail(VerticalScroll):
    DEFAULT_CSS = """
    DevelopmentDetail { width: 1fr; height: 100%; padding: 0 1; }
    .development-detail-text { height: auto; }
    .development-checkpoints { height: auto; max-height: 12; }
    DataTable { background: $surface; color: $text; }
    DataTable > .datatable--header { background: $surface; text-style: bold; }
    DataTable > .datatable--cursor { text-style: bold underline; }
    """

    def compose(self) -> ComposeResult:
        yield Static("", classes="development-detail-text")
        yield DataTable(
            cursor_type="row",
            show_row_labels=False,
            classes="development-checkpoints",
        )
        yield Static("", classes="development-evidence development-detail-text")

    def show_variant(self, comparison, variant, snapshot, receipt, notes) -> None:
        body = Text(
            f"Dev:{comparison.id} / {variant.label} | {variant.state}\n"
            f"Question: {_value(comparison.question)}\n"
            f"Description: {_value(comparison.description)}\n"
            f"PI rationale: {_value(comparison.rationale)}\n"
            f"Seed: {_value(comparison.seed)} | Initialization: {_value(comparison.initialization)}\n"
            f"Allocation per variant: {_value(comparison.allocation_per_variant)}"
            f" | Total: {_value(comparison.total_allocation)}\n"
            f"Proposed change: {_value(variant.proposed_change)}\n"
            f"Expected behavior: {_value(variant.expected_behavior)}\n"
            f"New steps: {_value(variant.actual_steps)} / {_value(variant.requested_steps)}\n"
            f"Parent: {'Dev:' + variant.parent_id if variant.parent_id else 'unavailable'}"
            f" | Prior exposure: {_value(variant.prior_steps)}\n"
            f"Parameter overrides:\n{_json(variant.parameters)}\n"
            f"Training reward PROXY: {_value(variant.training_reward)}"
            f" | Training success PROXY: {_percent(variant.training_success)}\n"
            f"Latest measured task result: {_measurement(variant.latest_measurement, full=True)}\n"
            f"{receipt}\nPI decision: {_value(snapshot.decision)}\n"
            f"PI role reasoning: {_value(snapshot.candidates_and_roles)}\n"
            f"Recorded choices: {_value(snapshot.choices or None)}\n{notes}"
        )
        text = self.query_one(".development-detail-text", Static)
        if text.content != body:
            text.update(body)
        table = self.query_one(DataTable)
        columns = (
            ("Checkpoint", 26),
            ("New steps", 12),
            ("Reward proxy", 14),
            ("Success proxy", 15),
            ("Measured task result / panel / op", 65),
        )
        keys = tuple(checkpoint.id for checkpoint in variant.checkpoints)
        if tuple(key.value for key in table.rows) != keys or not table.columns:
            table.clear(columns=True)
            for label, width in columns:
                table.add_column(label, key=label, width=width)
            for checkpoint in variant.checkpoints:
                table.add_row(*("" for _ in columns), key=checkpoint.id)
        evidence = []
        for checkpoint in variant.checkpoints:
            measurements = checkpoint.measurements
            cells = (
                f"Dev:{checkpoint.id}",
                _value(checkpoint.steps),
                _value(checkpoint.training_reward),
                _percent(checkpoint.training_success),
                "; ".join(
                    f"{_measurement(item)} / {_value(item.instrument)} / Dev:{item.operation_id}"
                    for item in measurements
                )
                or "not measured",
            )
            for (column, width), cell in zip(columns, cells, strict=True):
                content = fit_text(Text(cell), width)
                if table.get_cell(checkpoint.id, column) != content:
                    table.update_cell(checkpoint.id, column, content)
            evidence.append(
                f"Dev:{checkpoint.id} | New steps {_value(checkpoint.steps)}"
                f" | Reward PROXY {_value(checkpoint.training_reward)}"
                f" | Success PROXY {_percent(checkpoint.training_success)}\n"
                + (
                    "\n".join(_measurement(item, full=True) for item in measurements)
                    or "not measured"
                )
            )
        evidence_text = Text("\n\n".join(evidence) or "No recorded checkpoints")
        widget = self.query_one(".development-evidence", Static)
        if widget.content != evidence_text:
            widget.update(evidence_text)


class DevelopmentDetailScreen(ModalScreen):
    BINDINGS: ClassVar[list] = [("escape", "dismiss", "Back")]
    DEFAULT_CSS = """
    DevelopmentDetailScreen { background: $surface; }
    DevelopmentDetailScreen DevelopmentDetail { border: solid $accent; height: 1fr; }
    #development-detail-hints { height: 1; }
    """

    def __init__(self, owner) -> None:
        super().__init__()
        self.owner = owner

    def compose(self) -> ComposeResult:
        yield DevelopmentDetail()
        yield Static(
            "Esc back | Arrows scroll | F6 checkpoint table | Ctrl+C copy",
            id="development-detail-hints",
        )

    def on_mount(self) -> None:
        self.owner.refresh_detail(self.query_one(DevelopmentDetail))
        self.query_one(DevelopmentDetail).focus()

    def action_dismiss(self) -> None:
        self.dismiss()


class DevelopmentView(Widget):
    DEFAULT_CSS = """
    DevelopmentView { height: auto; display: none; }
    #development-summary, #development-question, #development-allocation { height: 1; }
    #development-comparison { height: 1; border: none; padding: 0; }
    #development-comparison SelectCurrent { height: 1; border: none; padding: 0; }
    #development-comparison SelectCurrent:focus { text-style: bold underline; }
    #development-comparison SelectOverlay { border: none; }
    #development-body { height: 5; }
    #development-variants { width: 1fr; height: 100%; background: $surface; }
    #development-variants > .datatable--header { background: $surface; text-style: bold; }
    #development-variants > .datatable--cursor { text-style: bold underline; }
    #development-side-detail { display: none; }
    """

    class Changed(Message):
        def __init__(self, snapshot: DevelopmentSnapshot, *, live: bool) -> None:
            super().__init__()
            self.snapshot = snapshot
            self.live = live

    def __init__(self, sources, **kwargs) -> None:
        super().__init__(**kwargs)
        self.sources = sources
        self.snapshot: DevelopmentSnapshot | None = None
        self.bundle = None
        self.comparison_id: str | None = None
        self.variant_label: str | None = None
        self._stamp = None
        self._worker = None
        self._progress: dict[tuple[str, str | None], dict] = {}
        self._revision = 0
        self._loaded_revision = -1
        self._table_key = None
        self._options = ()
        self._stale_error: str | None = None

    def compose(self) -> ComposeResult:
        yield Static("Development source unavailable", id="development-summary")
        yield Select(
            [], prompt="Comparison", allow_blank=True, id="development-comparison"
        )
        yield Static("", id="development-question")
        yield Static("", id="development-allocation")
        with Horizontal(id="development-body"):
            yield DataTable(
                id="development-variants", cursor_type="row", show_row_labels=False
            )
            yield DevelopmentDetail(id="development-side-detail")

    def on_mount(self) -> None:
        self.query_one("#development-comparison").tooltip = "Recorded comparisons"
        self.query_one(
            "#development-variants"
        ).tooltip = "Arrows select variant; Enter opens full details; Esc returns"
        self.refresh_source()
        self.set_interval(1.0, self.refresh_source)

    def on_unmount(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def refresh_source(self) -> None:
        if not callable(getattr(self.sources, "read_development", None)):
            return
        if self._worker is None or self._worker.is_finished:
            self._worker = self._read_source(dict(self._progress), self._revision)

    def observe_progress(self, event) -> None:
        if event.kind != "training_progress":
            return
        operation = event.operation_id or event.fields.get("operation_id")
        live = self.bundle and self._live_source(self.bundle)
        if not operation or not (
            str(operation).startswith("recipe_development:") or live
        ):
            return
        sample = {**event.fields, "operation_id": str(operation)}
        label = sample.get("variant")
        key = (str(operation), label if isinstance(label, str) else None)
        if self._progress.get(key) != sample:
            self._progress[key] = sample
            self._revision += 1

    @staticmethod
    def _live_source(bundle) -> bool:
        state = bundle.current_state or {}
        session = state.get("scientific_session") or {}
        return (
            state.get("campaign_phase") == "recipe_development"
            or session.get("kind") == "recipe_development"
        ) and not bundle.archived

    @work(thread=True, exclusive=True, group="development-source", exit_on_error=False)
    def _read_source(self, progress: dict, revision: int) -> None:
        worker = get_current_worker()
        try:
            stamp_of = getattr(self.sources, "development_stamp", None)
            stamp = stamp_of() if callable(stamp_of) else None
            if (
                stamp is not None
                and stamp == self._stamp
                and revision == self._loaded_revision
            ):
                return
            bundle = (
                self.bundle
                if self.bundle is not None and stamp == self._stamp
                else self.sources.read_development()
            )
            arguments = {
                "archived": bundle.archived,
                "current_state": bundle.current_state,
                "delivery_stage": bundle.delivery_stage,
                "source_available": bundle.source_available,
                "explanation": bundle.explanation,
                "training_metrics": bundle.training_metrics,
            }
            snapshot = build_development_snapshot(
                bundle.state, bundle.records, **arguments
            )
            if (
                self.snapshot is not None
                and bundle.campaign_id != self.snapshot.campaign_id
            ):
                progress = {}
            for sample in progress.values():
                operation = sample["operation_id"].removeprefix("recipe_development:")
                for comparison in snapshot.comparisons:
                    for variant in comparison.variants:
                        declared = sample.get("variant")
                        identity = comparison.id.removeprefix("recipe_development:")
                        if (
                            operation != identity
                            and operation != f"{identity}-{variant.label}"
                        ):
                            continue
                        if declared is not None and declared != variant.label:
                            continue
                        if declared is None and operation == identity:
                            continue
                        normalized = {
                            **sample,
                            "operation_id": comparison.id,
                            "variant": variant.label,
                        }
                        projected = build_development_snapshot(
                            bundle.state,
                            bundle.records,
                            progress=normalized,
                            **arguments,
                        )
                        projected_comparison = next(
                            item
                            for item in projected.comparisons
                            if item.id == comparison.id
                        )
                        projected_variant = next(
                            item
                            for item in projected_comparison.variants
                            if item.label == variant.label
                        )
                        snapshot = replace(
                            snapshot,
                            comparisons=tuple(
                                replace(
                                    item,
                                    variants=tuple(
                                        projected_variant
                                        if row.label == variant.label
                                        else row
                                        for row in item.variants
                                    ),
                                )
                                if item.id == comparison.id
                                else item
                                for item in snapshot.comparisons
                            ),
                        )
            if not worker.is_cancelled:
                self.app.call_from_thread(self._receive, bundle, snapshot, revision)
        except (OSError, ValueError) as error:
            if not worker.is_cancelled:
                self.app.call_from_thread(self._source_error, str(error))

    def _source_error(self, error: str) -> None:
        self._stale_error = error
        self._render_snapshot()

    def _receive(self, bundle, snapshot: DevelopmentSnapshot, revision: int) -> None:
        if (
            self.snapshot is not None
            and snapshot.campaign_id != self.snapshot.campaign_id
        ):
            self.comparison_id = self.variant_label = None
            self._progress.clear()
        self.bundle = bundle
        self.snapshot = snapshot
        self._stamp = bundle.stamp
        self._loaded_revision = revision
        self._stale_error = None
        self._render_snapshot()
        self.post_message(self.Changed(snapshot, live=self._live_source(bundle)))

    def selected_comparison(self) -> ComparisonSnapshot | None:
        return (
            next(
                (
                    item
                    for item in self.snapshot.comparisons
                    if item.id == self.comparison_id
                ),
                None,
            )
            if self.snapshot
            else None
        )

    @property
    def _view_width(self) -> int:
        return (
            self.size.width or self.parent.size.width or max(0, self.app.size.width - 2)
        )

    def selected_variant(self) -> VariantSnapshot | None:
        comparison = self.selected_comparison()
        return (
            next(
                (
                    item
                    for item in comparison.variants
                    if item.label == self.variant_label
                ),
                None,
            )
            if comparison
            else None
        )

    def receipt(self) -> str:
        if self.bundle is None:
            return "Delivery receipt unavailable"
        current = self.bundle.current_state or {}
        historical = self.bundle.state or {}
        delivered = self.snapshot and self.snapshot.phase == "delivered"
        canonical = (
            (current.get("campaign") or {}).get("recipe_source_commit")
            if delivered
            else None
        )
        commit = canonical
        if commit is None and isinstance(historical.get("recipe_development"), Mapping):
            commit = historical["recipe_development"].get("scientific_commit")
        stage = _value(current.get("campaign_phase"))
        return (
            f"{'Recipe delivered' if delivered else 'Recipe delivery'}"
            f" | {'Canonical recipe' if canonical else 'Development source'}"
            f" commit {_value(commit)} | Current phase {stage}"
            f" | Receipt stage {_value(self.bundle.delivery_stage)}"
        )

    def _notes(self, comparison: ComparisonSnapshot) -> str:
        state = self.bundle.state or {}
        events = [*(state.get("operation_events") or ()), *self.bundle.records]
        pending = state.get("pending_operation")
        if isinstance(pending, Mapping):
            events.append(pending)
        event = next(
            (item for item in reversed(events) if item.get("id") == comparison.id), {}
        )
        result = event.get("result") or {}
        data = event.get("data") or {}
        return (
            f"Recorded error: {_json(event.get('failure'))}\n"
            f"Recorded reviewer data: {_json(data.get('review') or result.get('review'))}\n"
            f"Recorded operation data:\n{_json(data or None)}\n"
            f"Recorded operation result:\n{_json(result or None)}\n"
            f"Read-only source identity: Dev:{self.snapshot.campaign_id} / {comparison.id}"
        )

    def refresh_detail(self, detail: DevelopmentDetail) -> None:
        comparison, variant = self.selected_comparison(), self.selected_variant()
        if comparison and variant:
            detail.show_variant(
                comparison,
                variant,
                self.snapshot,
                self.receipt(),
                self._notes(comparison),
            )

    def _render_snapshot(self) -> None:
        snapshot = self.snapshot
        if snapshot is None:
            return
        width = max(10, self._view_width)
        stale = self._stale_error or (
            self.bundle.explanation if self.bundle.last_known else None
        )
        label = (
            "Development archive (read-only)"
            if snapshot.archived or snapshot.phase == "delivered"
            else "Development"
        )
        summary = f"{label}: {snapshot.phase}"
        if stale:
            summary += f" | Stale: {stale}"
        elif snapshot.explanation:
            summary += f" | {snapshot.explanation}"
        if snapshot.phase == "delivered":
            summary += " | " + self.receipt()
        summary_widget = self.query_one("#development-summary", Static)
        summary_widget.display = bool(
            stale
            or snapshot.archived
            or snapshot.phase == "delivered"
            or not snapshot.source_available
        )
        summary_widget.tooltip = summary
        summary_widget.update(fit_text(Text(summary), width))
        choices = tuple((f"Dev:{item.id}", item.id) for item in snapshot.comparisons)
        selector = self.query_one("#development-comparison", Select)
        selector.display = bool(choices)
        if choices != self._options:
            self._options = choices
            selector.set_options(choices)
        if self.comparison_id not in {value for _, value in choices}:
            self.comparison_id = choices[-1][1] if choices else None
        if self.comparison_id and selector.value != self.comparison_id:
            selector.value = self.comparison_id
        comparison = self.selected_comparison()
        question = (
            (
                comparison.question
                or comparison.description
                or "Comparison question unavailable"
            )
            if comparison
            else "Preparing - no recorded comparisons"
        )
        allocation = (
            (
                f"Seed {_value(comparison.seed)} | {_value(comparison.initialization)}"
                f" | {_value(comparison.allocation_per_variant)} / variant"
                f" | Total {_value(comparison.total_allocation)} ({len(comparison.variants)} variants)"
            )
            if comparison
            else ""
        )
        for identity, text in (
            ("development-question", question),
            ("development-allocation", allocation),
        ):
            widget = self.query_one(f"#{identity}", Static)
            widget.display = bool(text)
            widget.tooltip = text
            widget.update(fit_text(Text(text), width))
        self._render_table(comparison)
        self.refresh_detail(self.query_one(DevelopmentDetail))
        if (
            isinstance(self.app.screen, DevelopmentDetailScreen)
            and self.app.screen.owner is self
        ):
            self.refresh_detail(self.app.screen.query_one(DevelopmentDetail))
        self.fit_layout()

    def _render_table(self, comparison: ComparisonSnapshot | None) -> None:
        table = self.query_one("#development-variants", DataTable)
        table.display = comparison is not None
        if comparison is None:
            return
        palette = PALETTES["dark" if self.app.current_theme.dark else "light"]
        compact = self._view_width < 70
        width = max(
            46, self._view_width // 2 if self._view_width > 120 else self._view_width
        )
        columns = [("Variant", max(8, width - (34 if compact else 54))), ("State", 10)]
        if not compact:
            columns.append(("New steps", 18))
        columns.append(("Measured success", 17))
        key = (comparison.id, comparison.variants, tuple(columns), palette)
        if key == self._table_key:
            return
        self._table_key = key
        labels = tuple(row.label for row in comparison.variants)
        if self.variant_label not in labels:
            self.variant_label = labels[0] if labels else None
        if (
            tuple(column.label.plain for column in table.columns.values())
            != tuple(name for name, _ in columns)
            or tuple(item.value for item in table.rows) != labels
        ):
            table.clear(columns=True)
            for name, size in columns:
                table.add_column(name, key=name, width=size)
            for row in comparison.variants:
                table.add_row(*("" for _ in columns), key=row.label)
            if self.variant_label:
                table.move_cursor(row=labels.index(self.variant_label), animate=False)
        for variant in comparison.variants:
            style = (
                palette.error
                if variant.state == "failed"
                else palette.success
                if variant.state == "completed"
                else palette.warning
                if variant.state == "running"
                else palette.muted
            )
            cells = {
                "Variant": Text(variant.label),
                "State": Text(variant.state, style=style),
                "New steps": Text(
                    f"{_value(variant.actual_steps)} / {_value(variant.requested_steps)}"
                ),
                "Measured success": Text(_measurement(variant.latest_measurement)),
            }
            for name, size in columns:
                content = fit_text(cells[name], size)
                if table.get_cell(variant.label, name) != content:
                    table.update_cell(variant.label, name, content)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "development-comparison":
            return
        event.stop()
        if isinstance(event.value, str) and event.value != self.comparison_id:
            self.comparison_id = event.value
            self.variant_label = None
            self._render_snapshot()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "development-variants":
            event.stop()
            self.variant_label = event.row_key.value
            self.refresh_detail(self.query_one(DevelopmentDetail))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "development-variants":
            event.stop()
            self.variant_label = event.row_key.value
            self.app.push_screen(DevelopmentDetailScreen(self))

    def fit_layout(self) -> None:
        wide = self._view_width > 120
        body = self.query_one("#development-body")
        comparison = self.selected_comparison()
        rows = len(comparison.variants) if comparison else 0
        body.display = bool(rows)
        available = self.parent.size.height
        compact_height = available < 20
        self.query_one("#development-question").display = not compact_height
        self.query_one("#development-allocation").display = (
            not compact_height and comparison is not None
        )
        body.styles.height = (
            max(5, min(14, available // 2))
            if wide
            else min(max(2, rows + 1), max(2, available - 10))
        )
        if compact_height:
            body.styles.height = min(max(3, rows + 1), max(3, available - 13))
        self.query_one("#development-side-detail").display = wide and bool(rows)

    def on_resize(self) -> None:
        if self.is_mounted:
            self._render_snapshot()
