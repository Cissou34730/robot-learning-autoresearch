"""Read-only queries and repeatable retrieval of completed JSON artifacts."""

from __future__ import annotations

import base64
import hashlib
import json
from contextlib import ExitStack
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from runner import repository
from runner.json_artifact_view import (
    JsonArray,
    JsonDocument,
    JsonObject,
    JsonScalar,
    OutputBudgetExceeded,
    TraversalBudgetExceededError,
    bounded_value,
    scalar_value,
)

MAX_BYTES = 32 * 1024 * 1024
MAX_NODES = 50_000
MAX_PATHS = 200
MAX_RESULTS = 200
MAX_BATCH_QUERIES = 16
MAX_BATCH_RESULTS = 200
MAX_ARTIFACTS_PER_OPERATION = 100
MAX_MATCH_OUTPUT_BYTES = 128 * 1024
MAX_READ_BYTES = MAX_MATCH_OUTPUT_BYTES // 4 * 3
HASH_BLOCK_BYTES = 1024 * 1024
MISSING = object()
DEFAULT_RESULTS = 20
DEFAULT_PAGE_BYTES = 16 * 1024


class EvidenceFilter(BaseModel):
    model_config = {"extra": "forbid"}

    path: str = Field(
        min_length=1,
        max_length=1024,
        pattern=r"^/",
        description="JSON Pointer relative to each row. A missing field is not a non-match.",
    )
    equals: Any = Field(description="Required equality value; null is a valid value.")


class ArtifactEvidenceQuerySpec(BaseModel):
    model_config = {"extra": "forbid"}

    @model_validator(mode="before")
    @classmethod
    def reject_nested_byte_budget(cls, value: Any) -> Any:
        if isinstance(value, dict) and "max_bytes" in value:
            raise ValueError(
                "A query item does not accept max_bytes. "
                "Set max_bytes on the request to limit the entire batch. "
                "This item was rejected; its query did not run."
            )
        return value

    path: str = Field(
        max_length=1024,
        description=(
            "JSON Pointer scope to query; wildcards select array/object rows. "
            "A selected array is expanded to rows for filtering, projection or aggregation. "
            "Use where/select for a subset, or request complete objects."
        ),
    )
    where: EvidenceFilter | None = Field(
        default=None,
        description=(
            'Optional equality filter: {"path": <relative JSON Pointer>, '
            '"equals": <JSON value>}. Apply it to narrow wildcard row matches.'
        ),
    )
    select: str | None = Field(
        default=None,
        max_length=1024,
        description=(
            "Optional JSON Pointer relative to each path match, applied after "
            "where filtering. Omit to retrieve complete row objects. "
            "A supplied pointer must start with / and cannot be empty."
        ),
    )
    aggregate: (
        Literal["count", "numeric_summary", "value_counts"] | None
    ) = Field(
        default=None,
        description=(
            "Optional bounded aggregate instead of returning raw matches: "
            "count, numeric_summary or value_counts."
        ),
    )
    limit: int = Field(
        default=DEFAULT_RESULTS,
        ge=1,
        le=MAX_RESULTS,
        description=(
            "Maximum raw matches returned for this specification; keep it "
            "bounded when raw episode rows are required."
        ),
    )
    offset: int = Field(
        default=0,
        ge=0,
        description=(
            "Record offset after filtering/projection, or distinct-value offset "
            "for value_counts. Repeat with next_offset to retrieve remaining "
            "results. A single oversized object can be retrieved with action=read."
        ),
    )


