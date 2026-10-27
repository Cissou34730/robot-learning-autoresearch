"""Python launcher behavior: exclusion, external stop, caps and text parity."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from runner.launcher import campaign_lock, pstext
from runner.paths import stop_request_path
from tools import run_parallel
from tui import controller as control

requires_windows = pytest.mark.skipif(
    os.name != "nt", reason="the campaign exclusion is a Windows mutex"
)


@requires_windows
def test_campaign_lock_excludes_a_second_owner_until_released(tmp_path):
    assert not campaign_lock.is_held(tmp_path)
    with campaign_lock.CampaignLock(tmp_path, "busy"):
        assert campaign_lock.is_held(tmp_path)
        alias = Path(str(tmp_path).upper())
        with (
            pytest.raises(campaign_lock.CampaignBusy, match="busy"),
            campaign_lock.CampaignLock(alias, "busy"),
        ):
            pass
    assert not campaign_lock.is_held(tmp_path)


def _campaigns(tmp_path: Path) -> control.WorkspaceLayout:
    root = tmp_path / "robot-learning-campaigns"
    (root / "campaign-1" / ".git").mkdir(parents=True)
    harness = tmp_path / "harness"
    harness.mkdir()
    return control.WorkspaceLayout(harness, root)


@pytest.mark.parametrize("running", [True, False])
def test_console_stops_a_campaign_it_did_not_start_through_its_request(
    tmp_path, running
):
    from tests.autoresearch.test_campaign_controller import FakeMachinery

    layout = _campaigns(tmp_path)
    requested = []
    controller = control.CampaignController(
        layout,
        FakeMachinery(),
        external=SimpleNamespace(
            running=lambda folder: running, request_stop=requested.append
        ),
    )
    outcome = controller.execute("stop", [1], settings=control.LaunchSettings())
    assert outcome.steps[0].status == (control.SUCCESS if running else control.SKIPPED)
    assert requested == ([layout.folder(1)] if running else [])


def test_external_stop_request_is_the_campaigns_own_file(tmp_path):
    folder = tmp_path / "campaign"
    (folder / ".git").mkdir(parents=True)
    control.ExternalCampaigns().request_stop(folder)
    assert stop_request_path(folder).is_file()


def _monitored(tmp_path: Path, *, aiu: float) -> tuple[run_parallel.Monitor, Path]:
    root = tmp_path / "campaign"
    state = root / "runner" / "state" / "research_state.json"
    state.parent.mkdir(parents=True)
    (root / ".git").mkdir()
    state.write_text(json.dumps({"campaign": {"id": "abc"}}), encoding="utf-8")
    usage = root / "reports" / "session_usage" / "abc.jsonl"
    usage.parent.mkdir(parents=True)
    usage.write_text(json.dumps({"role": "pi", "aiu": aiu}), encoding="utf-8")
    control_directory = tmp_path / "control"
    control_directory.mkdir()
    arguments = argparse.Namespace(
        campaign_roots=[root],
        control_directory=control_directory,
        max_hours=2.0,
        max_aiu=50.0,
        poll_seconds=60,
    )
    return run_parallel.Monitor(arguments), root


@pytest.mark.parametrize(
    ("aiu", "active_seconds", "stopped"),
    [(49.9, 0.0, False), (50.0, 0.0, True), (1.0, 7200.0, True)],
)
def test_parallel_monitor_stops_cooperatively_at_a_cap(
    tmp_path, aiu, active_seconds, stopped
):
    monitor, root = _monitored(tmp_path, aiu=aiu)
    (run,) = monitor.runs
    monitor.check(run, time.time(), active_seconds)
    assert stop_request_path(root).is_file() is stopped
    assert bool(run.stopped) is stopped
    assert not run.finished


def test_powershell_text_quirks_that_reach_pi_prompts():
    assert pstext.items(None) == [None]
    assert pstext.count(None) == 0
    assert pstext.count("one") == 1
    assert pstext.same("Measurement", "measurement")
    assert pstext.interpolated_number(0.1 + 0.2) == "0.3"
    assert pstext.json_number(2.0) == "2.0"
    assert pstext.invariant_fixed_one(1.25) == "1.3"
    assert pstext.pipeline_json(["only"]) == '"only"'
