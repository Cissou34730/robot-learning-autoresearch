"""Custom read-only tools exposed to the main PI and the preliminary analyst."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from copilot import ToolResult
from pydantic import BaseModel, ConfigDict, Field

from runner.copilot.path_policy import ROOT, file_read_denial, reference_read_denial
from runner.copilot.tool_policy import scoped_tool_hook

ARTIFACT_EVIDENCE_DESCRIPTION = (
    "Read JSON evidence by operation_id, not by file path. Use this tool, not "
    "view, for measurement artifacts. operations lists the operation index. "
    "metadata returns the record, the artifact references, the session records or "
    "the accepted pending request of one operation, without opening the artifact "
    "contents. discover shows the structure of an artifact. query and batch select, filter, "
    "project or aggregate fields. read returns the complete original artifact in "
    "pages. You choose the complete content or any subsets. A page is partial "
    "until next_offset is null. Pending metadata is execution metadata, not "
    "completed evidence."
)

TRAINING_LOG_DESCRIPTION = (
    "Read the kept training logs of one training operation by operation_id. "
    "discover lists the attempts, the timestep range and the metric names. "
    "records returns selected metrics over a timestep window, in pages of rows. "
    "raw returns the original log text in pages of bytes. A page is partial until "
    "next_offset is null. The logs of a failed operation are execution history, "
    "not scientific evidence."
)

TRAINING_SERIES_DESCRIPTION = (
    "Summarize one metric of one training log over a timestep window: rows, first, "
    "last, min, max, mean and standard deviation, with steps. Optional checks "
    "compare a statistic with a threshold that you choose and return whether the "
    "comparison is true. min and max checks also return the rows that fail. The "
    "logs of a failed operation are execution history, not scientific evidence."
)

PASS_PROBABILITY_DESCRIPTION = (
    "Estimate how likely a candidate is to reach a success-rate target. Give the "
    "target panel (trials and required successes, from contracts/scenario.md) and "
    "evidence entries. Each entry is either recorded measurements to pool, as "
    "{operation_id, candidate, optional instrument, optional label}, which the "
    "Runner reads from the "
    "records, or typed counts. For each entry, the result gives: the probability "
    "that a new target panel reaches the target, an interval at your confidence "
    "level, the pass probability if the true rate is at either bound of the "
    "interval, and whether the interval is above, below or across the target rate. "
    "It also gives the true success rate that a pass probability of 50%, 80% or "
    "95% needs. Recorded entries also list their sources and shared episodes, and "
    "for each source the candidates that the campaign measured on the same "
    "episodes. The tool assumes independent episodes that are representative of "
    "the target panel. The counts of the best of several candidates measured on "
    "the same episodes are optimistic."
)

EPISODE_OUTCOME_DESCRIPTION = (
    "Read the episode-level outcomes of recorded research_evaluation or "
    "task_reference measurements, given as {operation_id, candidate, optional "
    "instrument, optional label}. With one measurement: the successes and an "
    "interval at your "
    "confidence level. With two measurements of the same episodes: the paired "
    "counts (both, first only, second only, neither), an exact sign test and the "
    "share of the first measurement among the discordant episodes, where only one "
    "succeeds. Optional strata divide each result into bins of a numeric "
    "per-episode field (rows path, field and edges that you choose), for example "
    "the target radius."
)

API_REFERENCE_DESCRIPTION = (
    "Read installed definitions from mujoco, gymnasium or stable_baselines3. "
    "Select the library and a public dotted symbol relative to it. Omit symbol for "
    "the root of the library. action=members lists public names (filter with "
    "contains, page with offset and limit). action=definition returns the "
    "signature, the documentation, the Python source and the native MuJoCo "
    "declaration (page with offset and max_bytes). The tool reports a missing "
    "symbol. It does not guess a replacement. A definition does not show that an "
    "integration runs."
)

READ_DESCRIPTION = (
    "Read UTF-8 text from an exact permitted file. "
    "Use the optional view_range for pages of lines. "
    "The same file scopes apply as for view. "
    "Use the native view for images."
)


class ReadParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    view_range: list[int] | None = Field(default=None, min_length=2, max_length=2)
    forceReadLargeFiles: bool = False


def reader_guard(args, coding, operations):
    def authorize(invocation) -> None:
        if (
            invocation.session_id != args.session_id
            or getattr(invocation, "agent_id", None) is not None
            or (coding is not None and coding.locked)
            or (operations is not None and operations.locked)
        ):
            raise ValueError("Only the active, unlocked main/preliminary PI may query.")

    return authorize


def evidence_tools(args, authorize, coding, operations) -> list:
    from copilot import define_tool

    from runner.artifact_evidence_query import (
        ArtifactEvidenceQueryParams,
        query_artifact,
    )
    from runner.episode_outcomes import EpisodeOutcomeParams, query_episode_outcomes
    from runner.proportion_interval import (
        PassProbabilityParams,
        query_pass_probability,
    )
    from runner.query_training_log import TrainingLogQueryParams, query_training_log
    from runner.scientific_api_reference import (
        ScientificAPIReferenceParams,
        read_reference,
    )
    from runner.training_series import TrainingSeriesParams, query_training_series

    campaign_id = str(args.campaign_id or "")

    async def artifact_evidence_query(params, invocation) -> str:
        authorize(invocation)
        return await asyncio.to_thread(
            query_artifact, params.model_dump(), campaign_id=campaign_id
        )

    def training_log_query(params, invocation) -> str:
        authorize(invocation)
        return query_training_log(
            params.model_dump(exclude_none=True), campaign_id=campaign_id
        )

    async def training_series_statistics(params, invocation) -> str:
        authorize(invocation)
        return await asyncio.to_thread(
            query_training_series,
            params.model_dump(exclude_none=True),
            campaign_id=campaign_id,
        )

    def success_rate_pass_probability(params, invocation) -> str:
        authorize(invocation)
        return query_pass_probability(
            params.model_dump(exclude_none=True), campaign_id=campaign_id
        )

    async def episode_outcome_breakdown(params, invocation) -> str:
        authorize(invocation)
        return await asyncio.to_thread(
            query_episode_outcomes,
            params.model_dump(exclude_none=True),
            campaign_id=campaign_id,
        )

    def authorize_api_reader(invocation) -> None:
        if getattr(invocation, "agent_id", None) is None:
            authorize(invocation)
        elif (
            invocation.session_id != args.session_id
            or coding is None
            or not coding.busy
            or coding.closed
            or coding.binding is None
            or invocation.agent_id != coding.active_handle
            or (operations is not None and operations.locked)
        ):
            raise ValueError(
                "Only the active main PI or its authorized scientific child may read APIs."
            )

    async def scientific_api_reference(params, invocation) -> str | ToolResult:
        authorize_api_reader(invocation)
        try:
            reference = await asyncio.to_thread(read_reference, params)
        except ValueError as error:
            failure = {
                "status": "lookup_failed",
                "library": params.library,
                "symbol": params.symbol,
                "error": str(error),
            }
            return ToolResult(
                text_result_for_llm=json.dumps(failure, ensure_ascii=False),
                result_type="failure",
                error=str(error),
                tool_telemetry={},
            )
        return json.dumps(reference, ensure_ascii=False)

    return [
        define_tool(
            "artifact_evidence_query",
            description=ARTIFACT_EVIDENCE_DESCRIPTION,
            handler=artifact_evidence_query,
            params_type=ArtifactEvidenceQueryParams,
            defer="auto",
            skip_permission=True,
        ),
        define_tool(
            "training_log_query",
            description=TRAINING_LOG_DESCRIPTION,
            handler=training_log_query,
            params_type=TrainingLogQueryParams,
            defer="auto",
            skip_permission=True,
        ),
        define_tool(
            "training_series_statistics",
            description=TRAINING_SERIES_DESCRIPTION,
            handler=training_series_statistics,
            params_type=TrainingSeriesParams,
            defer="auto",
            skip_permission=True,
        ),
        define_tool(
            "success_rate_pass_probability",
            description=PASS_PROBABILITY_DESCRIPTION,
            handler=success_rate_pass_probability,
            params_type=PassProbabilityParams,
            defer="auto",
            skip_permission=True,
        ),
        define_tool(
            "episode_outcome_breakdown",
            description=EPISODE_OUTCOME_DESCRIPTION,
            handler=episode_outcome_breakdown,
            params_type=EpisodeOutcomeParams,
            defer="auto",
            skip_permission=True,
        ),
        define_tool(
            "scientific_api_reference",
            description=API_REFERENCE_DESCRIPTION,
            handler=scientific_api_reference,
            params_type=ScientificAPIReferenceParams,
            defer="auto",
            skip_permission=True,
        ),
    ]


def scoped_search(args, client, authorize):
    from runner.copilot.copilot_scoped_search import ScopedSearch

    # Use the SDK runtime's bundled rg rather than a model-controlled shell search.
    runtime_path = getattr(getattr(client, "_connection", None), "path", None)
    candidates = (
        sorted(Path(runtime_path).parent.glob("ripgrep\\bin\\*\\rg.exe"))
        if runtime_path
        else []
    )
    system_rg = shutil.which("rg")
    rg_path = Path(system_rg) if system_rg else next(iter(candidates), None)
    return ScopedSearch(
        ROOT,
        lambda path: file_read_denial(path, preliminary=args.preliminary),
        rg_path,
        authorize,
        lambda path: reference_read_denial(path, preliminary=args.preliminary),
    )


def _read_lines(path: Path, params: ReadParams) -> str:
    from runner.copilot.copilot_scoped_search import MAX_OUTPUT_BYTES

    first, last = params.view_range or (1, -1)
    if first < 1 or (last != -1 and last < first):
        raise ValueError("view_range requires a positive start and ordered end.")
    lines = []
    size = 0
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if last != -1 and number > last:
                break
            if number < first:
                continue
            size += len(line.encode("utf-8"))
            if size > MAX_OUTPUT_BYTES and not params.forceReadLargeFiles:
                raise ValueError(
                    "Read exceeds the page limit. Use a narrower view_range."
                )
            lines.append(line)
    return "".join(lines)


def read_tool(args, search, coding, operations):
    """OpenCode routes require a tool named `read`; it applies the `view` policy."""
    from copilot import define_tool

    hook = scoped_tool_hook(
        operations=operations, coding=coding, preliminary=args.preliminary
    )

    async def read(params: ReadParams, invocation) -> str:
        if (
            invocation.session_id != args.session_id
            or getattr(invocation, "agent_id", None) is not None
        ):
            raise ValueError("Read belongs to the OpenCode-routed main session only.")
        request = {
            "sessionId": args.session_id,
            "toolName": "view",
            "toolArgs": params.model_dump(exclude_none=True),
        }
        decision = hook(request, {"session_id": args.session_id})
        if decision and decision.get("permissionDecision") == "deny":
            raise ValueError(decision["permissionDecisionReason"])
        path = search.target(params.path)
        if not path.is_file():
            raise ValueError("Read requires an exact permitted text file.")
        return _read_lines(path, params)

    return define_tool(
        "read",
        description=READ_DESCRIPTION,
        handler=read,
        params_type=ReadParams,
        defer="never",
        skip_permission=True,
    )
