"""Build bounded research context for token-efficient autonomous sessions."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PureWindowsPath

from research import runner_console as console
from research.runner_protocol import (
    extends_lineage,
    is_researcher_owned,
    operation_description,
    preparation_ledger,
    scientific_strategy_section,
    upcoming_experiment_index,
)
from research.runner_repository import (
    ARTIFACT_FILES,
    MEASUREMENT_LEDGER_KEYS,
    campaign_coverage,
    compact_measurement_summary,
)
from robot_learning.training.progress import parse_training_records

ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DIR = ROOT / "research"
BRIEF_PATH = RESEARCH_DIR / "brief.md"


RESULTS_REFERENCE = "research/results.jsonl"
RESEARCH_STATE_REFERENCE = "research/research_state.json"
POSTMORTEMS_REFERENCE = "research/postmortems.md"

_SENTENCE_BOUNDARIES = ".;:"
_TRUNCATION_MARKER = "[truncated,"


def _sentence_boundary_within(text: str, limit: int) -> int:
    """Return the offset just past the last sentence boundary at or before the limit."""
    for index in range(min(limit, len(text)) - 1, -1, -1):
        if text[index] in _SENTENCE_BOUNDARIES and (
            index + 1 == len(text) or text[index + 1].isspace()
        ):
            return index + 1
    return -1


def _first_sentence_boundary(text: str) -> int:
    """Return the offset just past the first sentence boundary in the whole text."""
    for index, char in enumerate(text):
        if char in _SENTENCE_BOUNDARIES and (
            index + 1 == len(text) or text[index + 1].isspace()
        ):
            return index + 1
    return -1


def _truncation_marker(omitted: int, reference: str | None) -> str:
    hint = f"; full text in {reference}" if reference else ""
    return f"… [truncated, {omitted} more characters{hint}]"


def _compact(
    text: str,
    limit: int,
    *,
    reference: str | None = None,
    collapse_whitespace: bool = True,
) -> str:
    normalized = (
        re.sub(r"\s+", " ", text).strip() if collapse_whitespace else text.strip()
    )
    if len(normalized) <= limit:
        return normalized
    # Never re-truncate text that already announces its own truncation.
    if _TRUNCATION_MARKER in normalized:
        return normalized
    cut = _sentence_boundary_within(normalized, limit)
    if cut == -1:
        cut = _first_sentence_boundary(normalized)
    if cut == -1:
        # No sentence boundary exists, so any cut would leave a fragment.
        # Keep the whole text rather than truncate mid-sentence or mid-word.
        return normalized
    omitted = len(normalized) - cut
    # The only boundary was the end of the text, so nothing was omitted.
    if omitted == 0:
        return normalized
    return f"{normalized[:cut].rstrip()} {_truncation_marker(omitted, reference)}"


def _table_cell(text: object) -> str:
    """Render free text as one table cell without dropping any characters."""
    return re.sub(r"\s+", " ", str(text)).strip().replace("|", "&#124;")


def _indented_label_block(
    label: str, text: str, limit: int, reference: str
) -> list[str]:
    """Render free text as an indented block, preserving its line structure."""
    rendered = _compact(text, limit, reference=reference, collapse_whitespace=False)
    block = rendered.splitlines() or [""]
    lines = [f"- {label}: {block[0]}"]
    lines.extend(f"  {line}" for line in block[1:])
    return lines


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
        parts = [f"**{_compact(title, 180, reference=POSTMORTEMS_REFERENCE)}**"]
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
                    parts.append(
                        f"{display}: "
                        f"{_compact(value, 420, reference=POSTMORTEMS_REFERENCE)}"
                    )
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
                parts.insert(1, _compact(body, 420, reference=POSTMORTEMS_REFERENCE))
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
    description = operation_description(result)
    parameter_changes = result.get("parameter_changes") or []
    if parameter_changes:
        delta = "; ".join(
            f"{item['path']}: {item.get('before')} → {item.get('after')}"
            for item in parameter_changes
        )
        if extends_lineage(result) and description:
            return f"{description}; {delta}"
        return delta
    code_changes = result.get("code_changes") or []
    if code_changes:
        return f"{description or '-'}; files: {', '.join(code_changes)}"
    return description or "-"


def _recipe_basis(result: dict) -> str:
    """Name which recipe was in effect for a transfer run."""
    basis = str(result.get("recipe_basis", "")).strip()
    return {
        "parent_recipe": "the parent's restored recipe",
        "current_science": "the current worktree science",
    }.get(basis, basis or "not recorded")


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
        parts.append(_compact(str(result["error"]), 120, reference=RESULTS_REFERENCE))
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


def _researcher_owned_sources() -> list[str]:
    """Enumerated from the worktree so a new scientific module needs no registration."""
    package = ROOT / "robot_learning"
    if not package.is_dir():
        return []
    sources = []
    for path in package.rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        if path.name == "__init__.py" or not is_researcher_owned(relative):
            continue
        sources.append(relative)
    return sorted(sources)


def _intervention_surfaces(
    results: list[dict],
) -> tuple[list[tuple[str, int]], int, int]:
    counts = {source: 0 for source in _researcher_owned_sources()}
    parameter_only = 0
    unchanged = 0
    for result in results:
        changed = set()
        for entry in result.get("code_changes") or []:
            relative = str(entry).replace("\\", "/")
            if relative in counts:
                changed.add(relative)
        for relative in changed:
            counts[relative] += 1
        if changed:
            continue
        if result.get("parameter_changes"):
            parameter_only += 1
        else:
            unchanged += 1
    ordered = sorted(counts.items(), key=lambda item: item[0])
    return ordered, parameter_only, unchanged


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
            {
                int(item["episodes"])
                for item in group
                if item.get("episodes") is not None
            }
        )
        if len(episodes) == 1:
            details.append(
                f"{episodes[0]} episodes" + (" each" if len(group) > 1 else "")
            )
        elif episodes:
            details.append(f"episode counts {min(episodes)}-{max(episodes)}")
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
            f"{_episode_interval(evaluation)}"
        )
        if success is not None:
            result += f", success {float(success):.2f}%"
        panels.append(result)
    return "; ".join(panels)


def _candidate_identity(candidate: dict) -> str:
    """The stable identity used only to order candidates in the brief.

    It prefers a recorded fingerprint, then the artifact path. It deliberately
    ignores training proxy values, timesteps, input order and measurement status
    so that presentation cannot rank candidates by apparent promise.
    """
    for key in ("fingerprint", "model_fingerprint", "artifact", "name"):
        value = candidate.get(key)
        if value:
            return str(value)
    return _stable_json({key: candidate.get(key) for key in sorted(candidate)})


def _candidate_order_key(candidate: dict, scope: str) -> tuple:
    """A deterministic, metric-independent order key.

    The order is a stable permutation derived from candidate identity salted by
    the campaign/experiment scope. It does not depend on training proxy values,
    timesteps, candidate input order, or whether the candidate has been
    measured. Scoping by campaign and experiment keeps the permutation from
    collapsing to one fixed ordering if a candidate identifier ever becomes
    stable across experiments (e.g. a content fingerprint).
    """
    identity = _candidate_identity(candidate)
    salted = f"{scope}|{identity}"
    return (hashlib.sha256(salted.encode("utf-8")).hexdigest(), identity)


def candidate_display_order(
    candidates: list[dict],
    campaign_id: str | None = None,
    experiment: object = None,
) -> list[dict]:
    """Candidates in their deterministic, metric-independent display order."""
    scope = f"{campaign_id or ''}|{experiment if experiment is not None else ''}"
    return sorted(
        candidates, key=lambda candidate: _candidate_order_key(candidate, scope)
    )


def _candidate_steps(candidate: dict) -> str:
    timesteps = candidate.get("timesteps")
    return "-" if timesteps is None else f"{int(timesteps):,}"


def _steps_value(candidate: dict) -> int | None:
    value = candidate.get("timesteps")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _values_range(values: list[float]) -> str:
    """The run's own spread for one proxy: range and interquartile bounds.

    Issue #53: a proxy number in isolation reads as a score. Placing it inside
    the run's own spread lets it read as a location instead.
    """
    if not values:
        return "unavailable"
    ordered = sorted(values)
    if len(ordered) == 1:
        return f"{ordered[0]:g}"
    lower = _median(ordered[: len(ordered) // 2])
    upper = _median(ordered[(len(ordered) + 1) // 2 :])
    return f"{ordered[0]:g}-{ordered[-1]:g} (Q1-Q3 {lower:g}-{upper:g})"


def _quartile_label(value: float, values: list[float]) -> str:
    """Which quarter of the run's own spread a value occupies.

    Issue #53: the label is a location, so ties must share a position. A
    mid-rank fraction keeps a constant or tied distribution centred instead of
    pushing every member into the top quarter.
    """
    if not values:
        return "unavailable"
    less = sum(1 for other in values if other < value)
    equal = sum(1 for other in values if other == value)
    fraction = (less + 0.5 * equal) / len(values)
    if fraction <= 0.25:
        return "Q1"
    if fraction <= 0.5:
        return "Q2"
    if fraction <= 0.75:
        return "Q3"
    return "Q4"


def _proxy_shape(series: list[tuple[int, float]], position: int) -> str:
    """Describe a checkpoint's position on the proxy trajectory by step order.

    Issue #53: direction, turning point and local variability describe the run's
    behaviour around a checkpoint instead of its endpoint score. None of these
    values ranks one checkpoint above another.
    """
    value = series[position][1]
    previous = series[position - 1][1] if position > 0 else None
    following = series[position + 1][1] if position + 1 < len(series) else None
    if previous is None and following is None:
        return "single"
    if previous is not None and following is not None:
        if value > previous and value > following:
            return "local max"
        if value < previous and value < following:
            return "local min"
    if previous is not None:
        delta = value - previous
    else:
        delta = following - value
    if delta > 0:
        return "rising"
    if delta < 0:
        return "falling"
    return "flat"


def _local_spread(
    series: list[tuple[int, float]], position: int, window: int = 5
) -> float | None:
    """Variability of the signal across the last few raw records."""
    start = max(0, position - window + 1)
    recent = [value for _, value in series[start : position + 1]]
    if len(recent) < 2:
        return None
    return max(recent) - min(recent)


def _trajectory_ordered(candidates: list[dict]) -> list[dict]:
    """Candidates in training order, independent of the display permutation."""
    return sorted(
        candidates,
        key=lambda candidate: (
            _steps_value(candidate) is None,
            _steps_value(candidate) or 0,
            str(candidate.get("name", "")),
        ),
    )


_RAW_PROXY_KEYS = {
    "training_success": ("success_rate", "training_success"),
    "ep_rew_mean": ("ep_rew_mean",),
}


def _training_log_records(
    campaign_id: str | None, experiment: object
) -> list[dict[str, float]]:
    """Every preserved raw training snapshot for one experiment.

    The records are read from the campaign's training-log directory, which is
    the same preserved evidence the raw-log query exposes. Multiple attempts are
    read in attempt order.
    """
    if experiment is None:
        return []
    try:
        experiment_number = int(experiment)
    except (TypeError, ValueError):
        return []
    directory = RESEARCH_DIR / "training_logs"
    if campaign_id:
        directory = directory / campaign_id
    if not directory.is_dir():
        return []
    pattern = re.compile(rf"^experiment-{experiment_number}-attempt-(\d+)\.log$")
    logs: list[tuple[int, Path]] = []
    for log_path in directory.glob(f"experiment-{experiment_number}-attempt-*.log"):
        match = pattern.match(log_path.name)
        if match is not None:
            logs.append((int(match.group(1)), log_path))
    records: list[dict[str, float]] = []
    for _, log_path in sorted(logs):
        text = log_path.read_text(encoding="utf-8", errors="replace")
        records.extend(
            record
            for record in parse_training_records(text)
            if record.get("total_timesteps") is not None
        )
    return records


def _raw_training_series(
    campaign_id: str | None, experiment: object
) -> dict[str, list[tuple[float, float]]]:
    """Per-signal ``(timestep, value)`` series from the preserved raw records."""
    series: dict[str, list[tuple[float, float]]] = {key: [] for key in _RAW_PROXY_KEYS}
    for record in _training_log_records(campaign_id, experiment):
        timestep = record.get("total_timesteps")
        if timestep is None:
            continue
        for key, raw_keys in _RAW_PROXY_KEYS.items():
            for raw_key in raw_keys:
                if raw_key in record:
                    series[key].append((float(timestep), float(record[raw_key])))
                    break
    for points in series.values():
        points.sort(key=lambda item: item[0])
    return series


def _raw_context(
    series_points: list[tuple[float, float]], step: int | None, window: int = 5
) -> str | None:
    """Direction, variability and location at a checkpoint from raw records.

    Issue #53: these are derived from the preserved raw training records around
    the checkpoint, not from the checkpoint's endpoint proxies. ``None`` means
    the raw context does not exist, so the caller labels it honestly instead of
    implying it was consulted.
    """
    if not series_points or step is None:
        return None
    index: int | None = None
    for position, (timestep, _) in enumerate(series_points):
        if timestep <= step:
            index = position
        else:
            break
    if index is None:
        return None
    descriptors = [
        _quartile_label(series_points[index][1], [value for _, value in series_points]),
        _proxy_shape(series_points, index),
    ]
    spread = _local_spread(series_points, index, window)
    if spread is not None:
        descriptors.append(f"local spread {spread:g}")
    return ", ".join(descriptors)


def _candidate_discriminator_cells(
    candidates: list[dict], series: dict[str, list[tuple[float, float]]]
) -> dict[int, tuple[str, str, str]]:
    """Per-candidate non-proxy descriptors keyed by object identity.

    Issue #53: each row carries the checkpoint's position in the run and the
    location, direction and local variability of each training signal as
    recorded in the raw training log around that checkpoint. A signal whose raw
    context is missing is labelled unavailable rather than back-filled from the
    checkpoint endpoint proxies. The display order is never derived from these
    values.
    """
    ordered = _trajectory_ordered(candidates)
    steps = [value for value in (_steps_value(c) for c in ordered) if value is not None]
    longest = max(steps) if steps else None
    cells: dict[int, tuple[str, str, str]] = {}
    for candidate in ordered:
        steps_value = _steps_value(candidate)
        position = (
            "-"
            if steps_value is None or not longest
            else f"{round(100 * steps_value / longest)}%"
        )
        success_context = _raw_context(series.get("training_success", []), steps_value)
        reward_context = _raw_context(series.get("ep_rew_mean", []), steps_value)
        cells[id(candidate)] = (
            position,
            success_context or "raw log unavailable",
            reward_context or "raw log unavailable",
        )
    return cells


def _training_proxy_spread_lines(
    series: dict[str, list[tuple[float, float]]],
) -> list[str]:
    """Distributional context for each training signal in the run's own spread."""
    parts = []
    for key, label in (("training_success", "success"), ("ep_rew_mean", "reward")):
        values = [value for _, value in series.get(key, [])]
        if values:
            parts.append(f"{label} {_values_range(values)}")
    if not parts:
        return [
            (
                "- Raw training records are unavailable for this experiment, so "
                "recent direction, variability and trajectory location could not "
                "be derived."
            )
        ]
    return [
        "- Training-record spread across this run, so each checkpoint reads as a "
        "location rather than a score: " + "; ".join(parts) + "."
    ]


