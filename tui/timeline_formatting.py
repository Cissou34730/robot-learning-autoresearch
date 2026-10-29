"""Pure text formatting for timeline events."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from runner import reporting as console
from runner.copilot.reporting import tool_detail, tool_result_lines

if TYPE_CHECKING:
    from tui.timeline_items import TimelineItem


def now() -> datetime:
    return datetime.now(tz=UTC)


def clock(stamp: datetime | None) -> str:
    if stamp is None:
        return ""
    return f"{stamp.astimezone():%H:%M:%S}"


def duration(start: datetime | None, end: datetime | None) -> str:
    if start is None:
        return ""
    finish = end or now()
    seconds = max(0.0, (finish - start).total_seconds())
    return console.format_duration(seconds)


def first_line(text: object, limit: int = 120) -> str:
    value = " ".join(str(text or "").split())
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "..."


def full_text(text: object) -> str:
    return str(text or "").strip()


def short(value: object, limit: int = 160) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def json_text(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except (TypeError, ValueError):
        return str(value)


def tool_context(fields: dict, root: Path | None = None) -> str:
    text = str(
        fields.get("detail")
        or tool_detail(str(fields.get("name") or "tool"), fields.get("arguments"))
    )
    if root is not None:
        for prefix in {str(root), root.as_posix()}:
            text = text.replace(prefix + "\\", "").replace(prefix + "/", "")
    return " ".join(text.split())


def tool_summary(
    fields: dict, status: str, seconds: float | None = None, *, root: Path | None = None
) -> str:
    state = "running" if status == "started" else status
    return " | ".join(
        part
        for part in (
            state if state not in {"ok", "completed", ""} else "",
            tool_context(fields, root),
            console.format_duration(seconds)
            if seconds is not None and seconds >= 1
            else "",
        )
        if part
    )


def tool_details(fields: dict) -> tuple[str, ...]:
    details = [
        text.strip()
        for text, _ in tool_result_lines(
            str(fields.get("name") or "tool"), fields.get("result")
        )
    ]
    error = fields.get("error") or fields.get("reason")
    if error:
        details.append(f"Error: {error}")
    return tuple(details)


def number(value: object) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.1f}"
    return "unavailable"


def percent(value: object) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{float(value):g}%"
    return "unavailable"


def as_percent(value: object) -> float | None:
    """A percentage as a number, or ``None`` when the event did not carry it."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def candidate_summary(fields: dict) -> str:
    parts = []
    steps = fields.get("training_steps", fields.get("steps"))
    if steps is not None:
        parts.append(f"{number(steps)} steps")
    # Current journals carry the scenario's success metric in this summary.
    summary = str(fields.get("summary") or "")
    if summary:
        parts.append(summary)
    else:
        if fields.get("ep_rew_mean") is not None:
            parts.append(f"reward {fields['ep_rew_mean']:g}")
        success = fields.get("training_success")
        if isinstance(success, (int, float)) and not isinstance(success, bool):
            parts.append(f"success {float(success) * 100:g}%")
    return " | ".join(parts)


def operation_summary(item: TimelineItem) -> str:
    parts = [item.status] if item.status else []
    if item.kind == "training":
        latest = next(
            (
                child
                for child in reversed(item.children)
                if child.kind == "training_progress"
            ),
            None,
        )
        if latest is not None and item.status in {"running", "requested"}:
            parts.append(latest.title)
        else:
            completed = next(
                (
                    child
                    for child in reversed(item.children)
                    if child.kind == "training"
                ),
                None,
            )
            if completed is not None:
                result = (
                    completed.payload.get("result")
                    if isinstance(completed.payload.get("result"), dict)
                    else {}
                )
                steps = result.get("completed_steps", result.get("requested_steps"))
                dynamics = result.get("learning_dynamics")
                if isinstance(steps, int):
                    parts.append(f"{number(steps)} steps")
                if isinstance(dynamics, list) and dynamics:
                    last = dynamics[-1] if isinstance(dynamics[-1], dict) else {}
                    if last.get("ep_rew_mean") is not None:
                        parts.append(f"reward {last.get('ep_rew_mean')}")
                    if last.get("training_success") is not None:
                        parts.append(
                            f"success {round(float(last['training_success']) * 100)}%"
                        )
    elif item.kind in {"measurement", "measurement_progress"}:
        progress = measurement_summary(item)
        if progress:
            parts.append(progress)
        if item.status == "completed":
            completed = next(
                (
                    child
                    for child in reversed(item.children)
                    if child.kind == "measurement"
                ),
                None,
            )
            if completed is not None:
                result = (
                    completed.payload.get("result")
                    if isinstance(completed.payload.get("result"), dict)
                    else {}
                )
                panels = result.get("measurements")
                if isinstance(panels, list) and panels:
                    best = max(
                        (
                            panel
                            for panel in panels
                            if isinstance(panel, dict)
                            and isinstance(panel.get("metrics"), dict)
                        ),
                        key=lambda panel: float(
                            panel["metrics"].get("success_percent") or 0
                        ),
                        default=None,
                    )
                    if best is not None:
                        metrics = best["metrics"]
                        parts.append(percent(metrics.get("success_percent")))
                        if metrics.get("episodes") is not None:
                            parts.append(f"{metrics.get('episodes')} episodes")
    return " | ".join(part for part in parts if part)