class ArtifactEvidenceQueryParams(BaseModel):
    model_config = {"extra": "forbid"}

    action: Literal["discover", "query", "batch", "read", "operations", "metadata"] = (
        Field(
            description=(
                "discover lists paths. query or batch selects, filters, projects or "
                "aggregates values. read returns the complete original artifact in "
                "byte pages; continue with next_offset and expected_fingerprint. "
                "operations queries the operation index. metadata queries one "
                "operation's record, artifacts, checkpoints or accepted pending "
                "request without opening artifact data."
            ),
        )
    )
    operation_id: str | None = Field(
        default=None,
        description=(
            "Required except for operations. For metadata, any recorded or pending operation; "
            "otherwise the completed measurement that recorded the JSON artifact."
        ),
    )
    artifact_index: int = Field(
        default=0,
        ge=0,
        le=MAX_ARTIFACTS_PER_OPERATION - 1,
        description=(
            "Zero-based recorded artifact index when the operation produced "
            "multiple measurements. Only for artifact-content actions."
        ),
    )
    prefix: str | None = Field(
        default=None,
        max_length=1024,
        description="For discover, the JSON Pointer prefix to inspect.",
    )
    queries: list[ArtifactEvidenceQuerySpec] | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_BATCH_QUERIES,
        description=(
            f"For batch, at most {MAX_BATCH_QUERIES} related query specifications "
            "executed against one "
            "resolved and fingerprint-verified artifact. Prefer one batch over "
            "separate calls for related fields; provenance is returned once. "
            "Each specification can select subsets or complete objects. "
            "Set max_bytes on the request, never inside a query item."
        ),
    )
    path: str | None = Field(
        default=None,
        max_length=1024,
        description=(
            "JSON Pointer scope for query, operations or metadata. Operations "
            "defaults to /*; metadata defaults to /operation. Batch scopes belong "
            "inside queries. Filter or select wildcard matches for subsets."
        ),
    )
    where: EvidenceFilter | None = Field(
        default=None,
        description=(
            "Optional equality filter applied to wildcard matches before "
            "select; use it to avoid returning unrelated rows."
        ),
    )
    select: str | None = Field(
        default=None,
        max_length=1024,
        description=(
            "Optional JSON Pointer relative to each path match, applied after "
            "where filtering. Omit to retrieve complete row objects. "
            "A supplied pointer must start with / and cannot be empty."
        ),
    )
    aggregate: Literal["count", "numeric_summary", "value_counts"] | None = Field(
        default=None,
        description=(
            "Optional bounded aggregate instead of raw matches: count, "
            "numeric_summary or value_counts."
        ),
    )
    limit: int = Field(
        default=DEFAULT_RESULTS,
        ge=1,
        le=MAX_RESULTS,
        description="Maximum raw matches returned; keep it bounded when needed.",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description=(
            "For query, record offset after selection (distinct values for "
            "value_counts). For read, zero-based original file byte offset. "
            "Continue with the returned next_offset."
        ),
    )
    max_bytes: int = Field(
        default=DEFAULT_PAGE_BYTES,
        ge=1,
        le=MAX_READ_BYTES,
        description=(
            "Byte limit for selected values in query and batch. "
            "All batch items share this limit. "
            "Query items do not accept max_bytes. For read, it limits original bytes. "
            "Increase explicitly for broader retrieval; follow reported continuation."
        ),
    )
    encoding: Literal["utf-8", "base64"] = Field(
        default="utf-8",
        description=(
            "For read, UTF-8 returns readable exact text on character boundaries; "
            "base64 returns exact arbitrary bytes with an optional readable UTF-8 "
            "preview. Use base64 if UTF-8 decoding fails."
        ),
    )
    expected_fingerprint: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
        description=(
            "For read, SHA256 from the preceding page; required for nonzero "
            "offsets. Refuses continuation if the verified artifact differs."
        ),
    )

    @model_validator(mode="after")
    def validate_action_fields(self) -> "ArtifactEvidenceQueryParams":
        if self.action != "operations" and not (
            self.operation_id and self.operation_id.strip()
        ):
            raise ValueError("This action requires operation_id.")
        if self.action == "operations" and self.operation_id is not None:
            raise ValueError("operations lists the campaign; use metadata for one operation.")
        if self.action in {"operations", "metadata"} and (
            self.prefix is not None or self.queries is not None
            or self.expected_fingerprint is not None
            or self.artifact_index != 0 or self.encoding != "utf-8"
        ):
            raise ValueError(
                "Metadata selection uses path, where, select and aggregate. "
                "Artifact indices, fingerprints, discovery prefixes and byte encodings are not metadata selectors."
            )
        if self.action in {"operations", "metadata"} and self.path == "":
            raise ValueError("Metadata path must be a non-empty JSON Pointer or omitted.")
        if self.action == "batch" and not self.queries:
            raise ValueError("batch action requires queries")
        if self.action == "query" and not self.path:
            raise ValueError("query action requires path")
        if self.action == "read" and self.offset and not self.expected_fingerprint:
            raise ValueError("read continuation requires expected_fingerprint")
        if self.action == "read" and self.encoding == "utf-8" and self.max_bytes < 4:
            raise ValueError("UTF-8 read requires max_bytes >= 4")
        if self.action == "read" and any(
            field is not None
            for field in (
                self.path, self.where, self.select,
                self.aggregate, self.prefix, self.queries,
            )
        ):
            raise ValueError(
                "read retrieves the original artifact; "
                "selection fields require query or batch"
            )
        if self.action == "discover" and self.offset:
            raise ValueError("discover does not accept offsets; narrow prefix or use read")
        return self


class ArtifactUnavailableError(Exception):
    def __init__(self, reason: str, provenance: dict[str, Any] | None = None):
        super().__init__(reason)
        self.reason = reason
        self.provenance = provenance or {}


class FingerprintMismatchError(Exception):
    def __init__(
        self,
        provenance: dict[str, Any],
        reason: str = "artifact fingerprint differs from the recorded fingerprint",
    ):
        super().__init__(reason)
        self.provenance = provenance


class ArtifactBudgetExceededError(Exception):
    def __init__(self, provenance: dict[str, Any], total_bytes: int):
        self.provenance = provenance
        self.total_bytes = total_bytes
        super().__init__("artifact exceeds the bounded-query byte safety limit")


def _tokens(pointer: str) -> list[str]:
    if pointer in {"", "/"}:
        return []
    if not pointer.startswith("/"):
        raise ValueError("path must use JSON Pointer syntax")
    return [
        token.replace("~1", "/").replace("~0", "~")
        for token in pointer[1:].split("/")
    ]


def _pointer(tokens: list[str]) -> str:
    if not tokens:
        return "/"
    escaped = (
        str(token).replace("~", "~0").replace("/", "~1")
        for token in tokens
    )
    return "/" + "/".join(escaped)


def _artifact_catalog(event: dict[str, Any]) -> list[dict[str, Any]]:
    result = event.get("result")
    measurements = result.get("measurements") if isinstance(result, dict) else None
    artifacts = []
    for measurement in measurements if isinstance(measurements, list) else []:
        metrics = measurement.get("metrics") if isinstance(measurement, dict) else None
        if not isinstance(metrics, dict):
            continue
        artifact_path = metrics.get("evaluation_artifact")
        fingerprint = metrics.get("evaluation_artifact_fingerprint")
        if not isinstance(artifact_path, str) or not artifact_path:
            continue
        if not isinstance(fingerprint, str) or not fingerprint:
            continue
        artifacts.append({
            "artifact_path": artifact_path,
            "recorded_artifact_fingerprint": fingerprint,
            "instrument": measurement.get("instrument"),
            "label": measurement.get("label"),
        })
    return artifacts


