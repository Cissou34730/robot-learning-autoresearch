"""Run 1 to 5 campaign repositories in parallel on the current harness.

Maintainer utility and the standard batch launcher. Missing standard folders
are initialized from an existing one; each folder is reset to the recipe unless
``--no-reset``; each launcher starts detached without a visible console; a
detached monitor stops a campaign cooperatively at an active-time or AIU cap
and writes one report per campaign when all have ended. Caps act only through
each campaign's stop request; campaign agents never see them.

Usage:
    uv run python -m tools.run_parallel --count 3
    uv run python -m tools.run_parallel --count 1 --max-hours 4 --max-aiu 80
    uv run python -m tools.run_parallel --campaign-roots C:\\a C:\\b --no-reset
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

HARNESS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HARNESS))

from runner.launcher import campaign_lock
from runner.paths import stop_request_path

DEFAULT_RECIPE = "baseline-distinct-episodes-v3-robot"
_HIDDEN = 0x08000000 | 0x00000200  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
_KEEP_AWAKE = 0x80000001  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
_STARTUP_GRACE_SECONDS = 120


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m tools.run_parallel")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--count", type=int, choices=range(1, 6))
    selection.add_argument("--campaign-roots", type=Path, nargs="+")
    parser.add_argument(
        "--campaigns-root",
        type=Path,
        default=HARNESS.parent / "robot-learning-campaigns",
    )
    parser.add_argument("--recipe-ref", default=DEFAULT_RECIPE)
    parser.add_argument("--max-hours", type=float, default=6.0)
    parser.add_argument("--max-aiu", type=float, default=120.0)
    parser.add_argument("--provider", default="github-copilot")
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--no-reset", action="store_true")
    parser.add_argument("--control-directory", type=Path)
    parser.add_argument("--monitor", action="store_true")
    return parser.parse_args(argv)


def uv() -> str:
    found = shutil.which("uv")
    if not found:
        raise SystemExit("uv is not on PATH.")
    return found


def _python(*arguments: str, group: str | None = None) -> list[str]:
    command = [uv(), "run", "--project", str(HARNESS)]
    if group:
        command += ["--group", group]
    return [*command, "python", *arguments]


# -- Monitor -------------------------------------------------------------------


@dataclass
class Run:
    root: Path
    started: float
    active_seconds: float = 0.0
    stopped: str | None = None
    finished: bool = False


class Monitor:
    def __init__(self, arguments: argparse.Namespace) -> None:
        self.arguments = arguments
        self.control = arguments.control_directory
        self.runs = [Run(root, time.time()) for root in arguments.campaign_roots]

    def event(self, text: str) -> None:
        line = f"{datetime.now(UTC):%Y-%m-%d %H:%M:%SZ} {text}"
        print(line, flush=True)
        with (self.control / "monitor.log").open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")

    def watch(self) -> None:
        last = time.time()
        while any(not run.finished for run in self.runs):
            time.sleep(self.arguments.poll_seconds)
            now = time.time()
            gap, last = now - last, now
            if gap > 3 * self.arguments.poll_seconds:
                self.event(f"paused {gap:,.0f} s (sleep); not counted as active time")
                gap = 0
            for run in (run for run in self.runs if not run.finished):
                self.check(run, now, gap)

    def check(self, run: Run, now: float, gap: float) -> None:
        run.active_seconds += gap
        if now - run.started > _STARTUP_GRACE_SECONDS and not campaign_lock.is_held(
            run.root
        ):
            run.finished = True
            self.event(f"launcher exited {run.root}")
            return
        if run.stopped:
            return
        try:
            aiu = campaign_aiu(run.root)
        except (OSError, ValueError, KeyError, TypeError):
            return
        hours = run.active_seconds / 3600
        if hours >= self.arguments.max_hours:
            reason = f"active time {hours:,.2f} h"
        elif aiu >= self.arguments.max_aiu:
            reason = f"AIU {aiu:,.1f}"
        else:
            return
        request_stop(run.root)
        run.stopped = reason
        self.event(f"stop {run.root}: {reason}")

    def reports(self) -> None:
        reports = self.control / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        for run in self.runs:
            try:
                campaign_id = _state(run.root)["campaign"]["id"][:8]
                output = reports / f"{run.root.name}-{campaign_id}.html"
                completed = subprocess.run(
                    _python(
                        "tools/campaign_report.py",
                        "--repo",
                        str(run.root),
                        "--output",
                        str(output),
                    ),
                    cwd=HARNESS,
                    check=False,
                )
                self.event(f"report {run.root}: exit {completed.returncode}")
            except (OSError, ValueError, KeyError, TypeError) as error:
                self.event(f"report {run.root}: {error}")
        self.event("all campaigns ended")


def _state(root: Path) -> dict:
    return json.loads(
        (root / "runner" / "state" / "research_state.json").read_text(
            encoding="utf-8-sig"
        )
    )


def campaign_aiu(root: Path) -> float:
    usage = (
        root / "reports" / "session_usage" / f"{_state(root)['campaign']['id']}.jsonl"
    )
    if not usage.exists():
        return 0.0
    total = 0.0
    for line in usage.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            aiu = json.loads(line).get("aiu")
            if aiu is not None:
                total += float(aiu)
    return total


def request_stop(root: Path) -> None:
    stop_request_path(root).write_text("", encoding="utf-8")


def monitor(arguments: argparse.Namespace) -> int:
    # Lid closing can still force sleep; only the gaps it creates are excluded.
    if os.name == "nt":
        ctypes.windll.kernel32.SetThreadExecutionState(_KEEP_AWAKE)
    watcher = Monitor(arguments)
    watcher.watch()
    watcher.reports()
    return 0


# -- Launch --------------------------------------------------------------------


def standard_roots(arguments: argparse.Namespace) -> list[Path]:
    root = arguments.campaigns_root
    existing = [
        root / f"campaign-{slot}"
        for slot in range(1, 6)
        if (root / f"campaign-{slot}" / ".git").exists()
    ]
    if not existing:
        raise SystemExit(
            f"No campaign repository under {root}. Initialize campaign-1 with "
            "tools.initialize_campaign first."
        )
    roots = []
    for slot in range(1, arguments.count + 1):
        folder = root / f"campaign-{slot}"
        if not folder.exists():
            initialize(folder, existing[0], arguments.recipe_ref)
        roots.append(folder)
    return roots


def initialize(folder: Path, source: Path, recipe_ref: str) -> None:
    completed = subprocess.run(
        _python(
            "-m",
            "tools.initialize_campaign",
            "--campaign-root",
            str(folder),
            "--source-repository",
            str(source),
            "--recipe-ref",
            recipe_ref,
        ),
        cwd=HARNESS,
        check=False,
    )
    if completed.returncode:
        raise SystemExit(f"Initialization failed for {folder}.")


def require_ready(roots: list[Path]) -> None:
    status = subprocess.run(
        ["git", "-C", str(HARNESS), "status", "--porcelain", "--untracked-files=all"],
        capture_output=True,
        text=True,
        check=False,
    )
    if status.stdout.strip():
        raise SystemExit(
            "The harness worktree has uncommitted changes; the launchers would refuse to start."
        )
    for root in roots:
        if campaign_lock.is_held(root):
            raise SystemExit(f"A launcher already owns {root}.")


def reset(roots: list[Path], recipe_ref: str) -> None:
    for root in roots:
        completed = subprocess.run(
            _python(
                "-m",
                "runner.launcher.reset",
                "--campaign-root",
                str(root),
                "--mode",
                "fresh",
                "--clean",
                "--recipe-ref",
                recipe_ref,
                "--force",
            ),
            cwd=HARNESS,
            check=False,
        )
        if completed.returncode:
            raise SystemExit(f"Reset failed for {root}.")


def start_hidden(command: list[str], log: Path) -> subprocess.Popen:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"TUI_TYPED_EVENTS", "ROBOT_LEARNING_CAMPAIGN_ROOT"}
    }
    with log.open("ab") as stream:
        return subprocess.Popen(
            command,
            cwd=HARNESS,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=stream,
            creationflags=_HIDDEN if os.name == "nt" else 0,
        )


def launch(arguments: argparse.Namespace) -> int:
    roots = standard_roots(arguments) if arguments.count else arguments.campaign_roots
    # The launcher derives its exclusion name from the absolute, unresolved path.
    roots = [Path(os.path.abspath(root)) for root in roots]
    require_ready(roots)
    if not arguments.no_reset:
        reset(roots, arguments.recipe_ref)
    control = arguments.control_directory or (
        Path(os.environ.get("TEMP", HARNESS))
        / "robot-learning"
        / f"parallel-{datetime.now(UTC):%Y%m%dT%H%M%S}"
    )
    control.mkdir(parents=True, exist_ok=True)
    for root in roots:
        process = start_hidden(
            _python(
                "-m",
                "runner.launcher",
                "--campaign-root",
                str(root),
                "--provider",
                arguments.provider,
                group="researcher",
            ),
            control / f"{root.name}.log",
        )
        print(
            f"{datetime.now(UTC):%Y-%m-%d %H:%M:%SZ} started {root} (pid {process.pid})"
        )
        time.sleep(5)
    watcher = start_hidden(
        _python(
            "-m",
            "tools.run_parallel",
            "--monitor",
            "--control-directory",
            str(control),
            "--campaign-roots",
            *map(str, roots),
            "--max-hours",
            str(arguments.max_hours),
            "--max-aiu",
            str(arguments.max_aiu),
            "--poll-seconds",
            str(arguments.poll_seconds),
        ),
        control / "monitor.out.log",
    )
    print(f"Monitor pid {watcher.pid}. Control folder: {control}")
    print(
        f"Caps per campaign: {arguments.max_hours:g} h active time, {arguments.max_aiu:g} AIU."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(argv)
    if arguments.monitor:
        if not arguments.campaign_roots or not arguments.control_directory:
            raise SystemExit(
                "--monitor requires --campaign-roots and --control-directory."
            )
        return monitor(arguments)
    return launch(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
