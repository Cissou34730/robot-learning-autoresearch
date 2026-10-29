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
import os
import subprocess
import time

from runner import typed_events
from runner.copilot.coding_contracts import (
    MAIN_PI_TOOLS,
    RESEARCH_TOOLS,
    normalize_model,
)
from runner.copilot.coding_session import ScientificCoding
from runner.copilot.constants import (
    EXIT_INTERRUPTED,
    EXIT_MODEL_UNAVAILABLE,
    EXIT_NOT_AUTHENTICATED,
    EXIT_OK,
    EXIT_RUNTIME_FAILURE,
    EXIT_SESSION_ERROR,
    EXIT_TIMEOUT,
    FORCE_STOP_TIMEOUT_SECONDS,
    LARGE_OUTPUT_DIR,
    LARGE_OUTPUT_MAX_BYTES,
    SHUTDOWN_TIMEOUT_SECONDS,
)
from runner.copilot.opencode_provider import (
    DEFAULT_MODEL,
    PROVIDERS,
    api_key,
    load_catalog,
    project_id,
    provider_of,
    resolve_model,
    select_model,
    session_identity,
)
from runner.copilot.operation_submission import (
    ControllerChannel,
    OperationSubmission,
)
from runner.copilot.path_policy import ROOT
from runner.copilot.pi_tools import (
    evidence_tools,
    read_tool,
    reader_guard,
    scoped_search,
)
from runner.copilot.reporting import SessionReporter
from runner.copilot.session_events import (
    ModelCallRetry,
    event_handler,
    permission_handler,
)
from runner.copilot.system_prompt import system_message
from runner.copilot.tool_policy import scoped_tool_hook
from runner.copilot.usage import record_usage
from runner.event_contract import PREPARATION_SESSION
from runner.stop_control import stop_requested, wait_for_stop_request

# The scientific-model analysis runs on its own Copilot model; PI sessions keep the launcher's.
# Maintainer-only environment overrides allow a model comparison of the analysis.
ANALYST_MODEL = os.environ.get("ROBOT_LEARNING_ANALYST_MODEL", "gpt-6.1-terra")
ANALYST_REASONING = os.environ.get("ROBOT_LEARNING_ANALYST_REASONING", "medium")

RESUMED_STATE_PROMPT = (
    "\n\nRecovered current Runner state (factual metadata, not new "
    "scientific evidence). Automatic pending-work replay is disabled; "
    "continue from this durable state, not an unfinished old tool call:\n"
)

CONTINUE_PROMPT = (
    "This session is still active. Continue from the actual "
    "operation results in this conversation. Submit the next supported "
    "operation or the checkpoint operation through submit_operation. "
    "Current factual state: "
)

# Session statuses that do not by themselves explain a nonzero exit code.
UNEXPLAINED_EXIT_STATUSES = {
    None,
    "preliminary",
    "completed",
    "rejected",
    "implementation_error",
    "session_ended",
}


def worktree_status() -> dict[str, str]:
    """Path to Git status, so a file written by any means is still observed."""
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


# --- session configuration -------------------------------------------------


