"""Child processes under the launcher's cooperative stop and its run log."""

from __future__ import annotations

import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from runner.launcher.stop import StopControl, StopDeadlineExceeded
from runner.stop_control import STOP_REQUEST_ENV

POLL_SECONDS = 0.1


class RunLog:
    """One diagnostic file per launcher run; children write into it directly."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._stream: BinaryIO = open(path, "ab", buffering=0)  # noqa: SIM115

    @classmethod
    def for_campaign(cls, campaign_root: Path) -> RunLog:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        return cls(
            campaign_root / "reports" / "launcher" / f"{stamp}-{os.getpid()}.log"
        )

    @property
    def stream(self) -> BinaryIO:
        return self._stream

    def write(self, text: str) -> None:
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        self._stream.write(f"[{stamp}] {text.rstrip()}\n".encode())

    def close(self) -> None:
        self._stream.close()


def kill_tree(process: subprocess.Popen) -> None:
    """Terminate a child and all its descendants."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:  # pragma: no cover - Windows is the supported platform
        process.kill()


class ChildRunner:
    """Starts children with the campaign environment and polls the stop request."""

    def __init__(self, *, cwd: Path, stop: StopControl, log: RunLog) -> None:
        self._cwd = cwd
        self._stop = stop
        self._log = log

    def environment(self) -> dict[str, str]:
        environment = dict(os.environ)
        environment[STOP_REQUEST_ENV] = str(self._stop.path)
        environment["PYTHONIOENCODING"] = "utf-8"
        environment["PYTHONUNBUFFERED"] = "1"
        return environment

    def start(
        self, command: list[str], *, stdin=subprocess.DEVNULL
    ) -> subprocess.Popen:
        self._log.write("start: " + subprocess.list2cmdline(command))
        return subprocess.Popen(
            command,
            cwd=self._cwd,
            env=self.environment(),
            stdin=stdin,
            stdout=self._log.stream,
            stderr=self._log.stream,
        )

    def run(
        self, command: list[str], *, operation: str, input_text: str | None = None
    ) -> int:
        """Wait for a child; kill its tree once the stop deadline has passed."""
        process = self.start(
            command,
            stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
        )
        if input_text is not None:
            process.stdin.write(input_text.encode("utf-8"))
            process.stdin.close()
        while process.poll() is None:
            if self._stop.deadline_passed():
                self._stop.deadline_exceeded = True
                kill_tree(process)
                process.wait()
                raise StopDeadlineExceeded(
                    "The cooperative stop deadline expired while waiting for "
                    f"{operation} (PID {process.pid})."
                )
            time.sleep(POLL_SECONDS)
        self._stop.requested()
        self._log.write(f"exit {process.returncode}: {operation}")
        return int(process.returncode)
