"""Session usage accounting: counters fed by SDK events and the usage JSONL row."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from runner import typed_events
from runner.copilot.coding_contracts import normalize_model
from runner.copilot.opencode_provider import provider_of
from runner.copilot.path_policy import ROOT

TOKEN_FIELDS = (
    "input_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "output_tokens",
)


@dataclass
class SessionUsage:
    input_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0
    nano_aiu: float = 0.0
    # Fields the runtime actually reported; unreported usage stays None, not zero.
    reported: set[str] = field(default_factory=set)
    tool_calls: int = 0
    tool_counts: dict[str, int] = field(default_factory=dict)
    coding_duration_seconds: float = 0.0
    runner_wait_seconds: float = 0.0

    def add_assistant_usage(self, data) -> None:
        for name in TOKEN_FIELDS:
            value = getattr(data, name, None)
            if value is not None:
                self.reported.add(name)
                setattr(self, name, getattr(self, name) + value)
        aiu = getattr(getattr(data, "copilot_usage", None), "total_nano_aiu", None)
        if aiu is not None:
            self.reported.add("aiu")
            self.nano_aiu += aiu

    def count_tool(self, name: str) -> None:
        self.tool_calls += 1
        self.tool_counts[name] = self.tool_counts.get(name, 0) + 1

    def tokens(self, *, copilot_billed: bool) -> dict:
        values = {
            name: getattr(self, name) if name in self.reported else None
            for name in TOKEN_FIELDS
        }
        values["aiu"] = (
            self.nano_aiu / 1e9 if copilot_billed and "aiu" in self.reported else None
        )
        return values


def record_usage(
    args,
    usage: SessionUsage,
    elapsed: float,
    exit_code: int,
    *,
    role: str = "pi",
    session_id: str | None = None,
    parent_session_id: str | None = None,
    actual_models: list[str] | None = None,
    actual_reasoning_efforts: list[str] | None = None,
) -> None:
    """Append aggregate usage, never conversation content or tool arguments."""
    if not args.campaign_id:
        return  # Standalone invocations are not attributed to an arbitrary campaign.
    # Campaign IDs are path components, not filenames supplied by the model.
    campaign_id = str(uuid.UUID(args.campaign_id))
    directory = ROOT / "reports" / "session_usage"
    directory.mkdir(parents=True, exist_ok=True)
    provider = provider_of(args.model)
    row = {
        "campaign_id": campaign_id,
        "phase": args.phase,
        "attempt": args.attempt,
        "session_id": session_id or args.session_id,
        "role": role,
        "parent_session_id": parent_session_id,
        "recorded_at": datetime.now(UTC).isoformat(),
        "model": normalize_model(args.model),
        "provider": provider,
        "reasoning": getattr(args, "effective_reasoning", args.reasoning),
        # Child time is reported in its own row, not again in the PI row.
        "duration_seconds": round(
            max(
                0.0,
                elapsed - usage.coding_duration_seconds - usage.runner_wait_seconds,
            ),
            3,
        ),
        "wall_duration_seconds": round(elapsed, 3),
        "runner_wait_seconds": round(usage.runner_wait_seconds, 3),
        "exit_code": exit_code,
        **usage.tokens(copilot_billed=provider == "github-copilot"),
        "tool_calls": usage.tool_calls,
        "tools_by_name": usage.tool_counts,
    }
    external = getattr(args, "provider_model", None)
    if external is not None:
        row["provider_token_prices_per_million"] = external.cost
    if actual_models is not None:
        row["actual_models"] = actual_models
    if actual_reasoning_efforts is not None:
        row["actual_reasoning_efforts"] = actual_reasoning_efforts
    with (directory / f"{campaign_id}.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    typed_events.set_campaign(campaign_id)
    typed_events.emit(
        "usage_update",
        {**row},
        scope="usage",
        session_id=str(row.get("session_id") or ""),
        event_id=(
            f"domain:usage:{campaign_id}:{row.get('session_id') or ''}:"
            f"{row.get('role') or ''}:{args.phase}:{args.attempt}:{row['recorded_at']}"
        ),
    )
