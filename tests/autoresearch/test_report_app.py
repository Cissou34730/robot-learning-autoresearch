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
        self.campaign_id: str | None = None

    def read(self):
        from tui.demo import demo_snapshot_args

        self.calls += 1
        state, records, usage_rows = demo_snapshot_args()
        if self.active_inquiry is not None:
            state["active_inquiry"] = self.active_inquiry
        if self.synthesis_switch:
            state["pi_checkpoint"]["current_synthesis"] = self.synthesis_switch
        if self.campaign_id is not None:
            state["campaign"]["id"] = self.campaign_id
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
        assert "Stage: I3 / S7 / T4 / M5 / E13 | Inquiry I3 / S7" in ctx
        assert "Goal >=98% | best 94% | -4.0 pts" in ctx
        assert "Pending M6 measurement" in ctx
        assert "Inquiries 3/15" in ctx
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


def test_pi_partials_render_incrementally_without_duplicate():
    _run(_pi_partials())


async def _pi_partials():
    from datetime import UTC, datetime

    from tui.observations import Observation

    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        now = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)

        def drain(text: str, *, final: bool) -> str:
            app._process_events(
                [
                    Observation(
                        kind="pi_message",
                        ts=now,
                        fields={"text": text, "final": final, "turn": 7},
                    )
                ]
            )
            out = app.query_one("#output")
            return "\n".join(strip.text for strip in out.lines)

        rendered = drain("Zebra delta one ", final=False)
        assert "Zebra delta one" in rendered
        rendered = drain("two. ", final=False)
        await pilot.pause()
        rendered = drain("Zebra delta one two. Quokka final.", final=True)
        await pilot.pause()
        rendered = "\n".join(strip.text for strip in app.query_one("#output").lines)
        assert rendered.count("Zebra delta one") == 1
        assert rendered.count("two.") == 1
        assert rendered.count("Quokka final") == 1


def test_report_follows_only_its_campaign_feed(monkeypatch, tmp_path):
    from runner import paths
    from tui.report import CampaignReport

    monkeypatch.setattr(paths, "ROOT", tmp_path)
    app = CampaignReport()
    app._ensure_feed("campaign-abc")
    expected = tmp_path / "reports" / "tui_observations" / "campaign-abc.jsonl"
    assert app._feed.path == expected
    current = app._feed
    app._ensure_feed("campaign-abc")
    assert app._feed is current
    app._ensure_feed("campaign-other")
    assert (
        app._feed.path
        == tmp_path / "reports" / "tui_observations" / "campaign-other.jsonl"
    )


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


# ---------------------------------------------------------------------------
# Accessibility and palette
# ---------------------------------------------------------------------------


def _segment_colours(out) -> list[tuple[str, str, bool]]:
    """(text, truecolour hex, bold) for every styled segment in the log."""
    rows: list[tuple[str, str, bool]] = []
    for strip in out.lines:
        for segment in strip._segments:
            if segment.style and segment.style.color:
                rows.append(
                    (
                        segment.text,
                        segment.style.color.get_truecolor().hex,
                        bool(segment.style.bold),
                    )
                )
    return rows


def test_output_lines_fit_and_keep_long_words_at_several_widths():
    _run(_fit_widths())


async def _fit_widths():
    for width, height in ((100, 30), (120, 40), (160, 45)):
        app = _demo_app()
        async with app.run_test(size=(width, height)) as pilot:
            await pilot.pause()
            out = app.query_one("#output")
            app._append(datetime.now(tz=UTC), "x" * 200)
            await pilot.pause()
            content_width = out.scrollable_content_region.width
            assert all(len(strip.text) <= content_width for strip in out.lines)
            joined = "".join(strip.text for strip in out.lines)
            assert "x" * 200 in joined.replace(" ", "")


def test_palette_tokens_meet_contrast_floor():
    from tui.report import PALETTES, contrast_ratio

    tokens = (
        "text",
        "muted",
        "heading",
        "accent",
        "success",
        "warning",
        "error",
        "pi",
        "tool",
        "section",
        "result",
    )
    for palette in PALETTES.values():
        for token in tokens:
            ratio = contrast_ratio(getattr(palette, token), palette.background)
            assert ratio >= 4.5, f"{palette.name}.{token} contrast {ratio:.2f}"


def test_report_has_no_background_bands_or_cursor():
    _run(_no_bands())


async def _no_bands():
    from textual.color import Color

    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        table = app.query_one("#models")
        assert table.zebra_stripes is False
        assert table.cursor_type == "none"
        assert table.show_row_labels is False
        background = Color.parse(app._palette.background)
        for component in (
            "datatable--header",
            "datatable--even-row",
            "datatable--odd-row",
            "datatable--cursor",
            "datatable--hover",
        ):
            style = table.get_component_styles(component)
            assert style.background == background


def test_scope_styles_are_distinct_at_160x45():
    _run(_scope_styles())


