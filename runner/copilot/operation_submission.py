"""Launcher channel and existing operation submission lifecycle."""

from __future__ import annotations

import asyncio
import json
import time

from runner.copilot.coding_contracts import (
    OperationSubmissionParams,
)
from runner.copilot.reporting import SessionReporter
from runner.stop_control import stop_request_path

# Below the SDK's 1,800-second limit on one external tool call.
WAIT_SLICE_SECONDS = 1500.0
RUNNING_NOTICE = (
    "The accepted operation is still executing. Call submit_operation with "
    "request=null to keep waiting for its result."
)


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
                "The channel to the Runner closed. Recover the durable Runner "
                "state. Do not resubmit blindly."
            )
        message = json.loads(line)
        if not isinstance(message, dict):
            raise ValueError("Controller message must be an object.")
        return message


class OperationSubmission:
    def __init__(
        self, channel, binding: dict, console: SessionReporter, coding
    ) -> None:
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
        self.running: asyncio.Future | None = None
        self.running_call_id: str | None = None

    @property
    def locked(self) -> bool:
        return self.busy or self.closed or self.running is not None

    @property
    def awaiting_result(self) -> bool:
        return self.running is not None and not self.busy and not self.closed

    def tool(self):
        from copilot import define_tool

        return define_tool(
            "submit_operation",
            description=(
                "Submit in request one operation envelope that "
                "contracts/instruments.md defines. The files in contracts/instruments/ "
                "define the body of each operation. Do not write "
                "pi_workspace/operation_request.json: the Runner uses it internally. "
                "The Runner validates and executes the operation with its existing "
                "permissions and allocation. Then it returns a short factual result or "
                "the errors, and the current state, directly to this conversation. The "
                "detailed evidence stays available through artifact_evidence_query.\n\n"
                "Continue "
                "here after a normal result or after implementation_error. This status "
                "means that an accepted operation failed. It does not diagnose a code "
                "defect. Failures are execution history, not scientific evidence. Read "
                "the original error and the accepted invocation before you decide what to "
                "correct. Use artifact_evidence_query action=metadata with the pending "
                "operation_id and path=/pending to read its exact request and its "
                "resolved measurements.\n\n"
                "Correct request arguments with a replacement "
                "envelope. Use scientific_coding when the failure needs a source change. "
                "request=null accepts the SAME request again after a source repair. It "
                "cannot correct the arguments. status=running means that the accepted "
                "operation is still executing. Then request=null waits for its result.\n\n"
                "After "
                "an inquiry open, reframe or close, the next operation must be the "
                "checkpoint operation. Use the actual completed_operations metadata, not "
                "invented identities, and preserve your scientific content. A checkpoint "
                "operation or the request for the official assessment ends this session.\n\n"
                "Do not "
                "submit again after session_ended, validation_fatal, controller_fatal, "
                "publication_fatal, recovery_required or an interruption. Do not query "
                "evidence after the session ends. No result of a submission certifies "
                "scientific validity."
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
        resuming = self.awaiting_result
        if resuming and params.request is not None:
            return json.dumps({"status": "running", "error": RUNNING_NOTICE})
        if not resuming and (
            self.locked or (self.coding is not None and self.coding.busy)
        ):
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
            if not resuming:
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
                self.running_call_id = call_id
                self.running = asyncio.ensure_future(self.channel.receive())
            done, _ = await asyncio.wait({self.running}, timeout=WAIT_SLICE_SECONDS)
            if not done:
                self.console.operation_submitted("running")
                return json.dumps({"status": "running", "error": RUNNING_NOTICE})
            receive, self.running = self.running, None
            response = receive.result()
            if (
                response.get("type") != "operation_result"
                or response.get("invocation_id") != self.binding["invocation_id"]
                or response.get("call_id") != self.running_call_id
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
            self.console.operation_submitted(self.status, self.error)
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
            self.console.usage.runner_wait_seconds += (
                time.monotonic() - self.wait_started
            )
            self.wait_started = None
            self.busy = False
            self.active_tasks.discard(task)

    def current_wait_seconds(self) -> float:
        return self.console.usage.runner_wait_seconds + (
            time.monotonic() - self.wait_started
            if self.wait_started is not None
            else 0.0
        )

    async def close(self) -> None:
        self.closing = True
        self.closed = True
        tasks = list(self.active_tasks)
        if self.running is not None:
            tasks.append(self.running)
        if tasks:
            self.request_stop()
            # Runner owns the cooperative-stop deadline and durable transaction.
            # Consume its response before the shared channel receives another command.
            await asyncio.gather(*tasks, return_exceptions=True)
