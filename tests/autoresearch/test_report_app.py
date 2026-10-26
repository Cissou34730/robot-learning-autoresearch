"""Headless rendering tests for the single-screen report.

Everything runs in Textual's headless app harness against synthetic material;
no campaign files are read or written.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

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


def _timeline_items(app):
    roots, _ = app._timeline.view()

    def walk(item):
        yield item
        for child in item.children:
            yield from walk(child)

    for root in roots:
        yield from walk(root)


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
        assert reading.startswith("Following live events")


def test_pi_message_streamed_duplicate_renders_once():
    _run(_pi_once())


async def _pi_once():
    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        app.drain_feed()
        await pilot.pause()
        app._feed.advance(1.0)
        app.drain_feed()
        await pilot.pause()
        messages = [item for item in _timeline_items(app) if item.kind == "pi"]
        # The demo's replayed event must not add a second copy.
        assert len(messages) == 1
        assert "working candidate" in messages[0].summary
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

        def drain(text: str, *, final: bool) -> None:
            app._process_events(
                [
                    Observation(
                        kind="pi_message",
                        ts=now,
                        fields={"text": text, "final": final, "turn": 7},
                    )
                ]
            )

        drain("Zebra delta one ", final=False)
        messages = [item for item in _timeline_items(app) if item.kind == "pi"]
        assert len(messages) == 1
        assert "Zebra delta one" in messages[0].summary
        drain("two. ", final=False)
        await pilot.pause()
        drain("Zebra delta one two. Quokka final.", final=True)
        await pilot.pause()
        messages = [item for item in _timeline_items(app) if item.kind == "pi"]
        assert len(messages) == 1
        assert messages[0].summary == "Zebra delta one two. Quokka final."
        assert messages[0].detail == ("Zebra delta one two. Quokka final.",)


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
        sources.synthesis_switch = "Synthesis replaced with a newer PI record text."
        app.refresh_snapshot()
        await pilot.pause()
        rendered = "\n".join(app.query_one("#output").text_lines())
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
            rendered = out.render_lines(out.region)
            assert all(len(strip.text) <= content_width for strip in rendered)
            assert any("x" * 200 in line for line in out.text_lines())


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
        items = list(_timeline_items(app))
        tool = next(item for item in items if item.title == "> submit_operation train")
        assert tool.kind == "tool"
        error = next(item for item in items if item.title == "x failed")
        assert error.kind == "error"
        assert error.severity == "error"
        pi = next(item for item in items if item.title == "PI text")
        assert pi.kind == "pi"
        result = next(item for item in items if item.title == "= result 0.94")
        assert result.kind == "result"
        card = next(item for item in items if item.title == "OPERATION | T5")
        assert card.kind == "operation"
        assert card.detail == ("Why", "body line")


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


def test_event_log_uses_a_fixed_time_column():
    from tui.event_log import EventLog
    from tui.timeline import TimelineItem

    log = EventLog({})
    stamp = datetime(2026, 10, 26, 14, 32, 5, tzinfo=UTC)
    local = stamp.astimezone()
    leaf = TimelineItem(
        item_id="leaf",
        kind="tool",
        title="read_file",
        ts=stamp,
    )
    untimed = TimelineItem(item_id="untimed", kind="tool", title="read_file")
    assert "read_file" in log._label(leaf).plain
    assert "read_file" in log._label(untimed).plain
    assert log._column(leaf, False)[1].text == f"{local:%H:%M:%S}"
    assert log._column(untimed, False)[1].text == "        "


def test_selected_row_uses_a_gutter_marker():
    _run(_gutter_marker())


async def _gutter_marker():
    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        out = app.query_one("#output")
        node = out._node_by_id["session:S7"]
        out.move_cursor(node, animate=False)
        await pilot.pause()
        strip = out.render_line(out.cursor_line - int(out.scroll_offset.y))
        assert strip.text.startswith("▌ ")


def test_mouse_hover_marks_the_block_in_the_left_gutter():
    _run(_hover_block())


async def _hover_block():
    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        out = app.query_one("#output")
        session = out._node_by_id["session:S7"]
        session_y = next(
            y for y, line in enumerate(out._tree_lines) if line.node is session
        )
        cursor = out.cursor_node
        await pilot.hover(out, offset=(50, session_y))
        await pilot.pause()
        painted = out.render_lines(out.size.region)
        for y, line in enumerate(out._tree_lines):
            strip = painted[y]
            assert strip.text.startswith("▌ ") == (session in line.path)
            assert not any(
                segment.style and segment.style.underline for segment in strip
            )
        assert out.cursor_node is cursor

        # The fixed clock/gutter must be hoverable too, not just the tree label.
        await pilot.hover(out, offset=(0, session_y))
        await pilot.pause()
        assert out.render_line(session_y).text.startswith("▌ ")

        # Moving to a nested block removes the parent's marker immediately.
        child_y = session_y + 1
        child = out._tree_lines[child_y].node
        await pilot.hover(out, offset=(30, child_y))
        await pilot.pause()
        painted = out.render_lines(out.size.region)
        for y, line in enumerate(out._tree_lines):
            assert painted[y].text.startswith("▌ ") == (child in line.path)

        await pilot.hover("#context")
        await pilot.pause()
        assert not out.render_line(session_y).text.startswith("▌ ")


def test_output_has_a_fixed_clock_column():
    _run(_clock_column())


async def _clock_column():
    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        out = app.query_one("#output")
        for y, line in enumerate(out._tree_lines):
            if line.node.data is None:
                continue
            strip = out.render_line(y - int(out.scroll_offset.y))
            assert strip.text[11] == "│"
            stamp = line.node.data.ts
            expected = stamp.astimezone().strftime("%H:%M:%S") if stamp else " " * 8
            assert strip.text[2:10] == expected


@pytest.mark.parametrize("theme", ["textual-dark", "textual-light"])
def test_output_text_selection_copies_instead_of_quitting(theme):
    _run(_copy_output_selection(theme))


async def _copy_output_selection(theme):
    app = _demo_app()
    app.theme = theme
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        out = app.query_one("#output")
        assert out.ALLOW_SELECT is True
        selection_style = app.screen.get_component_rich_style("screen--selection")
        assert selection_style.bgcolor is not None
        assert selection_style.color is not None
        assert selection_style.color != selection_style.bgcolor
        original_style = app.screen.get_style_at(
            out.content_region.x + 25, out.content_region.y + 3
        )
        await pilot.mouse_down(out, offset=(20, 3))
        await pilot.hover(out, offset=(45, 5))
        await pilot.pause()
        # Check what is painted, not just the internal selection/clipboard state.
        for x, y in ((25, 3), (25, 4), (25, 5)):
            style = app.screen.get_style_at(
                out.content_region.x + x, out.content_region.y + y
            )
            assert style.bgcolor == selection_style.bgcolor
            assert style.color == selection_style.color
            assert style.color != style.bgcolor
            assert not style.conceal
        outside = app.screen.get_style_at(
            out.content_region.x + 18, out.content_region.y + 3
        )
        assert outside.bgcolor != selection_style.bgcolor
        await pilot.mouse_up(out, offset=(45, 5))
        await pilot.pause()
        # The visible selection must remain after releasing the mouse button.
        assert (
            app.screen.get_style_at(
                out.content_region.x + 25, out.content_region.y + 4
            ).bgcolor
            == selection_style.bgcolor
        )
        selection = out.text_selection
        assert selection is not None
        assert selection.start is not None
        assert selection.end is not None
        selected = app.screen.get_selected_text()
        assert selected
        assert len(selected.splitlines()) == 3
        assert selected == "\n".join(
            (
                out.render_line(3).text.rstrip()[20:],
                out.render_line(4).text.rstrip(),
                out.render_line(5).text.rstrip()[:46],
            )
        )
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert app.clipboard == selected
        assert app.is_running
        await pilot.click(out, offset=(18, 3))
        await pilot.pause()
        assert out.text_selection is None
        cleared_style = app.screen.get_style_at(
            out.content_region.x + 25, out.content_region.y + 3
        )
        assert cleared_style.bgcolor == original_style.bgcolor

        # A backwards, single-line drag must select only the requested text.
        await pilot.mouse_down(out, offset=(45, 3))
        await pilot.hover(out, offset=(20, 3))
        await pilot.mouse_up(out, offset=(20, 3))
        await pilot.pause()
        assert app.screen.get_selected_text() == out.render_line(3).text[20:46]
        assert (
            app.screen.get_style_at(
                out.content_region.x + 25, out.content_region.y + 3
            ).bgcolor
            == selection_style.bgcolor
        )
        assert (
            app.screen.get_style_at(
                out.content_region.x + 48, out.content_region.y + 3
            ).bgcolor
            != selection_style.bgcolor
        )


def test_event_log_collapses_and_expands_active_chain():
    _run(_collapse_expand())


def test_tool_actions_show_console_detail_and_keep_metadata_in_raw_view():
    _run(_tool_arguments_expand())


async def _tool_arguments_expand():
    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        stamp = datetime(2026, 10, 26, 9, 8, 13, tzinfo=UTC)
        app._process_events(
            [
                Observation(
                    "tool_call_started",
                    stamp,
                    {
                        "name": "glob",
                        "tool_call_id": "detail-call",
                        "detail": "pattern **/*.py | paths robot_learning",
                        "arguments": {"pattern": "**/*.py", "paths": "robot_learning"},
                    },
                ),
                Observation(
                    "tool_call_completed",
                    stamp + timedelta(seconds=1),
                    {
                        "name": "glob",
                        "tool_call_id": "detail-call",
                        "status": "completed",
                    },
                ),
            ]
        )
        await pilot.pause()
        out = app.query_one("#output")
        node = out._node_by_id["tool:detail-call"]
        out.move_cursor(node, animate=False)
        await pilot.pause()
        assert node.is_expanded
        painted = "\n".join(strip.text for strip in out.render_lines(out.size.region))
        assert "**/*.py" in painted
        assert "robot_learning" in painted
        assert '"pattern"' not in painted
        assert not node.children
        await pilot.press("r")
        await pilot.pause()
        assert app.screen.item.payload["arguments"] == {
            "pattern": "**/*.py",
            "paths": "robot_learning",
        }


def test_pi_text_is_shown_once_and_patch_payload_stays_in_raw_view():
    _run(_readable_messages_and_patches())


async def _readable_messages_and_patches():
    app = _demo_app()
    async with app.run_test(size=(160, 60)) as pilot:
        await pilot.pause()
        stamp = datetime(2026, 10, 26, 9, 13, tzinfo=UTC)
        message = "The physical definitions imply UNIQUE_OBSERVATION."
        patch = "*** Begin Patch\n*** Add File: pi_workspace/model.md\n+First line\n+Second line\n*** End Patch"
        app._process_events(
            [
                Observation(
                    "pi_message",
                    stamp,
                    {"text": message, "turn": "readable", "final": True},
                    session_id="opaque-backend-uuid",
                ),
                Observation(
                    "tool_call_started",
                    stamp,
                    {
                        "name": "apply_patch",
                        "tool_call_id": "readable-patch",
                        "detail": "pi_workspace/model.md",
                        "arguments": patch,
                    },
                ),
                Observation(
                    "tool_call_completed",
                    stamp,
                    {
                        "name": "apply_patch",
                        "tool_call_id": "readable-patch",
                        "status": "completed",
                    },
                ),
            ]
        )
        await pilot.pause()
        out = app.query_one("#output")
        message_item = next(
            item
            for item in _timeline_items(app)
            if item.kind == "pi" and item.payload.get("turn") == "readable"
        )
        message_node = out._node_by_id[message_item.item_id]
        assert message_node.is_expanded
        painted = "\n".join(strip.text for strip in out.render_lines(out.size.region))
        assert painted.count("UNIQUE_OBSERVATION") == 1
        assert "opaque-backend-uuid" not in painted
        assert "completed | 0s" not in painted
        out.move_cursor(message_node, animate=False)
        await pilot.press("left")
        await pilot.pause()
        app._render_log()
        await pilot.pause()
        assert out._node_by_id[message_item.item_id].is_collapsed
        patch_node = out._node_by_id["tool:readable-patch"]
        out.move_cursor(patch_node, animate=False)
        await pilot.press("right")
        await pilot.pause()
        painted = "\n".join(strip.text for strip in out.render_lines(out.size.region))
        assert "pi_workspace/model.md" in painted
        assert "+First line" not in painted and "+Second line" not in painted
        assert "\\n" not in painted
        assert not any(mark in painted for mark in ("├", "└", "[>]"))
        await pilot.press("r")
        await pilot.pause()
        assert app.screen.item.payload["arguments"] == patch


def test_expanded_text_wraps_and_updates_after_a_long_streamed_prefix():
    _run(_expanded_text_updates())


async def _expanded_text_updates():
    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        stamp = datetime(2026, 10, 26, 9, 8, 13, tzinfo=UTC)
        prefix = "A long scientific observation that must remain readable. " * 5

        def append(text):
            app._process_events(
                [
                    Observation(
                        "pi_message",
                        stamp,
                        {"turn": "detail-turn", "text": text, "final": False},
                        session_id="detail-session",
                    )
                ]
            )

        append(prefix)
        await pilot.pause()
        out = app.query_one("#output")
        item = next(
            item
            for item in _timeline_items(app)
            if item.kind == "pi" and item.payload.get("turn") == "detail-turn"
        )
        node = out._node_by_id[item.item_id]
        out.move_cursor(node, animate=False)
        await pilot.press("right")
        await pilot.pause()
        append("UNIQUE_FINAL_OBSERVATION")
        await pilot.pause()
        node = out._node_by_id[item.item_id]
        assert node.is_expanded
        assert "UNIQUE_FINAL_OBSERVATION" in "".join(
            child.label.plain for child in node.children
        )
        await pilot.resize_terminal(100, 45)
        await pilot.pause()
        node = out._node_by_id[item.item_id]
        assert "UNIQUE_FINAL_OBSERVATION" in "".join(
            child.label.plain for child in node.children
        )
        for y, line in enumerate(out._tree_lines):
            if line.node.parent is node:
                strip = out.render_line(y - int(out.scroll_offset.y))
                assert strip.text.rstrip().endswith(line.node.label.plain.rstrip())


def test_terminal_drag_release_does_not_collapse_the_selected_block():
    _run(_terminal_drag_release())


async def _terminal_drag_release():
    from textual import events

    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        out = app.query_one("#output")
        session = out._node_by_id["session:S7"]
        row = next(y for y, line in enumerate(out._tree_lines) if line.node is session)
        # Send terminal input through App, including its synthetic Click on
        # mouse release. Pilot.mouse_up bypasses that part of input processing.
        for event_type, x in (
            (events.MouseDown, 60),
            (events.MouseMove, 20),
            (events.MouseUp, 20),
        ):
            app.post_message(
                event_type(
                    widget=None,
                    x=out.content_region.x + x,
                    y=out.content_region.y + row,
                    delta_x=0,
                    delta_y=0,
                    button=1,
                    shift=False,
                    meta=False,
                    ctrl=False,
                )
            )
            await pilot.pause()
        assert session.is_expanded
        assert app.screen.get_selected_text()
        selection_style = app.screen.get_component_rich_style("screen--selection")
        assert (
            app.screen.get_style_at(
                out.content_region.x + 25, out.content_region.y + row
            ).bgcolor
            == selection_style.bgcolor
        )
        await pilot.click(out, offset=(13, row))
        await pilot.pause()
        assert out.text_selection is None
        assert not session.is_expanded


async def _collapse_expand():
    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        out = app.query_one("#output")
        node = out._node_by_id["session:S7"]
        out.move_cursor(node, animate=False)
        assert node.is_expanded is True
        await pilot.press("space")
        await pilot.pause()
        assert node.is_expanded is False
        await pilot.press("space")
        await pilot.pause()
        assert node.is_expanded is True
        await pilot.press("enter")
        await pilot.pause()
        assert node.is_expanded is False
        await pilot.press("enter")
        await pilot.pause()
        assert node.is_expanded is True


def test_search_input_filters_the_timeline():
    _run(_search_log())


async def _search_log():
    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        search = app.query_one("#log-search")
        assert search.display is True
        search.value = "measurement"
        await pilot.press("enter")
        await pilot.pause()
        heading = str(app.query_one("#output-heading").render())
        assert "search: measurement" in heading


def test_filter_modal_opens():
    _run(_filter_modal())


async def _filter_modal():
    from tui.event_log import FilterScreen

    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        await pilot.press("f")
        await pilot.pause()
        assert isinstance(app.screen, FilterScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, FilterScreen)


def test_raw_event_opens_a_modal():
    _run(_raw_modal())


async def _raw_modal():
    from tui.event_log import RawEventScreen

    app = _demo_app()
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        out = app.query_one("#output")
        out.move_cursor(out._node_by_id["session:S7"], animate=False)
        app.action_raw_event()
        await pilot.pause()
        assert isinstance(app.screen, RawEventScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, RawEventScreen)


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
    from runner import reporting as console
    from tui.report import _display_text

    monkeypatch.setattr(console, "_ROOT", tmp_path)
    path = tmp_path / "models" / "candidates" / "run.zip"
    text = _display_text(f"reward -6.122319559999999 at {path}")
    assert "reward -6.122" in text
    assert "models/candidates/run.zip" in text
    assert str(path) not in text
