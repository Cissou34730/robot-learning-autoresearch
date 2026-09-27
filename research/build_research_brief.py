"""Build a bounded, inquiry-centered Researcher context."""

from __future__ import annotations

import json
import re
from pathlib import Path

from research import runner_console as console
from research import runner_repository
from research.runner_protocol import scientific_strategy_section

ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DIR = ROOT / "research"
BRIEF_PATH = RESEARCH_DIR / "brief.md"
POSTMORTEMS_REFERENCE = "research/postmortems.md"


def _compact(text: str, limit: int, *, reference: str | None = None) -> str:
    normalized = re.sub(r"\s+", " ", str(text)).strip()
    if len(normalized) <= limit:
        return normalized
    boundary = max(
        normalized.rfind(".", 0, limit),
        normalized.rfind(";", 0, limit),
        normalized.rfind(":", 0, limit),
    )
    if boundary < 0:
        return normalized
    omitted = len(normalized) - boundary - 1
    hint = f"; full text in {reference}" if reference else ""
    return (
        f"{normalized[: boundary + 1]} … [truncated, {omitted} more characters{hint}]"
    )


def _postmortem_memory(
    text: str, campaign_id: str | None = None, count: int = 3
) -> list[str]:
    """Return only experiment notes explicitly scoped to the current campaign."""
    pattern = re.compile(
        r"^## (?P<campaign>[^\r\n/]+) / Experiment \d+\b.*?(?=^## |\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    sections = [
        match.group(0).strip()
        for match in pattern.finditer(text)
        if campaign_id is not None and match.group("campaign").strip() == campaign_id
    ]
    return [
        _compact(section, 700, reference=POSTMORTEMS_REFERENCE)
        for section in sections[-count:]
    ]


