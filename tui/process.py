"""Windows process containment for TUI-owned campaign launchers.

Owns the parts of the external-stop contract that must run inside the
controller process (see ``docs/external-campaign-stop.md``):

- a kill-on-close Job Object per launcher invocation;
- suspended child creation before Job assignment, new process groups, so a
  terminal Ctrl+C used for copying cannot reach the campaign;
- per-run private control directories (diagnostic logs) kept outside campaign
  state and outside the harness worktree;
- a single-instance lock keyed to the canonical harness directory.

The cooperative stop request is the campaign's own request file
(``runner.paths.stop_request_path``), whoever started the launcher.

No third-party dependency: ``ctypes`` only. The logic is Windows-only; the
module raises :class:`NotImplementedError` on other platforms instead of
silently degrading containment guarantees.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

if os.name != "nt":  # pragma: no cover - platform guard, Windows development
    raise NotImplementedError("campaign control requires Windows")


import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# Creation flags
_CREATE_SUSPENDED = 0x00000004
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_CREATE_UNICODE_ENVIRONMENT = 0x00000400
_CREATE_NEW_CONSOLE = 0x00000010
_EXTENDED_STARTUPINFO_PRESENT = 0x00080000
_PROC_THREAD_ATTRIBUTE_DESKTOP_APP_POLICY = 0x00020012
_PROCESS_CREATION_DESKTOP_APP_BREAKAWAY_DISABLE_PROCESS_TREE = 0x02

# Job limits
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_SYNCHRONIZE = 0x00100000
_JobObjectExtendedLimitInformation = 9
# JobObjectBasicProcessIdList per QueryInformationJobObject docs (winnt.h
# list struct: two DWORD counters, then pointer-sized ids).
_JobObjectBasicProcessIdList = 3

_WAIT_OBJECT_0 = 0x00000000
_WAIT_TIMEOUT = 0x00000102
_INFINITE = 0xFFFFFFFF
_STILL_ACTIVE = 259
_ERROR_ALREADY_EXISTS = 183
_HANDLE_FLAG_INHERIT = 0x00000001
_GENERIC_WRITE = 0x40000000
_GENERIC_READ = 0x80000000
_OPEN_EXISTING = 3
_FILE_SHARE_READ = 1
_NUL_PATH = "\\\\.\\NUL"
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [("value", ctypes.c_ulonglong * 6)]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("_affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.c_void_p),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


_STARTF_USESTDHANDLES = 0x00000100
_STARTF_USESHOWWINDOW = 0x00000001


class _STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [
        ("StartupInfo", _STARTUPINFOW),
        ("lpAttributeList", ctypes.c_void_p),
    ]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


for _name, _restype, _argtypes in (
    ("CreateJobObjectW", wintypes.HANDLE, [ctypes.c_void_p, wintypes.LPCWSTR]),
    (
        "SetInformationJobObject",
        wintypes.BOOL,
        [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD],
    ),
    (
        "QueryInformationJobObject",
        wintypes.BOOL,
        [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ],
    ),
    (
        "AssignProcessToJobObject",
        wintypes.BOOL,
        [wintypes.HANDLE, wintypes.HANDLE],
    ),
    (
        "CreateFileW",
        wintypes.HANDLE,
        [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ],
    ),
    (
        "CreateProcessW",
        wintypes.BOOL,
        [
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.BOOL,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.LPCWSTR,
            ctypes.POINTER(_STARTUPINFOW),
            ctypes.POINTER(_PROCESS_INFORMATION),
        ],
    ),
    ("TerminateProcess", wintypes.BOOL, [wintypes.HANDLE, wintypes.UINT]),
    ("ResumeThread", wintypes.DWORD, [wintypes.HANDLE]),
    (
        "TerminateJobObject",
        wintypes.BOOL,
        [wintypes.HANDLE, wintypes.DWORD],
    ),
    (
        "WaitForSingleObject",
        wintypes.DWORD,
        [wintypes.HANDLE, wintypes.DWORD],
    ),
    (
        "GetExitCodeProcess",
        wintypes.BOOL,
        [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)],
    ),
    ("CloseHandle", wintypes.BOOL, [wintypes.HANDLE]),
    (
        "SetHandleInformation",
        wintypes.BOOL,
        [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD],
    ),
    (
        "CreateMutexW",
        wintypes.HANDLE,
        [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR],
    ),
    (
        "InitializeProcThreadAttributeList",
        wintypes.BOOL,
        [
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_size_t),
        ],
    ),
    (
        "UpdateProcThreadAttribute",
        wintypes.BOOL,
        [
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.c_size_t,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ],
    ),
    ("DeleteProcThreadAttributeList", None, [ctypes.c_void_p]),
):
    function = getattr(kernel32, _name)
    function.restype = _restype
    function.argtypes = _argtypes


def _raise_winerror(context: str) -> None:
    error = ctypes.get_last_error()
    raise OSError(f"{context}: WinError {error}")


def _environment_block(env: dict[str, str]) -> bytes:
    entries = [f"{key}={value}" for key, value in env.items()]
    return ("".join(entry + "\0" for entry in entries) + "\0").encode("utf-16-le")


@contextmanager
def _desktop_app_attributes():
    """Keep packaged-app descendants inside their runtime and owning job.

    Desktop Bridge defaults to child breakaway. This documented Windows
    creation policy is inherited by descendants; it also works for unpackaged
    executables. It changes only this owned process tree, not the installation.
    """
    size = ctypes.c_size_t()
    kernel32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
    if not size.value:
        _raise_winerror("sizing the process creation attributes")
    attributes = ctypes.create_string_buffer(size.value)
    if not kernel32.InitializeProcThreadAttributeList(
        attributes, 1, 0, ctypes.byref(size)
    ):
        _raise_winerror("initializing the process creation attributes")
    policy = wintypes.DWORD(
        _PROCESS_CREATION_DESKTOP_APP_BREAKAWAY_DISABLE_PROCESS_TREE
    )
    try:
        if not kernel32.UpdateProcThreadAttribute(
            attributes,
            0,
            _PROC_THREAD_ATTRIBUTE_DESKTOP_APP_POLICY,
            ctypes.byref(policy),
            ctypes.sizeof(policy),
            None,
            None,
        ):
            _raise_winerror("disabling packaged process-tree breakaway")
        yield ctypes.cast(attributes, ctypes.c_void_p)
    finally:
        kernel32.DeleteProcThreadAttributeList(attributes)


def _canonical(path: Path) -> str:
    resolved = str(path.resolve()).replace("/", "\\").rstrip("\\")
    return resolved.lower()


def instance_lock_name(harness_root: Path) -> str:
    digest = hashlib.sha256(_canonical(harness_root).encode("utf-8")).hexdigest()[:16]
    return f"Local\\RobotLearningTui-{digest}"


@dataclass
class InstanceLock:
    """Application-level single-instance guard for one harness directory."""

    handle: wintypes.HANDLE
    name: str

    def release(self) -> None:
        if self.handle is not None:
            kernel32.CloseHandle(self.handle)
            self.handle = None


def acquire_instance_lock(harness_root: Path) -> InstanceLock | None:
    """Acquire the per-harness-directory TUI lock, or ``None`` if held."""
    name = instance_lock_name(harness_root)
    ctypes.set_last_error(0)
    handle = kernel32.CreateMutexW(None, False, name)
    if not handle:
        _raise_winerror("acquiring the campaign-console instance lock")
    if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return None
    return InstanceLock(handle=handle, name=name)


class ConsoleLog:
    """Per-run diagnostic files for a launcher child (stdout/stderr)."""

    def __init__(self, control_directory: Path) -> None:
        self.control_directory = control_directory
        self.stdout_path = control_directory / "console.out.log"
        self.stderr_path = control_directory / "console.err.log"
        self._handles: list[int] = []
        try:
            self._stdout = self._open_append(self.stdout_path)
            self._stderr = self._open_append(self.stderr_path)
        except OSError:
            self.close()
            raise

    def _open_append(self, path: Path) -> wintypes.HANDLE:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        handle = kernel32.CreateFileW(
            str(path),
            _GENERIC_WRITE,
            _FILE_SHARE_READ,
            None,
            _OPEN_EXISTING,
            0,
            None,
        )
        if not handle or handle == INVALID_HANDLE_VALUE:
            _raise_winerror(f"opening {path}")
        if not kernel32.SetHandleInformation(
            handle, _HANDLE_FLAG_INHERIT, _HANDLE_FLAG_INHERIT
        ):
            kernel32.CloseHandle(handle)
            _raise_winerror(f"making {path} inheritable")
        self._handles.append(handle)
        return handle

    @property
    def stdin_path(self) -> wintypes.HANDLE:
        handle = kernel32.CreateFileW(
            _NUL_PATH, _GENERIC_READ, _FILE_SHARE_READ, None, _OPEN_EXISTING, 0, None
        )
        if not handle or handle == INVALID_HANDLE_VALUE:
            _raise_winerror("opening NUL for child stdin")
        # The stdin handle must be inheritable: a non-inheritable std handle
        # reaches the child as a value that its own handle table does not
        # contain, and the child then furthers that dangling value to its own
        # spawns. `uv run` fails with "The handle is invalid" in that case
        # because Rust std forwards GetStdHandle results to CreateProcess.
        if not kernel32.SetHandleInformation(
            handle, _HANDLE_FLAG_INHERIT, _HANDLE_FLAG_INHERIT
        ):
            kernel32.CloseHandle(handle)
            _raise_winerror("making the child stdin inheritable")
        self._handles.append(handle)
        return handle

    def close(self) -> None:
        for handle in self._handles:
            kernel32.CloseHandle(handle)
        self._handles = []


def create_stop_request(stop_request_path: Path) -> bool:
    """Raise the request; ``False`` when one was already pending.

    Writing refreshes the time stamp, so a launcher that is still starting does
    not mistake the request for one left by an earlier run.
    """
    existed = stop_request_path.exists()
    stop_request_path.write_text("", encoding="utf-8")
    return not existed


@dataclass
class SupervisedLauncher:
    """One launcher invocation under Job containment.

    A launcher job is named and does not kill on close, so the console can leave
    it running (``detach``). A helper job (reset, initialize) kills on close.
    """

    pid: int
    job: wintypes.HANDLE
    _process: wintypes.HANDLE
    _thread: wintypes.HANDLE
    _log: ConsoleLog
    stop_request: Path | None = None
    stop_requested: bool = False
    _exit_code: int | None = None
    kill_on_close: bool = True

    # -- Observations ------------------------------------------------------
    def poll(self) -> bool:
        """``True`` when the launcher has exited."""
        if self._exit_code is not None:
            return True
        result = kernel32.WaitForSingleObject(self._process, 0)
        if result == _WAIT_OBJECT_0:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(self._process, ctypes.byref(code)):
                _raise_winerror("reading launcher exit code")
            self._exit_code = code.value
            return True
        return False

    @property
    def exit_code(self) -> int | None:
        return self._exit_code

    def last_error_line(self, limit: int = 400) -> str:
        """The last line the launcher wrote to standard error, if any."""
        try:
            text = self._log.stderr_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return lines[-1][:limit] if lines else ""

    def wait(self, seconds: float) -> int:
        """Block until the launcher exits or ``seconds`` elapse."""
        deadline = time.monotonic() + max(0.0, seconds)
        while not self.poll():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.05, remaining))
        return self._exit_code if self._exit_code is not None else _STILL_ACTIVE

    # -- Control -----------------------------------------------------------
    def request_stop(self) -> bool:
        """Cooperative stop; ``False`` when a request already exists."""
        if self.stop_requested or self.stop_request is None:
            return False
        created = create_stop_request(self.stop_request)
        self.stop_requested = True
        return created

    def force_stop(self, timeout: float = 15.0) -> None:
        """Emergency cleanup only: terminate the job and confirm it empties."""
        if not kernel32.TerminateJobObject(self.job, 1):
            _raise_winerror("terminating the campaign job object")
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            if self.poll() and not self.job_process_ids():
                return
            if time.monotonic() >= deadline:
                raise TimeoutError("The campaign job did not empty after termination.")
            time.sleep(0.05)

    def job_process_ids(self) -> list[int]:
        """Processes currently assigned to the containment job."""
        return _job_process_ids(self.job)

    def detach(self) -> None:
        """Let the launcher and everything it started keep running without us.

        Only a launcher job can be left: a helper job kills on close.
        """
        if self.kill_on_close:
            raise RuntimeError("This job kills its processes when it closes.")
        self.close()

    def close(self) -> None:
        """Release all owned handles. A kill-on-close job kills what remains in
        it; a launcher job leaves it running."""
        for name in ("job", "_thread", "_process"):
            handle = getattr(self, name)
            if handle:
                kernel32.CloseHandle(handle)
                setattr(self, name, None)
        self._log.close()


def _job_process_ids(job) -> list[int]:
    """Processes assigned to a job object."""
    # JOBOBJECT_BASIC_PROCESS_ID_LIST: two DWORD counters followed by
    # pointer-sized process ids. A too-small buffer fails with
    # ERROR_MORE_DATA; the process count can grow between queries.
    attempted = 8 + 64 * ctypes.sizeof(ctypes.c_size_t)
    for _ in range(8):
        buffer = ctypes.create_string_buffer(attempted)
        returned = wintypes.DWORD(0)
        if kernel32.QueryInformationJobObject(
            job,
            _JobObjectBasicProcessIdList,
            buffer,
            attempted,
            ctypes.byref(returned),
        ):
            break
        if ctypes.get_last_error() != 234:  # ERROR_MORE_DATA
            _raise_winerror("querying the campaign job processes")
        attempted = max(attempted * 2, returned.value)
    else:
        raise RuntimeError("The campaign job process list kept growing.")
    listed = int.from_bytes(buffer.raw[4:8], "little")
    ids: list[int] = []
    for index in range(listed):
        offset = 8 + index * ctypes.sizeof(ctypes.c_size_t)
        if offset + ctypes.sizeof(ctypes.c_size_t) > returned.value:
            raise RuntimeError("The campaign job returned a truncated process list.")
        ids.append(
            int.from_bytes(
                buffer.raw[offset : offset + ctypes.sizeof(ctypes.c_size_t)],
                "little",
            )
        )
    return ids


def _process_creation_time(process) -> int:
    """The creation time of a process handle as a 64-bit FILETIME value."""
    created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
    if not kernel32.GetProcessTimes(
        process,
        ctypes.byref(created),
        ctypes.byref(exited),
        ctypes.byref(kernel),
        ctypes.byref(user),
    ):
        _raise_winerror("reading a process creation time")
    return (created.dwHighDateTime << 32) | created.dwLowDateTime


def launcher_record_path(folder: Path) -> Path:
    """Where the console that started a campaign's launcher noted its process.

    It lives outside the campaign and the harness, keyed by the campaign folder,
    so any console can find it. Windows destroys a job object when its last
    handle closes, so a launcher left running has no job another console could
    open; its process, checked against this record, is what a later ``kill`` ends.
    """
    from runner.launcher.campaign_lock import mutex_name

    digest = mutex_name(Path(folder)).rsplit("-", 1)[1]
    return control_root() / "launchers" / f"{digest}.json"


def write_launcher_record(folder: Path, child: SupervisedLauncher) -> None:
    path = launcher_record_path(folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"pid": child.pid, "created": _process_creation_time(child._process)}
    path.write_text(json.dumps(record), encoding="utf-8")


def remove_launcher_record(folder: Path) -> None:
    try:
        launcher_record_path(folder).unlink()
    except OSError:
        pass


def kill_recorded_launcher(folder: Path, timeout: float = 15.0) -> bool:
    """End the launcher recorded for ``folder`` and everything it started.

    ``False`` when no console recorded one, or the recorded process is gone or
    is not the same process any more (its PID was reused).
    """
    path = launcher_record_path(folder)
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        pid, created = int(record["pid"]), int(record["created"])
    except (OSError, ValueError, KeyError, TypeError):
        return False
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    handle = kernel32.OpenProcess(
        _PROCESS_QUERY_LIMITED_INFORMATION | _SYNCHRONIZE, False, pid
    )
    if not handle:
        remove_launcher_record(folder)
        return False
    try:
        if kernel32.WaitForSingleObject(handle, 0) != _WAIT_TIMEOUT:
            remove_launcher_record(folder)
            return False
        if _process_creation_time(handle) != created:
            remove_launcher_record(folder)
            return False
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            check=False,
            timeout=timeout,
        )
        if kernel32.WaitForSingleObject(handle, int(timeout * 1000)) != _WAIT_OBJECT_0:
            raise TimeoutError("The launcher did not end after termination.")
        remove_launcher_record(folder)
        return True
    finally:
        kernel32.CloseHandle(handle)


class JobHandle:
    """Handle wrapper for one Job Object; keep it open for containment."""

    def __init__(self, *, kill_on_close: bool = True) -> None:
        self.handle = kernel32.CreateJobObjectW(None, None)
        if not self.handle:
            _raise_winerror("creating the campaign job object")
        limits = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        ctypes.memset(ctypes.byref(limits), 0, ctypes.sizeof(limits))
        limits.BasicLimitInformation.LimitFlags = (
            _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE if kill_on_close else 0
        )
        if not kernel32.SetInformationJobObject(
            self.handle,
            _JobObjectExtendedLimitInformation,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            kernel32.CloseHandle(self.handle)
            _raise_winerror("configuring the campaign job limits")

    def close(self) -> None:
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None


def _uv_executable() -> str:
    found = shutil.which("uv")
    if found:
        return found
    raise RuntimeError(
        "The campaign console requires uv on PATH. "
        "No campaign was initialized, reset or started."
    )


class LauncherBuilder:
    """Creates a supervised launcher with Job containment."""

    def __init__(self, harness_root: Path) -> None:
        self.harness_root = harness_root

    def start(
        self,
        arguments: list[str],
        control_directory: Path,
        *,
        stop_request: Path,
        env: dict[str, str] | None = None,
    ) -> SupervisedLauncher:
        child = self.start_command(
            [
                _uv_executable(),
                "run",
                "--project",
                str(self.harness_root),
                "--group",
                "researcher",
                "python",
                "-m",
                "runner.launcher",
                *arguments,
            ],
            control_directory,
            env=env,
            kill_on_close=False,
        )
        child.stop_request = stop_request
        return child

    def start_command(
        self,
        command: list[str],
        control_directory: Path,
        env: dict[str, str] | None = None,
        *,
        kill_on_close: bool = True,
    ) -> SupervisedLauncher:
        """The contained boundary for a launcher or an initializer/reset helper."""
        control_directory.mkdir(parents=True, exist_ok=True)
        environment = dict(env if env is not None else os.environ)
        command_line = subprocess.list2cmdline(command)
        log = ConsoleLog(control_directory)
        job = None
        process_information = _PROCESS_INFORMATION()
        try:
            job = JobHandle(kill_on_close=kill_on_close)
            extended_startup = _STARTUPINFOEXW()
            startup = extended_startup.StartupInfo
            startup.cb = ctypes.sizeof(extended_startup)
            startup.dwFlags = _STARTF_USESTDHANDLES | _STARTF_USESHOWWINDOW
            startup.wShowWindow = 0  # SW_HIDE: descendants inherit a private console.
            startup.hStdInput = log.stdin_path
            startup.hStdOutput = log._stdout
            startup.hStdError = log._stderr
            ctypes.memset(
                ctypes.byref(process_information), 0, ctypes.sizeof(process_information)
            )
            command_buffer = ctypes.create_unicode_buffer(command_line)
            with _desktop_app_attributes() as attributes:
                extended_startup.lpAttributeList = attributes
                created = kernel32.CreateProcessW(
                    None,
                    command_buffer,
                    None,
                    None,
                    True,
                    _CREATE_SUSPENDED
                    | _CREATE_NEW_PROCESS_GROUP
                    | _CREATE_NEW_CONSOLE
                    | _CREATE_UNICODE_ENVIRONMENT
                    | _EXTENDED_STARTUPINFO_PRESENT,
                    ctypes.cast(
                        ctypes.create_string_buffer(_environment_block(environment)),
                        ctypes.c_void_p,
                    ),
                    str(self.harness_root),
                    ctypes.cast(
                        ctypes.byref(extended_startup), ctypes.POINTER(_STARTUPINFOW)
                    ),
                    ctypes.byref(process_information),
                )
                if not created:
                    _raise_winerror("creating the suspended launcher process")
            if not kernel32.AssignProcessToJobObject(
                job.handle, process_information.hProcess
            ):
                _raise_winerror("assigning the launcher to the containment job")
            if kernel32.ResumeThread(process_information.hThread) == 0xFFFFFFFF:
                _raise_winerror("resuming the contained launcher")
            # The child now owns its inherited copies. Do not leave inheritable
            # log handles around for a subsequent campaign to inherit.
            log.close()
            return SupervisedLauncher(
                pid=process_information.dwProcessId,
                job=job.handle,
                _process=process_information.hProcess,
                _thread=process_information.hThread,
                _log=log,
                kill_on_close=kill_on_close,
            )
        except Exception:
            if process_information.hProcess:
                kernel32.TerminateProcess(process_information.hProcess, 1)
                kernel32.WaitForSingleObject(process_information.hProcess, 5000)
                kernel32.CloseHandle(process_information.hProcess)
            if process_information.hThread:
                kernel32.CloseHandle(process_information.hThread)
            if job is not None:
                job.close()
            log.close()
            raise


def control_root() -> Path:
    """Private per-run control directories live only in the user temp area."""
    base = Path(os.environ.get("TEMP") or os.environ.get("TMP") or os.getcwd())
    return base / "robot-learning" / "tui"


def new_control_directory(control_root_path: Path | None = None) -> Path:
    root = control_root_path if control_root_path is not None else control_root()
    directory = root / f"run-{time.time_ns():020x}"
    directory.mkdir(parents=True, exist_ok=False)
    return directory


class LauncherMachinery:
    """``ProcessMachinery`` adapter around :class:`LauncherBuilder`.

    One child per campaign folder at a time. Its console logs live in the
    controller's control directory; its stop request is the campaign's own.
    """

    def __init__(self, harness_root: Path) -> None:
        self._harness_root = Path(harness_root)
        self._builder = LauncherBuilder(self._harness_root)
        self._children: dict[Path, SupervisedLauncher] = {}
        self._helper_lock = threading.Lock()
        self._helpers: list[SupervisedLauncher] = []
        self._closing = False

    def preflight(self) -> None:
        _uv_executable()

    def _launch_environment(self) -> dict[str, str]:
        environment = dict(os.environ)
        for override in (
            "TUI_TYPED_EVENTS",
            "ROBOT_LEARNING_CAMPAIGN_ROOT",
        ):
            environment.pop(override, None)
        return environment

    def start(
        self, folder: Path, arguments: list[str], control_directory: Path
    ) -> SupervisedLauncher:
        from runner.paths import stop_request_path

        child = self._builder.start(
            list(arguments),
            control_directory,
            stop_request=stop_request_path(Path(folder)),
            env=self._launch_environment(),
        )
        try:
            write_launcher_record(Path(folder), child)
        except OSError:
            pass  # only a later kill from another console needs it
        self._children[Path(folder)] = child
        return child

    def detach(self, child: SupervisedLauncher) -> None:
        """Leave a launcher running and forget it."""
        child.detach()
        for folder, owned in list(self._children.items()):
            if owned is child:
                del self._children[folder]

    def kill_external(self, folder: Path) -> bool:
        """End the launcher a console recorded for this campaign folder."""
        return kill_recorded_launcher(Path(folder))

    def poll(self, child: SupervisedLauncher) -> bool:
        return child.poll()

    def exit_code(self, child: SupervisedLauncher) -> int | None:
        return child.exit_code

    def failure_reason(self, child: SupervisedLauncher) -> str:
        return child.last_error_line()

    def wait(self, child: SupervisedLauncher, seconds: float) -> int | None:
        code = child.wait(seconds)
        return None if code == _STILL_ACTIVE else code

    def request_stop(self, child: SupervisedLauncher) -> bool:
        return child.request_stop()

    def force_stop(
        self, child: SupervisedLauncher, timeout: float | None = None
    ) -> None:
        child.force_stop(timeout if timeout is not None else 15.0)

    def finish(self, child: SupervisedLauncher) -> None:
        """Verify no descendant remains before releasing a folder for reuse."""
        if child.job_process_ids():
            child.force_stop()
        child.close()
        for folder, owned in list(self._children.items()):
            if owned is child:
                del self._children[folder]
                remove_launcher_record(folder)

    def run(self, arguments: list[str]) -> subprocess.CompletedProcess[str]:
        """Execute command helpers without orphaning them on console exit."""
        if Path(arguments[0]).stem.lower() == "uv":
            arguments = [_uv_executable(), *arguments[1:]]
        with self._helper_lock:
            if self._closing:
                raise RuntimeError("The console is shutting down; helper refused.")
            try:
                child = self._builder.start_command(
                    arguments,
                    new_control_directory(),
                    env=self._launch_environment(),
                )
            except (OSError, RuntimeError) as error:
                return subprocess.CompletedProcess(
                    arguments, 1, stdout="", stderr=str(error)
                )
            self._helpers.append(child)
        try:
            while not child.poll():
                time.sleep(0.05)
            return subprocess.CompletedProcess(
                arguments,
                child.exit_code,
                stdout=child._log.stdout_path.read_text(
                    encoding="utf-8-sig", errors="replace"
                ),
                stderr=child._log.stderr_path.read_text(
                    encoding="utf-8-sig", errors="replace"
                ),
            )
        finally:
            with self._helper_lock:
                self.finish(child)
                self._helpers.remove(child)

    def stop_helpers(self) -> None:
        errors = []
        with self._helper_lock:
            self._closing = True
            for child in self._helpers:
                try:
                    child.force_stop()
                except (OSError, RuntimeError) as error:
                    errors.append(error)
        if errors:
            raise RuntimeError(
                f"Failed to stop {len(errors)} command helper(s): {errors[0]}"
            ) from errors[0]


__all__ = [
    "ConsoleLog",
    "InstanceLock",
    "JobHandle",
    "LauncherBuilder",
    "LauncherMachinery",
    "SupervisedLauncher",
    "acquire_instance_lock",
    "control_root",
    "create_stop_request",
    "instance_lock_name",
    "kill_recorded_launcher",
    "launcher_record_path",
    "new_control_directory",
    "remove_launcher_record",
    "write_launcher_record",
]
