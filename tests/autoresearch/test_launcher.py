"""Python launcher behavior: exclusion, external stop, caps and text parity."""

from __future__ import annotations

import argparse
import json
import os
import time
from contextlib import contextmanager
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


@pytest.mark.parametrize(
    "stage,missing,nested",
    [
        ("preparing", False, False),
        ("preparing", False, True),
        ("ready", False, False),
        ("ready", False, True),
        ("ready", True, False),
    ],
)
def test_launcher_recovers_root_under_lock_before_binding(
    tmp_path, monkeypatch, stage, missing, nested
):
    from runner import paths, recipe_development
    from runner.launcher import assembly, cli

    campaign = tmp_path / "campaign"
    archive = paths.recipe_development_archive(campaign, "delivery")
    archive.mkdir(parents=True)
    (archive.parent / "public" / ".git").mkdir(parents=True)
    marker = paths.recipe_handoff_directory(campaign) / "handoff.json"
    marker.write_text(
        json.dumps(
            {
                "version": 1,
                "root": str(campaign.resolve()),
                "stage": stage,
                "campaign_id": "delivery",
                "public_head": "public",
            }
        ),
        encoding="utf-8",
    )
    if not missing:
        campaign.mkdir()
        directory = campaign / "nested" if nested else campaign
        directory.mkdir(exist_ok=True)
        monkeypatch.chdir(directory)
    order = []

    @contextmanager
    def lock(root, _refusal, *, recovery=False):
        assert root == campaign and recovery
        campaign_lock.mutex_name(root, recovery=recovery)
        order.append("lock")
        yield
        order.append("unlock")

    def recover_child(command, *, cwd, env, capture_output, text, check):
        assert order == ["clean", "lock"]
        assert command[-1] == "runner.recipe_development"
        assert cwd == cli.HARNESS_ROOT
        assert Path.cwd().resolve() == cli.HARNESS_ROOT.resolve()
        assert env[paths.CAMPAIGN_ROOT_ENV] == str(campaign)
        assert capture_output and text and not check
        assert campaign.exists() is not missing
        if not missing:
            archive.rmdir()
            campaign.replace(archive)
        (archive.parent / "public").replace(campaign)
        order.append("recover")
        return SimpleNamespace(returncode=0)

    def bind(_harness, root):
        assert root.exists()
        os.chdir(root)
        order.append("bind")
        return root

    monkeypatch.setattr(
        cli, "require_clean_harness", lambda _root: order.append("clean")
    )
    monkeypatch.setattr(cli, "CampaignLock", lock)
    monkeypatch.setattr(cli.subprocess, "run", recover_child)
    monkeypatch.setattr(cli, "bind_campaign", bind)
    monkeypatch.setattr(
        assembly, "run_campaign", lambda *_args, **_kwargs: order.append("run") or 0
    )
    monkeypatch.setattr("runner.launcher.runner_client.uv_executable", lambda: "uv")
    assert recipe_development.recovery_pending(campaign)
    assert cli.main(["--campaign-root", str(campaign)]) == 0
    assert Path.cwd() == campaign
    assert order == ["clean", "lock", "recover", "bind", "run", "unlock"]


def test_missing_root_without_recovery_marker_is_still_refused(tmp_path):
    root = tmp_path / "missing"
    with pytest.raises(FileNotFoundError):
        campaign_lock.mutex_name(root, recovery=True)


def test_each_phase_resolves_its_own_backend():
    from runner.launcher import cli
    from runner.launcher.pi_session import PISessions

    def backends(*argv):
        resolved = cli.phase_backends(cli.parse_args(list(argv)))
        return {phase: (b.model, b.reasoning) for phase, b in resolved.items()}

    assert backends() == {
        "analyst": ("gpt-6-luna", "max"),
        "recipe": ("gpt-6-luna", "high"),
        "startup": ("gpt-6-luna", "high"),
        "research": ("gpt-6-luna", "high"),
    }
    assert set(backends("--model", "m", "--reasoning", "low").values()) == {
        ("m", "low")
    }
    # The picker's Copilot form and the bare name are the same backend.
    assert backends("--model", "github-copilot/gpt-6-sol")["startup"] == (
        "gpt-6-sol",
        "high",
    )
    assert backends(
        "--model",
        "m",
        "--analyst-model",
        "opencode-go/a",
        "--research-reasoning",
        "xhigh",
    ) == {
        "analyst": ("opencode-go/a", "max"),
        "recipe": ("m", "high"),
        "startup": ("m", "high"),
        "research": ("m", "xhigh"),
    }
    options = cli.launch_options(
        cli.parse_args(["--recipe-model", "r", "--startup-model", "s"]), Path(".")
    )
    sessions = PISessions(
        campaign_root=Path("."),
        options=options,
        runtime=None,
        bridge=None,
        trust=None,
        stop=None,
        events=None,
    )
    for kind, model in (
        ("recipe_development", "r"),
        ("startup", "s"),
        ("goal_review", "gpt-6-luna"),
        ("inquiry", "gpt-6-luna"),
    ):
        state = {"scientific_session": {"kind": kind}}
        assert sessions._backend(state, preliminary=False).model == model
    assert sessions._backend({}, preliminary=True) == options.analyst()


