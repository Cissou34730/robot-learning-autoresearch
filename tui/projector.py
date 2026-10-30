"""Read-only projection of campaign facts for the report.

`build_snapshot` turns durable files (research state, accepted transactions,
usage rows) into a plain snapshot the report renders. The projection performs
no state inference beyond the recorded identities:

- Model roles come from `model_roles`. A high metric never assigns a role.
- Development success is the latest completed evaluation for a candidate in
  recorded operation order; its source is shown. Failed operations and
  incomplete panels never count as development evidence.
- Recorded usage excludes price and currency fields and always keeps the
  PI, coder and reviewer scopes of the accounting rows.

Everything missing is reported as `unavailable` or `not measured`, never as
zero.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from runner import reporting as console
from tui.activity import (
    EvaluationProgress,
    TrainingProgress,
    parse_timestamp,
    training_eta_seconds,
)

__all__ = [
    "CampaignSnapshot",
    "EvaluationProgress",
    "GoalSummary",
    "ModelRow",
    "TimelineEntry",
    "TrainingProgress",
    "TrainingProxy",
    "UsageSummary",
    "build_snapshot",
    "campaign_age",
    "parse_timestamp",
    "role_assignment_text",
    "stage_elapsed",
    "terminal_stage_text",
    "training_eta_seconds",
    "usage_text",
]


def _as_dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list:
    return value if isinstance(value, list) else []


def _clock_time(stamp: datetime | None) -> str:
    if stamp is None:
        return "--:--"
    return f"{stamp.astimezone():%H:%M}"


def _number(value: object) -> str:
    return f"{value:,}" if isinstance(value, (int, float)) else "unavailable"


def _reward_text(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "unavailable"
    return f"{float(value):.1f}"


def _success_percent(value: object) -> str:
    """Percent text for a success value already defined in percent units."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "unavailable"
    return f"{float(value):g}%"


