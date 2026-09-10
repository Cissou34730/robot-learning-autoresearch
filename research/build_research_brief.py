"""Build bounded research context for token-efficient autonomous sessions."""

from __future__ import annotations

import json
import re
from pathlib import Path, PureWindowsPath

from research.runner_protocol import operation_description, scientific_strategy_section
from research.runner_repository import ARTIFACT_FILES, compact_measurement_summary

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


def _postmortem_memory(
    text: str, campaign_id: str | None = None, count: int = 3
) -> list[str]:
    """Extract postmortem sections for the given campaign.

    Handles both new "## Campaign ID / Experiment N" format and legacy "## Experiment N" format.
    When campaign_id is provided, only sections for that campaign are extracted.
    """
    section_pattern = re.compile(
        r"^## (?:(?P<campaign>[^\r\n/]+) / )?Experiment \d+\b.*?"
        r"(?=^## |\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )

    sections: list[str] = []

    for match in section_pattern.finditer(text):
        section_campaign = match.group("campaign")
        if section_campaign is not None:
            section_campaign = section_campaign.strip()

        if campaign_id is not None:
            if section_campaign != campaign_id:
                continue
        elif section_campaign is not None:
            continue

        sections.append(match.group(0).strip())
    memories: list[str] = []
    # Each rendered label accepts every heading past and present entries use, so
    # historical postmortems stay readable without being rewritten.
    labels = [
        ("Result", ("Result",)),
        ("Observed behavior", ("Observed behavior",)),
        ("Hypothesis assessment", ("Hypothesis assessment",)),
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
                    value = match.group(1)
                    if display == "Evidence inspected":
                        value = _artifact_reference_list(value)
                    parts.append(f"{display}: {_compact(value, 420)}")
                    recognized.add(display)
                    break
        if not recognized & narrative:
            body = "\n".join(section.splitlines()[1:]).strip()
            for _, headings in labels:
                for heading in headings:
                    body = re.sub(
                        rf"\*\*{re.escape(heading)}:\*\*\s*"
                        r".+?(?=\n\s*\n|\n\*\*|\Z)",
                        "",
                        body,
                        flags=re.DOTALL,
                    )
            body = body.strip()
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
            detail += f"; detail {_existing_artifact_reference(artifact, kind='file')}"
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
            detail += f"; detail {_existing_artifact_reference(artifact, kind='file')}"
        lines.append(detail)
    return lines


def _change_details(result: dict) -> str:
    parameter_changes = result.get("parameter_changes") or []
    if parameter_changes:
        return "; ".join(
            f"{item['path']}: {item.get('before')} → {item.get('after')}"
            for item in parameter_changes
        )
    code_changes = result.get("code_changes") or []
    if code_changes:
        return (
            f"{operation_description(result) or '-'}; files: {', '.join(code_changes)}"
        )
    return operation_description(result) or "-"


def _existing_artifact_reference(value: str | None, *, kind: str = "artifact") -> str:
    if not value:
        return "unavailable"
    normalized = str(value).replace("\\", "/")
    relative = Path(normalized)
    if relative.is_absolute() or PureWindowsPath(normalized).drive:
        return "unavailable"
    root = ROOT.resolve()
    resolved = (root / relative).resolve()
    if resolved != root and root not in resolved.parents:
        return "unavailable"
    is_complete_checkpoint = resolved.is_dir() and all(
        (resolved / filename).is_file() for filename in ARTIFACT_FILES
    )
    is_usable = {
        "artifact": resolved.is_file() or is_complete_checkpoint,
        "checkpoint": is_complete_checkpoint,
        "file": resolved.is_file(),
    }[kind]
    if is_usable:
        return f"`{resolved.relative_to(root).as_posix()}`"
    return "unavailable"


def _artifact_reference_list(value: str) -> str:
    references = [
        token.strip("`\"',;()[] ")
        for token in re.split(r"[\s,]+", value)
        if token.strip("`\"',;()[] ")
    ]
    return ", ".join(_existing_artifact_reference(path) for path in references)


def _postmortem_reference(value: str | None) -> str:
    if _existing_artifact_reference(value, kind="file") == "unavailable":
        return "unavailable"
    normalized = str(value).replace("\\", "/")
    return f"[postmortem]({normalized})"


def _experiment_outcome(result: dict) -> str:
    candidate = result.get("candidate_metrics") or {}
    success = candidate.get("pooled_success_percent", candidate.get("success_percent"))
    parts = []
    if success is not None:
        parts.append(f"success {float(success):.2f}%")
    if result.get("error"):
        parts.append(_compact(str(result["error"]), 120))
    return "; ".join(parts) or "no measured candidate result"


def _replicated_experiment_index(result: dict) -> int | None:
    raw_value = result.get("replication_of")
    if raw_value is None:
        return None
    try:
        return int(str(raw_value))
    except (TypeError, ValueError):
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


def _v4_result_measurements(result: dict) -> str:
    evaluations: list[dict] = []
    for requested in result.get("requested_evaluations") or []:
        metrics = requested.get("metrics") or {}
        evaluations.append(
            {
                "candidate": requested.get("candidate", "-"),
                "instrument": requested.get("instrument", "research_evaluation"),
                "model_fingerprint": requested.get("model_fingerprint"),
                **metrics,
            }
        )
    evaluations.extend(result.get("task_reference_evaluations") or [])
    if not evaluations:
        for candidate in result.get("candidates") or []:
            for evaluation in candidate.get("evaluations") or []:
                evaluations.append(
                    {"candidate": candidate.get("name", "-"), **evaluation}
                )
    if not evaluations:
        return "unmeasured"
    grouped: dict[tuple[str, str, str | None], list[dict]] = {}
    for evaluation in evaluations:
        instrument = evaluation.get("instrument", "research_evaluation")
        panel = evaluation.get("panel")
        measurement = f"{instrument}{f'/{panel}' if panel else ''}"
        fingerprint = evaluation.get("model_fingerprint")
        key = (
            str(evaluation.get("candidate", "-")),
            measurement,
            str(fingerprint) if fingerprint else None,
        )
        grouped.setdefault(key, []).append(evaluation)
    panels = []
    for (candidate, measurement, fingerprint), group in grouped.items():
        details = [candidate, measurement]
        if fingerprint:
            details.append(f"model {fingerprint[:12]}")
        if len(group) > 1:
            details.append(f"{len(group)} measurements")
        episodes = sorted(
            {int(item["episodes"]) for item in group if item.get("episodes") is not None}
        )
        if len(episodes) == 1:
            details.append(
                f"{episodes[0]} episodes" + (" each" if len(group) > 1 else "")
            )
        elif episodes:
            details.append(
                f"episode counts {min(episodes)}-{max(episodes)}"
            )
        seeds = sorted(
            {int(item["seed"]) for item in group if item.get("seed") is not None}
        )
        if len(seeds) == 1:
            details.append(f"seed {seeds[0]}")
        elif seeds:
            details.append(f"seeds {min(seeds)}-{max(seeds)}")
        scores = sorted(
            {
                float(item["success_percent"])
                for item in group
                if item.get("success_percent") is not None
            }
        )
        if len(scores) == 1:
            details.append(f"success {scores[0]:.2f}%")
        elif scores:
            details.append(f"success range {min(scores):.2f}-{max(scores):.2f}%")
        artifacts = [
            str(item["evaluation_artifact"])
            for item in group
            if item.get("evaluation_artifact")
        ]
        if len(artifacts) == 1:
            details.append(
                f"detail {_existing_artifact_reference(artifacts[0], kind='file')}"
            )
        elif artifacts:
            available = sum(
                _existing_artifact_reference(path, kind="file") != "unavailable"
                for path in artifacts
            )
            details.append(f"details available {available}/{len(artifacts)}")
        panels.append(", ".join(details))
    return "; ".join(panels)


def _v4_measurements(candidate: dict) -> str:
    evaluations = candidate.get("evaluations") or []
    if not evaluations:
        return "unmeasured"
    panels = []
    for evaluation in evaluations:
        success = evaluation.get("success_percent")
        result = (
            f"{evaluation.get('panel', 'research_evaluation')}, "
            f"seed {evaluation.get('seed', '-')}, "
            f"{evaluation.get('episodes', '-')} episodes"
        )
        if success is not None:
            result += f", success {float(success):.2f}%"
        panels.append(result)
    return "; ".join(panels)


def _training_proxy_trajectory(candidates: list[dict]) -> str:
    ordered = sorted(candidates, key=lambda item: int(item.get("timesteps", 0)))
    proxy_key = (
        "training_success"
        if any(item.get("training_success") is not None for item in ordered)
        else "ep_rew_mean"
    )
    proxy_label = {
        "training_success": "training success",
        "ep_rew_mean": "episode reward",
    }[proxy_key]
    observations = [
        (int(item.get("timesteps", 0)), item.get(proxy_key))
        for item in ordered
        if item.get(proxy_key) is not None
    ]
    if not observations:
        return (
            f"- Training proxy observations: unavailable ({proxy_label} proxy, "
            "not a training evaluation result)"
        )
    first_steps = observations[0][0]
    last_steps = observations[-1][0]
    values = [value for _, value in observations]
    return (
        f"- Training proxy observations: {len(observations)} checkpoints from "
        f"{first_steps:,}-{last_steps:,} local steps; observed {proxy_label} "
        f"range {min(values):g}-{max(values):g}. These are descriptive training "
        "facts, not a checkpoint ranking or evaluation result. Per-checkpoint "
        "values remain available through the training log query."
    )


def _checkpoint_inventory_lines(
    candidates: list[dict], *, parent_training_steps: int = 0
) -> list[str]:
    # Training records the pool in lexicographic name order, which interleaves step counts.
    candidates = sorted(candidates, key=lambda item: int(item.get("timesteps", 0)))
    artifacts = [str(candidate.get("artifact", "")) for candidate in candidates]
    parents = [Path(artifact.replace("\\", "/")).parent for artifact in artifacts]
    common_parts = list(parents[0].parts) if parents else []
    for parent in parents[1:]:
        common_length = 0
        for left, right in zip(common_parts, parent.parts):
            if left != right:
                break
            common_length += 1
        common_parts = common_parts[:common_length]
    common_parent = Path(*common_parts) if common_parts else None
    lines = []
    if common_parent is not None:
        lines.append(f"- Artifact base path: {_recorded_path(common_parent.as_posix())}")
        lines.append(
            f"- {len(candidates)} checkpoints available for measurement; steps "
            f"{min(int(candidate.get('timesteps', 0)) for candidate in candidates):,}-"
            f"{max(int(candidate.get('timesteps', 0)) for candidate in candidates):,}; "
            "each artifact is "
            f"{_recorded_path((common_parent / '<identifier>').as_posix())}"
        )
    else:
        lines.append(
            f"- {len(candidates)} checkpoints available for measurement; steps "
            f"{min(int(candidate.get('timesteps', 0)) for candidate in candidates):,}-"
            f"{max(int(candidate.get('timesteps', 0)) for candidate in candidates):,}"
        )
    lines.append(
        "- A measurement request may select at most 3 distinct models; the "
        "Researcher determines which models are informative."
    )
    identifiers = ", ".join(
        f"`{_recorded_value(candidate.get('name'))}` "
        f"(local {int(candidate.get('timesteps', 0)):,} steps; accumulated "
        f"{parent_training_steps + int(candidate.get('timesteps', 0)):,} steps)"
        for candidate in candidates
    )
    lines.append(f"- Identifiers: {identifiers}")
    for candidate, artifact, parent in zip(candidates, artifacts, parents):
        if common_parent is None or parent != common_parent:
            lines.append(
                f"- `{_recorded_value(candidate.get('name'))}` artifact: "
                f"{_recorded_path(artifact)}"
            )
    return lines


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _recorded_value(value: object) -> str:
    if value is None or value == "":
        return "not recorded"
    return str(value)


def _recorded_path(value: object) -> str:
    if value is None or value == "":
        return "not recorded"
    return f"`{str(value).replace('\\', '/')}`"


def _flatten_parameters(parameters: dict, prefix: str = "") -> dict[str, object]:
    flattened: dict[str, object] = {}
    for key, value in parameters.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flattened.update(_flatten_parameters(value, path))
        else:
            flattened[path] = value
    return flattened


def _parameter_differences(current: dict, lineage: dict | None) -> str:
    if not isinstance(lineage, dict) or not isinstance(lineage.get("parameters"), dict):
        return "not recorded"
    current_values = _flatten_parameters(current)
    lineage_values = _flatten_parameters(lineage["parameters"])
    missing = object()
    differences = []
    for path in sorted(current_values.keys() | lineage_values.keys()):
        current_value = current_values.get(path, missing)
        lineage_value = lineage_values.get(path, missing)
        if current_value == lineage_value:
            continue
        rendered_lineage = (
            "not recorded" if lineage_value is missing else _stable_json(lineage_value)
        )
        rendered_current = (
            "not recorded" if current_value is missing else _stable_json(current_value)
        )
        differences.append(
            f"`{path}`: lineage {rendered_lineage}; current {rendered_current}"
        )
    return "; ".join(differences) or "none"


def _authoritative_lineage_lines(identifier: str, lineage: dict) -> list[str]:
    evaluation_artifacts = lineage.get("evaluation_artifacts")
    evidence = (
        ", ".join(_recorded_path(path) for path in evaluation_artifacts)
        if isinstance(evaluation_artifacts, list) and evaluation_artifacts
        else "not recorded"
    )
    parameters = lineage.get("parameters")
    return [
        f"- `{identifier}`",
        f"  - Candidate: {_recorded_value(lineage.get('candidate'))}",
        f"  - Origin experiment: {_recorded_value(lineage.get('origin_experiment'))}",
        f"  - Accumulated training steps: {_recorded_value(lineage.get('training_steps'))}",
        f"  - Artifact: {_recorded_path(lineage.get('artifact'))}",
        f"  - Model fingerprint: {_recorded_value(lineage.get('fingerprint'))}",
        f"  - Scientific commit: {_recorded_value(lineage.get('scientific_commit'))}",
        "  - Effective parameters: "
        + (_stable_json(parameters) if isinstance(parameters, dict) else "not recorded"),
        f"  - Recorded evaluation artifacts: {evidence}",
        f"  - Researcher reason: {_recorded_value(lineage.get('reason'))}",
    ]


def _lineage_fact_identity(lineage: dict) -> tuple | None:
    parameters = lineage.get("parameters")
    required = (
        lineage.get("artifact"),
        lineage.get("fingerprint"),
        lineage.get("scientific_commit"),
    )
    if any(value is None or value == "" for value in required) or not isinstance(
        parameters, dict
    ):
        return None
    return (*required, _stable_json(parameters))


def _authoritative_lineage_alias_lines(
    identifier: str,
    canonical_identifier: str,
    lineage: dict,
    canonical_lineage: dict,
) -> list[str]:
    lines = [
        f"- `{identifier}`: alias of `{canonical_identifier}`",
        f"  - Researcher reason: {_recorded_value(lineage.get('reason'))}",
    ]
    for label, field in (
        ("Candidate", "candidate"),
        ("Origin experiment", "origin_experiment"),
        ("Accumulated training steps", "training_steps"),
    ):
        if lineage.get(field) != canonical_lineage.get(field):
            lines.append(f"  - {label}: {_recorded_value(lineage.get(field))}")
    if lineage.get("evaluation_artifacts") != canonical_lineage.get(
        "evaluation_artifacts"
    ):
        evidence = lineage.get("evaluation_artifacts")
        lines.append(
            "  - Recorded evaluation artifacts: "
            + (
                ", ".join(_recorded_path(path) for path in evidence)
                if isinstance(evidence, list) and evidence
                else "not recorded"
            )
        )
    return lines


def _current_lineages_and_recipes_lines(state: dict, current_params: dict) -> list[str]:
    working = state.get("working_lineage")
    best_known = state.get("best_known_lineage")
    retained = [
        lineage
        for lineage in state.get("retained_lineages", [])
        if isinstance(lineage, dict) and lineage.get("id")
    ]
    lineages = [
        *(([("working", working)]) if isinstance(working, dict) else []),
        *(([("best_known", best_known)]) if isinstance(best_known, dict) else []),
        *((str(lineage["id"]), lineage) for lineage in retained),
    ]
    identifiers = ", ".join(f"`{identifier}`" for identifier, _ in lineages)
    lines = [
        "## Current lineages and scientific recipes",
        "",
        f"- Valid `training_parent` identifiers: {identifiers or 'not recorded'}",
        "",
        "### Lineages",
        "",
    ]
    if lineages:
        canonical_by_identity: dict[tuple, tuple[str, dict]] = {}
        for identifier, lineage in lineages:
            identity = _lineage_fact_identity(lineage)
            canonical = canonical_by_identity.get(identity) if identity else None
            if canonical is None:
                lines.extend(_authoritative_lineage_lines(identifier, lineage))
                if identity is not None:
                    canonical_by_identity[identity] = (identifier, lineage)
            else:
                lines.extend(
                    _authoritative_lineage_alias_lines(
                        identifier, canonical[0], lineage, canonical[1]
                    )
                )
    else:
        lines.append("No current lineage is recorded.")
    lines.extend(
        [
            "",
            "### Effective scientific recipe in the current worktree",
            "",
            "- Researcher-owned source and tests: current worktree",
            f"- Effective parameters: {_stable_json(current_params)}",
            "- Parameter differences from `working`: "
            + _parameter_differences(current_params, working),
            "- Parameter differences from `best_known`: "
            + _parameter_differences(current_params, best_known),
            "",
            "### Current experiment checkpoints available for measurement",
            "",
        ]
    )
    candidates = (
        state.get("pending_analysis", {}).get("candidates", [])
        if isinstance(state.get("pending_analysis"), dict)
        else []
    )
    if candidates:
        parent_training_steps = int(
            state.get("pending_analysis", {}).get("parent_training_steps", 0)
        )
        lines.extend(
            _checkpoint_inventory_lines(
                candidates, parent_training_steps=parent_training_steps
            )
        )
    else:
        lines.append("No current experiment checkpoints are recorded.")
    return lines


def _v4_evidence_lines(pending: dict | None, results: list[dict]) -> list[str]:
    records: dict[str, str] = {}
    if isinstance(pending, dict):
        source = pending
        evaluations = [
            *(source.get("requested_evaluations") or []),
            *(source.get("partial_evaluations") or []),
        ]
        for evaluation in evaluations:
            metrics = evaluation.get("metrics") or {}
            path = metrics.get("evaluation_artifact")
            if not path:
                continue
            fingerprint = evaluation.get("model_fingerprint") or metrics.get(
                "model_fingerprint"
            )
            identity = str(fingerprint)[:12] if fingerprint else "unverified"
            semantics = evaluation.get("evaluation_semantics") or metrics.get(
                "evaluation_semantics", "unavailable"
            )
            episodes = evaluation.get("episodes", metrics.get("episodes", "-"))
            seed = evaluation.get("seed", metrics.get("seed", "-"))
            records[str(path)] = (
                f"research evaluation; candidate "
                f"`{evaluation.get('candidate', 'unavailable')}`; model `{identity}`; "
                f"seed {seed}; {episodes} episodes; success "
                f"{metrics.get('success_percent', 'unavailable')}%; semantics "
                f"`{semantics}`"
            )
        references = [
            *(source.get("task_reference_evaluations") or []),
            *(source.get("partial_task_reference_evaluations") or []),
        ]
        for evaluation in references:
            path = evaluation.get("evaluation_artifact")
            if not path:
                continue
            fingerprint = evaluation.get("model_fingerprint")
            identity = str(fingerprint)[:12] if fingerprint else "unverified"
            records[str(path)] = (
                f"task reference; candidate "
                f"`{evaluation.get('candidate', 'unavailable')}`; model `{identity}`; "
                f"panel `{evaluation.get('panel', 'unavailable')}`; "
                f"{evaluation.get('episodes', '-')} episodes; success "
                f"{evaluation.get('success_percent', 'unavailable')}%"
            )
    lines = [
        f"- {_existing_artifact_reference(path, kind='file')}: {description}"
        for path, description in sorted(records.items())
    ]
    for result in sorted(results, key=lambda item: int(item.get("index", 0)), reverse=True):
        summary = _v4_result_measurements(result)
        if summary == "unmeasured":
            continue
        sources = [_existing_artifact_reference("research/results.jsonl", kind="file")]
        postmortem = result.get("postmortem")
        if postmortem:
            sources.append(_existing_artifact_reference(postmortem, kind="file"))
        lines.append(
            f"- Experiment {result.get('index', '-')}: {summary}"
            + "; source "
            + ", ".join(dict.fromkeys(sources))
        )
    if not lines:
        return ["No fingerprint-bound development evidence recorded yet."]
    return lines


def _render_v4_research_brief(
    state: dict,
    results: list[dict],
    postmortems: str,
    campaign_id: str | None,
    campaign_base_commit: str | None,
    current_method: str,
    current_params: dict,
) -> str:
    pending = state.get("pending_analysis")
    latest = pending.get("result") if isinstance(pending, dict) else (results[-1] if results else None)
    latest_experiment = pending.get("experiment") if isinstance(pending, dict) else (latest or {}).get("index", "none")
    phase = "post-training analysis" if isinstance(pending, dict) else "experiment preparation"
    if state.get("pending_final_benchmark") is not None:
        phase = "official assessment"
    terminal = state.get("terminal_campaign_status")
    if terminal:
        phase = "terminal official assessment"
    lines = [
        "# Research Brief",
        "",
        "## Current phase and latest event",
        "",
        f"- Campaign: `{campaign_id or '-'}`",
        f"- Base commit: `{campaign_base_commit or '-'}`",
        f"- Current phase: {phase}",
        f"- Current experiment: {latest_experiment}",
        f"- Latest event: {state.get('last_verdict', (latest or {}).get('verdict', 'none'))}",
        "- Campaign objective: the human-defined objective in `research/scenario.md`.",
        "- Available deliverables: "
        + (
            "none; the campaign is complete"
            if terminal
            else "`research/evaluation_request.json` or closure `research/proposal.json`"
            if isinstance(pending, dict)
            else "`research/proposal.json`"
        ),
    ]
    if terminal:
        lines.append(f"- Terminal campaign status: {terminal}")

    lines.extend(["", "## Latest experiment", ""])
    if isinstance(pending, dict):
        result = pending.get("result", {})
        candidates = sorted(
            pending.get("candidates", []),
            key=lambda item: int(item.get("timesteps", 0)),
        )
        measured = [candidate for candidate in candidates if candidate.get("evaluations")]
        unmeasured = [candidate for candidate in candidates if not candidate.get("evaluations")]
        lines.extend([
            f"- Operation: {operation_description(result) or result.get('kind', '-')}",
            f"- Parent: {result.get('training_parent', pending.get('training_parent', '-'))}",
            f"- Intervention: {_change_details(result)}",
            "- Raw training logs: " + ", ".join(
                _existing_artifact_reference(path, kind="file")
                for path in pending.get("training_log_paths", [])
            ) if pending.get("training_log_paths") else "- Raw training logs: unmeasured",
            _training_proxy_trajectory(candidates),
        ])
        if unmeasured:
            steps = [int(candidate.get("timesteps", 0)) for candidate in candidates]
            lines.append(
                f"- Unmeasured checkpoints: {len(unmeasured)} of {len(candidates)}; "
                f"steps {min(steps):,}-{max(steps):,}. Every checkpoint carries its own "
                "training success and reward; retrieve them with `uv run python "
                f"research/query_training_log.py --experiment {pending.get('experiment', '-')} "
                f"--from-step {min(steps)} --to-step {max(steps)}`"
            )
        if measured:
            parent_steps = int(pending.get("parent_training_steps", 0))
            lines.extend([
                "",
                "| Checkpoint | Local steps | Accumulated steps | Training facts | Measurements |",
                "|---|---:|---:|---|---|",
            ])
            for candidate in measured:
                facts = f"success {_candidate_metric(candidate, 'training_success')}; reward {_candidate_metric(candidate, 'ep_rew_mean')}"
                local_steps = int(candidate.get("timesteps", 0))
                lines.append(f"| `{candidate.get('name', '-')}` | {local_steps:,} | {parent_steps + local_steps:,} | {facts} | {_v4_measurements(candidate)} |")
    elif latest:
        lines.extend([
            f"- Operation: {operation_description(latest) or latest.get('kind', '-')}",
            f"- Parent: {latest.get('training_parent', '-')}",
            f"- Intervention: {_change_details(latest)}",
            f"- Measurements: {_v4_result_measurements(latest)}",
            f"- Hypothesis assessment: {latest.get('hypothesis_assessment', 'unavailable')}",
            f"- Final action: {(latest.get('closure_decision') or {}).get('continue_from', 'unmeasured')}",
        ])
    else:
        lines.append("No experiment has completed in this campaign.")

    if latest:
        training_record = {**(pending or {}), **latest}
        requested_steps = training_record.get("training_budget_steps")
        completed_steps = training_record.get("completed_training_steps")
        if completed_steps is None:
            completed_steps = max(
                (
                    int(candidate["timesteps"])
                    for candidate in training_record.get("candidates", [])
                    if candidate.get("timesteps") is not None
                ),
                default=None,
            )
        if requested_steps is not None:
            lines.append(f"- Requested training budget: {int(requested_steps):,} steps")
        if completed_steps is not None:
            lines.append(f"- Completed training steps: {int(completed_steps):,}")

    lines.extend(["", *_current_lineages_and_recipes_lines(state, current_params)])

    lines.extend(["", "## Working lineage", ""])
    lines.append(
        "- See `working` under **Current lineages and scientific recipes**."
        if state.get("working_lineage")
        else "- Working: unset"
    )

    lines.extend(["", "## Campaign experiment index", "", "| # | Operation / family | Parent | Intervention | Measurements | Hypothesis assessment | Final decisions | Detail |", "|---:|---|---|---|---|---|---|---|"])
    for result in sorted(results, key=lambda item: int(item.get("index", 0)), reverse=True):
        checkpoints = compact_measurement_summary(result)
        closure = result.get("closure_decision") or {}
        lines.append(
            f"| {result.get('index', '-')} | {result.get('kind', '-')} / {result.get('family', '-')} | "
            f"{result.get('training_parent', '-')} | {_compact(_change_details(result), 100).replace('|', '/')} | "
            f"{_compact(checkpoints, 140).replace('|', '/')} | "
            f"{_compact(str(result.get('hypothesis_assessment', 'unavailable')), 140).replace('|', '/')} | "
            f"working {closure.get('continue_from', 'unmeasured')}; "
            f"best known {(closure.get('best_known') or {}).get('candidate', 'unchanged')}; "
            f"code {(closure.get('code') or {}).get('action', 'unrecorded')} | "
            f"{_postmortem_reference(result.get('postmortem'))} |"
        )
    if not results:
        lines.append("| - | - | - | - | - | - | - | - |")

    lines.extend(["", "## Available development evidence", ""])
    lines.extend(_v4_evidence_lines(pending, results))

    strategy = scientific_strategy_section(postmortems, campaign_id)
    lines.extend(
        [
            "",
            "## Provisional scientific synthesis",
            "",
            (
                "Researcher-authored interpretation of the campaign evidence. "
                "It is memory for reassessment, not a prescribed next direction:"
            ),
            "",
        ]
    )
    lines.append(
        "\n".join(strategy.splitlines()[1:]).strip()
        if strategy
        else "No scientific strategy recorded for this campaign yet."
    )

    lines.extend(["", "## Repeated operations", ""])
    groups = _replication_groups(results)
    if groups:
        for original, entries in groups:
            facts = "; ".join(
                f"experiment {entry.get('index')}, seed {entry.get('training_seed', '-')}, "
                f"{_v4_result_measurements(entry)}"
                for entry in entries
            )
            lines.append(f"- Replication group `{original}`: {facts}")
    else:
        lines.append("No repeated operations recorded.")

    lines.extend(["", "## Reusable lineages", ""])
    retained = state.get("retained_lineages") or []
    if retained:
        for lineage in retained:
            lines.append(
                f"- See `{lineage.get('id', '-')}` under "
                "**Current lineages and scientific recipes**."
            )
    else:
        lines.append("No retained alternatives.")
    lines.extend(["", "## Best-known model", ""])
    best_known = state.get("best_known_lineage")
    lines.append(
        "- See `best_known` under **Current lineages and scientific recipes**."
        if best_known
        else "- Best known: unset"
    )
    official = state.get("official_metrics")
    if official is not None:
        official_model = state.get("official_benchmark_model") or {}
        lines.extend([
            "",
            "## Official report",
            "",
            f"- Model: {official_model.get('selected', 'legacy official assessment')} ({official_model.get('artifact', 'not recorded')})",
            f"- Verdict: {state.get('official_benchmark_verdict', terminal or 'not recorded')}",
            f"- Result: {official}",
            f"- Terminal assessment: {terminal or 'not recorded'}",
        ])
    return "\n".join(lines).rstrip() + "\n"


def render_research_brief() -> str:
    from research import runner_repository  # Import here to avoid circular dependency

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

    # Extract campaign info for filtering
    campaign_id = runner_repository.current_campaign_id(state) if state else None
    campaign_base_commit = (
        runner_repository.current_campaign_base_commit(state) if state else None
    )

    results = []
    if results_path.exists():
        all_results = [
            json.loads(line)
            for line in results_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        # Filter by campaign if available
        if campaign_id:
            results = [r for r in all_results if r.get("campaign_id") == campaign_id]
        else:
            results = all_results

    if state.get("schema_version") == 4:
        return _render_v4_research_brief(
            state,
            results,
            postmortems,
            campaign_id,
            campaign_base_commit,
            current_method,
            params,
        )

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
            "",
            "| Candidate | Steps | Training success | Training reward | Artifact |",
            "|---|---:|---:|---:|---|",
        ]
        for candidate in sorted(
            pending_evaluation["candidates"], key=lambda item: int(item["timesteps"])
        ):
            evaluation_lines.append(
                f"| `{candidate['name']}` | {int(candidate['timesteps']):,} | "
                f"{_candidate_metric(candidate, 'training_success')} | "
                f"{_candidate_metric(candidate, 'ep_rew_mean')} | "
                f"{_existing_artifact_reference(candidate.get('artifact'), kind='checkpoint')} |"
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
                    "The available measurement operations and the "
                    "`research/evaluation_request.json` contract are defined in "
                    "`research/instruments.md`."
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
                "Use the summaries below as the normal evidence entry point. "
                "Inspect the referenced detailed evaluation artifacts as needed "
                "to resolve the lineage decision; they remain the authoritative "
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
    ]

    # Add campaign header if available
    if campaign_id:
        lines.extend(
            [
                "## Campaign Context",
                "",
                f"- Campaign: `{campaign_id}`",
                f"- Base commit: `{campaign_base_commit}`",
                "",
            ]
        )

    strategy = scientific_strategy_section(postmortems, campaign_id)
    lines.extend(
        [
            "- Campaign objective: the human-defined objective in `research/scenario.md`.",
            "",
            "## Immutable goal",
            "",
            (
                "The current scientific problem, its protected task definition, and its "
                "terminology are defined in `research/scenario.md`."
            ),
            "",
            "## Provisional scientific synthesis",
            "",
            (
                "Researcher-authored interpretation of the campaign evidence. "
                "It is memory for reassessment, not a prescribed next direction:"
            ),
            "",
            "\n".join(strategy.splitlines()[1:]).strip()
            if strategy
            else (
                "No scientific strategy recorded for this campaign yet. Establish it "
                "in `research/postmortems.md` when preparing the next experiment; "
                "historical results have not been reinterpreted automatically."
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
            "- Accepted checkpoint: "
            + (
                _existing_artifact_reference(
                    state["accepted_artifact"], kind="checkpoint"
                )
                if "accepted_artifact" in state
                else "missing"
            ),
            (
                "- Accepted evaluation detail: "
                + (
                    ", ".join(
                        _existing_artifact_reference(path, kind="file")
                        for path in state.get("accepted_evaluations", [])
                    )
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
            "| # | Family | Operation | Init / budget | Outcome | Verdict |",
            "|---:|---|---|---|---|---|",
        ]
    )

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

    families: dict[str, list[int]] = {}

    for result in results:
        family = str(result.get("family", "")).strip()
        if not family:
            continue
        families.setdefault(family, []).append(int(result["index"]))

    if families:
        lines.extend(
            [
                "",
                "## Intervention families explored",
                "",
            ]
        )

        for family, experiments in sorted(families.items()):
            experiment_list = ", ".join(str(index) for index in experiments)
            lines.append(f"- `{family}`: experiments {experiment_list}")

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
    memories = _postmortem_memory(postmortems, campaign_id=campaign_id)
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
            "- Keep historical observations and decisions intact; revise the campaign's scientific strategy as evidence changes. Record lessons with their sources and limits, not a prescribed line count.",
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