def _artifact_reference(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return "none"
    normalized = value.replace("\\", "/")
    return f"`{normalized}`"


def _authoritative_lineage_lines(identifier: str, lineage: dict) -> list[str]:
    lines = [
        (
            f"- `{identifier}`: candidate `{lineage.get('candidate', '-')}` from "
            f"experiment {lineage.get('origin_experiment', '-')}; "
            f"{int(lineage.get('training_steps', 0)):,} training steps; artifact "
            f"{_artifact_reference(lineage.get('artifact'))}."
        ),
        f"  - Reason: {lineage.get('reason', '-')}",
    ]
    evidence = lineage.get("evaluation_artifacts") or []
    lines.append(
        "  - Evidence: "
        + (
            ", ".join(_artifact_reference(path) for path in evidence)
            if evidence
            else "none recorded"
        )
    )
    return lines


def _pending_operation(state: dict) -> str:
    for field, label in (
        ("pending_inquiry_operation", "inquiry operation publication"),
        ("pending_training_operation", "training"),
        ("pending_baseline_decision", "baseline decision publication"),
        ("pending_method_decision", "method decision publication"),
    ):
        if state.get(field) is not None:
            return label
    analysis = state.get("pending_analysis")
    if isinstance(analysis, dict):
        return (
            "baseline analysis"
            if analysis.get("baseline")
            else ("post-training analysis")
        )
    for field, label in (
        ("pending_evaluation_request", "measurement"),
        ("pending_final_benchmark", "official assessment"),
        ("pending_campaign_conclusion", "campaign conclusion"),
    ):
        if state.get(field) is not None:
            return label
    if state.get("terminal_campaign_status") is not None:
        return "terminal"
    return "inquiry choice"


def _pending_method_decision_line(state: dict) -> str:
    operation = state.get("pending_method_decision")
    if not isinstance(operation, dict):
        return "- Pending method decision: none."
    return (
        f"- Pending method decision: `{operation.get('action', '-')}` for method "
        f"`{operation.get('method_id', '-')}`; publication progress "
        f"`{operation.get('progress', '-')}`."
    )


def _short(value: object, length: int = 12) -> str:
    text = str(value or "").strip()
    return f"`{text[:length]}`" if text else "unrecorded"


def _integer(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _context_label(context: dict) -> str:
    parts = []
    if context.get("inquiry") is not None:
        parts.append(f"inquiry {context['inquiry']}")
    if context.get("experiment") is not None:
        relation = "before experiment" if context.get("preparation") else "experiment"
        parts.append(f"{relation} {context['experiment']}")
    if context.get("method"):
        parts.append(f"method `{context['method']}`")
    return ", ".join(parts) if parts else "campaign"


def _measurement_sources(
    state: dict, results: list[dict], inquiries: list[dict]
) -> list[tuple[dict, dict]]:
    """Every current-campaign record that can carry measurements, in order."""
    sources: list[tuple[dict, dict]] = []
    for result in results:
        sources.append(
            (
                {
                    "inquiry": result.get("inquiry_id"),
                    "experiment": result.get("index"),
                    "method": result.get("method_id"),
                },
                result,
            )
        )
    for inquiry in inquiries:
        method = inquiry.get("method")
        sources.append(
            (
                {
                    "inquiry": inquiry.get("inquiry_id"),
                    "method": method.get("id") if isinstance(method, dict) else None,
                    "preparation": True,
                },
                inquiry,
            )
        )
    analysis = state.get("pending_analysis")
    if isinstance(analysis, dict):
        sources.append(
            (
                {
                    "inquiry": analysis.get("inquiry_id"),
                    "experiment": analysis.get("experiment"),
                    "method": analysis.get("method_id"),
                },
                analysis,
            )
        )
    request = state.get("pending_evaluation_request")
    if isinstance(request, dict):
        preparation = bool(request.get("preparation"))
        sources.append(
            (
                {
                    "inquiry": request.get("inquiry_id"),
                    "experiment": None if preparation else request.get("experiment"),
                    "method": request.get("method_id"),
                    "preparation": preparation,
                },
                request,
            )
        )
    ledger = state.get("preparation_measurement")
    if isinstance(ledger, dict):
        sources.append(
            (
                {"inquiry": ledger.get("inquiry_id"), "preparation": True},
                {
                    "preparation_evaluations": ledger.get("partial_evaluations"),
                    "preparation_task_reference_evaluations": ledger.get(
                        "partial_task_reference_evaluations"
                    ),
                    "evaluation_rounds": ledger.get("rounds"),
                },
            )
        )
    return sources


def _measurement_entry(
    instrument: str, key: str, entry: dict, context: dict
) -> dict | None:
    metrics = entry.get("metrics") if isinstance(entry.get("metrics"), dict) else {}
    merged = {**metrics, **entry}
    artifact = merged.get("evaluation_artifact")
    if instrument == "task_reference":
        panel = str(merged.get("panel") or "").strip()
        identity = ("task_reference", panel, merged.get("panel_version"))
    else:
        identity = (
            "research_evaluation",
            str(merged.get("evaluation_semantics") or ""),
            _integer(merged.get("seed")),
            _integer(merged.get("episodes")),
        )
    return {
        "instrument": instrument,
        "candidate": merged.get("candidate"),
        "label": merged.get("label"),
        "model_fingerprint": merged.get("model_fingerprint"),
        "artifact": str(artifact).replace("\\", "/") if artifact else None,
        "identity": identity,
        "context": {
            **context,
            "preparation": bool(context.get("preparation"))
            or key.startswith("preparation_"),
        },
    }


def _campaign_measurements(sources: list[tuple[dict, dict]]) -> list[dict]:
    measurements: list[dict] = []
    seen: set[str] = set()
    for context, record in sources:
        for instrument, keys in runner_repository.MEASUREMENT_LEDGER_KEYS.items():
            for key in keys:
                for entry in record.get(key) or []:
                    if not isinstance(entry, dict):
                        continue
                    item = _measurement_entry(instrument, key, entry, context)
                    identity = item["artifact"] or json.dumps(
                        [
                            instrument,
                            item["candidate"],
                            item["model_fingerprint"],
                            list(item["identity"]),
                        ],
                        default=str,
                    )
                    if identity in seen:
                        continue
                    seen.add(identity)
                    measurements.append(item)
    return measurements


def _panel_label(identity: tuple) -> str:
    if identity[0] == "task_reference":
        version = identity[2]
        return (
            f"`task_reference` panel `{identity[1] or '-'}`"
            f"{f' version {version}' if version is not None else ''}"
        )
    _, semantics, seed, episodes = identity
    if seed is None or episodes is None:
        interval = "episode interval unrecorded"
    else:
        interval = f"seed {seed}, episodes [{seed}, {seed + episodes}) ({episodes})"
    return f"`research_evaluation` {interval}, semantics {_short(semantics)}"


def _paired_comparisons(sources: list[tuple[dict, dict]]) -> list[tuple[dict, dict]]:
    comparisons: list[tuple[dict, dict]] = []
    seen: set[str] = set()
    for context, record in sources:
        entries: list[tuple[object, dict]] = []
        for key in ROUND_KEYS:
            for round_record in record.get(key) or []:
                if not isinstance(round_record, dict):
                    continue
                results = round_record.get("results")
                if not isinstance(results, dict):
                    continue
                entries.extend(
                    (round_record.get("round"), item)
                    for item in results.get("paired_comparisons") or []
                )
        entries.extend((None, item) for item in record.get("paired_comparisons") or [])
        for round_number, item in entries:
            if not isinstance(item, dict):
                continue
            sources_list = [
                str(path).replace("\\", "/")
                for path in item.get("source_artifacts") or []
            ]
            identity = json.dumps(
                [
                    item.get("candidate"),
                    item.get("reference"),
                    item.get("candidate_model_fingerprint"),
                    item.get("reference_model_fingerprint"),
                    sources_list,
                ],
                default=str,
            )
            if identity in seen:
                continue
            seen.add(identity)
            comparisons.append(
                (
                    {**context, "round": round_number},
                    {**item, "source_artifacts": sources_list},
                )
            )
    return comparisons


MEASUREMENT_LINE_LIMIT = 60
ROUND_KEYS = (
    "evaluation_rounds",
    "preparation_evaluation_rounds",
    "measurement_rounds",
)
ROUND_RESULT_INSTRUMENTS = {
    "research_evaluations": "research_evaluation",
    "task_reference_evaluations": "task_reference",
}


def _reused_measurements(sources: list[tuple[dict, dict]]) -> list[tuple[dict, dict]]:
    """Round resolutions that reused an existing measurement identity."""
    reused: list[tuple[dict, dict]] = []
    seen: set[str] = set()
    for context, record in sources:
        for key in ROUND_KEYS:
            for round_record in record.get(key) or []:
                if not isinstance(round_record, dict):
                    continue
                results = round_record.get("results")
                if not isinstance(results, dict):
                    continue
                for result_key, instrument in ROUND_RESULT_INSTRUMENTS.items():
                    for entry in results.get(result_key) or []:
                        if not isinstance(entry, dict) or entry.get("status") != (
                            "reused"
                        ):
                            continue
                        item = _measurement_entry(instrument, key, entry, context)
                        item["round"] = round_record.get("round")
                        item["reused_from_round"] = entry.get("reused_from_round")
                        identity = json.dumps(
                            [
                                context.get("inquiry"),
                                context.get("experiment"),
                                item["round"],
                                instrument,
                                item["candidate"],
                                list(item["identity"]),
                            ],
                            default=str,
                        )
                        if identity in seen:
                            continue
                        seen.add(identity)
                        reused.append((context, item))
    return reused


def _measurement_index_lines(
    state: dict, results: list[dict], inquiries: list[dict]
) -> list[str]:
    sources = _measurement_sources(state, results, inquiries)
    measurements = _campaign_measurements(sources)
    comparisons = _paired_comparisons(sources)
    lines = [
        "",
        "## Measurement / panel index",
        "",
        (
            "Current-campaign measurements by identity and location. Outcomes and "
            "any researcher-defined evidence remain in the referenced artifacts."
        ),
        "",
        "### Measurements",
        "",
    ]
    if not measurements:
        lines.append("- No measurements recorded.")
    omitted = max(0, len(measurements) - MEASUREMENT_LINE_LIMIT)
    if omitted:
        lines.append(
            f"- {omitted} earlier measurements are indexed in "
            "`research/results.jsonl` and `research/research_state.json`."
        )
    for item in measurements[omitted:]:
        label = f" (label `{item['label']}`)" if item.get("label") else ""
        lines.append(
            f"- {_context_label(item['context'])}"
            f"{'; inquiry measurement' if item['context'].get('preparation') else ''}: "
            f"candidate `{item.get('candidate') or '-'}`{label}; "
            f"{_panel_label(item['identity'])}; model "
            f"{_short(item.get('model_fingerprint'))}; artifact "
            f"{_artifact_reference(item.get('artifact'))}."
        )

    lines.extend(["", "### Panels", ""])
    panels: dict[tuple, list[dict]] = {}
    for item in measurements:
        panels.setdefault(item["identity"], []).append(item)
    if not panels:
        lines.append("- No panels recorded.")
    for identity, group in panels.items():
        models = sorted(
            {
                f"`{item.get('candidate') or '-'}` {_short(item.get('model_fingerprint'))}"
                for item in group
            }
        )
        lines.append(
            f"- {_panel_label(identity)}: {len(group)} "
            f"{'measurement' if len(group) == 1 else 'measurements'}; models "
            + ", ".join(models)
            + "."
        )

    lines.extend(["", "### Paired comparisons", ""])
    if not comparisons:
        lines.append("- No paired comparisons recorded.")
    for context, item in comparisons:
        round_note = (
            f", round {context['round']}" if context.get("round") is not None else ""
        )
        sources_text = (
            ", ".join(_artifact_reference(path) for path in item["source_artifacts"])
            if item["source_artifacts"]
            else "not recorded"
        )
        lines.append(
            f"- {_context_label(context)}{round_note}: `{item.get('candidate', '-')}` "
            f"{_short(item.get('candidate_model_fingerprint'))} against "
            f"`{item.get('reference', '-')}` "
            f"{_short(item.get('reference_model_fingerprint'))}; sources "
            f"{sources_text}."
        )

    reused = _reused_measurements(sources)
    lines.extend(["", "### Reused measurements", ""])
    if not reused:
        lines.append("- No reused measurements recorded.")
    for context, item in reused[-MEASUREMENT_LINE_LIMIT:]:
        round_note = f", round {item['round']}" if item.get("round") is not None else ""
        source_round = item.get("reused_from_round")
        lines.append(
            f"- {_context_label(context)}{round_note}: candidate "
            f"`{item.get('candidate') or '-'}`; {_panel_label(item['identity'])}; "
            f"reused from round {source_round if source_round is not None else '-'}; "
            f"model {_short(item.get('model_fingerprint'))}; artifact "
            f"{_artifact_reference(item.get('artifact'))}."
        )
    return lines


def _laboratory_index_lines(state: dict) -> list[str]:
    lines = ["", "## Campaign laboratory index", ""]
    lab = state.get("campaign_lab")
    manifest = lab.get("manifest") if isinstance(lab, dict) else None
    if not isinstance(lab, dict):
        lines.append("- No published laboratory files.")
        return lines
    lines.append(
        f"- Published at commit {_short(lab.get('commit'), 40)}; manifest "
        f"fingerprint {_short(lab.get('fingerprint'))}. Files are available, not "
        "required, inputs:"
    )
    entries = [
        item for item in manifest or [] if isinstance(item, dict) and item.get("path")
    ]
    if not entries:
        lines.append("- No published laboratory files.")
    for item in entries:
        lines.append(
            f"  - {_artifact_reference(item['path'])} "
            f"(fingerprint {_short(item.get('fingerprint'))})"
        )
    return lines


def _render_inquiry_centered_brief(
    state: dict,
    results: list[dict],
    inquiries: list[dict],
    postmortems: str,
    campaign_id: str,
    campaign_base_commit: str | None,
) -> str:
    lines = [
        "# Research brief",
        "",
        "## Campaign",
        "",
        f"- Campaign: `{campaign_id}`",
        f"- Base commit: `{campaign_base_commit or '-'}`",
        f"- Lifecycle operation: {_pending_operation(state)}",
        _pending_method_decision_line(state),
        f"- Last verdict: {state.get('last_verdict', '-')}",
        "",
        "## Active inquiry",
        "",
    ]
    inquiry = state.get("active_inquiry")
    if isinstance(inquiry, dict):
        lines.extend(
            [
                f"- ID: {inquiry.get('id', '-')}",
                f"- Question: {inquiry.get('question', '-')}",
                f"- Scope: {inquiry.get('scope', '-')}",
                f"- Closure condition: {inquiry.get('closure_condition', '-')}",
                f"- PI session: `{inquiry.get('session_id', '-')}`",
                f"- Reframes: {len(inquiry.get('reframes') or [])}",
            ]
        )
    else:
        session = state.get("inquiry_session")
        if isinstance(session, dict):
            lines.append(
                f"- Not yet opened; inquiry {session.get('inquiry_id', '-')} uses PI "
                f"session `{session.get('id', '-')}`."
            )
        else:
            lines.append("- None.")

    lines.extend(["", "## Active method", ""])
    method = state.get("active_method")
    if isinstance(method, dict):
        lines.extend(
            [
                f"- ID: `{method.get('id', '-')}`",
                f"- Inquiry: {method.get('inquiry_id', '-')}",
                f"- Scientific question: {method.get('scientific_question', '-')}",
                f"- Rationale: {method.get('rationale', '-')}",
                f"- Lifecycle: `{method.get('lifecycle', '-')}`",
                (
                    "- Base scientific commit: "
                    f"`{method.get('base_scientific_commit') or '-'}`"
                ),
            ]
        )
        lineage = method.get("current_lineage")
        if isinstance(lineage, dict):
            lines.extend(_authoritative_lineage_lines("active_method", lineage))
        else:
            lines.append("- Current lineage: none.")
        lines.append("- Iterations:")
        iterations = [
            item for item in method.get("iterations") or [] if isinstance(item, dict)
        ]
        for iteration in iterations:
            outcome = iteration.get("outcome")
            lines.append(
                f"  - experiment {iteration.get('experiment', '-')}: "
                f"{iteration.get('status', '-')}"
                + (f"; {_compact(outcome, 300)}" if outcome else "")
            )
        if not iterations:
            lines.append("  - none")
        final = method.get("resolution")
        if method.get("lifecycle") in {"promoted", "retained", "abandoned"} and (
            isinstance(final, dict)
        ):
            lines.append(f"- Final outcome: {final.get('outcome', '-')}")
            if final.get("retained_id"):
                lines.append(f"- Retained ID: `{final['retained_id']}`")
    else:
        lines.append("- None declared.")

    lines.extend(["", "## Saved model roles", ""])
    for role in ("working", "best_known"):
        lineage = state.get(f"{role}_lineage")
        if isinstance(lineage, dict):
            lines.extend(_authoritative_lineage_lines(role, lineage))
        else:
            lines.append(f"- `{role}`: none")
    for lineage in state.get("retained_lineages") or []:
        lines.extend(_authoritative_lineage_lines(str(lineage.get("id")), lineage))

    pending = state.get("pending_analysis") or state.get("pending_evaluation_request")
    lines.extend(["", "## Current operation candidates", ""])
    if isinstance(pending, dict) and pending.get("candidates"):
        if not pending.get("preparation"):
            lines.append(f"- Experiment: {pending.get('experiment', '-')}")
        if pending.get("method_id"):
            lines.append(f"- Method: `{pending['method_id']}`")
        for candidate in pending.get("candidates") or []:
            lines.append(
                f"- Candidate `{candidate.get('name', '-')}`: "
                f"{_artifact_reference(candidate.get('artifact'))}"
            )
    else:
        lines.append("- No experiment candidates are awaiting a decision.")

    lines.extend(_measurement_index_lines(state, results, inquiries))
    lines.extend(_laboratory_index_lines(state))

    strategy = scientific_strategy_section(postmortems, campaign_id)
    lines.extend(
        [
            "",
            "## Scientific strategy",
            "",
            "\n".join(strategy.splitlines()[1:]).strip()
            if strategy
            else "No current-campaign scientific strategy has been recorded.",
            "",
            "## Activity index",
            "",
        ]
    )
    if not results and not inquiries:
        lines.append("- No completed activity.")
    for result in results:
        decision = result.get("method_decision")
        action = decision.get("action") if isinstance(decision, dict) else None
        lines.append(
            f"- Experiment {result.get('index', '-')}: "
            f"{result.get('kind', 'training')} / {result.get('status', '-')}; "
            f"method `{result.get('method_id', 'baseline')}`"
            + (f"; method_decision `{action}`" if action else "")
            + "."
        )
    for inquiry_record in inquiries:
        method_record = inquiry_record.get("method")
        method_note = (
            f"; method `{method_record.get('id', '-')}` "
            f"`{method_record.get('lifecycle', '-')}`"
            if isinstance(method_record, dict)
            else ""
        )
        lines.append(
            f"- Inquiry {inquiry_record.get('inquiry_id', '-')}: closed"
            f"{method_note}; {inquiry_record.get('outcome', '-')}"
        )
    lines.extend(
        [
            "",
            (
                "Detailed measurements, training logs, and immutable experiment "
                "records remain in their referenced artifacts. This brief does not "
                "infer scenario-specific diagnoses."
            ),
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_research_brief() -> str:
    state_path = RESEARCH_DIR / "research_state.json"
    results_path = RESEARCH_DIR / "results.jsonl"
    postmortems_path = RESEARCH_DIR / "postmortems.md"
    if not state_path.exists():
        raise RuntimeError("research state is missing")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    runner_repository.validate_research_state(state, allow_missing_artifact=True)
    campaign_id = runner_repository.current_campaign_id(state)
    if not campaign_id:
        raise RuntimeError("research state has no campaign identity")
    records = (
        [
            json.loads(line)
            for line in results_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if results_path.exists()
        else []
    )
    campaign_records = [
        record for record in records if record.get("campaign_id") == campaign_id
    ]
    results = [
        record
        for record in campaign_records
        if record.get("record_type", "experiment") == "experiment"
    ]
    inquiries = [
        record for record in campaign_records if record.get("record_type") == "inquiry"
    ]
    postmortems = (
        postmortems_path.read_text(encoding="utf-8")
        if postmortems_path.exists()
        else ""
    )
    return _render_inquiry_centered_brief(
        state,
        results,
        inquiries,
        postmortems,
        campaign_id,
        runner_repository.current_campaign_base_commit(state),
    )


def write_research_brief() -> Path:
    BRIEF_PATH.write_text(render_research_brief(), encoding="utf-8")
    return BRIEF_PATH


def main() -> None:
    brief = write_research_brief()
    console.announce(f"[brief] wrote {brief.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
