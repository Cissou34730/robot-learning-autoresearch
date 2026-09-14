"""Isolated evidence review before an official final benchmark."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

from research import runner_console as console
from research import runner_paths as paths
from research import runner_repository as repository

REVIEW_MODEL = "gpt-5.6-luna"
REVIEW_TIMEOUT_SECONDS = 300
REVIEW_PROMPT = """Using only the stated campaign objective and the submitted measurements for
the current best-known model, assess whether proceeding to the terminal final
benchmark is reasonably supported.

Examine what the underlying measurements demonstrate about the model, beyond
their summary metrics. Interpret the observed behavior in relation to the
objective, considering the scope of the measurements, their consistency, and
the evidential strength of the observations.

When episode-level or similarly detailed records are available, inspect them
directly. Assess material behavioral patterns that are relevant to the stated
objective, including their prevalence, severity, and, where the submitted
measurements contain comparable information, whether they recur. Do not infer
a pattern from an aggregate rate alone or from an arbitrary subdivision of the
data. Treat unavailable or incomparable information as unresolved, not as
evidence for or against a pattern.

Build a rationale that explains how the demonstrated capability, observed
limitations, and uncertainty affect readiness. Give each observation weight
according to its relevance and evidential strength. Balance means proportionate
consideration of the material evidence, not an equal number of arguments for
each outcome. Where observations admit different interpretations, compare the
plausible interpretations and state whether the submitted evidence distinguishes
between them.

Use the stated objective as the standard without adding performance
requirements. The question is whether the submitted evidence justifies using
the distinct terminal assessment, not whether the development measurements
already establish its official outcome.

Choose APPROVE_FINAL when the evidence reasonably supports proceeding, and
REJECT_FINAL when it does not. Explain which recorded facts carry the decision,
how their weight was assessed, and why any material countervailing evidence,
when present, does not change the conclusion.

End with exactly one separate line:

DECISION: APPROVE_FINAL

or:

DECISION: REJECT_FINAL
"""


def _copy_review_bundle(best_known: dict, destination: Path) -> tuple[str, list[str]]:
    objective = paths.RESEARCH_DIR / "scenario.md"
    if not objective.is_file():
        raise RuntimeError("the campaign objective is unavailable for evidence review")
    evidence = best_known.get("evaluation_artifacts")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("best-known lineage must identify evaluation artifacts")

    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(objective, destination / "scenario.md")
    evidence_directory = destination / "evaluations"
    evidence_directory.mkdir()
    copied_paths = ["scenario.md"]
    for index, relative_path in enumerate(evidence, start=1):
        source = repository.resolve_repo_path(str(relative_path))
        if not source.is_file():
            raise RuntimeError(
                f"best-known evaluation artifact is unavailable: {relative_path}"
            )
        copied_path = f"evaluations/evaluation-{index:03}.json"
        shutil.copy2(source, destination / copied_path)
        copied_paths.append(copied_path)
    return str(best_known.get("candidate") or best_known.get("fingerprint")), copied_paths


def _review_message(model_identifier: str, evidence_paths: list[str]) -> str:
    files = "\n".join(f"- {path}" for path in evidence_paths)
    return (
        f"Current best-known model identifier: {model_identifier}\n\n"
        "Read every listed file with the view tool before deciding:\n"
        f"{files}\n\n{REVIEW_PROMPT}"
    )


def _parse_response(response: str) -> tuple[str, str]:
    lines = [line.strip() for line in response.splitlines() if line.strip()]
    if len(lines) < 2:
        raise RuntimeError("the evidence reviewer did not return a rationale and decision")
    decisions = {
        "DECISION: APPROVE_FINAL": "APPROVE_FINAL",
        "DECISION: REJECT_FINAL": "REJECT_FINAL",
    }
    decision = decisions.get(lines[-1])
    if decision is None or any(line in decisions for line in lines[:-1]):
        raise RuntimeError("the evidence reviewer did not return one final decision")
    rationale = " ".join(" ".join(lines[:-1]).split())
    if not rationale:
        raise RuntimeError("the evidence reviewer did not return a rationale")
    return decision, rationale


async def _request_review(
    working_directory: Path, model_identifier: str, evidence_paths: list[str]
) -> str:
    from copilot import CopilotClient, PermissionHandler, ToolSet
    from copilot.session_events import (
        AssistantMessageData,
        SessionErrorData,
        SessionIdleData,
        ToolExecutionCompleteData,
        ToolExecutionStartData,
    )

    completed = asyncio.Event()
    responses: list[str] = []
    errors: list[str] = []
    active_reads: dict[str, str] = {}

    def on_event(event) -> None:
        data = event.data
        if isinstance(data, AssistantMessageData) and data.content:
            responses.append(data.content)
        elif isinstance(data, ToolExecutionStartData):
            arguments = data.arguments if isinstance(data.arguments, dict) else {}
            target = str(arguments.get("path") or arguments.get("filePath") or "file")
            active_reads[data.tool_call_id] = target
            console.announce(f"[review] reading {target}")
        elif isinstance(data, ToolExecutionCompleteData):
            target = active_reads.pop(data.tool_call_id, "file")
            if data.success:
                console.announce(f"[review] read {target}")
            else:
                console.announce(f"[review] failed to read {target}: {data.error}")
        elif isinstance(data, SessionErrorData):
            errors.append(data.message or "unknown session error")
        elif isinstance(data, SessionIdleData):
            completed.set()

    async with CopilotClient(working_directory=str(working_directory)) as client:
        status = await client.get_auth_status()
        if not getattr(status, "isAuthenticated", False):
            raise RuntimeError("Copilot is not authenticated for evidence review")
        session = await client.create_session(
            model=REVIEW_MODEL,
            on_event=on_event,
            # Only "view" is available, so approving every request only ever
            # grants read access to the isolated evidence bundle.
            on_permission_request=PermissionHandler.approve_all,
            available_tools=ToolSet().add_builtin(["view"]),
            working_directory=str(working_directory),
            streaming=False,
            enable_skills=False,
            enable_session_store=False,
            skip_embedding_retrieval=True,
            enable_mcp_apps=False,
        )
        try:
            await session.send(_review_message(model_identifier, evidence_paths))
            await asyncio.wait_for(completed.wait(), timeout=REVIEW_TIMEOUT_SECONDS)
        except TimeoutError as error:
            await session.abort()
            raise RuntimeError("the evidence reviewer timed out") from error
        finally:
            await session.disconnect()
    if errors:
        raise RuntimeError(f"the evidence reviewer failed: {errors[-1]}")
    if not responses:
        raise RuntimeError("the evidence reviewer returned no assessment")
    return responses[-1]


def review_final_benchmark_evidence(best_known: dict) -> dict:
    """Run one stateless, fail-closed review over the frozen development evidence."""
    with tempfile.TemporaryDirectory(prefix="robot-learning-final-review-") as temporary:
        directory = Path(temporary)
        try:
            identifier, evidence_paths = _copy_review_bundle(best_known, directory)
            response = asyncio.run(_request_review(directory, identifier, evidence_paths))
            decision, rationale = _parse_response(response)
            return {"decision": decision, "rationale": rationale}
        except Exception as error:  # noqa: BLE001 - review failures must close the gate.
            return {
                "decision": "REJECT_FINAL",
                "rationale": f"Review unavailable: {error}",
            }