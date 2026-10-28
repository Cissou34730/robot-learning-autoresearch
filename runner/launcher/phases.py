"""Campaign phases between the launcher loop and the PI and Runner."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from runner import protocol
from runner.launcher import prompts, pstext
from runner.launcher.events import LauncherEvents
from runner.launcher.options import LaunchOptions
from runner.launcher.pi_session import STOPPED, PISessions
from runner.launcher.runner_client import LauncherError, RunnerClient
from runner.launcher.stop import StopControl
from runner.launcher.summaries import human_goal_summary, load_state

FAILED = 1
PROCEED = -1


@dataclass
class Phases:
    """One method per campaign phase; each returns 0, 1 or ``STOPPED``."""

    options: LaunchOptions
    runner: RunnerClient
    sessions: PISessions
    stop: StopControl
    events: LauncherEvents
    home: Path

    @property
    def campaign_root(self) -> Path:
        return self.options.campaign_root

    def stopped_after(self, exit_code: int | None, operation: str) -> bool:
        """After a child returns, a pending stop request ends the loop cooperatively."""
        if not self.stop.requested():
            return False
        if exit_code is None or exit_code not in {0, STOPPED}:
            raise LauncherError(
                f"{operation} exited with code {'' if exit_code is None else exit_code} "
                "instead of completing cooperatively after the stop request."
            )
        return True

    def update_brief(self) -> None:
        self.runner.build_brief()

    def scientific_model_feedback(self) -> str:
        outcome = self.runner.runner(
            "--check-scientific-model-deliverable", refresh_trust=False
        )
        return "" if outcome.exit_code == 0 else _joined(outcome.validation_message)

    def scientific_model(self, state: dict) -> int:
        goal = human_goal_summary(state, self.options.harness_root)
        self.sessions.forget()
        self.sessions.run(
            prompts.scientific_model_prompt(goal), "scientific model", preliminary=True
        )
        if self.stopped_after(self.sessions.exit_code, "PI session"):
            return STOPPED
        feedback = self.scientific_model_feedback()
        if feedback:
            self.sessions.run(
                prompts.scientific_model_retry_prompt(goal, feedback),
                "scientific model",
                resume=True,
                preliminary=True,
            )
            if self.stopped_after(self.sessions.exit_code, "PI session"):
                return STOPPED
            feedback = self.scientific_model_feedback()
            if feedback:
                raise LauncherError(
                    f"PI ended twice without a valid scientific model: {feedback}"
                )
        outcome = self.runner.runner("--mark-scientific-model-ready")
        if self.stopped_after(outcome.exit_code, "research runner"):
            return STOPPED
        if outcome.exit_code != 0:
            raise LauncherError(
                "The Runner could not publish the validated scientific model."
            )
        self.sessions.forget()
        return 0

    def session_prompt(self, state: dict, *, validation_error: str = "") -> str:
        session = state.get("scientific_session") or {}
        backend = session.get("backend_session_id")
        context = prompts.PromptContext(
            harness_root=self.options.harness_root,
            campaign_root=self.campaign_root,
            timesteps=self.options.timesteps,
            max_timesteps=self.options.max_timesteps,
            conversation_exists=self.sessions.invocation > 0
            or (
                pstext.truthy(backend)
                and (
                    self.home / ".copilot" / "session-state" / pstext.text(backend)
                ).exists()
            ),
        )
        prompt = prompts.scientific_session_prompt(
            state,
            protocol.session_operation_availability(state),
            context,
            validation_error=validation_error,
        )
        if prompt.context_note:
            self.events.status(
                prompt.context_note,
                scope="session",
                session_id=pstext.text(session.get("id")),
            )
        return prompt.text

    def pending_operation(self, state: dict) -> int:
        pending = state["pending_operation"]
        require_publication_recovered(state)
        if pending.get("failure"):
            return self._repair(state, pending)
        outcome = self.runner.runner("--execute-pending")
        if self.stopped_after(outcome.exit_code, "research runner"):
            return STOPPED
        if outcome.exit_code != 0:
            failed = load_state(self.campaign_root)
            require_publication_recovered(failed)
            if pstext.field(failed.get("pending_operation"), "failure"):
                return FAILED
            raise LauncherError(
                "The pending Runner operation failed without a recoverable transaction."
            )
        return 0

    def _repair(self, state: dict, pending: dict) -> int:
        self.update_brief()
        session = state.get("scientific_session")
        if not session or session.get("id") != pending.get("session_id"):
            raise LauncherError(
                "The failed operation has no matching active scientific session."
            )
        self.sessions.state_id = session.get("id")
        self.sessions.session_id = pstext.text(session.get("backend_session_id"))
        self.sessions.invocation = 0
        prompt = prompts.repair_prompt(self.session_prompt(state), pending)
        self.sessions.run(prompt, session["kind"])
        if self.stopped_after(self.sessions.exit_code, "PI session"):
            return STOPPED
        self.sessions.require_success()
        return 0

    def official_assessment(self) -> int:
        outcome = self.runner.runner("--run-official-assessment")
        if self.stopped_after(outcome.exit_code, "research runner"):
            return STOPPED
        if outcome.exit_code != 0:
            raise LauncherError(
                "The official assessment failed; its request remains durable."
            )
        self.update_brief()
        return 0

    def start_session(self, state: dict) -> int:
        kind = session_kind(state)
        arguments = [
            "--start-session",
            kind,
            "--session-objective",
            session_objective(kind, state),
            "--backend-session-id",
            str(uuid.uuid4()),
            "--backend-adapter",
            "copilot",
            "--backend-model",
            self.options.model,
            "--backend-reasoning",
            self.options.reasoning,
        ]
        if self.options.max_inquiries_explicit:
            arguments += ["--max-inquiries", str(self.options.max_inquiries)]
        outcome = self.runner.runner(*arguments)
        if self.stopped_after(outcome.exit_code, "research runner"):
            return STOPPED
        if outcome.exit_code != 0:
            raise LauncherError("The Runner could not start a bounded PI session.")
        self.sessions.forget()
        self.update_brief()
        return 0

    def pending_request_problem(self) -> tuple[int, str]:
        """Execute a request the PI left behind; ``PROCEED`` carries its validation text."""
        outcome = self.runner.runner()
        if self.stopped_after(outcome.exit_code, "research runner"):
            return STOPPED, ""
        if outcome.exit_code == 0:
            self.update_brief()
            return 0, ""
        failed = load_state(self.campaign_root)
        require_publication_recovered(failed)
        if pstext.field(failed.get("pending_operation"), "failure"):
            return FAILED, ""
        check = self.runner.runner("--check-operation", refresh_trust=False)
        problem = _joined(check.validation_message)
        if check.exit_code != 0:
            reason = problem.removeprefix("OPERATION_INVALID:").lstrip()
            self.events.card(
                "OPERATION INVALID",
                scope="error",
                lines=(reason,),
                session_id=pstext.text(
                    pstext.field(failed.get("scientific_session"), "id")
                ),
            )
        return PROCEED, problem

    def scientific_session(self, state: dict, validation_error: str) -> int:
        session = state["scientific_session"]
        prompt = self.session_prompt(state, validation_error=validation_error)
        self.sessions.run(
            prompt, session["kind"], resume=bool(self.sessions.session_id)
        )
        if self.stopped_after(self.sessions.exit_code, "PI session"):
            return STOPPED
        self.sessions.require_success()
        return 0


def _joined(message: str) -> str:
    """The launcher joined captured lines with single spaces."""
    return " ".join(line.strip() for line in message.splitlines())


def require_publication_recovered(state: dict) -> None:
    pending = state.get("pending_operation")
    if pending and pending.get("progress") in {"result_ready", "completed"}:
        raise LauncherError(
            f"Execution completed for {pstext.text(pending.get('id'))}, but publication failed. "
            "Its artifacts and pending transaction are preserved. Correct the "
            "publication error, then resume this campaign; do not reaccept "
            "the operation or retrain."
        )


def session_kind(state: dict) -> str:
    if pstext.truthy(state.get("active_inquiry")):
        return "inquiry"
    counters = state.get("counters") or {}
    if int(counters.get("session") or 0) == 0 and state.get("pi_checkpoint") is None:
        return "startup"
    return "goal_review"


def session_objective(kind: str, state: dict) -> str:
    if kind == "startup":
        return prompts.STARTUP_OBJECTIVE
    if kind == "goal_review":
        return prompts.GOAL_REVIEW_OBJECTIVE
    return prompts.inquiry_objective(pstext.field(state.get("active_inquiry"), "id"))


def inquiry_cap_reached(state: dict) -> bool:
    campaign = state.get("campaign") or {}
    counters = state.get("counters") or {}
    return (
        not state.get("scientific_session")
        and not state.get("active_inquiry")
        and not state.get("pending_operation")
        and not state.get("terminal_state")
        and int(counters.get("inquiry") or 0) >= int(campaign.get("max_inquiries") or 0)
    )