def _lineage_measurement_anchor_lines(
    training_parent_lineage: dict | None,
) -> list[str]:
    """Task-level measurements recorded for the frozen training parent.

    Issue #53: only the current candidates' actual frozen training parent is an
    ancestor. A fresh-initialization experiment has none, and unrelated working,
    best-known or retained roles must not be presented as ancestors.
    """
    if not isinstance(training_parent_lineage, dict):
        return []
    artifacts = training_parent_lineage.get("evaluation_artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return []
    references = ", ".join(_recorded_path(path) for path in artifacts)
    candidate = training_parent_lineage.get("candidate", "-")
    origin = training_parent_lineage.get("origin_experiment")
    origin_text = f" (origin experiment {origin})" if origin is not None else ""
    return [
        (
            "- Task-level measurement recorded for the frozen training parent "
            f"`{candidate}`{origin_text}: {references}."
        )
    ]


def _checkpoint_inventory_lines(
    candidates: list[dict],
    campaign_id: str | None = None,
    experiment: object = None,
    training_parent_lineage: dict | None = None,
) -> list[str]:
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
    measured = sum(bool(candidate.get("evaluations")) for candidate in candidates)
    label = "candidate" if len(candidates) == 1 else "candidates"
    lines = [
        (
            f"- Candidate inventory: {len(candidates)} {label} "
            f"({measured} measured, {len(candidates) - measured} unmeasured)."
        ),
        "",
        (
            "Training success and reward are training-time proxies, not task "
            "measurements: they indicate where the run was, not how good a policy "
            "is. The location and shape columns describe the trajectory around each "
            "checkpoint and are descriptive context, not a ranking. Selecting the "
            "highest proxy values is a weak strategy; prefer a set of candidates "
            "that spans the question you are asking (for example plateau entry, a "
            "local proxy peak, and the final checkpoint) so one measurement round "
            "can distinguish outcomes."
        ),
        "",
        (
            "Every candidate listed below loses its weights at closure unless the "
            "closure names it `working`, `best_known`, or retains it with an ID. A "
            "candidate without a role cannot later be extended, re-measured, or "
            "compared against, and cannot become a future `training_parent`. "
            "Retention has no budget and no preferred count. The `Weights if no "
            "role` column marks the candidates this applies to."
        ),
        "",
        (
            "| Candidate | Steps | Training success | Training reward | "
            "Measurements | Run position | Success location and shape | "
            "Reward location and shape | Weights if no role |"
        ),
        "|---|---:|---:|---:|---:|---:|---|---|---|",
    ]
    series = _raw_training_series(campaign_id, experiment)
    discriminators = _candidate_discriminator_cells(candidates, series)
    for candidate in candidate_display_order(candidates, campaign_id, experiment):
        position, success_context, reward_context = discriminators.get(
            id(candidate), ("-", "raw log unavailable", "raw log unavailable")
        )
        lines.append(
            f"| `{candidate.get('name', '-')}` | {_candidate_steps(candidate)} | "
            f"{_candidate_metric(candidate, 'training_success')} | "
            f"{_candidate_metric(candidate, 'ep_rew_mean')} | "
            f"{len(candidate.get('evaluations') or [])} | "
            f"{position} | {success_context} | {reward_context} | "
            "removed unless named |"
        )
    lines.append("")
    lines.extend(_training_proxy_spread_lines(series))
    lines.extend(_lineage_measurement_anchor_lines(training_parent_lineage))
    if common_parent is not None:
        lines.append(
            "- Inspect candidate identifiers, training metrics, and "
            f"artifacts in {_recorded_path((common_parent / 'inventory.json').as_posix())}."
        )
    else:
        lines.append(
            "- Inspect candidate identifiers, training metrics, and "
            f"artifacts in {_recorded_path('research/research_state.json')}."
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


def _selected_panels_lines(lineage: dict) -> list[str]:
    """The panels a lineage was selected on, with the non-independence caveat.

    Issue #57: a model chosen on a panel's episodes and later re-measured on the
    same episodes has an inflated score for that panel. Surfacing the selection
    exposure lets the Researcher see when a fresh disjoint panel is required. The
    recorded identity preserves both the instrument and the panel.
    """
    panels = lineage.get("selected_panels")
    if not isinstance(panels, list):
        return []
    rendered = []
    for panel in panels:
        identity = _selected_panel_identity(panel)
        if identity is not None:
            rendered.append(_panel_identity_label(identity))
    if not rendered:
        return []
    return [
        "  - Panels this lineage was selected on: "
        + ", ".join(rendered)
        + "; re-measuring on these episodes is not independent confirmation."
    ]


def _selected_panel_identity(panel: object) -> tuple | None:
    """Normalize a persisted selection-panel record to a panel identity."""
    if isinstance(panel, (list, tuple)) and len(panel) == 2:
        seed, episodes = panel
        if all(
            isinstance(value, int) and not isinstance(value, bool) for value in panel
        ):
            return ("research_evaluation", int(seed), int(episodes))
        return None
    if not isinstance(panel, dict):
        return None
    instrument = panel.get("instrument")
    if instrument == "task_reference":
        name = panel.get("panel")
        if not isinstance(name, str) or not name.strip():
            return None
        return (
            "task_reference",
            name,
            panel.get("panel_version"),
            panel.get("seed"),
            panel.get("episodes"),
        )
    if instrument == "research_evaluation":
        seed = panel.get("seed")
        episodes = panel.get("episodes")
        if isinstance(seed, bool) or not isinstance(seed, int):
            return None
        if isinstance(episodes, bool) or not isinstance(episodes, int):
            return None
        return ("research_evaluation", seed, episodes)
    return None


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
        + (
            _stable_json(parameters) if isinstance(parameters, dict) else "not recorded"
        ),
        f"  - Recorded evaluation artifacts: {evidence}",
        f"  - Researcher reason: {_recorded_value(lineage.get('reason'))}",
        *_selected_panels_lines(lineage),
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
        (
            "These are the only models the Runner can verify and restore as a "
            "parent. A new identifier is created only by a closure that names a "
            "candidate `working` or `best_known`, or retains it with an ID; the "
            "complete inference artifact, matching fingerprint, scientific commit "
            "and effective parameters are recorded at that moment. Candidates "
            "without such a role have their weights removed at closure and cannot "
            "become training parents later."
        ),
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
            "- Researcher-owned source: current worktree",
            f"- Effective parameters: {_stable_json(current_params)}",
            "- Parameter differences from `working`: "
            + _parameter_differences(current_params, working),
            "- Parameter differences from `best_known`: "
            + _parameter_differences(current_params, best_known),
            "",
            "### Current experiment candidate inventory",
            "",
        ]
    )
    candidates = (
        state.get("pending_analysis", {}).get("candidates", [])
        if isinstance(state.get("pending_analysis"), dict)
        else []
    )
    if candidates:
        pending_analysis = state.get("pending_analysis") or {}
        result = pending_analysis.get("result")
        training_parent_lineage = pending_analysis.get("training_parent_lineage") or (
            result.get("training_parent_lineage") if isinstance(result, dict) else None
        )
        lines.extend(
            _checkpoint_inventory_lines(
                candidates,
                campaign_id=state.get("campaign", {}).get("id"),
                experiment=pending_analysis.get("experiment"),
                training_parent_lineage=training_parent_lineage,
            )
        )
    else:
        lines.append("No current experiment candidates are recorded.")
    return lines


