"""The persistent Copilot runtime process and its JSON-lines control channel."""

from __future__ import annotations

import json
import socket
import subprocess
import time
import uuid
from collections.abc import Callable

from runner.launcher.child import ChildRunner, kill_tree
from runner.launcher.runner_client import LauncherError
from runner.launcher.stop import StopControl, StopDeadlineExceeded

_SLICE_SECONDS = 0.1
_CONNECT_SECONDS = 120
_SHUTDOWN_SECONDS = 45
_BOOTSTRAP_GRACE_SECONDS = 5


class CopilotRuntime:
    """Starts the adapter once per launcher run and exchanges bound messages."""

    def __init__(
        self,
        *,
        children: ChildRunner,
        stop: StopControl,
        command: Callable[[int, str], list[str]],
        before_start: Callable[[], None],
    ) -> None:
        self._children = children
        self._stop = stop
        self._command = command
        self._before_start = before_start
        self._process: subprocess.Popen | None = None
        self._connection: socket.socket | None = None
        self._buffer = b""

    def start(self) -> None:
        if self._stop.requested():
            return
        if self._process is not None:
            if self._process.poll() is not None:
                raise LauncherError(
                    "The owned Copilot runtime stopped; refusing an in-run replacement."
                )
            return
        self._before_start()
        listener = socket.create_server(("127.0.0.1", 0))
        try:
            token = str(uuid.uuid4()) + str(uuid.uuid4())
            port = listener.getsockname()[1]
            self._process = self._children.start(self._command(port, token))
            listener.settimeout(_SLICE_SECONDS)
            deadline = time.monotonic() + _CONNECT_SECONDS
            while True:
                try:
                    connection, _address = listener.accept()
                    break
                except TimeoutError:
                    if self._stop.requested():
                        return
                    if self._process.poll() is not None or time.monotonic() >= deadline:
                        raise LauncherError(
                            "Copilot runtime did not connect to its launcher."
                        ) from None
            connection.settimeout(_SLICE_SECONDS)
            self._connection = connection
            hello = self.receive(timeout_seconds=_CONNECT_SECONDS)
            if hello.get("type") != "ready" or hello.get("token") != token:
                raise LauncherError(
                    "Copilot controller authentication or runtime readiness failed."
                )
        finally:
            listener.close()

    def send(self, message: dict) -> None:
        line = json.dumps(message, ensure_ascii=False) + "\n"
        self._connection.sendall(line.encode("utf-8"))

    def receive(self, *, timeout_seconds: float = 0) -> dict:
        deadline = time.monotonic() + timeout_seconds
        while b"\n" not in self._buffer:
            if timeout_seconds > 0 and time.monotonic() >= deadline:
                raise LauncherError("Copilot controller readiness timed out.")
            if self._stop.deadline_passed():
                self._stop.deadline_exceeded = True
                raise StopDeadlineExceeded(
                    "Copilot controller cooperative stop deadline expired."
                )
            if self._process.poll() is not None and not self._readable():
                raise LauncherError(
                    f"Copilot runtime exited with code {self._process.returncode}."
                )
            try:
                chunk = self._connection.recv(1 << 16)
            except TimeoutError:
                continue
            if not chunk:
                raise LauncherError(
                    "Copilot control channel closed; durable Runner state must be recovered."
                )
            self._buffer += chunk
        line, self._buffer = self._buffer.split(b"\n", 1)
        message = json.loads(line.decode("utf-8"))
        if not isinstance(message, dict):
            raise LauncherError("Copilot control message must be an object.")
        return message

    def _readable(self) -> bool:
        try:
            self._connection.setblocking(False)
            try:
                return bool(self._connection.recv(1, socket.MSG_PEEK))
            finally:
                self._connection.settimeout(_SLICE_SECONDS)
        except (BlockingIOError, OSError):
            return False

    def stop(self) -> None:
        if self._process is None:
            return
        try:
            if self._process.poll() is None:
                if self._connection is None and self._stop.requested():
                    self._cancel_bootstrap()
                    return
                if self._connection is not None:
                    try:
                        self.send({"type": "shutdown"})
                    except OSError:
                        pass
                try:
                    self._process.wait(_SHUTDOWN_SECONDS)
                except subprocess.TimeoutExpired:
                    kill_tree(self._process)
                    self._process.wait()
                    raise LauncherError(
                        "Owned Copilot runtime exceeded its cooperative shutdown deadline."
                    ) from None
        finally:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
            self._process = None

    def _cancel_bootstrap(self) -> None:
        """No session was sent without a channel; end only the bootstrap tree."""
        grace = _BOOTSTRAP_GRACE_SECONDS
        remaining = self._stop.remaining_seconds()
        if remaining is not None:
            grace = min(grace, remaining)
        try:
            self._process.wait(grace)
        except subprocess.TimeoutExpired:
            kill_tree(self._process)
            try:
                self._process.wait(5)
            except subprocess.TimeoutExpired:
                raise LauncherError(
                    "Owned Copilot bootstrap did not exit after cancellation."
                ) from None
