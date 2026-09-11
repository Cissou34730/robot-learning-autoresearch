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


def _postmortem_reference(value: str | None) -> str:
    if _existing_artifact_reference(value, kind="file") == "unavailable":
        return "unavailable"
    normalized = str(value).replace("\\", "/")
    return f"[postmortem]({normalized})"


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
    lines.append("- A measurement request may select at most 3 distinct models.")
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
            "- Effective parameters: "
            + (_stable_json(current_params) if lineages else "not recorded"),
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
    research_evaluations: list[dict] = []
    task_reference_evaluations: list[dict] = []
    fingerprints: set[str] = set()
    artifacts: set[str] = set()
    seen_research: set[str] = set()
    seen_task_reference: set[str] = set()
    sources = [*results, *(([pending]) if isinstance(pending, dict) else [])]
    for source in sources:
        direct = [
            *(source.get("requested_evaluations") or []),
            *(source.get("partial_evaluations") or []),
        ]
        if not direct:
            direct = [
                {"candidate": candidate.get("name"), **evaluation}
                for candidate in source.get("candidates") or []
                for evaluation in candidate.get("evaluations") or []
            ]
        for evaluation in direct:
            metrics = evaluation.get("metrics") or evaluation
            normalized = {**metrics, **evaluation}
            identity = str(metrics.get("evaluation_artifact") or _stable_json({
                key: normalized.get(key)
                for key in (
                    "candidate",
                    "instrument",
                    "episodes",
                    "seed",
                    "evaluation_semantics",
                    "model_fingerprint",
                )
            }))
            if identity in seen_research:
                continue
            seen_research.add(identity)
            research_evaluations.append(normalized)
            fingerprint = evaluation.get("model_fingerprint") or metrics.get(
                "model_fingerprint"
            )
            if fingerprint:
                fingerprints.add(str(fingerprint))
            if metrics.get("evaluation_artifact"):
                artifacts.add(str(metrics["evaluation_artifact"]))
        for evaluation in [
            *(source.get("task_reference_evaluations") or []),
            *(source.get("partial_task_reference_evaluations") or []),
        ]:
            identity = str(evaluation.get("evaluation_artifact") or _stable_json({
                key: evaluation.get(key)
                for key in (
                    "candidate",
                    "panel",
                    "panel_version",
                    "episodes",
                    "seed",
                    "model_fingerprint",
                )
            }))
            if identity in seen_task_reference:
                continue
            seen_task_reference.add(identity)
            task_reference_evaluations.append(evaluation)
            if evaluation.get("model_fingerprint"):
                fingerprints.add(str(evaluation["model_fingerprint"]))
            if evaluation.get("evaluation_artifact"):
                artifacts.add(str(evaluation["evaluation_artifact"]))
    measurement_count = len(research_evaluations) + len(task_reference_evaluations)
    if not measurement_count:
        return ["No fingerprint-bound development evidence recorded yet."]

    def numeric_values(values: set[int]) -> str:
        ordered = sorted(values)
        if len(ordered) <= 5:
            return ", ".join(str(value) for value in ordered)
        return f"{ordered[0]}-{ordered[-1]} ({len(ordered)} distinct)"

    def text_values(values: set[str]) -> str:
        ordered = sorted(values)
        if len(ordered) <= 3:
            return ", ".join(f"`{value}`" for value in ordered)
        return f"{len(ordered)} distinct"

    lines = [
        (
            f"- {measurement_count} measurements; {len(artifacts)} detailed artifacts; "
            f"{len(fingerprints)} fingerprint-bound models."
        ),
        (
            "- Measurement record index: "
            f"{_existing_artifact_reference('research/results.jsonl', kind='file')}; "
            "current analysis records: "
            f"{_existing_artifact_reference('research/research_state.json', kind='file')}."
        ),
    ]
    if research_evaluations:
        episodes = {
            int(item["episodes"])
            for item in research_evaluations
            if item.get("episodes") is not None
        }
        seeds = {
            int(item["seed"])
            for item in research_evaluations
            if item.get("seed") is not None
        }
        semantics = {
            str(item["evaluation_semantics"])
            for item in research_evaluations
            if item.get("evaluation_semantics")
        }
        lines.append(
            f"- `research_evaluation`: {len(research_evaluations)} measurements; "
            f"episode counts {numeric_values(episodes) if episodes else 'not recorded'}; "
            f"seeds {numeric_values(seeds) if seeds else 'not recorded'}; semantics "
            f"{text_values(semantics) if semantics else 'not recorded'}."
        )
    if task_reference_evaluations:
        panels = {
            str(item["panel"])
            for item in task_reference_evaluations
            if item.get("panel")
        }
        lines.append(
            f"- `task_reference`: {len(task_reference_evaluations)} measurements; "
            f"panels {text_values(panels) if panels else 'not recorded'}."
        )
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
        f"- Current learning method: {current_method}",
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
        ])
        if unmeasured:
            steps = [int(candidate.get("timesteps", 0)) for candidate in candidates]
            lines.append(
                f"- Unmeasured checkpoints: {len(unmeasured)} of {len(candidates)}; "
                f"steps {min(steps):,}-{max(steps):,}."
            )
        if measured:
            parent_steps = int(pending.get("parent_training_steps", 0))
            lines.extend([
                "",
                "| Checkpoint | Local steps | Accumulated steps | Measurements |",
                "|---|---:|---:|---|",
            ])
            for candidate in measured:
                local_steps = int(candidate.get("timesteps", 0))
                lines.append(f"| `{candidate.get('name', '-')}` | {local_steps:,} | {parent_steps + local_steps:,} | {_v4_measurements(candidate)} |")
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

    lines.extend(["", "## Development evidence index", ""])
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
            experiments = ", ".join(
                str(entry.get("index", "-")) for entry in entries
            )
            lines.append(
                f"- Replication group `{original}`: {len(entries)} runs; "
                f"experiments {experiments}."
            )
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

    return _render_v4_research_brief(
        state,
        results,
        postmortems,
        campaign_id,
        campaign_base_commit,
        current_method,
        params,
    )


def write_research_brief() -> Path:
    BRIEF_PATH.write_text(render_research_brief(), encoding="utf-8")
    return BRIEF_PATH


def main() -> None:
    brief = write_research_brief()
    print(f"Wrote {brief.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