def _fraction_percent(value: object) -> str:
    """Percent text for a recorded fraction; the source defines the unit."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "unavailable"
    return f"{round(float(value) * 100)}%"


def _aiu_text(value: float) -> str:
    return f"{value:.2f}"


def _tokens_text(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return f"{value}"


@dataclass(frozen=True)
class ModelRow:
    """One role-assigned candidate with its recorded metrics."""

    candidate_id: str
    roles: tuple[str, ...]
    training_steps: str = "unavailable"
    reward_training: str = "unavailable"
    success_training: str = "unavailable"
    success_dev: str = "not measured"
    dev_source: str = ""


@dataclass(frozen=True)
class GoalSummary:
    """Recorded human goal and the latest development evidence against it."""

    text: str = ""
    target_percent: float | None = None
    best_percent: float | None = None
    gap_points: float | None = None
    gap_text: str = ""


@dataclass(frozen=True)
class TrainingProxy:
    """Best checkpoint of the last completed training operation."""

    operation_id: str
    candidate: str
    steps: str = "unavailable"
    reward: str = "unavailable"
    success: str = "unavailable"


@dataclass(frozen=True)
class UsageSummary:
    total_aiu: float | None = None
    copilot_accounting: bool = False
    pi_aiu: float | None = None
    coder_aiu: float | None = None
    reviewer_aiu: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    session_name: str | None = None
    session_aiu: float | None = None
    session_present: bool = False

    @property
    def available(self) -> bool:
        return (
            self.total_aiu is not None
            or bool(self.input_tokens)
            or bool(self.output_tokens)
        )


@dataclass(frozen=True)
class TimelineEntry:
    timestamp: datetime | None
    text: str
    kind: str
    identity: str = ""


@dataclass
class CampaignSnapshot:
    campaign_id: str = "unknown"
    started_at: datetime | None = None
    ended_at: datetime | None = None
    status: str = "Loading"
    human_goal: str = ""
    goal: GoalSummary = field(default_factory=GoalSummary)
    stage_ids: str = ""
    counters_text: str = ""
    pending_text: str = ""
    stage_text: str = "Preparation"
    campaign_phase: str = ""
    session_kind: str = ""
    session_id: str = ""
    inquiry_id: str = ""
    stage_started_at: datetime | None = None
    activity_text: str = "unavailable"
    question: str = ""
    question_source: str = ""
    synthesis: str = ""
    synthesis_session: str = ""
    objective: str = ""
    usage: UsageSummary = field(default_factory=UsageSummary)
    model_rows: tuple[ModelRow, ...] = ()
    timeline: tuple[TimelineEntry, ...] = ()
    training: TrainingProgress | None = None
    last_training: TrainingProxy | None = None
    evaluation: EvaluationProgress | None = None
    official_text: str = ""
    official_status: str = ""
    terminal: bool = False


_ROLE_ORDER = ("working", "best_known")
_ROLE_LABELS = {"working": "Working", "best_known": "Best-known"}


def _inquiry_identity(value: object) -> str:
    """Inquiry ids are recorded as strings or as full inquiry objects."""
    if isinstance(value, dict):
        return str(value.get("id") or value.get("inquiry_id") or "")
    return str(value or "")


def _stage_text(state: dict) -> tuple[str, str, str]:
    """Stage, recorded session id and active inquiry id."""
    session = _as_dict(state.get("scientific_session"))
    session_id = str(session.get("id") or "")
    inquiry_id = _inquiry_identity(state.get("active_inquiry"))
    if state.get("terminal_state"):
        return terminal_stage_text(state), session_id, inquiry_id
    if (
        "campaign_phase" in state
        and _as_dict(state.get("scientific_model")).get("status") == "pending"
    ):
        return "Preparation - PI scientific model pending", "", ""
    if session:
        kind = str(session.get("kind") or "scientific session")
        if inquiry_id or kind == "inquiry":
            label = inquiry_id or session_id
            stage = f"Inquiry {label} / {session_id}".rstrip(" /")
            return stage, session_id, inquiry_id
        title = kind.replace("_", " ").capitalize()
        return f"{title} {session_id}".strip(), session_id, ""
    if "campaign_phase" in state:
        phase = str(state.get("campaign_phase") or "")
        return phase.replace("_", " ").capitalize() or "Loading", "", inquiry_id
    if not _as_dict(state.get("counters")).get("session"):
        return "Preparation - PI scientific model pending", "", ""
    model = _as_dict(state.get("scientific_model"))
    if model:
        return "Startup - PI scientific model active", session_id, ""
    return "Loading", session_id, ""


def _terminal_status(state: dict) -> str:
    terminal = state.get("terminal_state")
    if isinstance(terminal, dict):
        return str(terminal.get("status") or terminal.get("outcome") or "ended")
    if isinstance(terminal, str) and terminal:
        return terminal
    return "ended"


def terminal_stage_text(state: dict) -> str:
    if not state.get("terminal_state"):
        return ""
    status = _terminal_status(state)
    assessment = _as_dict(state.get("official_assessment"))
    summary = str(assessment.get("summary") or "").strip()
    if summary:
        return f"Terminal {status} - {' '.join(summary.split())}"
    verb = (
        "reached"
        if status in {"goal_reached", "completed"}
        else status.replace("_", " ")
    )
    return f"Campaign ended - goal {verb}"


def _campaign_ended_at(state: dict, records: list[dict]) -> datetime | None:
    """The recorded stop time, never the wall clock after the campaign ended."""
    if not state.get("terminal_state"):
        return None
    assessment = _as_dict(state.get("official_assessment"))
    stamp = parse_timestamp(assessment.get("completed_at"))
    if stamp is not None:
        return stamp
    recorded: list[datetime] = []
    for event in _as_list(state.get("operation_events")):
        if isinstance(event, dict):
            value = parse_timestamp(event.get("completed_at"))
            if value is not None:
                recorded.append(value)
    for record in records:
        if isinstance(record, dict):
            value = parse_timestamp(record.get("completed_at"))
            if value is not None:
                recorded.append(value)
    return max(recorded) if recorded else None


# --------------------------------------------------------------------------
# Header facts: stage ids, goal, counters and pending operation.
# --------------------------------------------------------------------------

_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def _human_goal_text(state: dict) -> str:
    goal = state.get("human_goal")
    if isinstance(goal, dict):
        return str(goal.get("summary") or goal.get("source") or "").strip()
    return str(goal or "").strip()


def _goal_target(text: str) -> float | None:
    matches = _PERCENT_RE.findall(text)
    if not matches:
        return None
    try:
        return float(matches[-1])
    except ValueError:
        return None


def _goal_gap_text(state: dict, records: list[dict]) -> str:
    checkpoint = _as_dict(state.get("pi_checkpoint"))
    text = str(checkpoint.get("current_goal_gap") or "").strip()
    if text:
        return text
    for record in reversed(records):
        if record.get("kind") != "checkpoint":
            continue
        request = _as_dict(record.get("request"))
        result = _as_dict(record.get("result"))
        text = str(
            request.get("current_goal_gap") or result.get("current_goal_gap") or ""
        ).strip()
        if text:
            return text
    return ""


def _best_development_percent(records: list[dict]) -> float | None:
    best: float | None = None
    for record in records:
        if record.get("kind") != "measurement" or record.get("status") != "completed":
            continue
        for panel in _as_list(_as_dict(record.get("result")).get("measurements")):
            if not isinstance(panel, dict):
                continue
            metrics = _as_dict(panel.get("metrics"))
            if metrics.get("official_benchmark"):
                continue
            value = metrics.get("success_percent")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                best = float(value) if best is None else max(best, float(value))
    return best


def _goal_summary(state: dict, records: list[dict]) -> GoalSummary:
    text = _human_goal_text(state)
    target = _goal_target(text)
    best = _best_development_percent(records)
    gap = round(best - target, 1) if best is not None and target is not None else None
    return GoalSummary(
        text=text,
        target_percent=target,
        best_percent=best,
        gap_points=gap,
        gap_text=_goal_gap_text(state, records),
    )


def _stage_ids(state: dict) -> str:
    counters = _as_dict(state.get("counters"))
    session = _as_dict(state.get("scientific_session"))

    def number(name: str) -> int | None:
        value = counters.get(name)
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    inquiry = number("inquiry")
    session_number = number("session")
    training = number("training")
    measurement = number("measurement")
    event = number("event")
    session_id = str(session.get("id") or "")
    if not session_id and session_number is not None:
        session_id = f"S{session_number}"
    parts: list[str] = []
    if inquiry is not None:
        parts.append(f"I{inquiry}")
    if session_id:
        parts.append(session_id)
    if training is not None:
        parts.append(f"T{training}")
    if measurement is not None:
        parts.append(f"M{measurement}")
    if event is not None:
        parts.append(f"E{event}")
    return " / ".join(parts)


def _counters_text(state: dict) -> str:
    counters = _as_dict(state.get("counters"))
    campaign = _as_dict(state.get("campaign"))

    def count(name: str) -> int | None:
        value = counters.get(name)
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    parts: list[str] = []
    inquiries = count("inquiry")
    if inquiries is not None:
        maximum = campaign.get("max_inquiries")
        label = f"Inquiries {inquiries}"
        if isinstance(maximum, int) and not isinstance(maximum, bool):
            label += f"/{maximum}"
        parts.append(label)
    trainings = count("training")
    if trainings is not None:
        parts.append(f"Trainings {trainings}")
    measurements = count("measurement")
    if measurements is not None:
        parts.append(f"Measurements {measurements}")
    sessions = count("session")
    if sessions is not None:
        parts.append(f"Sessions {sessions}")
    return " | ".join(parts) if parts else "Counters unavailable"


def _pending_text(state: dict) -> str:
    pending = _as_dict(state.get("pending_operation"))
    if not pending:
        return ""
    identity = str(pending.get("id") or "")
    kind = str(pending.get("kind") or "operation")
    label = f"Pending {identity} {kind}".strip()
    session = str(pending.get("session_id") or "")
    inquiry = str(pending.get("inquiry_id") or "")
    context = " / ".join(part for part in (session, inquiry) if part)
    if context:
        label += f" ({context})"
    return label


def _last_training_proxy(records: list[dict]) -> TrainingProxy | None:
    for record in reversed(records):
        if record.get("kind") != "training" or record.get("status") != "completed":
            continue
        operation = str(record.get("id") or "training")
        result = _as_dict(record.get("result"))
        dynamics = [
            packet
            for packet in _as_list(result.get("learning_dynamics"))
            if isinstance(packet, dict)
        ]
        candidates = [
            str(candidate)
            for candidate in _as_list(result.get("candidates"))
            if isinstance(candidate, str) and candidate
        ]
        if not candidates:
            candidates = [
                str(packet.get("candidate"))
                for packet in dynamics
                if isinstance(packet.get("candidate"), str) and packet.get("candidate")
            ]
        if not candidates:
            return TrainingProxy(operation_id=operation, candidate="unavailable")
        best = candidates[-1]
        best_packet: dict = {}
        if dynamics:

            def score(packet: dict) -> tuple[int, float, int]:
                success = packet.get("training_success")
                reward = packet.get("ep_rew_mean")
                steps = packet.get("training_steps")
                success_rank = (
                    2
                    if isinstance(success, (int, float))
                    and not isinstance(success, bool)
                    else 0
                )
                reward_rank = (
                    1
                    if isinstance(reward, (int, float)) and not isinstance(reward, bool)
                    else 0
                )
                value = (
                    float(success)
                    if success_rank
                    else float(reward)
                    if reward_rank
                    else 0.0
                )
                step_value = (
                    steps
                    if isinstance(steps, int) and not isinstance(steps, bool)
                    else 0
                )
                return (success_rank or reward_rank, value, step_value)

            best_packet = max(dynamics, key=score)
            candidate = best_packet.get("candidate")
            if isinstance(candidate, str) and candidate:
                best = candidate
        steps = best_packet.get("training_steps")
        if not isinstance(steps, int) or isinstance(steps, bool):
            match = re.search(r"checkpoint-(\d+)$", best)
            steps = int(match.group(1)) if match else None
        return TrainingProxy(
            operation_id=operation,
            candidate=best,
            steps=_number(steps),
            reward=_reward_text(best_packet.get("ep_rew_mean")),
            success=_fraction_percent(best_packet.get("training_success")),
        )
    return None


# --------------------------------------------------------------------------
# Recorded candidate metrics.
# --------------------------------------------------------------------------


def _training_packets(records: list[dict]) -> dict[str, tuple[object, object]]:
    """Recorded training metrics per candidate from completed training runs.

    A later completed run replaces an earlier packet, and a run's own
    `training_steps` values stay with it.
    """
    packets: dict[str, tuple[object, object]] = {}
    for record in records:
        if record.get("kind") != "training" or record.get("status") != "completed":
            continue
        dynamics = _as_list(_as_dict(record.get("result")).get("learning_dynamics"))
        for packet in dynamics:
            if not isinstance(packet, dict):
                continue
            candidate = packet.get("candidate")
            if isinstance(candidate, str) and candidate:
                packets[candidate] = (
                    packet.get("ep_rew_mean"),
                    packet.get("training_success"),
                )
    return packets


def _development_packets(records: list[dict]) -> dict[str, tuple[str, str]]:
    """Recorded development success per candidate from completed measurements.

    The latest completed evaluation in recorded order wins. Failed
    operations, official panels and panels without recorded success never
    become development evidence.
    """
    packets: dict[str, tuple[str, str]] = {}
    for record in records:
        if record.get("kind") != "measurement" or record.get("status") != "completed":
            continue
        operation = str(record.get("id") or "measurement")
        panels = _as_list(_as_dict(record.get("result")).get("measurements"))
        for panel in panels:
            if not isinstance(panel, dict):
                continue
            candidate = panel.get("candidate") or panel.get("candidate_id")
            metrics = _as_dict(panel.get("metrics"))
            if metrics.get("official_benchmark"):
                continue
            if not isinstance(candidate, str) or not candidate:
                continue
            percent = metrics.get("success_percent")
            instrument = str(panel.get("instrument") or "")
            label = str(panel.get("label") or "")
            source = f"{operation}, {instrument or label}" + (
                f" ({label})" if label and instrument else ""
            )
            if isinstance(percent, (int, float)) and not isinstance(percent, bool):
                episodes = metrics.get("episodes")
                detail = _success_percent(percent)
                if isinstance(episodes, int):
                    detail += f", {episodes} episodes"
                packets[candidate] = (f"{detail} / {source}", source)
            else:
                packets[candidate] = ("not measured / " + source, source)
    return packets


def _role_values(roles: dict) -> tuple[tuple[str, str], ...]:
    """Role candidates in a stable order: fixed roles first, then retained."""
    values: list[tuple[str, str]] = []
    for role in _ROLE_ORDER:
        candidate = roles.get(role)
        if isinstance(candidate, str) and candidate:
            values.append((role, candidate))
    retained = _as_dict(roles.get("retained"))
    for label, candidate in retained.items():
        if (
            isinstance(candidate, str)
            and candidate
            and isinstance(label, str)
            and label
        ):
            values.append((f"retained:{label}", candidate))
    return tuple(values)


def _model_rows(
    state: dict,
    training: dict[str, tuple[object, object]],
    development: dict[str, tuple[str, str]],
) -> tuple[ModelRow, ...]:
    roles = _as_dict(state.get("model_roles"))
    candidates = _as_dict(state.get("candidates"))

    grouped: dict[str, list[str]] = {}
    order: list[str] = []
    for role, candidate in _role_values(roles):
        if candidate not in grouped:
            grouped[candidate] = []
            order.append(candidate)
        if role.startswith("retained:"):
            grouped[candidate].append(f"Retained: {role.split(':', 1)[1]}")
        else:
            grouped[candidate].append(_ROLE_LABELS.get(role, role))

    rows: list[ModelRow] = []
    for candidate in order:
        stored = _as_dict(candidates.get(candidate))
        steps = stored.get("training_steps")
        reward, success = training.get(candidate, (None, None))
        dev = development.get(candidate, ("not measured", ""))
        rows.append(
            ModelRow(
                candidate_id=candidate,
                roles=tuple(grouped[candidate]),
                training_steps=_number(steps) if steps is not None else "unavailable",
                reward_training=_reward_text(reward),
                success_training=_fraction_percent(success),
                success_dev=dev[0],
                dev_source=dev[1],
            )
        )
    return tuple(rows)


# --------------------------------------------------------------------------
# Timeline reconstruction from durable records.
# --------------------------------------------------------------------------


def _timeline(state: dict, records: list[dict]) -> tuple[TimelineEntry, ...]:
    entries: list[TimelineEntry] = []

    pending = _as_dict(state.get("pending_operation"))
    if pending:
        kind = str(pending.get("kind") or "operation")
        identity = str(pending.get("id") or "")
        entries.append(
            TimelineEntry(
                None,
                f"{identity or kind}: {kind} accepted - execution state not observed",
                "pending",
                identity,
            )
        )

    for record in records:
        entry = _record_entry(record)
        if entry is not None:
            entries.append(entry)
    return tuple(entries)


def _record_entry(record: dict) -> TimelineEntry | None:
    kind = record.get("kind")
    identity = str(record.get("id") or "")
    stamp = parse_timestamp(record.get("completed_at"))
    status = record.get("status")
    error = record.get("error")

    if status == "failed":
        detail = (
            f" - {' '.join(str(error).split())}"
            if isinstance(error, str) and error
            else ""
        )
        return TimelineEntry(
            stamp, f"{identity}: {kind} failed{detail}", "error", identity
        )
    if status != "completed":
        return None

    request = _as_dict(record.get("request"))
    result = _as_dict(record.get("result"))

    if kind == "training":
        return TimelineEntry(
            stamp, _training_line(identity, request, result), "training", identity
        )
    if kind == "measurement":
        return TimelineEntry(
            stamp, _measurement_line(identity, request, result), "measurement", identity
        )
    if kind == "inquiry":
        return _inquiry_entry(record, stamp)
    if kind == "checkpoint":
        session = str(record.get("session_id") or result.get("session_id") or "unknown")
        return TimelineEntry(
            stamp,
            f"Scientific session {session} checkpoint saved",
            "checkpoint",
            identity,
        )
    if kind == "model_role":
        return _role_entry(identity, request, result, stamp)
    if kind in {"restore_recipe", "campaign_conclusion"}:
        return TimelineEntry(
            stamp,
            f"{identity or kind}: {kind.replace('_', ' ')} completed",
            kind,
            identity,
        )
    return None


def _training_line(identity: str, request: dict, result: dict) -> str:
    requested = request.get("steps")
    completed = result.get("completed_steps", requested)
    candidates = _as_list(result.get("candidates"))
    text = (
        f"{identity}: training completed - "
        f"steps {_number(completed)} of {_number(requested)} requested"
    )
    if candidates:
        text += f", {len(candidates)} checkpoint candidates"
    return text


def _measurement_line(identity: str, request: dict, result: dict) -> str:
    label = str(result.get("instrument") or request.get("instrument") or "")
    parts: list[str] = []
    for panel in _as_list(result.get("measurements")):
        if not isinstance(panel, dict):
            continue
        candidate = panel.get("candidate") or panel.get("candidate_id")
        metrics = _as_dict(panel.get("metrics"))
        if not isinstance(candidate, str):
            continue
        piece = candidate
        percent = metrics.get("success_percent")
        if isinstance(percent, (int, float)) and not isinstance(percent, bool):
            piece += f" {_success_percent(percent)}"
        episodes = metrics.get("episodes")
        if isinstance(episodes, int):
            piece += f" ({episodes} episodes)"
        parts.append(piece)
    text = f"{identity}: measurement completed"
    if label:
        text += f" - {label}"
    detail = " | ".join(parts)
    if detail:
        text += f" - {detail}" if not label else f", {detail}"
    return text


def _inquiry_entry(record: dict, stamp: datetime | None) -> TimelineEntry:
    identity = str(record.get("id") or "")
    request = _as_dict(record.get("request"))
    result = _as_dict(record.get("result"))
    inquiry_id = str(record.get("inquiry_id") or result.get("inquiry_id") or "unknown")
    action = str(request.get("action") or "").lower()
    if action == "open":
        question = str(request.get("question") or "").strip()
        summary = question.split("\n", 1)[0]
        summary = summary if len(summary) <= 200 else summary[:200].rstrip() + "..."
        return TimelineEntry(
            stamp, f"Inquiry {inquiry_id} opened - {summary}", "inquiry", identity
        )
    if action == "close":
        return TimelineEntry(stamp, f"Inquiry {inquiry_id} closed", "inquiry", identity)
    readable = action.replace("_", " ") or "unknown action"
    return TimelineEntry(
        stamp, f"{identity}: inquiry {readable} for {inquiry_id}", "inquiry", identity
    )


def _role_entry(
    identity: str, request: dict, result: dict, stamp: datetime | None
) -> TimelineEntry:
    action = str(request.get("action") or result.get("action") or "")
    readable = action.removeprefix("set_").replace("_", " ").strip() or "assigned roles"
    candidate = request.get("candidate") or result.get("candidate")
    if not candidate and isinstance(result.get("assignments"), list):
        candidate = (
            ", ".join(
                assignment.get("candidate", "")
                for assignment in result["assignments"]
                if isinstance(assignment, dict)
            )
            or None
        )
    evidence = _as_list(request.get("evidence") or result.get("evidence"))
    text = f"PI assigned {readable}"
    if isinstance(candidate, str) and candidate:
        text += f" to {candidate}"
    elif isinstance(candidate, list) and candidate:
        text += f" to {', '.join(str(item) for item in candidate)}"
    if evidence:
        text += f" (evidence {', '.join(str(item) for item in evidence)})"
    return TimelineEntry(stamp, text, "role", identity)


# --------------------------------------------------------------------------
# Recorded usage.
# --------------------------------------------------------------------------


def _usage_summary(state: dict, usage_rows: list[dict]) -> UsageSummary:
    campaign_id = _as_dict(state.get("campaign")).get("id")
    session = _as_dict(state.get("scientific_session"))
    backend_session = session.get("backend_session_id")
    session_name = str(session.get("id") or "") if backend_session else None

    total: float | None = None
    copilot_accounting = False
    by_role: dict[str, float] = {}
    session_aiu: float | None = None
    session_present = False
    input_tokens = 0
    output_tokens = 0

    for row in usage_rows:
        if campaign_id is not None and row.get("campaign_id") != campaign_id:
            continue
        aiu = row.get("aiu")
        known_aiu = isinstance(aiu, (int, float)) and not isinstance(aiu, bool)
        if known_aiu:
            total = (total or 0.0) + float(aiu)
            copilot_accounting = (
                copilot_accounting or row.get("provider") == "github-copilot"
            )
        else:
            input_tokens += int(row.get("input_tokens") or 0)
            output_tokens += int(row.get("output_tokens") or 0)
        role = str(row.get("role") or "")
        mapped = {
            "pi": "pi",
            "scientific_coder": "coder",
            "scientific_reviewer": "reviewer",
        }.get(role)
        if known_aiu and mapped:
            by_role[mapped] = by_role.get(mapped, 0.0) + float(aiu)
        if backend_session and row.get("session_id") == backend_session:
            session_present = True
            if known_aiu:
                session_aiu = (session_aiu or 0.0) + float(aiu)

    return UsageSummary(
        total_aiu=total,
        copilot_accounting=copilot_accounting,
        pi_aiu=by_role.get("pi"),
        coder_aiu=by_role.get("coder"),
        reviewer_aiu=by_role.get("reviewer"),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        session_name=session_name,
        session_aiu=session_aiu,
        session_present=session_present,
    )


def usage_text(summary: UsageSummary) -> str:
    if not summary.available:
        return "Recorded usage: unavailable - no accounting rows for this campaign"
    if summary.total_aiu is None:
        text = "Usage recorded: campaign AIU unavailable"
    else:
        unit = "Copilot AIU" if summary.copilot_accounting else "recorded AIU"
        text = f"Usage recorded: campaign {_aiu_text(summary.total_aiu)} {unit}"
    scoped = []
    if summary.pi_aiu is not None:
        scoped.append(f"PI {_aiu_text(summary.pi_aiu)}")
    if summary.coder_aiu is not None:
        scoped.append(f"coder {_aiu_text(summary.coder_aiu)}")
    if summary.reviewer_aiu is not None:
        scoped.append(f"reviewer {_aiu_text(summary.reviewer_aiu)}")
    if scoped:
        text += " | " + " ".join(scoped)
    if summary.session_name:
        if summary.session_present and summary.session_aiu is not None:
            text += (
                f" | session {summary.session_name} {_aiu_text(summary.session_aiu)}"
            )
        else:
            text += f" | session {summary.session_name} accounting pending"
    tokens = []
    if summary.input_tokens:
        tokens.append(f"in {_tokens_text(summary.input_tokens)}")
    if summary.output_tokens:
        tokens.append(f"out {_tokens_text(summary.output_tokens)}")
    if tokens:
        text += " | tokens " + " ".join(tokens)
    return text


# --------------------------------------------------------------------------
# Question, synthesis and activity.
# --------------------------------------------------------------------------


def _question(state: dict, records: list[dict]) -> tuple[str, str]:
    inquiry = state.get("active_inquiry")
    if isinstance(inquiry, dict):
        text = str(inquiry.get("question") or "").strip()
        if text:
            identity = str(inquiry.get("id") or "unknown")
            return text, f"inquiry {identity}"
    inquiry_id = _inquiry_identity(state.get("active_inquiry"))
    if inquiry_id:
        for record in reversed(records):
            if (
                record.get("kind") != "inquiry"
                or record.get("inquiry_id") != inquiry_id
            ):
                continue
            request = _as_dict(record.get("request"))
            if str(request.get("action") or "").lower() == "open":
                question = str(request.get("question") or "").strip()
                if question:
                    return question, f"inquiry {inquiry_id}"
    checkpoint = _as_dict(state.get("pi_checkpoint"))
    next_question = str(checkpoint.get("next_question") or "").strip()
    if next_question:
        return next_question, "PI record"
    return "", ""


def _synthesis(state: dict, records: list[dict]) -> tuple[str, str]:
    checkpoint = _as_dict(state.get("pi_checkpoint"))
    synthesis = str(checkpoint.get("current_synthesis") or "").strip()
    session = ""
    for record in reversed(records):
        if record.get("kind") != "checkpoint":
            continue
        if not session:
            session = str(record.get("session_id") or "")
        if synthesis:
            break
        stored = _as_dict(record.get("result"))
        stored_synthesis = str(stored.get("current_synthesis") or "")
        if stored_synthesis:
            synthesis = stored_synthesis
            break
    if not synthesis:
        synthesis = str(
            _as_dict(state.get("scientific_session")).get("objective") or ""
        )
    return synthesis, session


def _objective_without_inquiry(state: dict) -> str:
    session = _as_dict(state.get("scientific_session"))
    objective = str(session.get("objective") or "").strip()
    if objective:
        return objective
    model = _as_dict(state.get("scientific_model"))
    if "campaign_phase" in state and model.get("status") != "pending":
        return ""
    if model.get("status") == "pending" or not _as_dict(state.get("counters")).get(
        "session"
    ):
        return (
            "Prepare the PI scientific model: read the task, refresh the shared "
            "scientific understanding and open the first inquiry."
        )
    return ""


def _activity_text(state: dict, records: list[dict], terminal: bool) -> str:
    if terminal:
        assessment = _as_dict(state.get("official_assessment"))
        if assessment.get("status"):
            return f"official assessment {assessment.get('status')}"
        return "idle"
    pending = _as_dict(state.get("pending_operation"))
    if pending:
        kind = str(pending.get("kind") or "operation")
        identity = str(pending.get("id") or "")
        return f"{identity or kind} {kind} accepted - execution not observed"
    if records:
        latest = records[-1]
        identity = str(latest.get("id") or "")
        kind = str(latest.get("kind") or "operation")
        return f"last completed {identity} {kind} - live activity not observed"
    return "waiting for the first operation"


def build_snapshot(
    state: dict | None,
    records: list[dict],
    usage_rows: list[dict],
    *,
    training: TrainingProgress | None = None,
    evaluation: EvaluationProgress | None = None,
    activity: str | None = None,
    stage_started_at: datetime | None = None,
    process_observed_recently: bool = False,
) -> CampaignSnapshot:
    state = state or {}
    campaign = _as_dict(state.get("campaign"))
    campaign_id = str(campaign.get("id") or "unknown")
    started_at = parse_timestamp(campaign.get("started_at"))
    ended_at = _campaign_ended_at(state, records)
    stage, session_id, inquiry_id = _stage_text(state)
    terminal = bool(state.get("terminal_state"))

    if terminal:
        status = f"ENDED ({_terminal_status(state)})"
    elif state:
        status = (
            "RUNNING (observed)"
            if process_observed_recently
            else "RUNNING (process state unknown)"
        )
    else:
        status = "Loading"

    usage = _usage_summary(state, usage_rows)
    model_rows = (
        _model_rows(state, _training_packets(records), _development_packets(records))
        if state
        else ()
    )
    goal = _goal_summary(state, records) if state else GoalSummary()
    stage_ids = _stage_ids(state) if state else ""
    counters_text = _counters_text(state) if state else ""
    pending_text = _pending_text(state) if state else ""
    last_training = _last_training_proxy(records) if records else None

    question, question_source = _question(state, records)
    synthesis, synthesis_session = _synthesis(state, records)
    objective = "" if question else _objective_without_inquiry(state)
    activity = (
        _activity_text(state, records, terminal)
        if terminal
        else activity
        if activity is not None
        else _activity_text(state, records, terminal)
    )

    assessment = _as_dict(state.get("official_assessment"))
    summary = str(assessment.get("summary") or "").strip()
    official_text = (
        f"Official assessment {assessment.get('status')} - {' '.join(summary.split())}"
        if summary and assessment.get("status")
        else ""
    )

    return CampaignSnapshot(
        campaign_id=campaign_id,
        started_at=started_at,
        ended_at=ended_at,
        status=status,
        human_goal=_human_goal_text(state),
        goal=goal,
        stage_ids=stage_ids,
        counters_text=counters_text,
        pending_text=pending_text,
        stage_text=stage,
        campaign_phase=str(state.get("campaign_phase") or ""),
        session_kind=str(_as_dict(state.get("scientific_session")).get("kind") or ""),
        session_id=session_id,
        inquiry_id=inquiry_id,
        stage_started_at=stage_started_at,
        activity_text=activity,
        question=question,
        question_source=question_source,
        synthesis=synthesis,
        synthesis_session=synthesis_session,
        objective=objective,
        usage=usage,
        model_rows=model_rows,
        timeline=_timeline(state, records),
        training=training,
        last_training=last_training,
        evaluation=evaluation,
        official_text=official_text,
        official_status=str(assessment.get("status") or ""),
        terminal=terminal,
    )


def campaign_age(
    started_at: datetime | None,
    now: datetime,
    ended_at: datetime | None = None,
) -> str:
    if started_at is None:
        return "unavailable"
    end = ended_at or now
    return console.format_duration(max(0.0, (end - started_at).total_seconds()))


def stage_elapsed(
    stage_started_at: datetime | None,
    now: datetime,
    ended_at: datetime | None = None,
) -> str:
    if stage_started_at is None:
        return "unavailable"
    end = ended_at or now
    return console.format_duration(max(0.0, (end - stage_started_at).total_seconds()))


def role_assignment_text(snapshot: CampaignSnapshot) -> str:
    """Stable text of the role table, for attachment and change detection."""
    parts = []
    for row in snapshot.model_rows:
        value = f"{' + '.join(row.roles)}: {row.candidate_id}"
        metrics = f"Reward(tr) {row.reward_training}, Success(tr) {row.success_training}, Success(dev) {row.success_dev}"
        parts.append(f"{value} | {metrics}")
    return "\n".join(parts)
