"""Entry point: `uv run python -m tui`.

Without arguments this opens the multi-campaign operator console
(issue #68): one Commands tab plus one tab per installed campaign folder.
Console commands launch and stop campaign launchers; nothing runs on its
own. The legacy flags below open the unchanged single-campaign report.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> None:
    # The campaign root must be selected before `runner.paths` is imported.
    parser = argparse.ArgumentParser(
        prog="python -m tui",
        description="Multi-campaign operator console for Windows Terminal.",
    )
    parser.add_argument(
        "--campaign-root",
        type=Path,
        default=None,
        help="Open the legacy single-campaign report for this campaign root "
        "(defaults to ROBOT_LEARNING_CAMPAIGN_ROOT or the sibling campaign "
        "checkout). Console mode ignores this and discovers every installed "
        "campaign folder itself.",
    )
    parser.add_argument(
        "--events",
        type=Path,
        default=None,
        help="Legacy single-campaign report: structured observation JSONL "
        "file to follow (read-only).",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Legacy single-campaign report: render synthetic campaign "
        "material; no campaign files are read.",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Force the legacy single-campaign report instead of the console.",
    )
    parser.add_argument(
        "--light",
        action="store_true",
        help="Use the light theme (the terminal's NO_COLOR setting is honored).",
    )
    arguments = parser.parse_args()

    if arguments.report or arguments.demo or arguments.events:
        # Legacy behaviour: one read-only report for one campaign root.
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
        return

    from tui.console import run_console

    raise SystemExit(run_console(light=arguments.light))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:  # pragma: no cover - user exit closes presentation only
        sys.exit(130)
