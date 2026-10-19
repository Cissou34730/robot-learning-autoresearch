"""Render the strict schema-6 scientific context for a bounded PI session."""

from __future__ import annotations

import json
import re
from pathlib import Path

from runner import paths
from runner import protocol as runner_protocol
from runner import repository as runner_repository

RESEARCH_DIR = paths.CAMPAIGNS_DIR
BRIEF_PATH = paths.CAMPAIGNS_DIR / "brief.md"


def _compact(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or "-"


def _markdown_section(text: str, heading: str) -> str:
    match = re.search(
        rf"(?ms)^## {re.escape(heading)}\s+(.*?)(?=^## |\Z)",
        text,
    )
    return _compact(match.group(1)) if match else ""


def _human_goal(state: dict) -> str:
    summary = state["human_goal"].get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    scenario_path = paths.HARNESS_ROOT / "contracts" / "scenario.md"
    if scenario_path.is_file():
        success = _markdown_section(
            scenario_path.read_text(encoding="utf-8"), "Success criterion"
        )
        if success:
            return success
    return f"Defined by `{state['human_goal']['source']}`."


def _scientific_model_lines(state: dict) -> list[str]:
    model_path = state["scientific_model"]["path"]
    model_file = paths.locate(model_path)
    lines = [
        f"- Source: [`{model_path}`](../{model_path}).",
        "- Lifecycle contract: [`contracts/program.md`](../contracts/program.md).",
        f"- Publication status: `{state['scientific_model']['status']}`.",
    ]
    commit = state["scientific_model"].get("commit")
    if commit:
        lines.append(f"- Published commit: `{commit}`.")
    if not model_file.is_file():
        lines.append("- Model content is not available in the current worktree.")
        return lines
    text = model_file.read_text(encoding="utf-8")
    selected = _markdown_section(text, "Decision-relevant synthesis")
    if selected:
        lines.append(f"- **Decision-relevant synthesis:** {selected}")
    else:
        lines.append(
            "- This historical model predates the required decision-relevant synthesis."
        )
    return lines


def _artifact(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return "none"
    return f"`{value.replace(chr(92), '/')}`"


def _event_summary(event: dict) -> str:
    result = event.get("result")
    if not isinstance(result, dict):
        return event.get("status", "-")
    return _compact(
        result.get("summary")
        or result.get("outcome")
        or result.get("status")
        or event.get("status")
    )


def _event_artifacts(event: dict) -> list[str]:
    result = event.get("result")
    if not isinstance(result, dict):
        return []
    artifacts: list[str] = []
    for measurement in result.get("measurements") or []:
        if not isinstance(measurement, dict):
            continue
        metrics = measurement.get("metrics")
        if isinstance(metrics, dict) and metrics.get("evaluation_artifact"):
            artifacts.append(str(metrics["evaluation_artifact"]))
    provenance = result.get("tool_provenance")
    publication = (
        provenance.get("campaign_lab_publication")
        if isinstance(provenance, dict)
        else None
    )
    if isinstance(publication, dict):
        for entry in publication.get("manifest") or []:
            if isinstance(entry, dict) and entry.get("path"):
                artifacts.append(str(entry["path"]))
    return list(dict.fromkeys(artifacts))


def _measurement_facts(record: object, *, omitted: set[str] | None = None) -> str:
    if not isinstance(record, dict):
        return "none"
    excluded = omitted or set()
    facts = []
    for key, value in record.items():
        if key in excluded:
            continue
        rendered = (
            json.dumps(value, sort_keys=True)
            if isinstance(value, (dict, list))
            else _compact(value)
        )
        facts.append(f"{key}={rendered}")
    return ", ".join(facts) or "none"


def _event_detail_lines(event: dict) -> list[str]:
    result = event.get("result")
    if not isinstance(result, dict):
        return []
    if event["kind"] == "measurement":
        lines: list[str] = []
        for measurement in result.get("measurements") or []:
            if not isinstance(measurement, dict):
                continue
            metrics = measurement.get("metrics")
            artifact = (
                metrics.get("evaluation_artifact")
                if isinstance(metrics, dict)
                else None
            )
            lines.append(
                f"  - {measurement.get('label') or measurement.get('instrument')}: "
                f"artifact {_artifact(artifact)}; "
                "result summary (not the complete artifact): "
                + _measurement_facts(
                    metrics,
                    omitted={
                        "episode_results",
                        "evaluation_artifact",
                        "evaluation_artifact_fingerprint",
                        "evaluation_artifact_contents",
                        "model_fingerprint",
                    },
                )
                + "."
            )
        comparisons = result.get("paired_comparisons") or []
        if comparisons:
            summaries = [
                {
                    key: value
                    for key, value in comparison.items()
                    if key != "shared_episode_seeds"
                }
                for comparison in comparisons
            ]
            lines.append(
                "  - Paired comparisons: "
                + _compact(json.dumps(summaries, sort_keys=True))
            )
            lines.append(
                "    Complete seed panels: `campaigns/results.jsonl`, "
                f"operation `{event['id']}`."
            )
        return lines
    if event["kind"] == "training":
        provenance = result.get("mechanical_provenance")
        changed = (
            [
                entry.get("path")
                for entry in provenance.get("changed_files") or []
                if isinstance(entry, dict) and entry.get("path")
            ]
            if isinstance(provenance, dict)
            else []
        )
        lines = [
            (
                f"  - Training: initialization `{result['initialization']}`; "
                f"parent `{result['parent'] or 'none'}`; seed {result['seed']}; "
                f"requested steps {result['requested_steps']}; "
                f"completed steps {result['completed_steps']}."
            ),
            "  - Mechanical provenance: parent `"
            + str((provenance or {}).get("code_parent_commit") or "-")
            + "`; changed "
            + (", ".join(f"`{item}`" for item in changed) or "none")
            + ".",
        ]
        saved = result.get("saved_component_comparisons")
        if isinstance(saved, dict):
            exact = []
            for comparison in saved.get("comparisons") or []:
                matches = comparison.get("exact_component_matches") or []
                if not matches:
                    continue
                runtime = comparison.get("runtime") or {}
                exact.append(
                    f"`{comparison['operation']}`: {len(matches)}/"
                    f"{comparison['corresponding_checkpoint_count']} corresponding "
                    "checkpoints; runtime files "
                    f"{runtime.get('equal', 0)}/{runtime.get('compared', 0)}"
                )
            lines.append(
                "  - Exact saved-component comparison: "
                + ("; ".join(exact) if exact else "no exact checkpoint matches")
                + "."
            )
        return lines
    return []


def _best_evidence(state: dict) -> list[str]:
    lines: list[str] = []
    checkpoint = state["pi_checkpoint"]
    if isinstance(checkpoint, dict):
        lines.append("- PI interpretation: see the latest durable checkpoint below.")
        if checkpoint["evidence_references"]:
            lines.append(
                "- Supporting references: "
                + ", ".join(f"`{item}`" for item in checkpoint["evidence_references"])
            )
    best_id = state["model_roles"]["best_known"]
    if best_id is not None:
        candidate = state["candidates"][best_id]
        lines.extend(
            [
                (
                    f"- Best-known model: `{best_id}` from "
                    f"`{candidate['origin_operation']}`; "
                    f"{candidate['training_steps']:,} accumulated training steps."
                ),
                (
                    f"- Artifact: {_artifact(candidate['artifact'])}; fingerprint "
                    f"`{candidate['fingerprint'][:12]}`."
                ),
                "- Development evidence: "
                + (
                    ", ".join(
                        _artifact(path) for path in candidate["evaluation_artifacts"]
                    )
                    if candidate["evaluation_artifacts"]
                    else "none recorded"
                ),
            ]
        )
    assessment = state["official_assessment"]
    if isinstance(assessment, dict):
        lines.append(
            f"- Official assessment: `{assessment['status']}` for "
            f"`{assessment['model']}`; {assessment['summary']}"
        )
    if not lines:
        lines.append(
            "- No PI checkpoint, best-known model, or official assessment yet."
        )
    return lines


def _goal_gap(state: dict) -> str:
    assessment = state["official_assessment"]
    if isinstance(assessment, dict):
        return assessment["summary"]
    checkpoint = state["pi_checkpoint"]
    if isinstance(checkpoint, dict):
        return checkpoint["current_goal_gap"]
    return "No PI-interpreted goal gap has been checkpointed yet."


def _active_inquiry_lines(state: dict) -> list[str]:
    inquiry = state["active_inquiry"]
    if not isinstance(inquiry, dict):
        session = state["scientific_session"]
        if not isinstance(session, dict):
            return ["- None; no bounded scientific session is active."]
        if session["kind"] == "startup":
            return [
                (
                    "- None; the current scientific session is `startup`. "
                    "Goal review begins after the startup checkpoint."
                )
            ]
        if session["kind"] == "goal_review":
            return ["- None; the current scientific session is `goal_review`."]
        return [
            (
                "- None; the inquiry has closed and the current `inquiry` session "
                "must checkpoint before the next session."
            )
        ]
    return [
        f"- ID: `{inquiry['id']}`",
        f"- Question: {inquiry['question']}",
        f"- Goal connection: {inquiry['goal_connection']}",
        f"- Closure condition: {inquiry['closure_condition']}",
        f"- Rationale: {inquiry['rationale']}",
        f"- Reframes: {len(inquiry['reframes'])}",
    ]


def _checkpoint_lines(state: dict) -> list[str]:
    checkpoint = state["pi_checkpoint"]
    if not isinstance(checkpoint, dict):
        return ["- No durable PI checkpoint has been recorded."]
    question_label = (
        "Active inquiry question"
        if isinstance(state["active_inquiry"], dict)
        else "Proposed next inquiry question"
    )
    historical_context = []
    if isinstance(state["official_assessment"], dict):
        historical_context = [
            (
                "- This checkpoint predates the official assessment. Its "
                "statements describe the evidence available at that time."
            ),
            f"- Goal gap at checkpoint: {checkpoint['current_goal_gap']}",
        ]
    return [
        *historical_context,
        f"- Inquiry: `{checkpoint['inquiry_id'] or '-'}`",
        f"- Human-goal connection: {checkpoint['human_goal_connection']}",
        f"- Current synthesis: {checkpoint['current_synthesis']}",
        f"- Decision frontier: {checkpoint['decision_frontier']}",
        f"- {question_label}: {checkpoint['next_question']}",
        "- Completed operations: "
        + (
            ", ".join(f"`{item}`" for item in checkpoint["completed_operations"])
            if checkpoint["completed_operations"]
            else "none"
        ),
        f"- Candidates and roles: {checkpoint['candidates_and_roles']}",
        f"- Next direction or closure: {checkpoint['next_direction_or_closure']}",
        f"- Cumulative resource use: {checkpoint['cumulative_resource_use']}",
    ]


def _session_lines(state: dict) -> list[str]:
    session = state["scientific_session"]
    if not isinstance(session, dict):
        return ["- None; the next scientific work begins from durable state."]
    availability = runner_protocol.session_operation_availability(state)
    allowed = availability["allowed_operations"]
    evaluation_root = (
        f"campaigns/evaluations/{runner_repository.current_campaign_id(state)}/"
    )
    return [
        f"- Session kind: `{session['kind']}`",
        "- Currently permitted operation kinds (request, evidence and resource "
        "checks still apply): "
        + (", ".join(f"`{operation}`" for operation in allowed) or "none"),
        "- Required transition: " + (availability["checkpoint_reason"] or "none"),
        f"- Campaign evaluation artifact root: `{evaluation_root}`",
        f"- Objective: {session['objective']}",
        f"- Inquiry: `{session['inquiry_id'] or '-'}`",
        "- Completed operations in the current work: "
        + (
            ", ".join(f"`{item}`" for item in session["operation_ids"])
            if session["operation_ids"]
            else "none"
        ),
    ]


def _candidate_lines(state: dict) -> list[str]:
    roles = state["model_roles"]
    lines = [
        f"- Working: `{roles['working'] or '-'}`",
        f"- Best-known: `{roles['best_known'] or '-'}`",
    ]
    retained = roles["retained"]
    if retained:
        lines.append(
            "- Retained: "
            + ", ".join(
                f"`{label}` → `{candidate}`" for label, candidate in retained.items()
            )
        )
    else:
        lines.append("- Retained: none")
    if not state["candidates"]:
        lines.append("- Available candidates: none")
        return lines
    campaign_id = runner_repository.current_campaign_id(state)
    lines.extend(
        [
            (
                f"- Available checkpoints: {len(state['candidates'])}. "
                "The training index below does not nominate a checkpoint."
            ),
            f"- Candidate archive root: `campaigns/checkpoints/candidates/{campaign_id}/`.",
            f"- Retained archive root: `campaigns/checkpoints/retained/{campaign_id}/`.",
            (
                "- Operation index: `artifact_evidence_query` action=operations. "
                "Checkpoint metadata and learning statistics: action=metadata, "
                "selected by training operation, paths /checkpoints and /record. "
                "Archived `artifact.json` files remain available. "
                "Training statistics are not development measurements."
            ),
            "- Preserved training trajectories: `training_log_query`, selected by training operation.",
            (
                "- Saved-component comparisons report saved-state equality, "
                "not full artifact equivalence. "
                "Compare source and runtime changes before claiming a different method."
            ),
        ]
    )
    for event in _completed_events(state):
        if event["kind"] != "training":
            continue
        candidates = [
            (identifier, candidate)
            for identifier, candidate in state["candidates"].items()
            if candidate["origin_operation"] == event["id"]
        ]
        measured = [
            f"`{identifier}`"
            for identifier, candidate in candidates
            if candidate["evaluation_artifacts"]
        ]
        lines.append(
            f"- `{event['id']}`: {len(candidates)} archived checkpoints. "
            "Development-measured checkpoints: "
            + (", ".join(measured) if measured else "none")
            + "."
        )
        lines.extend(_event_detail_lines(event))
    return lines


def _completed_events(state: dict) -> list[dict]:
    return [
        event
        for event in state["operation_events"]
        if event.get("status") == "completed"
    ]


def _event_lines(state: dict) -> list[str]:
    references: set[str] = set()
    checkpoint = state["pi_checkpoint"]
    if isinstance(checkpoint, dict):
        references.update(checkpoint["completed_operations"])
        references.update(checkpoint["evidence_references"])
    session = state["scientific_session"]
    if isinstance(session, dict):
        references.update(session["operation_ids"])
    events = [
        event
        for event in _completed_events(state)
        if event["id"] in references and event["kind"] != "training"
    ]
    if not events:
        return [
            "- No non-training operations referenced by current work or the latest checkpoint."
        ]
    lines = []
    for event in events:
        inquiry = f" in `{event['inquiry_id']}`" if event["inquiry_id"] else ""
        artifacts = _event_artifacts(event)
        artifact_note = (
            "; artifacts " + ", ".join(_artifact(path) for path in artifacts)
            if artifacts
            else ""
        )
        lines.append(
            f"- `{event['id']}` `{event['kind']}`{inquiry}: "
            f"{_event_summary(event)}{artifact_note}"
        )
        lines.extend(_event_detail_lines(event))
    return lines


def _execution_history_lines(state: dict) -> list[str]:
    failed = [
        event for event in state["operation_events"] if event.get("status") == "failed"
    ]
    lines: list[str] = []
    for event in failed:
        retry = (
            f"; superseded by `{event['superseded_by']}`"
            if event.get("superseded_by")
            else "; not yet superseded"
        )
        lines.append(f"- `{event['id']}` `{event['kind']}` failed{retry}.")
        if not event.get("superseded_by"):
            lines.append(f"  - Unresolved error: {_compact(event.get('error'))}.")
    pending = state["pending_operation"]
    if isinstance(pending, dict) and pending.get("failure"):
        lines.append(
            f"- Pending `{pending['id']}` `{pending['kind']}` failed and awaits "
            f"repair: {_compact(pending['failure'])}."
        )
    return lines or ["- No failed attempts."]


def render_research_brief() -> str:
    state_path = (
        RESEARCH_DIR / "research_state.json"
        if RESEARCH_DIR != paths.CAMPAIGNS_DIR
        else paths.STATE_PATH
    )
    if not state_path.is_file():
        raise RuntimeError("research state is missing")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    runner_repository.validate_research_state(state, allow_missing_artifact=True)
    lines = [
        "# Research brief",
        "",
        "## Human goal",
        "",
        _human_goal(state),
        "",
        "Source: `" + state["human_goal"]["source"] + "`.",
        "",
        "## Best evidence relative to the goal",
        "",
        *_best_evidence(state),
        "",
        "## Current goal gap",
        "",
        _goal_gap(state),
        "",
        "## Initial scientific model",
        "",
        *_scientific_model_lines(state),
        "",
        "## Active inquiry and goal relevance",
        "",
        *_active_inquiry_lines(state),
        "",
        "## Latest durable PI checkpoint",
        "",
        *_checkpoint_lines(state),
        "",
        "## Current scientific work",
        "",
        *_session_lines(state),
        "",
        "## Available artifacts and evidence",
        "",
        *_candidate_lines(state),
        "",
        "### Evidence referenced by current work",
        "",
        *_event_lines(state),
        "",
        "### Full evidence sources",
        "",
        (
            "- Full operation records, including all checkpoint metadata, paired "
            "comparisons and execution errors: `campaigns/results.jsonl`."
        ),
        "- Chronological operation index: `campaigns/EXPERIMENTS.md`.",
        (
            "- JSON artifact structure and values: `artifact_evidence_query`, "
            "selected by operation and artifact index."
        ),
        "- These sources remain complete. Their omission here is not absence of evidence.",
        "",
        "### Execution history (not evidence)",
        "",
        *_execution_history_lines(state),
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def write_research_brief() -> Path:
    BRIEF_PATH.write_text(render_research_brief(), encoding="utf-8")
    return BRIEF_PATH


def main() -> None:
    write_research_brief()


if __name__ == "__main__":
    main()