def _recorded_artifact(
    state: dict[str, Any],
    campaign_id: str,
    operation_id: str,
    artifact_index: int,
) -> tuple[Any, dict[str, Any]]:
    state_campaign_id = state.get("campaign", {}).get("id")
    if not campaign_id or state_campaign_id != campaign_id:
        raise ValueError("tool campaign does not match the active Runner state")
    event = next(
        (
            item
            for item in state.get("operation_events", [])
            if item.get("id") == operation_id
        ),
        None,
    )
    if event is None:
        raise ArtifactUnavailableError("operation_not_found")
    event_provenance = {
        "campaign_id": campaign_id,
        "operation_id": operation_id,
        "operation_kind": event.get("kind"),
        "operation_status": event.get("status"),
    }
    if event.get("status") != "completed":
        raise ArtifactUnavailableError(
            "operation_not_completed", event_provenance
        )
    if event.get("kind") != "measurement":
        raise ArtifactUnavailableError(
            "operation_has_no_measurement_artifacts", event_provenance
        )
    result = event.get("result")
    measurements = (
        result.get("measurements") if isinstance(result, dict) else None
    )
    if not isinstance(measurements, list):
        raise ArtifactUnavailableError(
            "completed_measurement_result_unavailable", event_provenance
        )
    artifacts = _artifact_catalog(event)
    if not artifacts:
        raise ArtifactUnavailableError(
            "operation_has_no_recorded_json_artifacts", event_provenance
        )
    if artifact_index >= len(artifacts):
        raise ValueError(
            f"artifact_index {artifact_index} is outside the recorded range "
            f"0..{len(artifacts) - 1}"
        )
    selected = artifacts[artifact_index]
    relative = repository.canonical_repo_path(selected["artifact_path"])
    expected_prefix = f"campaigns/evaluations/{campaign_id}/"
    if (
        not relative.startswith(expected_prefix)
        or not relative.lower().endswith(".json")
    ):
        raise ValueError(
            "recorded measurement artifact is outside the active campaign "
            "evaluation directory or is not JSON"
        )
    path = repository.resolve_repo_path(relative)
    provenance: dict[str, Any] = {
        **event_provenance,
        "artifact_index": artifact_index,
        "artifact_count": len(artifacts),
        "artifact_path": relative,
        "recorded_artifact_fingerprint": selected[
            "recorded_artifact_fingerprint"
        ],
    }
    for key in ("instrument", "label"):
        if selected[key] is not None:
            provenance[key] = selected[key]
    if not path.is_file():
        raise ArtifactUnavailableError("artifact_file_unavailable", provenance)
    return path, provenance


class ArtifactReference(BaseModel):
    model_config = {"extra": "forbid"}

    operation_id: str = Field(min_length=1)
    artifact_index: int = Field(ge=0, lt=MAX_ARTIFACTS_PER_OPERATION, strict=True)


class CandidateReference(BaseModel):
    model_config = {"extra": "forbid"}

    candidate: str = Field(min_length=1, description="Candidate ID or role.")


MAX_CANDIDATE_METADATA_BYTES = 16_384


def recorded_candidate_metadata(state: dict, reference: dict) -> dict:
    """Archive file names and artifact.json of one verified candidate."""
    from runner import protocol

    selected = CandidateReference.model_validate(reference)
    try:
        candidate = protocol.resolve_candidate(state, selected.candidate)
    except KeyError as error:
        raise ValueError(f"evidence input {selected.candidate!r}: {error}") from error
    archive = repository.resolve_repo_path(candidate["artifact"])
    metadata_path = archive / "artifact.json"
    metadata = None
    if (
        metadata_path.is_file()
        and metadata_path.stat().st_size <= MAX_CANDIDATE_METADATA_BYTES
    ):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return {
        "candidate": candidate["id"],
        "archive_path": candidate["artifact"],
        "archive_files": sorted(path.name for path in archive.iterdir() if path.is_file()),
        "artifact_json": metadata,
    }


def resolve_artifact_reference(state: dict, reference: dict) -> dict:
    selected = ArtifactReference.model_validate(reference)
    path, provenance = _recorded_artifact(
        state, repository.current_campaign_id(state),
        selected.operation_id.strip(), selected.artifact_index,
    )
    _artifact_bytes(path, provenance, max_bytes=0)
    return {
        key: provenance[key]
        for key in (
            "operation_id", "artifact_index", "artifact_path",
            "recorded_artifact_fingerprint",
        )
    }


def recorded_artifact_structure(state: dict, reference: dict) -> dict:
    """Recorded structure-only inventory of one completed measurement artifact."""
    selected = ArtifactReference.model_validate(reference)
    operation_id = selected.operation_id.strip()
    try:
        _, provenance = _recorded_artifact(
            state, repository.current_campaign_id(state),
            operation_id, selected.artifact_index,
        )
    except ArtifactUnavailableError as error:
        raise ValueError(
            f"evidence input {operation_id}/{selected.artifact_index} is unavailable: "
            f"{error.args[0] if error.args else error}"
        ) from error
    event = next(
        item for item in state["operation_events"] if item.get("id") == operation_id
    )
    structure = next(
        (
            measurement["metrics"].get("evaluation_artifact_contents")
            for measurement in event["result"]["measurements"]
            if isinstance(measurement, dict)
            and isinstance(measurement.get("metrics"), dict)
            and isinstance(measurement["metrics"].get("evaluation_artifact"), str)
            and repository.canonical_repo_path(
                measurement["metrics"]["evaluation_artifact"]
            ) == provenance["artifact_path"]
        ),
        None,
    )
    return {
        **{
            key: provenance.get(key)
            for key in ("operation_id", "artifact_index", "artifact_path", "label")
        },
        "recorded_structure": structure,
    }


def _operation_summary(event: dict) -> dict:
    request = event.get("request") or {}
    return {
        **{key: event.get(key) for key in (
            "id", "kind", "status", "session_id", "inquiry_id",
            "completed_at", "supersedes", "superseded_by",
        )},
        "description": request.get("description"),
        "artifact_count": len(_artifact_catalog(event)),
    }


def _pending_summary(pending: dict) -> dict:
    return {
        **{key: pending.get(key) for key in ("id", "kind", "session_id", "inquiry_id")},
        "status": "failed_pending" if pending.get("failure") else "pending",
        "progress": pending["progress"],
        "description": pending["request"][pending["kind"]].get("description"),
        "artifact_count": 0,
        "checkpoint_count": 0,
    }


