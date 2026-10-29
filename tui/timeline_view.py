"""Chronological, filtered and folded views of timeline ownership."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from tui.timeline_formatting import now as _now
from tui.timeline_formatting import tool_summary as _tool_summary
from tui.timeline_items import TimelineItem

FILTER_CATEGORIES = {
    "sessions": {"session"},
    "inquiries": {"inquiry"},
    "training": {"training", "training_progress", "training_checkpoints"},
    "measurements": {
        "measurement",
        "eval_progress",
        "measurement_panel_started",
        "measurement_panel_completed",
    },
    "tools": {
        "tool",
        "tool_call",
        "tool_call_started",
        "tool_call_completed",
        "tool_call_failed",
        "tool_denied",
        "coding",
        "file_changed",
        "file",
    },
    "pi": {"pi", "pi_message", "pi_context"},
    "roles": {
        "role",
        "checkpoint",
        "role_assigned",
        "candidate_created",
        "checkpoint_saved",
    },
    "usage": {"usage", "usage_update", "campaign_usage", "session_usage"},
    "warnings": {
        "warning",
        "error",
        "operation_failed",
        "publication_retry",
    },
    "operations": {
        "operation",
        "operation_requested",
        "operation_started",
        "operation_completed",
        "operation_failed",
        "operation_submitted",
        "campaign_started",
        "campaign_concluded",
        "campaign_goal_review",
        "run_state",
        "scientific_model_validated",
        "notice",
    },
}


class TimelineView:
    def __init__(
        self,
        roots: list[TimelineItem],
        items: dict[str, TimelineItem],
        campaign_root: Path | None,
    ) -> None:
        self._roots = roots
        self._items = items
        self._campaign_root = campaign_root
        self._chronological_version = -1
        self._chronological: list[TimelineItem] = []
        self._segments: dict[str, list[str]] = {}
        self._leaf_counts: dict[str, tuple[tuple, int]] = {}
        self.version = -1
        self._active: set[str] = set()

    def expand_active(self, version: int, ids: set[str]) -> set[str]:
        self.version = version
        self._chronological_roots()
        expanded = set(ids)
        for owner in ids:
            expanded.update(self._segments.get(owner, []))
        return expanded

    def project(
        self,
        version: int,
        active: set[str],
        *,
        query: str = "",
        categories: set[str] | None = None,
        open_ids: set[str] | None = None,
    ) -> tuple[list[TimelineItem], int]:
        self.version = version
        self._active = self.expand_active(version, active)
        return self.view(query=query, categories=categories, open_ids=open_ids)

    @staticmethod
    def _category_match(item: TimelineItem, categories: set[str]) -> bool:
        if not categories:
            return True
        if "warnings" in categories and item.severity in {"warning", "error"}:
            return True
        return any(
            item.kind in FILTER_CATEGORIES.get(category, set())
            or item.event_kind in FILTER_CATEGORIES.get(category, set())
            for category in categories
        )

    @staticmethod
    def _clone(item: TimelineItem, children: list[TimelineItem]) -> TimelineItem:
        return TimelineItem(
            item_id=item.item_id,
            kind=item.kind,
            title=item.title,
            summary=item.summary,
            ts=item.ts,
            end_ts=item.end_ts,
            severity=item.severity,
            detail=item.detail,
            children=children,
            default_expanded=item.default_expanded,
            is_group=item.is_group,
            event_id=item.event_id,
            event_kind=item.event_kind,
            payload=item.payload,
            status=item.status,
            role=item.role,
            lazy=item.lazy,
        )

    def _live_tool(self, item: TimelineItem) -> TimelineItem:
        """A running tool shows how long it has been running."""
        if item.kind != "tool" or item.status != "started" or item.ts is None:
            return item
        seconds = max(0.0, (_now() - item.ts).total_seconds())
        if seconds < 1:
            return item
        live = self._clone(item, item.children)
        live.summary = _tool_summary(
            item.payload, item.status, seconds, root=self._campaign_root
        )
        return live

    def _chronological_roots(self) -> list[TimelineItem]:
        """Project ownership into contiguous, independently collapsible segments."""
        if self._chronological_version == self.version:
            return self._chronological
        self._leaf_counts.clear()
        entries: list[tuple[datetime, int, tuple[TimelineItem, ...], TimelineItem]] = []
        order = {item_id: n for n, item_id in enumerate(self._items)}
        earliest = datetime.min.replace(tzinfo=UTC)

        def collect(items: list[TimelineItem], path: tuple[TimelineItem, ...]) -> None:
            for item in items:
                owners = (*path, item) if item.is_group else path
                if item.is_group and item.children:
                    collect(item.children, owners)
                else:
                    entries.append(
                        (item.ts or earliest, order[item.item_id], owners, item)
                    )

        collect(self._roots, ())
        entries.sort(key=lambda entry: (entry[0], entry[1]))
        roots: list[TimelineItem] = []
        stack: list[tuple[str, TimelineItem]] = []
        segments: dict[str, list[str]] = {}
        for _, _, owners, item in entries:
            shared = 0
            while (
                shared < min(len(stack), len(owners))
                and stack[shared][0] == owners[shared].item_id
            ):
                shared += 1
            del stack[shared:]
            for owner in owners[shared:]:
                segment = self._clone(owner, [])
                previous = segments.setdefault(owner.item_id, [])
                if previous:
                    segment.item_id = f"{owner.item_id}:continued:{item.item_id}"
                    segment.title += " (continued)"
                segment.ts = item.ts
                segment.end_ts = segment.ts
                previous.append(segment.item_id)
                (stack[-1][1].children if stack else roots).append(segment)
                stack.append((owner.item_id, segment))
            if not item.is_group:
                (stack[-1][1].children if stack else roots).append(item)
            for _, segment in stack:
                if item.ts is not None:
                    segment.end_ts = max(segment.end_ts or item.ts, item.ts)
        self._segments = segments
        self._chronological = roots
        self._chronological_version = self.version
        return roots

    def _leaf_count(self, item: TimelineItem) -> int:
        """Events inside a group; cached until the group itself changes."""
        key = (len(item.children), item.end_ts)
        cached = self._leaf_counts.get(item.item_id)
        if cached is not None and cached[0] == key:
            return cached[1]

        def count(node: TimelineItem) -> int:
            if not node.is_group:
                return 1
            return sum(count(child) for child in node.children)

        total = count(item)
        self._leaf_counts[item.item_id] = (key, total)
        return total

    def _fast_view(self, open_ids: set[str] | None) -> tuple[list[TimelineItem], int]:
        """The unfiltered view in one pass. A finished session that nobody has
        opened is shown folded, so the cost follows what is open, not how long
        the campaign has run."""
        active = self._active
        matches = 0

        def build(item: TimelineItem) -> TimelineItem:
            nonlocal matches
            if not item.is_group:
                matches += 1
                return self._live_tool(item)
            if (
                open_ids is not None
                and item.kind == "session"
                and item.status == "closed"
                and item.item_id not in active
                and item.item_id not in open_ids
            ):
                folded = self._clone(item, [])
                folded.lazy = self._leaf_count(item)
                matches += folded.lazy
                return folded
            return self._clone(item, [build(child) for child in item.children])

        roots = [build(root) for root in self._chronological_roots()]
        return roots, matches

    def view(
        self,
        *,
        query: str = "",
        categories: set[str] | None = None,
        open_ids: set[str] | None = None,
    ) -> tuple[list[TimelineItem], int]:
        query = query.strip().casefold()
        categories = categories or set()
        if not query and not categories:
            return self._fast_view(open_ids)
        matches = 0

        def include(
            item: TimelineItem, ancestor_match: bool = False
        ) -> TimelineItem | None:
            nonlocal matches
            text_match = ancestor_match or not query or query in item.searchable()
            if not item.is_group:
                keep = text_match and self._category_match(item, categories)
                if keep:
                    matches += 1
                return self._live_tool(item) if keep else None
            child_items: list[TimelineItem] = []
            for child in item.children:
                filtered = include(child, bool(query and text_match))
                if filtered is not None:
                    child_items.append(filtered)
            keep = bool(child_items) or (
                text_match
                and self._category_match(item, categories)
                and not item.children
            )
            if not keep:
                return None
            return self._clone(item, child_items)

        roots: list[TimelineItem] = []
        for root in self._chronological_roots():
            filtered = include(root)
            if filtered is not None:
                roots.append(filtered)
        return roots, matches
