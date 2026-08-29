"""Build bounded research context for token-efficient autonomous sessions."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TypedDict

from robot_learning.scenario import render_scenario_evidence

ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DIR = ROOT / "research"
TRAIN_LOG_PATH = RESEARCH_DIR / "last_train.log"
TRAIN_SUMMARY_PATH = RESEARCH_DIR / "last_train_summary.md"
BRIEF_PATH = RESEARCH_DIR / "brief.md"


class FamilySummary(TypedDict):
    experiments: list[str]
    changes: list[str]
    lesson: str


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
        "| Metric | First | Final |",
        "|---|---:|---:|",
    ]
    for label, key in fields:
        lines.append(
            f"| {label} | {_format_value(first, key)} | {_format_value(final, key)} |"
        )

    lines.extend(
        [
            "",
            (
                "- `Success` is Stable-Baselines3's rolling 100-episode rate "
                "for the stochastic training policy; it is not the deterministic "
                "held-out benchmark."
            ),
            (
                "- Snapshot maxima are intentionally omitted because selecting the "
                "maximum of a noisy rolling series creates a false peak."
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


def _postmortem_memory(text: str, count: int = 3) -> list[str]:
    sections = re.split(r"(?=^## Experiment \d+\b)", text, flags=re.MULTILINE)
    sections = [
        section.strip() for section in sections if section.startswith("## Experiment")
    ]
    memories: list[str] = []
    labels = [
        "Result",
        "Observed behavior",
        "What was learned / do NOT retry",
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


def _postmortem_lessons(text: str) -> dict[int, str]:
    lessons: dict[int, str] = {}
    sections = re.split(r"(?=^## Experiment \d+\b)", text, flags=re.MULTILINE)
    for section in sections:
        title = re.match(r"^## Experiment (\d+)\b", section)
        learned = re.search(
            r"\*\*What was learned / do NOT retry:\*\*\s*(.+?)"
            r"(?=\n\s*\n|\n\*\*|\Z)",
            section,
            flags=re.DOTALL,
        )
        if title and learned:
            lessons[int(title.group(1))] = _compact(learned.group(1), 240)
    return lessons


def _legacy_family(result: dict) -> str:
    if result.get("family") and result["family"] not in {
        "training",
        "method",
        "calibration",
    }:
        return str(result["family"])
    if result.get("kind") == "calibration":
        return "research.training_seed_calibration"
    change = str(result.get("change", "")).lower()
    families = [
        (("rollout length",), "ppo.n_steps"),
        (("learning rate",), "ppo.learning_rate"),
        (("entropy",), "ppo.ent_coef"),
        (("gae",), "ppo.gae_lambda"),
        (("minibatch", "batch size"), "ppo.batch_size"),
        (("optimization epochs", "update epochs"), "ppo.n_epochs"),
        (("gradient clipping",), "ppo.max_grad_norm"),
        (("value-function loss", "value function loss"), "ppo.vf_coef"),
        (("clipping range",), "ppo.clip_range"),
        (("discount factor",), "ppo.gamma"),
        (("target kl",), "ppo.target_kl"),
        (("policy network", "network"), "policy.net_arch"),
        (("relu", "activation"), "policy.activation"),
        (("action standard deviation",), "policy.log_std_init"),
        (("parallel",), "training.n_envs"),
        (("sac",), "algorithm.name"),
        (("dwell reward",), "reward.DWELL_BONUS_PER_STEP"),
        (("completion bonus",), "reward.HOLD_COMPLETE_BONUS"),
        (
            ("closeness reward potential", "sharpen closeness"),
            "reward.CLOSENESS_LENGTH_SCALE",
        ),
        (("closeness reward",), "reward.CLOSENESS_COEFFICIENT"),
        (("progress reward",), "reward.PROGRESS_COEFFICIENT"),
        (("action cost",), "reward.ACTION_COST_COEFFICIENT"),
        (("selection evaluation episodes",), "training.selection_eval_episodes"),
        (("checkpoint selection frequency",), "training.selection_eval_every_steps"),
        (("baseline",), "training.baseline"),
    ]
    for terms, family in families:
        if any(term in change for term in terms):
            return family
    return _compact(str(result.get("change", result.get("kind", "unknown"))), 80)


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
    accepted_failures: int | str = "-"
    if accepted_metrics is not None and accepted_score is not None:
        accepted_failures = round(
            int(accepted_metrics.get("episodes", 0))
            * (100 - float(accepted_score))
            / 100
        )
    official_metrics = state.get("official_metrics")
    accepted_seed_count = (
        accepted_metrics.get("seed_count") if accepted_metrics else None
    )
    accepted_seed_passes = (
        accepted_metrics.get("seeds_passing_98_percent") if accepted_metrics else None
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
                f"artifact `{candidate['artifact']}`."
            )
        if pending_evaluation.get("champion_available"):
            evaluation_lines.append("- `champion` — current accepted model lineage.")
        evaluation_lines.extend(
            [
                "",
                (
                    "Decide which candidates need measurement, with which episode "
                    "counts, seeds, labels, and diagnostics. Write "
                    "`research/evaluation_request.json` and exit. There is no "
                    "automatic tournament."
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
        champion_summary = pending_decision.get("champion_summary")
        if champion_summary is not None:
            decision_lines.append(
                f"- champion: pooled success "
                f"{champion_summary['pooled_success_percent']:.2f}%; "
                f"{champion_summary['episodes']} episodes over "
                f"{champion_summary['seed_count']} seed(s)."
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
            f"- Accepted seeds passing 98%: "
            f"{accepted_seed_passes if accepted_seed_passes is not None else '-'}"
            f"/{accepted_seed_count if accepted_seed_count is not None else '-'}"
            + (
                " (legacy single-seed measurement)"
                if accepted_metrics and "seed_count" not in accepted_metrics
                else ""
            )
        ),
        f"- Accepted failed episodes: {accepted_failures}",
        (
            "- Reported result: pending"
            if official_metrics is None
            else f"- Reported result: "
            f"{official_metrics.get('pooled_success_percent', official_metrics.get('success_percent', 0)):.1f}%"
        ),
        f"- Accepted checkpoint: {state.get('accepted_artifact', 'missing')}",
        (
            f"- Accepted lineage training budget: "
            f"{int(state.get('accepted_training_steps', 0)):,} steps"
        ),
        (f"- Last experiment: {displayed_last_experiment}"),
        (f"- Last verdict: {displayed_last_verdict}"),
        *evaluation_lines,
        *decision_lines,
        "",
        "## Current parameters",
        "",
        "```json",
        json.dumps(params, indent=2),
        "```",
        "",
        "## Recent experiment cards",
        "",
        "| # | Family | Exact change | Init / budget | Outcome | Verdict |",
        "|---:|---|---|---|---|---|",
    ]

    for result in results[-5:]:
        family = _legacy_family(result).replace("|", "/")
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

    lessons = _postmortem_lessons(postmortems)
    families: dict[str, FamilySummary] = {}
    for result in results:
        family = _legacy_family(result)
        family_summary: FamilySummary | None = families.get(family)
        if family_summary is None:
            family_summary = {"experiments": [], "changes": [], "lesson": "-"}
            families[family] = family_summary
        experiment_label = f"#{result['index']} {result['verdict']}"
        family_summary["experiments"].append(experiment_label)
        details = _change_details(result)
        if details not in family_summary["changes"]:
            family_summary["changes"].append(details)
        result_index = _result_index(result)
        if result_index in lessons:
            family_summary["lesson"] = lessons[result_index]

    lines.extend(
        [
            "",
            "## Tested hypothesis families",
            "",
            (
                "A different numeric value is not a new hypothesis family. Revisit a "
                "family only when new evidence identifies a materially different mechanism."
            ),
            "",
            "| Family | Experiments and verdicts | Changes tested | Latest conclusion |",
            "|---|---|---|---|",
        ]
    )
    if families:
        for family, family_summary in families.items():
            experiments = _compact("; ".join(family_summary["experiments"]), 280)
            changes = _compact("; ".join(family_summary["changes"]), 320)
            lesson = _compact(str(family_summary["lesson"]), 240)
            lines.append(
                f"| {family.replace('|', '/')} | {experiments.replace('|', '/')} | "
                f"{changes.replace('|', '/')} | {lesson.replace('|', '/')} |"
            )
    else:
        lines.append("| None yet | - | - | - |")

    lines.extend(["", "## Observed failure diagnostics", ""])
    lines.extend(render_scenario_evidence(accepted_metrics))

    measured_challengers = (
        (pending_decision or {}).get("candidates", []) if pending_decision else []
    )
    if measured_challengers:
        lines.extend(["", "## Measured challenger diagnostics", ""])
        for candidate in measured_challengers:
            summary = candidate.get("summary")
            if summary is None:
                continue
            lines.append(f"**{candidate['name']}**")
            lines.extend(render_scenario_evidence(summary))
            lines.append("")
        measured_champion = (pending_decision or {}).get("champion_summary")
        if measured_champion is not None:
            lines.append("**champion**")
            lines.extend(render_scenario_evidence(measured_champion))
            lines.append("")

    retained = state.get("retained_lineages", [])
    if retained:
        lines.extend(["## Retained alternative lineages", ""])
        for lineage in retained:
            lines.append(
                f"- `{lineage['id']}`: {lineage['candidate']} from experiment "
                f"{lineage['origin_experiment']}; {lineage['reason']}."
            )
        lines.append("")

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
            "- Use the brief by default; inspect relevant logs, artifacts, or code when a hypothesis cannot otherwise be discriminated.",
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
    write_training_summary()
    BRIEF_PATH.write_text(render_research_brief(), encoding="utf-8")
    return BRIEF_PATH


def main() -> None:
    brief = write_research_brief()
    print(f"Wrote {brief.relative_to(ROOT)}")
    print(f"Wrote {TRAIN_SUMMARY_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
