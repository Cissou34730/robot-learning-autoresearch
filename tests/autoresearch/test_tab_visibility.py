"""Idle tab deadlines are operator metadata, not campaign lifecycle state."""

import json

import pytest

from tui.tab_visibility import IDLE_TAB_SECONDS, TabIdleTracker


def test_idle_deadline_survives_restart_and_running_clears_it(tmp_path):
    folder = tmp_path / "campaign-1"
    folder.mkdir()
    tracker = TabIdleTracker(tmp_path / "control")
    assert tracker.observe(folder, active=False, now=100) == 100
    reopened = TabIdleTracker(tmp_path / "control")
    assert reopened.observe(folder, active=False, now=100 + IDLE_TAB_SECONDS) == 100
    assert reopened.observe(folder, active=True, now=8000) is None
    assert reopened.observe(folder, active=True, now=20000) is None
    assert reopened.observe(folder, active=False, now=20001) == 20001
    assert not list(folder.iterdir())


def test_new_activity_while_console_was_closed_restarts_unknown_idle_period(tmp_path):
    folder = tmp_path / "campaign-1"
    journal = folder / "reports" / "tui_observations" / "one.events.v2.jsonl"
    journal.parent.mkdir(parents=True)
    journal.write_text("first run\n", encoding="utf-8")
    tracker = TabIdleTracker(tmp_path / "control")
    assert tracker.observe(folder, active=False, now=100) == 100
    journal.write_text("first run\nnew execution\n", encoding="utf-8")
    reopened = TabIdleTracker(tmp_path / "control")
    assert reopened.observe(folder, active=False, now=10000) == 10000
    assert reopened.observe(folder, active=False, now=11000) == 10000


def test_bad_idle_metadata_is_reported_instead_of_assuming_expiry(tmp_path):
    tracker = TabIdleTracker(tmp_path / "control")
    folder = tmp_path / "campaign-1"
    folder.mkdir()
    tracker.observe(folder, active=False, now=100)
    record = next((tmp_path / "control").glob("*.json"))
    for data in (
        "broken",
        "null",
        json.dumps({"idle_since": "yesterday", "activity": ""}),
    ):
        record.write_text(data, encoding="utf-8")
        with pytest.raises(ValueError):
            tracker.observe(folder, active=False, now=10000)