def _v4_evidence_lines(
    state: dict, pending: dict | None, results: list[dict]
) -> list[str]:
    research_evaluations: list[dict] = []
    task_reference_evaluations: list[dict] = []
    fingerprints: set[str] = set()
    artifacts: set[str] = set()
    seen_research: set[str] = set()
    seen_task_reference: set[str] = set()
    sources = _evidence_records(state, results, pending)
    for source in sources:
        direct = _measurement_entries(source, "research_evaluation")
        if not direct:
            direct = [
                {"candidate": candidate.get("name"), **evaluation}
                for candidate in source.get("candidates") or []
                for evaluation in candidate.get("evaluations") or []
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
            identity = str(
                metrics.get("evaluation_artifact")
                or _stable_json(
                    {
                        key: normalized.get(key)
                        for key in (
                            "candidate",
                            "instrument",
                            "episodes",
                            "seed",
                            "evaluation_semantics",
                            "model_fingerprint",
                        )
                    }
                )
            )
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
        for evaluation in _measurement_entries(source, "task_reference"):
            identity = str(
                evaluation.get("evaluation_artifact")
                or _stable_json(
                    {
                        key: evaluation.get(key)
                        for key in (
                            "candidate",
                            "panel",
                            "panel_version",
                            "episodes",
                            "seed",
                            "model_fingerprint",
                        )
                    }
                )
            )
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


def _v4_phase_section(
    state: dict,
    pending: dict | None,
    latest: dict | None,
    latest_experiment,
    terminal,
    campaign_id: str | None,
    campaign_base_commit: str | None,
) -> list[str]:
    """The campaign header: where the campaign is and what it expects next."""
    phase = (
        "post-training analysis"
        if isinstance(pending, dict)
        else "experiment preparation"
    )
    if state.get("pending_final_benchmark") is not None:
        phase = "official assessment"
    if terminal:
        phase = "terminal official assessment"
    conclusion_only = bool(state.get("preparation_conclusion_only")) and not (
        terminal or isinstance(pending, dict)
    )
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
            else (
                "only a `campaign_conclusion` in `research/proposal.json`; the "
                "experiment budget is exhausted"
                if conclusion_only
                else (
                    "`research/proposal.json` or a saved-lineage "
                    "`research/evaluation_request.json`"
                )
            )
        ),
    ]
    if terminal:
        lines.append(f"- Terminal campaign status: {terminal}")
    return lines


def _v4_lineage_section(state: dict, current_params: dict) -> list[str]:
    """Lineage facts and the current experiment candidate inventory."""
    lines = ["", *_current_lineages_and_recipes_lines(state, current_params)]
    lines.extend(["", "## Working lineage", ""])
    lines.append(
        "- See `working` under **Current lineages and scientific recipes**."
        if state.get("working_lineage")
        else "- Working: unset"
    )
    return lines


def _precedent_prose_inline(pending: dict | None) -> bool:
    """Whether a past decision's rationale is rendered inline or retrospectively.

    Issue #54 (correcting #43): the brief must treat a past decision's rationale
    and its outcome symmetrically. #43 hid the round-level `reason` and the
    per-candidate `selection` prose while preparing a request, because the inline
    `Reason:` and `Selection:` field names read as a form to copy, but it left the
    campaign experiment index's closure pattern unconditional. The Researcher was
    then shown the outcome many times over with no reasoning to weigh against it.

    The policy is to retain the rationale and present it deliberately
    de-templated during preparation - a labelled retrospective note, never the
    inline field names - while the experiment index states that past closure
    choices are not defaults. Both renderers consult this one predicate so the
    two policies cannot drift apart again.
    """
    return isinstance(pending, dict)


