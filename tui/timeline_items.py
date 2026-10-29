"""Terminal-free items shared by timeline reduction and projection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from tui.timeline_formatting import duration as _duration
from tui.timeline_formatting import json_text as _json_text

KIND_GLYPHS = {
    "campaign": "[C]",
    "session": "[S]",
    "inquiry": "[I]",
    "training": "[T]",
    "measurement": "[M]",
    "event": "[E]",
    "operation": "[E]",
    "pi": "[P]",
    "tool": "[>]",
    "coding": "[>]",
    "file": "[~]",
    "result": "[=]",
    "checkpoint": "[#]",
    "role": "[R]",
    "warning": "[!]",
    "error": "[x]",
    "usage": "[U]",
    "log": "[.]",
}


@dataclass
class TimelineItem:
    """One group or leaf in the operator timeline."""

    item_id: str
    kind: str
    title: str
    summary: str = ""
    ts: datetime | None = None
    end_ts: datetime | None = None
    severity: str = "info"
    detail: tuple[str, ...] = ()
    children: list[TimelineItem] = field(default_factory=list)
    default_expanded: bool = False
    is_group: bool = False
    event_id: str = ""
    event_kind: str = ""
    payload: dict = field(default_factory=dict)
    status: str = ""
    role: str = ""
    # Number of events hidden in a closed group that is shown folded.
    lazy: int = 0

    @property
    def glyph(self) -> str:
        return KIND_GLYPHS.get(self.kind, "[.]")

    def duration_text(self) -> str:
        return _duration(self.ts, self.end_ts) if self.is_group else ""

    def searchable(self) -> str:
        parts = [self.title, self.summary, self.kind, self.status, *self.detail]
        if self.payload:
            parts.append(_json_text(self.payload))
        return "\n".join(parts).casefold()
