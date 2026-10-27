"""Focused tests for the external cooperative-stop bridge."""

import asyncio
import os
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from runner import execution, paths, repository, run_experiment
from runner.launcher import cli, copilot_runtime, phases
from runner.launcher import reset as launcher_reset
from runner.launcher.runner_client import LauncherError
from runner.launcher.stop import StopControl
from runner.stop_control import (
    STOP_REQUEST_ENV,
    interrupt_on_stop_request,
    stop_request_path,
    stop_requested,
    wait_for_stop_request,
)


def _stop(path: Path, **options) -> StopControl:
    return StopControl(path, 180, started_at=0.0, **options)


class _Bootstrap:
    """A runtime process that never connects to the launcher."""

    def __init__(self, *, exits: bool = True) -> None:
        self.exits = exits
        self.waits: list[float] = []

    def poll(self):
        return None

    def wait(self, timeout=None):
        self.waits.append(timeout)
        if not self.exits and len(self.waits) == 1:
            raise subprocess.TimeoutExpired("copilot", timeout)
        return 0


@pytest.mark.parametrize("stop_before_start", [True, False])
def test_launcher_stop_during_runtime_startup_starts_no_session(
    tmp_path, stop_before_start
):
    request = tmp_path / "stop-request"
    started = []
    process = _Bootstrap()

    def start(command):
        started.append(command)
        request.touch()
        return process

    if stop_before_start:
        request.touch()
    runtime = copilot_runtime.CopilotRuntime(
        children=SimpleNamespace(start=start),
        stop=_stop(request),
        command=lambda port, token: ["copilot", str(port), token],
        before_start=lambda: None,
    )
    runtime.start()
    assert bool(started) is not stop_before_start
    runtime.stop()
    if not stop_before_start:
        assert process.waits, "the bootstrap must be awaited before release"


def test_cancelled_startup_without_channel_cleans_up_bootstrap_without_failure(
    monkeypatch, tmp_path
):
    request = tmp_path / "stop-request"
    request.touch()
    killed = []
    monkeypatch.setattr(copilot_runtime, "kill_tree", killed.append)
    process = _Bootstrap(exits=False)
    runtime = copilot_runtime.CopilotRuntime(
        children=SimpleNamespace(start=lambda _command: process),
        stop=_stop(request),
        command=lambda port, token: [],
        before_start=lambda: None,
    )
    runtime._process = process
    runtime.stop()
    assert killed == [process]
    assert process.waits[0] <= 5
    assert len(process.waits) == 2
    assert runtime._process is None


def test_stop_request_is_explicit_and_run_scoped(monkeypatch, tmp_path):
    request = tmp_path / "one-run" / "stop.request"
    request.parent.mkdir()
    monkeypatch.setenv(STOP_REQUEST_ENV, str(request))

    assert stop_request_path() == request
    assert not stop_requested()

    request.touch()

    assert stop_requested()


def test_launcher_discards_only_a_request_older_than_its_start(tmp_path):
    request = tmp_path / "stop-request"
    request.touch()
    os.utime(request, (1000.0, 1000.0))
    StopControl(request, 180, started_at=2000.0).discard_stale()
    assert not request.exists()
    request.touch()
    StopControl(request, 180, started_at=1000.0).discard_stale()
    assert request.exists()


def test_launcher_stop_deadline_starts_at_the_first_observation(tmp_path):
    request = tmp_path / "stop-request"
    clock = [10.0]
    notices = []
    stop = _stop(request, on_request=notices.append, clock=lambda: clock[0])
    assert not stop.requested()
    request.touch()
    assert stop.requested()
    assert stop.remaining_seconds() == 180
    clock[0] = 189.0
    assert not stop.deadline_passed()
    clock[0] = 190.0
    assert stop.deadline_passed()
    assert len(notices) == 1


def test_sync_runner_bridge_interrupts_when_request_appears(tmp_path):
    request = tmp_path / "stop.request"
    interrupted = threading.Event()

    with interrupt_on_stop_request(
        request,
        interrupt=interrupted.set,
        poll_seconds=0.005,
    ):
        request.touch()
        assert interrupted.wait(1)


def test_async_researcher_bridge_completes_when_request_appears(tmp_path):
    request = tmp_path / "stop.request"

    async def exercise() -> None:
        waiter = asyncio.create_task(wait_for_stop_request(request))
        await asyncio.sleep(0)
        request.touch()
        await asyncio.wait_for(waiter, timeout=1)

    asyncio.run(exercise())