def _fingerprint_qualified_label(label: str, fingerprint: str) -> str:
    """A surfaced candidate label with the aggregate index's model suffix.

    ``_aggregate_task_evidence_lines`` already disambiguates a reused candidate
    name by appending ``(model <fingerprint12>)``; the rationale quotes repeat
    the same bare name, so they append the identical suffix for the measured
    model the name resolves to. When no fingerprint is recorded the label is
    left exactly as before.
    """
    return f"{label} (model {fingerprint[:12]})" if fingerprint else label


def _experiment_rationale(result: dict) -> list[str]:
    """De-templated rationale recorded by one experiment's measurement rounds.

    Issue #54: an indexed closure outcome must be shown together with the
    rationale that answered its question. This renders the same content as the
    measurement-rounds section without the inline ``Reason:`` / ``Selection:``
    field names, so it cannot be read as a form the next request should fill in.
    """
    items: list[str] = []
    rounds = result.get("evaluation_rounds")
    if not isinstance(rounds, list):
        return items
    for record in rounds:
        if not isinstance(record, dict):
            continue
        if record.get("reason"):
            items.extend(
                _indented_label_block(
                    "Round rationale", str(record["reason"]), 400, RESULTS_REFERENCE
                )
            )
        round_results = record.get("results")
        if not isinstance(round_results, dict):
            continue
        for key in ("research_evaluations", "task_reference_evaluations"):
            for item in round_results.get(key) or []:
                if not isinstance(item, dict) or not item.get("selection"):
                    continue
                label = _fingerprint_qualified_label(
                    str(item.get("candidate", "-")), _entry_fingerprint(item)
                )
                items.extend(
                    _indented_label_block(
                        f"Choice rationale for `{label}`",
                        str(item["selection"]),
                        600,
                        RESULTS_REFERENCE,
                    )
                )
    return items


def _assessment_with_confidence(result: dict) -> str:
    """Render the recorded hypothesis assessment beside its prediction confidence.

    Issue #56: a prediction may be recorded as weakly held, so a contradicted
    weak prediction is not read as a refuted strong one.
    """
    assessment = result.get("hypothesis_assessment")
    rendered = (
        assessment.strip()
        if isinstance(assessment, str) and assessment.strip()
        else "unavailable"
    )
    reasoning = result.get("reasoning")
    confidence = reasoning.get("confidence") if isinstance(reasoning, dict) else None
    if isinstance(confidence, str) and confidence.strip():
        return f"{rendered} (prediction confidence: {confidence.strip()})"
    return rendered


def _v4_experiment_index_section(
    results: list[dict], pending: dict | None = None
) -> list[str]:
    """One row per completed experiment, newest first.

    Issue #54: the section states that a recorded closure answered that
    experiment's question, so it is not a default for the next one. During
    preparation every recorded closure is shown with its de-templated rationale,
    and a closure whose rationale is not reproduced here is withheld, so outcome
    and rationale stay symmetric across the whole index.
    """
    preparing = not _precedent_prose_inline(pending)
    preamble = (
        "Each row records what one experiment did and concluded. Past closure "
        "choices answered the question that experiment asked; they are not a "
        "default for the next one."
    )
    if preparing:
        preamble += (
            " Each recorded closure is shown with the de-templated rationale "
            "that answered its question; a closure whose rationale is not "
            "reproduced here is withheld."
        )
    lines = [
        "",
        "## Campaign experiment index",
        "",
        preamble,
        "",
        "| # | Operation / family | Parent | Intervention | Measurements | Hypothesis assessment | Final decisions | Detail |",
        "|---:|---|---|---|---|---|---|---|",
    ]
    rationale_notes: list[str] = []
    for result in sorted(
        results, key=lambda item: int(item.get("index", 0)), reverse=True
    ):
        checkpoints = compact_measurement_summary(result)
        closure = result.get("closure_decision") or {}
        rationale = _experiment_rationale(result) if preparing else []
        if preparing and closure and not rationale:
            decisions = (
                "closure withheld during preparation; its rationale is not "
                "reproduced here"
            )
        else:
            decisions = (
                f"working {closure.get('continue_from', 'not recorded')}; "
                f"best known {(closure.get('best_known') or {}).get('candidate', 'not recorded')}; "
                f"code {(closure.get('code') or {}).get('action', 'not recorded')}"
            )
        operation = (
            operation_description(result)
            if extends_lineage(result)
            else result.get("kind", "-")
        )
        intervention = _change_details(result)
        if result.get("recipe_basis"):
            intervention = f"{_recipe_basis(result)}; {intervention}"
        lines.append(
            f"| {result.get('index', '-')} | {_table_cell(operation)} / {result.get('family', '-')} | "
            f"{result.get('training_parent', '-')} | {_table_cell(_compact(intervention, 100, reference=RESULTS_REFERENCE))} | "
            f"{_table_cell(_compact(checkpoints, 140, reference=RESULTS_REFERENCE))} | "
            f"{_table_cell(_assessment_with_confidence(result))} | "
            f"{decisions} | "
            f"{_postmortem_reference(result.get('postmortem'))} |"
        )
        if rationale:
            rationale_notes.extend(
                ["", f"**Experiment {result.get('index', '-')}**", *rationale]
            )
    if not results:
        lines.append("| - | - | - | - | - | - | - | - |")
    if rationale_notes:
        lines.extend(
            [
                "",
                (
                    "Recorded rationale for past decisions; each answered a "
                    "question that is not yours. It is retained for audit, not as "
                    "a template to copy:"
                ),
                *rationale_notes,
            ]
        )
    return lines


def _lineage_names_by_fingerprint(state: dict) -> dict[str, list[str]]:
    """Every saved-lineage identifier that currently resolves to each artifact."""
    names: dict[str, list[str]] = {}
    for identifier in ("working", "best_known"):
        lineage = state.get(f"{identifier}_lineage")
        if isinstance(lineage, dict) and lineage.get("fingerprint"):
            names.setdefault(str(lineage["fingerprint"]), []).append(identifier)
    for lineage in state.get("retained_lineages") or []:
        if isinstance(lineage, dict) and lineage.get("fingerprint"):
            names.setdefault(str(lineage["fingerprint"]), []).append(
                str(lineage.get("id", "retained"))
            )
    return names


def _aggregate_task_evidence(records: list[dict]) -> list[dict]:
    """Each measured model's research-panel results summed over distinct panels.

    Every panel result is already shown individually, one measurement at a time.
    A model measured across several disjoint panels therefore had no campaign-
    level total anywhere in the brief, and assembling one by hand was left to the
    Researcher at the moment it decided whether to stop.

    Only distinct panel identities are summed, so a reused panel contributes its
    episodes once and cannot inflate a model's aggregate. The aggregate is a
    count of measured episodes and successes: it carries no threshold, no
    comparison and no readiness verdict, because the objective belongs to
    ``research/scenario.md`` and the verdict to the official benchmark alone.
    """
    models: dict[str, dict] = {}
    for record in records:
        for entry in _measurement_entries(record, "research_evaluation"):
            metrics = entry.get("metrics") or {}
            merged = {**metrics, **entry}
            fingerprint = _entry_fingerprint(entry)
            successes = merged.get("successes", metrics.get("successes"))
            episodes = merged.get("episodes")
            seed = merged.get("seed")
            if not fingerprint or not isinstance(successes, int):
                continue
            if not isinstance(episodes, int) or not isinstance(seed, int):
                continue
            panel = (str(merged.get("evaluation_semantics", "")), seed, episodes)
            model = models.setdefault(
                fingerprint,
                {"fingerprint": fingerprint, "panels": {}, "labels": []},
            )
            model["panels"].setdefault(panel, successes)
            label = str(merged.get("candidate", "")).strip()
            if label and label not in model["labels"]:
                model["labels"].append(label)
    summaries = []
    for model in models.values():
        episodes = sum(panel[2] for panel in model["panels"])
        successes = sum(model["panels"].values())
        if episodes <= 0:
            continue
        summaries.append(
            {
                "fingerprint": model["fingerprint"],
                "labels": model["labels"],
                "panels": len(model["panels"]),
                "episodes": episodes,
                "successes": successes,
                "seeds": sorted(panel[1] for panel in model["panels"]),
            }
        )
    return sorted(summaries, key=lambda item: -item["episodes"])


