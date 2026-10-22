"""Native scientific coder and reviewer, supervised on behalf of the main PI."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import uuid

from runner import paths
from runner.copilot.coding_contracts import (
    CODER_START_CONTEXT,
    CODING_INSTRUCTIONS,
    CODING_TOOL_DESCRIPTION,
    CODING_TOOLS,
    REPAIR_INTENT,
    REVIEW_INSTRUCTIONS,
    REVIEW_REASONING,
    REVIEW_TOOLS,
    REVIEWER_START_CONTEXT,
    CodingReport,
    ReviewReport,
    ScientificCodingParams,
    load_task_context,
    normalize_model,
)
from runner.copilot.constants import (
    EXIT_INTERRUPTED,
    EXIT_OK,
    EXIT_RUNTIME_FAILURE,
    EXIT_SESSION_ERROR,
    EXIT_TIMEOUT,
    LARGE_OUTPUT_DIR,
    LARGE_OUTPUT_MAX_BYTES,
    SHUTDOWN_TIMEOUT_SECONDS,
)
from runner.copilot.copilot_console import CodingConsole, Console
from runner.copilot.opencode_provider import DEFAULT_MODEL, provider_of
from runner.copilot.path_policy import (
    CODING_PERMISSION_DENIAL,
    CODING_SCOPE_DENIAL,
    ROOT,
    coding_file_scope,
)
from runner.copilot.session_events import event_handler
from runner.copilot.source_changes import coding_changes, coding_snapshot
from runner.copilot.tool_policy import deny, scoped_tool_hook
from runner.copilot.usage import record_usage

CODER = "scientific-coder"
REVIEWER = "scientific-reviewer"
NO_CHECK_EXECUTED = "No scientific check has been executed by this tool."
TERMINAL_TASK_STATES = {"cancelled", "completed", "failed"}
CHILD_USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "aiu",
)


class ScientificCoding:
    def __init__(self, client, args, console: Console) -> None:
        self.args = args
        self.console = console
        self.active_tasks: set[asyncio.Task] = set()
        self.busy = False
        self.closed = False
        self.operations = None
        self.session = None
        self.bindings: dict[str, dict] = {}
        self.original_requests: dict[str, dict] = {}
        self.review_handles: set[str] = set()
        self.reviewers: dict[str, str] = {}
        self.review_reports: dict[str, ReviewReport] = {}
        self.permission_requests: dict[int, tuple[object, str | None, dict | None]] = {}
        self.cancellation_unconfirmed = False
        self.completed = asyncio.Event()
        self._reset_child(CODER, None, None)

    def _reset_child(self, agent: str, handle: str | None, binding: dict | None):
        """State of the one native child that may run at a time."""
        self.active_agent = agent
        self.active_handle = handle
        self.binding = binding
        self.child_console = CodingConsole()
        self.child_events = None
        self.completed.clear()
        self.stop_response = ""
        self.stop_challenges = 0
        self.child_error = None
        self.native_accounting: dict = {}
        self.child_models: set[str] = set()
        self.child_reasoning: set[str] = set()
        self.quiescent = False

    @property
    def locked(self) -> bool:
        return self.busy or self.closed

    @property
    def runner_locked(self) -> bool:
        return self.operations is not None and self.operations.locked

    @property
    def external_pi(self) -> bool:
        return provider_of(self.args.model) != "github-copilot"

    @property
    def reviewer_model(self) -> str:
        # Native children stay on Copilot when the PI uses an OpenCode route.
        return DEFAULT_MODEL if self.external_pi else normalize_model(self.args.model)

    @property
    def reviewer_reasoning(self) -> str:
        return REVIEW_REASONING

    def verify_reviewer_identity(self) -> None:
        if self.child_models != {self.reviewer_model} or self.child_reasoning != {
            self.reviewer_reasoning
        }:
            raise ValueError(
                f"Requested reviewer {self.reviewer_model!r}/"
                f"{self.reviewer_reasoning!r} "
                f"was not verified; reported models: {sorted(self.child_models)}, "
                f"reasoning: {sorted(self.child_reasoning)}."
            )

    # --- agent profiles and tool -------------------------------------------

    def agent(self) -> dict:
        agent = {
            "name": CODER,
            "description": "Bounded scientific source author.",
            "prompt": CODING_INSTRUCTIONS,
            "tools": CODING_TOOLS,
            "infer": False,
            "mcp_servers": {},
        }
        if self.external_pi:
            agent["model"] = self.reviewer_model
            agent["reasoning_effort"] = self.reviewer_reasoning
        return agent

    def reviewer_agent(self) -> dict:
        return {
            "name": REVIEWER,
            "display_name": "Scientific rubber duck",
            "description": "Read-only implementation and logic reviewer.",
            "prompt": REVIEW_INSTRUCTIONS,
            "tools": REVIEW_TOOLS,
            "model": self.reviewer_model,
            "reasoning_effort": self.reviewer_reasoning,
            "infer": False,
            "mcp_servers": {},
        }

    def tool(self):
        from copilot import define_tool

        return define_tool(
            "scientific_coding",
            description=CODING_TOOL_DESCRIPTION,
            handler=self.invoke,
            params_type=ScientificCodingParams,
            defer="auto",
            skip_permission=True,
        )

    # --- SDK hooks and events ----------------------------------------------

    def authorize_parent(self, invocation) -> None:
        if (
            invocation.session_id != self.args.session_id
            or getattr(invocation, "agent_id", None) is not None
            or self.locked
            or self.runner_locked
        ):
            raise ValueError("Only the active, unlocked main PI may use this tool.")

    def on_event(self, event) -> None:
        from copilot.session_events import (
            AssistantTurnStartData,
            AssistantUsageData,
            PermissionRequestedData,
            SubagentCompletedData,
            SubagentFailedData,
            SubagentStartedData,
        )

        data = event.data
        handle = getattr(event, "agent_id", None)
        if (
            isinstance(data, SubagentStartedData)
            and self.busy
            and data.agent_name == self.active_agent
            and self.active_handle is None
        ):
            self.active_handle = handle or data.tool_call_id
        if isinstance(data, PermissionRequestedData) and not data.resolved_by_hook:
            # SDK dispatches this event before its callback, using the same request object.
            self.permission_requests[id(data.permission_request)] = (
                data.permission_request,
                handle,
                self.binding if self.busy and handle == self.active_handle else None,
            )
        if handle is None or handle != self.active_handle or not self.busy:
            return
        if self.child_events is not None:
            self.child_events(event)
        if isinstance(data, (AssistantTurnStartData, AssistantUsageData)):
            self._observe_identity(data)
        if isinstance(data, (SubagentCompletedData, SubagentFailedData)):
            self._observe_completion(handle, data)

    def _observe_identity(self, data) -> None:
        model = getattr(data, "model", None)
        if model:
            self.child_models.add(normalize_model(model))
        reasoning = getattr(data, "reasoning_effort", None)
        if reasoning:
            self.child_reasoning.add(reasoning)

    def _observe_completion(self, handle: str, data) -> None:
        self.native_accounting = {
            "agent_id": handle,
            "scope": "native_task_lifetime",
            "model": getattr(data, "model", None),
            "duration_seconds": data.duration.total_seconds()
            if data.duration
            else None,
            "total_tokens": data.total_tokens,
            "total_tool_calls": data.total_tool_calls,
        }
        model = getattr(data, "model", None)
        if model:
            self.child_models.add(normalize_model(model))
        self.child_error = getattr(data, "error", None)
        if getattr(data, "cancelled", False):
            self.child_error = f"Native {self.active_agent} task was cancelled."
        self.completed.set()

    def pre_tool_use(self, request, invocation):
        """Native hooks identify the child in request.sessionId, not invocation."""
        try:
            if self.closed:
                return deny("This coding/PI context has ended.")
            handle = request.get("sessionId")
            if handle == self.active_handle and self.busy and self.binding is not None:
                if (
                    self.active_agent == REVIEWER
                    and request.get("toolName") not in REVIEW_TOOLS
                ):
                    return deny("The scientific reviewer is read-only.")
                return scoped_tool_hook(
                    coding_paths=frozenset(self.binding["allowed_paths"]),
                    read_paths=frozenset(self.binding["read_paths"]),
                    operations=self.operations,
                )(request, invocation)
            if handle != self.args.session_id or self.busy or self.closed:
                return deny("Unknown child or coding/Runner context is locked.")
            if request.get("toolName") == "read" and self.external_pi:
                request = {**request, "toolName": "view"}
            return scoped_tool_hook(operations=self.operations)(request, invocation)
        except Exception:  # noqa: BLE001 - SDK hook exceptions otherwise fail open
            return deny(CODING_SCOPE_DENIAL)

    def permission_scope(self, request, invocation) -> dict | None:
        record = self.permission_requests.pop(id(request), None)
        if (
            record is None
            or record[0] is not request
            or self.closed
            or not isinstance(invocation, dict)
            or invocation.get("session_id") != self.args.session_id
        ):
            raise ValueError(CODING_PERMISSION_DENIAL)
        _, handle, binding = record
        if handle is None and not self.busy:
            return None
        if (
            self.busy
            and self.binding is not None
            and handle is not None
            and handle == self.active_handle
            and binding is self.binding
        ):
            return self.binding
        raise ValueError(CODING_PERMISSION_DENIAL)

    def start_hook(self, request, invocation):
        if (
            invocation.get("session_id") != self.args.session_id
            or request.get("agentName") != self.active_agent
            or not self.busy
            or self.binding is None
        ):
            return {
                "additionalContext": "Unauthorized child: all tools are denied. Stop."
            }
        context = (
            REVIEWER_START_CONTEXT
            if self.active_agent == REVIEWER
            else CODER_START_CONTEXT
        )
        return {
            "additionalContext": context + json.dumps(self.binding, ensure_ascii=False)
        }

    def stop_hook(self, request, invocation):
        if (
            invocation.get("session_id") != self.args.session_id
            or request.get("agentId") != self.active_handle
            or not self.busy
            or self.closed
        ):
            return None
        self.stop_response = request.get("response", "")
        report_type = ReviewReport if self.active_agent == REVIEWER else CodingReport
        try:
            report_type.model_validate_json(self.stop_response)
        except (ValueError, OSError) as error:
            if self.stop_challenges < 2:
                self.stop_challenges += 1
                return {
                    "decision": "block",
                    "reason": (
                        "Engineering handoff is incomplete: "
                        + str(error)
                        + ". Return the exact JSON handoff contract. "
                        "Do not execute checks, broaden scope, make a scientific "
                        "judgment, or select a research direction."
                    ),
                }
        self.completed.set()
        return None

    # --- tool invocation: validate, code, review, package -------------------

    async def invoke(self, params: ScientificCodingParams, invocation) -> str:
        if self.locked or self.runner_locked:
            return json.dumps(
                {"status": "error", "error": "Coding is closed or already active."}
            )
        try:
            binding, context, before = await self._prepare(params, invocation)
        except (OSError, ValueError) as error:
            self.console.line(f"  > scientific_coding: rejected; {error}")
            return json.dumps({"status": "error", "error": str(error)})
        if self.locked or self.runner_locked:
            return json.dumps(
                {
                    "status": "error",
                    "error": "Coding/Runner lock changed during validation.",
                }
            )
        self.busy = True
        task = asyncio.current_task()
        self.active_tasks.add(task)
        result = {
            "status": "error",
            "review_required": True,
            "repair_history": [],
            "unchecked_scope": [NO_CHECK_EXECUTED],
        }
        request = {
            "intent": params.intent,
            **binding,
            "source_context": params.source_context,
            "task_context": context,
        }
        try:
            cancelled = await self._code_and_review(
                request, binding, params.session_handle, before, result
            )
        finally:
            self.active_tasks.discard(task)
            self.busy = self.cancellation_unconfirmed
        return self._package(result, before, cancelled)

    async def _prepare(self, params: ScientificCodingParams, invocation):
        self.authorize_parent(invocation)
        if self.session is None or not invocation.tool_call_id:
            raise ValueError("Native coding requires the bound parent SDK session.")
        await self.session.rpc.tools.initialize_and_validate()
        if self.args.preliminary:
            raise ValueError("Coding is unavailable during preliminary publication.")
        if not self.args.campaign_id:
            raise ValueError("Coding requires an explicit campaign identity.")
        uuid.UUID(self.args.campaign_id)
        binding = self.resolve_binding(params)
        if params.session_handle:
            context = self.original_requests[params.session_handle]["task_context"]
            await self._require_idle_children(params.session_handle)
        else:
            context = load_task_context(paths.HARNESS_ROOT if paths.SPLIT else ROOT)
            if params.evidence_inputs:
                from runner import repository
                from runner.artifact_evidence_query import (
                    CandidateReference,
                    recorded_artifact_structure,
                    recorded_candidate_metadata,
                )

                state = repository.load_state(allow_missing_artifact=True)
                context["evidence_inputs"] = [
                    recorded_candidate_metadata(state, reference.model_dump())
                    if isinstance(reference, CandidateReference)
                    else recorded_artifact_structure(state, reference.model_dump())
                    for reference in params.evidence_inputs
                ]
        return binding, context, coding_snapshot(frozenset(binding["allowed_paths"]))

    async def _require_idle_children(self, coder_handle: str) -> None:
        tasks = {item.id: item for item in (await self.session.rpc.tasks.list()).tasks}
        child = tasks.get(coder_handle)
        if child is None or child.status.value != "idle":
            raise ValueError(
                "Only this context's idle native child accepts corrections."
            )
        review_handle = self.reviewers.get(coder_handle)
        if review_handle is not None:
            reviewer = tasks.get(review_handle)
            if reviewer is None or reviewer.status.value != "idle":
                raise ValueError(
                    "The stored reviewer is not idle in this bounded context; "
                    "a correction cannot start a replacement review."
                )

    def resolve_binding(self, params: ScientificCodingParams) -> dict:
        previous = None
        if params.session_handle:
            previous = self.bindings.get(params.session_handle)
            if previous is None:
                raise ValueError(
                    "Unknown native coding handle in this bounded context; "
                    "a handle from another context cannot authorize a correction."
                )
        supplied = params.model_dump(
            include={"allowed_paths", "read_paths"}, exclude_none=True
        )
        scope = {**(previous or {}), **supplied}
        if "allowed_paths" not in scope:
            raise ValueError("A new coding call requires allowed_paths.")
        paths = coding_file_scope(scope["allowed_paths"], writable=True)
        reads = paths | coding_file_scope(scope.get("read_paths", []), writable=False)
        binding = {"allowed_paths": sorted(paths), "read_paths": sorted(reads)}
        if previous is not None:
            changed = [field for field in binding if binding[field] != previous[field]]
            if changed:
                raise ValueError(
                    f"Coding correction changes immutable scope fields: {changed}. "
                    "Omit scope fields to reuse the stored binding. "
                    "A new scope requires a new PI-directed call without session_handle."
                )
        return binding

    async def _code_and_review(
        self, request: dict, binding: dict, coding_handle, before, result: dict
    ) -> bool:
        """Run coder and reviewer until validation, a blocker or failure; True if cancelled."""
        paths = frozenset(binding["allowed_paths"])
        step_before = before
        pending_repair = None
        try:
            while True:
                report = await self.run_child(
                    agent=CODER,
                    prompt=json.dumps(request, ensure_ascii=False),
                    binding=binding,
                    result=result,
                    handle=coding_handle,
                )
                if pending_repair is not None:
                    pending_repair["coder_status"] = result["status"]
                if not isinstance(report, CodingReport):
                    return False
                if pending_repair is not None:
                    pending_repair["coder_summary"] = report.summary
                result["summary"] = report.summary
                result["unchecked_scope"] = [NO_CHECK_EXECUTED, *report.unchecked_scope]
                result["changes"], result["diff"] = coding_changes(step_before)
                coder_handle = result["session_handle"]
                review = await self._review(
                    report, request, binding, coder_handle, pending_repair, result
                )
                if review is None or review.validation:
                    return False
                if pending_repair is not None and not result["changes"]:
                    result.update(
                        status="needs_pi",
                        reason="The coder changed no source and review validation still failed.",
                    )
                    return False
                pending_repair = {
                    "review": review.model_dump(),
                    "coder_status": "pending",
                    "review_status": "pending",
                }
                result["repair_history"].append(pending_repair)
                request = {
                    "intent": REPAIR_INTENT,
                    "source_context": json.dumps(
                        review.model_dump(), ensure_ascii=False
                    ),
                }
                coding_handle = coder_handle
                step_before = coding_snapshot(paths)
                result["review"] = {
                    "status": "pending",
                    "mode": "correction",
                    "coding_session_handle": coder_handle,
                }
        except asyncio.CancelledError:
            result.update(
                status="cancelled",
                error="Coding/review cancelled; partial changes require PI review.",
            )
            return True
        except (OSError, ValueError) as error:
            result.update(status="error", error=f"{type(error).__name__}: {error}")
            return False
        finally:
            if (
                pending_repair is not None
                and pending_repair["coder_status"] == "pending"
            ):
                pending_repair["coder_status"] = result["status"]

    async def _review(
        self, report, request, binding, coder_handle, pending_repair, result
    ) -> ReviewReport | None:
        review_handle = self.reviewers.get(coder_handle)
        mode = "correction" if review_handle is not None else "initial"
        review = {
            "status": "error",
            "mode": mode,
            "coding_session_handle": coder_handle,
        }
        result["review"] = review
        self.console.line(
            f"  > scientific_coding: {mode} review "
            f"({self.reviewer_model}, {self.reviewer_reasoning})"
        )
        review_request = {
            "mode": mode,
            "coder_summary": report.summary,
            "coder_unchecked_scope": report.unchecked_scope,
            "changes": result["changes"],
            "diff": result["diff"],
        }
        if review_handle is None:
            review_request["request"] = self.original_requests[coder_handle]
        else:
            previous = self.review_reports.get(coder_handle)
            review_request["previous_review"] = (
                previous.model_dump() if previous is not None else None
            )
            if pending_repair is None:
                review_request["correction_intent"] = request["intent"]
                review_request["correction_context"] = request["source_context"]
        try:
            review_report = await self.run_child(
                agent=REVIEWER,
                prompt=json.dumps(review_request, ensure_ascii=False),
                binding={**binding, "allowed_paths": []},
                result=review,
                handle=review_handle,
            )
        finally:
            if (
                self.active_handle is not None
                and self.active_handle in self.review_handles
            ):
                self.reviewers[coder_handle] = self.active_handle
            if pending_repair is not None:
                pending_repair["review_status"] = review["status"]
        if isinstance(review_report, ReviewReport):
            self.review_reports[coder_handle] = review_report
            if pending_repair is not None:
                pending_repair["follow_up_review"] = review_report.model_dump()
            verdict = (
                "passed"
                if review_report.validation
                else "failed: "
                + " ".join(review_report.what_is_wrong.split())[:160]
            )
            self.console.line(f"  > scientific_coding: {mode} review {verdict}")
        if (
            not isinstance(review_report, ReviewReport)
            or review["status"] != "completed"
        ):
            result.update(
                status="error",
                error=f"Independent review did not complete: {review.get('error', review['status'])}",
            )
            return None
        return review_report

    def _package(self, result: dict, before, cancelled: bool) -> str:
        try:
            result["changes"], result["diff"] = coding_changes(before)
        except OSError as error:
            result.update(status="error", review_error=str(error), changes=[], diff="")
            result["unchecked_scope"].append(
                "Actual change review could not be collected."
            )
        encoded = json.dumps(result, ensure_ascii=False)
        if cancelled or len(encoded.encode("utf-8")) > LARGE_OUTPUT_MAX_BYTES:
            LARGE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            output = (
                LARGE_OUTPUT_DIR
                / f"coding-{result.get('session_handle')}-{uuid.uuid4()}.json"
            )
            output.write_text(encoded, encoding="utf-8")
            result.pop("diff", None)
            result["review_output_path"] = str(output)
            encoded = json.dumps(result, ensure_ascii=False)
        self.console.line(
            f"  > scientific_coding: {result['status']}; source review required"
        )
        if cancelled:
            self.console.line(
                f"  ! Coding cancelled; partial-change review: {result['review_output_path']}"
            )
            raise asyncio.CancelledError
        return encoded

    # --- one native child run ----------------------------------------------

    async def run_child(
        self,
        *,
        agent: str,
        prompt: str,
        binding: dict,
        result: dict,
        handle: str | None = None,
    ) -> CodingReport | ReviewReport | None:
        started = time.monotonic()
        self.permission_requests.clear()
        self._reset_child(agent, handle, binding)
        self.child_events = event_handler(
            self.child_console, asyncio.Event(), child_accounting=True
        )
        report = None
        exit_code = EXIT_RUNTIME_FAILURE
        cancelled = False
        try:
            await self._dispatch_child(agent, prompt, binding, handle)
            report = await self._child_report(agent, result)
            exit_code = EXIT_OK
        except asyncio.CancelledError:
            cancelled = True
            result.update(
                status="cancelled",
                error=f"{agent} cancelled; source and review require PI inspection.",
            )
            exit_code = EXIT_INTERRUPTED
        except TimeoutError:
            result.update(
                status="timeout",
                error=f"{agent} timed out; source and review require PI inspection.",
            )
            exit_code = EXIT_TIMEOUT
        except Exception as error:  # noqa: BLE001 - return partial edits, not an assurance
            result["error"] = f"{type(error).__name__}: {error}"
            exit_code = EXIT_SESSION_ERROR
        finally:
            override, interrupted = await self._quiesce(agent, result)
            exit_code = exit_code if override is None else override
            cancelled = cancelled or interrupted
            self._account_child(agent, started, exit_code, result)
        if cancelled:
            raise asyncio.CancelledError
        return report if result["status"] == "completed" else None

    async def _dispatch_child(self, agent, prompt, binding, handle) -> None:
        from copilot.generated.rpc import (
            TasksSendMessageRequest,
            TasksStartAgentRequest,
        )

        if handle:
            sent = await self.session.rpc.tasks.send_message(
                TasksSendMessageRequest(id=handle, message=prompt)
            )
            if not sent.sent:
                raise ValueError(
                    sent.error or "Native same-child correction was not delivered."
                )
        else:
            child = await self.session.rpc.tasks.start_agent(
                TasksStartAgentRequest(
                    agent_type=agent,
                    name=agent,
                    description=(
                        "Independent implementation and logic review"
                        if agent == REVIEWER
                        else "Scoped source authoring"
                    ),
                    prompt=prompt,
                )
            )
            if self.active_handle not in (None, child.agent_id):
                raise ValueError("Native child identity changed during dispatch.")
            self.active_handle = child.agent_id
        if agent == REVIEWER:
            self.review_handles.add(self.active_handle)
        else:
            self.bindings[self.active_handle] = binding
            if handle is None:
                self.original_requests[self.active_handle] = json.loads(prompt)

    async def _child_report(self, agent: str, result: dict):
        await asyncio.wait_for(self.wait_child_idle(), self.args.timeout)
        if self.child_error or self.child_console.session_error:
            raise RuntimeError(self.child_error or self.child_console.session_error)
        if agent == REVIEWER:
            self.verify_reviewer_identity()
            report = ReviewReport.model_validate_json(self.stop_response)
            result.update(report.model_dump())
        else:
            report = CodingReport.model_validate_json(self.stop_response)
        result["status"] = "completed"
        return report

    async def _quiesce(self, agent: str, result: dict) -> tuple[int | None, bool]:
        """Cancel an unsettled child; return an overriding exit code and cancellation."""
        if self.quiescent:
            return None, False
        cleanup = asyncio.create_task(self.cancel_child())
        exit_code = None
        cancelled = False
        while True:
            try:
                await asyncio.shield(cleanup)
                self.quiescent = True
                return exit_code, cancelled
            except asyncio.CancelledError:
                cancelled = True
                result.update(
                    status="cancelled",
                    error=f"{agent} cancelled; source and review require PI inspection.",
                )
                exit_code = EXIT_INTERRUPTED
                if cleanup.cancelled():
                    self.closed = True
                    self.cancellation_unconfirmed = True
                    return exit_code, cancelled
            except Exception as error:  # noqa: BLE001 - shutdown must still follow
                result.update(
                    status="error", cleanup_error=f"{type(error).__name__}: {error}"
                )
                return EXIT_RUNTIME_FAILURE, cancelled

    def _account_child(self, agent: str, started: float, exit_code: int, result: dict):
        elapsed = time.monotonic() - started
        self.console.usage.coding_duration_seconds += elapsed
        handle = self.active_handle
        usage = self.child_console.usage
        tokens = usage.tokens(copilot_billed=True)
        result["session_handle"] = handle
        self.native_accounting["agent_id"] = handle
        result["native_accounting"] = self.native_accounting
        result["actual_models"] = sorted(self.child_models)
        result["actual_reasoning_efforts"] = sorted(self.child_reasoning)
        result["usage"] = {
            "wall_duration_seconds": round(elapsed, 3),
            **{name: tokens[name] for name in CHILD_USAGE_FIELDS},
            "tool_calls": usage.tool_calls,
        }
        usage_args = self.args
        if agent == REVIEWER or self.external_pi:
            usage_args = argparse.Namespace(
                **{
                    **vars(self.args),
                    "model": self.reviewer_model,
                    "reasoning": self.reviewer_reasoning,
                    "effective_reasoning": self.reviewer_reasoning,
                    "provider_model": None,
                }
            )
        try:
            record_usage(
                usage_args,
                usage,
                elapsed,
                exit_code,
                role=agent.replace("-", "_"),
                session_id=handle,
                parent_session_id=self.args.session_id,
                actual_models=sorted(self.child_models),
                actual_reasoning_efforts=sorted(self.child_reasoning),
            )
        except (OSError, ValueError) as error:
            result["usage_error"] = str(error)
            self.console.line(f"  ! {agent} usage could not be recorded: {error}")

    async def wait_child_idle(self) -> None:
        # Stop hooks run on every correction; subagent.completed is not repeated on
        # every idle transition, so unlock only once the native task has settled.
        await self.completed.wait()
        while True:
            tasks = await self.session.rpc.tasks.list()
            child = next(
                (item for item in tasks.tasks if item.id == self.active_handle), None
            )
            if child is None:
                raise ValueError("Native coding child disappeared before its handoff.")
            if child.status.value in {"idle", *TERMINAL_TASK_STATES}:
                self.quiescent = True
                if child.status.value in {"failed", "cancelled"}:
                    raise ValueError(
                        child.error or f"Native child is {child.status.value}."
                    )
                self.native_accounting["active_time_ms"] = child.active_time_ms
                self.native_accounting["scope"] = "native_task_lifetime"
                if not self.stop_response:
                    self.stop_response = child.latest_response or child.result or ""
                return
            await asyncio.sleep(0.05)

    # --- shutdown ----------------------------------------------------------

    async def close(self) -> None:
        self.closed = True
        tasks = list(self.active_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for handle in (
            set(self.bindings)
            | self.review_handles
            | ({self.active_handle} if self.active_handle else set())
        ):
            await self.cancel_child(handle)

    async def cancel_child(self, handle: str | None = None) -> None:
        handle = handle or self.active_handle
        if self.session is None:
            return
        try:
            if handle is None:
                if self.busy:
                    await self._cancel_all_children()
                return
            await self._cancel_one_child(handle)
        except Exception:
            self.cancellation_unconfirmed = True
            self.closed = True
            if self.operations is not None:
                self.operations.closed = True
            raise

    async def _cancel_all_children(self) -> None:
        await self.session.rpc.cancel_all_background_agents(
            timeout=SHUTDOWN_TIMEOUT_SECONDS
        )
        async with asyncio.timeout(SHUTDOWN_TIMEOUT_SECONDS):
            while any(
                item.status.value == "running"
                for item in (await self.session.rpc.tasks.list()).tasks
            ):
                await asyncio.sleep(0.05)

    async def _cancel_one_child(self, handle: str) -> None:
        from copilot.generated.rpc import TasksCancelRequest

        await self.session.rpc.tasks.cancel(
            TasksCancelRequest(id=handle), timeout=SHUTDOWN_TIMEOUT_SECONDS
        )
        async with asyncio.timeout(SHUTDOWN_TIMEOUT_SECONDS):
            while True:
                tasks = await self.session.rpc.tasks.list()
                child = next((item for item in tasks.tasks if item.id == handle), None)
                if child is None or child.status.value in TERMINAL_TASK_STATES:
                    return
                await asyncio.sleep(0.05)
