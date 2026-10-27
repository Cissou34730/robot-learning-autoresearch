"""PI-visible factual summaries of durable campaign state."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path

from runner.launcher import pstext
from runner.launcher.pstext import field, items, text

_MEASUREMENT_HIDDEN_METRICS = frozenset(
    {
        "episode_results",
        "evaluation_artifact",
        "evaluation_artifact_fingerprint",
        "evaluation_artifact_contents",
        "model_fingerprint",
    }
)
_CODING_ROLES = frozenset({"scientific_coder", "scientific_reviewer"})


def load_state(campaign_root: Path) -> dict:
    path = campaign_root / "runner" / "state" / "research_state.json"
    return json.loads(path.read_text(encoding="utf-8-sig"))


def completed_events(state: dict) -> list:
    return [
        event
        for event in items(field(state, "operation_events"))
        if pstext.same(field(event, "status"), "completed")
    ]


def _measurement_result(identifier: str, result: object) -> str:
    measurements = []
    for measurement in items(field(result, "measurements")):
        metrics = field(measurement, "metrics")
        artifact_value = field(metrics, "evaluation_artifact")
        artifact = text(artifact_value) if pstext.truthy(artifact_value) else "none"
        facts = {
            name: value
            for name, value in (metrics.items() if isinstance(metrics, dict) else ())
            if name.casefold() not in _MEASUREMENT_HIDDEN_METRICS
        }
        measurements.append(
            f"{text(field(measurement, 'label'))}: artifact={artifact}; "
            f"result summary (not the complete artifact)={pstext.to_json(facts)}"
        )
    comparisons = [
        {
            name: value
            for name, value in (
                comparison.items() if isinstance(comparison, dict) else ()
            )
            if name.casefold() != "shared_episode_seeds"
        }
        for comparison in items(field(result, "paired_comparisons"))
    ]
    comparison_fact = pstext.pipeline_json(comparisons) if comparisons else "none"
    return (
        f"Operation {identifier} (measurement): {' | '.join(measurements)}; "
        f"comparisons={comparison_fact}."
    )


def _saved_component_fact(result: object) -> str:
    saved = field(result, "saved_component_comparisons")
    if not pstext.truthy(saved):
        return ""
    exact = [
        (
            f"{text(field(comparison, 'operation'))}: "
            f"{len(items(field(comparison, 'exact_component_matches')))}/"
            f"{text(field(comparison, 'corresponding_checkpoint_count'))} corresponding "
            "checkpoints; runtime files "
            f"{text(field(field(comparison, 'runtime'), 'equal'))}/"
            f"{text(field(field(comparison, 'runtime'), 'compared'))}"
        )
        for comparison in items(field(saved, "comparisons"))
        if len(items(field(comparison, "exact_component_matches"))) > 0
    ]
    summary = " | ".join(exact) if exact else "no exact checkpoint matches"
    return (
        f" Exact saved-component comparison={summary}. "
        "This reports serialized equality only; realization of an "
        "intended intervention is not determined."
    )


def _training_result(identifier: str, result: object) -> str:
    dynamics = [
        (
            f"{text(field(entry, 'candidate'))}: "
            f"steps={text(field(entry, 'training_steps'))}, "
            f"success={text(field(entry, 'training_success'))}, "
            f"reward={text(field(entry, 'ep_rew_mean'))}"
        )
        for entry in items(field(result, "learning_dynamics"))
    ]
    provenance = field(result, "mechanical_provenance")
    changed = [
        text(field(entry, "path"))
        for entry in items(field(provenance, "changed_files"))
    ]
    candidates = pstext.join(items(field(result, "candidates")), ", ")
    return (
        f"Operation {identifier} (training): candidates={candidates}; "
        f"learning dynamics={' | '.join(dynamics)}; provenance parent="
        f"{text(field(provenance, 'code_parent_commit'))}, changed="
        f"{', '.join(changed)}.{_saved_component_fact(result)}"
    )


def latest_session_result(state: dict) -> str:
    session = field(state, "scientific_session")
    operation_ids = field(session, "operation_ids")
    if (
        not pstext.truthy(session)
        or not pstext.truthy(operation_ids)
        or pstext.count(operation_ids) == 0
    ):
        return "No operation has completed in the current line of work."
    identifier = text(items(operation_ids)[-1])
    event = next(
        (
            entry
            for entry in items(field(state, "operation_events"))
            if pstext.same(field(entry, "id"), identifier)
            and pstext.same(field(entry, "status"), "completed")
        ),
        None,
    )
    if event is None:
        return f"There is no completed result for {identifier}; the failed attempt is not evidence."
    result = field(event, "result")
    kind = field(event, "kind")
    if pstext.same(kind, "measurement"):
        return _measurement_result(identifier, result)
    if pstext.same(kind, "training"):
        return _training_result(identifier, result)
    for name in ("summary", "status", "outcome"):
        if pstext.truthy(field(result, name)):
            fact = text(field(result, name))
            break
    else:
        fact = "completed"
    return f"Operation {identifier} ({text(kind)}) recorded factual result: {fact}."


def _elapsed(started_at: object, now: datetime) -> str:
    started = datetime.fromisoformat(str(started_at)).astimezone()
    seconds = (now - started).total_seconds()
    return f"elapsed {math.floor(seconds / 3600)}h{int(seconds // 60) % 60:02d}m"


def _usage(campaign_root: Path, campaign_id: str) -> tuple[float, float] | None:
    path = campaign_root / "reports" / "session_usage" / f"{campaign_id}.jsonl"
    if not path.exists():
        return None
    pi = coding = 0.0
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        aiu = field(row, "aiu")
        if aiu is None:
            continue
        role = field(row, "role")
        if isinstance(role, str) and role.casefold() in _CODING_ROLES:
            coding += float(aiu)
        else:
            pi += float(aiu)
    return pi, coding


def campaign_resource_summary(
    state: dict, campaign_root: Path, *, now: datetime | None = None
) -> str:
    completed = completed_events(state)
    measurements = sum(
        1 for event in completed if pstext.same(field(event, "kind"), "measurement")
    )
    training = sum(
        1 for event in completed if pstext.same(field(event, "kind"), "training")
    )
    campaign = field(state, "campaign")
    parts = []
    if pstext.truthy(field(campaign, "started_at")):
        parts.append(
            _elapsed(field(campaign, "started_at"), now or datetime.now().astimezone())
        )
    usage = _usage(campaign_root, text(field(campaign, "id")))
    if usage is not None:
        pi, coding = usage
        parts.append(
            "AI usage of completed sessions "
            f"{pstext.invariant_fixed_one(pi + coding)} AIU "
            f"(PI {pstext.invariant_fixed_one(pi)}, coding and review "
            f"{pstext.invariant_fixed_one(coding)})"
        )
    counters = field(state, "counters")
    candidates = field(state, "candidates")
    candidate_count = len(candidates) if isinstance(candidates, dict) else 1
    parts.append(
        f"inquiries {_integer(field(counters, 'inquiry'))} | "
        f"sessions {_integer(field(counters, 'session'))} | measurements {measurements} | "
        f"training {training} | candidates {candidate_count}"
    )
    return " | ".join(parts)


def _integer(value: object) -> int:
    """``[int]$value``: ``$null`` is zero and halves round to even."""
    if value is None:
        return 0
    return round(float(value)) if isinstance(value, float) else int(value)


def human_goal_summary(state: dict, harness_root: Path) -> str:
    summary = field(field(state, "human_goal"), "summary")
    if pstext.truthy(summary):
        return text(summary)
    scenario = (harness_root / "contracts" / "scenario.md").read_text(
        encoding="utf-8-sig"
    )
    match = re.search(
        r"(?ms)^## Success criterion\s+(?P<body>.*?)(?=^## |\Z)", scenario
    )
    if match:
        return re.sub(r"\s+", " ", match["body"]).strip()
    return "The protected human goal is defined in contracts/scenario.md."
