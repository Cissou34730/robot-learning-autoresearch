"""Windows process containment for TUI-owned campaign launchers.

Owns the parts of the external-stop contract that must run inside the
controller process (see ``docs/external-campaign-stop.md``):

- a kill-on-close Job Object per launcher invocation, so a TUI crash can
  never leave campaign descendants behind;
- suspended child creation before Job assignment, new process groups, so a
  terminal Ctrl+C used for copying cannot reach the campaign;
- per-run private control directories (stop request + diagnostic logs) kept
  outside campaign state and outside the harness worktree;
- a single-instance lock keyed to the canonical harness directory.

No third-party dependency: ``ctypes`` only. The logic is Windows-only; the
module raises :class:`NotImplementedError` on other platforms instead of
silently degrading containment guarantees.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import time
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

# Job limits
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JobObjectExtendedLimitInformation = 9
_JobObjectBasicProcessIdList = 25

_WAIT_OBJECT_0 = 0x00000000
_WAIT_TIMEOUT = 0x00000102
_INFINITE = 0xFFFFFFFF
_STILL_ACTIVE = 259
_ERROR_ALREADY_EXISTS = 183
_HANDLE_FLAG_INHERIT = 0x00000001
_GENERIC_WRITE = 0x40000000
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
    ("GetLastError", wintypes.DWORD, []),
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
    handle = kernel32.CreateMutexW(None, False, name)
    if not handle:
        _raise_winerror("acquiring the campaign-console instance lock")
    if kernel32.GetLastError() == _ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return None
    return InstanceLock(handle=handle, name=name)


class ConsoleLog:
    """Per-run diagnostic files for a launcher child (stdout/stderr)."""

    def __init__(self, control_directory: Path) -> None:
        self.control_directory = control_directory
        self.stdout_path = control_directory / "console.out.log"
        self.stderr_path = control_directory / "console.err.log"
        self.stop_request_path = control_directory / "stop.request"
        self._handles: list[int] = []
        self._stdout = self._open_append(self.stdout_path)
        self._stderr = self._open_append(self.stderr_path)

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
            _raise_winerror(f"making {path} inheritable")
        self._handles.append(handle)
        return handle

    @property
    def stdin_path(self) -> wintypes.HANDLE:
        handle = kernel32.CreateFileW(
            _NUL_PATH, _GENERIC_WRITE, _FILE_SHARE_READ, None, _OPEN_EXISTING, 0, None
        )
        if not handle:
            _raise_winerror("opening NUL for child stdin")
        # The stdin handle must be inheritable: a non-inheritable std handle
        # reaches the child as a value that its own handle table does not
        # contain, and the child then furthers that dangling value to its own
        # spawns. `uv run` fails with "The handle is invalid" in that case
        # because Rust std forwards GetStdHandle results to CreateProcess.
        if not kernel32.SetHandleInformation(
            handle, _HANDLE_FLAG_INHERIT, _HANDLE_FLAG_INHERIT
        ):
            _raise_winerror("making the child stdin inheritable")
        self._handles.append(handle)
        return handle

    def close(self) -> None:
        for handle in self._handles:
            kernel32.CloseHandle(handle)
        self._handles = []


def create_stop_request(stop_request_path: Path) -> bool:
    """Create ``stop.request`` atomically; ``False`` when it already exists."""
    try:
        with open(stop_request_path, "x", encoding="utf-8") as request:
            request.write("")
        return True
    except FileExistsError:
        return False


@dataclass
class SupervisedLauncher:
    """One launcher invocation under kill-on-close Job containment."""

    pid: int
    job: wintypes.HANDLE
    _process: wintypes.HANDLE
    _thread: wintypes.HANDLE
    _log: ConsoleLog
    stop_requested: bool = False
    _exit_code: int | None = None

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

    def wait(self, seconds: float) -> int:
        """Block until the launcher exits or ``seconds`` elapse."""
        while self._exit_code is None:
            if self.poll():
                return self._exit_code
            if seconds <= 0.0:
                break
            time.sleep(min(0.1, seconds))
            seconds -= 0.1
        return self._exit_code if self._exit_code is not None else _STILL_ACTIVE

    # -- Control -----------------------------------------------------------
    def request_stop(self) -> bool:
        """Cooperative stop; ``False`` when a request already exists."""
        if self.stop_requested:
            return False
        self.stop_requested = not create_stop_request(self._log.stop_request_path)
        return self.stop_requested

    def force_stop(self, timeout: float = 15.0) -> None:
        """Terminate everything contained in the job, then wait for empty."""
        if self._exit_code is None:
            if not kernel32.TerminateJobObject(self.job, 1):
                _raise_winerror("terminating the campaign job object")
            self.wait(timeout)
        if self.poll():
            code = wintypes.DWORD()
            kernel32.GetExitCodeProcess(self._process, ctypes.byref(code))
            self._exit_code = code.value
        deadline = time.monotonic() + max(1.0, timeout)
        while time.monotonic() < deadline:
            pids = self.job_process_ids()
            if not pids:
                return
            time.sleep(0.05)

    def job_process_ids(self) -> list[int]:
        size = wintypes.DWORD(0)
        kernel32.QueryInformationJobObject(
            self.job,
            _JobObjectBasicProcessIdList,
            None,
            0,
            ctypes.byref(size),
        )
        if size.value == 0:
            return []
        buffer = ctypes.create_string_buffer(size.value)
        if not kernel32.QueryInformationJobObject(
            self.job,
            _JobObjectBasicProcessIdList,
            buffer,
            size.value,
            ctypes.byref(size),
        ):
            return []
        count, remainder = divmod(
            size.value - ctypes.sizeof(ctypes.c_size_t) * 2,
            ctypes.sizeof(wintypes.DWORD),
        )
        if remainder or count <= 0:
            return []
        start = ctypes.sizeof(ctypes.c_size_t) * 2
        return [
            int.from_bytes(
                buffer.raw[start + index * 4 : start + index * 4 + 4], "little"
            )
            for index in range(count)
        ]

    def close(self) -> None:
        """Release child handles; the job may outlive this call via handle."""
        kernel32.CloseHandle(self._thread)
        kernel32.CloseHandle(self._process)
        self._thread = None
        self._process = None


class JobHandle:
    """Handle wrapper for one Job Object; keep it open for containment."""

    def __init__(self) -> None:
        self.handle = kernel32.CreateJobObjectW(None, None)
        if not self.handle:
            _raise_winerror("creating the campaign job object")
        limits = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        ctypes.memset(ctypes.byref(limits), 0, ctypes.sizeof(limits))
        limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(
            self.handle,
            _JobObjectExtendedLimitInformation,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            _raise_winerror("configuring kill-on-close job limits")

    def close(self) -> None:
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None


def _launcher_executable() -> str:
    for candidate in ("pwsh.exe", "pwsh", "powershell.exe", "powershell"):
        found = shutil.which(candidate)
        if found:
            return found
    raise RuntimeError("Neither pwsh nor powershell was found on PATH.")


class LauncherBuilder:
    """Creates a supervised launcher with Job containment."""

    def __init__(self, harness_root: Path) -> None:
        self.harness_root = harness_root

    def start(
        self,
        script_path: Path,
        arguments: list[str],
        control_directory: Path,
        env: dict[str, str] | None = None,
    ) -> SupervisedLauncher:
        script_path = script_path.resolve()
        if not script_path.is_file():
            raise RuntimeError(f"Launcher script is missing: {script_path}")
        control_directory.mkdir(parents=True, exist_ok=True)
        environment = dict(env if env is not None else os.environ)
        executable = _launcher_executable()
        command_line = subprocess.list2cmdline(
            [
                executable,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
                *arguments,
            ]
        )
        log = ConsoleLog(control_directory)
        job = JobHandle()
        try:
            startup = _STARTUPINFOW()
            ctypes.memset(ctypes.byref(startup), 0, ctypes.sizeof(startup))
            startup.cb = ctypes.sizeof(startup)
            startup.dwFlags = _STARTF_USESTDHANDLES
            startup.hStdInput = log.stdin_path
            startup.hStdOutput = log._stdout
            startup.hStdError = log._stderr
            process_information = _PROCESS_INFORMATION()
            ctypes.memset(
                ctypes.byref(process_information), 0, ctypes.sizeof(process_information)
            )
            command_buffer = ctypes.create_unicode_buffer(command_line)
            created = kernel32.CreateProcessW(
                None,
                command_buffer,
                None,
                None,
                True,
                _CREATE_SUSPENDED
                | _CREATE_NEW_PROCESS_GROUP
                | _CREATE_UNICODE_ENVIRONMENT,
                ctypes.cast(
                    ctypes.create_string_buffer(_environment_block(environment)),
                    ctypes.c_void_p,
                ),
                str(self.harness_root),
                ctypes.byref(startup),
                ctypes.byref(process_information),
            )
            if not created:
                _raise_winerror("creating the suspended launcher process")
            if not kernel32.AssignProcessToJobObject(
                job.handle, process_information.hProcess
            ):
                kernel32.TerminateProcess(process_information.hProcess, 1)
                _raise_winerror("assigning the launcher to the containment job")
            kernel32.ResumeThread(process_information.hThread)
            return SupervisedLauncher(
                pid=process_information.dwProcessId,
                job=job.handle,
                _process=process_information.hProcess,
                _thread=process_information.hThread,
                _log=log,
            )
        except Exception:
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

    One child per campaign folder at a time. The control directory comes from
    the controller's ``-StopRequestPath`` argument so the cooperative stop
    file and the captured console logs live together.
    """

    def __init__(self, harness_root: Path) -> None:
        self._harness_root = Path(harness_root)
        self._builder = LauncherBuilder(self._harness_root)
        self._children: dict[Path, SupervisedLauncher] = {}

    def _control_directory(self, arguments: list[str]) -> tuple[Path, list[str]]:
        if "-StopRequestPath" in arguments:
            index = arguments.index("-StopRequestPath")
            stop_request_path = Path(arguments[index + 1])
            return stop_request_path.parent, arguments
        return new_control_directory(control_root()), arguments

    def _launch_environment(self) -> dict[str, str]:
        environment = dict(os.environ)
        for override in (
            "TUI_OBSERVATIONS",
            "TUI_TYPED_EVENTS",
            "ROBOT_LEARNING_CAMPAIGN_ROOT",
        ):
            environment.pop(override, None)
        return environment

    def start(self, folder: Path, arguments: list[str]) -> SupervisedLauncher:
        control_directory, arguments = self._control_directory(arguments)
        child = self._builder.start(
            self._harness_root / "run_research.ps1",
            list(arguments),
            control_directory,
            env=self._launch_environment(),
        )
        self._children[Path(folder)] = child
        return child

    def poll(self, child: SupervisedLauncher) -> bool:
        return child.poll()

    def exit_code(self, child: SupervisedLauncher) -> int | None:
        return child.exit_code

    def wait(self, child: SupervisedLauncher, seconds: float) -> int | None:
        code = child.wait(seconds)
        return None if code == _STILL_ACTIVE else code

    def request_stop(self, child: SupervisedLauncher) -> bool:
        return child.request_stop()

    def force_stop(
        self, child: SupervisedLauncher, timeout: float | None = None
    ) -> None:
        child.force_stop(timeout if timeout is not None else 15.0)


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
    "new_control_directory",
]
