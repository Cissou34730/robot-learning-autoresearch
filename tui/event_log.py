"""Collapsible operator log built on Textual's virtualized Tree."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import ClassVar

from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.selection import Selection
from textual.strip import Strip
from textual.widgets import SelectionList, Static, Tree
from textual.widgets._tree import TreeNode

from runner.copilot.reporting import tool_color_role, tool_result_parts
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
        stamp = ""
        if self.item.ts is not None:
            stamp = self.item.ts.astimezone().isoformat(sep=" ", timespec="seconds")
            if self.item.end_ts is not None:
                stopped = self.item.end_ts.astimezone().isoformat(
                    sep=" ", timespec="seconds"
                )
                stamp = f"{stamp} - {stopped}"
        prefix = f"Recorded {stamp}\n\n" if stamp else ""
        yield VerticalScroll(
            Static(f"Raw event: {self.item.title}", id="raw-title"),
            Static(
                prefix
                + json.dumps(
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

    ALLOW_SELECT = True
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
        self._styles = styles
        self.show_root = False
        self.show_guides = False
        self.guide_depth = 0
        self._expanded: set[str] = set()
        self._collapsed: set[str] = set()
        self._following = True
        self._missed = 0
        self._node_by_id: dict[str, TreeNode[TimelineItem]] = {}
        self._items_by_id: dict[str, TimelineItem] = {}
        self._last_signature: tuple[tuple, ...] = ()
        self._last_active_ids: frozenset[str] = frozenset()
        self._last_styles: dict[str, str] = {}
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
        while node is not None and node.data is None:
            node = node.parent
        return node.data if node is not None else None

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
        self._collapsed.clear()
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
        if (
            signature == self._last_signature
            and active_key == self._last_active_ids
            and self._styles == self._last_styles
        ):
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
        self._last_styles = dict(self._styles)
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
        if selected is None and roots:
            self.call_after_refresh(self._select_latest_visible)

    def _select_latest_visible(self) -> None:
        if self.cursor_node is not None:
            return
        lines = self._tree_lines
        if not lines:
            return
        start = max(0, int(self.scroll_offset.y))
        height = max(1, self.size.height)
        for line in reversed(lines[start : start + height]):
            if line.node.data is not None:
                self.move_cursor(line.node, animate=False)
                return
        for line in reversed(lines):
            if line.node.data is not None:
                self.move_cursor(line.node, animate=False)
                return

    def _flatten_ids(self, roots: list[TimelineItem]) -> Iterable[tuple]:
        for item in roots:
            yield (
                item.item_id,
                item.title,
                item.summary,
                item.ts,
                item.end_ts,
                item.status,
                item.severity,
                item.detail,
            )
            yield from self._flatten_ids(item.children)

    def _add_item(
        self,
        parent: TreeNode[TimelineItem],
        item: TimelineItem,
        active_ids: set[str],
    ) -> None:
        self._items_by_id[item.item_id] = item
        expanded = item.item_id not in self._collapsed and (
            item.item_id in self._expanded
            or item.default_expanded
            or item.item_id in active_ids
        )
        label = self._label(item)
        expandable = item.is_group or bool(item.detail) or self._is_flow(item)
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
            self._populate_details(node, item)

    def _populate_details(
        self, node: TreeNode[TimelineItem], item: TimelineItem
    ) -> None:
        """Materialize full, wrapped detail rows only when their event is open."""
        node.remove_children()
        if self._is_flow(item):
            lines = self._flow_lines(node, item)
            node.allow_expand = len(lines) > 1
            for line in lines[1:]:
                node.add_leaf(line, data=None)
            return
        width = max(1, self._label_width(node) - self.guide_depth)
        for block in item.detail:
            for line in block.splitlines() or [""]:
                style = (
                    self._kind_style(item)
                    if item.kind == "pi"
                    else self._styles.get("text", "")
                )
                text = Text(line, style=style)
                for wrapped in text.wrap(self.app.console, width, overflow="fold"):
                    node.add_leaf(wrapped, data=None)

    @staticmethod
    def _is_flow(item: TimelineItem) -> bool:
        return item.kind == "tool" or (item.kind == "pi" and item.title == "PI")

    def _flow_lines(
        self, node: TreeNode[TimelineItem], item: TimelineItem
    ) -> list[Text]:
        text = Text(item.title, style=self._kind_style(item))
        if item.kind == "tool":
            if item.summary:
                text.append(": ", style=self._styles.get("muted", ""))
                text.append_text(self._summary_text(item))
            results = tool_result_parts(
                str(item.payload.get("name") or item.title), item.payload.get("result")
            )
            result_roles = {line.strip(): role for line, role in results}
            for line in item.detail:
                role = result_roles.get(
                    line, "error" if item.severity == "error" else "text"
                )
                text.append("\n" + line, style=self._styles.get(role, ""))
        else:
            text.append("  " + "\n".join(item.detail), style=self._styles.get("pi", ""))
        return list(
            text.wrap(
                self.app.console, max(1, self._label_width(node) - 2), overflow="fold"
            )
        )

    def _label_width(self, node: TreeNode[TimelineItem]) -> int:
        depth = -1
        parent = node
        while parent is not self.root:
            depth += 1
            parent = parent.parent
        column_width = sum(segment.cell_length for segment in self._column(None, False))
        return max(1, (self.size.width or 80) - column_width - depth * self.guide_depth)

    def render_label(
        self, node: TreeNode[TimelineItem], base_style: Style, style: Style
    ) -> Text:
        item = node.data
        if item is not None and self._is_flow(item):
            lines = self._flow_lines(node, item)
            marker = (
                (self.ICON_NODE_EXPANDED if node.is_expanded else self.ICON_NODE)
                if len(lines) > 1
                else "  "
            )
            label = Text(marker, style=base_style + Style(meta={"toggle": True}))
            label.append_text(lines[0])
            return label
        # Cursor/hover feedback lives in the fixed gutter. Tree's default
        # label foreground must not overwrite the semantic text spans.
        label = super().render_label(node, base_style, Style())
        if node is self.root:
            return label
        label.truncate(self._label_width(node), overflow="ellipsis")
        return label

    def _label(self, item: TimelineItem) -> Text:
        styles = self._styles
        kind_style = self._kind_style(item)
        label = Text()
        message = item.kind == "pi" and item.title == "PI"
        if item.kind != "tool" and not message:
            label.append(item.glyph, style=kind_style)
            label.append(" ")
        label.append(item.title, style=kind_style)
        if item.summary and not message:
            label.append("  ")
            label.append_text(self._summary_text(item))
        if item.is_group:
            duration = item.duration_text()
            if duration:
                label.append("  ")
                label.append(f"[{duration}]", style=styles.get("muted", ""))
        return label

    def _summary_text(self, item: TimelineItem) -> Text:
        if item.severity in {"error", "warning"}:
            return Text(item.summary, style=self._styles.get(item.severity, ""))
        summary = Text(item.summary, style=self._styles.get("text", ""))
        status = str(item.payload.get("status") or item.status or "")
        role = (
            "success"
            if status in {"completed", "checkpointed", "passed", "accepted"}
            else "warning"
            if status in {"needs_pi", "timeout", "cancelled", "interrupted"}
            else "accent"
            if status in {"running", "started"}
            else ""
        )
        if role and item.summary.startswith(status):
            summary.stylize(self._styles.get(role, ""), 0, len(status))
        return summary

    def _column(self, item: TimelineItem | None, selected: bool) -> list[Segment]:
        """Fixed left column: selection marker, clock, and separator."""
        marker = "▌ " if selected else "  "
        stamp = (
            item.ts.astimezone().strftime("%H:%M:%S")
            if item is not None and item.ts is not None
            else "        "
        )
        accent = self._styles.get("accent", "")
        muted = self._styles.get("muted", "")
        column_bg = self._styles.get("column_bg", "")
        suffix = f" on {column_bg}" if column_bg else ""

        def column_style(color: str, *, bold: bool = False) -> Style:
            parts = []
            if bold and color:
                parts.append("bold")
            if color:
                parts.append(color)
            if suffix:
                parts.append(suffix.strip())
            return Style.parse(" ".join(parts)) if parts else Style()

        marker_style = column_style(accent, bold=selected)
        muted_style = column_style(muted)
        if item is None:
            return [
                Segment(marker, marker_style),
                Segment(" " * (len(stamp) + 3), muted_style),
            ]
        return [
            Segment(marker, marker_style),
            Segment(stamp, muted_style),
            Segment(" │ ", muted_style),
        ]

    def _decorated_strip(self, content_y: int, scroll_x: int, width: int) -> Strip:
        width = max(1, width)
        if not 0 <= content_y < len(self._tree_lines):
            return Strip.blank(width, self.rich_style)
        line = self._tree_lines[content_y]
        node = line.node
        item = node.data
        hovered = self._get_node(self.hover_line)
        selected = (
            hovered in line.path if hovered is not None else node is self.cursor_node
        )
        column = self._column(item, selected)
        column_width = sum(len(segment.text) for segment in column)
        content_width = max(1, width - column_width)
        content = self._render_line(
            content_y,
            scroll_x,
            scroll_x + content_width,
            self.rich_style,
        )
        return (
            Strip([*column, *content])
            .crop_extend(0, width, self.rich_style)
            .apply_meta({"line": content_y})
        )

    def render_line(self, y: int) -> Strip:
        content_y = y + int(self.scroll_offset.y)
        strip = self._decorated_strip(
            content_y,
            int(self.scroll_offset.x),
            self.size.width,
        )
        selection = self.text_selection
        if (
            selection is not None
            and (span := selection.get_span(content_y)) is not None
        ):
            start, end = span
            text_length = len(strip.text)
            start = strip.index_to_cell_position(min(start, text_length))
            end = strip.index_to_cell_position(
                text_length if end == -1 else min(end, text_length)
            )
            selection_style = self.screen.get_component_rich_style("screen--selection")
            selected = strip.crop(start, end)
            # Selection must override the existing label colours/background.
            selected = Strip(Segment.apply_style(selected, post_style=selection_style))
            strip = Strip.join((strip.crop(0, start), selected, strip.crop(end)))
        return strip.apply_offsets(0, content_y)

    def get_selection(self, selection: Selection) -> tuple[str, str]:
        width = max(1, self.size.width)
        scroll_x = int(self.scroll_offset.x)
        lines = [
            self._decorated_strip(y, scroll_x, width).text.rstrip()
            for y in range(self.last_line + 1)
        ]
        return selection.extract("\n".join(lines)), "\n"

    def _kind_style(self, item: TimelineItem) -> str:
        styles = self._styles
        if item.severity == "error":
            return f"bold {styles.get('error', '')}".strip()
        if item.severity == "warning":
            return f"bold {styles.get('warning', '')}".strip()
        if item.kind == "tool":
            return styles.get(
                tool_color_role(str(item.payload.get("name") or item.title)), ""
            )
        if item.kind == "file":
            role = {"created": "success", "deleted": "error"}.get(
                str(item.payload.get("operation")), "accent"
            )
            return styles.get(role, "")
        if item.kind == "result":
            return styles.get(
                "result" if item.payload.get("scope") == "result" else "success", ""
            )
        if item.kind == "coding":
            status = str(item.payload.get("status") or "")
            role = (
                "error"
                if status in {"failed", "error", "rejected"}
                else "warning"
                if status in {"needs_pi", "cancelled", "blocked"}
                else "success"
                if status in {"passed", "completed"}
                else "accent"
            )
            return styles.get(role, "")
        scope_role = {
            "session": "session",
            "campaign": "heading",
            "inquiry": "warning",
            "validation": "success",
            "assessment": "success",
            "success": "success",
        }.get(str(item.payload.get("scope") or ""))
        if scope_role:
            return styles.get(scope_role, "")
        mapping = {
            "campaign": f"bold {styles.get('heading', '')}".strip(),
            "session": f"bold {styles.get('session', '')}".strip(),
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

    def watch_hover_line(self, previous_hover_line: int, hover_line: int) -> None:
        super().watch_hover_line(previous_hover_line, hover_line)
        # Hover marks the whole visible subtree. Repaint the keyboard cursor's
        # marker as well when entering/leaving a block without moving the cursor.
        self.refresh()

    def on_click(self, event: events.Click) -> None:
        # App synthesizes Click even after a drag. Do not let Tree toggle a
        # block (or Widget select all on a repeated click) after text selection.
        if self.text_selection is not None:
            event.prevent_default()
            event.stop()

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
            self._collapsed.discard(item.item_id)
            if not item.is_group and not event.node.children:
                self._populate_details(event.node, item)

    def on_tree_node_collapsed(self, event: Tree.NodeCollapsed) -> None:
        item = event.node.data
        if item is not None:
            self._expanded.discard(item.item_id)
            self._collapsed.add(item.item_id)

    def on_resize(self) -> None:
        for node in self._node_by_id.values():
            item = node.data
            if item is not None and not item.is_group and node.is_expanded:
                self._populate_details(node, item)
