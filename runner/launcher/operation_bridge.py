"""Operation submissions from a PI session, validated and executed by the Runner."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from runner import protocol
from runner.launcher import pstext
from runner.launcher.runner_client import PUBLICATION_FAILURE_EXIT_CODE, RunnerClient
from runner.launcher.stop import StopControl
from runner.launcher.summaries import (
    campaign_resource_summary,
    latest_session_result,
    load_state,
)
from runner.launcher.trust import TrustGuard

_SETTLED_PROGRESS = ("result_ready", "completed")


def operation_state(state: dict, campaign_root: Path) -> dict:
    """The factual state returned to the PI with each submission result."""
    session = state.get("scientific_session")
    availability = protocol.session_operation_availability(state)
    pending = state.get("pending_operation")
    return {
        "campaign_id": pstext.text(pstext.field(state.get("campaign"), "id")),
        "session_id": pstext.text(session.get("id")) if session else None,
        "backend_session_id": pstext.text(session.get("backend_session_id"))
        if session
        else None,
        "session_kind": pstext.text(session.get("kind")) if session else None,
        "operation_event_count": len(pstext.items(state.get("operation_events"))),
        "completed_operations": list(session.get("operation_ids") or [])
        if session
        else [],
        "allowed_operations": list(availability["allowed_operations"]),
        "checkpoint_required": bool(availability["checkpoint_required"]),
        "transition": availability["checkpoint_reason"],
        "next_question": availability["next_question"],
        "model_roles": state.get("model_roles"),
        "pending": (
            {
                "id": pending.get("id"),
                "progress": pending.get("progress"),
                "failure": pending.get("failure"),
                "request_fingerprint": pending.get("request_fingerprint"),
                "metadata_path": "/pending",
            }
            if pending
            else None
        ),
        "terminal": state.get("terminal_state"),
        "resources": campaign_resource_summary(state, campaign_root),
        "brief": "campaigns/brief.md",
    }


class OperationBridge:
    """Turns one bound ``operation`` message into one ``operation_result``."""

    def __init__(
        self,
        *,
        campaign_root: Path,
        runner: RunnerClient,
        trust: TrustGuard,
        stop: StopControl,
        update_brief: Callable[[], None],
    ) -> None:
        self._campaign_root = campaign_root
        self._runner = runner
        self._trust = trust
        self._stop = stop
        self._update_brief = update_brief

    def submit(self, message: dict, binding: dict) -> dict:
        self._trust.verify()
        state = load_state(self._campaign_root)
        response = {
            "type": "operation_result",
            "invocation_id": binding["invocation_id"],
            "call_id": message.get("call_id"),
            "status": "rejected",
            "error": None,
            "state": operation_state(state, self._campaign_root),
        }
        refusal = self._refusal(message, binding, state)
        if refusal is not None:
            response["status"], response["error"] = refusal
            return response
        payload = json.dumps(
            message.get("request"), ensure_ascii=False, separators=(",", ":")
        )
        check = self._runner.runner("--check-operation-input", input_text=payload)
        validation = check.validation_message
        if self._stop.requested():
            response["status"], response["error"] = "interrupted", validation
            return response
        if check.exit_code != 0:
            response["error"] = validation
            return response
        outcome = self._execute(message.get("request"), payload)
        return self._settle(response, state, outcome)

    def _refusal(
        self, message: dict, binding: dict, state: dict
    ) -> tuple[str, str] | None:
        if self._stop.requested():
            return "interrupted", "Campaign stop requested."
        session = state.get("scientific_session")
        if (
            message.get("invocation_id") != binding["invocation_id"]
            or message.get("session_id") != binding["session_id"]
            or message.get("campaign_id") != binding["campaign_id"]
            or pstext.field(state.get("campaign"), "id") != binding["campaign_id"]
            or not session
            or session.get("backend_session_id") != binding["session_id"]
            or session.get("id") != binding["scientific_session_id"]
            or state.get("terminal_state")
        ):
            return (
                "session_ended",
                "Submission does not belong to the active bounded session.",
            )
        if message.get("event_count") != len(
            pstext.items(state.get("operation_events"))
        ):
            return (
                "recovery_required",
                "Runner state changed; recover durable state before submitting again.",
            )
        pending = state.get("pending_operation")
        if pending and (
            not pending.get("failure") or pending.get("progress") in _SETTLED_PROGRESS
        ):
            return (
                "recovery_required",
                "Accepted transaction requires controller recovery, not another submission.",
            )
        return None

    def _execute(self, request: object, payload: str):
        if request is None:
            outcome = self._runner.runner("--reaccept-pending")
            if outcome.exit_code == 0:
                outcome = self._runner.runner("--execute-pending")
            return outcome
        self._trust.verify()
        request_path = self._campaign_root / "pi_workspace" / "operation_request.json"
        request_path.write_bytes(payload.encode("utf-8"))
        return self._runner.runner()

    def _settle(self, response: dict, before: dict, outcome) -> dict:
        current = load_state(self._campaign_root)
        response["state"] = operation_state(current, self._campaign_root)
        previous = len(pstext.items(before.get("operation_events")))
        new_completed = [
            event
            for event in (current.get("operation_events") or [])[previous:]
            if pstext.same(pstext.field(event, "status"), "completed")
        ]
        pending = current.get("pending_operation")
        response["operation_id"] = (
            pending.get("id")
            if pending
            else new_completed[-1].get("id")
            if new_completed
            else None
        )
        failure = pending.get("failure") if pending else None
        if (
            outcome.exit_code == PUBLICATION_FAILURE_EXIT_CODE
            or (pending and pending.get("progress") in _SETTLED_PROGRESS)
            or (outcome.exit_code != 0 and new_completed)
        ):
            response["status"], response["error"] = (
                "publication_fatal",
                outcome.submission_error(),
            )
        elif self._stop.requested():
            response["status"] = "interrupted"
            response["error"] = (
                "Runner interrupted; its pending/completed transaction is preserved."
            )
        elif outcome.exit_code != 0:
            self._record_failure(response, pending, failure, outcome)
        else:
            self._update_brief()
            ended = not current.get("scientific_session") or current.get(
                "terminal_state"
            )
            response["status"] = "session_ended" if ended else "completed"
            response["result"] = latest_session_result(current)
        return response

    def _record_failure(
        self, response: dict, pending: dict | None, failure, outcome
    ) -> None:
        if not failure:
            response["status"], response["error"] = (
                "controller_fatal",
                outcome.submission_error(),
            )
            return
        response["status"], response["error"] = (
            "implementation_error",
            pstext.text(failure),
        )
        measurements = pstext.items(
            pstext.field(pstext.field(pending, "data"), "measurements")
        )
        completed = len(
            pstext.items(pstext.field(pstext.field(pending, "data"), "partial_results"))
        )
        if pstext.same(pending.get("kind"), "measurement") and completed < len(
            measurements
        ):
            response["accepted_measurement"] = measurements[completed]
        self._update_brief()
