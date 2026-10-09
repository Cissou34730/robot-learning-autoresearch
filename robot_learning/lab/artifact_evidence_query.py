"""Bounded, read-only access to completed JSON evidence artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
MAX_BYTES = 32 * 1024 * 1024
MAX_NODES = 50_000
MAX_PATHS = 500
MAX_RESULTS = 200


class ArtifactEvidenceQueryParams(BaseModel):
    action: Literal["discover", "query"]
    artifact_path: str
    operation_id: str | None = None
    expected_fingerprint: str | None = None
    prefix: str | None = None
    path: str | None = None
    where: dict[str, Any] | None = None
    aggregate: Literal["count", "numeric_summary", "value_counts"] | None = None
    limit: int = Field(default=MAX_RESULTS, ge=1, le=MAX_RESULTS)


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


def _artifact_path(value: Any) -> tuple[Path, str]:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError("artifact_path must be a repository-relative path")
    candidate = (ROOT / value).resolve()
    relative = candidate.relative_to(ROOT).as_posix()
    if not (
        relative.startswith("campaigns/evaluations/")
        or relative.startswith("campaigns/checkpoints/")
    ):
        raise ValueError(
            "artifact_path must be under campaigns/evaluations or "
            "campaigns/checkpoints"
        )
    if candidate.suffix.lower() != ".json":
        raise ValueError("artifact_path must identify a JSON artifact")
    return candidate, relative


def _load(args: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    path, relative = _artifact_path(args.get("artifact_path"))
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        raise ValueError(f"artifact exceeds the {MAX_BYTES} byte safety limit")
    fingerprint = hashlib.sha256(data).hexdigest()
    expected = args.get("expected_fingerprint")
    if expected and expected != fingerprint:
        raise ValueError(
            f"artifact fingerprint mismatch: expected {expected}, got {fingerprint}"
        )
    try:
        value = json.loads(data)
    except json.JSONDecodeError as error:
        raise ValueError("artifact is not valid JSON") from error
    return value, {
        "operation_id": args.get("operation_id"),
        "artifact_path": relative,
        "artifact_fingerprint": fingerprint,
    }


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
        return
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
    return matches[0][1] if matches else None


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
        if _relative_value(match[1], where["path"]) == where["equals"]
    ]


def _summary(values: list[Any], aggregate: Any) -> dict[str, Any] | None:
    if aggregate == "count":
        return {"count": len(values)}
    if aggregate == "value_counts":
        counts: dict[str, int] = {}
        decoded: dict[str, Any] = {}
        for value in values:
            key = json.dumps(value, sort_keys=True, separators=(",", ":"))
            counts[key] = counts.get(key, 0) + 1
            decoded[key] = value
        return {
            "counts": [
                {"value": decoded[key], "count": count}
                for key, count in list(counts.items())[:MAX_RESULTS]
            ],
            "distinct_count": len(counts),
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


def query_artifact(args: dict[str, Any]) -> str:
    action = args.get("action")
    if action not in {"discover", "query"}:
        raise ValueError("action must be discover or query")
    value, provenance = _load(args)
    if action == "discover":
        prefix = args.get("prefix") or "/"
        roots = _matches(value, prefix)
        paths: list[str] = []
        for path, root in roots:
            _discover(root, path, paths, [0])
            if len(paths) >= MAX_PATHS:
                break
        return json.dumps({
            "status": "queried",
            "action": "discover",
            "provenance": provenance,
            "paths": paths,
            "truncated": len(paths) >= MAX_PATHS,
        })
    path = args.get("path")
    if not isinstance(path, str) or not path:
        raise ValueError("query action requires path")
    matches = _apply_where(_matches(value, path), args.get("where"))
    values = [match[1] for match in matches]
    summary = _summary(values, args.get("aggregate"))
    if summary is None:
        limit = min(max(int(args.get("limit", MAX_RESULTS)), 1), MAX_RESULTS)
        result: dict[str, Any] = {
            "matches": [
                {"path": match_path, "value": match_value}
                for match_path, match_value in matches[:limit]
            ],
            "returned": min(limit, len(matches)),
            "total_matches": len(matches),
        }
    else:
        result = summary
    return json.dumps({
        "status": "queried" if matches else "field_absent",
        "action": "query",
        "provenance": provenance,
        "path": path,
        "where": args.get("where"),
        "aggregate": args.get("aggregate"),
        "result": result,
        "bounded": True,
    })
