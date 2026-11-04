"""Recorded training, checkpoint and measurement relationships."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from tui.timeline_items import TimelineItem


def _object(value: object) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def _items(value: object) -> Sequence:
    return value if isinstance(value, (list, tuple)) else ()


def _events(state: Mapping, records: Sequence[Mapping]) -> list[Mapping]:
    events: dict[str, Mapping] = {}
    for event in (*_items(state.get("operation_events")), *records):
        if isinstance(event, Mapping) and isinstance(event.get("id"), str):
            events[event["id"]] = event
    pending = _object(state.get("pending_operation"))
    identity = pending.get("id")
    if isinstance(identity, str) and identity:
        events[identity] = pending
    return list(events.values())


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _status(event: Mapping) -> str:
    if event.get("failure"):
        return "failed"
    return _text(event.get("status")) or _text(event.get("progress"))


def _metric(value: object, *, fraction: bool = False) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = value * 100 if fraction else value
        return f"{number:g}%"
    return "unavailable"


def _scope_tree(
    namespace: str, state: Mapping, records: Sequence[Mapping]
) -> list[TimelineItem]:
    events = _events(state, records)
    roots: list[TimelineItem] = []
    checkpoints: dict[str, TimelineItem] = {}
    checkpoint_order: dict[str, int] = {}
    trainings: list[tuple[TimelineItem, str]] = []

    for event in events:
        if event.get("kind") != "training":
            continue
        identity = _text(event.get("id"))
        result = _object(event.get("result"))
        request = _object(event.get("request"))
        request = _object(request.get("training")) or request
        variants = _items(result.get("variants"))
        groups = variants or (result,)
        packets = {
            packet.get("candidate"): packet
            for packet in _items(result.get("learning_dynamics"))
            if isinstance(packet, Mapping) and isinstance(packet.get("candidate"), str)
        }
        for variant in groups:
            variant = _object(variant)
            label = _text(variant.get("label"))
            name = f"{identity}:{label}" if label else identity
            status = _status(event)
            initialization = _text(result.get("initialization")) or _text(
                request.get("initialization")
            )
            steps = result.get("requested_steps", request.get("steps"))
            summary = " · ".join(
                part
                for part in (
                    initialization,
                    f"{steps:,} steps" if isinstance(steps, int) else "",
                    status if status and status != "completed" else "",
                )
                if part
            )
            training = TimelineItem(
                item_id=f"{namespace}:training:{name}",
                kind="training",
                title=f"{name} Training",
                summary=summary,
                detail=(f"Operation: {identity}", f"Status: {status or 'unknown'}"),
                is_group=True,
                default_expanded=True,
            )
            parent = (
                _text(variant.get("parent"))
                if variants
                else _text(result.get("parent"))
                or _text(_object(_object(event.get("data")).get("parent")).get("id"))
            )
            for candidate in _items(variant.get("candidates")):
                if not isinstance(candidate, str) or not candidate:
                    continue
                packet = _object(packets.get(candidate))
                steps = packet.get("training_steps")
                metrics = []
                if packet.get("ep_rew_mean") is not None:
                    metrics.append(f"training reward {packet['ep_rew_mean']}")
                if packet.get("training_success") is not None:
                    metrics.append(
                        f"training success {_metric(packet['training_success'], fraction=True)}"
                    )
                checkpoint = TimelineItem(
                    item_id=f"{namespace}:checkpoint:{candidate}",
                    kind="checkpoint",
                    title=f"Checkpoint {steps:,}"
                    if isinstance(steps, int)
                    else candidate,
                    summary=" · ".join(metrics),
                    detail=(f"Candidate: {candidate}",),
                    is_group=True,
                    default_expanded=True,
                )
                training.children.append(checkpoint)
                checkpoints[candidate] = checkpoint
                checkpoint_order[candidate] = len(trainings)
            trainings.append((training, parent))

    for index, (training, parent) in enumerate(trainings):
        parent_node = checkpoints.get(parent)
        # A parent must already exist before the child training operation.
        if parent_node is not None and checkpoint_order[parent] < index:
            parent_node.children.append(training)
            continue
        if parent:
            training.detail += (f"Parent not present in this history: {parent}",)
        roots.append(training)

    unlinked: list[TimelineItem] = []
    for event in events:
        if event.get("kind") != "measurement":
            continue
        identity = _text(event.get("id"))
        status = _status(event)
        result = _object(event.get("result"))
        panels = _items(result.get("measurements"))
        if not panels:
            data = _object(event.get("data"))
            planned = _items(data.get("measurements"))
            partials = _items(data.get("partial_results"))
            panels = [
                {
                    **_object(spec),
                    **_object(partials[index] if index < len(partials) else None),
                }
                for index, spec in enumerate(planned)
            ]
        if not panels:
            unlinked.append(
                TimelineItem(
                    item_id=f"{namespace}:measurement:{identity}",
                    kind="measurement",
                    title=f"{identity} Measurement",
                    summary=status or "result pending",
                    detail=(f"Status: {status or 'unknown'}",),
                )
            )
        for index, value in enumerate(panels):
            panel = _object(value)
            candidate = _text(panel.get("candidate")) or _text(
                panel.get("candidate_id")
            )
            metrics = _object(panel.get("metrics"))
            instrument = _text(panel.get("instrument")) or "measurement"
            instrument_label = {
                "research_evaluation": "research eval",
                "task_reference": "task reference",
                "python_module": "python module",
            }.get(instrument, instrument)
            episodes = metrics.get("episodes")
            summary = " · ".join(
                part
                for part in (
                    status if status and status != "completed" else "",
                    f"success {_metric(metrics.get('success_percent'))}"
                    if metrics.get("success_percent") is not None
                    else "artifact recorded"
                    if metrics.get("evaluation_artifact")
                    else "result pending"
                    if status not in {"completed", "failed", "interrupted"}
                    else "result unavailable",
                    instrument_label,
                    f"{episodes} episodes" if isinstance(episodes, int) else "",
                )
                if part
            )
            measurement = TimelineItem(
                item_id=f"{namespace}:measurement:{identity}:{index}",
                kind="measurement",
                title=f"{identity} Measurement",
                summary=summary,
                detail=(
                    f"Operation: {identity}",
                    f"Candidate: {candidate or 'not recorded'}",
                    f"Instrument: {instrument}",
                    f"Status: {status or 'unknown'}",
                    f"Recorded metrics:\n{json.dumps(metrics, indent=2, default=str)}",
                ),
            )
            if candidate in checkpoints:
                checkpoints[candidate].children.append(measurement)
            else:
                unlinked.append(measurement)
    if unlinked:
        roots.append(
            TimelineItem(
                item_id=f"{namespace}:unlinked",
                kind="measurement",
                title="Measurements without a recorded checkpoint link",
                children=unlinked,
                is_group=True,
                default_expanded=True,
            )
        )
    return roots


def build_training_tree(
    state: Mapping | None,
    records: Sequence[Mapping],
    *,
    archived_state: Mapping | None = None,
    archived_records: Sequence[Mapping] = (),
) -> list[TimelineItem]:
    roots: list[TimelineItem] = []
    if archived_state:
        archived = _scope_tree("recipe", archived_state, archived_records)
        if archived:
            roots.append(
                TimelineItem(
                    item_id="recipe:root",
                    kind="session",
                    title="Recipe development",
                    children=archived,
                    is_group=True,
                    default_expanded=True,
                )
            )
    roots.extend(_scope_tree("campaign", state or {}, records))
    return roots
