"""Build bounded research context for token-efficient autonomous sessions."""

from __future__ import annotations

import json
import re
from pathlib import Path

from robot_learning.benchmark.spec import HOLD_SECONDS, SUCCESS_THRESHOLD

ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DIR = ROOT / "research"
TRAIN_LOG_PATH = RESEARCH_DIR / "last_train.log"
TRAIN_SUMMARY_PATH = RESEARCH_DIR / "last_train_summary.md"
BRIEF_PATH = RESEARCH_DIR / "brief.md"


def _compact(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def parse_training_records(text: str) -> list[dict[str, float]]:
    records: list[dict[str, float]] = []
    current: dict[str, float] = {}
    section = ""

    for line in text.splitlines():
        section_match = re.match(r"\|\s+(rollout|time|train)/\s+\|", line)
        if section_match:
            next_section = section_match.group(1)
            if next_section == "rollout" and "total_timesteps" in current:
                records.append(current)
                current = {}
            section = next_section
            continue

        value_match = re.match(
            r"\|\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+\|\s+"
            r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?)\s+\|",
            line,
            flags=re.IGNORECASE,
        )
        if value_match and section:
            key = value_match.group(1)
            try:
                current[key] = float(value_match.group(2))
            except ValueError:
                continue

    if current:
        records.append(current)
    return records


def _format_value(record: dict[str, float], key: str) -> str:
    value = record.get(key)
    if value is None:
        return "-"
    return f"{value:g}"


def render_training_summary(log_text: str) -> str:
    records = parse_training_records(log_text)
    if not records:
        tail = _compact("\n".join(log_text.splitlines()[-20:]), 1200)
        return (
            "# Last Training Summary\n\n"
            "No Stable-Baselines3 metric blocks were parsed.\n\n"
            f"Log tail: {tail or '(empty log)'}\n"
        )

    first = records[0]
    peak = max(records, key=lambda row: row.get("success_rate", float("-inf")))
    final = records[-1]
    fields = [
        ("Steps", "total_timesteps"),
        ("Success", "success_rate"),
        ("Episode length", "ep_len_mean"),
        ("Reward", "ep_rew_mean"),
        ("Policy std", "std"),
        ("Explained variance", "explained_variance"),
        ("Value loss", "value_loss"),
    ]

    lines = [
        "# Last Training Summary",
        "",
        (
            f"Compressed from {len(log_text.encode('utf-8')):,} bytes and "
            f"{len(records)} metric snapshots."
        ),
        "",
        "| Metric | First | Peak-success snapshot | Final |",
        "|---|---:|---:|---:|",
    ]
    for label, key in fields:
        lines.append(
            f"| {label} | {_format_value(first, key)} | "
            f"{_format_value(peak, key)} | {_format_value(final, key)} |"
        )

    peak_index = records.index(peak)
    zero_after_peak = next(
        (row for row in records[peak_index + 1 :] if row.get("success_rate") == 0),
        None,
    )
    lines.extend(
        [
            "",
            (
                f"- Peak success: {_format_value(peak, 'success_rate')} at "
                f"{_format_value(peak, 'total_timesteps')} steps."
            ),
            "- First zero-success snapshot after the peak: "
            + (
                f"{_format_value(zero_after_peak, 'total_timesteps')} steps."
                if zero_after_peak
                else "not observed."
            ),
            f"- Final policy std: {_format_value(final, 'std')}.",
        ]
    )

    model_match = re.search(r"Model saved to\s+(.+model\.zip)", log_text)
    if model_match:
        lines.append(f"- Saved model: {_compact(model_match.group(1), 240)}.")
    return "\n".join(lines) + "\n"


def write_training_summary() -> Path:
    text = TRAIN_LOG_PATH.read_text(encoding="utf-8") if TRAIN_LOG_PATH.exists() else ""
    TRAIN_SUMMARY_PATH.write_text(render_training_summary(text), encoding="utf-8")
    return TRAIN_SUMMARY_PATH


