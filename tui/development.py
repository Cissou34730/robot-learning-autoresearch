"""Pure, read-only projection of recorded recipe-development trials."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType


def freeze(value: object) -> object:
    """Detach JSON values from their producer and make nested values read-only."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class MeasurementSnapshot:
    candidate_id: str
    success_percent: float
    episodes: int | None
    instrument: str | None
    operation_id: str
    seed: int | None
    artifact: str | None
    label: str | None


@dataclass(frozen=True)
class CheckpointSnapshot:
    id: str
    steps: int | None
    training_reward: float | None = None
    training_success: float | None = None
    measurements: tuple[MeasurementSnapshot, ...] = ()


@dataclass(frozen=True)
class VariantSnapshot:
    label: str
    state: str
    requested_steps: int | None
    actual_steps: int | None
    parent_id: str | None
    prior_steps: int | None
    checkpoints: tuple[CheckpointSnapshot, ...]
    latest_measurement: MeasurementSnapshot | None = None
    training_reward: float | None = None
    training_success: float | None = None
    parameters: Mapping | None = None
    proposed_change: str | None = None
    expected_behavior: str | None = None


@dataclass(frozen=True)
class ComparisonSnapshot:
    id: str
    question: str | None
    description: str | None
    rationale: str | None
    seed: int | None
    initialization: str | None
    allocation_per_variant: int | None
    total_allocation: int | None
    variants: tuple[VariantSnapshot, ...]


@dataclass(frozen=True)
class DevelopmentSnapshot:
    phase: str
    archived: bool
    source_available: bool
    explanation: str | None
    comparisons: tuple[ComparisonSnapshot, ...]
    campaign_id: str | None = None
    decision: str | None = None
    choices: tuple[tuple[str, str], ...] = ()
    chosen_comparison_ids: tuple[str, ...] = ()
    candidates_and_roles: str | None = None


def _object(value: object) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def _items(value: object) -> Sequence:
    return value if isinstance(value, (list, tuple)) else ()


def _integer(value: object) -> int | None:
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0
        else None
    )


def _number(value: object) -> float | None:
    return (
        float(value)
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        else None
    )


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _events(state: Mapping, records: Sequence[Mapping]) -> tuple[Mapping, ...]:
    ordered = {}
    for event in (*_items(state.get("operation_events")), *records):
        if isinstance(event, Mapping) and _text(event.get("id")):
            ordered[event["id"]] = event
    pending = _object(state.get("pending_operation"))
    if (
        pending
        and _text(pending.get("id"))
        and _object(ordered.get(pending["id"])).get("status") != "completed"
    ):
        ordered[pending["id"]] = pending
    return tuple(ordered.values())


def _session_ids(state: Mapping, events: Sequence[Mapping]) -> set[str]:
    session = _object(state.get("scientific_session"))
    handoff = _object(state.get("recipe_development"))
    session_ids = set()
    if _text(handoff.get("session_id")):
        session_ids.add(handoff["session_id"])
    if session.get("kind") == "recipe_development" and _text(session.get("id")):
        session_ids.add(session["id"])
    for event in events:
        presentation = _object(_object(event.get("data")).get("presentation"))
        if event.get(
            "session_kind", presentation.get("session_kind")
        ) == "recipe_development" and _text(event.get("session_id")):
            session_ids.add(event["session_id"])
    return session_ids


def _measurements(events: Sequence[Mapping]) -> tuple[MeasurementSnapshot, ...]:
    measured = []
    for event in events:
        if event.get("kind") != "measurement" or event.get("status") != "completed":
            continue
        for panel in _items(_object(event.get("result")).get("measurements")):
            panel = _object(panel)
            metrics = _object(panel.get("metrics"))
            percent = _number(metrics.get("success_percent"))
            identity = _text(panel.get("candidate_id")) or _text(panel.get("candidate"))
            if not identity or percent is None or metrics.get("official_benchmark"):
                continue
            instrument = _text(panel.get("instrument"))
            if instrument not in {"research_evaluation", "task_reference"}:
                continue
            seed = _integer(panel.get("seed"))
            measured.append(
                MeasurementSnapshot(
                    identity,
                    percent,
                    _integer(metrics.get("episodes")),
                    instrument,
                    str(event["id"]),
                    seed if seed is not None else _integer(metrics.get("seed")),
                    _text(metrics.get("evaluation_artifact")),
                    _text(panel.get("label")),
                )
            )
    return tuple(measured)


