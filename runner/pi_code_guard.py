"""Run PI-authored code under a write guard.

The Runner starts training, evaluation and lab modules through this module. An
audit hook refuses the file changes the launcher's trust gate would reject
afterwards: files outside the PI-owned and Runner-written paths of the
campaign, and any file of a separate harness. Usage:
``python -m runner.pi_code_guard <module> [arguments...]``.
"""

from __future__ import annotations

import os
import runpy
import sys

from runner import paths
from runner.launcher.trust import is_excluded, is_pi_writable

_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
# Audit event -> positions of the paths whose content it creates or changes.
_CHANGED_PATHS = {
    "os.remove": (0,),
    "os.rename": (0, 1),
    "os.truncate": (0,),
    "os.link": (1,),
    "os.symlink": (1,),
}
_RUNNER_RECORDS = frozenset(
    {
        "runner/state/research_state.json",
        "runner/state/goal_reached",
        "runner/state/recovery_pending",
        "runner/state/restart_pending",
        "campaigns/results.jsonl",
        "campaigns/experiments.md",
        "campaigns/brief.md",
    }
)
_TRANSIENT_SUFFIXES = (".tmp", ".progress")
# A training variant imports the scientific package from its own source copy.
VARIANT_SOURCE_VARIABLE = "ROBOT_LEARNING_VARIANT_SOURCE"


def _allowed_in_campaign(relative: str) -> bool:
    if relative.lower() in _RUNNER_RECORDS:
        return False
    if is_pi_writable(relative, preliminary=False):
        return True
    # Progress and atomic-write companions of Runner-written files come and go.
    while relative.lower().endswith(_TRANSIENT_SUFFIXES):
        relative = relative.rsplit(".", 1)[0]
    return is_excluded(relative)


def _relative(path: str, root: str) -> str | None:
    try:
        relative = os.path.relpath(path, root)
    except ValueError:
        return None
    if relative == os.pardir or relative.startswith(os.pardir + os.sep):
        return None
    return "" if relative == os.curdir else relative.replace("\\", "/")


def refusal(target: object) -> str | None:
    path = os.path.abspath(os.fsdecode(os.fspath(target)))
    if paths.SPLIT:
        relative = _relative(path, str(paths.HARNESS_ROOT))
        if relative is not None and not is_excluded(relative):
            return f"PI code cannot change reserved files: {path}"
    relative = _relative(path, str(paths.ROOT))
    if relative is not None and not _allowed_in_campaign(relative):
        return (
            f"PI code cannot change {relative}: it is outside the PI-owned paths "
            "in contracts/authority.md."
        )
    return None


def _audit(event: str, args: tuple) -> None:
    if event == "open":
        path, mode, flags = args
        writes = (
            bool(flags & _WRITE_FLAGS)
            if isinstance(flags, int)
            else any(character in (mode or "") for character in "wax+")
        )
        targets = (path,) if writes else ()
    elif event in _CHANGED_PATHS:
        targets = tuple(args[index] for index in _CHANGED_PATHS[event])
    else:
        return
    for target in targets:
        if target is None or isinstance(target, int):
            continue
        reason = refusal(target)
        if reason:
            raise PermissionError(reason)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m runner.pi_code_guard <module> [args...]")
    module = sys.argv[1]
    sys.argv = sys.argv[1:]
    variant_source = os.environ.get(VARIANT_SOURCE_VARIABLE)
    if variant_source:
        sys.path.insert(0, variant_source)
    sys.addaudithook(_audit)
    runpy.run_module(module, run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
