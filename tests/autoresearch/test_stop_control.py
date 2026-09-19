"""Focused tests for the external cooperative-stop bridge."""

import asyncio
import json
import threading
from argparse import Namespace
from pathlib import Path

from research import run_experiment
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


def test_runner_marks_an_early_training_interrupt_for_restart(monkeypatch, tmp_path):
    proposal = tmp_path / "proposal.json"
    restart = tmp_path / "RESTART_PENDING"
    recovery = tmp_path / "RECOVERY_PENDING"
    proposal.write_text(json.dumps({"change": "test"}), encoding="utf-8")

    monkeypatch.setattr(
        run_experiment,
        "parse_args",
        lambda: Namespace(
            migrate_research_state=False,
            begin_hypothesis=False,
            check_proposal=False,
            check_evaluation_request=False,
            check_analysis_deliverable=False,
            check_lineage_evidence=None,
            evaluate_pending_final=False,
            evaluate_pending=False,
        ),
    )
    monkeypatch.setattr(run_experiment.repository, "synchronize_experiment_log", lambda: None)
    monkeypatch.setattr(run_experiment.repository, "read_state", dict)
    monkeypatch.setattr(
        run_experiment.protocol,
        "validate_proposal_against_state",
        lambda proposal, state: "training",
    )
    monkeypatch.setattr(
        run_experiment,
        "run_training_experiment",
        lambda proposal, args: (_ for _ in ()).throw(KeyboardInterrupt),
    )
    monkeypatch.setattr(run_experiment.paths, "PROPOSAL_PATH", proposal)
    monkeypatch.setattr(run_experiment.paths, "RESTART_PENDING_PATH", restart)
    monkeypatch.setattr(run_experiment.paths, "RECOVERY_PENDING_PATH", recovery)

    assert run_experiment.main() == 130
    assert restart.read_text(encoding="utf-8") == (
        "Restart the preserved proposal from the beginning.\n"
    )


def test_launcher_supervises_children_and_stops_before_phase_validation():
    source = (Path(__file__).resolve().parents[2] / "run_research.ps1").read_text(
        encoding="utf-8"
    )

    assert "[string]$StopRequestPath" in source
    assert 'Environment["ROBOT_RESEARCH_STOP_REQUEST"]' in source
    assert "WaitForExit(100)" in source
    assert "StopTimeoutSeconds = 180" in source
    assert source.count(
        'Test-StopAfterOperation $script:ResearcherExitCode "researcher session"'
    ) == source.count("Invoke-ResearcherSession -Prompt")

    cursor = 0
    while True:
        invocation = source.find("Invoke-ResearcherSession -Prompt", cursor)
        if invocation < 0:
            break
        stop_check = source.find(
            'Test-StopAfterOperation $script:ResearcherExitCode "researcher session"',
            invocation,
        )
        validation = source.find("Get-", invocation)
        assert invocation < stop_check < validation
        cursor = stop_check + 1
