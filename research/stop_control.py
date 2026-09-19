"""Run-scoped cooperative stop requests shared by launcher children."""

from __future__ import annotations

import _thread
import asyncio
import os
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

STOP_REQUEST_ENV = "ROBOT_RESEARCH_STOP_REQUEST"
POLL_SECONDS = 0.1


def stop_request_path() -> Path | None:
    value = os.environ.get(STOP_REQUEST_ENV)
    return Path(value) if value else None


def stop_requested(path: Path | None = None) -> bool:
    request = path if path is not None else stop_request_path()
    return request is not None and request.is_file()


async def wait_for_stop_request(path: Path | None = None) -> None:
    request = path if path is not None else stop_request_path()
    if request is None:
        await asyncio.Event().wait()
        return
    while not request.is_file():
        await asyncio.sleep(POLL_SECONDS)


@contextmanager
def interrupt_on_stop_request(
    path: Path | None = None,
    *,
    interrupt: Callable[[], None] = _thread.interrupt_main,
    poll_seconds: float = POLL_SECONDS,
) -> Iterator[None]:
    """Raise KeyboardInterrupt on the main thread when the request appears."""
    request = path if path is not None else stop_request_path()
    if request is None:
        yield
        return

    closed = threading.Event()

    def watch() -> None:
        while not closed.wait(poll_seconds):
            if request.is_file():
                interrupt()
                return

    thread = threading.Thread(
        target=watch,
        name="research-stop-request",
        daemon=True,
    )
    thread.start()
    try:
        yield
    finally:
        closed.set()
        thread.join()
