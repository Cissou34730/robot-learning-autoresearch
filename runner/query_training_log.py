"""Query metric snapshots or retrieve preserved raw logs for a training operation."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from robot_learning.training.progress import parse_training_records
from runner import paths, repository
from runner.artifact_evidence_query import utf8_page

MAX_PARSE_BYTES = 32 * 1024 * 1024
MAX_OUTPUT_BYTES = 128 * 1024
MAX_READ_BYTES = MAX_OUTPUT_BYTES // 4 * 3
MAX_RECORDS = 200
DEFAULT_RECORDS = 20
DEFAULT_PAGE_BYTES = 16 * 1024
HASH_BLOCK_BYTES = 1024 * 1024


class TrainingLogQueryParams(BaseModel):
    model_config = {"extra": "forbid"}

    action: Literal["discover", "records", "raw"] = Field(
        default="discover",
        description=(
            "discover returns attempt, timestep and metric names without record values. "
            "records parses preserved metric snapshots, filters timesteps and "
            "projects metrics before paging. raw retrieves original log bytes "
            "in readable UTF-8 pages (or base64 for arbitrary bytes), without "
            "parsing or summarizing. Repeat with next_offset and fingerprints; "
            "concatenate page content for the entire log. "
            "Failed training logs are execution history, not scientific evidence."
        ),
    )
    operation_id: str = Field(
        pattern=r"^T[1-9]\d*$",
        description=(
            "Training operation in the active campaign: completed, recorded "
            "failed, or pending with a recorded failure. Running operations "
            "without failure are not readable through this tool."
        ),
    )
    attempts: list[int] | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description=(
            "Attempt numbers to inspect. Omit for all attempts in records mode. "
            "raw requires one attempt when multiple logs exist. Available "
            "attempts and log fingerprints are returned. Attempt outcomes are "
            "not recorded; operation status does not establish each attempt's outcome."
        ),
    )
    from_step: int = Field(
        default=0, ge=0, description="Inclusive lower timestep bound for records."
    )
    to_step: int | None = Field(
        default=None,
        ge=0,
        description="Inclusive upper timestep bound for records; omit for all later steps.",
    )
    metrics: list[str] | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description=(
            "Exact metric names to project in records mode. Discover names first "
            "when unknown. Missing metrics are null and explicitly listed, not zero."
        ),
    )
    all_metrics: bool = Field(
        default=False,
        description="Explicitly request all metric columns in records mode instead of metrics.",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description=(
            "records: selected row offset after timestep filtering. raw: "
            "original file byte offset. Continue with next_offset."
        ),
    )
    limit: int = Field(
        default=DEFAULT_RECORDS,
        ge=1,
        le=MAX_RECORDS,
        description="Maximum selected records per page; repeat for remaining rows.",
    )
    max_bytes: int = Field(
        default=DEFAULT_PAGE_BYTES,
        ge=1,
        le=MAX_READ_BYTES,
        description="Page budget for selected record values or original raw bytes.",
    )
    encoding: Literal["utf-8", "base64"] = Field(
        default="utf-8",
        description=(
            "raw: readable UTF-8 pages on character boundaries, or exact base64 "
            "bytes with a UTF-8 preview where possible if the log is not UTF-8. "
            "Offsets always count original bytes."
        ),
    )
    expected_fingerprint: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
        description=(
            "SHA256 from the previous raw page; required for nonzero raw "
            "offsets. A changed log refuses continuation; restart at offset zero."
        ),
    )
    expected_log_fingerprints: dict[int, str] | None = Field(
        default=None,
        description=(
            "records: attempt-to-SHA256 mapping from provenance.logs. Required "
            "for nonzero record offsets, to refuse pages from changed logs or "
            "a changed attempt selection."
        ),
    )

    @model_validator(mode="after")
    def validate_scope(self) -> "TrainingLogQueryParams":
        if self.to_step is not None and self.to_step < self.from_step:
            raise ValueError("timestep bounds must satisfy from_step <= to_step")
        if self.attempts is not None and (
            any(attempt < 1 for attempt in self.attempts)
            or len(set(self.attempts)) != len(self.attempts)
        ):
            raise ValueError("attempts must contain distinct positive integers")
        if self.metrics is not None and (
            any(not metric.strip() or len(metric) > 256 for metric in self.metrics)
            or len(set(self.metrics)) != len(self.metrics)
        ):
            raise ValueError("metrics must contain distinct non-empty metric names")
        if self.action == "raw":
            if (
                self.metrics is not None
                or self.all_metrics
                or self.from_step
                or self.to_step is not None
            ):
                raise ValueError(
                    "raw byte ranges do not accept timestep or metric filters"
                )
            if self.offset and not self.expected_fingerprint:
                raise ValueError("raw continuation requires expected_fingerprint")
            if self.encoding == "utf-8" and self.max_bytes < 4:
                raise ValueError("UTF-8 raw retrieval requires max_bytes >= 4")
        elif self.action == "discover":
            if self.metrics is not None or self.all_metrics or self.offset:
                raise ValueError(
                    "discover returns metadata; selection requires records"
                )
        elif self.metrics is None and not self.all_metrics:
            raise ValueError(
                "records requires metrics or explicit all_metrics=true; use discover for names"
            )
        elif self.metrics is not None and self.all_metrics:
            raise ValueError("records accepts metrics or all_metrics, not both")
        if (
            self.action == "records"
            and self.offset
            and not self.expected_log_fingerprints
        ):
            raise ValueError("record continuation requires expected_log_fingerprints")
        if self.expected_log_fingerprints is not None and any(
            attempt < 1 or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None
            for attempt, fingerprint in self.expected_log_fingerprints.items()
        ):
            raise ValueError(
                "expected_log_fingerprints requires positive attempts and SHA256 values"
            )
        return self


def training_log_paths(
    operation_id: str, *, state: dict[str, Any] | None = None
) -> list[tuple[int, Path]]:
    if re.fullmatch(r"T[1-9]\d*", operation_id) is None:
        raise ValueError("operation_id must be a training operation ID")
    if state is None:
        state = repository.load_state(allow_missing_artifact=True)
    campaign_id = repository.current_campaign_id(state)
    if (
        not campaign_id
        or campaign_id in {".", ".."}
        or any(character in campaign_id for character in "/\\:")
    ):
        raise ValueError("active campaign ID is not a safe directory name")
    directory = paths.TRAINING_LOG_DIR / campaign_id
    stem = operation_id.lower()
    pattern = re.compile(rf"^{re.escape(stem)}-attempt-(\d+)\.log$")
    logs: list[tuple[int, Path]] = []
    for log_path in directory.glob(f"{stem}-attempt-*.log"):
        match = pattern.match(log_path.name)
        if match is not None and int(match.group(1)) > 0:
            relative = repository.repo_relative_path(log_path.resolve())
            if relative != (
                f"campaigns/training_logs/{campaign_id}/{log_path.name}"
            ):
                raise ValueError("training log is outside its campaign log directory")
            if not log_path.is_file():
                continue
            attempt = int(match.group(1))
            if any(previous == attempt for previous, _ in logs):
                raise ValueError("multiple preserved logs claim the same attempt")
            logs.append((attempt, log_path))
    return sorted(logs)


def selected_records(
    operation_id: str,
    first_step: int,
    last_step: int | None,
    *,
    logs: list[tuple[int, Path]] | None = None,
    texts: dict[int, str] | None = None,
) -> list[tuple[int, dict[str, float]]]:
    records = []
    for attempt, log_path in (
        training_log_paths(operation_id) if logs is None else logs
    ):
        text = (
            log_path.read_text(encoding="utf-8")
            if texts is None
            else texts[attempt]
        )
        for record in parse_training_records(text):
            timestep = record.get("total_timesteps")
            if (
                timestep is not None
                and first_step <= timestep
                and (last_step is None or timestep <= last_step)
            ):
                records.append((attempt, record))
    return records


def _training_operation(state: dict, operation_id: str) -> dict[str, Any]:
    event = next(
        (
            event for event in state.get("operation_events", [])
            if event["id"] == operation_id
        ),
        None,
    )
    if event is not None:
        if event.get("kind") != "training":
            raise ValueError("operation is not training")
        if event.get("status") not in {"completed", "failed"}:
            raise ValueError("training operation is neither completed nor failed")
        return {
            "operation_status": event["status"],
            "operation_error": event.get("error"),
            "execution_history_only": event["status"] == "failed",
        }
    pending = state.get("pending_operation")
    if isinstance(pending, dict) and pending.get("id") == operation_id:
        if pending.get("kind") != "training" or not pending.get("failure"):
            raise ValueError("pending operation is not a failed training operation")
        return {
            "operation_status": "failed_pending",
            "operation_error": pending["failure"],
            "execution_history_only": True,
        }
    raise ValueError("training operation not found in the active campaign")


def _log_bytes(
    path: Path, offset: int = 0, max_bytes: int | None = None
) -> tuple[bytes, dict[str, Any]]:
    digest = hashlib.sha256()
    content = bytearray()
    total = 0
    with path.open("rb") as stream:
        while block := stream.read(HASH_BLOCK_BYTES):
            digest.update(block)
            if max_bytes is None:
                if total + len(block) <= MAX_PARSE_BYTES:
                    content.extend(block)
            else:
                start = max(0, offset - total)
                end = min(len(block), offset + max_bytes - total)
                if start < end:
                    content.extend(block[start:end])
            total += len(block)
    return bytes(content), {
        "log_path": repository.repo_relative_path(path),
        "content_fingerprint": digest.hexdigest(),
        "fingerprint_source": "current_preserved_file",
        "attempt_outcome": "not_recorded",
        "total_bytes": total,
    }


def query_training_log(args: dict[str, Any], campaign_id: str) -> str:
    """Native custom-tool handler; it never executes commands or accepts paths."""
    provenance: dict[str, Any] = {"campaign_id": campaign_id}
    try:
        params = TrainingLogQueryParams.model_validate(args)
        state = repository.load_state(allow_missing_artifact=True)
        if not campaign_id or repository.current_campaign_id(state) != campaign_id:
            raise ValueError("tool campaign does not match the active Runner state")
        provenance.update(
            operation_id=params.operation_id,
            operation_kind="training",
            **_training_operation(state, params.operation_id),
        )
        logs = training_log_paths(params.operation_id, state=state)
        available_attempts = [attempt for attempt, _ in logs]
        provenance["available_attempts"] = available_attempts
        if params.attempts is not None:
            missing = sorted(set(params.attempts) - set(available_attempts))
            if missing:
                return json.dumps(
                    {
                        "status": "logs_unavailable",
                        "missing_attempts": missing,
                        "provenance": provenance,
                    }
                )
            logs = [item for item in logs if item[0] in params.attempts]
        if not logs:
            return json.dumps({"status": "no_logs", "provenance": provenance})
        if params.action == "raw":
            if len(logs) != 1:
                raise ValueError("raw requires selecting one available attempt")
            attempt, path = logs[0]
            page_limit = (
                MAX_READ_BYTES if params.encoding == "utf-8" else MAX_READ_BYTES // 2
            )
            content, identity = _log_bytes(
                path, params.offset, min(params.max_bytes, page_limit)
            )
            provenance["logs"] = [{"attempt": attempt, **identity}]
            if (
                params.expected_fingerprint
                and params.expected_fingerprint != identity["content_fingerprint"]
            ):
                return json.dumps(
                    {
                        "status": "fingerprint_mismatch",
                        "provenance": provenance,
                        "expected_fingerprint": params.expected_fingerprint,
                        "recovery": (
                            "Restart at offset zero; do not join pages "
                            "from different fingerprints."
                        ),
                    }
                )
            total = identity["total_bytes"]
            if params.offset > total:
                raise ValueError(f"offset exceeds log size ({total} bytes)")
            preview: dict[str, Any] = {}
            if params.encoding == "utf-8":
                page, content = utf8_page(
                    content, params.offset + len(content) < total, MAX_OUTPUT_BYTES
                )
            else:
                page = base64.b64encode(content).decode("ascii")
                try:
                    text, preview_bytes = utf8_page(
                        content, True, MAX_OUTPUT_BYTES - len(page) - 64
                    )
                    preview = {
                        "decoded_text": text,
                        "decoded_text_bytes": len(preview_bytes),
                        "decoded_text_complete": len(preview_bytes) == len(content),
                    }
                except ValueError:
                    preview = {
                        "decoded_text": None,
                        "decoded_text_bytes": 0,
                        "decoded_text_complete": False,
                        "decoded_text_reason": (
                            "page is not UTF-8 or starts within a character"
                        ),
                    }
            end = params.offset + len(content)
            return json.dumps(
                {
                    "status": "read",
                    "action": "raw",
                    "provenance": provenance,
                    "encoding": params.encoding,
                    "offset_unit": "original_file_bytes",
                    "content": page,
                    **preview,
                    "offset": params.offset,
                    "returned_bytes": len(content),
                    "total_bytes": total,
                    "remaining_bytes": total - end,
                    "next_offset": end if end < total else None,
                    "output_truncated": end < total,
                    "max_page_bytes": page_limit,
                },
                ensure_ascii=False,
            )
        texts: dict[int, str] = {}
        provenance["logs"] = []
        total_bytes = 0
        for attempt, path in logs:
            content, identity = _log_bytes(path)
            provenance["logs"].append({"attempt": attempt, **identity})
            total_bytes += identity["total_bytes"]
            if total_bytes > MAX_PARSE_BYTES:
                return json.dumps(
                    {
                        "status": "parse_budget_exhausted",
                        "provenance": provenance,
                        "max_parse_bytes": MAX_PARSE_BYTES,
                        "recovery": "Select fewer attempts or use raw byte pages for complete logs.",
                    }
                )
            texts[attempt] = content.decode("utf-8")
        fingerprints = {
            log["attempt"]: log["content_fingerprint"] for log in provenance["logs"]
        }
        if (
            params.expected_log_fingerprints is not None
            and params.expected_log_fingerprints != fingerprints
        ):
            return json.dumps(
                {
                    "status": "fingerprint_mismatch",
                    "provenance": provenance,
                    "expected_log_fingerprints": params.expected_log_fingerprints,
                    "recovery": "Restart at offset zero; do not combine rows from changed logs.",
                }
            )
        records = selected_records(
            params.operation_id,
            params.from_step,
            params.to_step,
            logs=logs,
            texts=texts,
        )
        if params.offset > len(records):
            raise ValueError("offset exceeds the selected record count")
        available_metrics = sorted(
            {
                metric
                for _, record in records
                for metric in record
                if metric != "total_timesteps"
            }
        )
        metric_page = []
        metric_bytes = 0
        for metric in available_metrics[:MAX_RECORDS]:
            metric_bytes += len(json.dumps(metric).encode("utf-8"))
            if metric_bytes > MAX_OUTPUT_BYTES:
                break
            metric_page.append(metric)
        if params.action == "discover":
            return json.dumps(
                {
                    "status": "discovered",
                    "action": "discover",
                    "provenance": provenance,
                    "available_metrics": metric_page,
                    "available_metric_count": len(available_metrics),
                    "available_metrics_output_truncated": len(metric_page)
                    < len(available_metrics),
                    "total_records": len(records),
                    "first_step": min(
                        (row["total_timesteps"] for _, row in records), default=None
                    ),
                    "last_step": max(
                        (row["total_timesteps"] for _, row in records), default=None
                    ),
                },
                separators=(",", ":"),
            )
        output = []
        size = 0
        byte_truncated = False
        for attempt, record in records[params.offset : params.offset + params.limit]:
            metric_names = (
                [metric for metric in record if metric != "total_timesteps"]
                if params.metrics is None
                else params.metrics
            )
            row = {
                "attempt": attempt,
                "total_timesteps": record["total_timesteps"],
                "metrics": {metric: record.get(metric) for metric in metric_names},
                "missing_metrics": [
                    metric for metric in metric_names if metric not in record
                ],
            }
            row_bytes = len(json.dumps(row).encode("utf-8"))
            if size + row_bytes > params.max_bytes:
                byte_truncated = True
                break
            output.append(row)
            size += row_bytes
        end = params.offset + len(output)
        return json.dumps(
            {
                "status": "queried" if records else "no_matching_rows",
                "action": "records",
                "provenance": provenance,
                "from_step": params.from_step,
                "to_step": params.to_step,
                "available_metrics": metric_page,
                "available_metric_count": len(available_metrics),
                "available_metrics_output_truncated": (
                    len(metric_page) < len(available_metrics)
                ),
                "metric_discovery_recovery": (
                    "Retrieve raw logs for the complete metric names."
                    if len(metric_page) < len(available_metrics)
                    else None
                ),
                "absent_metrics": (
                    []
                    if params.metrics is None or not records
                    else sorted(
                        set(params.metrics)
                        - set(available_metrics)
                        - {"total_timesteps"}
                    )
                ),
                "records": output,
                "offset": params.offset,
                "returned": len(output),
                "total_records": len(records),
                "remaining_records": len(records) - end,
                "next_offset": end if end < len(records) else None,
                "output_truncated": end < len(records),
                "truncation_causes": (
                    (["byte_budget"] if byte_truncated else [])
                    + (
                        ["record_limit"]
                        if len(records) - params.offset > params.limit
                        else []
                    )
                ),
                "limits": {
                    "max_records": MAX_RECORDS,
                    "max_result_bytes": params.max_bytes,
                },
                "recovery": (
                    "Continue with next_offset and log fingerprints. If no row "
                    "fits, select fewer metrics or use raw for complete logs."
                    if byte_truncated
                    else None
                ),
            }
        )
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        return json.dumps(
            {
                "status": "query_failed",
                "error": str(error),
                "provenance": provenance,
                "recovery": (
                    "Use raw with encoding=base64 for logs that cannot be decoded as UTF-8."
                    if isinstance(error, UnicodeError)
                    else None
                ),
            }
        )


def render_markdown(records: list[tuple[int, dict[str, float]]]) -> str:
    metric_names = sorted(
        {
            metric
            for _, record in records
            for metric in record
            if metric != "total_timesteps"
        }
    )
    columns = ["attempt", "total_timesteps", *metric_names]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for attempt, record in records:
        values = [str(attempt), f"{record['total_timesteps']:g}"]
        values.extend(
            "" if metric not in record else f"{record[metric]:g}"
            for metric in metric_names
        )
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--from-step", required=True, type=int)
    parser.add_argument("--to-step", required=True, type=int)
    arguments = parser.parse_args(argv)
    if re.fullmatch(r"T[1-9]\d*", arguments.operation) is None:
        parser.error("--operation must be a training operation ID such as T1")
    if arguments.from_step < 0 or arguments.from_step > arguments.to_step:
        parser.error("timestep bounds must satisfy 0 <= --from-step <= --to-step")
    return arguments


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    try:
        logs = training_log_paths(arguments.operation)
        if not logs:
            print(
                f"no training logs found for operation {arguments.operation}",
                file=sys.stderr,
            )
            return 1
        records = selected_records(
            arguments.operation, arguments.from_step, arguments.to_step, logs=logs
        )
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"training log query failed: {error}", file=sys.stderr)
        return 1
    print(render_markdown(records))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