def _aggregate_task_evidence_lines(state: dict, records: list[dict]) -> list[str]:
    """The per-model aggregate, stated as measured counts without a verdict."""
    summaries = _aggregate_task_evidence(records)
    if not summaries:
        return []
    names = _lineage_names_by_fingerprint(state)
    lines = [
        "",
        (
            "Aggregate research-panel evidence per measured model, summed over "
            "the distinct panels that measured it. A reused panel counts once. "
            "These are measured development counts, not an official result and "
            "not a readiness indicator; the objective they must be judged "
            "against is defined in `research/scenario.md` and only the official "
            "benchmark reports the official result:"
        ),
        "",
    ]
    for summary in summaries:
        fingerprint = summary["fingerprint"]
        identifiers = names.get(fingerprint) or []
        labels = identifiers or summary["labels"] or ["unnamed model"]
        percent = 100.0 * summary["successes"] / summary["episodes"]
        seeds = ", ".join(str(seed) for seed in summary["seeds"])
        panels = summary["panels"]
        lines.append(
            f"- {', '.join(labels)} (model {fingerprint[:12]}): "
            f"{summary['successes']}/{summary['episodes']} successes "
            f"({percent:.1f}%) over {panels} distinct "
            f"{'panel' if panels == 1 else 'panels'} "
            f"(seed{'' if panels == 1 else 's'} {seeds})."
        )
    return lines


def _v4_evidence_section(
    state: dict, pending: dict | None, results: list[dict]
) -> list[str]:
    """Aggregate fingerprint-bound development evidence."""
    return [
        "",
        "## Development evidence index",
        "",
        *_v4_evidence_lines(state, pending, results),
        *_aggregate_task_evidence_lines(
            state, _evidence_records(state, results, pending)
        ),
    ]


def _v4_synthesis_section(postmortems: str, campaign_id: str | None) -> list[str]:
    """The Researcher-authored, revisable scientific synthesis."""
    strategy = scientific_strategy_section(postmortems, campaign_id)
    lines = [
        "",
        "## Provisional scientific synthesis",
        "",
        (
            "Researcher-authored interpretation of the campaign evidence. "
            "It is memory for reassessment, not a prescribed next direction:"
        ),
        "",
    ]
    lines.append(
        "\n".join(strategy.splitlines()[1:]).strip()
        if strategy
        else "No scientific strategy recorded for this campaign yet."
    )
    return lines


def _v4_repeated_operations_section(results: list[dict]) -> list[str]:
    """Replication groups, stated as facts rather than a next direction."""
    lines = ["", "## Repeated operations", ""]
    groups = _replication_groups(results)
    if groups:
        for original, entries in groups:
            experiments = ", ".join(str(entry.get("index", "-")) for entry in entries)
            lines.append(
                f"- Replication group `{original}`: {len(entries)} runs; "
                f"experiments {experiments}."
            )
    else:
        lines.append("No repeated operations recorded.")
    return lines


def _v4_intervention_surfaces_section(results: list[dict]) -> list[str]:
    """Where the campaign has intervened, in path order, without ranking."""
    lines = ["", "## Intervention surfaces", ""]
    surfaces, parameter_only, unchanged = _intervention_surfaces(results)
    if surfaces:
        lines.append(
            "Experiments that changed each researcher-owned source, including "
            "sources never changed. Listed in path order; frequency of past "
            "change carries no information about where the next intervention "
            "should be. This is a record of where the campaign has intervened, "
            "not a suggestion about where to intervene next:"
        )
        lines.append("")
        changed = [(source, count) for source, count in surfaces if count]
        never_changed = [source for source, count in surfaces if not count]
        lines.append("### Changed in this campaign")
        lines.append("")
        if changed:
            for source, count in changed:
                noun = "experiment" if count == 1 else "experiments"
                lines.append(f"- `{source}` — changed in {count} {noun}")
        else:
            lines.append("- None.")
        lines.append("")
        lines.append("### Not yet changed")
        lines.append("")
        if never_changed:
            for source in never_changed:
                lines.append(f"- `{source}`")
        else:
            lines.append("- None.")
        lines.append("")
        lines.append(
            f"- Experiments with no researcher-owned source change: "
            f"{parameter_only} parameter-only, {unchanged} unchanged."
        )
    else:
        lines.append("No researcher-owned sources found.")
    return lines


def _v4_reusable_lineages_section(state: dict) -> list[str]:
    """Retained alternative lineages available as training parents."""
    lines = ["", "## Reusable lineages", ""]
    retained = state.get("retained_lineages") or []
    if retained:
        for lineage in retained:
            lines.append(
                f"- See `{lineage.get('id', '-')}` under "
                "**Current lineages and scientific recipes**."
            )
    else:
        lines.append("No retained alternatives.")
    return lines


def _v4_best_known_section(state: dict) -> list[str]:
    """Pointer to the best-known lineage among the current lineages."""
    lines = ["", "## Best-known model", ""]
    best_known = state.get("best_known_lineage")
    lines.append(
        "- See `best_known` under **Current lineages and scientific recipes**."
        if best_known
        else "- Best known: unset"
    )
    return lines


def _v4_terminal_assessment_section(state: dict) -> list[str]:
    """The irreversible request, stated with the model it will freeze.

    Issue #59: the protocol frames the terminal assessment only as a risk, so a
    pending final-benchmark request must name the frozen best-known lineage and
    the Researcher's terminal reason. The decision becomes a confirmed object
    instead of a recall; the mechanism itself is unchanged.
    """
    pending = state.get("pending_final_benchmark")
    if not isinstance(pending, dict):
        return []
    lineage = pending.get("best_known")
    if not isinstance(lineage, dict):
        lineage = state.get("best_known_lineage")
    if not isinstance(lineage, dict):
        return []
    expectation = pending.get("terminal_expectation")
    if not isinstance(expectation, dict):
        conclusion = state.get("campaign_conclusion")
        if isinstance(conclusion, dict):
            expectation = conclusion.get("terminal_expectation")
    if not isinstance(expectation, dict):
        expectation = {}
    lines = [
        "",
        "## Pending terminal assessment",
        "",
        (
            "A request for the official assessment is pending. The campaign ends "
            "after either verdict, `goal_reached` or `goal_not_reached`, and the "
            "decision is irreversible. This is the frozen model the verdict will "
            "describe:"
        ),
    ]
    lines.extend(_authoritative_lineage_lines("best_known", lineage))
    lines.append(
        "  - Expected verdict: "
        f"{_recorded_value(expectation.get('expected_verdict'))}"
    )
    lines.append(f"  - Terminal reason: {_recorded_value(expectation.get('reason'))}")
    lines.extend(
        [
            "",
            (
                "Both verdicts are legitimate campaign outcomes; "
                "`goal_not_reached` on a well-evidenced submission is not a "
                "failure of the research process, and the campaign's scientific "
                "record survives the verdict intact. There is no reversal and no "
                "second verdict."
            ),
        ]
    )
    return lines


def _cost_records(state: dict, results: list[dict], pending: dict | None) -> list[dict]:
    """Experiment records once each, preferring the full pending result."""
    records = [record for record in results if isinstance(record, dict)]
    indices = {int(record.get("index", -1)) for record in records}
    if isinstance(pending, dict):
        result = pending.get("result")
        if isinstance(result, dict) and int(result.get("index", -1)) not in indices:
            records.append(result)
    return records


def _preparation_ledger_record(
    state: dict, experiment_records: list[dict]
) -> dict | None:
    """The live preparation ledger as an evidence record, when it has no row yet.

    A preparation round measures saved lineages before the upcoming experiment
    exists, so its episodes live in ``preparation_measurement`` until that
    experiment closes and persists them. Reading only the durable rows therefore
    hid every preparation measurement of an experiment that never ran - the case
    of a campaign concluded from preparation - and understated both the executed
    work and the panels already consumed.
    """
    ledger = preparation_ledger(state)
    if ledger is None:
        return None
    experiment = int(ledger.get("experiment", -1))
    if experiment in {
        int(record.get("index", -1))
        for record in experiment_records
        if isinstance(record, dict)
    }:
        return None
    entries = [
        entry
        for entry in ledger.get("partial_evaluations") or []
        if isinstance(entry, dict)
    ]
    reference = [
        entry
        for entry in ledger.get("partial_task_reference_evaluations") or []
        if isinstance(entry, dict)
    ]
    rounds = [item for item in ledger.get("rounds") or [] if isinstance(item, dict)]
    if not entries and not reference and not rounds:
        return None
    return {
        "index": experiment,
        "preparation_evaluations": entries,
        "preparation_task_reference_evaluations": reference,
        "preparation_evaluation_rounds": rounds,
    }


def _evidence_records(
    state: dict, results: list[dict], pending: dict | None
) -> list[dict]:
    """Every record that carries measurements, experiments and preparation alike."""
    records = _cost_records(state, results, pending)
    ledger_record = _preparation_ledger_record(state, records)
    return [*records, ledger_record] if ledger_record else list(records)


