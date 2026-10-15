"""Bounded PI contexts on a launcher-owned persistent GitHub Copilot SDK runtime.

The launcher owns the research protocol and decides whether a phase is complete;
this adapter owns only the Copilot runtime: session identity, the tool profile,
the command policy, and what reaches the console. Nothing printed here is read
back as a scientific fact.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from copilot import ToolResult

from runner.copilot.coding_contracts import (
    MAIN_PI_TOOLS,
    RESEARCH_TOOLS,
    normalize_model,
)
from runner.copilot.coding_session import (
    EXIT_INTERRUPTED,
    EXIT_OK,
    EXIT_RUNTIME_FAILURE,
    EXIT_SESSION_ERROR,
    EXIT_TIMEOUT,
    LARGE_OUTPUT_DIR,
    LARGE_OUTPUT_MAX_BYTES,
    SHUTDOWN_TIMEOUT_SECONDS,
    ScientificCoding,
    build_handlers,
    scoped_tool_hook,
)
from runner.copilot.command_policy import (  # noqa: F401 - preserve existing policy imports
    DEPENDENCY_DENIAL,
    EXECUTION_DENIAL,
    GIT_DENIAL,
    SUITE_DENIAL,
    command_denial,
    execution_target,
    shell_command_text,
)
from runner.copilot.copilot_console import (
    Console,
    record_usage,
)
from runner.copilot.operation_submission import (
    ControllerChannel,
    OperationSubmission,
)
from runner.copilot.path_policy import (  # noqa: F401 - preserve existing policy imports
    FILE_EDIT_DENIAL,
    FILE_READ_DENIAL,
    file_edit_denial,
    file_read_denial,
)
from runner.stop_control import stop_requested, wait_for_stop_request

ROOT = Path(__file__).resolve().parents[2]


EXIT_NOT_AUTHENTICATED = 3


EXIT_MODEL_UNAVAILABLE = 4


FORCE_STOP_TIMEOUT_SECONDS = 10.0


MODEL_CALL_RETRY_LIMIT = 5


MODEL_CALL_RETRY_DELAY_SECONDS = 5.0


def worktree_status() -> dict[str, str]:
    """Path to Git status, so a file written by any means is still observed.

    The runtime's own change events only cover its edit tools, and this
    researcher writes most files through the shell.
    """
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    entries = {}
    for line in completed.stdout.splitlines():
        if len(line) > 3:
            entries[line[3:].strip().strip('"')] = line[:2].strip()
    return entries


def changed_since(before: dict[str, str]) -> list[str]:
    after = worktree_status()
    return sorted(
        path for path in set(before) | set(after) if before.get(path) != after.get(path)
    )


def offload_snapshot() -> set[str]:
    if not LARGE_OUTPUT_DIR.is_dir():
        return set()
    return {entry.name for entry in LARGE_OUTPUT_DIR.iterdir() if entry.is_file()}


def offloaded_since(before: set[str]) -> tuple[int, int]:
    """How much tool output never entered the context, as count and bytes.

    Per-session cost tracks how much work the researcher chose to do, so only a
    direct measure of the mechanism can say whether offloading is doing anything.
    """
    if not LARGE_OUTPUT_DIR.is_dir():
        return (0, 0)
    written = [
        entry
        for entry in LARGE_OUTPUT_DIR.iterdir()
        if entry.is_file() and entry.name not in before
    ]
    return (len(written), sum(entry.stat().st_size for entry in written))


def session_options(
    args,
    console: Console,
    finished: asyncio.Event,
    coding=None,
    operations=None,
    client=None,
) -> dict:
    from copilot import ToolSet, define_tool
    from copilot.session_events import AssistantMessageData

    from runner.artifact_evidence_query import (
        ArtifactEvidenceQueryParams,
        query_artifact,
    )
    from runner.copilot.copilot_scoped_search import ScopedSearch
    from runner.query_training_log import TrainingLogQueryParams, query_training_log
    from runner.scientific_api_reference import (
        ScientificAPIReferenceParams,
        read_reference,
    )

    def authorize_reader(invocation) -> None:
        if (
            invocation.session_id != args.session_id
            or getattr(invocation, "agent_id", None) is not None
            or (coding is not None and (coding.busy or coding.closed))
            or (operations is not None and (operations.busy or operations.closed))
        ):
            raise ValueError("Only the active, unlocked main/preliminary PI may query.")

    model_call_retries = 0

    async def on_error_occurred(request, invocation):
        nonlocal model_call_retries
        if (
            invocation.get("session_id") != args.session_id
            or request.get("sessionId") != args.session_id
            or request.get("errorContext") != "model_call"
            or request.get("recoverable") is not True
            or (operations is not None and operations.closed)
            or (coding is not None and coding.closed)
            or stop_requested()
        ):
            return None
        error = request.get("error")
        message = error.get("message") if isinstance(error, dict) else error
        if not isinstance(message, str):
            return None
        try:
            details = json.loads(message)
        except json.JSONDecodeError:
            return None
        if not isinstance(details, dict) or (
            details.get("code") != "invalid_request_body"
            or details.get("type") != "websocket_error"
            or details.get("message") != "internal server error"
        ):
            return None
        if model_call_retries >= MODEL_CALL_RETRY_LIMIT:
            console.line(
                "  ! Copilot model request failed after five retries; stopping"
            )
            return {"errorHandling": "abort"}
        model_call_retries += 1
        console.line(
            f"  ! Copilot model request failed; retry "
            f"{model_call_retries}/{MODEL_CALL_RETRY_LIMIT} "
            f"in {MODEL_CALL_RETRY_DELAY_SECONDS:g}s"
        )
        await asyncio.sleep(MODEL_CALL_RETRY_DELAY_SECONDS)
        if (
            stop_requested()
            or (operations is not None and operations.closed)
            or (coding is not None and coding.closed)
        ):
            return {"errorHandling": "abort"}
        return {"errorHandling": "retry", "retryCount": 1}

    async def artifact_evidence_query(params, invocation) -> str:
        authorize_reader(invocation)
        return await asyncio.to_thread(
            query_artifact,
            params.model_dump(),
            campaign_id=str(args.campaign_id or ""),
        )

    artifact_evidence_tool = define_tool(
        "artifact_evidence_query",
        description=(
            "Read-only campaign-bound JSON evidence, including large measurement artifacts. "
            "Selected queries and complete byte-paged reads use this reader, not view. "
            "Provide operation identity, "
            "not a filesystem path. operations pages the operation index; metadata "
            "selects an operation's record, artifact references or checkpoint metadata "
            "without loading artifact contents. Metadata paths are /operation, /record, "
            "/artifacts/* and /checkpoints/*. For an accepted pending operation, "
            "/pending contains the exact request, resolved measurements and failure; "
            "these are execution metadata, not completed evidence. "
            "Use recorded operation_id/artifact_index "
            "as named python_module inputs instead of transcribing filenames. "
            "YOU choose full original content (action=read) "
            "or any selected subsets (query/batch path/where/select), including "
            "several distinct subsets; no summary or projection is compulsory. "
            "discover helps learn shape; aggregates are optional. Array paths expand "
            "to rows when selecting/filtering/aggregating. Missing filter fields are "
            "reported separately from zero matches. Page limits are small by default; "
            "increase limit explicitly for more rows. Set max_bytes on the request. "
            "All batch items share that selected-value budget. Query items reject max_bytes. "
            "Omit select for complete rows; a supplied pointer cannot be empty. Filtering occurs "
            "before data enters PI context. Full reads use byte offset/max_bytes, "
            "UTF-8 content or explicit base64, and fingerprint-bound continuation. "
            "query/batch raw and value_counts use offset paging after selection. "
            "Follow reported next offsets/fingerprints; report transport/traversal "
            "limits honestly and never mistake one truncated page for full retrieval."
        ),
        handler=artifact_evidence_query,
        params_type=ArtifactEvidenceQueryParams,
        defer="auto",
        skip_permission=True,
    )

    def training_log_query(params, invocation) -> str:
        authorize_reader(invocation)
        return query_training_log(
            params.model_dump(exclude_none=True),
            campaign_id=str(args.campaign_id or ""),
        )

    training_log_tool = define_tool(
        "training_log_query",
        description=(
            "Read-only training execution logs by operation_id in this campaign. "
            "Omitting action discovers attempt/step/metric metadata without log values. "
            "YOU choose detailed records, any attempt/time-step/metric subsets "
            "(action=records, attempts/from_step/to_step/metrics), or full original "
            "logs (action=raw); request several distinct subsets if useful. No "
            "forced summary. Records require exact metrics or explicit all_metrics=true; "
            "small row/byte pages are the default, not full trajectories. Filtering "
            "occurs before data enters PI context. "
            "Records have offset/limit with expected_log_fingerprints on continuation; "
            "raw pages have byte offset/max_bytes/expected_fingerprint, readable "
            "UTF-8 by default or explicit base64. Follow provenance and continuation, "
            "and report limits rather than claim incomplete transport is complete. "
            "Failed/pending-failure logs are execution history, NOT scientific evidence."
        ),
        handler=training_log_query,
        params_type=TrainingLogQueryParams,
        defer="auto",
        skip_permission=True,
    )

    async def scientific_api_reference(params, invocation) -> str | ToolResult:
        if getattr(invocation, "agent_id", None) is None:
            authorize_reader(invocation)
        elif (
            invocation.session_id != args.session_id
            or coding is None
            or not coding.busy
            or coding.closed
            or coding.binding is None
            or invocation.agent_id != coding.active_handle
            or (operations is not None and (operations.busy or operations.closed))
        ):
            raise ValueError(
                "Only the active main PI or its authorized scientific child may read APIs."
            )
        try:
            reference = await asyncio.to_thread(read_reference, params)
        except ValueError as error:
            message = str(error)
            return ToolResult(
                text_result_for_llm=json.dumps(
                    {
                        "status": "lookup_failed",
                        "library": params.library,
                        "symbol": params.symbol,
                        "error": message,
                    },
                    ensure_ascii=False,
                ),
                result_type="failure",
                error=message,
                tool_telemetry={},
            )
        return json.dumps(reference, ensure_ascii=False)

    api_reference_tool = define_tool(
        "scientific_api_reference",
        description=(
            "Read-only installed API definitions for mujoco, gymnasium or stable_baselines3. "
            "Select library and a public dotted symbol relative to that library. "
            "No filesystem paths, private attributes, arbitrary code, constructors, "
            "or scientific API calls are accepted. Imports load only the fixed library roots. "
            "action=members lists public names with optional contains filtering; "
            "offset/limit page member rows. action=definition returns installed signature, "
            "documentation, available Python source and native MuJoCo declaration; "
            "offset/max_bytes page UTF-8 definition bytes. Missing symbols and unavailable "
            "source/signatures are explicit, not guessed. Follow next_offset for complete "
            "retrieval. Main PI and its exact-scope coding/review children can use this reader. "
            "Reference availability is not proof that a production integration executes."
        ),
        handler=scientific_api_reference,
        params_type=ScientificAPIReferenceParams,
        defer="auto",
        skip_permission=True,
    )
    # The pinned SDK exposes the actual spawned runtime connection. Locate its
    # bundled rg, rather than invoking a model-controlled shell or directory search.
    runtime_path = getattr(getattr(client, "_connection", None), "path", None)
    runtime_directory = Path(runtime_path).parent if runtime_path else None
    candidates = (
        sorted(runtime_directory.glob("ripgrep\\bin\\*\\rg.exe"))
        if runtime_directory is not None
        else []
    )
    rg_path = (
        Path(shutil.which("rg")) if shutil.which("rg") else next(iter(candidates), None)
    )
    search = ScopedSearch(
        ROOT,
        lambda path: file_read_denial(path, preliminary=args.preliminary),
        rg_path,
        authorize_reader,
    )

    handle_event, on_permission_request = build_handlers(
        console,
        finished,
        preliminary=args.preliminary,
        operations=operations,
        coding=coding,
    )

    def on_event(event) -> None:
        nonlocal model_call_retries
        if (
            getattr(event, "agent_id", None) is None
            and isinstance(event.data, AssistantMessageData)
            and event.data.interaction_id is not None
        ):
            model_call_retries = 0
        handle_event(event)

    tools = [
        *search.tools(),
        artifact_evidence_tool,
        training_log_tool,
        api_reference_tool,
    ]
    available = (
        ToolSet()
        .add_builtin(
            [
                name
                for name in (RESEARCH_TOOLS if args.preliminary else MAIN_PI_TOOLS)
                if name not in {"rg", "glob"}
            ]
        )
        .add_custom("rg")
        .add_custom("glob")
        .add_custom("artifact_evidence_query")
        .add_custom("training_log_query")
        .add_custom("scientific_api_reference")
    )
    if not args.preliminary and coding is not None:
        tools.append(coding.tool())
        available.add_custom("scientific_coding")
        available.add_builtin("apply_patch")
    if not args.preliminary and operations is not None:
        tools.append(operations.tool())
        available.add_custom("submit_operation")
    options = {
        "model": normalize_model(args.model),
        "reasoning_effort": args.reasoning,
        "on_event": on_event,
        "on_permission_request": on_permission_request,
        "tools": tools,
        "available_tools": available,
        "working_directory": str(ROOT),
        "streaming": True,
        "enable_file_change_tracking": True,
        "enable_skills": False,
        "enable_session_store": False,
        "skip_embedding_retrieval": True,
        "enable_mcp_apps": False,
        "skip_custom_instructions": True,
        "enable_config_discovery": False,
        "enable_on_demand_instruction_discovery": False,
        "mcp_servers": {},
        "custom_agents": [coding.agent(), coding.reviewer_agent()]
        if coding is not None
        else [],
        "memory": {"enabled": False},
        "large_output": {
            "enabled": True,
            "max_size_bytes": LARGE_OUTPUT_MAX_BYTES,
            "output_directory": str(LARGE_OUTPUT_DIR),
        },
    }
    options["hooks"] = {
        "on_pre_tool_use": scoped_tool_hook(
            operations=operations, coding=coding, preliminary=args.preliminary
        ),
        "on_error_occurred": on_error_occurred,
    }
    if not args.preliminary:
        options["include_sub_agent_streaming_events"] = True
        options["default_agent"] = {"excluded_tools": ["apply_patch"]}
        if coding is not None:
            options["hooks"]["on_subagent_start"] = coding.start_hook
            options["hooks"]["on_subagent_stop"] = coding.stop_hook
        options["enable_file_hooks"] = False
        options["enable_host_git_operations"] = False
        options["request_extensions"] = False
    return options


async def open_session(client, args, options: dict):
    args.resumed_session = bool(args.resume)
    if args.resume:
        try:
            # The new controller has no prior tool-response cache. Never replay
            # unfinished SDK work against already advanced durable Runner state.
            return await client.resume_session(
                args.session_id, continue_pending_work=False, **options
            )
        except Exception as error:
            raise RuntimeError(
                "could not resume the persisted researcher session "
                f"{args.session_id!r}; refusing to create a replacement"
            ) from error
    if args.resume_or_create:
        metadata = await client.get_session_metadata(args.session_id)
        if metadata is not None:
            args.resumed_session = True
            return await client.resume_session(
                args.session_id, continue_pending_work=False, **options
            )
        return await client.create_session(session_id=args.session_id, **options)
    return await client.create_session(session_id=args.session_id, **options)


async def shutdown_runtime(client, session, console: Console, *, abort: bool) -> None:
    interruption = None

    async def graceful_shutdown() -> None:
        if session is not None:
            if abort:
                await session.abort()
            await session.disconnect()
        await client.stop()

    try:
        await asyncio.wait_for(graceful_shutdown(), timeout=SHUTDOWN_TIMEOUT_SECONDS)
    except TimeoutError:
        console.line(
            f"  ! Copilot shutdown timed out after {SHUTDOWN_TIMEOUT_SECONDS:g}s; "
            "forcing the adapter-owned runtime to stop"
        )
    except asyncio.CancelledError as error:
        interruption = error
        console.line(
            "  ! Copilot shutdown interrupted; "
            "forcing the adapter-owned runtime to stop"
        )
    except Exception as error:  # noqa: BLE001 - SDK cleanup needs owned-runtime recovery
        console.line(
            f"  ! Copilot shutdown failed: {error}; "
            "forcing the adapter-owned runtime to stop"
        )
    else:
        return

    try:
        await asyncio.wait_for(client.force_stop(), timeout=FORCE_STOP_TIMEOUT_SECONDS)
    except TimeoutError as error:
        raise RuntimeError(
            f"Copilot forced shutdown timed out after {FORCE_STOP_TIMEOUT_SECONDS:g}s"
        ) from error
    console.line("  ! Copilot owned runtime force-stopped; session data preserved")
    if interruption is not None:
        raise interruption


async def run(args, *, client=None, channel=None, binding=None) -> int:
    from copilot import CopilotClient

    console = getattr(args, "usage_console", None) or Console()
    finished = asyncio.Event()
    model = normalize_model(args.model)

    if stop_requested():
        return EXIT_INTERRUPTED

    owned_client = client is None
    if not args.preliminary and channel is None:
        raise ValueError(
            "Ordinary Copilot PI sessions require the trusted launcher controller."
        )
    client = client or CopilotClient(working_directory=str(ROOT))
    coding = ScientificCoding(client, args, console) if not args.preliminary else None
    operations = (
        OperationSubmission(channel, binding, console, coding)
        if not args.preliminary
        else None
    )
    if coding is not None:
        coding.operations = operations
    args.operation_submission = operations
    session = None
    abort_session = False
    try:
        if owned_client:
            await client.start()
        status = await client.get_auth_status() if owned_client else None
        if owned_client and not getattr(status, "isAuthenticated", False):
            print(
                "Copilot is not authenticated. Run `copilot` once and sign in.",
                file=sys.stderr,
            )
            return EXIT_NOT_AUTHENTICATED

        available = (
            [entry.id for entry in await client.list_models()] if owned_client else []
        )
        if owned_client and model not in available:
            print(
                f"Model '{model}' is not available to this Copilot account. "
                f"Available: {', '.join(available)}",
                file=sys.stderr,
            )
            return EXIT_MODEL_UNAVAILABLE

        session = await open_session(
            client,
            args,
            session_options(args, console, finished, coding, operations, client),
        )
        if coding is not None:
            coding.session = session
        before = worktree_status()
        before_offload = offload_snapshot()
        started = time.monotonic()
        finished_task = asyncio.create_task(finished.wait())
        stop_task = asyncio.create_task(wait_for_stop_request())

        async def active_timeout() -> None:
            while True:
                waited = (
                    operations.current_wait_seconds() if operations is not None else 0.0
                )
                if time.monotonic() - started - waited >= args.timeout:
                    return
                await asyncio.sleep(0.25)

        timeout_task = asyncio.create_task(active_timeout())
        try:
            prompt = args.prompt
            if operations is not None and args.resumed_session:
                prompt += (
                    "\n\nRecovered current Runner state (factual metadata, not new "
                    "scientific evidence). Automatic pending-work replay is disabled; "
                    "continue from this durable state, not an unfinished old tool call:\n"
                    + json.dumps(operations.state, ensure_ascii=False)
                )
            await session.send(prompt)
            for attempt in range(2):
                done, _ = await asyncio.wait(
                    (finished_task, stop_task, timeout_task),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if (
                    stop_task in done
                    or timeout_task in done
                    or args.preliminary
                    or console.session_error
                    or (operations is not None and operations.closed)
                ):
                    break
                if attempt == 0:
                    finished.clear()
                    finished_task = asyncio.create_task(finished.wait())
                    await session.send(
                        "This bounded session is still active. Continue from the actual "
                        "operation results in this conversation. Submit the next supported "
                        "action or the scientific checkpoint through submit_operation. "
                        "Current factual state: " + json.dumps(operations.state)
                    )
            if stop_task in done:
                abort_session = True
                console.line("  ! session interrupted")
                return EXIT_INTERRUPTED
            if timeout_task in done:
                abort_session = True
                console.line(f"  ! session timed out after {args.timeout}s")
                console.summary(
                    session.session_id,
                    changed_since(before),
                    offloaded_since(before_offload),
                    elapsed_seconds=time.monotonic() - started,
                )
                return EXIT_TIMEOUT
        except TimeoutError:
            abort_session = True
            console.line(f"  ! session timed out after {args.timeout}s")
            console.summary(
                session.session_id,
                changed_since(before),
                offloaded_since(before_offload),
                elapsed_seconds=time.monotonic() - started,
            )
            return EXIT_TIMEOUT
        except KeyboardInterrupt:
            abort_session = True
            console.line("  ! session interrupted")
            return EXIT_INTERRUPTED
        except asyncio.CancelledError:
            abort_session = True
            raise
        finally:
            finished_task.cancel()
            stop_task.cancel()
            timeout_task.cancel()
            await asyncio.gather(
                finished_task, stop_task, timeout_task, return_exceptions=True
            )

        console.summary(
            session.session_id,
            changed_since(before),
            offloaded_since(before_offload),
            elapsed_seconds=time.monotonic() - started,
        )
        if operations is not None and operations.status != "session_ended":
            return EXIT_SESSION_ERROR
        return EXIT_SESSION_ERROR if console.session_error else EXIT_OK
    finally:
        try:
            if operations is not None:
                await operations.close()
            if coding is not None:
                await coding.close()
        finally:
            if owned_client:
                await shutdown_runtime(client, session, console, abort=abort_session)
            elif session is not None:
                if abort_session:
                    await asyncio.wait_for(session.abort(), SHUTDOWN_TIMEOUT_SECONDS)
                await asyncio.wait_for(session.disconnect(), SHUTDOWN_TIMEOUT_SECONDS)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", nargs="?")
    parser.add_argument("--session-id")
    parser.add_argument("--controller-port", type=int)
    parser.add_argument("--controller-token")
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument(
        "--reasoning", default="high", choices=["low", "medium", "high", "xhigh", "max"]
    )
    # Continuation is explicit: a retry resumes this phase's own session and can
    # never inherit whatever session happened to run last on this machine.
    continuation = parser.add_mutually_exclusive_group()
    continuation.add_argument("--resume", action="store_true")
    continuation.add_argument("--resume-or-create", action="store_true")
    parser.add_argument("--timeout", type=float, default=900.0)
    # Accounting metadata only; these values never enter the model prompt.
    parser.add_argument("--campaign-id")
    parser.add_argument("--phase")
    parser.add_argument("--preliminary", action="store_true")
    parser.add_argument("--attempt", type=int, default=1)
    args = parser.parse_args(argv)
    if args.controller_port:
        if not args.controller_token or args.session_id or args.prompt:
            parser.error(
                "controller mode requires a token and no direct session/prompt"
            )
    elif not args.session_id or args.prompt is None:
        parser.error("a bounded invocation requires session-id and prompt")
    return args


def console_label(args) -> str:
    """The bounded phase a session belongs to, for the console only."""
    return str(args.phase or "")


async def serve(args) -> int:
    from copilot import CopilotClient

    reader, writer = await asyncio.open_connection(
        "127.0.0.1", args.controller_port, limit=4 * 1024 * 1024
    )
    channel = ControllerChannel(reader, writer)
    client = CopilotClient(working_directory=str(ROOT))
    console = Console()
    try:
        await client.start()
        status = await client.get_auth_status()
        if not getattr(status, "isAuthenticated", False):
            raise RuntimeError("Copilot is not authenticated.")
        available = [entry.id for entry in await client.list_models()]
        if normalize_model(args.model) not in available:
            raise RuntimeError(f"Configured model {args.model!r} is unavailable.")
        await channel.send({"type": "ready", "token": args.controller_token})
        while not stop_requested():
            command = await channel.receive()
            if command.get("type") == "shutdown":
                break
            if command.get("type") != "session":
                raise ValueError("Unexpected controller command.")
            invocation_args = parse_args(command["arguments"])
            if (
                invocation_args.session_id != command["session_id"]
                or invocation_args.campaign_id != command["campaign_id"]
                or normalize_model(invocation_args.model) != normalize_model(args.model)
                or invocation_args.reasoning != args.reasoning
            ):
                raise ValueError(
                    "Controller invocation binding/configuration mismatch."
                )
            invocation_args.usage_console = Console(console_label(invocation_args))
            started = time.monotonic()
            exit_code = EXIT_RUNTIME_FAILURE
            error = None
            try:
                exit_code = await run(
                    invocation_args, client=client, channel=channel, binding=command
                )
            except Exception as exc:  # noqa: BLE001 - preserve bounded runtime failure
                error = f"{type(exc).__name__}: {exc}"
            finally:
                try:
                    record_usage(
                        invocation_args,
                        invocation_args.usage_console,
                        time.monotonic() - started,
                        exit_code,
                    )
                except (OSError, ValueError) as exc:
                    print(
                        f"Session usage could not be recorded: {exc}", file=sys.stderr
                    )
            operations = getattr(invocation_args, "operation_submission", None)
            outcome_status = (
                operations.status if operations is not None else "preliminary"
            )
            outcome_error = (
                error
                or (operations.error if operations is not None else None)
                or invocation_args.usage_console.session_error
            )
            if exit_code == EXIT_TIMEOUT:
                outcome_status = "controller_fatal"
                outcome_error = f"Copilot bounded session timed out after {invocation_args.timeout}s."
            elif exit_code == EXIT_INTERRUPTED:
                outcome_status = "interrupted"
                outcome_error = "Copilot bounded session interrupted."
            elif exit_code != EXIT_OK and outcome_status in {
                None,
                "preliminary",
                "completed",
                "rejected",
                "implementation_error",
                "session_ended",
            }:
                outcome_status = "controller_fatal"
                outcome_error = outcome_error or (
                    f"Copilot bounded session exited with code {exit_code} "
                    "without a successful session outcome."
                )
            await channel.send(
                {
                    "type": "session_result",
                    "invocation_id": command["invocation_id"],
                    "exit_code": exit_code,
                    "status": outcome_status,
                    "error": outcome_error,
                }
            )
            if exit_code not in {EXIT_OK, EXIT_SESSION_ERROR}:
                break
        return EXIT_OK
    finally:
        try:
            await shutdown_runtime(client, None, console, abort=False)
        finally:
            writer.close()
            await writer.wait_closed()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.usage_console = Console(console_label(args))
    started = time.monotonic()
    exit_code = EXIT_RUNTIME_FAILURE
    try:
        exit_code = asyncio.run(serve(args) if args.controller_port else run(args))
    except KeyboardInterrupt:
        exit_code = EXIT_INTERRUPTED
    except Exception as error:  # noqa: BLE001 - the launcher needs a code, not a traceback
        print(f"Copilot runtime failure: {error}", file=sys.stderr)
    finally:
        try:
            record_usage(
                args, args.usage_console, time.monotonic() - started, exit_code
            )
        except (OSError, ValueError) as error:
            # Accounting failure must not invalidate a scientific deliverable.
            print(f"Session usage could not be recorded: {error}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