def _experiment_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        if not re.match(r"^\|\s*\d+\s*\|", line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 8:
            rows.append(cells)
    return rows


def _postmortem_memory(text: str, count: int = 3) -> list[str]:
    sections = re.split(r"(?=^## Experiment \d+\b)", text, flags=re.MULTILINE)
    sections = [
        section.strip() for section in sections if section.startswith("## Experiment")
    ]
    memories: list[str] = []
    labels = [
        "Result",
        "Likely current binding constraint",
        "What was learned / do NOT retry",
        "Recommended next experiment class",
    ]
    for section in sections[-count:]:
        title = section.splitlines()[0].removeprefix("## ").strip()
        parts = [f"**{_compact(title, 180)}**"]
        for label in labels:
            match = re.search(
                rf"\*\*{re.escape(label)}:\*\*\s*(.+?)(?=\n\s*\n|\n\*\*|\Z)",
                section,
                flags=re.DOTALL,
            )
            if match:
                parts.append(f"{label}: {_compact(match.group(1), 420)}")
        memories.append("\n".join(parts))
    return memories


def render_research_brief() -> str:
    postmortems_path = RESEARCH_DIR / "postmortems.md"
    params_path = RESEARCH_DIR / "current_params.json"
    state_path = RESEARCH_DIR / "research_state.json"
    results_path = RESEARCH_DIR / "results.jsonl"

    postmortems = (
        postmortems_path.read_text(encoding="utf-8")
        if postmortems_path.exists()
        else ""
    )
    params = json.loads(params_path.read_text(encoding="utf-8"))
    state = (
        json.loads(state_path.read_text(encoding="utf-8"))
        if state_path.exists()
        else {}
    )
    results = []
    if results_path.exists():
        results = [
            json.loads(line)
            for line in results_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    accepted_metrics = state.get("accepted_metrics")
    accepted_score = None
    if accepted_metrics is not None:
        accepted_score = accepted_metrics.get(
            "pooled_success_percent", accepted_metrics.get("success_percent")
        )
    accepted_status = (
        f"{accepted_score:g}%" if accepted_score is not None else "baseline pending"
    )
    accepted_progress = (
        accepted_metrics.get("failed_episode_progress", {})
        if accepted_metrics is not None
        else {}
    )

    lines = [
        "# Compact Research Brief",
        "",
        (
            "This is the default context for one autonomous experiment. Read the full "
            "history only when this brief identifies a genuine ambiguity."
        ),
        "",
        "## Immutable goal",
        "",
        (
            "Reach a random target 6–20 cm away, remain within 1.0 cm for 100 "
            "consecutive control steps (2.0 s), and achieve at least 98% over the "
            "fixed 200-episode evaluation."
        ),
        "",
        "## Current status",
        "",
        f"- Evaluation target: {100 * SUCCESS_THRESHOLD:g} cm / {HOLD_SECONDS:g} s",
        f"- Selection method: v{state.get('selection_method_version', 1)}",
        f"- Accepted success: {accepted_status}",
        (
            f"- Accepted seeds passing 98%: "
            f"{accepted_metrics.get('seeds_passing_98_percent', '-') if accepted_metrics else '-'}"
            f"/{accepted_metrics.get('seed_count', '-') if accepted_metrics else '-'}"
        ),
        f"- Accepted failed episodes: {accepted_progress.get('failed_episodes', '-')}",
        f"- Accepted checkpoint: {state.get('accepted_artifact', 'missing')}",
        f"- Last experiment: {state.get('last_experiment', 'none')}",
        f"- Last verdict: {state.get('last_verdict', 'none')}",
        "",
        "## Current parameters",
        "",
        "```json",
        json.dumps(params, indent=2),
        "```",
        "",
        (
            "## Current experiments"
        ),
        "",
        "| # | Change | Pooled success | Seeds passed | Failed hold | Best window | Verdict |",
        "|---:|---|---:|---:|---:|---:|---|",
    ]

    for result in results[-5:]:
        candidate = result.get("candidate_metrics", {})
        progress = candidate.get("failed_episode_progress", {})
        pooled_success = candidate.get(
            "pooled_success_percent", candidate.get("success_percent", "-")
        )
        passed = candidate.get("seeds_passing_98_percent", "-")
        seed_count = candidate.get("seed_count", "-")
        lines.append(
            f"| {result['index']} | {_compact(result['change'], 180)} | "
            f"{pooled_success} | "
            f"{passed}/{seed_count} | "
            f"{progress.get('longest_consecutive_steps_mean', '-')} | "
            f"{progress.get('best_window_inside_steps_mean', '-')} | "
            f"{_compact(result['verdict'], 80)} |"
        )
    if not results:
        lines.append("| - | New baseline pending | - | - | - | - | - |")

    lines.extend(["", "## Recent scientific memory", ""])
    memories = _postmortem_memory(postmortems)
    if memories:
        for memory in memories:
            lines.extend([memory, ""])
    else:
        lines.extend(["No postmortem entries yet.", ""])

    if TRAIN_SUMMARY_PATH.exists():
        summary = TRAIN_SUMMARY_PATH.read_text(encoding="utf-8")
        lines.extend(["## Most recent training dynamics", "", summary, ""])

    lines.extend(
        [
            "## Context discipline",
            "",
            "- Do not read the full training log; use `research/last_train_summary.md`.",
            (
                "- Do not read full experiment or postmortem history unless the compact "
                "evidence is insufficient for one specific decision."
            ),
            "- One experiment, one hypothesis, no subagents.",
            "- Record only 5-8 concise postmortem lines.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_research_brief() -> Path:
    write_training_summary()
    BRIEF_PATH.write_text(render_research_brief(), encoding="utf-8")
    return BRIEF_PATH


def main() -> None:
    brief = write_research_brief()
    print(f"Wrote {brief.relative_to(ROOT)}")
    print(f"Wrote {TRAIN_SUMMARY_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
