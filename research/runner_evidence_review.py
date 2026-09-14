"""Isolated evidence review before an official final benchmark."""

from __future__ import annotations

import asyncio
import re
import shutil
import tempfile
from pathlib import Path

from research import runner_paths as paths
from research import runner_repository as repository

REVIEW_MODEL = "gpt-5.6-luna"
REVIEW_TIMEOUT_SECONDS = 300
REVIEW_PROMPT = """Based only on the recorded measurements for the current best-known model and
the stated campaign objective, assess whether the evidence justifies requesting
the terminal final benchmark at this point.

Before concluding, do two things: (1) account for the statistical uncertainty
implied by the number of episodes evaluated, rather than treating the reported
percentage as exact; (2) inspect the individual episode records and determine
whether failures are spread evenly across the recorded per-episode parameters
or instead cluster on recurring values of one or more of those parameters,
whatever those parameters are for this evaluation.

Explain the basis for your assessment, including what you found in (1) and (2).
Do not assess the value of further research or propose next steps.

Return exactly one decision:
- APPROVE_FINAL
- REJECT_FINAL
"""


def _copy_review_bundle(best_known: dict, destination: Path) -> str:
    objective = paths.RESEARCH_DIR / "scenario.md"
    if not objective.is_file():
        raise RuntimeError("the campaign objective is unavailable for evidence review")
    evidence = best_known.get("evaluation_artifacts")
    if not isinstance(evidence, list) or len(evidence) != 2:
        raise ValueError("best-known lineage must identify two evaluation artifacts")

    shutil.copy2(objective, destination / "scenario.md")
    evidence_directory = destination / "evaluations"
    evidence_directory.mkdir()
    for index, relative_path in enumerate(evidence, start=1):
        source = repository.resolve_repo_path(str(relative_path))
        if not source.is_file():
            raise RuntimeError(
                f"best-known evaluation artifact is unavailable: {relative_path}"
            )
        shutil.copy2(source, evidence_directory / f"{index}-{source.name}")
    return str(best_known.get("candidate") or best_known.get("fingerprint"))


def _decision(response: str) -> str:
    decisions = set(re.findall(r"\b(?:APPROVE|REJECT)_FINAL\b", response))
    if len(decisions) != 1:
        raise RuntimeError("the evidence reviewer did not return one unambiguous verdict")
    return decisions.pop()


async def _request_review(working_directory: Path, model_identifier: str) -> str:
    from copilot import CopilotClient, ToolSet
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
            available_tools=ToolSet().add_builtin(["view"]),
            working_directory=str(working_directory),
            streaming=True,
            enable_skills=False,
            enable_session_store=False,
            skip_embedding_retrieval=True,
            enable_mcp_apps=False,
        )
        try:
            await session.send(
                f"Current best-known model identifier: {model_identifier}\n\n{REVIEW_PROMPT}"
            )
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
            identifier = _copy_review_bundle(best_known, directory)
            response = asyncio.run(_request_review(directory, identifier))
            return {"decision": _decision(response), "rationale": response}
        except Exception as error:  # noqa: BLE001 - review failures must close the gate.
            return {
                "decision": "REJECT_FINAL",
                "rationale": f"Review unavailable: {error}",
            }