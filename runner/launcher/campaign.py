"""The goal-centered campaign loop."""

from __future__ import annotations

from runner.launcher import pstext
from runner.launcher.phases import PROCEED, Phases, inquiry_cap_reached
from runner.launcher.pi_session import STOPPED
from runner.launcher.runner_client import LauncherError
from runner.launcher.summaries import campaign_resource_summary, load_state


def prepare(phases: Phases) -> None:
    """Session-backend and inquiry-cap checks before the first PI turn."""
    options = phases.options
    outcome = phases.runner.runner(
        "--validate-session-backend",
        "--backend-adapter",
        "copilot",
        "--backend-model",
        options.model,
        "--backend-reasoning",
        options.reasoning,
    )
    if outcome.exit_code != 0:
        raise LauncherError(
            "Launcher backend descriptor must match the active bounded "
            "scientific session until checkpoint."
        )
    if options.max_inquiries_explicit:
        outcome = phases.runner.runner(
            "--synchronize-max-inquiries", str(options.max_inquiries)
        )
        if outcome.exit_code != 0:
            raise LauncherError(
                "Explicit launcher MaxInquiries may change only during fresh "
                "initialization or as an increase at an inquiry-cap pause."
            )
    state = load_state(options.campaign_root)
    fresh = int((state.get("counters") or {}).get("session") or 0) == 0 and not len(
        pstext.items(state.get("operation_events"))
    )
    phases.events.status(
        f"{'START' if fresh else 'RESUME'} | goal-centered research | "
        f"{campaign_resource_summary(state, options.campaign_root)} | "
        f"inquiry cap {int((state.get('campaign') or {}).get('max_inquiries') or 0)}",
        scope="info",
    )


def step(phases: Phases) -> int | None:
    """One loop iteration; ``None`` continues, a status ends the loop."""
    state = load_state(phases.campaign_root)
    if pstext.same(pstext.field(state.get("scientific_model"), "status"), "pending"):
        phases.events.status("START | campaign preparation", scope="session")
        if phases.scientific_model(state) == STOPPED:
            return STOPPED
        phases.events.status("END | campaign preparation", scope="session")
        phases.update_brief()
        return None
    if state.get("pending_operation"):
        status = phases.pending_operation(state)
        if status == STOPPED:
            return STOPPED
        if status == 0:
            phases.update_brief()
        return None
    terminal = state.get("terminal_state")
    if terminal:
        if (
            pstext.text(pstext.field(terminal, "status"))
            .lower()
            .startswith("official_assessment_")
        ):
            return phases.official_assessment()
        return 0
    if inquiry_cap_reached(state):
        phases.events.status(
            "PAUSE | inquiry creation cap reached | scientific state preserved; no "
            "campaign conclusion | resume with an explicit higher --max-inquiries",
            scope="info",
        )
        return 0
    if not state.get("scientific_session"):
        return STOPPED if phases.start_session(state) == STOPPED else None
    phases.sessions.bind_scientific_session(state["scientific_session"])
    phases.update_brief()
    problem = ""
    if (phases.campaign_root / "pi_workspace" / "operation_request.json").is_file():
        status, problem = phases.pending_request_problem()
        if status == STOPPED:
            return STOPPED
        if status != PROCEED:
            return None
    return STOPPED if phases.scientific_session(state, problem) == STOPPED else None


def run(phases: Phases) -> int:
    """Run until the campaign pauses, concludes or stops; return the exit code."""
    prepare(phases)
    while True:
        if phases.stop.requested():
            return STOPPED
        status = step(phases)
        if status is not None:
            return STOPPED if status == STOPPED else 0
