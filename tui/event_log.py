"""Collapsible operator log built on Textual's virtualized Tree."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import ClassVar

from rich.text import Text
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import SelectionList, Static, Tree
from textual.widgets._tree import TreeNode

from tui.timeline import TimelineItem


class RawEventScreen(ModalScreen[None]):
    """Read-only full payload for one event."""

    BINDINGS: ClassVar[list] = [
        ("escape", "dismiss", "Close"),
        ("q", "dismiss", "Close"),
    ]

    CSS = """
    RawEventScreen {
        align: center middle;
        background: $surface;
    }
    #raw-dialog {
        width: 86%;
        height: 82%;
        background: $surface;
        color: $text;
        padding: 1 2;
    }
    #raw-title {
        height: 1;
        text-style: bold;
        color: $text;
    }
    #raw-body {
        height: 1fr;
        color: $text;
    }
    #raw-hint {
        height: 1;
        color: $text-muted;
    }
    """

    def __init__(self, item: TimelineItem) -> None:
        super().__init__()
        self.item = item

    def compose(self):
        yield VerticalScroll(
            Static(f"Raw event: {self.item.title}", id="raw-title"),
            Static(
                json.dumps(
                    self.item.payload, ensure_ascii=False, indent=2, default=str
                ),
                id="raw-body",
            ),
            Static("Esc closes", id="raw-hint"),
            id="raw-dialog",
        )


class FilterScreen(ModalScreen[set[str] | None]):
    """Kind/category filter for the operator log."""

    BINDINGS: ClassVar[list] = [
        ("escape", "cancel", "Cancel"),
        ("enter", "apply", "Apply"),
    ]

    CSS = """
    FilterScreen {
        align: center middle;
        background: $surface;
    }
    #filter-dialog {
        width: 56;
        height: auto;
        max-height: 90%;
        background: $surface;
        color: $text;
        padding: 1 2;
    }
    #filter-title {
        height: 1;
        text-style: bold;
    }
    #filter-list {
        height: auto;
        max-height: 16;
        background: $surface;
    }
    #filter-hint {
        height: 1;
        color: $text-muted;
    }
    """

    def __init__(self, selected: set[str] | None = None) -> None:
        super().__init__()
        self.selected = selected or set()

    def compose(self):
        options = [
            (label, key, key in self.selected)
            for key, label in (
                ("sessions", "Sessions"),
                ("inquiries", "Inquiries"),
                ("training", "Training"),
                ("measurements", "Measurements"),
                ("tools", "Tools"),
                ("pi", "PI messages"),
                ("roles", "Roles and candidates"),
                ("usage", "Usage"),
                ("warnings", "Warnings and errors"),
                ("operations", "Operations and console lines"),
            )
        ]
        yield VerticalScroll(
            Static("Filter event kinds", id="filter-title"),
            SelectionList[str](*options, id="filter-list"),
            Static("Space toggle | Enter apply | Esc cancel", id="filter-hint"),
            id="filter-dialog",
        )

    def action_apply(self) -> None:
        values = set(self.query_one("#filter-list", SelectionList).selected)
        self.dismiss(values)

    def action_cancel(self) -> None:
        self.dismiss(None)


class EventLog(Tree[TimelineItem]):
    """A virtualized, collapsible chronological event stream."""

    ICON_NODE = "> "
    ICON_NODE_EXPANDED = "v "

    BINDINGS: ClassVar[list] = [
        *Tree.BINDINGS,
        Binding("enter", "toggle_node", "Toggle", show=False),
        Binding("left", "collapse_node", "Collapse", show=False),
        Binding("right", "expand_node", "Expand", show=False),
        Binding("g", "scroll_home", "Top", show=False),
        Binding("G", "scroll_end", "Bottom", show=False),
        Binding("end", "follow", "Follow", show=False),
    ]

    def __init__(self, styles: dict[str, str], **kwargs) -> None:
        super().__init__("Campaign", **kwargs)
        self.show_root = False
        self.guide_depth = 0
        self._styles = styles
        self._expanded: set[str] = set()
        self._following = True
        self._missed = 0
        self._node_by_id: dict[str, TreeNode[TimelineItem]] = {}
        self._items_by_id: dict[str, TimelineItem] = {}
        self._last_signature: tuple[str, ...] = ()
        self._last_active_ids: frozenset[str] = frozenset()
        self._follow_listeners: list = []

    # ------------------------------------------------------------------
    # Public state
    # ------------------------------------------------------------------

    @property
    def following(self) -> bool:
        return self._following

    @property
    def missed(self) -> int:
        return self._missed

    def on_follower(self, listener) -> None:
        self._follow_listeners.append(listener)

    def selected_item(self) -> TimelineItem | None:
        node = self.cursor_node
        if node is None or node.data is None:
            return None
        return node.data

    @property
    def lines(self) -> list:
        """Compatibility view of the full timeline text for tests."""
        from rich.segment import Segment
        from textual.strip import Strip

        return [Strip([Segment(line)]) for line in self.text_lines()]

    def text_lines(self) -> list[str]:
        """All item text, including collapsed children, for tests and search."""
        lines: list[str] = []

        def walk(item: TimelineItem) -> None:
            lines.append(f"{item.glyph} {item.title} {item.summary}".strip())
            lines.extend(item.detail)
            for child in item.children:
                walk(child)

        top_ids = {
            child.item_id
            for item in self._items_by_id.values()
            for child in item.children
        }
        for item in self._items_by_id.values():
            if item.item_id not in top_ids:
                walk(item)
        return lines

    def reset_campaign(self) -> None:
        self.clear()
        self._expanded.clear()
        self._node_by_id.clear()
        self._items_by_id.clear()
        self._following = True
        self._missed = 0
        self._last_signature = ()
        self._last_active_ids = frozenset()

    # ------------------------------------------------------------------
    # View construction
    # ------------------------------------------------------------------

    def set_view(
        self,
        roots: list[TimelineItem],
        *,
        active_ids: set[str] | None = None,
    ) -> None:
        active_ids = active_ids or set()
        signature = tuple(self._flatten_ids(roots))
        active_key = frozenset(active_ids)
        if signature == self._last_signature and active_key == self._last_active_ids:
            return
        new_items = bool(self._last_signature) and signature != self._last_signature
        was_following = self._following
        selected = self.selected_item()
        scroll_y = self.scroll_offset.y
        self.clear()
        self._node_by_id.clear()
        self._items_by_id.clear()
        for item in roots:
            self._add_item(self.root, item, active_ids)
        self._last_signature = signature
        self._last_active_ids = active_key
        if selected is not None:
            node = self._node_by_id.get(selected.item_id)
            if node is not None:
                self.move_cursor(node, animate=False)
        if was_following:
            self.scroll_end(animate=False)
        else:
            self.scroll_to(y=scroll_y, animate=False)
            if new_items:
                self._missed += 1

    def _flatten_ids(self, roots: list[TimelineItem]) -> Iterable[str]:
        for item in roots:
            yield "|".join(
                (
                    item.item_id,
                    item.title,
                    item.summary,
                    str(item.ts),
                    str(item.end_ts),
                    item.status,
                    item.severity,
                    str(len(item.detail)),
                )
            )
            yield from self._flatten_ids(item.children)

    def _add_item(
        self,
        parent: TreeNode[TimelineItem],
        item: TimelineItem,
        active_ids: set[str],
    ) -> None:
        self._items_by_id[item.item_id] = item
        expanded = (
            item.item_id in self._expanded
            or item.default_expanded
            or item.item_id in active_ids
        )
        label = self._label(item)
        expandable = item.is_group or bool(item.detail)
        node = parent.add(
            label,
            data=item,
            allow_expand=expandable,
            expand=expanded,
        )
        self._node_by_id[item.item_id] = node
        if item.is_group:
            for child in item.children:
                self._add_item(node, child, active_ids)
        elif expanded:
            for line in item.detail:
                node.add_leaf(
                    Text(line, style=self._styles.get("muted", "")), data=None
                )

    def _label(self, item: TimelineItem) -> Text:
        styles = self._styles
        stamp = item.ts.astimezone().strftime("%H:%M:%S") if item.ts else "--:--:--"
        label = Text()
        label.append(stamp, style=styles.get("muted", ""))
        label.append(" ")
        kind_style = self._kind_style(item)
        label.append(item.glyph, style=kind_style)
        label.append(" ")
        label.append(item.title, style=kind_style)
        if item.summary:
            label.append("  ")
            label.append(item.summary, style=styles.get("text", ""))
        if item.is_group:
            duration = item.duration_text()
            if duration:
                label.append("  ")
                label.append(f"[{duration}]", style=styles.get("muted", ""))
        return label

    def _kind_style(self, item: TimelineItem) -> str:
        styles = self._styles
        if item.severity == "error":
            return f"bold {styles.get('error', '')}".strip()
        if item.severity == "warning":
            return f"bold {styles.get('warning', '')}".strip()
        mapping = {
            "campaign": f"bold {styles.get('heading', '')}".strip(),
            "session": f"bold {styles.get('accent', '')}".strip(),
            "inquiry": f"bold {styles.get('warning', '')}".strip(),
            "training": f"bold {styles.get('accent', '')}".strip(),
            "measurement": f"bold {styles.get('accent', '')}".strip(),
            "operation": f"bold {styles.get('accent', '')}".strip(),
            "pi": styles.get("pi", ""),
            "tool": styles.get("tool", ""),
            "usage": styles.get("muted", ""),
            "role": styles.get("pi", ""),
            "checkpoint": styles.get("section", ""),
            "error": f"bold {styles.get('error', '')}".strip(),
            "warning": f"bold {styles.get('warning', '')}".strip(),
        }
        return mapping.get(item.kind, styles.get("text", ""))

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def action_collapse_node(self) -> None:
        node = self.cursor_node
        if node is not None:
            node.collapse()

    def action_expand_node(self) -> None:
        node = self.cursor_node
        if node is not None:
            node.expand()

    def action_follow(self) -> None:
        self._following = True
        self._missed = 0
        self.scroll_end(animate=False, immediate=True)
        for listener in self._follow_listeners:
            listener(True, 0)

    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        try:
            super().watch_scroll_y(old_value, new_value)
        except AttributeError:  # pragma: no cover - base class variants
            pass
        try:
            bottom = self.scroll_offset.y >= self.max_scroll_y - 0.5
        except Exception:  # noqa: BLE001 - layout not ready yet
            bottom = True
        if bottom != self._following:
            self._following = bottom
            if bottom:
                self._missed = 0
            for listener in self._follow_listeners:
                listener(bottom, self._missed)

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        item = event.node.data
        if item is not None:
            self._expanded.add(item.item_id)

    def on_tree_node_collapsed(self, event: Tree.NodeCollapsed) -> None:
        item = event.node.data
        if item is not None:
            self._expanded.discard(item.item_id)
