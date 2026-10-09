"""Bounded, read-only access to completed JSON evidence artifacts."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from runner import repository

MAX_BYTES = 32 * 1024 * 1024
MAX_NODES = 50_000
MAX_PATHS = 500
MAX_RESULTS = 200
MAX_ARTIFACTS_PER_OPERATION = 100
MAX_MATCH_OUTPUT_BYTES = 128 * 1024
MISSING = object()


class ArtifactEvidenceQueryParams(BaseModel):
    action: Literal["discover", "query"]
    operation_id: str = Field(
        description="Completed measurement operation that recorded the artifact."
    )
    artifact_index: int = Field(
        default=0,
        ge=0,
        le=MAX_ARTIFACTS_PER_OPERATION - 1,
        description=(
            "Zero-based recorded artifact index when the operation produced "
            "multiple measurements."
        ),
    )
    prefix: str | None = None
    path: str | None = None
    where: dict[str, Any] | None = None
    select: str | None = Field(
        default=None,
        description=(
            "Optional JSON Pointer relative to each path match, applied after "
            "where filtering."
        ),
    )
    aggregate: Literal["count", "numeric_summary", "value_counts"] | None = None
    limit: int = Field(default=MAX_RESULTS, ge=1, le=MAX_RESULTS)


class ArtifactUnavailableError(Exception):
    def __init__(self, reason: str, provenance: dict[str, Any] | None = None):
        super().__init__(reason)
        self.reason = reason
        self.provenance = provenance or {}


class FingerprintMismatchError(Exception):
    def __init__(self, provenance: dict[str, Any]):
        super().__init__("artifact fingerprint differs from the recorded fingerprint")
        self.provenance = provenance


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
    artifacts: list[dict[str, Any]] = []
    for measurement in measurements:
        metrics = (
            measurement.get("metrics") if isinstance(measurement, dict) else None
        )
        if not isinstance(metrics, dict):
            continue
        artifact_path = metrics.get("evaluation_artifact")
        fingerprint = metrics.get("evaluation_artifact_fingerprint")
        if not isinstance(artifact_path, str) or not artifact_path:
            continue
        if not isinstance(fingerprint, str) or not fingerprint:
            continue
        artifacts.append(
            {
                "artifact_path": artifact_path,
                "recorded_artifact_fingerprint": fingerprint,
                "instrument": measurement.get("instrument"),
                "label": measurement.get("label"),
            }
        )
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
    provenance = {
        **event_provenance,
        "artifact_index": artifact_index,
        "artifact_count": len(artifacts),
        "instrument": selected["instrument"],
        "label": selected["label"],
        "artifact_path": relative,
        "recorded_artifact_fingerprint": selected[
            "recorded_artifact_fingerprint"
        ],
    }
    if not path.is_file():
        raise ArtifactUnavailableError("artifact_file_unavailable", provenance)
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        raise ValueError(f"artifact exceeds the {MAX_BYTES} byte safety limit")
    fingerprint = hashlib.sha256(data).hexdigest()
    provenance["verified_artifact_fingerprint"] = fingerprint
    if selected["recorded_artifact_fingerprint"] != fingerprint:
        raise FingerprintMismatchError(provenance)
    try:
        value = json.loads(data)
    except json.JSONDecodeError as error:
        raise ValueError("artifact is not valid JSON") from error
    return value, provenance


def _visit(
    value: Any,
    tokens: list[str],
    current: list[str],
    matches: list[tuple[str, Any]],
    budget: list[int],
) -> None:
    budget[0] += 1
    if budget[0] > MAX_NODES:
        raise ValueError("query traversal exceeded the node safety limit")
    if not tokens:
        matches.append((_pointer(current), value))
        return
    head, *tail = tokens
    if head == "*":
        if isinstance(value, list):
            for index, child in enumerate(value):
                _visit(child, tail, [*current, str(index)], matches, budget)
        elif isinstance(value, dict):
            for key, child in value.items():
                _visit(child, tail, [*current, key], matches, budget)
        return
    if isinstance(value, list) and head.isdigit():
        index = int(head)
        if index < len(value):
            _visit(value[index], tail, [*current, head], matches, budget)
    elif isinstance(value, dict) and head in value:
        _visit(value[head], tail, [*current, head], matches, budget)


def _matches(value: Any, path: str) -> list[tuple[str, Any]]:
    matches: list[tuple[str, Any]] = []
    _visit(value, _tokens(path), [], matches, [0])
    return matches


def _discover(
    value: Any, prefix: str, output: list[str], budget: list[int]
) -> None:
    if len(output) >= MAX_PATHS:
        return
    budget[0] += 1
    if budget[0] > MAX_NODES:
        raise ValueError("discovery traversal exceeded the node safety limit")
    if value is None or not isinstance(value, (dict, list)):
        output.append(prefix or "/")
        return
    if isinstance(value, list):
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


def _relative_value(value: Any, path: str) -> Any:
    matches = _matches(value, path)
    return matches[0][1] if matches else MISSING


def _apply_where(
    matches: list[tuple[str, Any]], where: Any
) -> list[tuple[str, Any]]:
    if where is None:
        return matches
    if not isinstance(where, dict) or "path" not in where or "equals" not in where:
        raise ValueError("where requires path and equals")
    return [
        match
        for match in matches
        if (
            (relative := _relative_value(match[1], where["path"])) is not MISSING
            and relative == where["equals"]
        )
    ]


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
    matches: list[tuple[str, Any]], select: Any
) -> list[tuple[str, Any]]:
    if select is None:
        return matches
    if not isinstance(select, str) or not select:
        raise ValueError("select must be a non-empty JSON Pointer")
    selected: list[tuple[str, Any]] = []
    for base_path, value in matches:
        for relative_path, selected_value in _matches(value, select):
            selected.append(
                (_join_pointer(base_path, relative_path), selected_value)
            )
    return selected


def _bounded_matches(
    matches: list[tuple[str, Any]], limit: int
) -> tuple[list[dict[str, Any]], bool]:
    output: list[dict[str, Any]] = []
    size = 0
    for match_path, match_value in matches[:limit]:
        item = {"path": match_path, "value": match_value}
        item_size = len(
            json.dumps(item, separators=(",", ":")).encode("utf-8")
        )
        if size + item_size > MAX_MATCH_OUTPUT_BYTES:
            return output, True
        output.append(item)
        size += item_size
    return output, len(matches) > len(output)


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


def _summary(values: list[Any], aggregate: Any) -> dict[str, Any] | None:
    if aggregate == "count":
        return {"count": len(values)}
    if aggregate == "value_counts":
        if any(isinstance(value, (dict, list)) for value in values):
            raise ValueError("value_counts requires scalar selected values")
        counts: dict[str, int] = {}
        decoded: dict[str, Any] = {}
        for value in values:
            key = json.dumps(value, sort_keys=True, separators=(",", ":"))
            counts[key] = counts.get(key, 0) + 1
            decoded[key] = value
        output: list[dict[str, Any]] = []
        size = 0
        for key, count in list(counts.items())[:MAX_RESULTS]:
            item = {"value": decoded[key], "count": count}
            item_size = len(
                json.dumps(item, separators=(",", ":")).encode("utf-8")
            )
            if size + item_size > MAX_MATCH_OUTPUT_BYTES:
                break
            output.append(item)
            size += item_size
        return {
            "counts": output,
            "distinct_count": len(counts),
            "returned_distinct": len(output),
            "output_truncated": len(output) < len(counts),
        }
    if aggregate == "numeric_summary":
        numbers = [
            value for value in values
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]
        if not numbers:
            return {"count": len(values), "numeric_values": 0}
        return {
            "count": len(values),
            "numeric_values": len(numbers),
            "min": min(numbers),
            "max": max(numbers),
            "mean": sum(numbers) / len(numbers),
            "nonpositive": sum(value <= 0 for value in numbers),
            "positive": sum(value > 0 for value in numbers),
        }
    if aggregate is not None:
        raise ValueError(
            "aggregate must be count, numeric_summary or value_counts"
        )
    return None


def query_artifact(args: dict[str, Any], campaign_id: str) -> str:
    try:
        state = repository.load_state(allow_missing_artifact=True)
        action = args.get("action")
        if action not in {"discover", "query"}:
            raise ValueError("action must be discover or query")
        operation_id = args.get("operation_id")
        if not isinstance(operation_id, str) or not operation_id.strip():
            raise ValueError("operation_id must be non-empty")
        artifact_index = int(args.get("artifact_index", 0))
        value, provenance = _recorded_artifact(
            state,
            campaign_id,
            operation_id.strip(),
            artifact_index,
        )
        if action == "discover":
            prefix = args.get("prefix") or "/"
            roots = _matches(value, prefix)
            paths: list[str] = []
            seen: set[str] = set()
            budget = [0]
            for path, root in roots:
                root_paths: list[str] = []
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
            bounded_paths, byte_truncated = _bounded_strings(paths)
            return json.dumps(
                {
                    "status": (
                        "discovered" if roots else "field_absent"
                    ),
                    "action": "discover",
                    "evidence_state": (
                        "present_not_inspected" if roots else "absent"
                    ),
                    "provenance": provenance,
                    "prefix": prefix,
                    "paths": bounded_paths,
                    "truncated": (
                        len(paths) >= MAX_PATHS or byte_truncated
                    ),
                    "bounded": True,
                }
            )
        path = args.get("path")
        if not isinstance(path, str) or not path:
            raise ValueError("query action requires path")
        path_matches = _matches(value, path)
        filtered_matches = _apply_where(path_matches, args.get("where"))
        matches = _select(filtered_matches, args.get("select"))
        values = [match[1] for match in matches]
        summary = _summary(values, args.get("aggregate"))
        if summary is None:
            limit = min(
                max(int(args.get("limit", MAX_RESULTS)), 1), MAX_RESULTS
            )
            bounded_matches, output_truncated = _bounded_matches(matches, limit)
            result: dict[str, Any] = {
                "matches": bounded_matches,
                "returned": len(bounded_matches),
                "total_matches": len(matches),
                "output_truncated": output_truncated,
            }
        else:
            result = summary
        selected_field_absent = (
            bool(filtered_matches)
            and args.get("select") is not None
            and not matches
        )
        field_absent = not path_matches or selected_field_absent
        return json.dumps(
            {
                "status": "field_absent" if field_absent else "queried",
                "action": "query",
                "evidence_state": "absent" if field_absent else "inspected",
                "absence_reason": (
                    "path_absent"
                    if not path_matches
                    else "selected_field_absent"
                    if selected_field_absent
                    else None
                ),
                "provenance": provenance,
                "path": path,
                "where": args.get("where"),
                "select": args.get("select"),
                "aggregate": args.get("aggregate"),
                "result": result,
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
                "bounded": True,
            }
        )
