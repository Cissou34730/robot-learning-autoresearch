"""Headless rendering tests for the single-screen report.

Everything runs in Textual's headless app harness against synthetic material;
no campaign files are read or written.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from tui.observations import Observation
from tui.report import CampaignReport, DemoSources


def _run(coro):
    return asyncio.run(coro)


class _ControlledSources(DemoSources):
    def __init__(self) -> None:
        super().__init__()
        self.calls: int = 0
        self.active_inquiry: dict | None = None
        self.synthesis_switch: str = ""

    def read(self):
        from tui.demo import demo_snapshot_args

        self.calls += 1
        state, records, usage_rows = demo_snapshot_args()
        if self.active_inquiry is not None:
            state["active_inquiry"] = self.active_inquiry
        if self.synthesis_switch:
            state["pi_checkpoint"]["current_synthesis"] = self.synthesis_switch
        return state, records, usage_rows


def _demo_app():
    return CampaignReport(demo=True, sources=DemoSources())


def test_initial_single_screen_composition():
    _run(_initial())


def _cells(value) -> float:
    """Textual heights come back as Scalar for styles and int for size."""
    return float(getattr(value, "value", value))


async def _model_table_shows_all_rows():
    """The table viewport fits its header plus every assigned role row."""
    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        for _ in range(20):
            await pilot.pause()
        table = app.query_one("#models")
        assert len(table.rows) == 3
        assert _cells(table.styles.max_height) == len(table.rows) + 1
        assert _cells(table.virtual_size.height) <= _cells(table.size.height)


def test_model_table_shows_all_assigned_rows():
    _run(_model_table_shows_all_rows())


async def _initial():
    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        ctx = str(app.query_one("#context").render())
        assert "Autoresearch | RUNNING (observed)" in ctx
        assert "Stage: Inquiry I3 / S7" in ctx
        assert "PI record S6" in ctx
        assert "Usage recorded:" in ctx
        assert app.query_one("#progress").display is False
        snapshot = app.snapshot
        assert snapshot and len(snapshot.model_rows) == 3
        reading = str(app.query_one("#reading").render())
        assert reading.startswith("Following live output")


def test_pi_message_streamed_duplicate_renders_once():
    _run(_pi_once())


async def _pi_once():
    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        app.drain_feed()
        await pilot.pause()
        out = app.query_one("#output")
        app._feed.advance(1.0)
        app.drain_feed()
        await pilot.pause()
        rendered = "\n".join(strip.text for strip in out.lines)
        pi_lines = [line for line in rendered.splitlines() if "PI (S7):" in line]
        # The demo's replayed event must not add a second copy.
        assert len(pi_lines) == 1
        assert app.snapshot is not None


def test_training_progress_appears_and_disappears_on_end():
    _run(_progress())


async def _progress():
    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        app.drain_feed()
        await pilot.pause()
        app._feed.advance(2.0)
        app.drain_feed()  # training progress at t=2.0: 24,000/80,000
        await pilot.pause()
        progress = app.query_one("#progress")
        assert progress.display
        rendered = str(progress.render())
        assert "Training T5" in rendered
        assert "Attempt 1" in rendered
        assert "24,000 / 80,000" in rendered
        assert "Elapsed 12m" in rendered
        app._feed.advance(1.0)
        app.drain_feed()  # execution_end for T5
        await pilot.pause()
        progress = app.query_one("#progress")
        assert progress.display is False


def test_evaluation_panels_official_label_and_module_measurement():
    _run(_evals())


async def _evals():
    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        app.drain_feed()
        app._feed.advance(3.8)
        app.drain_feed()
        await pilot.pause()
        progress = str(app.query_one("#progress").render())
        assert "Evaluation M6" in progress
        assert "Panel 1/3" in progress
        assert "Episodes 44 / 100" in progress
        app._feed.advance(0.4)  # official assessment event
        app.drain_feed()
        await pilot.pause()
        rendered = str(app.query_one("#progress").render())
        assert "Official assessment" in rendered
        assert rendered.count("Evaluation") == 0
        app._feed.advance(0.5)
        app.drain_feed()
        await pilot.pause()
        # module measurement without counters -> explicit unavailable progress
        app._process_events(
            [
                Observation(
                    "eval_progress",
                    None,
                    {
                        "operation_id": "M7",
                        "instrument": "module",
                        "elapsed_seconds": 30,
                    },
                )
            ]
        )
        await pilot.pause()
        rendered = str(app.query_one("#progress").render())
        assert "Running - progress unavailable" in rendered


def test_reading_history_preserves_position_and_returns():
    _run(_reading())


async def _reading():
    app = _demo_app()
    async with app.run_test(size=(120, 35)) as pilot:
        await pilot.pause()
        app.drain_feed()
        await pilot.pause()
        out = app.query_one("#output")
        # Push enough rows below the viewport that up-scroll has somewhere to go.
        for index in range(200):
            app._append(
                datetime.now(tz=UTC),
                f"synthetic fill line {index} to force scrollable history",
            )
        await pilot.pause()
        out.scroll_to(y=0, animate=False)
        await pilot.pause()
        assert out.following is False
        app._feed.advance(1.0)
        app.drain_feed()
        await pilot.pause()
        reading = str(app.query_one("#reading").render())
        assert reading.startswith("Reading history")
        assert "newer" in reading
        assert out.missed >= 1
        await pilot.press("end")
        await pilot.pause()
        assert out.following is True
        assert str(app.query_one("#reading").render()).startswith("Following")


def test_too_small_terminal_falls_back_to_message():
    _run(_too_small())


async def _too_small():
    app = _demo_app()
    async with app.run_test(size=(40, 12)) as pilot:
        await pilot.pause()
        overlay = app.query_one("#too-small")
        assert overlay.display is True
        assert "too small" in str(overlay.render()).lower()


def test_context_change_appends_attributed_update():
    _run(_context_change())


async def _context_change():
    sources = _ControlledSources()
    app = CampaignReport(
        demo=True,
        sources=sources,
    )
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        app.drain_feed()
        await pilot.pause()
        out = app.query_one("#output")
        before = len(out.lines)
        sources.synthesis_switch = "Synthesis replaced with a newer PI record text."
        app.refresh_snapshot()
        await pilot.pause()
        rendered = "\n".join(strip.text for strip in out.lines[before - 3 :])
        assert "PI synthesis updated (S6)" in rendered
        assert "newer PI record text" in rendered


def test_stale_counter_is_labeled_not_claimed_live():
    _run(_stale())


async def _stale():
    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        app.drain_feed()
        app._feed.advance(2.4)
        app.drain_feed()
        await pilot.pause()
        # Age the observation far beyond the staleness horizon.
        from tui.report import PROGRESS_STALE_SECONDS

        stale_time = datetime.now(tz=UTC) - timedelta(
            seconds=PROGRESS_STALE_SECONDS + 60
        )
        app._training["last_ts"] = stale_time
        app._render_progress()
        await pilot.pause()
        rendered = str(app.query_one("#progress").render())
        assert "counter observation stale" in rendered
