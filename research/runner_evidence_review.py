"""Isolated evidence review before an official final benchmark."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

from research import runner_paths as paths
from research import runner_repository as repository

REVIEW_MODEL = "gpt-5.6-luna"
REVIEW_TIMEOUT_SECONDS = 300
REVIEW_PROMPT = """Based only on the stated campaign objective and the recorded measurements for
the current best-known model, assess whether the available evidence supports
using the terminal final benchmark at this point.

Base the assessment on the evidence as a whole, including measured performance,
consistency across available measurements, sample uncertainty, and the structure
of recorded failures. No single factor is automatically decisive.

Assess readiness for terminal assessment. Do not treat development measurements
as an official result, predict the benchmark outcome, assess the value of future
research, or propose another experiment.

Explain concisely which recorded facts determine the decision. End with exactly
one separate line:

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
    )

    completed = asyncio.Event()
    responses: list[str] = []
    errors: list[str] = []

    def on_event(event) -> None:
        data = event.data
        if isinstance(data, AssistantMessageData) and data.content:
            responses.append(data.content)
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