def _query_metadata(state: dict, args: dict, campaign_id: str) -> str:
    if repository.current_campaign_id(state) != campaign_id:
        raise ValueError("tool campaign does not match the active Runner state")
    events = state.get("operation_events", [])
    pending = state.get("pending_operation")
    if args["action"] == "operations":
        source = [_operation_summary(event) for event in events]
        if isinstance(pending, dict) and not any(
            event["id"] == pending["id"] for event in events
        ):
            source.append(_pending_summary(pending))
        default_path = "/*"
    else:
        identifier = args["operation_id"].strip()
        event = next((item for item in events if item["id"] == identifier), None)
        selected_pending = (
            pending
            if isinstance(pending, dict) and pending["id"] == identifier
            else None
        )
        if event is None and selected_pending is None:
            raise ArtifactUnavailableError("operation_not_found", {"operation_id": identifier})
        source = {
            "operation": _operation_summary(event)
            if event
            else _pending_summary(selected_pending),
            "record": event,
            "artifacts": [
                {"operation_id": identifier, "artifact_index": index, **artifact}
                for index, artifact in enumerate(_artifact_catalog(event))
            ]
            if event
            else [],
            "checkpoints": [
                candidate
                for candidate in state.get("candidates", {}).values()
                if candidate["origin_operation"] == identifier
            ],
            "pending": {
                **{
                    key: selected_pending.get(key)
                    for key in (
                        "id",
                        "kind",
                        "progress",
                        "failure",
                        "request",
                        "request_fingerprint",
                    )
                },
                "measurements": selected_pending["data"].get("measurements", []),
                "completed_measurement_count": len(
                    selected_pending["data"].get("partial_results", [])
                ),
            }
            if selected_pending
            else None,
        }
        source["operation"]["checkpoint_count"] = len(source["checkpoints"])
        default_path = "/operation"
    spec = {**args, "path": args.get("path") or default_path}
    try:
        response, _, _ = _query(
            source, spec, [0], MAX_RESULTS, args["max_bytes"],
        )
    except TraversalBudgetExceededError as error:
        response = {
            "status": "traversal_budget_exhausted", "evidence_state": "not_inspected",
            "error": str(error), "max_traversed_nodes": MAX_NODES,
        }
    if args["action"] == "operations" and response.get("absence_reason") == "path_absent":
        response["recovery"] = (
            "Operation rows are a list (/0, /1, ...), not keyed by ID. Use "
            'where {"path": "/id", "equals": "<ID>"} or action=metadata with operation_id.'
        )
    return json.dumps({
        **response, "action": args["action"], "scope": "recorded_metadata_only",
        "campaign_id": campaign_id, "operation_id": args.get("operation_id"),
        "artifact_contents_inspected": False, "bounded": True,
    })


def _artifact_bytes(
    path: Any,
    provenance: dict[str, Any],
    *,
    offset: int = 0,
    max_bytes: int | None = None,
) -> tuple[bytes, int]:
    """Hash and capture from one stream without loading large artifacts."""
    digest = hashlib.sha256()
    captured = bytearray()
    total = 0
    with path.open("rb") as stream:
        while block := stream.read(HASH_BLOCK_BYTES):
            digest.update(block)
            if max_bytes is None:
                if total + len(block) <= MAX_BYTES:
                    captured.extend(block)
            else:
                start = max(0, offset - total)
                end = min(len(block), offset + max_bytes - total)
                if start < end:
                    captured.extend(block[start:end])
            total += len(block)
    fingerprint = digest.hexdigest()
    provenance["verified_artifact_fingerprint"] = fingerprint
    if provenance["recorded_artifact_fingerprint"] != fingerprint:
        raise FingerprintMismatchError(provenance)
    if max_bytes is None and total > MAX_BYTES:
        raise ArtifactBudgetExceededError(provenance, total)
    return bytes(captured), total


def _read_artifact(path: Any, provenance: dict[str, Any], args: dict) -> dict:
    offset = args["offset"]
    page_limit = (
        MAX_READ_BYTES if args["encoding"] == "utf-8" else MAX_READ_BYTES // 2
    )
    chunk, total = _artifact_bytes(
        path, provenance, offset=offset, max_bytes=min(args["max_bytes"], page_limit)
    )
    expected = args.get("expected_fingerprint")
    if expected and expected != provenance["verified_artifact_fingerprint"]:
        provenance["expected_artifact_fingerprint"] = expected
        raise FingerprintMismatchError(
            provenance, "artifact differs from the expected continuation fingerprint"
        )
    if offset > total:
        raise ValueError(f"offset exceeds artifact size ({total} bytes)")
    preview: dict[str, Any] = {}
    if args["encoding"] == "utf-8":
        content, chunk = utf8_page(chunk, offset + len(chunk) < total)
    else:
        content = base64.b64encode(chunk).decode("ascii")
        try:
            text, preview_bytes = utf8_page(
                chunk, True, MAX_MATCH_OUTPUT_BYTES - len(content) - 64
            )
            preview = {
                "decoded_text": text,
                "decoded_text_bytes": len(preview_bytes),
                "decoded_text_complete": len(preview_bytes) == len(chunk),
            }
        except ValueError:
            preview = {
                "decoded_text": None,
                "decoded_text_bytes": 0,
                "decoded_text_complete": False,
                "decoded_text_reason": "page is not UTF-8 or starts within a character",
            }
    end = offset + len(chunk)
    return {
        "status": "read",
        "action": "read",
        "evidence_state": "inspected",
        "provenance": provenance,
        "encoding": args["encoding"],
        "offset_unit": "original_file_bytes",
        "content": content,
        **preview,
        "offset": offset,
        "returned_bytes": len(chunk),
        "total_bytes": total,
        "remaining_bytes": total - end,
        "next_offset": end if end < total else None,
        "output_truncated": end < total,
        "max_page_bytes": page_limit,
        "bounded": True,
    }


