"""Console presentation for the Runner.

The Runner formats facts the researcher already decided or the tools already
measured. It never adds a scientific conclusion of its own.
"""

import sys
from datetime import datetime


_RESET = "\033[0m"
_DIM = "\033[90m"
_CYAN = "\033[1;96m"
_YELLOW = "\033[1;93m"
_RED = "\033[1;91m"
_SECTION_HEADINGS = frozenset(
    {
        "Hypothesis",
        "Experiment",
        "Training dynamics",
        "Candidates",
        "Next",
        "Question",
        "Plan",
        "Reason",
        "Candidate",
        "Champion",
        "Task reference",
        "Paired comparison",
        "Continue from",
        "Code",
        "Retained alternatives",
        "Removed retained alternatives",
        "Final benchmark",
    }
)


def _style_card_sections(text: str) -> str:
    lines = text.splitlines(keepends=True)
    return "".join(
        f"{_YELLOW}{line}{_RESET}"
        if line.rstrip("\r\n") in _SECTION_HEADINGS
        else line
        for line in lines
    )


def announce(message: str) -> None:
    leading_break = "\n" if message.startswith("\n") else ""
    text = message.lstrip("\n")
    timestamp = f"[{datetime.now():%H:%M:%S}]"
    if sys.stdout.isatty() and text.startswith("==="):
        title, separator, remainder = text.partition("\n")
        text = f"{_CYAN}{timestamp} {title}{_RESET}{separator}{_style_card_sections(remainder)}"
        timestamp = ""
    elif sys.stdout.isatty() and text.startswith("[") and "]" in text:
        prefix, _, remainder = text.partition("]")
        color = _RED if prefix == "[error" else _CYAN
        text = f"{color}{prefix}]{_RESET}{remainder}"
        timestamp = f"{_DIM}{timestamp}{_RESET}"
    separator = " " if timestamp else ""
    print(f"{leading_break}{timestamp}{separator}{text}", flush=True)


def format_duration(seconds: float) -> str:
    total = max(int(seconds), 0)
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{seconds:02d}s"
    return f"{seconds}s"


def scenario_progress_metric(record: dict[str, float]) -> str | None:
    """The one live training metric the scenario owns, resolved on demand.

    Imported here rather than at module scope so presenting a card never pulls
    the training and physics stack into a validation-only command.
    """
    from robot_learning.scenario import render_training_progress_metric

    return render_training_progress_metric(record)


def experiment_change_lines(result: dict) -> list[str]:
    changes = result.get("parameter_changes") or []
    if changes:
        return [
            f"{item['path']}: {item.get('before')} → {item.get('after')}"
            for item in changes
        ]
    return [str(result.get("change", "")).strip() or "-"]


def render_experiment_card(result: dict) -> str:
    budget = result.get("training_budget_steps")
    return "\n".join(
        [
            f"=== Research hypothesis · Experiment {result['index']} ===",
            "",
            "Hypothesis",
            str(result.get("hypothesis", "")).strip() or "-",
            "",
            "Experiment",
            *experiment_change_lines(result),
            "",
            f"Family : {result.get('family', '-')}",
            f"Parent : {result.get('training_parent', '-')}",
            f"Init   : {result.get('initialization', '-')}",
            f"Seed   : {result.get('training_seed', '-')}",
            f"Budget : {int(budget):,} steps" if budget else "Budget : -",
        ]
    )


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


def _metric_transition(
    first: dict[str, float],
    final: dict[str, float],
    key: str,
) -> tuple[str, str] | None:
    before, after = first.get(key), final.get(key)
    if before is None or after is None:
        return None
    return f"{float(before):g}", f"{float(after):g}"


def _scenario_transition(
    first: dict[str, float],
    final: dict[str, float],
) -> tuple[str, str, str] | None:
    before = scenario_progress_metric(first)
    after = scenario_progress_metric(final)
    if not before or not after:
        return None
    before_label, _, before_value = before.partition(" ")
    after_label, _, after_value = after.partition(" ")
    if before_value and before_label == after_label:
        return before_label.capitalize(), before_value, after_value
    return "Scenario", before, after


def training_dynamics_rows(records: list[dict[str, float]]) -> list[str]:
    if not records:
        return []
    first, final = records[0], records[-1]
    rows: list[tuple[str, str, str]] = []
    reward = _metric_transition(first, final, "ep_rew_mean")
    if reward is not None:
        rows.append(("Reward mean", *reward))
    scenario = _scenario_transition(first, final)
    if scenario is not None:
        rows.append(scenario)
    for label, key in (
        ("Episode length", "ep_len_mean"),
        ("Policy std", "std"),
        ("Explained variance", "explained_variance"),
    ):
        transition = _metric_transition(first, final, key)
        if transition is not None:
            rows.append((label, *transition))
    if not rows:
        return []
    label_width = max(len(label) for label, _, _ in rows)
    value_width = max(len(before) for _, before, _ in rows)
    return [
        f"  {label:<{label_width}}  {before:>{value_width}} → {after}"
        for label, before, after in rows
    ]


