"""Cooperative stop: one request file per campaign and a shutdown deadline."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path


class StopDeadlineExceeded(RuntimeError):
    """The cooperative stop deadline expired; the launcher exits with 124."""


class StopControl:
    """Level-triggered stop request with a deadline from its first observation."""

    def __init__(
        self,
        path: Path,
        timeout_seconds: int,
        *,
        started_at: float,
        on_request: Callable[[str], None] = lambda _message: None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.path = path
        self.timeout_seconds = timeout_seconds
        self._started_at = started_at
        self._on_request = on_request
        self._clock = clock
        self._requested = False
        self.deadline: float | None = None
        self.deadline_exceeded = False

    def discard_stale(self) -> None:
        """Drop a request left by an earlier run; a newer one is honored."""
        try:
            if self.path.stat().st_mtime < self._started_at:
                self.path.unlink(missing_ok=True)
        except FileNotFoundError:
            pass

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)

    def request(self, message: str) -> bool:
        if self._requested:
            return True
        self._requested = True
        self.deadline = self._clock() + self.timeout_seconds
        self._on_request(
            f"{message}; waiting up to {self.timeout_seconds} seconds for "
            "cooperative shutdown."
        )
        return True

    def requested(self) -> bool:
        if self._requested:
            return True
        if self.path.is_file():
            return self.request("External stop requested")
        return False

    def deadline_passed(self) -> bool:
        return (
            self.requested()
            and self.deadline is not None
            and self._clock() >= self.deadline
        )

    def remaining_seconds(self) -> float | None:
        if self.deadline is None:
            return None
        return max(0.0, self.deadline - self._clock())