def _fresh_restart_line(records: list[dict]) -> str:
    """One factual count of how much of the campaign left the baseline recipe.

    Every campaign opens with an automatic fresh baseline, so that experiment is
    excluded: what this counts is the discretionary fresh restarts, the
    experiments that trained a recipe from zero instead of continuing an
    existing lineage.

    It is reported because it is the only campaign-level quantity that separated
    the campaigns in this repository's history from each other, and it was
    invisible in the brief. It is a count of what happened, not a target: no
    value is preferred, fresh initialization is not better than transfer, and
    nothing in the protocol reads this line.

    This function and its single call site are the whole mechanism; deleting
    both removes it without affecting anything else.
    """
    fresh = sorted(
        int(record["index"])
        for record in records
        if str(record.get("initialization")) == "fresh"
        and int(record.get("index", 0)) > 1
    )
    return (
        "- Fresh restarts after the baseline: "
        + (", ".join(f"experiment {index}" for index in fresh) if fresh else "none")
        + f" ({len(fresh)} of {len(records)} experiments)."
    )


def _v4_activity_record_section(
    state: dict, results: list[dict], pending: dict | None
) -> list[str]:
    """Factual campaign activity in non-overlapping units.

    Issue #34: surfaces training and evaluation work without implying a target,
    a preferred allocation, or an automatic stopping decision.
    Issue #46: describes what was executed separately from the evidence coverage
    it produced, and carries no running total of consumed resources.

    Preparation rounds are executed work: they are counted with the experiments'
    own rounds so the record describes every measurement the campaign ran, not
    only the ones a training experiment persisted.
    """
    records = _cost_records(state, results, pending)
    evidence_records = _evidence_records(state, results, pending)
    replications = sorted(
        int(record["index"])
        for record in records
        if str(record.get("kind")) == "replication"
    )
    rounds: list[dict] = []
    for record in evidence_records:
        for key in ("preparation_evaluation_rounds", "evaluation_rounds"):
            rounds.extend(
                item for item in record.get(key) or [] if isinstance(item, dict)
            )
    instrument_executions = {"research_evaluation": 0, "task_reference": 0}
    for record in evidence_records:
        for instrument, keys in MEASUREMENT_LEDGER_KEYS.items():
            instrument_executions[instrument] += sum(
                isinstance(item, dict) for key in keys for item in record.get(key) or []
            )
    coverage = campaign_coverage(evidence_records)
    research_coverage = coverage["research_evaluation"]
    reference_coverage = coverage["task_reference"]
    intervals = _consumed_research_intervals(evidence_records)
    return [
        "",
        "## Campaign activity record",
        "",
        (
            "What this campaign has executed so far. These counts exist so "
            "measurements can be located and compared. They are descriptive "
            "records only: no value is a target or a limit, and no value is "
            "preferred over another."
        ),
        "",
        "### Executed so far",
        "",
        f"- Training experiments: {len(records)}.",
        (
            "- Replication experiments recorded: "
            + (
                ", ".join(str(index) for index in replications)
                if replications
                else "none"
            )
            + "."
        ),
        f"- Evaluation rounds: {len(rounds)}.",
        _fresh_restart_line(records),
        (
            f"- Instrument executions: "
            f"{instrument_executions['research_evaluation']} research_evaluation, "
            f"{instrument_executions['task_reference']} task_reference."
        ),
        "",
        "### Evidence coverage",
        "",
        (
            f"- research_evaluation coverage: "
            f"{research_coverage['distinct_episodes']} distinct episodes; "
            f"{research_coverage['episode_executions']} episode executions; "
            f"{research_coverage['repeated_episodes']} repeated."
        ),
        (
            f"- task_reference coverage: "
            f"{reference_coverage['distinct_episodes']} distinct episodes; "
            f"{reference_coverage['episode_executions']} episode executions; "
            f"{reference_coverage['repeated_episodes']} repeated."
        ),
        (
            "- research_evaluation intervals consumed: "
            + (", ".join(intervals) if intervals else "none")
            + "."
        ),
    ]


def _round_entry_status(item: dict) -> str:
    """A compact status marker for a round measurement entry."""
    return f" ({item.get('status', 'executed')})"


def _episode_interval(entry: dict) -> str:
    """The evaluated episode interval of a research evaluation, e.g. 1208-1407."""
    seed = entry.get("seed")
    episodes = entry.get("episodes")
    if (
        isinstance(seed, int)
        and not isinstance(seed, bool)
        and isinstance(episodes, int)
        and not isinstance(episodes, bool)
        and episodes > 0
    ):
        return f"episodes {seed}–{seed + episodes - 1}"
    return "episodes unknown"


def _research_panel_of(entry: dict) -> tuple[int, int] | None:
    """The ``(seed, episodes)`` panel of a recorded research measurement."""
    seed = entry.get("seed")
    episodes = entry.get("episodes")
    if isinstance(seed, bool) or not isinstance(seed, int):
        return None
    if isinstance(episodes, bool) or not isinstance(episodes, int):
        return None
    return seed, episodes


def _record_research_panels(record: dict) -> list[tuple[int, int]]:
    """The research-evaluation panels a durable or pending record consumed.

    Every persisted ledger counts: a preparation round consumes its interval as
    definitively as an executed request, so omitting it let the brief present an
    already-measured interval as still available.
    """
    panels: list[tuple[int, int]] = []
    ordered_keys = (
        "preparation_evaluations",
        "requested_evaluations",
        "partial_evaluations",
    )
    for key in ordered_keys:
        for entry in record.get(key) or []:
            if not isinstance(entry, dict):
                continue
            if entry.get("instrument", "research_evaluation") != "research_evaluation":
                continue
            metrics = entry.get("metrics") or {}
            panel = _research_panel_of({**metrics, **entry})
            if panel is not None:
                panels.append(panel)
    return panels


def _entry_fingerprint(entry: dict) -> str:
    """The immutable model fingerprint of a recorded measurement, if present."""
    metrics = entry.get("metrics") if isinstance(entry.get("metrics"), dict) else {}
    value = entry.get("model_fingerprint") or metrics.get("model_fingerprint")
    return "" if value is None else str(value)


def _measurement_entries(record: dict, instrument: str):
    """Every persisted measurement entry of one instrument in a record.

    Issue #57: the durable record separates the executed request from the
    partial and preparation ledgers; all of them are prior panel uses.
    """
    if instrument == "task_reference":
        keys = (
            "task_reference_evaluations",
            "partial_task_reference_evaluations",
            "preparation_task_reference_evaluations",
        )
    else:
        keys = (
            "requested_evaluations",
            "partial_evaluations",
            "preparation_evaluations",
        )
    for key in keys:
        for entry in record.get(key) or []:
            if isinstance(entry, dict):
                yield entry


def _panel_identity(entry: dict, instrument: str) -> tuple | None:
    """The immutable identity of the panel a measurement ran on.

    Issue #57: reuse must be recognized by panel identity, never by a mutable
    candidate or role label, and both instruments are covered by the same rule.
    """
    if instrument == "task_reference":
        panel = entry.get("panel")
        if not isinstance(panel, str) or not panel.strip():
            return None
        return (
            "task_reference",
            panel,
            entry.get("panel_version"),
            entry.get("seed"),
            entry.get("episodes"),
        )
    seed = entry.get("seed")
    episodes = entry.get("episodes")
    if isinstance(seed, bool) or not isinstance(seed, int):
        return None
    if isinstance(episodes, bool) or not isinstance(episodes, int):
        return None
    return ("research_evaluation", seed, episodes)


def _panel_identity_label(identity: tuple) -> str:
    if identity[0] == "task_reference":
        return f"panel `{identity[1]}`"
    _, seed, episodes = identity
    if episodes > 0:
        return f"episodes {seed}–{seed + episodes - 1}"
    return f"episode {seed}"


def _record_panel_uses(record: dict) -> list[tuple[tuple, str]]:
    """``(panel identity, model fingerprint)`` for every prior measurement."""
    uses: list[tuple[tuple, str]] = []
    for instrument in ("research_evaluation", "task_reference"):
        for entry in _measurement_entries(record, instrument):
            if entry.get("instrument", instrument) != instrument:
                continue
            metrics = (
                entry.get("metrics") if isinstance(entry.get("metrics"), dict) else {}
            )
            merged = {**metrics, **entry}
            identity = _panel_identity(merged, instrument)
            if identity is None:
                continue
            uses.append((identity, _entry_fingerprint(merged)))
    return uses