def render_training_summary_card(
    result: dict,
    *,
    records: list[dict[str, float]],
    completed_steps: int,
    elapsed_seconds: float,
    candidate_names: list[str],
) -> str:
    budget = result.get("training_budget_steps")
    lines = [
        f"=== Training summary · Experiment {result['index']} ===",
        "",
        f"Hypothesis : {str(result.get('hypothesis', '')).strip() or '-'}",
        f"Change     : {'; '.join(experiment_change_lines(result))}",
        f"Family     : {result.get('family', '-')}",
        f"Parent     : {result.get('training_parent', '-')}",
        f"Init       : {result.get('initialization', '-')}",
        f"Seed       : {result.get('training_seed', '-')}",
        f"Budget     : {int(budget):,} steps" if budget else "Budget     : -",
        (
            f"Completed  : {completed_steps:,} steps in "
            f"{format_duration(elapsed_seconds)}"
        ),
    ]
    dynamics = training_dynamics_rows(records)
    if dynamics:
        lines.extend(["", "Training dynamics", *dynamics])
    lines.extend(["", "Candidates"])
    lines.extend(f"  {name}" for name in candidate_names)
    lines.extend(["", "Next", "  Researcher evaluation design"])
    return "\n".join(lines)


def evaluation_plan_rows(request: dict) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for spec in request.get("evaluations") or []:
        if not isinstance(spec, dict):
            continue
        name = str(spec.get("label") or spec.get("candidate", "")).strip() or "-"
        try:
            detail = f"{int(spec['episodes'])} episodes · seed {int(spec['seed'])}"
        except (KeyError, TypeError, ValueError):
            detail = "episodes and seed pending validation"
        rows.append((name, detail))
    for spec in request.get("task_reference_evaluations") or []:
        if not isinstance(spec, dict):
            continue
        name = str(spec.get("candidate", "")).strip() or "-"
        rows.append(("task reference", name))
    for comparison in request.get("paired_comparisons") or []:
        if not isinstance(comparison, dict):
            continue
        candidate = comparison.get("candidate", "?")
        reference = comparison.get("reference", "?")
        rows.append(("paired comparison", f"{candidate} vs {reference}"))
    return rows


def render_evaluation_plan(request: dict, experiment: int) -> str:
    lines = [f"=== Evaluation design · Experiment {experiment} ===", ""]
    question = str(request.get("question", "")).strip()
    if question:
        lines.extend(["Question", question, ""])
    rows = evaluation_plan_rows(request)
    if rows:
        width = max(len(name) for name, _ in rows)
        lines.append("Plan")
        lines.extend(f"  {name:<{width}}   {detail}" for name, detail in rows)
    reason = str(request.get("reason", "")).strip()
    if reason:
        lines.extend(["", "Reason", reason])
    return "\n".join(lines)


def summary_headline(summary: dict) -> str:
    success = summary.get("pooled_success_percent", summary.get("success_percent"))
    episodes = int(summary.get("episodes", 0))
    if success is None:
        return f"{episodes} episodes"
    return f"success {float(success):.1f}% · {episodes} episodes"


def render_evidence_card(
    experiment: int,
    candidates: list[dict],
    champion_summary: dict | None,
    comparisons: list[dict],
    next_phase: str,
    task_reference_evaluations: list[dict] | None = None,
) -> str:
    lines = [f"=== Evidence · Experiment {experiment} ===", ""]
    measured = [item for item in candidates if item.get("summary") is not None]
    if measured:
        width = max(len(str(item["name"])) for item in measured)
        lines.append("Candidate")
        lines.extend(
            f"  {item['name']!s:<{width}}   {summary_headline(item['summary'])}"
            for item in measured
        )
        lines.append("")
    if champion_summary is not None:
        lines.extend(["Champion", f"  {summary_headline(champion_summary)}", ""])
    references = task_reference_evaluations or []
    if references:
        width = max(len(str(item["candidate"])) for item in references)
        lines.append("Task reference")
        lines.extend(
            f"  {item['candidate']!s:<{width}}   "
            f"success {float(item['success_percent']):.1f}% · "
            f"{int(item['episodes'])} episodes · {item['panel']}"
            for item in references
        )
        lines.append("")
    for comparison in comparisons:
        delta = float(comparison["success_delta_percent"])
        lines.extend(
            [
                "Paired comparison",
                f"  {comparison['candidate']} vs {comparison['reference']}",
                f"  delta {delta:+.1f} pp",
                "",
            ]
        )
    lines.extend(["Next", f"  {next_phase}"])
    return "\n".join(lines)


def render_decision_card(plan: dict) -> str:
    pending = plan["pending"]
    retained = [
        f"  {retention['record']['id']} (from {retention['record']['candidate']})"
        for retention in plan["retentions"]
    ]
    lines = [
        f"=== Research decision · Experiment {int(pending['experiment'])} ===",
        "",
        "Continue from",
        plan["selected_name"],
        "",
        "Reason",
        str(plan["decision"]["reason"]).strip(),
        "",
        "Code",
        plan["code_action"],
        "",
        "Retained alternatives",
        *(retained or ["  none"]),
    ]
    if plan["removed_retained"]:
        lines.extend(
            [
                "",
                "Removed retained alternatives",
                *(f"  {lineage['id']}" for lineage in plan["removed_retained"]),
            ]
        )
    lines.extend(
        [
            "",
            "Final benchmark",
            "requested" if plan["request_final_benchmark"] else "not requested",
        ]
    )
    return "\n".join(lines)
