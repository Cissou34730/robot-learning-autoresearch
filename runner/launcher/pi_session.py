"""Bounded PI sessions over the persistent Copilot runtime."""

from __future__ import annotations

import uuid
from pathlib import Path

from runner.launcher import pstext
from runner.launcher.copilot_runtime import CopilotRuntime
from runner.launcher.events import LauncherEvents
from runner.launcher.operation_bridge import OperationBridge, operation_state
from runner.launcher.runner_client import LauncherError
from runner.launcher.stop import StopControl
from runner.launcher.summaries import load_state
from runner.launcher.trust import TrustGuard

STOPPED = 130


class PISessions:
    """Backend session identity, invocation count and the last session outcome."""

    def __init__(
        self,
        *,
        campaign_root: Path,
        model: str,
        reasoning: str,
        runtime: CopilotRuntime,
        bridge: OperationBridge,
        trust: TrustGuard,
        stop: StopControl,
        events: LauncherEvents,
    ) -> None:
        self._campaign_root = campaign_root
        self._model = model
        self._reasoning = reasoning
        self._runtime = runtime
        self._bridge = bridge
        self._trust = trust
        self._stop = stop
        self._events = events
        self.session_id: str | None = None
        self.state_id: str | None = None
        self.invocation = 0
        self.exit_code: int | None = None
        self.outcome: dict = {}

    def forget(self) -> None:
        self.session_id = None
        self.state_id = None
        self.invocation = 0

    def close_runtime(self) -> None:
        self._runtime.stop()

    def bind_scientific_session(self, session: dict) -> None:
        """Adopt the durable session's backend identity when it changed."""
        if self.state_id != session.get("id") or self.session_id != session.get(
            "backend_session_id"
        ):
            self.state_id = session.get("id")
            self.session_id = pstext.text(session.get("backend_session_id"))
            self.invocation = 0

    def run(
        self,
        prompt: str,
        phase: str,
        *,
        resume: bool = False,
        preliminary: bool = False,
    ) -> int:
        self._trust.verify()
        self._trust.capture(preliminary=preliminary)
        self._advance_identity(resume=resume, preliminary=preliminary)
        state = load_state(self._campaign_root)
        stage = self._stage(state, phase, preliminary=preliminary)
        self._events.card(f"PI | {stage}", scope="pi")
        self._events.observe(
            "session_start",
            fields={
                "session_id": self.session_id,
                "stage": stage,
                "phase": phase,
                "resumed": resume,
                "preliminary": preliminary,
            },
        )
        self.exit_code = self._converse(
            self._arguments(state, phase, resume=resume, preliminary=preliminary),
            prompt,
            state,
            preliminary=preliminary,
        )
        return self.exit_code

    def require_success(self) -> None:
        if self.exit_code != 0:
            raise LauncherError(
                f"Copilot bounded session failed: {pstext.text(self.outcome.get('error'))}"
            )
        if self.outcome.get("status") != "session_ended":
            raise LauncherError(
                "Copilot bounded session ended without a checkpoint or terminal commitment."
            )

    def _advance_identity(self, *, resume: bool, preliminary: bool) -> None:
        if preliminary:
            if resume and not self.session_id:
                raise LauncherError(
                    "There is no active preliminary PI backend session to continue."
                )
            if resume:
                self.invocation += 1
            else:
                self.session_id = str(uuid.uuid4())
                self.invocation = 1
            return
        if not self.session_id:
            raise LauncherError(
                "The active scientific session has no persisted backend session ID."
            )
        self.invocation += 1

    @staticmethod
    def _stage(state: dict, phase: str, *, preliminary: bool) -> str:
        if preliminary:
            return "campaign preparation"
        session_id = pstext.field(state.get("scientific_session"), "id")
        if pstext.truthy(session_id):
            return f"{pstext.text(session_id)} {phase.replace('_', ' ')}"
        return phase.replace("_", " ")

    def _arguments(
        self, state: dict, phase: str, *, resume: bool, preliminary: bool
    ) -> list[str]:
        arguments = [
            "--session-id",
            self.session_id,
            "--model",
            self._model,
            "--reasoning",
            self._reasoning,
            "--phase",
            phase,
            "--attempt",
            str(self.invocation),
        ]
        campaign_id = pstext.field(state.get("campaign"), "id")
        if pstext.truthy(campaign_id):
            arguments += ["--campaign-id", pstext.text(campaign_id)]
        if preliminary and resume:
            arguments.append("--resume")
        elif not preliminary:
            arguments.append("--resume-or-create")
        if preliminary:
            arguments.append("--preliminary")
        return arguments

    def _converse(
        self, arguments: list[str], prompt: str, state: dict, *, preliminary: bool
    ) -> int:
        self._runtime.start()
        if self._stop.requested():
            return STOPPED
        binding = {
            "type": "session",
            "invocation_id": str(uuid.uuid4()),
            "session_id": self.session_id,
            "scientific_session_id": None
            if preliminary
            else pstext.field(state.get("scientific_session"), "id"),
            "campaign_id": pstext.text(pstext.field(state.get("campaign"), "id")),
            "arguments": [*arguments, prompt],
            "state": operation_state(state, self._campaign_root),
        }
        self._runtime.send(binding)
        while True:
            message = self._runtime.receive()
            if message.get("invocation_id") != binding["invocation_id"]:
                raise LauncherError(
                    "Copilot returned a message for a different logical invocation."
                )
            if message.get("type") == "session_result":
                self.outcome = message
                return int(message.get("exit_code"))
            if message.get("type") != "operation" or preliminary:
                raise LauncherError(
                    "Unexpected control message from the bounded Copilot session."
                )
            try:
                response = self._bridge.submit(message, binding)
            except Exception as error:  # noqa: BLE001 - the PI receives the controller failure
                response = {
                    "type": "operation_result",
                    "invocation_id": binding["invocation_id"],
                    "call_id": message.get("call_id"),
                    "status": "controller_fatal",
                    "error": str(error),
                }
            self._runtime.send(response)
