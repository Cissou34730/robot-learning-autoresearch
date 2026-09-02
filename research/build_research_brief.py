"""Build bounded research context for token-efficient autonomous sessions."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DIR = ROOT / "research"
BRIEF_PATH = RESEARCH_DIR / "brief.md"


def _compact(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _candidate_metric(candidate: dict, key: str) -> str:
    value = candidate.get(key)
    return "unavailable" if value is None else f"{float(value):g}"


def _postmortem_memory(text: str, count: int = 3) -> list[str]:
    sections = re.split(r"(?=^## Experiment \d+\b)", text, flags=re.MULTILINE)
    sections = [
        section.strip() for section in sections if section.startswith("## Experiment")
    ]
    memories: list[str] = []
    # Each rendered label accepts every heading past and present entries use, so
    # historical postmortems stay readable without being rewritten.
    labels = [
        ("Result", ("Result",)),
        ("Observed behavior", ("Observed behavior",)),
        (
            "Interpretation",
            (
                "Interpretation",
                "Interpretation / what was learned",
                "What was learned",
                "What was learned / do NOT retry",
            ),
        ),
        ("Evidence inspected", ("Evidence inspected",)),
    ]
    # Losing the narrative sections would erase the entry, so an unfamiliar
    # heading falls back to the raw section instead of being dropped.
    narrative = {"Result", "Observed behavior", "Interpretation"}
    for section in sections[-count:]:
        title = section.splitlines()[0].removeprefix("## ").strip()
        parts = [f"**{_compact(title, 180)}**"]
        recognized: set[str] = set()
        for display, headings in labels:
            for heading in headings:
                match = re.search(
                    rf"\*\*{re.escape(heading)}:\*\*\s*(.+?)(?=\n\s*\n|\n\*\*|\Z)",
                    section,
                    flags=re.DOTALL,
                )
                if match:
                    parts.append(f"{display}: {_compact(match.group(1), 420)}")
                    recognized.add(display)
                    break
        if not recognized & narrative:
            body = "\n".join(section.splitlines()[1:]).strip()
            if body:
                parts.insert(1, _compact(body, 420))
        memories.append("\n".join(parts))
    return memories


def _evaluation_panel_lines(evaluations: list[dict]) -> list[str]:
    """Point at the detailed measurements without interpreting any of them."""
    lines: list[str] = []
    for evaluation in evaluations:
        success = evaluation.get("success_percent")
        detail = (
            f"  - {int(evaluation['episodes'])} episodes, seed "
            f"{evaluation.get('seed', '-')}"
        )
        if success is not None:
            detail += f", success {float(success):.2f}%"
        artifact = evaluation.get("evaluation_artifact")
        if artifact:
            detail += f"; detail `{artifact}`"
        lines.append(detail)
    return lines


def _task_reference_lines(evaluations: list[dict]) -> list[str]:
    """Name the human-owned measurements and where their detail lives."""
    lines: list[str] = []
    for evaluation in evaluations:
        detail = (
            f"- task reference `{evaluation['candidate']}` on "
            f"`{evaluation.get('panel', '-')}`: success "
            f"{float(evaluation['success_percent']):.2f}% over "
            f"{int(evaluation['episodes'])} episodes"
        )
        artifact = evaluation.get("evaluation_artifact")
        if artifact:
            detail += f"; detail `{artifact}`"
        lines.append(detail)
    return lines


def _change_details(result: dict) -> str:
    parameter_changes = result.get("parameter_changes") or []
    if parameter_changes:
        return "; ".join(
            f"{item['path']}: {item.get('before')} → {item.get('after')}"
            for item in parameter_changes
        )
    hypothesis = str(result.get("hypothesis", ""))
    transitions = re.findall(
        r"(?:from\s+)?(`?[-+]?\d[\d,._e-]*`?)\s+"
        r"(?:to|->|→)\s+(`?[-+]?\d[\d,._e-]*`?)",
        hypothesis,
        flags=re.IGNORECASE,
    )
    if transitions:
        unique_transitions = list(dict.fromkeys(transitions))
        return "; ".join(f"{before} → {after}" for before, after in unique_transitions)
    code_changes = result.get("code_changes") or []
    if code_changes:
        return f"{result.get('change', '-')}; files: {', '.join(code_changes)}"
    return str(result.get("change", "-"))


def _experiment_outcome(result: dict) -> str:
    candidate = result.get("candidate_metrics") or {}
    success = candidate.get("pooled_success_percent", candidate.get("success_percent"))
    parts = []
    if success is not None:
        parts.append(f"success {float(success):.2f}%")
    if result.get("requested_evaluations"):
        parts.append(f"{len(result['requested_evaluations'])} requested measurements")
    if result.get("error"):
        parts.append(_compact(str(result["error"]), 120))
    return "; ".join(parts) or "no measured candidate result"


def _replicated_experiment_index(result: dict) -> int | None:
    raw_value = result.get("replication_of")
    if raw_value is None:
        return None
    try:
        return int(str(raw_value))
    except ValueError:
        return None


def _result_index(result: dict) -> int | None:
    raw_value = result.get("index")
    if raw_value is None:
        return None
    try:
        return int(str(raw_value))
    except ValueError:
        return None


def _replication_groups(results: list[dict]) -> list[tuple[str, list[dict]]]:
    groups: dict[int, list[dict]] = {}
    for result in results:
        replicated_experiment = _replicated_experiment_index(result)
        if replicated_experiment is not None:
            groups.setdefault(replicated_experiment, [])
    results_by_index: dict[int, dict] = {}
    for result in results:
        result_index = _result_index(result)
        if result_index is not None:
            results_by_index[result_index] = result
    for original, entries in groups.items():
        if original in results_by_index:
            entries.append(results_by_index[original])
        for result in results:
            if _replicated_experiment_index(result) == original:
                entries.append(result)
    return [
        (str(original), entries)
        for original, entries in groups.items()
        if len(entries) > 1
    ]


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
    declared_method = params.get("algorithm", {}).get("name")
    current_method = str(declared_method).upper() if declared_method else "unspecified"
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
    latest_result = results[-1] if results else None
    accepted_score = None
    if accepted_metrics is not None:
        accepted_score = accepted_metrics.get(
            "pooled_success_percent", accepted_metrics.get("success_percent")
        )
    accepted_status = (
        f"{accepted_score:g}%" if accepted_score is not None else "baseline pending"
    )
    official_metrics = state.get("official_metrics")
    accepted_seed_count = (
        accepted_metrics.get("seed_count") if accepted_metrics else None
    )
    pending_evaluation = state.get("pending_evaluation_request")
    evaluation_lines: list[str] = []
    if pending_evaluation:
        evaluation_lines = [
            "",
            "## Evaluation design required",
            "",
            (
                f"Experiment {pending_evaluation['experiment']} finished training. "
                "The runner saved checkpoints but made no ranking or selection."
            ),
            f"Available candidates ({len(pending_evaluation['candidates'])}):",
        ]
        for candidate in sorted(
            pending_evaluation["candidates"], key=lambda item: int(item["timesteps"])
        ):
            evaluation_lines.append(
                f"- `{candidate['name']}` — {int(candidate['timesteps']):,} steps; "
                f"training success {_candidate_metric(candidate, 'training_success')}; "
                f"training reward {_candidate_metric(candidate, 'ep_rew_mean')}; "
                f"artifact `{candidate['artifact']}`."
            )
        if pending_evaluation.get("champion_available"):
            evaluation_lines.append("- `champion` — current accepted model lineage.")
        evaluation_lines.extend(
            _task_reference_lines(
                pending_evaluation.get("partial_task_reference_evaluations", []) or []
            )
        )
        evaluation_lines.extend(
            [
                "",
                (
                    "Decide what evidence this experiment needs. You may inspect "
                    "existing evidence, run a small local analysis, and change "
                    "researcher-owned evaluation or instrumentation code before "
                    "deciding which candidates to measure, with which episode "
                    "counts, seeds and labels. Write "
                    "`research/evaluation_request.json` with the scientific "
                    "`question`, the `reason` this plan is sufficient, and the "
                    "evaluations, then exit. There is no automatic tournament."
                ),
                (
                    "`research/program.md` describes when a stable human-owned "
                    "`task_reference_evaluations` measurement is the right "
                    "instrument instead of, or alongside, your own evaluations."
                ),
            ]
        )

    pending_decision = state.get("pending_researcher_decision")
    decision_lines: list[str] = []
    if pending_decision:
        choices = [item["name"] for item in pending_decision["candidates"]]
        if pending_decision.get("champion_available"):
            choices.append("champion")
        decision_lines = [
            "",
            "## Researcher lineage decision required",
            "",
            (
                f"Experiment {pending_decision['experiment']} has been measured. "
                "The runner made no promotion or rollback decision."
            ),
            (
                "The next proposal must include `previous_result_decision` with "
                f"`experiment`, `continue_from` ({', '.join(choices)}), `reason`, "
                "and a `code` decision (`keep` or `revert`) with its reason."
            ),
            (
                "The code/configuration parent before that experiment was commit "
                f"`{pending_decision.get('code_parent_commit', 'unknown')}`."
            ),
            (
                "Open the detailed evaluation artifacts listed below before "
                "writing the postmortem or choosing a lineage. They hold the "
                "full record of each measurement."
            ),
        ]
        for candidate in pending_decision["candidates"]:
            summary = candidate.get("summary")
            if summary is None:
                decision_lines.append(
                    f"- {candidate['name']}: not measured by the requested plan."
                )
            else:
                decision_lines.append(
                    f"- {candidate['name']}: pooled success "
                    f"{summary['pooled_success_percent']:.2f}%; "
                    f"{summary['episodes']} episodes over {summary['seed_count']} "
                    f"seed(s)."
                )
                decision_lines.extend(
                    _evaluation_panel_lines(candidate.get("evaluations", []))
                )
        champion_summary = pending_decision.get("champion_summary")
        if champion_summary is not None:
            decision_lines.append(
                f"- champion: pooled success "
                f"{champion_summary['pooled_success_percent']:.2f}%; "
                f"{champion_summary['episodes']} episodes over "
                f"{champion_summary['seed_count']} seed(s)."
            )
            decision_lines.extend(
                _evaluation_panel_lines(
                    pending_decision.get("champion_evaluations", [])
                )
            )
        decision_lines.extend(
            _task_reference_lines(
                pending_decision.get("task_reference_evaluations", []) or []
            )
        )

    state_last_index = int(state.get("last_experiment", 0))
    latest_result_index = int(latest_result["index"]) if latest_result else 0
    if state_last_index >= latest_result_index:
        displayed_last_experiment = state_last_index or "none"
        displayed_last_verdict = state.get("last_verdict", "none")
    else:
        displayed_last_experiment = latest_result_index
        displayed_last_verdict = latest_result["verdict"] if latest_result else "none"

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
            "The current scientific problem, its protected task definition, and its "
            "terminology are defined in `research/scenario.md`. Read it together "
            "with `research/program.md`."
        ),
        "",
        "## Current status",
        "",
        f"- Accepted success: {accepted_status}",
        (
            f"- Accepted seed panels: "
            f"{accepted_seed_count if accepted_seed_count is not None else '-'}"
            + (
                " (legacy single-seed measurement)"
                if accepted_metrics and "seed_count" not in accepted_metrics
                else ""
            )
        ),
        (
            "- Reported result: pending"
            if official_metrics is None
            else f"- Reported result: "
            f"{official_metrics.get('pooled_success_percent', official_metrics.get('success_percent', 0)):.1f}%"
        ),
        f"- Accepted checkpoint: {state.get('accepted_artifact', 'missing')}",
        (
            "- Accepted evaluation detail: "
            + (
                ", ".join(f"`{path}`" for path in state.get("accepted_evaluations", []))
                or "-"
            )
        ),
        (
            f"- Accepted lineage training budget: "
            f"{int(state.get('accepted_training_steps', 0)):,} steps"
        ),
        (f"- Last experiment: {displayed_last_experiment}"),
        (f"- Last verdict: {displayed_last_verdict}"),
        f"- Current learning method: {current_method}",
        *evaluation_lines,
        *decision_lines,
        "",
        "## Recent experiment cards",
        "",
        "| # | Family | Exact change | Init / budget | Outcome | Verdict |",
        "|---:|---|---|---|---|---|",
    ]

    for result in results[-5:]:
        family = str(result.get("family", "-")).replace("|", "/")
        details = _compact(_change_details(result), 220).replace("|", "/")
        initialization = result.get("initialization", "-")
        budget = result.get("training_budget_steps")
        setup = initialization
        if budget is not None:
            setup += f" / {int(budget):,} steps"
        outcome = _compact(_experiment_outcome(result), 220).replace("|", "/")
        verdict = _compact(result["verdict"], 100).replace("|", "/")
        lines.append(
            f"| {result['index']} | {family} | {details} | {setup} | "
            f"{outcome} | {verdict} |"
        )
    if not results:
        if pending_evaluation:
            lines.append(
                f"| {pending_evaluation['experiment']} | training.baseline | "
                "Fresh baseline trained | fresh / 120,000 steps | "
                "awaiting researcher-designed evaluation | trained |"
            )
        else:
            lines.append("| - | training.baseline | New baseline pending | - | - | - |")

    replication_groups = _replication_groups(results)
    if replication_groups:
        lines.extend(["", "## Replication Evidence", ""])
        for identity, entries in replication_groups:
            replication_details: list[str] = []
            successes = []
            for replication_result in entries:
                metrics = replication_result.get("candidate_metrics") or {}
                success = metrics.get(
                    "pooled_success_percent", metrics.get("success_percent")
                )
                if success is not None:
                    successes.append(float(success))
                replication_details.append(
                    f"seed {replication_result.get('training_seed', '-')}: "
                    f"{_experiment_outcome(replication_result)}"
                )
            spread = (
                f" success range {min(successes):.2f}-{max(successes):.2f}%"
                if successes
                else ""
            )
            lines.append(
                f"- `{identity}`:{spread}; " + "; ".join(replication_details) + "."
            )

    retained = state.get("retained_lineages", [])
    if retained:
        lines.extend(["## Retained alternative lineages", ""])
        for lineage in retained:
            lines.append(
                f"- `{lineage['id']}`: {lineage['candidate']} from experiment "
                f"{lineage['origin_experiment']}; {lineage['reason']}."
            )
        lines.append("")

    lines.extend(["", "## Prior researcher interpretations", ""])
    memories = _postmortem_memory(postmortems)
    if memories:
        lines.extend(
            [
                (
                    "Written by earlier researcher sessions. They interpret "
                    "measured evidence and may be reconsidered when evidence "
                    "warrants it."
                ),
                "",
            ]
        )
        for memory in memories:
            lines.extend([memory, ""])
    else:
        lines.extend(["No postmortem entries yet.", ""])

    lines.extend(
        [
            "## Context discipline",
            "",
            "- Use the brief by default; inspect relevant logs, artifacts, or code when a hypothesis cannot otherwise be discriminated.",
            (
                "- Referenced evaluation artifacts hold the full record of each "
                "measurement, including researcher-defined evidence when the "
                "scenario evaluation emitted any."
            ),
            (
                "- `research/current_params.json` holds the active method's "
                "configuration. Read it when a diagnosed mechanism makes a specific "
                "setting relevant, not to look for something to change."
            ),
            (
                "- Do not read full experiment or postmortem history unless the compact "
                "evidence is insufficient for one specific decision."
            ),
            "- One experiment should test one identifiable hypothesis; a continuation may test whether more training changes the conclusion.",
            "- Record only 5-8 concise postmortem lines.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_research_brief() -> Path:
    BRIEF_PATH.write_text(render_research_brief(), encoding="utf-8")
    return BRIEF_PATH


def main() -> None:
    brief = write_research_brief()
    print(f"Wrote {brief.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
