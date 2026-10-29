"""Confirmed idle periods for automatic tab visibility, outside campaign state."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

from runner.repository import atomic_write_json
from tui.process import control_root, launcher_record_path

IDLE_TAB_SECONDS = 2 * 60 * 60


class TabIdleTracker:
    """Observe off the UI thread; never infer a process exit from log silence."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = (
            directory if directory is not None else control_root() / "tab-idle"
        )

    def observe(
        self, folder: Path, *, active: bool, now: float | None = None
    ) -> float | None:
        now = time.time() if now is None else now
        path = self.directory / launcher_record_path(folder).name
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            record = None
        else:
            record = json.loads(text)
            if not isinstance(record, dict) or "idle_since" not in record:
                raise ValueError(f"Invalid tab idle record: {path}")
            since = record["idle_since"]
            if since is not None and (
                isinstance(since, bool)
                or not isinstance(since, (float, int))
                or not math.isfinite(since)
                or since < 0
            ):
                raise ValueError(f"Invalid tab idle timestamp: {path}")
            if not isinstance(record.get("activity"), str):
                raise ValueError(f"Invalid tab activity identity: {path}")  # noqa: TRY004 - malformed serialized metadata
        activity = "" if active else self._activity_identity(folder)
        since = None
        if not active:
            since = record["idle_since"] if record is not None else None
            if since is None or since > now or record["activity"] != activity:
                since = now
        updated = {"idle_since": since, "activity": activity}
        if updated != record:
            atomic_write_json(path, updated)
        return since

    @staticmethod
    def _activity_identity(folder: Path) -> str:
        """Invalidate old deadlines after an execution/reset we did not observe.

        File changes prove new activity, not its end time. The next confirmed
        stopped observation starts a fresh, conservative idle period.
        """
        paths = [folder / "runner" / "state" / "research_state.json"]
        paths.extend(
            (folder / "reports" / "tui_observations").glob("*.events.v2.jsonl")
        )
        stamps = []
        for path in paths:
            try:
                stamp = path.stat()
            except FileNotFoundError:
                continue
            stamps.append(f"{path.name}:{stamp.st_mtime_ns}:{stamp.st_size}")
        return "|".join(sorted(stamps))