def test_runner_preserves_an_early_training_interrupt_for_resume(monkeypatch, tmp_path):
    research = tmp_path / "campaigns"
    research.mkdir()
    for name, value in {
        "ROOT": tmp_path,
        "RESEARCH_DIR": research,
        "STATE_PATH": research / "research_state.json",
        "RESULTS_PATH": research / "results.jsonl",
        "LOG_PATH": research / "EXPERIMENTS.md",
        "OPERATION_REQUEST_PATH": research / "operation_request.json",
        "TRAINING_LOG_DIR": research / "training_logs",
        "CANDIDATE_ROOT": tmp_path / "models" / "candidates",
    }.items():
        monkeypatch.setattr(paths, name, value)
    monkeypatch.setattr(repository, "git", lambda *args: "a" * 40 + "\n")
    monkeypatch.setattr(repository, "scientific_delta", lambda _parent: [])
    monkeypatch.setattr(
        repository, "publish_scientific_recipe", lambda *_args: "a" * 40
    )
    monkeypatch.setattr(run_experiment.research_config, "load_experiment_config", dict)
    monkeypatch.setattr(execution, "validate_active_configuration", lambda: None)
    monkeypatch.setattr(
        execution,
        "train_candidate",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt),
    )

    state = repository.empty_campaign_state(
        campaign={"id": "campaign", "started_at": "now", "base_commit": "base"},
        last_verdict="fresh",
    )
    state["scientific_model"] = {
        "status": "ready",
        "path": "pi_workspace/scientific_model.md",
        "commit": "a" * 40,
    }
    repository.start_scientific_session(
        state,
        kind="startup",
        objective="Request bounded training evidence.",
        backend_adapter="copilot",
        backend_model="gpt-5.6-luna",
        backend_reasoning="high",
    )
    repository.write_state(state)
    run_experiment.accept_operation(
        {
            "training": {
                "initialization": "fresh",
                "seed": 4,
                "steps": 10,
                "description": "Train the current scientific recipe.",
                "rationale": "Learning dynamics inform the next decision.",
            }
        },
        state,
    )

    assert run_experiment.execute_pending_operation() == 130
    pending = repository.read_state()["pending_operation"]
    assert pending["progress"] == "training_dispatched"
    assert pending["failure"] is None


@pytest.fixture
def _bound_process(monkeypatch, tmp_path):
    """Launcher entry points bind the process to a campaign; restore it."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(paths.CAMPAIGN_ROOT_ENV, str(tmp_path))
    monkeypatch.setenv("PYTHONPATH", "")


@pytest.mark.parametrize("mode", ["conflict", "missing"])
def test_launcher_refusals_return_failure_before_any_work(
    monkeypatch, tmp_path, _bound_process, mode
):
    campaign = tmp_path / "campaign"
    (campaign / ".git").mkdir(parents=True)
    monkeypatch.setattr(cli, "require_clean_harness", lambda _root: None)
    monkeypatch.setattr(
        cli,
        "CampaignLock",
        lambda *_args: pytest.fail("A refused launch must not take the campaign."),
    )
    arguments = {
        "conflict": [
            "--campaign-root",
            str(campaign),
            "--provider",
            "github-copilot",
            "--model",
            "opencode/test-model",
        ],
        "missing": ["--campaign-root", str(tmp_path / "missing")],
    }[mode]
    assert cli.main(arguments) == 1


@pytest.mark.parametrize("reset_exit_code", [0, 1, 130])
def test_reset_runs_in_the_campaign_with_its_arguments(
    monkeypatch, tmp_path, _bound_process, reset_exit_code
):
    campaign = tmp_path / "campaign"
    (campaign / ".git").mkdir(parents=True)
    calls = []

    def run(command, *, cwd, check):
        calls.append((command, Path(cwd)))
        return subprocess.CompletedProcess(command, reset_exit_code)

    monkeypatch.setattr(launcher_reset, "uv_executable", lambda: "uv")
    monkeypatch.setattr(launcher_reset.subprocess, "run", run)
    code = launcher_reset.main(
        [
            "--campaign-root",
            str(campaign),
            "--mode",
            "Fresh",
            "--clean",
            "--recipe-ref",
            "baseline-distinct-episodes-v3",
            "--force",
        ]
    )
    assert code == (0 if reset_exit_code == 0 else 1)
    ((command, cwd),) = calls
    assert cwd == campaign
    assert command[command.index("--mode") + 1] == "fresh"
    assert "--clean" in command
    assert "baseline-distinct-episodes-v3" in command


@pytest.mark.parametrize(
    "arguments",
    [
        ["--mode", "fresh"],
        ["--mode", "fresh", "--baseline-ref", "x", "--force"],
        ["--mode", "baseline", "--force"],
        ["--mode", "baseline", "--baseline-ref", "x", "--recipe-ref", "y", "--force"],
    ],
)
def test_reset_refuses_inconsistent_arguments_before_any_work(
    monkeypatch, tmp_path, arguments
):
    monkeypatch.setattr(
        launcher_reset.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("A refused reset must not run."),
    )
    assert launcher_reset.main(["--campaign-root", str(tmp_path), *arguments]) == 1


def test_launcher_stop_helper_executes_the_cooperative_exit_contract(tmp_path):
    request = tmp_path / "stop-request"
    stage = phases.Phases(
        options=SimpleNamespace(campaign_root=tmp_path),
        runner=SimpleNamespace(),
        sessions=SimpleNamespace(),
        stop=_stop(request),
        events=SimpleNamespace(),
        home=tmp_path,
    )
    assert not stage.stopped_after(0, "PI session")
    request.touch()
    assert stage.stopped_after(0, "PI session")
    assert stage.stopped_after(phases.STOPPED, "PI session")
    with pytest.raises(LauncherError, match="instead of completing cooperatively"):
        stage.stopped_after(1, "PI session")
