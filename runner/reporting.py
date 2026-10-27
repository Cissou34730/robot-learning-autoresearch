"""Runner observations and shared formatting helpers.

The Runner formats facts the researcher already decided or the tools already
measured. It never adds a scientific conclusion of its own. Every fact goes to
the campaign's typed event feed; nothing is written to a console.
"""

import json
import re
from pathlib import Path

from runner import invocation_result, paths, typed_events

_ROOT = paths.ROOT
_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
SCOPES = frozenset(
    {
        "campaign",
        "session",
        "pi",
        "inquiry",
        "operation",
        "measurement",
        "training",
        "checkpoint",
        "assessment",
        "validation",
        "runner",
        "warning",
        "error",
    }
)
_CARD_SCOPES = frozenset(
    {
        "assessment",
        "campaign",
        "error",
        "inquiry",
        "measurement",
        "operation",
        "session",
        "warning",
    }
)


def compact_path(value: str | Path) -> str:
    """Keep paths useful without leaking a long machine-specific prefix."""
    path = Path(value)
    try:
        relative = path.resolve().relative_to(_ROOT.resolve())
        return relative.as_posix()
    except (OSError, ValueError):
        if not path.is_absolute():
            return path.as_posix()
        parts = path.parts[-2:]
        return (".../" + "/".join(parts)).replace("\\", "/")


def compact_text(text: object) -> str:
    return _UUID.sub("<id>", str(text))


def _severity(scope: str) -> str:
    return "error" if scope == "error" else "warning" if scope == "warning" else "info"


def diagnostic(message: str, *, code: str = "runner_error") -> None:
    """An execution diagnostic for the launcher result and the operator log."""
    invocation_result.add_error(message)
    typed_events.emit(
        "error", {"code": code, "message": message}, scope="error", severity="error"
    )


def _marker_scope(text: str) -> str:
    """The scope named by a leading ``[marker]``, if it is a known scope."""
    if text.startswith("[") and "]" in text:
        marker = text[1 : text.index("]")].casefold()
        return marker if marker in SCOPES else "info"
    return "info"


def announce(message: str) -> None:
    """One operator notice line."""
    text = message.lstrip("\n")
    scope = _marker_scope(compact_text(text))
    typed_events.emit(
        "notice", {"text": text, "scope": scope}, scope=scope, severity=_severity(scope)
    )


def card(scope: str, title: str, lines: list[str] | tuple[str, ...] = ()) -> None:
    """One titled operator notice for a meaningful lifecycle boundary."""
    scope = scope.casefold()
    typed_events.emit(
        "notice",
        {"title": title, "body": list(lines), "scope": scope},
        scope=scope,
        severity=_severity(scope),
    )


def boundary(scope: str, action: str, subject: str = "", detail: str = "") -> None:
    """One durable lifecycle boundary with a stable hierarchy."""
    normalized_scope = scope.casefold()
    if normalized_scope in _CARD_SCOPES:
        title = " | ".join(
            part for part in (normalized_scope.upper(), action.upper(), subject) if part
        )
        card(normalized_scope, title, tuple(detail.splitlines()) if detail else ())
        return
    head = " | ".join(part for part in (action.upper(), subject) if part)
    if "\n" in detail:
        announce(f"[{normalized_scope}] {head}\n{detail}")
        return
    body = " | ".join(part for part in (head, detail) if part)
    announce(f"[{normalized_scope}] {body}")


def format_duration(seconds: float) -> str:
    total = max(int(seconds), 0)
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{seconds:02d}s"
    return f"{seconds}s"


def format_count(value: float) -> str:
    count = float(value)
    for threshold, suffix in ((1_000_000, "m"), (1_000, "k")):
        if abs(count) >= threshold:
            scaled = count / threshold
            return f"{scaled:.1f}".rstrip("0").rstrip(".") + suffix
    return f"{count:g}"


def scenario_progress_metric(record: dict[str, float]) -> str | None:
    """The one live training metric the scenario owns, resolved on demand.

    Imported here rather than at module scope so presenting a card never pulls
    the training and physics stack into a validation-only command.
    """
    from robot_learning.scenario.progress import render_training_progress_metric

    return render_training_progress_metric(record)


def training_progress_suffix(record: dict[str, float] | None) -> str:
    """Append the rolling reward and the single scenario-owned live metric."""
    if not record:
        return ""
    parts: list[str] = []
    reward = record.get("ep_rew_mean")
    if reward is not None:
        parts.append(f"reward {float(reward):g}")
    scenario_fragment = scenario_progress_metric(record)
    if scenario_fragment:
        parts.append(scenario_fragment)
    return "".join(f" | {part}" for part in parts)


def _usage_rows(campaign_id: str, session_id: str | None = None) -> list[dict]:
    usage_path = _ROOT / "reports" / "session_usage" / f"{campaign_id}.jsonl"
    if not usage_path.is_file():
        return []
    rows: list[dict] = []
    for line in usage_path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (
            session_id is None
            or row.get("session_id") == session_id
            or row.get("parent_session_id") == session_id
        ):
            rows.append(row)
    return rows


def usage_aiu(campaign_id: str) -> float | None:
    rows = _usage_rows(campaign_id)
    return sum(float(row.get("aiu") or 0) for row in rows) if rows else None


def usage_totals(campaign_id: str, session_id: str | None = None) -> dict:
    """Aggregate durable accounting without creating a new budget."""
    rows = _usage_rows(campaign_id, session_id)
    if not rows:
        return {}
    duration = sum(float(row.get("duration_seconds") or 0) for row in rows)
    prompt = sum(int(row.get("input_tokens") or 0) for row in rows)
    cached = sum(int(row.get("cache_read_tokens") or 0) for row in rows)
    output = sum(int(row.get("output_tokens") or 0) for row in rows)
    aiu = sum(float(row.get("aiu") or 0) for row in rows)
    cost = sum(float(row.get("reported_cost_usd") or 0) for row in rows)
    return {
        "rows": len(rows),
        "duration_seconds": duration,
        "input_tokens": prompt,
        "cache_read_tokens": cached,
        "output_tokens": output,
        "aiu": aiu,
        "cost_usd": cost,
    }


def usage_summary(campaign_id: str, session_id: str | None = None) -> str:
    """Render the durable accounting aggregate shown in lifecycle cards."""
    totals = usage_totals(campaign_id, session_id)
    if not totals:
        return "usage unavailable"
    prompt = totals["input_tokens"]
    cached = totals["cache_read_tokens"]
    parts = [format_duration(totals["duration_seconds"])]
    if totals["aiu"]:
        parts.append(f"{totals['aiu']:.2f} AIU")
    if totals["cost_usd"]:
        parts.append(f"${totals['cost_usd']:.4f} estimated")
    if prompt:
        cache_share = round(100 * cached / prompt) if cached else 0
        parts.append(f"prompt {format_count(prompt)} ({cache_share}% cached)")
    if totals["output_tokens"]:
        parts.append(f"output {format_count(totals['output_tokens'])}")
    return " | ".join(parts)