def _variant(
    event: Mapping,
    request: Mapping,
    declared: Mapping,
    candidates: Mapping,
    measurements: Sequence[MeasurementSnapshot],
    training_metrics: Mapping,
    progress: Mapping,
) -> VariantSnapshot:
    label = str(declared["label"])
    result = _object(event.get("result"))
    recorded = next(
        (
            _object(item)
            for item in _items(result.get("variants"))
            if _object(item).get("label") == label
        ),
        {},
    )
    packets = {
        item["candidate"]: item
        for item in _items(result.get("learning_dynamics"))
        if isinstance(item, Mapping) and "candidate" in item
    }
    single = not _items(request.get("variants"))
    identities = list(
        _items(result.get("candidates"))
        if single
        else _items(recorded.get("candidates"))
    )
    for identity, candidate in candidates.items():
        candidate = _object(candidate)
        if (
            candidate.get("origin_operation") == event["id"]
            and (single or str(candidate.get("name", "")).startswith(label + "-"))
            and identity not in identities
        ):
            identities.append(identity)
    checkpoints = []
    for identity in identities:
        if not isinstance(identity, str):
            continue
        candidate = _object(candidates.get(identity))
        packet = _object(packets.get(identity))
        metrics = _object(training_metrics.get(identity))
        steps = _integer(candidate.get("training_steps"))
        if steps is None:
            steps = _integer(packet.get("training_steps"))
        if steps is None:
            steps = _integer(metrics.get("timesteps", metrics.get("total_timesteps")))
        reward = _number(packet.get("ep_rew_mean"))
        success = _number(packet.get("training_success"))
        checkpoints.append(
            CheckpointSnapshot(
                identity,
                steps,
                reward if reward is not None else _number(metrics.get("ep_rew_mean")),
                success
                if success is not None
                else _number(metrics.get("training_success")),
                tuple(
                    panel for panel in measurements if panel.candidate_id == identity
                ),
            )
        )
    own_progress = (
        progress
        if progress.get("operation_id") == event["id"]
        and progress.get("variant") == label
        else {}
    )
    actual = [
        checkpoint.steps for checkpoint in checkpoints if checkpoint.steps is not None
    ]
    if _integer(own_progress.get("steps")) is not None:
        actual.append(own_progress["steps"])
    latest = (
        max(
            enumerate(checkpoints),
            key=lambda item: (
                item[1].steps if item[1].steps is not None else -1,
                item[0],
            ),
        )[1]
        if checkpoints
        else None
    )
    evidence = next(
        (panel for panel in reversed(measurements) if panel.candidate_id in identities),
        None,
    )
    parent = (
        _text(declared.get("parent"))
        or _text(request.get("parent"))
        or _text(recorded.get("parent"))
    )
    status = event.get("status")
    if status in {"failed", "interrupted"} or event.get("failure"):
        variant_state = "failed"
    elif (
        status == "completed"
        or actual
        and event.get("progress")
        in {
            "training_completed",
            "candidates_archived",
            "recipe_published",
            "result_ready",
            "completed",
        }
    ):
        variant_state = "completed"
    elif actual or own_progress:
        variant_state = "running"
    else:
        variant_state = "queued"
    return VariantSnapshot(
        label,
        variant_state,
        _integer(request.get("steps")),
        max(actual) if actual else None,
        parent,
        _integer(_object(candidates.get(parent)).get("training_steps")),
        tuple(checkpoints),
        evidence,
        _number(own_progress.get("ep_rew_mean"))
        if own_progress
        else latest.training_reward
        if latest
        else None,
        _number(own_progress.get("training_success"))
        if own_progress
        else latest.training_success
        if latest
        else None,
        freeze(_object(declared.get("parameters")))
        if "parameters" in declared
        else None,
        _text(declared.get("proposed_change")),
        _text(declared.get("expected_behavior")),
    )