def utf8_page(
    chunk: bytes, more_bytes: bool, byte_limit: int = MAX_MATCH_OUTPUT_BYTES
) -> tuple[str, bytes]:
    """Return complete UTF-8 characters within a serialized-content byte limit."""
    try:
        content = chunk.decode("utf-8")
    except UnicodeDecodeError as error:
        if (
            not more_bytes or error.reason != "unexpected end of data"
            or error.end != len(chunk)
        ):
            raise ValueError(
                "page is not UTF-8 or offset splits a character; use encoding=base64 "
                "or a returned next_offset"
            ) from error
        content = chunk[:error.start].decode("utf-8")
    while (
        len(json.dumps(content, ensure_ascii=False).encode("utf-8"))
        > byte_limit
    ):
        content = content[:len(content) // 2]
    return content, content.encode("utf-8")


def _artifact_value(path: Any, provenance: dict[str, Any], resources: ExitStack) -> Any:
    if path.stat().st_size > MAX_BYTES:
        document = resources.enter_context(JsonDocument(path))
        provenance["verified_artifact_fingerprint"] = document.fingerprint
        if document.fingerprint != provenance["recorded_artifact_fingerprint"]:
            raise FingerprintMismatchError(provenance)
        return document.root()
    data, _ = _artifact_bytes(path, provenance)
    try:
        value = json.loads(data)
    except json.JSONDecodeError as error:
        raise ValueError("artifact is not valid JSON") from error
    return value


def _visit(
    value: Any,
    tokens: list[str],
    current: list[str],
    matches: list[tuple[str, Any]],
    budget: list[int],
) -> None:
    budget[0] += 1
    if budget[0] > MAX_NODES:
        raise TraversalBudgetExceededError(
            "query traversal exceeded the per-query node safety limit"
        )
    if not tokens:
        matches.append((_pointer(current), value))
        return
    head, *tail = tokens
    if head == "*":
        if isinstance(value, (list, JsonArray)):
            for index, child in enumerate(value):
                _visit(child, tail, [*current, str(index)], matches, budget)
        elif isinstance(value, (dict, JsonObject)):
            for key, child in value.items():
                _visit(child, tail, [*current, key], matches, budget)
        return
    if isinstance(value, (list, JsonArray)) and head.isdigit():
        index = int(head)
        if index < len(value):
            _visit(value[index], tail, [*current, head], matches, budget)
    elif isinstance(value, (dict, JsonObject)) and head in value:
        _visit(value[head], tail, [*current, head], matches, budget)


def _matches(
    value: Any, path: str, budget: list[int] | None = None
) -> list[tuple[str, Any]]:
    matches: list[tuple[str, Any]] = []
    _visit(
        value,
        _tokens(path),
        [],
        matches,
        budget if budget is not None else [0],
    )
    return matches


def _discover(
    value: Any, prefix: str, output: list[str], budget: list[int]
) -> None:
    if len(output) >= MAX_PATHS:
        return
    budget[0] += 1
    if budget[0] > MAX_NODES:
        raise TraversalBudgetExceededError(
            "discovery traversal exceeded the node safety limit"
        )
    if value is None or not isinstance(value, (dict, list, JsonObject, JsonArray)):
        output.append(prefix or "/")
        return
    if isinstance(value, (list, JsonArray)):
        if not value:
            output.append(f"{'' if prefix == '/' else prefix}/*")
            return
        seen: set[str] = set()
        array_prefix = f"{'' if prefix == '/' else prefix}/*"
        for child in value:
            child_paths: list[str] = []
            _discover(child, array_prefix, child_paths, budget)
            for child_path in child_paths:
                if child_path not in seen:
                    seen.add(child_path)
                    output.append(child_path)
                    if len(output) >= MAX_PATHS:
                        return
        return
    base = "" if prefix == "/" else prefix
    for key, child in value.items():
        escaped = key.replace("~", "~0").replace("/", "~1")
        _discover(child, f"{base}/{escaped}", output, budget)
        if len(output) >= MAX_PATHS:
            return


def _relative_value(value: Any, path: str, budget: list[int]) -> Any:
    matches = _matches(value, path, budget)
    return scalar_value(matches[0][1]) if matches else MISSING


def _apply_where(
    matches: list[tuple[str, Any]], where: Any, budget: list[int]
) -> list[tuple[str, Any]]:
    if where is None:
        return matches
    if not isinstance(where, dict) or "path" not in where or "equals" not in where:
        raise ValueError("where requires path and equals")
    if not isinstance(where["path"], str) or not where["path"]:
        raise ValueError("where.path must be a non-empty JSON Pointer")
    return [
        match
        for match in matches
        if (
            (relative := _relative_value(match[1], where["path"], budget))
            is not MISSING
            and relative == where["equals"]
        )
    ]


def _available_fields(matches: list[tuple[str, Any]]) -> list[str]:
    fields: set[str] = set()
    for _, value in matches:
        if isinstance(value, (dict, JsonObject)):
            fields.update(
                "/" + key.replace("~", "~0").replace("/", "~1") for key in value
            )
    output = []
    size = 0
    for field in sorted(fields)[:MAX_PATHS]:
        size += len(json.dumps(field).encode("utf-8"))
        if size > DEFAULT_PAGE_BYTES:
            break
        output.append(field)
    return output


def _join_pointer(base: str, relative: str) -> str:
    if relative == "/":
        return base
    if base == "/":
        return relative
    return f"{base.rstrip('/')}{relative}"


def _pattern_path(concrete: str, pattern: str) -> str:
    concrete_tokens = _tokens(concrete)
    pattern_tokens = _tokens(pattern)
    if len(concrete_tokens) != len(pattern_tokens):
        raise ValueError("discovery prefix did not match the resolved path")
    return _pointer(
        [
            "*" if pattern_token == "*" else concrete_token
            for concrete_token, pattern_token in zip(
                concrete_tokens, pattern_tokens, strict=True
            )
        ]
    )


def _select(
    matches: list[tuple[str, Any]], select: Any, budget: list[int]
) -> list[tuple[str, Any]]:
    if select is None:
        return matches
    if not isinstance(select, str) or not select:
        raise ValueError("select must be a non-empty JSON Pointer")
    selected: list[tuple[str, Any]] = []
    for base_path, value in matches:
        for relative_path, selected_value in _matches(value, select, budget):
            selected.append(
                (_join_pointer(base_path, relative_path), selected_value)
            )
    return selected


def _bounded_matches(
    matches: list[tuple[str, Any]], limit: int, byte_limit: int
) -> tuple[list[dict[str, Any]], bool, int]:
    output: list[dict[str, Any]] = []
    size = 0
    for match_path, match_value in matches[:limit]:
        wrapper_size = len(json.dumps(
            {"path": match_path, "value": None}, separators=(",", ":")
        ).encode("utf-8")) - 4
        try:
            match_value = bounded_value(match_value, byte_limit - size - wrapper_size)
        except OutputBudgetExceeded:
            return output, True, size
        item = {"path": match_path, "value": match_value}
        item_size = len(
            json.dumps(item, separators=(",", ":")).encode("utf-8")
        )
        if size + item_size > byte_limit:
            return output, True, size
        output.append(item)
        size += item_size
    return output, False, size


def _bounded_strings(values: list[str]) -> tuple[list[str], bool]:
    output: list[str] = []
    size = 0
    for value in values:
        value_size = len(json.dumps(value).encode("utf-8"))
        if size + value_size > MAX_MATCH_OUTPUT_BYTES:
            return output, True
        output.append(value)
        size += value_size
    return output, False


def _summary(
    values: list[Any],
    aggregate: Any,
    result_limit: int,
    byte_limit: int,
    query_limit: int,
    offset: int = 0,
) -> tuple[dict[str, Any] | None, int, int]:
    if aggregate == "count":
        return {"count": len(values)}, 0, 0
    if aggregate == "value_counts":
        if any(isinstance(value, (dict, list, JsonObject, JsonArray)) for value in values):
            raise ValueError("value_counts requires scalar selected values")
        counts: dict[str, int] = {}
        decoded: dict[str, Any] = {}
        for value in values:
            value = scalar_value(value)
            key = json.dumps(value, sort_keys=True, separators=(",", ":"))
            counts[key] = counts.get(key, 0) + 1
            decoded[key] = value
        output: list[dict[str, Any]] = []
        size = 0
        effective_limit = min(query_limit, result_limit)
        byte_truncated = False
        if offset > len(counts):
            raise ValueError("offset exceeds the distinct value count")
        remaining = len(counts) - offset
        for key, count in list(counts.items())[offset:offset + effective_limit]:
            item = {"value": decoded[key], "count": count}
            item_size = len(
                json.dumps(item, separators=(",", ":")).encode("utf-8")
            )
            if size + item_size > byte_limit:
                byte_truncated = True
                break
            output.append(item)
            size += item_size
        truncation_causes: list[str] = []
        if remaining > query_limit:
            truncation_causes.append("query_limit")
        if result_limit < query_limit and remaining > result_limit:
            truncation_causes.append("batch_result_budget")
        if byte_truncated:
            truncation_causes.append("byte_budget")
        return (
            {
                "counts": output,
                "distinct_count": len(counts),
                "returned_distinct": len(output),
                "offset": offset,
                "remaining_distinct": remaining - len(output),
                "next_offset": (
                    offset + len(output) if len(output) < remaining else None
                ),
                "output_truncated": bool(truncation_causes),
                "truncation_causes": truncation_causes,
                "recovery": (
                    "Continue with next_offset. If no distinct value fits, use "
                    "action=read for the original artifact."
                    if byte_truncated else None
                ),
            },
            len(output),
            size,
        )
    if aggregate == "numeric_summary":
        numbers = [
            value for value in (
                scalar_value(item) if (
                    not isinstance(item, JsonScalar)
                    or item.document.buffer[item.start] != 34
                ) else item
                for item in values
            )
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]
        if not numbers:
            return {"count": len(values), "numeric_values": 0}, 0, 0
        return (
            {
                "count": len(values),
                "numeric_values": len(numbers),
                "min": min(numbers),
                "max": max(numbers),
                "mean": sum(numbers) / len(numbers),
                "nonpositive": sum(value <= 0 for value in numbers),
                "positive": sum(value > 0 for value in numbers),
            },
            0,
            0,
        )
    if aggregate is not None:
        raise ValueError(
            "aggregate must be count, numeric_summary or value_counts"
        )
    return None, 0, 0


def _query(
    value: Any,
    spec: dict[str, Any],
    budget: list[int],
    result_limit: int,
    byte_limit: int,
) -> tuple[dict[str, Any], int, int]:
    path = spec.get("path")
    if not isinstance(path, str) or not path:
        raise ValueError("query requires path")
    query_limit = min(
        max(int(spec.get("limit", DEFAULT_RESULTS)), 1),
        MAX_RESULTS,
    )
    offset = int(spec.get("offset", 0))
    if offset < 0:
        raise ValueError("offset must be nonnegative")
    if offset and spec.get("aggregate") in {"count", "numeric_summary"}:
        raise ValueError("offset applies to raw matches or value_counts only")
    path_matches = _matches(value, path, budget)
    expanded_arrays = 0
    if any(spec.get(key) is not None for key in ("where", "select", "aggregate")):
        row_matches = []
        for base, item in path_matches:
            if isinstance(item, (list, JsonArray)):
                expanded_arrays += 1
                budget[0] += len(item)
                if budget[0] > MAX_NODES:
                    raise TraversalBudgetExceededError(
                        "array row selection exceeded the node safety limit"
                    )
                row_matches.extend(
                    (f"{base.rstrip('/')}/{index}", row)
                    for index, row in enumerate(item)
                )
            else:
                row_matches.append((base, item))
        path_matches = row_matches
    where = spec.get("where")
    if where is not None:
        where = EvidenceFilter.model_validate(where).model_dump()
        present = [
            match
            for match in path_matches
            if _relative_value(match[1], where["path"], budget) is not MISSING
        ]
        if path_matches and not present:
            return (
                {
                    "status": "filter_field_absent",
                    "evidence_state": "absent",
                    "path": path,
                    "filter_path": where["path"],
                    "available_fields": _available_fields(path_matches),
                    "available_fields_scope": "bounded direct-field hints, not exhaustive discovery",
                    "recovery": "Select a filter field present in these rows; no match count was established.",
                    "result": None,
                },
                0,
                0,
            )
        missing_filter_fields = len(path_matches) - len(present)
    else:
        missing_filter_fields = 0
    filtered_matches = _apply_where(path_matches, where, budget)
    matches = _select(filtered_matches, spec.get("select"), budget)
    values = [match[1] for match in matches]
    summary, used_results, used_bytes = _summary(
        values,
        spec.get("aggregate"),
        result_limit,
        byte_limit,
        query_limit,
        offset,
    )
    if summary is None:
        if offset > len(matches):
            raise ValueError("offset exceeds the selected record count")
        remaining = len(matches) - offset
        effective_limit = min(query_limit, result_limit)
        bounded_matches, byte_truncated, used_bytes = _bounded_matches(
            matches[offset:],
            effective_limit,
            byte_limit,
        )
        used_results = len(bounded_matches)
        truncation_causes: list[str] = []
        if remaining > query_limit:
            truncation_causes.append("query_limit")
        if result_limit < query_limit and remaining > result_limit:
            truncation_causes.append("batch_result_budget")
        if byte_truncated:
            truncation_causes.append("byte_budget")
        result: dict[str, Any] = {
            "matches": bounded_matches,
            "returned": used_results,
            "total_matches": len(matches),
            "offset": offset,
            "remaining_matches": remaining - used_results,
            "next_offset": (
                offset + used_results if used_results < remaining else None
            ),
            "output_truncated": bool(truncation_causes),
            "truncation_causes": truncation_causes,
        }
        if byte_truncated:
            result["recovery"] = (
                "Continue with next_offset. If no match fits, use action=read "
                "to retrieve the original artifact in byte pages."
            )
    else:
        result = summary
    selected_field_absent = (
        bool(filtered_matches)
        and spec.get("select") is not None
        and not matches
    )
    field_absent = (not path_matches and not expanded_arrays) or selected_field_absent
    response: dict[str, Any] = {
        "status": "field_absent" if field_absent else "queried",
        "evidence_state": "absent" if field_absent else "inspected",
        "path": path,
        "result": result,
    }
    if expanded_arrays:
        response["array_rows_expanded"] = expanded_arrays
    if missing_filter_fields:
        response["rows_missing_filter_field"] = missing_filter_fields
    if not path_matches and not expanded_arrays:
        response["absence_reason"] = "path_absent"
    elif selected_field_absent:
        response["absence_reason"] = "selected_field_absent"
        response["available_fields"] = _available_fields(filtered_matches)
        response["available_fields_scope"] = (
            "bounded direct-field hints, not exhaustive discovery"
        )
        response["recovery"] = "Select a field present in these rows."
    return response, used_results, used_bytes


def _query_echo(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        key: spec[key]
        for key in ("path", "where", "select", "aggregate", "offset")
        if spec.get(key) is not None
    }


def _budget_exhausted_response(
    index: int,
    spec: dict[str, Any],
    exhausted_limits: list[str],
) -> dict[str, Any]:
    return {
        "index": index,
        "status": "budget_exhausted",
        "evidence_state": "not_inspected",
        **_query_echo(spec),
        "limits": exhausted_limits,
    }


def query_artifact(args: dict[str, Any], campaign_id: str) -> str:
    with ExitStack() as resources:
        return _query_artifact(args, campaign_id, resources)


def _query_artifact(args: dict[str, Any], campaign_id: str, resources: ExitStack) -> str:
    provenance: dict[str, Any] = {}
    try:
        if args.get("action") != "batch":
            args = ArtifactEvidenceQueryParams.model_validate(args).model_dump()
        else:
            artifact_index = int(args.get("artifact_index", 0))
            if not 0 <= artifact_index < MAX_ARTIFACTS_PER_OPERATION:
                raise ValueError("artifact_index is outside the supported range")
        state = repository.load_state(allow_missing_artifact=True)
        action = args.get("action")
        if action in {"operations", "metadata"}:
            return _query_metadata(state, args, campaign_id)
        operation_id = args.get("operation_id")
        if not isinstance(operation_id, str) or not operation_id.strip():
            raise ValueError("operation_id must be non-empty")
        artifact_index = int(args.get("artifact_index", 0))
        artifact_path, provenance = _recorded_artifact(
            state,
            campaign_id,
            operation_id.strip(),
            artifact_index,
        )
        if action == "read":
            return json.dumps(
                _read_artifact(artifact_path, provenance, args), ensure_ascii=False
            )
        value = _artifact_value(artifact_path, provenance, resources)
        if action == "discover":
            prefix = args.get("prefix") or "/"
            budget = [0]
            paths: list[str] = []
            seen: set[str] = set()
            root_paths: list[str] = []
            try:
                roots = _matches(value, prefix, budget)
                for path, root in roots:
                    root_paths = []
                    _discover(
                        root,
                        _pattern_path(path, prefix),
                        root_paths,
                        budget,
                    )
                    for discovered_path in root_paths:
                        if discovered_path in seen:
                            continue
                        seen.add(discovered_path)
                        paths.append(discovered_path)
                        if len(paths) >= MAX_PATHS:
                            break
                    if len(paths) >= MAX_PATHS:
                        break
            except TraversalBudgetExceededError as error:
                partial = paths + [item for item in root_paths if item not in seen]
                bounded_partial, _ = _bounded_strings(partial[:MAX_PATHS])
                return json.dumps(
                    {
                        "status": "traversal_budget_exhausted",
                        "action": "discover",
                        "evidence_state": (
                            "present_not_inspected" if partial else "not_inspected"
                        ),
                        "provenance": provenance,
                        "prefix": prefix,
                        "partial_paths": bounded_partial,
                        "partial_paths_complete": False,
                        "limit": "max_traversed_nodes",
                        "max_traversed_nodes": MAX_NODES,
                        "error": str(error),
                        "recovery": (
                            "partial_paths were found before the limit and are "
                            "incomplete. Discover a narrower prefix, query known "
                            "paths directly, or read the recorded structure with "
                            "action=metadata, path=/record/result/measurements/"
                            "<index>/metrics/evaluation_artifact_contents."
                        ),
                        "bounded": True,
                    }
                )
            bounded_paths, byte_truncated = _bounded_strings(paths)
            return json.dumps(
                {
                    "status": ("discovered" if roots else "field_absent"),
                    "action": "discover",
                    "evidence_state": ("present_not_inspected" if roots else "absent"),
                    "provenance": provenance,
                    "prefix": prefix,
                    "paths": bounded_paths,
                    "truncated": (len(paths) >= MAX_PATHS or byte_truncated),
                    "remaining_paths": None,
                    "limits": {
                        "max_paths": MAX_PATHS,
                        "max_result_bytes": MAX_MATCH_OUTPUT_BYTES,
                        "max_traversed_nodes": MAX_NODES,
                    },
                    "recovery": (
                        "Discovery is bounded; remaining path count is unknown. "
                        "Narrow prefix or use action=read for the entire artifact."
                    ),
                    "bounded": True,
                }
            )
        if action == "query":
            try:
                response, _, _ = _query(
                    value,
                    args,
                    [0],
                    MAX_RESULTS,
                    int(args.get("max_bytes", DEFAULT_PAGE_BYTES)),
                )
            except TraversalBudgetExceededError as error:
                return json.dumps(
                    {
                        "status": "traversal_budget_exhausted",
                        "action": "query",
                        "evidence_state": "not_inspected",
                        "provenance": provenance,
                        **_query_echo(args),
                        "limit": "max_traversed_nodes",
                        "max_traversed_nodes": MAX_NODES,
                        "error": str(error),
                        "recovery": "Narrow the path or use action=read for the raw artifact.",
                        "bounded": True,
                    }
                )
            for key in ("where", "select", "aggregate"):
                if args.get(key) is not None:
                    response[key] = args[key]
            return json.dumps(
                {
                    "status": response.pop("status"),
                    "action": "query",
                    "provenance": provenance,
                    **response,
                    "bounded": True,
                }
            )
        queries = args.get("queries")
        if not isinstance(queries, list) or not queries:
            raise ValueError("batch action requires queries")
        if len(queries) > MAX_BATCH_QUERIES:
            raise ValueError(
                f"batch exceeds the {MAX_BATCH_QUERIES} query safety limit"
            )
        remaining_results = MAX_BATCH_RESULTS
        page_bytes = int(args.get("max_bytes", DEFAULT_PAGE_BYTES))
        if not 1 <= page_bytes <= MAX_READ_BYTES:
            raise ValueError("max_bytes is outside the supported page range")
        remaining_bytes = page_bytes
        responses: list[dict[str, Any]] = []
        failures = 0
        for index, spec in enumerate(queries):
            if not isinstance(spec, dict):
                responses.append(
                    {
                        "index": index,
                        "status": "query_failed",
                        "error": "query specification must be an object",
                    }
                )
                failures += 1
                continue
            exhausted_limits: list[str] = []
            if remaining_results <= 0:
                exhausted_limits.append("batch_result_budget")
            if remaining_bytes <= 0:
                exhausted_limits.append("byte_budget")
            if exhausted_limits:
                responses.append(
                    _budget_exhausted_response(
                        index,
                        spec,
                        exhausted_limits,
                    )
                )
                failures += 1
                continue
            try:
                spec = ArtifactEvidenceQuerySpec.model_validate(spec).model_dump()
                query_limit = min(
                    max(int(spec.get("limit", DEFAULT_RESULTS)), 1),
                    MAX_RESULTS,
                )
                remaining_specs = len(queries) - index
                fair_result_share = min(
                    query_limit,
                    (remaining_results + remaining_specs - 1) // remaining_specs,
                )
                response, used_results, used_bytes = _query(
                    value,
                    spec,
                    [0],
                    fair_result_share,
                    remaining_bytes,
                )
                remaining_results -= used_results
                remaining_bytes -= used_bytes
                responses.append(
                    {
                        "index": index,
                        **response,
                        **_query_echo(spec),
                    }
                )
            except TraversalBudgetExceededError as error:
                responses.append(
                    {
                        "index": index,
                        "status": "traversal_budget_exhausted",
                        "evidence_state": "not_inspected",
                        **_query_echo(spec),
                        "limit": "max_traversed_nodes_per_query",
                        "max_traversed_nodes": MAX_NODES,
                        "error": str(error),
                        "recovery": "Narrow the path or use action=read for the raw artifact.",
                    }
                )
                failures += 1
            except (TypeError, ValueError) as error:
                failure = {
                    "index": index,
                    "status": "query_failed",
                    "error": str(error),
                    **_query_echo(spec),
                }
                responses.append(failure)
                failures += 1
        return json.dumps(
            {
                "status": (
                    "batch_completed_with_failures" if failures else "batch_queried"
                ),
                "action": "batch",
                "provenance": provenance,
                "query_count": len(queries),
                "queries": responses,
                "limits": {
                    "max_queries": MAX_BATCH_QUERIES,
                    "max_returned_results": MAX_BATCH_RESULTS,
                    "max_traversed_nodes_per_query": MAX_NODES,
                    "max_total_traversed_nodes": (MAX_BATCH_QUERIES * MAX_NODES),
                    "max_result_bytes": page_bytes,
                },
                "bounded": True,
            }
        )
    except ArtifactBudgetExceededError as error:
        return json.dumps(
            {
                "status": "artifact_budget_exhausted",
                "evidence_state": "not_inspected",
                "provenance": error.provenance,
                "total_bytes": error.total_bytes,
                "max_query_bytes": MAX_BYTES,
                "recovery": "Use action=read to retrieve all original bytes in pages.",
                "bounded": True,
            }
        )
    except ArtifactUnavailableError as error:
        return json.dumps(
            {
                "status": "artifact_unavailable",
                "reason": error.reason,
                "provenance": error.provenance,
                "bounded": True,
            }
        )
    except FingerprintMismatchError as error:
        return json.dumps(
            {
                "status": "fingerprint_mismatch",
                "reason": str(error),
                "provenance": error.provenance,
                "bounded": True,
            }
        )
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        return json.dumps(
            {
                "status": "query_failed",
                "error": str(error),
                "provenance": provenance,
                "bounded": True,
            }
        )