def session_options(
    args,
    console: SessionReporter,
    finished: asyncio.Event,
    coding=None,
    operations=None,
    client=None,
) -> dict:
    from copilot import ToolSet

    external = getattr(args, "provider_model", None)
    authorize = reader_guard(args, coding, operations)
    search = scoped_search(args, client, authorize)
    retry = ModelCallRetry(args.session_id, console, coding, operations)
    handle_event = event_handler(console, finished, coding=coding)

    def on_event(event) -> None:
        retry.reset_after(event)
        handle_event(event)

    builtin = RESEARCH_TOOLS if args.preliminary else MAIN_PI_TOOLS
    tools = [*search.tools(), *evidence_tools(args, authorize, coding, operations)]
    available = (
        ToolSet()
        .add_builtin([name for name in builtin if name not in {"rg", "glob"}])
        .add_custom("rg")
        .add_custom("glob")
        .add_custom("artifact_evidence_query")
        .add_custom("training_log_query")
        .add_custom("training_series_statistics")
        .add_custom("success_rate_pass_probability")
        .add_custom("episode_outcome_breakdown")
        .add_custom("scientific_api_reference")
    )
    if external is not None:
        tools.append(read_tool(args, search, coding, operations))
        available.add_custom("read")
        if args.preliminary:
            # Non-GPT routes may not drive freeform patches for the model document.
            available.add_builtin(["create", "edit"])
    if not args.preliminary and coding is not None:
        tools.append(coding.tool())
        available.add_custom("scientific_coding")
        available.add_builtin("apply_patch")
    if not args.preliminary and operations is not None:
        tools.append(operations.tool())
        available.add_custom("submit_operation")
    options = {
        "model": normalize_model(args.model),
        "reasoning_effort": getattr(args, "effective_reasoning", args.reasoning),
        "on_event": on_event,
        "on_permission_request": permission_handler(
            console,
            preliminary=args.preliminary,
            operations=operations,
            coding=coding,
        ),
        "tools": tools,
        "available_tools": available,
        "system_message": system_message(args.preliminary, console.warning),
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
        "hooks": {
            "on_pre_tool_use": scoped_tool_hook(
                operations=operations,
                coding=coding,
                preliminary=args.preliminary,
                read_alias=external is not None,
                json_editors=external is not None,
            ),
            "on_error_occurred": retry.on_error_occurred,
        },
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
    if external is not None:
        options.update(
            external.session_options(
                args.provider_identity, api_key(), args.provider_project
            )
        )
    return options


# --- inference provider and Copilot access ---------------------------------


async def prepare_provider(args) -> None:
    if provider_of(args.model) == "github-copilot":
        return
    if getattr(args, "provider_model", None) is None:
        catalog = await asyncio.to_thread(load_catalog)
        args.provider_model = resolve_model(args.model, catalog)
        args.provider_project = await asyncio.to_thread(project_id)
    api_key()
    args.effective_reasoning = args.reasoning if args.provider_model.reasoning else None


def required_copilot_model(args) -> str | None:
    """The Copilot model this session needs; native children always run on Copilot."""
    if provider_of(args.model) == "github-copilot":
        return normalize_model(args.model)
    return None if args.preliminary else DEFAULT_MODEL


async def copilot_access_failure(client, required: str | None):
    """Return (exit code, message) when Copilot cannot serve `required`."""
    if required is None:
        return None
    status = await client.get_auth_status()
    if not getattr(status, "isAuthenticated", False):
        return (
            EXIT_NOT_AUTHENTICATED,
            "Copilot is not authenticated. Run `copilot` once and sign in.",
        )
    available = [entry.id for entry in await client.list_models()]
    if required not in available:
        return (
            EXIT_MODEL_UNAVAILABLE,
            (
                f"Model '{required}' is not available to this Copilot account. "
                f"Available: {', '.join(available)}"
            ),
        )
    return None


async def list_model_choices(args) -> int:
    if args.provider in (None, "github-copilot"):
        from copilot import CopilotClient

        client = CopilotClient(working_directory=str(ROOT))
        try:
            await client.start()
            status = await client.get_auth_status()
            if not getattr(status, "isAuthenticated", False):
                raise RuntimeError("Sign in to Copilot to list its available models.")
            for model in await client.list_models():
                print(f"github-copilot/{model.id}")
        finally:
            await client.stop()
    if args.provider != "github-copilot":
        catalog = await asyncio.to_thread(load_catalog)
        for provider, entry in catalog.items():
            if args.provider is not None and provider != args.provider:
                continue
            for model_id, model in sorted(entry["models"].items()):
                selection = f"{provider}/{model_id}"
                cost = model.get("cost", {})
                try:
                    resolve_model(selection, catalog)
                    note = (
                        "free"
                        if cost.get("input") == 0 and cost.get("output") == 0
                        else ""
                    )
                except (TypeError, ValueError) as error:
                    note = str(error)
                print(f"{selection}" + (f"\t{note}" if note else ""))
    return EXIT_OK


# --- one bounded session ---------------------------------------------------


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


async def assign_provider_identity(client, args) -> None:
    if getattr(args, "provider_model", None) is None:
        return
    existing = args.resume
    if args.resume_or_create:
        existing = await client.get_session_metadata(args.session_id) is not None
    args.provider_identity = session_identity(
        args.session_id, args.model, resume=existing
    )


async def shutdown_runtime(
    client, session, console: SessionReporter, *, abort: bool
) -> None:
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
        console.warning(
            f"Copilot shutdown timed out after {SHUTDOWN_TIMEOUT_SECONDS:g}s; "
            "forcing the adapter-owned runtime to stop",
            code="copilot_shutdown_timeout",
        )
    except asyncio.CancelledError as error:
        interruption = error
        console.warning(
            "Copilot shutdown interrupted; forcing the adapter-owned runtime to stop",
            code="copilot_shutdown_interrupted",
        )
    except Exception as error:  # noqa: BLE001 - SDK cleanup needs owned-runtime recovery
        console.warning(
            f"Copilot shutdown failed: {error}; "
            "forcing the adapter-owned runtime to stop",
            code="copilot_shutdown_failed",
        )
    else:
        return

    try:
        await asyncio.wait_for(client.force_stop(), timeout=FORCE_STOP_TIMEOUT_SECONDS)
    except TimeoutError as error:
        raise RuntimeError(
            f"Copilot forced shutdown timed out after {FORCE_STOP_TIMEOUT_SECONDS:g}s"
        ) from error
    console.warning(
        "Copilot owned runtime force-stopped; session data preserved",
        code="copilot_force_stopped",
    )
    if interruption is not None:
        raise interruption


async def active_timeout(limit: float, started: float, operations) -> None:
    """Expire after `limit` seconds of PI activity; Runner waits do not count."""
    while True:
        waited = operations.current_wait_seconds() if operations is not None else 0.0
        if time.monotonic() - started - waited >= limit:
            return
        await asyncio.sleep(0.25)


async def converse(session, args, console: SessionReporter, finished, operations):
    """Drive one bounded conversation; return (exit code, abort the session)."""
    before = worktree_status()
    started = time.monotonic()
    finished_task = asyncio.create_task(finished.wait())
    stop_task = asyncio.create_task(wait_for_stop_request())
    timeout_task = asyncio.create_task(
        active_timeout(args.timeout, started, operations)
    )

    def timed_out():
        console.warning(
            f"session timed out after {args.timeout}s", code="session_timeout"
        )
        console.summary(changed_since(before))
        return EXIT_TIMEOUT, True

    try:
        prompt = args.prompt
        if operations is not None and args.resumed_session:
            prompt += RESUMED_STATE_PROMPT + json.dumps(
                operations.state, ensure_ascii=False
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
                await session.send(CONTINUE_PROMPT + json.dumps(operations.state))
        if stop_task in done:
            console.warning("session interrupted", code="session_interrupted")
            return EXIT_INTERRUPTED, True
        if timeout_task in done:
            return timed_out()
    except TimeoutError:
        return timed_out()
    except KeyboardInterrupt:
        console.warning("session interrupted", code="session_interrupted")
        return EXIT_INTERRUPTED, True
    finally:
        for task in (finished_task, stop_task, timeout_task):
            task.cancel()
        await asyncio.gather(
            finished_task, stop_task, timeout_task, return_exceptions=True
        )
    console.summary(changed_since(before))
    if operations is not None and operations.status != "session_ended":
        return EXIT_SESSION_ERROR, False
    return (EXIT_SESSION_ERROR if console.session_error else EXIT_OK), False


async def run(args, *, client=None, channel=None, binding=None) -> int:
    from copilot import CopilotClient

    if args.preliminary and provider_of(args.model) == "github-copilot":
        args.model, args.reasoning = ANALYST_MODEL, ANALYST_REASONING
    await prepare_provider(args)
    console = getattr(args, "usage_console", None) or SessionReporter()
    if getattr(args, "session_id", ""):
        console.session_id = args.session_id
    finished = asyncio.Event()
    if stop_requested():
        return EXIT_INTERRUPTED
    owned_client = client is None
    if not args.preliminary and channel is None:
        raise ValueError(
            "Ordinary Copilot PI sessions require the trusted launcher controller."
        )
    client = client or CopilotClient(working_directory=str(ROOT))
    coding = None
    operations = None
    if not args.preliminary:
        coding = ScientificCoding(client, args, console)
        operations = OperationSubmission(channel, binding, console, coding)
        coding.operations = operations
    args.operation_submission = operations
    session = None
    abort_session = False
    try:
        if owned_client:
            await client.start()
            failure = await copilot_access_failure(client, required_copilot_model(args))
            if failure is not None:
                exit_code, message = failure
                console.diagnostic(
                    message, code="copilot_access_failed", severity="error"
                )
                return exit_code
        await assign_provider_identity(client, args)
        session = await open_session(
            client,
            args,
            session_options(args, console, finished, coding, operations, client),
        )
        if coding is not None:
            coding.session = session
        try:
            exit_code, abort_session = await converse(
                session, args, console, finished, operations
            )
        except asyncio.CancelledError:
            abort_session = True
            raise
        return exit_code
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


# --- command line and launcher controller ----------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", nargs="?")
    parser.add_argument("--session-id")
    parser.add_argument("--controller-port", type=int)
    parser.add_argument("--controller-token")
    parser.add_argument("--model")
    parser.add_argument("--provider", choices=PROVIDERS)
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument(
        "--reasoning", default="high", choices=["low", "medium", "high", "xhigh", "max"]
    )
    # Continuation is explicit: a retry resumes this phase's own session and can
    # never inherit whatever session happened to run last on this machine.
    continuation = parser.add_mutually_exclusive_group()
    continuation.add_argument("--resume", action="store_true")
    continuation.add_argument("--resume-or-create", action="store_true")
    parser.add_argument("--timeout", type=float, default=21600.0)
    # Accounting metadata only; these values never enter the model prompt.
    parser.add_argument("--campaign-id")
    parser.add_argument("--phase")
    parser.add_argument("--preliminary", action="store_true")
    parser.add_argument("--attempt", type=int, default=1)
    args = parser.parse_args(argv)
    try:
        args.model = select_model(args.model, args.provider)
    except ValueError as error:
        parser.error(str(error))
    if args.list_models:
        if args.prompt or args.session_id or args.controller_port:
            parser.error("--list-models cannot start or resume a session")
    elif args.controller_port:
        if not args.controller_token or args.session_id or args.prompt:
            parser.error(
                "controller mode requires a token and no direct session/prompt"
            )
    elif not args.session_id or args.prompt is None:
        parser.error("a bounded invocation requires session-id and prompt")
    return args


def session_outcome(exit_code: int, invocation_args, error: str | None):
    """The status and error the launcher receives for one bounded session."""
    operations = getattr(invocation_args, "operation_submission", None)
    status = operations.status if operations is not None else "preliminary"
    message = (
        error
        or (operations.error if operations is not None else None)
        or invocation_args.usage_console.session_error
    )
    if exit_code == EXIT_TIMEOUT:
        return (
            "controller_fatal",
            f"Copilot bounded session timed out after {invocation_args.timeout}s.",
        )
    if exit_code == EXIT_INTERRUPTED:
        return "interrupted", "Copilot bounded session interrupted."
    if exit_code != EXIT_OK and status in UNEXPLAINED_EXIT_STATUSES:
        return "controller_fatal", message or (
            f"Copilot bounded session exited with code {exit_code} "
            "without a successful session outcome."
        )
    return status, message


async def serve_session(args, client, channel, command: dict) -> int:
    invocation_args = parse_args(command["arguments"])
    if (
        invocation_args.session_id != command["session_id"]
        or invocation_args.campaign_id != command["campaign_id"]
        or normalize_model(invocation_args.model) != normalize_model(args.model)
        or invocation_args.reasoning != args.reasoning
    ):
        raise ValueError("Controller invocation binding/configuration mismatch.")
    invocation_args.usage_console = SessionReporter()
    if getattr(args, "provider_model", None) is not None:
        invocation_args.provider_model = args.provider_model
        invocation_args.provider_project = args.provider_project
    started = time.monotonic()
    exit_code = EXIT_RUNTIME_FAILURE
    error = None
    # The journal owner of everything this invocation reports: the durable
    # session (S<n>, or the preparation), pinned once here so the failure and
    # accounting paths carry it too. The backend conversation id is not an owner.
    owner = typed_events.bind(
        session_id=command.get("scientific_session_id") or PREPARATION_SESSION,
        attempt=command["invocation_id"],
        actor="pi",
    )
    try:
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
                    invocation_args.usage_console.usage,
                    time.monotonic() - started,
                    exit_code,
                )
                announce_usage(invocation_args)
            except (OSError, ValueError) as exc:
                invocation_args.usage_console.diagnostic(
                    f"Session usage could not be recorded: {exc}",
                    code="usage_recording_failed",
                )
    finally:
        typed_events.reset_context(owner)
    status, message = session_outcome(exit_code, invocation_args, error)
    await channel.send(
        {
            "type": "session_result",
            "invocation_id": command["invocation_id"],
            "exit_code": exit_code,
            "status": status,
            "error": message,
        }
    )
    return exit_code


async def serve(args) -> int:
    if stop_requested():
        return EXIT_INTERRUPTED
    from copilot import CopilotClient

    try:
        reader, writer = await asyncio.open_connection(
            "127.0.0.1", args.controller_port, limit=4 * 1024 * 1024
        )
    except OSError:
        if stop_requested():
            return EXIT_INTERRUPTED
        raise
    channel = ControllerChannel(reader, writer)
    client = CopilotClient(working_directory=str(ROOT))
    try:
        await client.start()
        await prepare_provider(args)
        failure = await copilot_access_failure(client, required_copilot_model(args))
        if failure is not None:
            raise RuntimeError(failure[1])
        await channel.send({"type": "ready", "token": args.controller_token})
        while not stop_requested():
            command = await channel.receive()
            if command.get("type") == "shutdown":
                break
            if command.get("type") != "session":
                raise ValueError("Unexpected controller command.")
            exit_code = await serve_session(args, client, channel, command)
            if exit_code not in {EXIT_OK, EXIT_SESSION_ERROR}:
                break
        return EXIT_OK
    finally:
        try:
            await shutdown_runtime(client, None, SessionReporter(), abort=False)
        finally:
            writer.close()
            await writer.wait_closed()


def announce_usage(args) -> None:
    """Report this session's recorded usage, including its coding children."""
    if not args.campaign_id or not args.session_id:
        return
    from runner import reporting as runner_console
    from runner import typed_events

    totals = runner_console.usage_totals(args.campaign_id, args.session_id)
    summary = runner_console.usage_summary(args.campaign_id, args.session_id)
    typed_events.set_campaign(args.campaign_id)
    typed_events.emit(
        "session_usage",
        {
            "phase": args.phase,
            "session_id": args.session_id,
            "totals": totals,
            "text": summary,
        },
        scope="usage",
        event_id=(
            f"domain:session_usage:{args.session_id}:{args.phase or ''}:{args.attempt}"
        ),
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.usage_console = SessionReporter()
    started = time.monotonic()
    exit_code = EXIT_RUNTIME_FAILURE
    try:
        if args.list_models:
            exit_code = asyncio.run(list_model_choices(args))
        else:
            exit_code = asyncio.run(serve(args) if args.controller_port else run(args))
    except KeyboardInterrupt:
        exit_code = EXIT_INTERRUPTED
    except Exception as error:  # noqa: BLE001 - the launcher needs a code, not a traceback
        args.usage_console.diagnostic(
            f"Copilot runtime failure: {error}",
            code="copilot_runtime_failed",
            severity="error",
        )
    finally:
        try:
            record_usage(
                args, args.usage_console.usage, time.monotonic() - started, exit_code
            )
            announce_usage(args)
        except (OSError, ValueError) as error:
            # Accounting failure must not invalidate a scientific deliverable.
            args.usage_console.diagnostic(
                f"Session usage could not be recorded: {error}",
                code="usage_recording_failed",
            )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
