"""Pure report text, colors and size calculations."""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from datetime import datetime

from rich.text import Text

from runner import reporting as console
from tui import projector


def context_budget(width: int, height: int) -> int:
    if width < 60:
        return 4
    if width < 120 or height < 40:
        return 6
    return 8


def output_min_rows(height: int) -> int:
    if height >= 40:
        return max(5, int(height * 0.55))
    return max(4, height // 2)


def model_budget(
    height: int,
    *,
    context_rows: int,
    progress_rows: int,
    training_rows: int,
    output_hidden: bool,
    show_hints: bool,
    now_rows: int,
    search_visible: bool,
) -> int:
    reserved = context_rows + 1 + progress_rows + training_rows
    if not output_hidden:
        reserved += (2 if show_hints else 1) + now_rows + int(search_visible)
    output_min = 0 if output_hidden else output_min_rows(height)
    return max(1, min(20, height - reserved - output_min))


@dataclass(frozen=True)
class Palette:
    """Semantic colour tokens for one terminal background."""

    name: str
    background: str
    log_bg: str
    column_bg: str
    text: str
    muted: str
    heading: str
    accent: str
    success: str
    warning: str
    error: str
    pi: str
    pi_text: str
    tool: str
    section: str
    result: str


PALETTES: dict[str, Palette] = {
    "dark": Palette(
        name="dark",
        background="#1e1e1e",
        log_bg="#000000",
        column_bg="#262626",
        text="#e6e6e6",
        muted="#b0b0b0",
        heading="#f0f0f0",
        accent="#7cc7ff",
        success="#6ee7a8",
        warning="#ffd166",
        error="#ff8a9b",
        pi="#e0aaff",
        pi_text="#7de3e8",
        tool="#b8c0cc",
        section="#d7d7d7",
        result="#6ee7a8",
    ),
    "light": Palette(
        name="light",
        background="#f5f5f5",
        log_bg="#ffffff",
        column_bg="#e2e2e2",
        text="#1a1a1a",
        muted="#4a4a4a",
        heading="#111111",
        accent="#0b5fa5",
        success="#0f6b3d",
        warning="#8a5a00",
        error="#b3261e",
        pi="#6b2d8f",
        pi_text="#00656b",
        tool="#3f4a5a",
        section="#2a2a2a",
        result="#0f6b3d",
    ),
}

_FLOAT_RE = re.compile(r"(?<![\w.])-?\d+\.\d{4,}(?![\w.])")

_PATH_RE = re.compile(
    r"(?<![\w:/])(?:[A-Za-z]:[\\/][^\s,;:)\]}\"']*|/[^\s,;:)\]}\"']*)"
)


def relative_luminance(color: str) -> float:
    value = color.lstrip("#")
    channels = [int(value[index : index + 2], 16) / 255 for index in (0, 2, 4)]

    def linear(channel: float) -> float:
        if channel <= 0.04045:
            return channel / 12.92
        return ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast ratio between two #RRGGBB colours."""
    first = relative_luminance(foreground)
    second = relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def status_style_for(status: str, palette: Palette) -> str:
    """Pair the campaign status text with a semantic token."""
    if status.startswith("RUNNING") and "unknown" not in status:
        return f"bold {palette.success}"
    if status.startswith("RUNNING"):
        return f"bold {palette.warning}"
    if status.startswith("ENDED") or status == "Loading":
        return palette.muted
    return palette.text


def display_text(value: str) -> str:
    """Round long floats and compact absolute paths for display only."""
    text = clean_text(value)

    def rounded(match: re.Match) -> str:
        return f"{float(match.group(0)):.3f}"

    text = _FLOAT_RE.sub(rounded, text)

    def compact(match: re.Match) -> str:
        token = match.group(0)
        suffix = ""
        while token and token[-1] in ".,;:":
            suffix = token[-1] + suffix
            token = token[:-1]
        return f"{console.compact_path(token)}{suffix}"

    return _PATH_RE.sub(compact, text)


def clean_text(value: object) -> str:
    """Untrusted source text renders as text, never as markup or controls."""
    if value is None:
        return ""
    return str(value).replace("\r", "")


def ts(stamp: datetime | None) -> str:
    if stamp is None:
        return "--:--"
    return f"{stamp.astimezone():%H:%M}"


def start_time(stamp: datetime | None, now: datetime) -> str:
    if stamp is None:
        return "unavailable"
    local = stamp.astimezone()
    today = now.astimezone()
    if local.year != today.year:
        return local.strftime("%Y-%m-%d %H:%M:%S")
    return local.strftime(
        "%H:%M:%S" if local.date() == today.date() else "%d %b %H:%M:%S"
    )


def hang_styled(
    prefix: str,
    text: str,
    width: int,
    prefix_style: str = "dim",
    body_style: str | None = None,
) -> list[Text]:
    """Wrap text under a fixed prefix, styling the prefix and the body."""
    width = max(width, 20)
    out: list[Text] = []
    indent = " " * len(prefix)
    current_prefix = prefix
    for paragraph in text.split("\n") or [""]:
        if not paragraph.strip():
            out.append(Text(""))
            current_prefix = indent
            continue
        wrapped = textwrap.wrap(
            paragraph,
            width=width,
            initial_indent=current_prefix,
            subsequent_indent=indent,
            break_long_words=True,
            break_on_hyphens=False,
        )
        segments = wrapped or [current_prefix.rstrip()]
        for index, line in enumerate(segments):
            piece = Text()
            if index == 0 and current_prefix and len(line) >= len(current_prefix):
                piece.append(line[: len(current_prefix)], style=prefix_style)
                body = line[len(current_prefix) :]
            else:
                body = line
            if body:
                piece.append(body, style=body_style or "")
            out.append(piece)
        current_prefix = indent
    return out


def fit_text(text: Text, width: int) -> Text:
    if len(text.plain) <= width:
        return text
    clipped = text.copy()
    clipped.truncate(max(1, width))
    return clipped


def elapsed_text(seconds: float | None, label: str) -> str:
    if seconds is None:
        return f"{label} unavailable"
    return f"{label} {console.format_duration(float(seconds))}"


def metric_cell(value: str, missing: str = "unavailable", muted: str = "dim") -> Text:
    """Metric cell text; missing values render muted instead of invisible."""
    text = clean_text(value)
    if value == missing or value.startswith(missing):
        return Text(text, style=muted)
    return Text(text)


def progress_title(
    palette: Palette, lead: str, lead_style: str, parts: list[str], stale: bool
) -> Text:
    title = Text(lead, style=lead_style)
    for part in parts:
        title.append(" | ", style=palette.muted)
        title.append(part, style=palette.text)
    if stale:
        title.append(" | ", style=palette.muted)
        title.append("counter observation stale", style=f"bold {palette.error}")
    return title


def progress_bar_line(
    palette: Palette, label: str, first: int, total: int | None, width: int
) -> Text:
    line = Text(f"{label} {first:,}", style=f"bold {palette.accent}")
    if not total:
        line.append(" / target unavailable", style=palette.muted)
        return line
    line.append(f" / {total:,}", style=palette.muted)
    line.append("  [", style=palette.muted)
    progress = max(0.0, min(1.0, first / max(total, 1)))
    bar_width = max(8, min(width - 22, 60))
    filled = max(0, min(bar_width, round(bar_width * progress)))
    line.append("#" * filled, style=palette.success)
    line.append("-" * (bar_width - filled), style=palette.muted)
    line.append(f"] {round(progress * 100)}%", style=palette.text)
    return line


def training_lines(
    palette: Palette,
    training: projector.TrainingProgress,
    width: int,
    *,
    paused: bool = False,
) -> list[Text]:
    parts = [f"Attempt {training.attempt}"]
    if paused:
        parts.append("Paused")
    parts.append(elapsed_text(training.elapsed_seconds, "Elapsed"))
    parts.append(elapsed_text(training.eta_seconds, "ETA"))
    if isinstance(training.reward, (int, float)) and not isinstance(
        training.reward, bool
    ):
        parts.append(f"Reward {training.reward:.1f}")
    if isinstance(training.success, (int, float)) and not isinstance(
        training.success, bool
    ):
        parts.append(f"Success {round(training.success * 100)}%")
    elif isinstance(training.success, str) and training.success:
        parts.append(training.success[:1].upper() + training.success[1:])
    title = progress_title(
        palette,
        f"Training {training.operation_id}",
        f"bold {palette.accent}",
        parts,
        training.stale,
    )
    lines = [title]
    if training.steps is None:
        lines.append(Text("Steps: starting - no step count yet", style=palette.muted))
        return lines
    lines.append(
        progress_bar_line(palette, "Steps", training.steps, training.target, width)
    )
    return lines


def evaluation_lines(
    palette: Palette, evaluation: projector.EvaluationProgress, width: int
) -> list[Text]:
    lead_style = (
        f"bold {palette.success}" if evaluation.official else f"bold {palette.accent}"
    )
    lead = (
        "Official assessment"
        if evaluation.official
        else f"Evaluation {evaluation.operation_id}"
    )
    parts: list[str] = []
    if evaluation.instrument:
        parts.append(evaluation.instrument)
    if evaluation.panel_total:
        parts.append(f"Panel {evaluation.panel_index or '?'}/{evaluation.panel_total}")
    if evaluation.completed_panels:
        parts.append(
            "Completed panels "
            + (
                f"{evaluation.completed_panels}/{evaluation.panel_total}"
                if evaluation.panel_total
                else str(evaluation.completed_panels)
            )
        )
    parts.append(
        elapsed_text(
            evaluation.elapsed_seconds,
            "Panel elapsed" if evaluation.panel_total else "Elapsed",
        )
    )
    title = progress_title(palette, lead, lead_style, parts, evaluation.stale)
    lines = [title]
    if evaluation.episodes is None and evaluation.episodes_total is None:
        lines.append(Text("Running - progress unavailable", style=palette.warning))
        return lines
    lines.append(
        progress_bar_line(
            palette,
            "Episodes",
            evaluation.episodes or 0,
            evaluation.episodes_total,
            width,
        )
    )
    return lines


def assessment_style(palette: Palette, status: str) -> str:
    outcome = status.casefold()
    if outcome == "passed":
        return f"bold {palette.success}"
    if outcome == "failed":
        return f"bold {palette.error}"
    return f"bold {palette.warning}"


def role_style(palette: Palette, role: str) -> str:
    if role == "Working":
        return f"bold {palette.accent}"
    if role == "Best-known":
        return f"bold {palette.pi}"
    return palette.muted


def context_lines(
    snapshot: projector.CampaignSnapshot,
    width: int,
    *,
    palette: Palette,
    now: datetime,
    campaign_end: datetime,
    stage_end: datetime,
    paused: bool,
    owned: bool,
    budget: int,
    last_error: str,
) -> list[Text]:
    from tui.projector import campaign_age, stage_elapsed

    age = campaign_age(snapshot.started_at, campaign_end)
    elapsed = stage_elapsed(snapshot.stage_started_at, stage_end)

    gap = 3
    status = "STOPPED (TUI)" if paused and not snapshot.terminal else snapshot.status
    status_style = status_style_for(status, palette)
    left = Text("Autoresearch", style=f"bold {palette.heading}")
    left.append(" | ", style=palette.muted)
    left.append(status, style=status_style)
    left.append(" | ", style=palette.muted)
    left.append("campaign ", style=palette.muted)
    left.append(snapshot.campaign_id[:13], style=palette.muted)
    age_label = "Campaign elapsed" if owned else "Campaign age"
    campaign_time = Text(f"{age_label} {age} (started ", style=palette.muted)
    campaign_time.append(start_time(snapshot.started_at, now), style=palette.text)
    campaign_time.append(")", style=palette.muted)
    stage_time = Text(f"Stage elapsed {elapsed} (started ", style=palette.muted)
    stage_time.append(start_time(snapshot.stage_started_at, now), style=palette.text)
    stage_time.append(")", style=palette.muted)
    right = campaign_time.copy()
    right.append(" | ", style=palette.muted)
    right.append_text(stage_time)
    timing_rows: list[Text] = []
    if len(left.plain) + gap + len(right.plain) <= width:
        first = Text()
        first.append_text(left)
        first.append(" " * (width - len(left.plain) - len(right.plain)))
        first.append_text(right)
    else:
        first = left
        timing_rows = (
            [right] if len(right.plain) <= width else [campaign_time, stage_time]
        )
    lines: list[Text] = [
        first if len(first.plain) <= width else Text(first.plain[:width])
    ]
    lines.extend(fit_text(row, width) for row in timing_rows)

    stage = Text()
    stage.append("Stage: ", style=palette.muted)
    if snapshot.stage_ids:
        stage.append(snapshot.stage_ids, style=f"bold {palette.accent}")
        stage.append(" | ", style=palette.muted)
    stage.append(
        snapshot.stage_text,
        style=f"bold {palette.warning}"
        if snapshot.terminal
        else f"bold {palette.accent}",
    )
    activity = Text()
    activity.append("Current activity: ", style=palette.muted)
    activity.append(
        snapshot.activity_text,
        style=palette.accent
        if "not observed" not in snapshot.activity_text
        else palette.muted,
    )
    if len(stage.plain) + gap + len(activity.plain) <= width:
        second = Text()
        second.append_text(stage)
        second.append(" " * (width - len(stage.plain) - len(activity.plain)))
        second.append_text(activity)
    else:
        second = stage
    lines.append(fit_text(second, width))

    goal = snapshot.goal
    goal_line = Text()
    goal_line.append("Goal", style=palette.muted)
    if goal.target_percent is not None:
        goal_line.append(" >=", style=palette.muted)
        goal_line.append(f"{goal.target_percent:g}%", style=f"bold {palette.heading}")
    elif goal.text:
        goal_line.append(f": {goal.text}", style=palette.text)
    else:
        goal_line.append(" unavailable", style=palette.muted)
    if goal.best_percent is not None:
        goal_line.append(" | best ", style=palette.muted)
        goal_line.append(f"{goal.best_percent:g}%", style=palette.text)
    else:
        goal_line.append(" | best not measured", style=palette.muted)
    if goal.gap_points is not None:
        gap_style = palette.error if goal.gap_points < 0 else palette.success
        goal_line.append(f" | {goal.gap_points:+.1f} pts", style=f"bold {gap_style}")
    elif goal.gap_text:
        goal_line.append(f" | {goal.gap_text}", style=palette.muted)
    lines.append(fit_text(goal_line, width))

    counters_line = Text()
    if snapshot.pending_text:
        counters_line.append(snapshot.pending_text, style=f"bold {palette.warning}")
        if snapshot.counters_text:
            counters_line.append(" | ", style=palette.muted)
    if snapshot.counters_text:
        counters_line.append(snapshot.counters_text, style=palette.muted)
    if counters_line.plain:
        lines.append(fit_text(counters_line, width))

    excerpt_rows = max(0, budget - 4 - len(timing_rows))
    leads: list[Text] = []
    question = clean_text(snapshot.question) or clean_text(snapshot.objective)
    if question and excerpt_rows:
        prefix = (
            f"Inquiry [{snapshot.question_source}]: "
            if snapshot.question
            else "Objective: "
        )
        take = 2 if width >= 120 and excerpt_rows >= 4 else 1
        leads.extend(
            hang_styled(prefix, question, width, palette.warning, palette.text)[:take]
        )
    synthesis = clean_text(snapshot.synthesis)
    if synthesis and excerpt_rows > len(leads):
        prefix = f"PI record {snapshot.synthesis_session or 'S?'}: "
        take = 2 if width >= 120 and excerpt_rows - len(leads) >= 3 else 1
        leads.extend(
            hang_styled(prefix, synthesis, width, palette.pi, palette.text)[:take]
        )
    lines.extend(leads)

    usage = clean_text(projector.usage_text(snapshot.usage))[:width]
    usage_text_obj = Text()
    usage_text_obj.append("Usage recorded", style=palette.muted)
    usage_text_obj.append(usage[len("Usage recorded") :], style=palette.text)
    lines.append(usage_text_obj)
    if snapshot.official_text:
        lines.append(
            Text(
                clean_text(snapshot.official_text)[:width],
                style=assessment_style(palette, snapshot.official_status),
            )
        )
    if last_error:
        attention = f"Attention: {last_error}"
        if len(attention) > width:
            attention = attention[: max(1, width - 1)] + "…"
        lines.append(Text(attention, style=f"bold {palette.error}"))
    return lines[: budget + 2]
