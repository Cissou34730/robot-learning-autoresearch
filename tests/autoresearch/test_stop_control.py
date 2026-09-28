"""Focused tests for the external cooperative-stop bridge."""

import asyncio
import threading
from pathlib import Path

from research import run_experiment
from research import runner_execution as execution
from research import runner_paths as paths
from research import runner_repository as repository
from research.stop_control import (
    STOP_REQUEST_ENV,
    interrupt_on_stop_request,
    stop_request_path,
    stop_requested,
    wait_for_stop_request,
)


def test_stop_request_is_explicit_and_run_scoped(monkeypatch, tmp_path):
    request = tmp_path / "one-run" / "stop.request"
    request.parent.mkdir()
    monkeypatch.setenv(STOP_REQUEST_ENV, str(request))

    assert stop_request_path() == request
    assert not stop_requested()

    request.touch()

    assert stop_requested()


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
    research = tmp_path / "research"
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
        "path": "research/scientific_model.md",
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


def test_launcher_supervises_children_and_stops_before_phase_validation():
    source = (Path(__file__).resolve().parents[2] / "run_research.ps1").read_text(
        encoding="utf-8"
    )

    assert "[string]$StopRequestPath" in source
    assert 'Environment["ROBOT_RESEARCH_STOP_REQUEST"]' in source
    assert "WaitForExit(100)" in source
    assert "StopTimeoutSeconds = 180" in source
    invocations = [
        index
        for index in range(len(source))
        if source.startswith("Invoke-PISession -Prompt", index)
    ]
    stop_checks = [
        index
        for index in range(len(source))
        if source.startswith(
            'Test-StopAfterOperation $script:PIExitCode "PI session"', index
        )
    ]
    assert invocations
    assert len(invocations) == len(stop_checks)
    assert all(invocation < stop for invocation, stop in zip(invocations, stop_checks))


def test_launcher_does_not_consume_native_console_interrupts():
    source = (Path(__file__).resolve().parents[2] / "run_research.ps1").read_text(
        encoding="utf-8"
    )

    assert "SetConsoleCtrlHandler" not in source
    assert "RobotResearchConsoleInterrupt" not in source
