"""Launcher channel and existing operation submission lifecycle."""

from __future__ import annotations

import asyncio
import json
import time

from runner.copilot.coding_contracts import (
    OperationSubmissionParams,
)
from runner.copilot.copilot_console import (
    Console,
)
from runner.stop_control import stop_request_path


class ControllerChannel:
    def __init__(self, reader, writer) -> None:
        self.reader = reader
        self.writer = writer

    async def send(self, message: dict) -> None:
        self.writer.write(
            (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")
        )
        await self.writer.drain()

    async def receive(self) -> dict:
        line = await self.reader.readline()
        if not line:
            raise ConnectionError(
                "Launcher channel closed; recover durable Runner state, never resubmit blindly."
            )
        message = json.loads(line)
        if not isinstance(message, dict):
            raise ValueError("Controller message must be an object.")
        return message


class OperationSubmission:
    def __init__(self, channel, binding: dict, console: Console, coding) -> None:
        self.channel = channel
        self.binding = binding
        self.console = console
        self.coding = coding
        self.state = binding["state"]
        self.busy = False
        self.closed = False
        self.status = None
        self.error = None
        self.wait_started = None
        self.responses: dict[str, str] = {}
        self.rejections = 0
        self.active_tasks: set[asyncio.Task] = set()
        self.closing = False

    def tool(self):
        from copilot import define_tool

        return define_tool(
            "submit_operation",
            description=(
                "Submit one existing typed operation envelope from contracts/instruments.md "
                "in request. Do not write pi_workspace/operation_request.json; it is internal "
                "Runner exchange. The trusted controller validates and executes it using "
                "existing Runner permissions and allocation, then returns compact factual "
                "result/errors and current state directly to this conversation. Detailed "
                "evidence remains available through artifact_evidence_query. Continue here "
                "after ordinary results or implementation_error. That status means an "
                "accepted operation failed; it is not a diagnosis of defective code. "
                "Failures are execution history, not scientific evidence. Inspect the "
                "original error and accepted invocation before deciding what to correct. "
                "Use artifact_evidence_query action=metadata with the pending operation_id "
                "and path=/pending to read its exact request and resolved measurements. "
                "Correct request arguments with a replacement envelope; use scientific_coding "
                "only for an actual source repair. request=null reaccepts the SAME request "
                "after source repair and cannot correct its arguments. Inquiry "
                "open/reframe/close requires checkpoint next. Use actual completed_operations "
                "metadata, not invented IDs; preserve your scientific content. Checkpoint "
                "or terminal commitment ends this bounded context. Do not submit again after "
                "session_ended, validation_fatal, controller_fatal, publication_fatal, "
                "recovery_required or interruption. Do not query evidence after context closure. "
                "No submission result certifies scientific validity."
            ),
            handler=self.invoke,
            params_type=OperationSubmissionParams,
            defer="never",
            skip_permission=True,
        )

    def request_stop(self) -> None:
        path = stop_request_path()
        if path is not None:
            path.write_text("Copilot operation wait interrupted.\n", encoding="utf-8")

    async def invoke(self, params: OperationSubmissionParams, invocation) -> str:
        if (
            invocation.session_id != self.binding["session_id"]
            or not invocation.tool_call_id
            or getattr(invocation, "agent_id", None) is not None
        ):
            return json.dumps(
                {"status": "rejected", "error": "Invalid SDK session binding."}
            )
        call_id = invocation.tool_call_id
        if call_id in self.responses:
            return self.responses[call_id]
        if self.busy or self.closed or (self.coding is not None and self.coding.busy):
            return json.dumps(
                {
                    "status": "rejected",
                    "error": "Another operation/coding call is active or this session has ended.",
                }
            )
        self.busy = True
        task = asyncio.current_task()
        self.active_tasks.add(task)
        self.wait_started = time.monotonic()
        try:
            await self.channel.send(
                {
                    "type": "operation",
                    "invocation_id": self.binding["invocation_id"],
                    "session_id": self.binding["session_id"],
                    "campaign_id": self.binding["campaign_id"],
                    "event_count": self.state["operation_event_count"],
                    "call_id": call_id,
                    "request": params.request,
                }
            )
            response = await self.channel.receive()
            if (
                response.get("type") != "operation_result"
                or response.get("invocation_id") != self.binding["invocation_id"]
                or response.get("call_id") != call_id
            ):
                raise ValueError(
                    "Operation response binding does not match this submission."
                )
            self.status = response["status"]
            self.error = response.get("error")
            if isinstance(response.get("state"), dict):
                self.state = response["state"]
            self.closed = self.closing or self.status not in {
                "completed",
                "rejected",
                "implementation_error",
            }
            if self.status == "rejected":
                self.rejections += 1
                if self.rejections >= 2:
                    self.closed = True
                    self.status = "validation_fatal"
                    response["status"] = self.status
            else:
                self.rejections = 0
            result = {
                key: value
                for key, value in response.items()
                if key not in {"type", "invocation_id", "call_id"}
            }
            encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
            self.responses[call_id] = encoded
            self.console.line(f"  > submit_operation: {self.status}")
            return encoded
        except asyncio.CancelledError:
            self.closed = True
            self.status = "interrupted"
            self.request_stop()
            raise
        except (OSError, ValueError) as error:
            self.closed = True
            self.status = "recovery_required"
            self.error = str(error)
            self.request_stop()
            return json.dumps({"status": self.status, "error": self.error})
        finally:
            self.console.runner_wait_seconds += time.monotonic() - self.wait_started
            self.wait_started = None
            self.busy = False
            self.active_tasks.discard(task)

    def current_wait_seconds(self) -> float:
        return self.console.runner_wait_seconds + (
            time.monotonic() - self.wait_started
            if self.wait_started is not None
            else 0.0
        )

    async def close(self) -> None:
        self.closing = True
        self.closed = True
        tasks = list(self.active_tasks)
        if tasks:
            self.request_stop()
            # Runner owns the cooperative-stop deadline and durable transaction.
            # Consume its response before the shared channel receives another command.
            await asyncio.gather(*tasks, return_exceptions=True)
