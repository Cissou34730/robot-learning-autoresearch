"""Reset one campaign checkout: ``python -m runner.launcher.reset``.

Holds the same per-campaign exclusion as the launcher, then runs the human-only
reset implementation in ``runner.reset_campaign`` for that campaign.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from runner.launcher.campaign_lock import CampaignBusy, CampaignLock
from runner.launcher.environment import LaunchRefused, bind_campaign
from runner.launcher.options import default_campaign_root
from runner.launcher.runner_client import uv_executable

HARNESS_ROOT = Path(__file__).resolve().parents[2]


class ResetRefused(ValueError):
    """The requested reset arguments are inconsistent."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m runner.launcher.reset",
        description="Reset the campaign, optionally restoring a scientific recipe first.",
    )
    parser.add_argument(
        "--campaign-root", type=Path, default=default_campaign_root(HARNESS_ROOT)
    )
    parser.add_argument(
        "--mode", required=True, type=str.lower, choices=("fresh", "baseline")
    )
    parser.add_argument("--recipe-ref")
    parser.add_argument("--baseline-ref")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def validate(arguments: argparse.Namespace) -> None:
    if not arguments.force:
        raise ResetRefused(
            "Stop the campaign first and pass --force to confirm the reset."
        )
    if arguments.mode == "fresh" and arguments.baseline_ref:
        raise ResetRefused(
            "Fresh accepts optional --recipe-ref only; --baseline-ref is Baseline-only."
        )
    if arguments.mode == "baseline" and (
        not arguments.baseline_ref or arguments.recipe_ref
    ):
        raise ResetRefused(
            "Baseline requires --baseline-ref and does not accept --recipe-ref."
        )


def reset_command(arguments: argparse.Namespace) -> list[str]:
    command = [
        uv_executable(),
        "run",
        "--project",
        str(HARNESS_ROOT),
        "python",
        "-m",
        "runner.reset_campaign",
        "--mode",
        arguments.mode,
    ]
    if arguments.recipe_ref:
        command += ["--recipe-ref", arguments.recipe_ref]
    if arguments.baseline_ref:
        command += ["--baseline-ref", arguments.baseline_ref]
    if arguments.clean:
        command.append("--clean")
    return command


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(argv)
    try:
        validate(arguments)
        campaign_root = bind_campaign(HARNESS_ROOT, arguments.campaign_root)
        with CampaignLock(
            campaign_root,
            "Another robot autoresearch loop or reset is already running in this worktree.",
        ):
            completed = subprocess.run(
                reset_command(arguments), cwd=campaign_root, check=False
            )
    except (ResetRefused, LaunchRefused, CampaignBusy) as error:
        print(str(error), file=sys.stderr)
        return 1
    if completed.returncode != 0:
        print(
            "Research reset failed. Review the reported error and starting commit "
            "before retrying.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