def _record_label_fingerprints(record: dict) -> dict[str, str]:
    """Map each candidate or role label in a record to its model fingerprint.

    Issue #57: a closure names the selected model by a mutable label, so the
    label must be resolved to the immutable fingerprint recorded with the
    measurements of that same experiment before it can be associated with a
    prior panel use.
    """
    mapping: dict[str, str] = {}
    for instrument in ("research_evaluation", "task_reference"):
        for entry in _measurement_entries(record, instrument):
            metrics = (
                entry.get("metrics") if isinstance(entry.get("metrics"), dict) else {}
            )
            merged = {**metrics, **entry}
            label = merged.get("candidate")
            fingerprint = _entry_fingerprint(merged)
            if label is not None and fingerprint:
                mapping.setdefault(str(label), fingerprint)
    for candidate in record.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        name = candidate.get("name")
        for evaluation in candidate.get("evaluations") or []:
            if not isinstance(evaluation, dict):
                continue
            fingerprint = _entry_fingerprint(evaluation)
            if name is not None and fingerprint:
                mapping.setdefault(str(name), fingerprint)
    return mapping


def _closure_selected_labels(record: dict) -> set[str]:
    """The candidate or role labels a recorded closure chose for a lineage role."""
    closure = record.get("closure_decision") or {}
    selected: set[str] = set()
    working = closure.get("continue_from")
    if working is not None:
        selected.add(str(working))
    best = closure.get("best_known")
    if isinstance(best, dict) and best.get("candidate") is not None:
        selected.add(str(best["candidate"]))
    for retained in closure.get("retain") or []:
        if isinstance(retained, dict) and retained.get("candidate") is not None:
            selected.add(str(retained["candidate"]))
    return selected


def _closure_selected_fingerprints(record: dict) -> set[str]:
    """The immutable fingerprints a recorded closure selected for a lineage role."""
    mapping = _record_label_fingerprints(record)
    return {
        mapping[label] for label in _closure_selected_labels(record) if label in mapping
    }


def _reuse_context(
    prior_uses: dict[tuple, int],
    prior_selected: dict[tuple, dict[str, int]],
    identity: tuple | None,
    fingerprint: str,
) -> tuple[str, str]:
    """A panel marker and non-independence qualifier for one rendered result."""
    if identity is None:
        return "", ""
    uses = prior_uses.get(identity, 0)
    if not uses:
        return " (new panel)", ""
    location = "this panel" if identity[0] == "task_reference" else "these episodes"
    suffix = "" if uses == 1 else "s"
    history = [f"{uses} prior measurement{suffix} on {location}"]
    selected = (
        prior_selected.get(identity, {}).get(fingerprint, 0) if fingerprint else 0
    )
    if selected:
        history.append(f"{selected} preceded a closure that selected this lineage")
    qualifier = (
        " Reused panel: comparable to earlier results on the same episodes, "
        "not independent confirmation."
    )
    return " (reused panel: " + "; ".join(history) + ")", qualifier


def _consumed_research_intervals(records: list[dict]) -> list[str]:
    """Every distinct research-evaluation interval already consumed, in first-use order."""
    ordered: list[tuple[int, int]] = []
    known: set[tuple[int, int]] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        for panel in _record_research_panels(record):
            if panel not in known:
                known.add(panel)
                ordered.append(panel)
    return [
        f"{seed}–{seed + episodes - 1}" if episodes > 0 else f"{seed}"
        for seed, episodes in ordered
    ]


def _v4_measurement_rounds_section(
    state: dict, results: list[dict], pending: dict | None
) -> list[str]:
    """Completed and accepted measurement rounds in request order.

    Issue #39: the durable record keeps each request's question, selections and
    artifact references so the progression of scientific questions stays
    auditable after closure instead of being reconstructed from timestamps.

    Issue #57: a reused panel is reported with its reuse history - how many prior
    measurements consumed this exact interval and how many of them preceded a
    closure that selected the measured lineage - and carries an explicit
    non-independence qualifier. A panel is counted as reused only when it was
    consumed before the current round (by an earlier experiment or an earlier
    round). Candidates that share one panel within a round share the same history;
    they are not treated as successive reuse.
    """
    preparation_source = False
    if isinstance(pending, dict):
        # Analysis keeps the experiment's own rounds after the preparation
        # rounds that informed its parent choice, all under one experiment.
        source = {
            **pending,
            "evaluation_rounds": [
                *(pending.get("preparation_evaluation_rounds") or []),
                *(pending.get("evaluation_rounds") or []),
            ],
        }
    else:
        ledger = preparation_ledger(state)
        if ledger is not None and int(ledger.get("experiment", -1)) != (
            upcoming_experiment_index(state)
        ):
            ledger = None
        if ledger is not None:
            # The upcoming experiment's preparation rounds belong to it, never
            # to the previous completed experiment.
            source = {
                "experiment": int(ledger.get("experiment", 0)),
                "evaluation_rounds": list(ledger.get("rounds") or []),
            }
            preparation_source = True
        else:
            source = results[-1] if results else None
    if not isinstance(source, dict):
        return []
    rounds = source.get("evaluation_rounds")
    if not isinstance(rounds, list) or not rounds:
        return []
    current_index = int(source.get("experiment") or source.get("index") or 0)
    prior_uses: dict[tuple, int] = {}
    prior_selected: dict[tuple, dict[str, int]] = {}
    for record in results:
        if not isinstance(record, dict):
            continue
        if int(record.get("index", -1)) == current_index:
            continue
        selected_fingerprints = _closure_selected_fingerprints(record)
        for identity, fingerprint in _record_panel_uses(record):
            prior_uses[identity] = prior_uses.get(identity, 0) + 1
            if fingerprint and fingerprint in selected_fingerprints:
                by_model = prior_selected.setdefault(identity, {})
                by_model[fingerprint] = by_model.get(fingerprint, 0) + 1
    # Issue #54 (correcting #43): the rationale is retained in both phases. While
    # preparing a request it is rendered de-templated at the foot of the round
    # instead of inline, so it stays auditable without reading as a form to copy.
    inline_precedent = _precedent_prose_inline(pending)
    source_reference = (
        RESEARCH_STATE_REFERENCE if inline_precedent else RESULTS_REFERENCE
    )
    if preparation_source:
        heading = (
            "Preparation measurement rounds for the upcoming experiment, in the "
            "order they were requested. Questions, results and artifact "
            "references are retained; the recorded rationale for each past "
            "decision is kept below as a de-templated retrospective note, not as "
            "a template for the next request:"
        )
    elif inline_precedent:
        heading = (
            "Measurement rounds for the current experiment in the order they were "
            "requested. Each round records its own question, selections and "
            "resulting artifacts:"
        )
    else:
        heading = (
            "Completed measurement rounds from the most recent experiment, in "
            "the order they were requested. Questions, results and artifact "
            "references are retained; the recorded rationale for each past "
            "decision is kept below as a de-templated retrospective note, not as "
            "a template for the next request:"
        )
    lines = ["", "## Measurement rounds", "", heading]
    for record in rounds:
        if not isinstance(record, dict):
            continue
        status = str(record.get("status", "accepted"))
        lines.extend(["", f"### Round {record.get('round', '-')} ({status})"])
        if record.get("question"):
            lines.extend(
                _indented_label_block(
                    "Question", str(record["question"]), 400, source_reference
                )
            )
        # Issue #54: the round-level rationale is retained in both phases. It is
        # inline during analysis and collected for the de-templated note during
        # preparation.
        precedent: list[str] = []
        if record.get("reason"):
            if inline_precedent:
                lines.extend(
                    _indented_label_block(
                        "Reason", str(record["reason"]), 400, source_reference
                    )
                )
            else:
                precedent.extend(
                    _indented_label_block(
                        "Round rationale",
                        str(record["reason"]),
                        400,
                        source_reference,
                    )
                )
        round_results = (
            record.get("results") if isinstance(record.get("results"), dict) else {}
        )
        round_panels: list[tuple] = []
        for item in round_results.get("research_evaluations") or []:
            if not isinstance(item, dict):
                continue
            metrics = (
                item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
            )
            identity = _panel_identity({**metrics, **item}, "research_evaluation")
            panel_note, qualifier = _reuse_context(
                prior_uses, prior_selected, identity, _entry_fingerprint(item)
            )
            if identity is not None:
                round_panels.append(identity)
            detail = _episode_interval(item)
            if item.get("success_percent") is not None:
                detail += f", success {float(item['success_percent']):.2f}%"
            lines.append(
                f"- `{item.get('candidate', '-')}` "
                f"`research_evaluation`{_round_entry_status(item)}"
                f"{panel_note}: {detail}.{qualifier}"
            )
            if item.get("selection"):
                if inline_precedent:
                    lines.append(
                        f"  - Selection: "
                        f"{_compact(str(item['selection']), 600, reference=source_reference)}"
                    )
                else:
                    label = _fingerprint_qualified_label(
                        str(item.get("candidate", "-")), _entry_fingerprint(item)
                    )
                    precedent.extend(
                        _indented_label_block(
                            f"Choice rationale for `{label}`",
                            str(item["selection"]),
                            600,
                            source_reference,
                        )
                    )
            if item.get("reused_from_round") is not None:
                lines.append(f"  - Reused from round {item['reused_from_round']}")
            if item.get("evaluation_artifact"):
                lines.append(
                    "  - Artifact: "
                    + _existing_artifact_reference(
                        item["evaluation_artifact"], kind="file"
                    )
                )
        for item in round_results.get("task_reference_evaluations") or []:
            if not isinstance(item, dict):
                continue
            metrics = (
                item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
            )
            identity = _panel_identity({**metrics, **item}, "task_reference")
            panel_note, qualifier = _reuse_context(
                prior_uses, prior_selected, identity, _entry_fingerprint(item)
            )
            if identity is not None:
                round_panels.append(identity)
            detail = f"panel `{item.get('panel', '-')}`"
            if item.get("success_percent") is not None:
                detail += f", success {float(item['success_percent']):.2f}%"
            lines.append(
                f"- `{item.get('candidate', '-')}` "
                f"`task_reference`{_round_entry_status(item)}"
                f"{panel_note}: {detail}.{qualifier}"
            )
            if item.get("selection"):
                if inline_precedent:
                    lines.append(
                        f"  - Selection: "
                        f"{_compact(str(item['selection']), 600, reference=source_reference)}"
                    )
                else:
                    label = _fingerprint_qualified_label(
                        str(item.get("candidate", "-")), _entry_fingerprint(item)
                    )
                    precedent.extend(
                        _indented_label_block(
                            f"Choice rationale for `{label}`",
                            str(item["selection"]),
                            600,
                            source_reference,
                        )
                    )
            if item.get("reused_from_round") is not None:
                lines.append(f"  - Reused from round {item['reused_from_round']}")
            if item.get("evaluation_artifact"):
                lines.append(
                    "  - Artifact: "
                    + _existing_artifact_reference(
                        item["evaluation_artifact"], kind="file"
                    )
                )
        for item in round_results.get("paired_comparisons") or []:
            if not isinstance(item, dict):
                continue
            reused = []
            for panel in item.get("panels") or []:
                if not isinstance(panel, dict):
                    continue
                identity = _panel_identity(panel, "research_evaluation")
                if identity is None:
                    continue
                uses = prior_uses.get(identity, 0)
                if uses:
                    reused.append((identity, uses))
            qualifier = ""
            if reused:
                context = ", ".join(
                    f"{_panel_identity_label(identity)} ({uses} prior)"
                    for identity, uses in reused
                )
                qualifier = (
                    f" Reused panel context: {context}; comparable to earlier "
                    "results on the same episodes, not independent confirmation."
                )
            lines.append(
                f"- Paired comparison `{item.get('candidate', '-')}` vs "
                f"`{item.get('reference', '-')}`: {item.get('candidate_wins', '-')} "
                f"vs {item.get('reference_wins', '-')} discordant wins over "
                f"{item.get('episodes', '-')} episodes.{qualifier}"
            )
        if precedent:
            lines.extend(
                [
                    "",
                    (
                        "Recorded rationale for a past decision; it answered a "
                        "question that is not yours. It is retained for audit, not "
                        "as a template to copy:"
                    ),
                    *precedent,
                ]
            )
        for identity in round_panels:
            prior_uses[identity] = prior_uses.get(identity, 0) + 1
    return lines