def build_development_snapshot(
    state: Mapping | None,
    records: Sequence[Mapping],
    *,
    archived: bool = False,
    current_state: Mapping | None = None,
    delivery_stage: str | None = None,
    source_available: bool | None = None,
    explanation: str | None = None,
    training_metrics: Mapping | None = None,
    progress: Mapping | None = None,
) -> DevelopmentSnapshot:
    """Project only identified development sessions; no scores select PI choices.

    Training success is a recorded fraction, measured success is a percentage.
    Structured progress must identify both its operation and variant.
    """
    state = state or {}
    events = _events(state, records)
    session_ids = _session_ids(state, events)
    scoped = tuple(event for event in events if event.get("session_id") in session_ids)
    measurements = _measurements(scoped)
    candidates = dict(_object(state.get("candidates")))
    pending = _object(state.get("pending_operation"))
    for item in _items(_object(pending.get("data")).get("archived_candidates")):
        item = _object(item)
        name = _text(item.get("name"))
        if name and pending.get("session_id") in session_ids:
            identity = f"{pending['id']}:{name}"
            candidates.setdefault(
                identity,
                {
                    **item,
                    "origin_operation": pending["id"],
                    "training_steps": item.get("timesteps"),
                },
            )
    comparisons = []
    for event in scoped:
        if event.get("kind") != "training":
            continue
        request = _object(event.get("request"))
        request = _object(request.get("training")) or request
        declared_variants = _items(request.get("variants")) or ({"label": event["id"]},)
        variants = tuple(
            _variant(
                event,
                request,
                declared,
                candidates,
                measurements,
                training_metrics or {},
                progress or {},
            )
            for declared in declared_variants
            if isinstance(declared, Mapping) and _text(declared.get("label"))
        )
        if not variants:
            continue
        steps = _integer(request.get("steps"))
        comparisons.append(
            ComparisonSnapshot(
                str(event["id"]),
                _text(request.get("question")),
                _text(request.get("description")),
                _text(request.get("rationale")),
                _integer(request.get("seed")),
                _text(request.get("initialization")),
                steps,
                sum(variant.requested_steps for variant in variants)
                if all(variant.requested_steps is not None for variant in variants)
                else None,
                variants,
            )
        )
    handoff = _object(state.get("recipe_development"))
    session = _object(state.get("scientific_session"))
    roles = (
        _object(state.get("model_roles"))
        if archived or session.get("kind") == "recipe_development"
        else {}
    )
    recorded_roles = {}
    for role, identity in roles.items():
        if isinstance(identity, str):
            recorded_roles[str(role)] = identity
        elif role == "retained":
            recorded_roles.update(
                (f"retained:{label}", identity)
                for label, identity in _object(identity).items()
                if isinstance(identity, str)
            )
    for event in scoped:
        if event.get("kind") != "model_role" or event.get("status") != "completed":
            continue
        request = _object(event.get("request"))
        request = _object(request.get("model_role")) or request
        result = _object(event.get("result"))
        identity = (
            _text(result.get("candidate_id"))
            or _text(result.get("candidate"))
            or _text(request.get("candidate"))
        )
        action = request.get("action", result.get("action"))
        role = {"set_working": "working", "set_best_known": "best_known"}.get(action)
        if action == "retain" and _text(request.get("label", result.get("label"))):
            role = "retained:" + str(request.get("label", result.get("label")))
        if role and identity:
            recorded_roles[role] = identity
    scoped_candidates = {
        checkpoint.id
        for comparison in comparisons
        for variant in comparison.variants
        for checkpoint in variant.checkpoints
    }
    choices = tuple(
        (role, identity)
        for role, identity in recorded_roles.items()
        if identity in scoped_candidates
    )
    selected = {identity for _, identity in choices}
    chosen = tuple(
        comparison.id
        for comparison in comparisons
        if any(
            checkpoint.id in selected
            for variant in comparison.variants
            for checkpoint in variant.checkpoints
        )
    )
    available = bool(session_ids) or state.get("campaign_phase") == "recipe_development"
    if archived:
        phase = (
            "delivered"
            if delivery_stage == "published"
            or (current_state or {}).get("campaign_phase") in {"startup", "research"}
            else "delivering"
        )
    elif handoff:
        phase = "delivering"
    elif pending.get("failure") or state.get("terminal_state"):
        phase = "failed"
    elif _object(state.get("scientific_session")).get("status") in {
        "paused",
        "interrupted",
    } or state.get("paused"):
        phase = "paused"
    elif pending.get("session_id") in session_ids and pending.get("kind") in {
        "measurement",
        "checkpoint",
    }:
        phase = "validating" if pending["kind"] == "measurement" else "delivering"
    else:
        phase = "comparing" if comparisons else "preparing"
    return DevelopmentSnapshot(
        phase,
        archived,
        available if source_available is None else source_available,
        explanation,
        tuple(comparisons),
        _text(_object(state.get("campaign")).get("id")),
        _text(handoff.get("current_synthesis")),
        choices,
        chosen,
        _text(handoff.get("candidates_and_roles")),
    )
