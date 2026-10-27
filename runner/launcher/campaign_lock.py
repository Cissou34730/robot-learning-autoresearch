"""Per-campaign exclusion shared by the launcher, the reset and the parallel monitor.

Both a launch and a reset rewrite one campaign checkout, so they never run
together in the same worktree. The named mutex is scoped to the canonical
worktree path (hashed: a mutex name cannot contain a path separator), and the
operating system releases it if its owner dies.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
from ctypes import wintypes
from pathlib import Path
from typing import Self

_ERROR_ALREADY_EXISTS = 183
_SYNCHRONIZE = 0x00100000

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True) if os.name == "nt" else None
if _kernel32 is not None:
    _kernel32.CreateMutexW.restype = wintypes.HANDLE
    _kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    _kernel32.OpenMutexW.restype = wintypes.HANDLE
    _kernel32.OpenMutexW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    _kernel32.ReleaseMutex.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


class CampaignBusy(RuntimeError):
    """Another launcher or reset owns this campaign checkout."""


def mutex_name(worktree: Path) -> str:
    resolved = Path(os.path.abspath(worktree))
    if not resolved.exists():
        raise FileNotFoundError(
            f"Cannot find path '{worktree}' because it does not exist."
        )
    canonical = str(resolved).replace("\\", "/").rstrip("/")
    if os.name == "nt":
        canonical = canonical.lower()
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest().upper()[:16]
    return f"Local\\RobotLearningAutoresearch-{digest}"


def is_held(worktree: Path) -> bool:
    """Whether a launcher or reset currently owns the campaign."""
    if _kernel32 is None:
        raise NotImplementedError("campaign exclusion requires Windows")
    handle = _kernel32.OpenMutexW(_SYNCHRONIZE, False, mutex_name(worktree))
    if not handle:
        return False
    _kernel32.CloseHandle(handle)
    return True


class CampaignLock:
    """Owns the campaign mutex for the lifetime of a ``with`` block."""

    def __init__(self, worktree: Path, refusal: str) -> None:
        self._name = mutex_name(worktree)
        self._refusal = refusal
        self._handle = None

    def __enter__(self) -> Self:
        if _kernel32 is None:
            raise NotImplementedError("campaign exclusion requires Windows")
        ctypes.set_last_error(0)
        handle = _kernel32.CreateMutexW(None, True, self._name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
            _kernel32.CloseHandle(handle)
            raise CampaignBusy(self._refusal)
        self._handle = handle
        return self

    def __exit__(self, *_exc) -> None:
        if self._handle is not None:
            _kernel32.ReleaseMutex(self._handle)
            _kernel32.CloseHandle(self._handle)
            self._handle = None
