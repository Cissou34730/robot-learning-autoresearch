"""Pre-commit guard: refuse commits of harness runtime code while a campaign runs."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from runner.launcher.campaign_lock import is_held
from runner.paths import HARNESS_ROOT, is_harness_runtime

CAMPAIGNS_ROOT = HARNESS_ROOT.parent / "robot-learning-campaigns"


def running_campaigns(root: Path | None = None) -> list[str]:
    root = root or CAMPAIGNS_ROOT
    if not root.is_dir():
        return []
    return sorted(
        folder.name
        for folder in root.iterdir()
        if (folder / ".git").exists() and is_held(folder)
    )


def staged_runtime_paths() -> list[str]:
    output = subprocess.run(
        ["git", "-C", str(HARNESS_ROOT), "diff", "--cached", "--name-only", "-z"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [path for path in output.split("\0") if path and is_harness_runtime(path)]


def main() -> int:
    staged = staged_runtime_paths()
    running = running_campaigns() if staged else []
    if not running:
        return 0
    print(
        f"Commit refused: {', '.join(running)} running, and this commit changes "
        f"code they load: {', '.join(staged)}. Commit after the campaigns stop.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
