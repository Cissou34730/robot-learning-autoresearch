"""Entry point: `uv run python -m tui` (one reading-only screen)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> None:
    # The campaign root must be selected before `runner.paths` is imported.
    parser = argparse.ArgumentParser(
        prog="python -m tui",
        description="Read-only autoresearch campaign report for Windows Terminal.",
    )
    parser.add_argument(
        "--campaign-root",
        type=Path,
        default=None,
        help="Campaign repository root (defaults to ROBOT_LEARNING_CAMPAIGN_ROOT "
        "or the sibling campaign checkout).",
    )
    parser.add_argument(
        "--events",
        type=Path,
        default=None,
        help="Structured observation JSONL file to follow (read-only).",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Render synthetic campaign material; no campaign files are read.",
    )
    parser.add_argument(
        "--light",
        action="store_true",
        help="Use the light theme (the terminal's NO_COLOR setting is honored).",
    )
    arguments = parser.parse_args()

    if arguments.campaign_root is not None:
        os.environ["ROBOT_LEARNING_CAMPAIGN_ROOT"] = str(arguments.campaign_root)

    from tui.report import CampaignReport

    app = CampaignReport(
        demo=arguments.demo,
        events_path=arguments.events,
    )
    if arguments.light:
        app.theme = "textual-light"
    app.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:  # pragma: no cover - user exit closes presentation only
        sys.exit(130)
