"""Preconditions a launch or reset checks before touching a campaign."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from runner.paths import CAMPAIGN_ROOT_ENV


class LaunchRefused(RuntimeError):
    """A precondition failed before any campaign work started."""


def require_clean_harness(harness_root: Path) -> None:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(harness_root),
            "status",
            "--porcelain",
            "--untracked-files=all",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise LaunchRefused(
            "Could not read the harness Git status. No campaign was started."
        )
    changes = [line for line in result.stdout.splitlines() if line]
    if changes:
        raise LaunchRefused(
            "The harness worktree has uncommitted changes. Commit or discard them "
            "before launching a campaign. No campaign was started.\n"
            + "\n".join(changes)
        )


def bind_campaign(harness_root: Path, campaign_root: Path) -> Path:
    """Point this process and its children at one campaign checkout."""
    harness = Path(os.path.abspath(harness_root))
    campaign = Path(os.path.abspath(campaign_root))
    if not campaign.exists():
        raise LaunchRefused(
            f"Cannot find path '{campaign_root}' because it does not exist."
        )
    if not (campaign / ".git").exists():
        raise LaunchRefused(f"The campaign folder must be a Git repository: {campaign}")
    os.environ[CAMPAIGN_ROOT_ENV] = str(campaign)
    entries = [str(campaign), str(harness)]
    if os.environ.get("PYTHONPATH"):
        entries.append(os.environ["PYTHONPATH"])
    os.environ["PYTHONPATH"] = os.pathsep.join(entries)
    os.chdir(campaign)
    return campaign
