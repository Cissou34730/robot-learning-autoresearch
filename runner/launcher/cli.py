"""Command line of the campaign launcher: ``python -m runner.launcher``."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from runner.launcher import options as defaults
from runner.launcher.campaign_lock import CampaignBusy, CampaignLock
from runner.launcher.environment import (
    LaunchRefused,
    bind_campaign,
    require_clean_harness,
)
from runner.launcher.options import LaunchOptions, resolve_model
from runner.launcher.runner_client import LauncherError

HARNESS_ROOT = Path(__file__).resolve().parents[2]


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def _non_negative(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be at least 0")
    return number


def _stop_timeout(value: str) -> int:
    number = int(value)
    if not 1 <= number <= 3600:
        raise argparse.ArgumentTypeError("must be between 1 and 3600")
    return number


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m runner.launcher",
        description="Goal-centered robot-learning research launcher. It writes no "
        "console output; watch the campaign with campaign_tui.ps1.",
    )
    parser.add_argument(
        "--campaign-root",
        type=Path,
        default=defaults.default_campaign_root(HARNESS_ROOT),
    )
    parser.add_argument("--model")
    parser.add_argument("--provider", choices=defaults.PROVIDERS)
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument(
        "--reasoning",
        choices=defaults.REASONING_LEVELS,
        default=defaults.DEFAULT_REASONING,
    )
    # 0 pauses the campaign after its startup session.
    parser.add_argument("--max-inquiries", type=_non_negative)
    parser.add_argument(
        "--timesteps", type=_positive, default=defaults.DEFAULT_TIMESTEPS
    )
    parser.add_argument(
        "--max-timesteps", type=_positive, default=defaults.DEFAULT_MAX_TIMESTEPS
    )
    parser.add_argument(
        "--stop-timeout-seconds",
        type=_stop_timeout,
        default=defaults.DEFAULT_STOP_TIMEOUT_SECONDS,
    )
    arguments = parser.parse_args(argv)
    if arguments.model is not None and not arguments.model:
        parser.error("--model must not be empty")
    return arguments


def list_models(provider: str | None) -> int:
    from runner.launcher.runner_client import uv_executable

    command = [
        uv_executable(),
        "run",
        "--no-sync",
        "--group",
        "researcher",
        "python",
        "-m",
        "runner.copilot.copilot_adapter",
        "--list-models",
    ]
    if provider:
        command += ["--provider", provider]
    return subprocess.run(command, cwd=HARNESS_ROOT, check=False).returncode


def launch_options(arguments: argparse.Namespace, campaign_root: Path) -> LaunchOptions:
    return LaunchOptions(
        harness_root=HARNESS_ROOT,
        campaign_root=campaign_root,
        model=resolve_model(arguments.model, arguments.provider),
        reasoning=arguments.reasoning,
        max_inquiries=defaults.DEFAULT_MAX_INQUIRIES
        if arguments.max_inquiries is None
        else arguments.max_inquiries,
        max_inquiries_explicit=arguments.max_inquiries is not None,
        timesteps=arguments.timesteps,
        max_timesteps=arguments.max_timesteps,
        stop_timeout_seconds=arguments.stop_timeout_seconds,
    )


def main(argv: list[str] | None = None) -> int:
    started_at = time.time()
    arguments = parse_args(argv)
    if arguments.list_models:
        return list_models(arguments.provider)
    try:
        require_clean_harness(HARNESS_ROOT)
        campaign_root = bind_campaign(HARNESS_ROOT, arguments.campaign_root)
        options = launch_options(arguments, campaign_root)
        with CampaignLock(
            campaign_root,
            "Another robot autoresearch loop is already running in this worktree.",
        ):
            from runner.launcher.assembly import run_campaign

            return run_campaign(options, started_at=started_at)
    except (LaunchRefused, CampaignBusy, LauncherError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
