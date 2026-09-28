"""Render the strict schema-6 scientific context for a bounded PI session."""

from __future__ import annotations

import json
import re
from pathlib import Path

from research import runner_console as console
from research import runner_repository

ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DIR = ROOT / "research"
BRIEF_PATH = RESEARCH_DIR / "brief.md"


def _compact(value: object, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text or "-"
    return text[: limit - 1].rstrip() + "…"


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
    scenario_path = RESEARCH_DIR / "scenario.md"
    if scenario_path.is_file():
        success = _markdown_section(
            scenario_path.read_text(encoding="utf-8"), "Success criterion"
        )
        if success:
            return success
    return f"Defined by `{state['human_goal']['source']}`."


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


def _best_evidence(state: dict) -> list[str]:
    lines: list[str] = []
    checkpoint = state["pi_checkpoint"]
    if isinstance(checkpoint, dict):
        lines.append(f"- PI synthesis: {checkpoint['current_synthesis']}")
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
    checkpoint = state["pi_checkpoint"]
    if isinstance(checkpoint, dict):
        return checkpoint["current_goal_gap"]
    return "No PI-interpreted goal gap has been checkpointed yet."


def _active_inquiry_lines(state: dict) -> list[str]:
    inquiry = state["active_inquiry"]
    if not isinstance(inquiry, dict):
        return ["- None; the campaign is at goal review."]
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
    return [
        f"- Session: `{checkpoint['session_id']}`",
        f"- Inquiry: `{checkpoint['inquiry_id'] or '-'}`",
        f"- Human-goal connection: {checkpoint['human_goal_connection']}",
        f"- Current synthesis: {checkpoint['current_synthesis']}",
        f"- Decision frontier: {checkpoint['decision_frontier']}",
        "- Completed operations: "
        + (
            ", ".join(f"`{item}`" for item in checkpoint["completed_operations"])
            if checkpoint["completed_operations"]
            else "none"
        ),
        f"- Candidates and roles: {checkpoint['candidates_and_roles']}",
        f"- Next direction or closure: {checkpoint['next_direction_or_closure']}",
        f"- Cumulative resource use: {checkpoint['cumulative_resource_use']}",
        f"- Scientific commit: `{checkpoint['scientific_commit']}`",
    ]


def _session_lines(state: dict) -> list[str]:
    session = state["scientific_session"]
    if not isinstance(session, dict):
        return ["- None; the next PI session will start from durable state."]
    return [
        f"- ID: `{session['id']}`",
        f"- Kind: `{session['kind']}`",
        f"- Objective: {session['objective']}",
        f"- Inquiry: `{session['inquiry_id'] or '-'}`",
        "- Completed operations in this session: "
        + (
            ", ".join(f"`{item}`" for item in session["operation_ids"])
            if session["operation_ids"]
            else "none"
        ),
        f"- Scientific parent commit: `{session['scientific_parent_commit']}`",
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
    lines.append("- Available candidates:")
    candidates = list(state["candidates"].items())
    if len(candidates) > 40:
        lines.append(f"  - {len(candidates) - 40} earlier candidates omitted.")
    for identifier, candidate in candidates[-40:]:
        evidence = candidate["evaluation_artifacts"]
        lines.append(
            f"  - `{identifier}`: {_artifact(candidate['artifact'])}; "
            f"origin `{candidate['origin_operation']}`; "
            f"{candidate['training_steps']:,} training steps; "
            f"{len(evidence)} evaluation artifact(s)."
        )
    return lines


def _event_lines(state: dict) -> list[str]:
    events = state["operation_events"]
    if not events:
        return ["- No completed operations."]
    lines = []
    if len(events) > 40:
        lines.append(
            f"- {len(events) - 40} earlier events remain in `research/results.jsonl`."
        )
    for event in events[-40:]:
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
    return lines


def render_research_brief() -> str:
    state_path = RESEARCH_DIR / "research_state.json"
    if not state_path.is_file():
        raise RuntimeError("research state is missing")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    runner_repository.validate_research_state(state, allow_missing_artifact=True)

    pending = state["pending_operation"]
    terminal = state["terminal_state"]
    campaign = state["campaign"]
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
        "## Active inquiry and goal relevance",
        "",
        *_active_inquiry_lines(state),
        "",
        "## Latest durable PI checkpoint",
        "",
        *_checkpoint_lines(state),
        "",
        "## Current bounded scientific session",
        "",
        *_session_lines(state),
        "",
        "## Available artifacts and evidence",
        "",
        *_candidate_lines(state),
        "",
        "### Completed operation evidence",
        "",
        *_event_lines(state),
        "",
        "## Strategic resource use",
        "",
        (
            f"- Inquiries created: {state['counters']['inquiry']} of "
            f"{campaign['max_inquiries']} unattended maximum."
        ),
        f"- Scientific sessions started: {state['counters']['session']}.",
        (
            f"- Measurement operations completed or allocated: "
            f"{state['counters']['measurement']}."
        ),
        f"- Training operations completed or allocated: {state['counters']['training']}.",
        (
            f"- Other lifecycle operations completed or allocated: "
            f"{state['counters']['event']}."
        ),
        f"- Candidate artifacts available: {len(state['candidates'])}.",
        "",
        "## Current control state",
        "",
        (
            f"- Pending Runner operation: `{pending['id']}` `{pending['kind']}` "
            f"at `{pending['progress']}`"
            + (f"; failure: {pending['failure']}" if pending["failure"] else "")
            + "."
            if isinstance(pending, dict)
            else "- Pending Runner operation: none."
        ),
        (
            f"- Terminal decision: `{terminal['status']}`; {terminal['reason']}"
            if isinstance(terminal, dict)
            else "- Terminal decision: none."
        ),
        f"- Last factual verdict: {state['last_verdict']}",
        "",
        (
            "Training is one evidence-producing operation among measurements, "
            "diagnostics, inquiry decisions, model-role assignments, recipe "
            "restoration, and checkpoints. Detailed facts remain in "
            "`research/results.jsonl` and referenced artifacts."
        ),
    ]
    return "\n".join(lines).rstrip() + "\n"


def write_research_brief() -> Path:
    BRIEF_PATH.write_text(render_research_brief(), encoding="utf-8")
    return BRIEF_PATH


def main() -> None:
    brief = write_research_brief()
    console.announce(f"[brief] wrote {brief.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
