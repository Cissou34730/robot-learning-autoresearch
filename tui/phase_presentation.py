"""Campaign tab presentation, kept separate from execution and phase transitions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath

from rich.cells import cell_len


def tab_folder_text(folder: PurePath, width: int) -> str:
    text = str(folder)
    if cell_len(text) <= width:
        return text
    for start in range(1, len(folder.parts) - 1):
        compact = str(folder.with_segments("...", *folder.parts[start:]))
        if cell_len(compact) <= width:
            return compact
    return ""


@dataclass(frozen=True)
class PhasePresentation:
    dark: str
    light: str
    pulse: bool = False
    outcome: bool = False


TAB_STATE_COLOURS = {
    "failed": "$error",
    "attention": "$warning",
    "running": "$success",
    "quiet": "$text-muted",
}

PHASE_PRESENTATIONS = {
    "training": PhasePresentation("#5aa9ff", "#0b5cc4", pulse=True),
    "evaluating": PhasePresentation("#4ed8e0", "#00747d", pulse=True),
    "coding": PhasePresentation("#e07cf0", "#8b1fa0", pulse=True),
    "official": PhasePresentation("#ffd54a", "#946b00", pulse=True),
    "preparing": PhasePresentation("#a58bff", "#5b3fc7"),
    "completed": PhasePresentation("#8aa4c8", "#4b6584"),
    "official_passed": PhasePresentation("#3ddc84", "#0a7d3b", outcome=True),
    "official_failed": PhasePresentation("#ff9a3c", "#b35900", outcome=True),
}

TAB_PHASE_COLOURS = {
    phase: (presentation.dark, presentation.light)
    for phase, presentation in PHASE_PRESENTATIONS.items()
}
TAB_TAG_COLOURS = {
    **TAB_STATE_COLOURS,
    **{tag: pair[0] for tag, pair in TAB_PHASE_COLOURS.items()},
}

PULSING_TAGS = frozenset(
    phase for phase, presentation in PHASE_PRESENTATIONS.items() if presentation.pulse
)

OUTCOME_TAGS = frozenset(
    phase for phase, presentation in PHASE_PRESENTATIONS.items() if presentation.outcome
)


def tab_tag(stage: str, stalled: bool, phase: str = "none", outcome: str = "") -> str:
    """The tag for one campaign tab. State beats phase: a failed or stalled
    campaign keeps its warning colour whatever it was doing. Once the campaign
    is not running, the final benchmark's outcome is what the tab shows."""
    if stage == "failed":
        return "failed"
    if stage in {"stopping", "resetting"}:
        return "attention"
    if stage in {"launching", "running"}:
        if stalled:
            return "attention"
        return phase if phase in TAB_PHASE_COLOURS else "running"
    if outcome in {"passed", "failed"}:
        return f"official_{outcome}"
    if stage == "completed":
        return "completed"
    return "quiet"
