"""Render the strict schema-6 scientific context for a bounded PI session."""

from __future__ import annotations

import json
import re
from pathlib import Path

from research import runner_repository

ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DIR = ROOT / "research"
BRIEF_PATH = RESEARCH_DIR / "brief.md"


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
                f"artifact {_artifact(artifact)}; metrics "
                + _measurement_facts(
                    metrics,
                    omitted={
                        "episode_results",
                        "evaluation_artifact",
                        "evaluation_artifact_fingerprint",
                        "model_fingerprint",
                    },
                )
                + "."
            )
        comparisons = result.get("paired_comparisons") or []
        if comparisons:
            lines.append(
                "  - Paired comparisons: "
                + _compact(json.dumps(comparisons, sort_keys=True))
            )
        return lines
    if event["kind"] == "training":
        dynamics = result.get("learning_dynamics") or []
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
        return [
            "  - Training candidates: "
            + ", ".join(f"`{item}`" for item in result.get("candidates") or [])
            + ".",
            "  - Learning dynamics: "
            + _compact(json.dumps(dynamics, sort_keys=True))
            + ".",
            "  - Mechanical provenance: parent `"
            + str((provenance or {}).get("code_parent_commit") or "-")
            + "`; changed "
            + (", ".join(f"`{item}`" for item in changed) or "none")
            + ".",
        ]
    return []


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
    ]


def _session_lines(state: dict) -> list[str]:
    session = state["scientific_session"]
    if not isinstance(session, dict):
        return ["- None; the next scientific work begins from durable state."]
    return [
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
    dynamics = {
        item["candidate"]: item
        for event in state["operation_events"]
        if event.get("status") == "completed" and event.get("kind") == "training"
        for item in (event.get("result") or {}).get("learning_dynamics", [])
        if isinstance(item, dict) and isinstance(item.get("candidate"), str)
    }
    lines.append("- Available candidates:")
    for identifier, candidate in state["candidates"].items():
        evidence = candidate["evaluation_artifacts"]
        training = dynamics.get(identifier, {})
        success = training.get("training_success")
        reward = training.get("ep_rew_mean")
        lines.append(
            f"  - `{identifier}`: {_artifact(candidate['artifact'])}; "
            f"origin `{candidate['origin_operation']}`; "
            f"{candidate['training_steps']:,} training steps; "
            f"training success {success if success is not None else 'not recorded'}; "
            f"reward {reward if reward is not None else 'not recorded'}; "
            "evaluation artifacts "
            + (
                ", ".join(_artifact(path) for path in evidence)
                if evidence
                else "none"
            )
            + "."
        )
    return lines


def _completed_events(state: dict) -> list[dict]:
    return [
        event
        for event in state["operation_events"]
        if event.get("status") == "completed"
    ]


def _event_lines(state: dict) -> list[str]:
    events = _completed_events(state)
    if not events:
        return ["- No completed operations."]
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
        lines.append(
            f"- `{event['id']}` `{event['kind']}` failed: "
            f"{_compact(event.get('error'))}{retry}."
        )
    pending = state["pending_operation"]
    if isinstance(pending, dict) and pending.get("failure"):
        lines.append(
            f"- Pending `{pending['id']}` `{pending['kind']}` failed and awaits "
            f"repair: {_compact(pending['failure'])}."
        )
    return lines or ["- No failed attempts."]


def render_research_brief() -> str:
    state_path = RESEARCH_DIR / "research_state.json"
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
        "### Completed operation evidence",
        "",
        *_event_lines(state),
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