async def _scope_styles():
    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        now = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
        app._process_events(
            [
                Observation(
                    "console_line",
                    now,
                    {"scope": "tool", "text": "> submit_operation train"},
                ),
                Observation(
                    "console_line",
                    now,
                    {"scope": "error", "text": "x failed"},
                ),
                Observation(
                    "console_line",
                    now,
                    {"scope": "pi", "text": "PI text"},
                ),
                Observation(
                    "console_line",
                    now,
                    {"scope": "result", "text": "= result 0.94"},
                ),
                Observation(
                    "console_line",
                    now,
                    {
                        "scope": "operation",
                        "text": "=== OPERATION | T5 ===\nWhy\nbody line",
                    },
                ),
            ]
        )
        await pilot.pause()
        palette = app._palette
        segments = _segment_colours(app.query_one("#output"))
        by_text = {
            text: (colour, bold) for text, colour, bold in segments if text.strip()
        }
        assert by_text["> submit_operation train"] == (palette.tool, False)
        assert by_text["x failed"] == (palette.error, True)
        assert by_text["PI text"] == (palette.pi, False)
        assert by_text["= result 0.94"] == (palette.success, True)
        assert by_text["=== OPERATION | T5 ==="] == (palette.accent, True)
        assert by_text["Why"] == (palette.section, True)
        assert by_text["body line"] == (palette.text, False)


def test_no_color_pinned_frame_keeps_text_meaning(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    _run(_no_color_frame())


async def _no_color_frame():
    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        assert app.no_color is True
        now = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
        app._process_events(
            [
                Observation(
                    "console_line",
                    now,
                    {"scope": "tool", "text": "> submit_operation train"},
                ),
                Observation(
                    "console_line",
                    now,
                    {"scope": "error", "text": "x failed"},
                ),
                Observation(
                    "console_line",
                    now,
                    {"scope": "pi", "text": "PI text"},
                ),
            ]
        )
        await pilot.pause()
        out = app.query_one("#output")
        rendered = "\n".join(strip.text for strip in out.lines)
        assert "> submit_operation train" in rendered
        assert "x failed" in rendered
        assert "PI text" in rendered
        from textual.filter import Monochrome, NoColor

        assert any(
            isinstance(line_filter, (NoColor, Monochrome))
            for line_filter in app.get_line_filters()
        )
        context = str(app.query_one("#context").render())
        assert "RUNNING (observed)" in context
        assert str(app.query_one("#reading").render()).startswith("Following")


def test_light_theme_selects_light_palette():
    _run(_light_palette())


async def _light_palette():
    app = _demo_app()
    app.theme = "textual-light"
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        assert app._palette.name == "light"
        assert "Autoresearch" in str(app.query_one("#context").render())


def test_new_campaign_clears_previous_output():
    _run(_campaign_switch())


async def _campaign_switch():
    sources = _ControlledSources()
    app = CampaignReport(demo=True, sources=sources)
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        out = app.query_one("#output")
        app._append(datetime.now(tz=UTC), "OLD CAMPAIGN OUTPUT")
        await pilot.pause()
        assert "OLD CAMPAIGN OUTPUT" in "\n".join(strip.text for strip in out.lines)
        app.refresh_snapshot()
        await pilot.pause()
        assert "OLD CAMPAIGN OUTPUT" in "\n".join(strip.text for strip in out.lines)
        sources.campaign_id = "new-campaign-id"
        app.refresh_snapshot()
        await pilot.pause()
        rendered = "\n".join(strip.text for strip in out.lines)
        assert "OLD CAMPAIGN OUTPUT" not in rendered
        assert "new-campaign-id" in rendered
        assert app._campaign_id == "new-campaign-id"


def test_training_status_shows_last_training_proxy():
    _run(_training_status())


async def _training_status():
    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        widget = app.query_one("#training")
        assert widget.display is True
        rendered = str(widget.render())
        assert "Last training T4" in rendered
        assert "best proxy T4:checkpoint-120000" in rendered
        assert "reward 86.3" in rendered
        assert "success 97%" in rendered


def test_active_training_line_includes_reward_and_success():
    _run(_active_training_metrics())


async def _active_training_metrics():
    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        app._process_events(
            [
                Observation(
                    "training_progress",
                    datetime(2026, 10, 24, 12, 0, tzinfo=UTC),
                    {
                        "operation_id": "T9",
                        "attempt": 1,
                        "steps": 24000,
                        "target": 80000,
                        "elapsed_seconds": 720,
                        "ep_rew_mean": 86.3,
                        "training_success": 0.97,
                    },
                )
            ]
        )
        await pilot.pause()
        rendered = str(app.query_one("#progress").render())
        assert "Reward 86.3" in rendered
        assert "Success 97%" in rendered
        assert app.query_one("#training").display is False


def test_compact_floor_hides_output_and_keeps_training_status():
    _run(_compact_floor())


async def _compact_floor():
    app = _demo_app()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.query_one("#output").display is False
        assert app.query_one("#output-heading").display is False
        assert app.query_one("#reading").display is False
        assert app.query_one("#training").display is True
        table = app.query_one("#models")
        assert len(table.columns) == 3
        assert [str(column.label) for column in table.columns.values()] == [
            "PI-assigned role",
            "Candidate",
            "Success (development) / source",
        ]
        assert len(table.rows) == 3
        assert table.virtual_size.width <= table.size.width
        context = str(app.query_one("#context").render())
        assert "Stage: I3 / S7 / T4 / M5 / E13" in context
        assert "Goal >=98% | best 94% | -4.0 pts" in context
        assert "Pending M6 measurement" in context


def test_display_text_rounds_floats_and_compacts_paths(monkeypatch, tmp_path):
    from runner import console
    from tui.report import _display_text

    monkeypatch.setattr(console, "_ROOT", tmp_path)
    path = tmp_path / "models" / "candidates" / "run.zip"
    text = _display_text(f"reward -6.122319559999999 at {path}")
    assert "reward -6.122" in text
    assert "models/candidates/run.zip" in text
    assert str(path) not in text
