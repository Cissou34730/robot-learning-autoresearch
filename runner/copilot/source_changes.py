"""Byte snapshots and unified diffs of the files a coding child may change."""

from __future__ import annotations

import difflib

from runner.copilot.path_policy import ROOT


def coding_snapshot(paths: frozenset[str]) -> dict[str, bytes | None]:
    return {
        path: (ROOT / path).read_bytes() if (ROOT / path).is_file() else None
        for path in paths
    }


def _change_kind(previous: bytes | None, current: bytes | None) -> str:
    if previous is None:
        return "created"
    return "deleted" if current is None else "modified"


def coding_changes(before: dict[str, bytes | None]) -> tuple[list[dict], str]:
    """Compare the invocation's actual bytes, including already-dirty files."""
    manifest = []
    diffs = []
    for path, previous in sorted(before.items()):
        current = (ROOT / path).read_bytes() if (ROOT / path).is_file() else None
        if previous == current:
            continue
        change = {
            "path": path,
            "change": _change_kind(previous, current),
            "before_bytes": len(previous) if previous is not None else None,
            "after_bytes": len(current) if current is not None else None,
        }
        manifest.append(change)
        try:
            old_lines = (previous or b"").decode("utf-8").splitlines(keepends=True)
            new_lines = (current or b"").decode("utf-8").splitlines(keepends=True)
        except UnicodeDecodeError:
            change["text_diff_available"] = False
            diffs.append(f"Binary/non-UTF-8 file differs: {path}\n")
            continue
        change["text_diff_available"] = True
        for line in difflib.unified_diff(
            old_lines, new_lines, fromfile=f"before/{path}", tofile=f"after/{path}"
        ):
            diffs.append(
                line
                if line.endswith("\n")
                else line + "\n\\ No newline at end of file\n"
            )
    return manifest, "".join(diffs)
