"""Wires the launcher's parts for one campaign run and owns their cleanup."""

from __future__ import annotations

import traceback
from pathlib import Path

from runner import paths
from runner.launcher import campaign
from runner.launcher.child import ChildRunner, RunLog
from runner.launcher.copilot_runtime import CopilotRuntime
from runner.launcher.events import LauncherEvents
from runner.launcher.operation_bridge import OperationBridge
from runner.launcher.options import LaunchOptions
from runner.launcher.phases import Phases
from runner.launcher.pi_session import PISessions
from runner.launcher.runner_client import LauncherError, RunnerClient
from runner.launcher.stop import StopControl, StopDeadlineExceeded
from runner.launcher.trust import TrustGuard

STOP_DEADLINE_EXIT_CODE = 124


def build(options: LaunchOptions, *, started_at: float, log: RunLog) -> Phases:
    events = LauncherEvents(options.campaign_root)
    stop = StopControl(
        paths.stop_request_path(options.campaign_root),
        options.stop_timeout_seconds,
        started_at=started_at,
        on_request=lambda message: events.status(message, scope="info"),
    )
    stop.discard_stale()
    children = ChildRunner(cwd=options.campaign_root, stop=stop, log=log)
    trust = TrustGuard(options.campaign_root, options.harness_root)
    runner = RunnerClient(
        harness_root=options.harness_root,
        children=children,
        trust=trust,
        timesteps=options.timesteps,
        max_timesteps=options.max_timesteps,
    )
    runtime = CopilotRuntime(
        children=children,
        stop=stop,
        command=lambda port, token: runner.adapter_command(
            "--controller-port",
            str(port),
            "--controller-token",
            token,
            "--model",
            options.model,
            "--reasoning",
            options.reasoning,
        ),
        before_start=trust.verify,
    )
    bridge = OperationBridge(
        campaign_root=options.campaign_root,
        runner=runner,
        trust=trust,
        stop=stop,
        update_brief=runner.build_brief,
    )
    sessions = PISessions(
        campaign_root=options.campaign_root,
        model=options.model,
        reasoning=options.reasoning,
        runtime=runtime,
        bridge=bridge,
        trust=trust,
        stop=stop,
        events=events,
    )
    return Phases(
        options=options,
        runner=runner,
        sessions=sessions,
        stop=stop,
        events=events,
        home=Path.home(),
    )


def run_campaign(options: LaunchOptions, *, started_at: float) -> int:
    log = RunLog.for_campaign(options.campaign_root)
    phases = build(options, started_at=started_at, log=log)
    try:
        phases.runner.require_runtime()
        return campaign.run(phases)
    except Exception as error:
        log.write(traceback.format_exc())
        code = (
            "stop_deadline_exceeded"
            if phases.stop.deadline_exceeded
            else "launcher_failed"
        )
        phases.events.failure(str(error), code=code)
        if phases.stop.deadline_exceeded or isinstance(error, StopDeadlineExceeded):
            return STOP_DEADLINE_EXIT_CODE
        raise LauncherError(str(error)) from error
    finally:
        try:
            phases.sessions.close_runtime()
        finally:
            phases.stop.clear()
            phases.runner.close()
            log.close()
