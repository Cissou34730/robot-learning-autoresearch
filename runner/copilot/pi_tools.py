"""Custom read-only tools exposed to the main PI and the preliminary analyst."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from copilot import ToolResult
from pydantic import BaseModel, ConfigDict, Field

from runner.copilot.path_policy import ROOT, file_read_denial
from runner.copilot.tool_policy import scoped_tool_hook

ARTIFACT_EVIDENCE_DESCRIPTION = (
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
    "All batch items share that byte limit for selected values. Query items reject max_bytes. "
    "Omit select for complete rows; a supplied pointer cannot be empty. Filtering occurs "
    "before data enters PI context. Full reads use byte offset/max_bytes, "
    "UTF-8 content or explicit base64, and fingerprint-bound continuation. "
    "query/batch raw and value_counts use offset paging after selection. "
    "Follow reported next offsets/fingerprints; report transport/traversal "
    "limits honestly and never mistake one truncated page for full retrieval."
)

TRAINING_LOG_DESCRIPTION = (
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
)

TRAINING_SERIES_DESCRIPTION = (
    "Read-only numeric summary of one metric in one preserved training log. Select "
    "operation_id, the exact metric name, attempt when several logs exist, and an "
    "optional inclusive from_step/to_step window. Returns the row count; first and "
    "last values with steps; minimum and maximum with first step and number of rows "
    "at that value; mean and sample standard deviation. Optional checks compare "
    "min, max, mean, first or last with a threshold you choose (>= or <=) and return "
    "the value and holds true/false; min and max checks also return the number and "
    "first/last steps of rows that do not meet the comparison. Checks are optional "
    "and do not judge claims. Rows without a finite value are excluded and counted. "
    "Failed/pending-failure logs are execution history, NOT scientific evidence."
)

WILSON_DESCRIPTION = (
    "Wilson score intervals for up to 20 success proportions at a two-sided "
    "confidence level you choose. Supply labelled success and trial counts read "
    "from the records; the tool reads no files and does not verify counts. With an "
    "optional threshold rate, each interval is reported as above, below or "
    "including it. Assumes independent trials with one common success probability."
)

API_REFERENCE_DESCRIPTION = (
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
)

READ_DESCRIPTION = (
    "Read UTF-8 text from an exact permitted file. "
    "Use optional view_range for line pages. "
    "The same file scopes apply as for view. "
    "Use native view for images."
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
    from runner.proportion_interval import WilsonParams, query_wilson_interval
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

    def wilson_proportion_interval(params, invocation) -> str:
        authorize(invocation)
        return query_wilson_interval(params.model_dump())

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
            "wilson_proportion_interval",
            description=WILSON_DESCRIPTION,
            handler=wilson_proportion_interval,
            params_type=WilsonParams,
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
                raise ValueError("Read exceeds the page limit. Use a narrower view_range.")
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