def measurement_summary(item: TimelineItem) -> str:
    """Accumulate each panel once; a new panel never resets the operation."""
    planned: list[dict] = []
    panels: dict[tuple[str, str, str], tuple[int, int]] = {}
    current: tuple[str, str, str] | None = None
    for child in item.children:
        fields = child.payload
        request = fields.get("request")
        if isinstance(request, dict):
            measurement = request.get("measurement")
            if isinstance(measurement, dict) and isinstance(
                measurement.get("measurements"), list
            ):
                planned = measurement["measurements"]
        if child.item_id.startswith("leaf:measurement_panel_started:"):
            current = (
                str(fields.get("artifact") or ""),
                str(fields.get("instrument") or ""),
                str(fields.get("seed", "")),
            )
            episodes = fields.get("episodes")
            previous = panels.get(current, (0, 0))
            panels[current] = (
                previous[0],
                episodes if isinstance(episodes, int) else previous[1],
            )
        elif child.kind == "eval_progress" or child.item_id.startswith(
            "leaf:measurement_panel_completed:"
        ):
            if current is None:
                current = ("", str(fields.get("instrument") or ""), "")
            episodes = fields.get("episodes")
            total = fields.get("episodes_total")
            previous = panels.get(current, (0, 0))
            panels[current] = (
                max(previous[0], episodes)
                if isinstance(episodes, int)
                else previous[0],
                total if isinstance(total, int) else previous[1],
            )

    targets = [panel.get("episodes") for panel in planned if isinstance(panel, dict)]
    total = (
        sum(targets)
        if targets
        and all(isinstance(n, int) and not isinstance(n, bool) for n in targets)
        else sum(target for _, target in panels.values())
    )
    done = sum(episodes for episodes, _ in panels.values())
    if not panels and not total:
        return ""
    return " | ".join(
        part
        for part in (
            f"{number(done)} / {number(total)} episodes",
            f"{100 * done / total:.0f}%" if total else "",
            f"panel {len(panels)}/{len(planned)}" if planned else "",
        )
        if part
    )


def operation_detail(fields: dict) -> tuple[str, ...]:
    request = fields.get("request") if isinstance(fields.get("request"), dict) else {}
    result = fields.get("result") if isinstance(fields.get("result"), dict) else {}
    lines: list[str] = []
    for key in (
        "description",
        "rationale",
        "seed",
        "parent",
        "steps",
        "initialization",
    ):
        if request.get(key) not in (None, ""):
            lines.append(f"{key.title()}: {short(request[key])}")
    for key in (
        "status",
        "completed_steps",
        "requested_steps",
        "instrument",
        "summary",
    ):
        if result.get(key) not in (None, ""):
            lines.append(f"{key.replace('_', ' ').title()}: {short(result[key])}")
    candidates = result.get("candidates")
    if isinstance(candidates, list) and candidates:
        lines.append("Candidates: " + ", ".join(str(item) for item in candidates))
    dynamics = result.get("learning_dynamics")
    if isinstance(dynamics, list):
        for packet in dynamics:
            if not isinstance(packet, dict):
                continue
            lines.append(
                "Learning: "
                + " | ".join(
                    part
                    for part in (
                        str(packet.get("candidate") or ""),
                        f"steps {number(packet.get('training_steps'))}"
                        if packet.get("training_steps") is not None
                        else "",
                        f"reward {packet.get('ep_rew_mean')}"
                        if packet.get("ep_rew_mean") is not None
                        else "",
                        f"success {round(float(packet['training_success']) * 100)}%"
                        if isinstance(packet.get("training_success"), (int, float))
                        and not isinstance(packet.get("training_success"), bool)
                        else "",
                    )
                    if part
                )
            )
    measurements = result.get("measurements")
    if isinstance(measurements, list):
        for panel in measurements:
            if not isinstance(panel, dict):
                continue
            metrics = (
                panel.get("metrics") if isinstance(panel.get("metrics"), dict) else {}
            )
            lines.append(
                "Panel: "
                + " | ".join(
                    part
                    for part in (
                        str(panel.get("candidate") or panel.get("candidate_id") or ""),
                        str(panel.get("instrument") or ""),
                        percent(metrics.get("success_percent")),
                        f"{metrics.get('episodes')} episodes"
                        if metrics.get("episodes") is not None
                        else "",
                    )
                    if part
                )
            )
    if not lines:
        lines.append(short(json_text(fields), 400))
    return tuple(lines)