def test_runtime_restarts_only_when_the_next_session_changes_backend(tmp_path):
    import socket
    import threading

    from runner.launcher.copilot_runtime import CopilotRuntime
    from runner.launcher.options import PhaseBackend
    from runner.launcher.stop import StopControl

    started, connections, threads = [], [], []

    class Process:
        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

    def start(command):
        port, token, backend = command
        started.append(backend)

        def connect():
            connection = socket.create_connection(("127.0.0.1", port))
            ready = json.dumps({"type": "ready", "token": token}) + "\n"
            connection.sendall(ready.encode("utf-8"))
            connections.append(connection)

        threads.append(threading.Thread(target=connect))
        threads[-1].start()
        return Process()

    runtime = CopilotRuntime(
        children=SimpleNamespace(start=start),
        stop=StopControl(tmp_path / "stop", 180, started_at=0.0),
        command=lambda port, token, backend: [port, token, backend],
        before_start=lambda: None,
    )
    analyst = PhaseBackend("gpt-6-luna", "max")
    research = PhaseBackend("gpt-6-luna", "high")
    try:
        runtime.start(analyst)
        runtime.start(analyst)
        runtime.start(research)
        assert started == [analyst, research]
    finally:
        runtime.stop()
        for thread in threads:
            thread.join()
        for connection in connections:
            connection.close()


@requires_windows
def test_recovery_keeps_the_same_mutex_when_the_root_is_archived(tmp_path):
    from runner import paths

    root = tmp_path / "campaign"
    root.mkdir()
    archive = paths.recipe_development_archive(root, "campaign")
    (archive.parent / "public" / ".git").mkdir(parents=True)
    marker = paths.recipe_handoff_directory(root) / "handoff.json"
    marker.write_text(
        json.dumps(
            {
                "version": 1,
                "root": str(root.resolve()),
                "stage": "ready",
                "campaign_id": "campaign",
                "public_head": "public",
            }
        ),
        encoding="utf-8",
    )
    name = campaign_lock.mutex_name(root)
    with campaign_lock.CampaignLock(root, "busy"):
        root.replace(archive)
        assert campaign_lock.mutex_name(root, recovery=True) == name
        with (
            pytest.raises(campaign_lock.CampaignBusy),
            campaign_lock.CampaignLock(root, "busy", recovery=True),
        ):
            pass


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


@requires_windows
def test_commit_guard_refuses_runtime_commits_only_while_a_campaign_runs(
    tmp_path, monkeypatch
):
    from tools import commit_guard

    campaign = tmp_path / "campaign-1"
    (campaign / ".git").mkdir(parents=True)
    staged = ["docs/harness-experiment-log.md"]
    monkeypatch.setattr(commit_guard, "CAMPAIGNS_ROOT", tmp_path)
    monkeypatch.setattr(
        commit_guard,
        "staged_runtime_paths",
        lambda: [path for path in staged if commit_guard.is_harness_runtime(path)],
    )
    with campaign_lock.CampaignLock(campaign, "busy"):
        assert commit_guard.main() == 0
        staged.append("runner/execution.py")
        assert commit_guard.main() == 1
    assert commit_guard.main() == 0


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


def test_batch_launcher_forwards_only_the_backend_options_set():
    assert (
        run_parallel.backend_arguments(run_parallel.parse_args(["--count", "2"])) == []
    )
    assert run_parallel.backend_arguments(
        run_parallel.parse_args(
            [
                "--count",
                "2",
                "--reasoning",
                "medium",
                "--analyst-model",
                "opencode-go/a",
                "--research-reasoning",
                "xhigh",
            ]
        )
    ) == [
        "--reasoning",
        "medium",
        "--analyst-model",
        "opencode-go/a",
        "--research-reasoning",
        "xhigh",
    ]


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
