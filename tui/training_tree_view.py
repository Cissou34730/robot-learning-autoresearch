"""On-demand training and measurement tree."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import Static, Tree
from textual.worker import Worker, get_current_worker

from tui.console_screens import ConsoleDetail
from tui.sources import CampaignSources
from tui.timeline_items import TimelineItem
from tui.training_tree import build_training_tree


class TrainingTree(Tree[TimelineItem]):
    BINDINGS: ClassVar[list] = [
        *Tree.BINDINGS,
        Binding("enter", "show_details", "Details", priority=True),
    ]

    def __init__(self) -> None:
        super().__init__("Training and measurement", id="training-tree")
        self.show_root = False
        self.guide_depth = 2
        self._signature: tuple | None = None

    def set_items(self, items: list[TimelineItem]) -> None:
        def signature(item: TimelineItem) -> tuple:
            return (
                item.item_id,
                item.title,
                item.summary,
                item.detail,
                tuple(signature(child) for child in item.children),
            )

        updated = tuple(signature(item) for item in items)
        if updated == self._signature:
            return
        self._signature = updated
        expanded: set[str] = set()
        selected = (
            self.cursor_node.data.item_id
            if self.cursor_node and self.cursor_node.data
            else ""
        )

        def remember(node) -> None:
            if node.data and node.is_expanded:
                expanded.add(node.data.item_id)
            for child in node.children:
                remember(child)

        remember(self.root)
        first = not self.root.children
        self.root.remove_children()
        selected_node = None

        def add(parent, item: TimelineItem) -> None:
            nonlocal selected_node
            text = item.title + (f" · {item.summary}" if item.summary else "")
            node = parent.add(
                text,
                data=item,
                allow_expand=bool(item.children),
                expand=item.item_id in expanded or (first and item.default_expanded),
            )
            if item.item_id == selected:
                selected_node = node
            for child in item.children:
                add(node, child)

        for item in items:
            add(self.root, item)
        if selected_node is not None:
            self.move_cursor(selected_node, animate=False)

    def action_show_details(self) -> None:
        item = self.cursor_node.data if self.cursor_node else None
        if item is not None:
            body = "\n".join(part for part in (item.summary, *item.detail) if part)
            self.app.push_screen(
                ConsoleDetail(item.title, body or "No details recorded.")
            )


class TrainingTreePanel(Widget):
    DEFAULT_CSS = """
    TrainingTreePanel {
        display: none;
        width: 44;
        height: 100%;
        border-left: solid $panel;
        padding-left: 1;
    }
    TrainingTreePanel > Static { height: 1; }
    TrainingTreePanel > TrainingTree { height: 1fr; }
    """

    def __init__(self, campaign_root: Path, *, id: str) -> None:
        super().__init__(id=id)
        self.sources = CampaignSources(campaign_root)
        self._worker: Worker | None = None
        self._stamp: tuple | None = None

    def compose(self) -> ComposeResult:
        yield Static("Training & Measurement  F4 close")
        yield Static("Loading...", id="training-tree-status")
        yield TrainingTree()
        yield Static("F6 focus · arrows navigate · Enter details")

    def on_mount(self) -> None:
        self.set_interval(1.0, self.refresh_source)

    def on_unmount(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def refresh_source(self) -> None:
        if all(widget.display for widget in self.ancestors_with_self) and (
            self._worker is None or self._worker.is_finished
        ):
            self._worker = self._load()

    @work(thread=True, exclusive=True, group="training-tree", exit_on_error=False)
    def _load(self) -> None:
        worker = get_current_worker()
        try:
            stamp = (self.sources.stamp(), self.sources.development_stamp())
            if stamp == self._stamp:
                return
            state, records, _ = self.sources.read()
            if state is None:
                self.app.call_from_thread(
                    self._receive, None, "Campaign state unavailable", None
                )
                return
            development = self.sources.read_development()
            campaign = state.get("campaign")
            identity = campaign.get("id") if isinstance(campaign, dict) else None
            if self.sources.stamp()[:2] != stamp[0][:2]:
                raise RuntimeError("Campaign data changed while reading; retrying")
            if development.archived and development.campaign_id != identity:
                raise RuntimeError("Campaign changed while reading the recipe archive")
            archived_state = development.state if development.archived else None
            archived_records = development.records if development.archived else ()
            items = build_training_tree(
                state,
                records,
                archived_state=archived_state,
                archived_records=archived_records,
            )
            if not worker.is_cancelled:
                self.app.call_from_thread(
                    self._receive,
                    items,
                    "" if items else "No training or measurements recorded",
                    stamp,
                )
        except (OSError, RuntimeError, ValueError) as error:
            if not worker.is_cancelled:
                self.app.call_from_thread(
                    self._receive, None, f"Tree unavailable: {error}", None
                )

    def _receive(
        self, items: list[TimelineItem] | None, status: str, stamp: tuple | None
    ) -> None:
        self._stamp = stamp
        self.query_one("#training-tree-status", Static).update(status)
        self.query_one(TrainingTree).set_items(items or [])