def _v4_official_section(state: dict, terminal) -> list[str]:
    """The terminal official report, present only after a verdict."""
    official = state.get("official_metrics")
    if official is None:
        return []
    official_model = state.get("official_benchmark_model") or {}
    expectation = state.get("official_benchmark_expectation")
    if not isinstance(expectation, dict):
        expectation = {}
    return [
        "",
        "## Official report",
        "",
        f"- Model: {official_model.get('selected', 'legacy official assessment')} ({official_model.get('artifact', 'not recorded')})",
        f"- Verdict: {state.get('official_benchmark_verdict', terminal or 'not recorded')}",
        f"- Result: {official}",
        f"- Terminal assessment: {terminal or 'not recorded'}",
        (
            "  - Expected verdict: "
            f"{_recorded_value(expectation.get('expected_verdict'))}"
        ),
        f"  - Terminal reason: {_recorded_value(expectation.get('reason'))}",
    ]


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
    latest = (
        pending.get("result")
        if isinstance(pending, dict)
        else (results[-1] if results else None)
    )
    latest_experiment = (
        pending.get("experiment")
        if isinstance(pending, dict)
        else (latest or {}).get("index", "none")
    )
    terminal = state.get("terminal_campaign_status")
    lines = _v4_phase_section(
        state,
        pending,
        latest,
        latest_experiment,
        terminal,
        campaign_id,
        campaign_base_commit,
    )

    lines.extend(["", "## Latest experiment", ""])
    if isinstance(pending, dict):
        result = pending.get("result", {})
        candidates = sorted(
            pending.get("candidates", []),
            key=lambda item: str(item.get("name", "")),
        )
        measured = [
            candidate for candidate in candidates if candidate.get("evaluations")
        ]
        unmeasured = [
            candidate for candidate in candidates if not candidate.get("evaluations")
        ]
        lines.extend(
            [
                f"- Operation: {operation_description(result) or result.get('kind', '-')}",
                f"- Parent: {result.get('training_parent', pending.get('training_parent', '-'))}",
                f"- Intervention: {_change_details(result)}",
                "- Raw training logs: "
                + ", ".join(
                    _existing_artifact_reference(path, kind="file")
                    for path in pending.get("training_log_paths", [])
                )
                if pending.get("training_log_paths")
                else "- Raw training logs: unmeasured",
            ]
        )
        if result.get("recipe_basis"):
            lines.append(f"- Recipe basis: {_recipe_basis(result)}")
        if unmeasured:
            lines.append(
                f"- Unmeasured candidates: {len(unmeasured)} of {len(candidates)}."
            )
        if measured:
            lines.extend(
                [
                    "",
                    "| Candidate | Measurements |",
                    "|---|---|",
                ]
            )
            for candidate in measured:
                lines.append(
                    f"| `{candidate.get('name', '-')}` | {_v4_measurements(candidate)} |"
                )
    elif latest:
        selected_lineage = (latest.get("closure_decision") or {}).get(
            "continue_from", "unmeasured"
        )
        lines.extend(
            [
                f"- Operation: {operation_description(latest) or latest.get('kind', '-')}",
                f"- Parent: {latest.get('training_parent', '-')}",
                f"- Intervention: {_change_details(latest)}",
                f"- Measurements: {_v4_result_measurements(latest)}",
                f"- Hypothesis assessment: {_assessment_with_confidence(latest)}",
                f"- Working lineage selected: {selected_lineage}",
            ]
        )
        if latest.get("recipe_basis"):
            lines.append(f"- Recipe basis: {_recipe_basis(latest)}")
    else:
        lines.append("No experiment has completed in this campaign.")

    lines.extend(_v4_lineage_section(state, current_params))

    lines.extend(_v4_experiment_index_section(results, pending))

    lines.extend(_v4_evidence_section(state, pending, results))

    lines.extend(_v4_measurement_rounds_section(state, results, pending))

    lines.extend(_v4_activity_record_section(state, results, pending))

    lines.extend(_v4_synthesis_section(postmortems, campaign_id))

    lines.extend(_v4_repeated_operations_section(results))

    lines.extend(_v4_intervention_surfaces_section(results))

    lines.extend(_v4_reusable_lineages_section(state))
    lines.extend(_v4_best_known_section(state))

    lines.extend(_v4_terminal_assessment_section(state))

    lines.extend(_v4_official_section(state, terminal))
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
        for candidate in candidate_display_order(
            pending_evaluation["candidates"],
            campaign_id=campaign_id,
            experiment=pending_evaluation.get("experiment"),
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
                f"- Accepted lineage training: "
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
            "| # | Family | Operation | Init / steps | Outcome | Verdict |",
            "|---:|---|---|---|---|---|",
        ]
    )

    for result in results[-5:]:
        family = _table_cell(result.get("family", "-"))
        details = _table_cell(
            _compact(_change_details(result), 220, reference=RESULTS_REFERENCE)
        )
        initialization = result.get("initialization", "-")
        requested_steps = result.get("training_budget_steps")
        setup = initialization
        if requested_steps is not None:
            setup += f" / {int(requested_steps):,} steps"
        outcome = _table_cell(
            _compact(_experiment_outcome(result), 220, reference=RESULTS_REFERENCE)
        )
        verdict = _table_cell(
            _compact(result["verdict"], 100, reference=RESULTS_REFERENCE)
        )
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
    # Reported through the runner console so this line carries the same label
    # and timestamp as the other runner steps, instead of appearing unattributed.
    console.announce(f"[brief] wrote {brief.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
