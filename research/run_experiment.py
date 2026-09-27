"""Transactional Runner for goal-centered scientific operations."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from research import runner_console as console
from research import runner_execution as execution
from research import runner_paths as paths
from research import runner_protocol as protocol
from research import runner_repository as repository
from research.stop_control import interrupt_on_stop_request
from robot_learning.training import research_config

PROPOSAL_ERRORS = (
    json.JSONDecodeError,
    KeyError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
ACCEPTED_REQUEST_KEY = "_runner_accepted_operation"
ACCEPTED_REQUEST_VERSION = 1


class FrozenOperationMismatch(ValueError):
    """The live request or scientific surface differs from accepted state."""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _canonical_fingerprint(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _accepted_request_handoff(operation_id: str) -> dict:
    return {
        ACCEPTED_REQUEST_KEY: {
            "schema_version": ACCEPTED_REQUEST_VERSION,
            "operation_id": operation_id,
        }
    }


def _accepted_request_id(value: object) -> str | None:
    if not isinstance(value, dict) or set(value) != {ACCEPTED_REQUEST_KEY}:
        return None
    accepted = value[ACCEPTED_REQUEST_KEY]
    if (
        not isinstance(accepted, dict)
        or set(accepted) != {"schema_version", "operation_id"}
        or accepted["schema_version"] != ACCEPTED_REQUEST_VERSION
        or not isinstance(accepted["operation_id"], str)
        or not accepted["operation_id"].strip()
    ):
        return None
    return accepted["operation_id"]


def _write_accepted_request_handoff(pending: dict) -> None:
    repository.atomic_write_json(
        paths.OPERATION_REQUEST_PATH,
        _accepted_request_handoff(str(pending["id"])),
    )


def _consume_accepted_request_handoff(operation_id: str) -> bool:
    try:
        handoff = json.loads(paths.OPERATION_REQUEST_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    if _accepted_request_id(handoff) != operation_id:
        return False
    paths.OPERATION_REQUEST_PATH.unlink(missing_ok=True)
    return True


def _scientific_manifest(relative_paths: list[str]) -> list[dict]:
    manifest: list[dict] = []
    for relative in sorted(
        {repository.canonical_repo_path(path) for path in relative_paths}
    ):
        path = repository.resolve_repo_path(relative)
        if path.exists() and not path.is_file():
            raise ValueError(f"scientific manifest path is not a file: {relative}")
        manifest.append(
            {
                "path": relative,
                "exists": path.is_file(),
                "fingerprint": (
                    repository.file_fingerprint(path) if path.is_file() else None
                ),
            }
        )
    return manifest


def _current_scientific_manifest(parent: str) -> list[dict]:
    return _scientific_manifest(
        [
            path
            for path in repository.scientific_delta(parent)
            if path.replace("\\", "/") not in protocol.PARAMETER_ONLY_PATHS
            and not protocol.is_human_owned(path)
        ]
    )


def _require_matching_manifest(
    expected: object, actual: list[dict], description: str
) -> None:
    if not isinstance(expected, list) or expected != actual:
        raise FrozenOperationMismatch(
            f"{description} changed after the operation was accepted"
        )


def _protected_panel_overlap():
    from robot_learning.scenario.final_benchmark import (
        research_panel_overlaps_protected,
    )

    return research_panel_overlaps_protected


def _task_reference_contract() -> dict:
    from robot_learning.scenario.task_reference import task_reference_panel

    return task_reference_panel()


def _python_module_paths(measurements: list[dict]) -> list[str]:
    module_paths: list[str] = []
    for spec in measurements:
        if spec["instrument"] != "python_module":
            continue
        stem = spec["module"].replace(".", "/")
        candidates = [f"{stem}.py", f"{stem}/__main__.py"]
        relative = next(
            (
                repository.canonical_repo_path(candidate)
                for candidate in candidates
                if repository.resolve_repo_path(candidate).is_file()
            ),
            None,
        )
        if relative is None:
            raise ValueError(
                f"python_module source does not exist: {' or '.join(candidates)}"
            )
        module_paths.append(relative)
    return sorted(set(module_paths))


def _revalidate_frozen_science(data: dict, description: str) -> None:
    _require_matching_manifest(
        data["scientific_manifest"],
        _current_scientific_manifest(data["code_parent_commit"]),
        description,
    )
    if research_config.load_experiment_config() != data["effective_parameters"]:
        raise FrozenOperationMismatch(
            f"{description} configuration changed after the operation was accepted"
        )


def _revalidate_module_provenance(data: dict) -> None:
    provenance = data.get("module_provenance")
    if not isinstance(provenance, dict):
        return
    _revalidate_frozen_science(provenance, "python_module scientific surface")
    _require_matching_manifest(
        provenance["module_manifest"],
        _scientific_manifest(list(provenance["module_paths"])),
        "python_module source",
    )
    if repository.campaign_lab_manifest() != provenance["campaign_lab_manifest"]:
        raise FrozenOperationMismatch(
            "python_module campaign laboratory changed after the operation was accepted"
        )


def _transaction_data(kind: str, request: dict, state: dict) -> dict:
    session = protocol.require_active_session(state)
    if kind == "training":
        parent_commit = str(session["scientific_parent_commit"])
        repository.require_resolvable_commit(parent_commit)
        changed = repository.scientific_delta(parent_commit)
        protocol.validate_research_delta_ownership(changed)
        source_changes = [
            path
            for path in changed
            if path.replace("\\", "/") not in protocol.PARAMETER_ONLY_PATHS
        ]
        parent = protocol.resolved_training_parent(request["training"], state)
        return {
            "parent": copy.deepcopy(parent),
            "code_parent_commit": parent_commit,
            "scientific_manifest": _scientific_manifest(source_changes),
            "scientific_paths": list(changed),
            "scientific_commit": None,
            "effective_parameters": research_config.load_experiment_config(),
            "candidate_dir": None,
            "archived_candidates": None,
            "result": None,
        }
    if kind == "measurement":
        measurement = request["measurement"]
        planned = protocol.planned_measurements(measurement, state)
        protocol.validate_panel_independence(
            measurement,
            protected_overlap=_protected_panel_overlap(),
        )
        module_paths = _python_module_paths(planned)
        module_provenance = None
        if module_paths:
            parent_commit = str(session["scientific_parent_commit"])
            repository.require_resolvable_commit(parent_commit)
            changed = repository.scientific_delta(parent_commit)
            protocol.validate_research_delta_ownership(changed)
            module_provenance = {
                "code_parent_commit": parent_commit,
                "scientific_manifest": _current_scientific_manifest(parent_commit),
                "scientific_paths": list(changed),
                "scientific_commit": None,
                "effective_parameters": research_config.load_experiment_config(),
                "module_paths": module_paths,
                "module_manifest": _scientific_manifest(module_paths),
                "campaign_lab_manifest": repository.campaign_lab_manifest(),
                "campaign_lab_publication": None,
            }
        has_research_evaluation = any(
            spec["instrument"] == "research_evaluation" for spec in planned
        )
        has_task_reference = any(
            spec["instrument"] == "task_reference" for spec in planned
        )
        return {
            "measurements": planned,
            "paired_comparisons": protocol.planned_paired_comparisons(
                measurement, state, planned
            ),
            "evaluation_semantics": (
                protocol.evaluation_semantics_fingerprint()
                if has_research_evaluation
                else None
            ),
            "task_reference_contract": (
                _task_reference_contract() if has_task_reference else None
            ),
            "module_provenance": module_provenance,
            "partial_results": [],
            "result": None,
        }
    if kind == "inquiry":
        return {
            "plan": protocol.plan_inquiry_operation(request["inquiry"], state),
            "result": None,
        }
    if kind == "checkpoint":
        parent_commit = str(session["scientific_parent_commit"])
        repository.require_resolvable_commit(parent_commit)
        changed = repository.scientific_delta(parent_commit)
        protocol.validate_research_delta_ownership(changed)
        source_changes = [
            path
            for path in changed
            if path.replace("\\", "/") not in protocol.PARAMETER_ONLY_PATHS
        ]
        return {
            "plan": protocol.plan_checkpoint(request["checkpoint"], state),
            "code_parent_commit": parent_commit,
            "scientific_manifest": _scientific_manifest(source_changes),
            "scientific_paths": list(changed),
            "effective_parameters": research_config.load_experiment_config(),
            "scientific_commit": None,
            "result": None,
        }
    if kind == "model_role":
        return {
            "plan": protocol.plan_model_role(request["model_role"], state),
            "publication": None,
            "result": None,
        }
    if kind == "restore_recipe":
        plan = protocol.plan_recipe_restore(request["restore_recipe"], state)
        return {
            "plan": plan,
            "pre_restore_manifest": _scientific_manifest(
                [*plan["restore"], *plan["remove_created"]]
            ),
            "result": None,
        }
    return {
        "plan": protocol.plan_campaign_conclusion(
            request["campaign_conclusion"], state
        ),
        "result": None,
    }


def accept_operation(request: dict, state: dict | None = None) -> dict:
    state = state or repository.load_state(allow_missing_artifact=True)
    kind = protocol.validate_operation_request(request, state)
    existing = state["pending_operation"]
    fingerprint = _canonical_fingerprint(request)
    if isinstance(existing, dict):
        if (
            existing["request_fingerprint"] != fingerprint
            or existing["request"] != request
        ):
            raise FrozenOperationMismatch("operation request changed after acceptance")
        _write_accepted_request_handoff(existing)
        return existing
    identifier = protocol.allocate_operation_id(kind, state)
    session = protocol.require_active_session(state)
    pending = {
        "id": identifier,
        "kind": kind,
        "session_id": session["id"],
        "inquiry_id": session["inquiry_id"],
        "request": copy.deepcopy(request),
        "request_fingerprint": fingerprint,
        "progress": "accepted",
        "failure": None,
        "supersedes": None,
        "data": _transaction_data(kind, request, state),
    }
    state["pending_operation"] = pending
    repository.write_state(state)
    _write_accepted_request_handoff(pending)
    return pending


def reaccept_pending_operation(state: dict | None = None) -> dict:
    state = state or repository.load_state(allow_missing_artifact=True)
    previous = state["pending_operation"]
    if not isinstance(previous, dict):
        raise TypeError("there is no pending Runner operation to reaccept")
    if not str(previous.get("failure") or "").strip():
        raise ValueError("only a failed Runner operation can be reaccepted")
    request = copy.deepcopy(previous["request"])
    state["pending_operation"] = None
    kind = protocol.validate_operation_request(request, state)
    identifier = protocol.allocate_operation_id(kind, state)
    session = protocol.require_active_session(state)
    data = _transaction_data(kind, request, state)
    pending = {
        "id": identifier,
        "kind": kind,
        "session_id": session["id"],
        "inquiry_id": session["inquiry_id"],
        "request": request,
        "request_fingerprint": _canonical_fingerprint(request),
        "progress": "accepted",
        "failure": None,
        "supersedes": previous["id"],
        "data": data,
    }
    failed_event = _event_for(
        state,
        previous,
        {"status": "failed", "error": previous["failure"]},
        status="failed",
        superseded_by=identifier,
    )
    repository.upsert_operation_event(failed_event)
    state["operation_events"].append(
        {key: value for key, value in failed_event.items() if key != "campaign_id"}
    )
    state["pending_operation"] = pending
    repository.write_state(state)
    _write_accepted_request_handoff(pending)
    if not repository.commit_runner_memory(
        f"supersede {previous['id']} with {identifier}"
    ):
        repository.push_head()
    return pending


def _event_for(
    state: dict,
    pending: dict,
    result: dict,
    *,
    status: str = "completed",
    superseded_by: str | None = None,
) -> dict:
    inquiry_id = pending["inquiry_id"]
    if pending["kind"] == "inquiry" and result.get("action") == "open":
        inquiry_id = result["inquiry_id"]
    return {
        "campaign_id": repository.current_campaign_id(state),
        "id": pending["id"],
        "kind": pending["kind"],
        "session_id": pending["session_id"],
        "inquiry_id": inquiry_id,
        "request": copy.deepcopy(pending["request"][pending["kind"]]),
        "result": copy.deepcopy(result),
        "status": status,
        "error": pending.get("failure") if status == "failed" else None,
        "supersedes": pending.get("supersedes"),
        "superseded_by": superseded_by,
        "completed_at": _now(),
    }


def _complete_operation(
    state: dict,
    result: dict,
    apply: Callable[[dict, dict], None] | None = None,
    *,
    include_in_session: bool = True,
) -> None:
    pending = state["pending_operation"]
    if not isinstance(pending, dict):
        raise TypeError("no pending operation to complete")
    if pending["progress"] != "completed":
        pending["data"]["result"] = copy.deepcopy(result)
        pending["progress"] = "result_ready"
        repository.write_state(state)
        event = _event_for(state, pending, result)
        repository.upsert_operation_event(event)
        if not any(item["id"] == event["id"] for item in state["operation_events"]):
            state["operation_events"].append(
                {key: value for key, value in event.items() if key != "campaign_id"}
            )
        if apply is not None:
            apply(state, result)
        session = state.get("scientific_session")
        if (
            include_in_session
            and isinstance(session, dict)
            and event["id"] not in session["operation_ids"]
        ):
            session["operation_ids"].append(event["id"])
        state["last_verdict"] = str(
            result.get("summary") or result.get("status") or "operation completed"
        )
        pending["progress"] = "completed"
        repository.write_state(state)
        if not repository.commit_runner_memory(
            f"complete {pending['id']} {pending['kind']}"
        ):
            repository.push_head()
    _finalize_operation(state, pending)


def _finalize_operation(state: dict, pending: dict) -> None:
    state["pending_operation"] = None
    repository.write_state(state)
    try:
        if not repository.commit_runner_memory(f"finalize {pending['id']}"):
            repository.push_head()
    except Exception:
        state["pending_operation"] = pending
        repository.write_state(state)
        raise
    _consume_accepted_request_handoff(str(pending["id"]))


def _matching_completed_pending(state: dict, operation_id: str) -> dict | None:
    pending = state.get("pending_operation")
    if (
        isinstance(pending, dict)
        and pending.get("progress") == "completed"
        and pending.get("id") == operation_id
    ):
        return pending
    return None


def _recover_interrupted_finalization(state: dict) -> str | None:
    if (
        state["pending_operation"] is not None
        or not paths.OPERATION_REQUEST_PATH.is_file()
    ):
        return None
    try:
        handoff = json.loads(paths.OPERATION_REQUEST_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    operation_id = _accepted_request_id(handoff)
    if operation_id is None:
        return None
    try:
        committed = repository.read_committed_state("HEAD")
    except (OSError, UnicodeError, json.JSONDecodeError, RuntimeError, ValueError):
        return None
    pending = _matching_completed_pending(committed, operation_id)
    if pending is not None:
        state["pending_operation"] = copy.deepcopy(pending)
        repository.write_state(state)
        return "retry"
    subject = repository.git("log", "-1", "--format=%s", "HEAD").strip()
    prefix = repository.campaign_commit_message("finalize ")
    if not subject.startswith(prefix):
        return None
    try:
        previous = repository.read_committed_state("HEAD^")
    except (json.JSONDecodeError, RuntimeError, ValueError):
        return None
    pending = _matching_completed_pending(previous, operation_id)
    if pending is None or subject != repository.campaign_commit_message(
        f"finalize {pending['id']}"
    ):
        return None
    repository.push_head()
    if _consume_accepted_request_handoff(operation_id):
        return "published"
    return None


def _execute_inquiry(state: dict, pending: dict) -> int:
    plan = pending["data"]["plan"]

    def apply(current: dict, _result: dict) -> None:
        if plan["action"] == "open":
            current["active_inquiry"] = copy.deepcopy(plan["inquiry"])
            current["counters"]["inquiry"] = int(plan["inquiry"]["id"][1:])
        elif plan["action"] == "reframe":
            inquiry = current["active_inquiry"]
            inquiry["reframes"].append(copy.deepcopy(plan["reframe"]))
            for field in ("question", "goal_connection", "closure_condition"):
                inquiry[field] = plan["reframe"][field]
            inquiry["rationale"] = plan["reframe"]["rationale"]
        else:
            current["active_inquiry"] = None

    result = {
        "status": "completed",
        "action": plan["action"],
        "inquiry_id": (
            plan["inquiry"]["id"] if plan["action"] == "open" else plan["inquiry_id"]
        ),
    }
    if plan["action"] == "close":
        result.update(outcome=plan["outcome"], reason=plan["reason"])
    _complete_operation(state, result, apply)
    return 0


def _execute_checkpoint(state: dict, pending: dict) -> int:
    data = pending["data"]
    _revalidate_frozen_science(data, "scientific session surface")
    if data["scientific_commit"] is None:
        changed_paths = [entry["path"] for entry in data["scientific_manifest"]]
        if changed_paths:
            execution.validate_changed_sources(changed_paths)
        data["scientific_commit"] = repository.publish_scientific_recipe(
            pending["id"], list(data["scientific_paths"])
        )
        pending["progress"] = "checkpoint_recipe_published"
        repository.write_state(state)
    checkpoint = {
        **copy.deepcopy(data["plan"]),
        "scientific_commit": data["scientific_commit"],
    }

    def apply(current: dict, _result: dict) -> None:
        current["pi_checkpoint"] = checkpoint
        current["scientific_session"] = None

    _complete_operation(
        state,
        {"status": "checkpointed", "session_id": checkpoint["session_id"]},
        apply,
        include_in_session=False,
    )
    return 0


def _execute_model_role(state: dict, pending: dict) -> int:
    plan = pending["data"]["plan"]
    candidate = state["candidates"][plan["candidate_id"]]
    publication = pending["data"].get("publication")
    if publication is None:
        destination = repository.durable_artifact_destination(
            campaign_id=repository.current_campaign_id(state),
            origin_operation=candidate["origin_operation"],
            candidate=candidate["name"],
            fingerprint=candidate["fingerprint"],
        )
        publication = {
            "source": candidate["artifact"],
            "destination": repository.repo_relative_path(destination),
            "fingerprint": candidate["fingerprint"],
        }
        pending["data"]["publication"] = publication
        pending["progress"] = "publishing_artifact"
        repository.write_state(state)
    repository.publish_artifact(publication)

    def apply(current: dict, _result: dict) -> None:
        current_candidate = current["candidates"][plan["candidate_id"]]
        current_candidate["artifact"] = publication["destination"]
        roles = current["model_roles"]
        if plan["action"] == "set_working":
            roles["working"] = plan["candidate_id"]
        elif plan["action"] == "set_best_known":
            roles["best_known"] = plan["candidate_id"]
        else:
            roles["retained"][plan["label"]] = plan["candidate_id"]

    _complete_operation(
        state,
        {
            "status": "assigned",
            "action": plan["action"],
            "candidate": plan["candidate_id"],
            "evidence": plan["evidence"],
        },
        apply,
    )
    return 0


def _execute_recipe_restore(state: dict, pending: dict) -> int:
    plan = pending["data"]["plan"]
    if pending["progress"] == "accepted":
        live_plan = protocol.plan_recipe_restore(
            pending["request"]["restore_recipe"], state
        )
        if live_plan != plan:
            raise FrozenOperationMismatch(
                "recipe restoration inputs changed after the operation was accepted"
            )
        _require_matching_manifest(
            pending["data"]["pre_restore_manifest"],
            _scientific_manifest([*plan["restore"], *plan["remove_created"]]),
            "pre-restore scientific surface",
        )
        pending["progress"] = "restoring"
        repository.write_state(state)
    repository.apply_recipe_restore(plan)
    restored = research_config.load_experiment_config()
    if restored != plan["parameters"]:
        raise FrozenOperationMismatch(
            "restored training configuration differs from selected candidate"
        )
    if not repository.recipe_paths_match_commit(plan):
        raise FrozenOperationMismatch(
            "restored scientific surface differs from selected candidate"
        )

    def apply(current: dict, _result: dict) -> None:
        session = current["scientific_session"]
        session["scientific_parent_commit"] = plan["parent"]

    _complete_operation(
        state,
        {
            "status": "restored",
            "candidate": plan["candidate_id"],
            "scientific_commit": plan["parent"],
            "restored_paths": [*plan["restore"], *plan["remove_created"]],
        },
        apply,
    )
    return 0


def _execute_campaign_conclusion(state: dict, pending: dict) -> int:
    terminal = copy.deepcopy(pending["data"]["plan"])

    def apply(current: dict, _result: dict) -> None:
        current["terminal_state"] = terminal
        current["scientific_session"] = None

    _complete_operation(
        state,
        {"status": terminal["status"], "model": terminal["model"]},
        apply,
        include_in_session=False,
    )
    return 0


def _measurement_result(
    spec: dict,
    metrics: dict,
    output_path: Path,
    *,
    semantics: str | None,
) -> dict:
    record = repository.measurement_record(metrics)
    record["evaluation_artifact"] = repository.repo_relative_path(output_path)
    record["evaluation_artifact_fingerprint"] = repository.file_fingerprint(output_path)
    record["model_fingerprint"] = spec["model_fingerprint"]
    if semantics is not None:
        record["evaluation_semantics"] = semantics
    return {
        "instrument": spec["instrument"],
        "candidate": spec["candidate"],
        "candidate_id": spec["candidate_id"],
        "label": spec["label"],
        "metrics": record,
    }


def _expected_measurement_artifact(
    state: dict,
    pending: dict,
    spec: dict,
    *,
    semantics: str | None,
    task_reference_contract: dict | None,
) -> str:
    if spec["instrument"] == "python_module":
        return spec["artifact"]
    campaign_id = repository.current_campaign_id(state)
    if spec["instrument"] == "research_evaluation":
        return repository.repo_relative_path(
            paths.campaign_evaluation_dir(campaign_id)
            / protocol.evaluation_artifact_name(
                pending["id"],
                spec["candidate"],
                int(spec["episodes"]),
                int(spec["seed"]),
                str(semantics),
                campaign_id=campaign_id,
            )
        )
    if not isinstance(task_reference_contract, dict):
        raise FrozenOperationMismatch("accepted task-reference contract is missing")
    return repository.repo_relative_path(
        paths.campaign_evaluation_dir(campaign_id)
        / protocol.task_reference_artifact_name(
            pending["id"],
            spec["candidate"],
            str(task_reference_contract["panel"]),
            campaign_id=campaign_id,
        )
    )


def _validate_partial_measurement(
    state: dict,
    pending: dict,
    spec: dict,
    partial: dict,
    *,
    semantics: str | None,
    task_reference_contract: dict | None,
) -> dict:
    if partial.get("instrument") != spec["instrument"]:
        raise FrozenOperationMismatch("partial measurement instrument changed")
    if partial.get("label") != spec["label"]:
        raise FrozenOperationMismatch("partial measurement label changed")
    metrics = partial.get("metrics")
    if not isinstance(metrics, dict):
        raise FrozenOperationMismatch("partial measurement record is missing")
    expected_artifact = _expected_measurement_artifact(
        state,
        pending,
        spec,
        semantics=semantics,
        task_reference_contract=task_reference_contract,
    )
    if metrics.get("evaluation_artifact") != expected_artifact:
        raise FrozenOperationMismatch("partial measurement artifact changed")
    try:
        evidence = repository.measurement_evidence(metrics)
    except (OSError, TypeError, ValueError) as error:
        raise FrozenOperationMismatch(str(error)) from error
    if spec["instrument"] == "python_module":
        if (
            partial.get("module") != spec["module"]
            or partial.get("args") != spec["args"]
        ):
            raise FrozenOperationMismatch("partial python_module invocation changed")
        return evidence
    for field in ("candidate", "candidate_id"):
        if partial.get(field) != spec[field]:
            raise FrozenOperationMismatch(f"partial measurement {field} changed")
    if metrics.get("model_fingerprint") != spec["model_fingerprint"]:
        raise FrozenOperationMismatch("partial measurement model fingerprint changed")
    if spec["instrument"] == "research_evaluation":
        if metrics.get("evaluation_semantics") != semantics:
            raise FrozenOperationMismatch(
                "partial research evaluation semantics changed"
            )
        expected_panel = {
            "episodes": int(spec["episodes"]),
            "seed": int(spec["seed"]),
        }
    else:
        if not isinstance(task_reference_contract, dict):
            raise FrozenOperationMismatch("accepted task-reference contract is missing")
        expected_panel = {
            "episodes": int(task_reference_contract["episodes"]),
            "seed": int(task_reference_contract["seed"]),
            "panel": task_reference_contract["panel"],
            "panel_version": task_reference_contract["panel_version"],
        }
    for field, expected in expected_panel.items():
        if metrics.get(field) != expected or evidence.get(field) != expected:
            raise FrozenOperationMismatch(
                f"partial measurement {field} differs from its accepted contract"
            )
    return evidence


def execute_measurement(state: dict, pending: dict) -> int:
    data = pending["data"]
    planned = data["measurements"]
    partials = data["partial_results"]
    campaign_id = repository.current_campaign_id(state)
    semantics = data["evaluation_semantics"]
    if (
        semantics is not None
        and protocol.evaluation_semantics_fingerprint() != semantics
    ):
        raise FrozenOperationMismatch(
            "measurement semantics changed after the operation was accepted"
        )
    task_reference_contract = data["task_reference_contract"]
    if (
        task_reference_contract is not None
        and _task_reference_contract() != task_reference_contract
    ):
        raise FrozenOperationMismatch(
            "task-reference contract changed after the operation was accepted"
        )
    _revalidate_module_provenance(data)
    module_provenance = data.get("module_provenance")
    if isinstance(module_provenance, dict):
        scientific_paths = list(module_provenance["scientific_paths"])
        if scientific_paths and module_provenance["scientific_commit"] is None:
            changed_paths = [
                entry["path"] for entry in module_provenance["scientific_manifest"]
            ]
            if changed_paths:
                execution.validate_changed_sources(changed_paths)
            module_provenance["scientific_commit"] = (
                repository.publish_scientific_recipe(pending["id"], scientific_paths)
            )
            repository.write_state(state)
        elif module_provenance["scientific_commit"] is not None:
            repository.require_resolvable_commit(
                str(module_provenance["scientific_commit"])
            )
    if (
        isinstance(module_provenance, dict)
        and module_provenance["campaign_lab_publication"] is None
        and any(
            spec["module"].startswith("research.lab.")
            for spec in planned
            if spec["instrument"] == "python_module"
        )
    ):
        module_provenance["campaign_lab_publication"] = (
            repository.publish_campaign_laboratory(pending["id"])
        )
        repository.write_state(state)
    if len(partials) > len(planned):
        raise FrozenOperationMismatch("too many partial measurement results")
    for index, partial in enumerate(partials):
        _validate_partial_measurement(
            state,
            pending,
            planned[index],
            partial,
            semantics=semantics,
            task_reference_contract=task_reference_contract,
        )
    try:
        for index, spec in enumerate(planned):
            if index < len(partials):
                continue
            if spec["instrument"] == "python_module":
                output_path = repository.resolve_repo_path(spec["artifact"])
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.unlink(missing_ok=True)
                execution.run_module(spec["module"], *spec["args"])
                if not output_path.is_file():
                    raise RuntimeError(
                        "python_module measurement produced no declared artifact"
                    )
                try:
                    metrics = json.loads(output_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as error:
                    raise ValueError(
                        "python_module measurement artifact must contain JSON"
                    ) from error
                if not isinstance(metrics, dict):
                    raise TypeError(
                        "python_module measurement artifact must contain a JSON object"
                    )
                partials.append(
                    {
                        "instrument": "python_module",
                        "module": spec["module"],
                        "args": list(spec["args"]),
                        "label": spec["label"],
                        "metrics": {
                            "evaluation_artifact": spec["artifact"],
                            "evaluation_artifact_fingerprint": (
                                repository.file_fingerprint(output_path)
                            ),
                        },
                    }
                )
                pending["progress"] = f"measured_{len(partials)}_of_{len(planned)}"
                repository.write_state(state)
                continue
            artifact = repository.resolve_repo_path(spec["artifact"])
            if repository.artifact_fingerprint(artifact) != spec["model_fingerprint"]:
                raise FrozenOperationMismatch("measurement model fingerprint changed")
            output_dir = paths.campaign_evaluation_dir(campaign_id)
            output_dir.mkdir(parents=True, exist_ok=True)
            if spec["instrument"] == "research_evaluation":
                output_path = output_dir / protocol.evaluation_artifact_name(
                    pending["id"],
                    spec["candidate"],
                    int(spec["episodes"]),
                    int(spec["seed"]),
                    str(semantics),
                    campaign_id=campaign_id,
                )
                metrics = execution.evaluate_artifact(
                    artifact,
                    int(spec["seed"]),
                    label=spec["label"],
                    episodes=int(spec["episodes"]),
                    output_path=output_path,
                )
                result = _measurement_result(
                    spec, metrics, output_path, semantics=str(semantics)
                )
            else:
                if not isinstance(task_reference_contract, dict):
                    raise FrozenOperationMismatch(
                        "accepted task-reference contract is missing"
                    )
                output_path = output_dir / protocol.task_reference_artifact_name(
                    pending["id"],
                    spec["candidate"],
                    task_reference_contract["panel"],
                    campaign_id=campaign_id,
                )
                metrics = execution.evaluate_artifact(
                    artifact,
                    int(task_reference_contract["seed"]),
                    label=spec["label"],
                    episodes=int(task_reference_contract["episodes"]),
                    output_path=output_path,
                    task_reference=True,
                )
                result = _measurement_result(spec, metrics, output_path, semantics=None)
                result["metrics"]["panel"] = task_reference_contract["panel"]
                result["metrics"]["panel_version"] = task_reference_contract[
                    "panel_version"
                ]
            partials.append(result)
            pending["progress"] = f"measured_{len(partials)}_of_{len(planned)}"
            repository.write_state(state)
    except KeyboardInterrupt:
        console.announce(
            "[runner] Measurement paused; completed results remain in the transaction."
        )
        return 130
    except Exception as error:
        pending["failure"] = str(error)[:500]
        repository.write_state(state)
        raise

    verified_evidence = [
        _validate_partial_measurement(
            state,
            pending,
            spec,
            partial,
            semantics=semantics,
            task_reference_contract=task_reference_contract,
        )
        for spec, partial in zip(planned, partials, strict=True)
    ]
    by_candidate: dict[str, list[dict]] = {}
    for item, evidence in zip(partials, verified_evidence, strict=True):
        if item["instrument"] != "research_evaluation":
            continue
        by_candidate.setdefault(item["candidate"], []).append(evidence)
    comparisons: list[dict] = []
    for frozen in data["paired_comparisons"]:
        shared_seeds = set(frozen["shared_episode_seeds"])

        def contributing_evidence(
            indexes: list[int], shared: set[int] = shared_seeds
        ) -> list[dict]:
            selected: list[dict] = []
            for index in indexes:
                evidence = copy.deepcopy(verified_evidence[index])
                evidence["episode_results"] = [
                    item
                    for item in evidence["episode_results"]
                    if int(item["episode_seed"]) in shared
                ]
                evidence["episodes"] = len(evidence["episode_results"])
                if evidence["episodes"]:
                    selected.append(evidence)
            return selected

        candidate_evidence = contributing_evidence(
            frozen["candidate_measurement_indexes"]
        )
        reference_evidence = contributing_evidence(
            frozen["reference_measurement_indexes"]
        )
        comparison = execution.requested_paired_comparisons(
            {
                "paired_comparisons": [
                    {
                        "candidate": frozen["candidate"],
                        "reference": frozen["reference"],
                    }
                ]
            },
            {
                frozen["candidate"]: candidate_evidence,
                frozen["reference"]: reference_evidence,
            },
        )[0]
        contributing_indexes = list(
            dict.fromkeys(
                [
                    *frozen["candidate_measurement_indexes"],
                    *frozen["reference_measurement_indexes"],
                ]
            )
        )
        comparison.update(
            candidate_model_fingerprint=frozen["candidate_model_fingerprint"],
            reference_model_fingerprint=frozen["reference_model_fingerprint"],
            shared_episode_seeds=list(frozen["shared_episode_seeds"]),
            source_artifacts=[
                partials[index]["metrics"]["evaluation_artifact"]
                for index in contributing_indexes
            ],
        )
        comparisons.append(comparison)
    result = {
        "status": "completed",
        "measurements": copy.deepcopy(partials),
        "paired_comparisons": comparisons,
        "tool_provenance": copy.deepcopy(module_provenance),
    }

    def apply(current: dict, _result: dict) -> None:
        for item in partials:
            if "candidate_id" not in item:
                continue
            candidate = current["candidates"][item["candidate_id"]]
            artifact = item["metrics"]["evaluation_artifact"]
            if artifact not in candidate["evaluation_artifacts"]:
                candidate["evaluation_artifacts"].append(artifact)
        if (
            isinstance(module_provenance, dict)
            and module_provenance["scientific_commit"] is not None
        ):
            current["scientific_session"]["scientific_parent_commit"] = str(
                module_provenance["scientific_commit"]
            )

    _complete_operation(state, result, apply)
    return 0


def _training_log_attempt(operation_id: str, campaign_id: str) -> int:
    directory = paths.TRAINING_LOG_DIR / campaign_id
    pattern = re.compile(rf"^{re.escape(operation_id.lower())}-attempt-(\d+)\.log$")
    attempts = [
        int(match.group(1))
        for path in directory.glob(f"{operation_id.lower()}-attempt-*.log")
        if (match := pattern.match(path.name)) is not None
    ]
    return max(attempts, default=0) + 1


def _candidate_records(
    operation_id: str,
    archived: list[dict],
    config: dict,
    scientific_commit: str,
) -> list[dict]:
    return [
        {
            "id": f"{operation_id}:{item['name']}",
            "artifact": item["artifact"],
            "fingerprint": item["fingerprint"],
            "origin_operation": operation_id,
            "name": item["name"],
            "parameters": copy.deepcopy(config),
            "scientific_commit": scientific_commit,
            "training_steps": int(item["timesteps"]),
            "evaluation_artifacts": [],
        }
        for item in archived
    ]


def execute_training(state: dict, pending: dict) -> int:
    data = pending["data"]
    request = pending["request"]["training"]
    parent_commit = str(data["code_parent_commit"])
    campaign_id = repository.current_campaign_id(state)
    operation_id = pending["id"]
    manifest = data["scientific_manifest"]
    _revalidate_frozen_science(data, "scientific surface")
    if data["scientific_commit"] is None:
        changed_paths = [entry["path"] for entry in manifest]
        if changed_paths:
            execution.validate_changed_sources(changed_paths)
        execution.validate_active_configuration()
        selected_tests = protocol.validation_test_paths(changed_paths)
        if selected_tests:
            execution.run_validation_suites(selected_tests)
        data["scientific_commit"] = repository.publish_scientific_recipe(
            operation_id, list(data["scientific_paths"])
        )
        pending["progress"] = "recipe_published"
        repository.write_state(state)
    else:
        repository.require_resolvable_commit(str(data["scientific_commit"]))

    config = data["effective_parameters"]
    if not isinstance(config, dict):
        raise FrozenOperationMismatch("accepted training has no frozen configuration")
    parent = data["parent"]
    if isinstance(parent, dict):
        parent_artifact = repository.resolve_repo_path(parent["artifact"])
        repository.require_complete_inference_artifact(
            parent_artifact, "frozen training parent"
        )
        if repository.artifact_fingerprint(parent_artifact) != parent["fingerprint"]:
            raise FrozenOperationMismatch("frozen training parent fingerprint changed")
    resume = parent_artifact / "model.zip" if isinstance(parent, dict) else None
    candidate_dir = paths.campaign_candidate_root(campaign_id) / operation_id.lower()
    data["candidate_dir"] = repository.repo_relative_path(candidate_dir)
    archived = data.get("archived_candidates")
    try:
        if archived is None:
            completed = False
            if candidate_dir.exists() and all(
                (candidate_dir / filename).is_file()
                for filename in repository.INFERENCE_ARTIFACT_FILES
            ):
                metadata = json.loads(
                    (candidate_dir / "artifact.json").read_text(encoding="utf-8")
                )
                if bool(metadata.get("completed", True)):
                    execution.validate_reusable_candidate(
                        candidate_dir,
                        timesteps=int(request["steps"]),
                        seed=int(request["seed"]),
                        resume=resume,
                        config=config,
                    )
                    completed = True
            if not completed:
                if candidate_dir.exists():
                    execution.remove_candidate_dir(candidate_dir)
                pending["progress"] = "training_dispatched"
                repository.write_state(state)
                attempt = _training_log_attempt(operation_id, campaign_id)
                execution.train_candidate(
                    candidate_dir,
                    int(request["steps"]),
                    int(request["seed"]),
                    resume,
                    paths.training_log_path(
                        operation_id, attempt, campaign_id=campaign_id
                    ),
                    label=f"training {operation_id}",
                )
            pending["progress"] = "training_completed"
            repository.write_state(state)
            contenders = [
                {**candidate, "kind": "candidate", "evaluations": []}
                for candidate in execution.candidate_directories(candidate_dir)
            ]
            archived = repository.archive_candidates(
                operation_id, contenders, config, campaign_id=campaign_id
            )
            data["archived_candidates"] = copy.deepcopy(archived)
            pending["progress"] = "candidates_archived"
            repository.write_state(state)
    except KeyboardInterrupt:
        console.announce(
            "[runner] Training paused; the accepted transaction will resume."
        )
        return 130
    except Exception as error:
        pending["failure"] = str(error)[:500]
        repository.write_state(state)
        raise

    records = _candidate_records(
        operation_id,
        archived,
        config,
        str(data["scientific_commit"]),
    )
    completed_steps = max(
        (candidate["training_steps"] for candidate in records), default=0
    )
    result = {
        "status": "completed",
        "initialization": request["initialization"],
        "parent": parent["id"] if isinstance(parent, dict) else None,
        "seed": int(request["seed"]),
        "requested_steps": int(request["steps"]),
        "completed_steps": completed_steps,
        "scientific_commit": data["scientific_commit"],
        "mechanical_provenance": {
            "code_parent_commit": parent_commit,
            "changed_files": copy.deepcopy(data["scientific_manifest"]),
        },
        "candidates": [candidate["id"] for candidate in records],
        "learning_dynamics": [
            {
                "candidate": item["id"],
                "training_steps": item["training_steps"],
                "training_success": archived[index].get("training_success"),
                "ep_rew_mean": archived[index].get("ep_rew_mean"),
            }
            for index, item in enumerate(records)
        ],
    }

    def apply(current: dict, _result: dict) -> None:
        for candidate in records:
            current["candidates"][candidate["id"]] = copy.deepcopy(candidate)
        session = current["scientific_session"]
        session["scientific_parent_commit"] = str(data["scientific_commit"])

    _complete_operation(state, result, apply)
    if candidate_dir.exists():
        execution.remove_candidate_dir(candidate_dir)
    return 0


def execute_pending_operation() -> int:
    state = repository.load_state(allow_missing_artifact=True)
    pending = state["pending_operation"]
    if not isinstance(pending, dict):
        raise TypeError("there is no pending Runner operation")
    if pending["failure"] is not None:
        raise ValueError(
            f"pending operation {pending['id']} failed and must be reaccepted "
            "with --reaccept-pending"
        )
    request = pending["request"]
    if _canonical_fingerprint(request) != pending["request_fingerprint"]:
        raise FrozenOperationMismatch("accepted operation request changed")
    _write_accepted_request_handoff(pending)
    if pending["progress"] == "completed":
        _finalize_operation(state, pending)
        return 0
    kind = pending["kind"]
    try:
        if kind == "measurement":
            return execute_measurement(state, pending)
        if kind == "training":
            return execute_training(state, pending)
        if kind == "inquiry":
            return _execute_inquiry(state, pending)
        if kind == "checkpoint":
            return _execute_checkpoint(state, pending)
        if kind == "model_role":
            return _execute_model_role(state, pending)
        if kind == "restore_recipe":
            return _execute_recipe_restore(state, pending)
        if kind == "campaign_conclusion":
            return _execute_campaign_conclusion(state, pending)
        raise RuntimeError(f"unsupported pending operation kind: {kind}")
    except Exception as error:
        if pending["progress"] not in {"result_ready", "completed"}:
            pending["failure"] = str(error)[:500]
            repository.write_state(state)
        raise


def check_operation() -> int:
    try:
        request = json.loads(paths.OPERATION_REQUEST_PATH.read_text(encoding="utf-8"))
        state = repository.load_state(allow_missing_artifact=True)
        kind = protocol.validate_operation_request(request, state)
    except PROPOSAL_ERRORS as error:
        print(f"OPERATION_INVALID: {error}")
        return 1
    print(f"OPERATION_VALID: {kind}")
    return 0


def check_scientific_model_deliverable() -> int:
    try:
        if not paths.SCIENTIFIC_MODEL_PATH.is_file():
            raise FileNotFoundError("research/scientific_model.md is missing")
        if not paths.SCIENTIFIC_MODEL_PATH.read_text(encoding="utf-8").strip():
            raise ValueError("research/scientific_model.md is empty")
    except (OSError, UnicodeError, ValueError) as error:
        print(f"SCIENTIFIC_MODEL_DELIVERABLE_INVALID: {error}")
        return 1
    print("SCIENTIFIC_MODEL_DELIVERABLE_VALID")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-operation", action="store_true")
    parser.add_argument("--execute-pending", action="store_true")
    parser.add_argument(
        "--start-session", choices=("goal_review", "inquiry"), default=None
    )
    parser.add_argument("--session-objective")
    parser.add_argument("--check-scientific-model-deliverable", action="store_true")
    parser.add_argument("--mark-scientific-model-ready", action="store_true")
    parser.add_argument("--reaccept-pending", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check_scientific_model_deliverable:
        return check_scientific_model_deliverable()
    if args.mark_scientific_model_ready:
        if check_scientific_model_deliverable() != 0:
            return 1
        state = repository.load_state(allow_missing_artifact=True)
        repository.require_scientific_model_publication_pending(state)
        repository.commit_paths(
            repository.campaign_commit_message("scientific model"),
            ["research/scientific_model.md"],
        )
        commit = repository.git("rev-parse", "HEAD").strip()
        repository.require_path_at_commit(commit, "research/scientific_model.md")
        repository.mark_scientific_model_ready(state, commit)
        repository.write_state(state)
        if not repository.commit_runner_memory("publish scientific model"):
            repository.push_head()
        return 0
    if args.reaccept_pending:
        pending = reaccept_pending_operation()
        print(
            f"OPERATION_REACCEPTED: {pending['id']} supersedes {pending['supersedes']}"
        )
        return 0
    if args.start_session:
        if not args.session_objective:
            print("ERROR: --start-session requires --session-objective")
            return 1
        state = repository.load_state(allow_missing_artifact=True)
        session = repository.start_scientific_session(
            state, kind=args.start_session, objective=args.session_objective
        )
        repository.write_state(state)
        print(f"SCIENTIFIC_SESSION_STARTED: {session['id']}")
        return 0
    if args.check_operation:
        return check_operation()
    repository.synchronize_operation_log()
    state = repository.load_state(allow_missing_artifact=True)
    finalization = _recover_interrupted_finalization(state)
    if finalization == "published":
        return 0
    if finalization == "retry":
        state = repository.load_state(allow_missing_artifact=True)
    if isinstance(state["pending_operation"], dict):
        if state["pending_operation"]["failure"] is not None:
            print(
                f"ERROR: pending operation {state['pending_operation']['id']} failed; "
                "run --reaccept-pending before execution"
            )
            return 1
        return execute_pending_operation()
    if args.execute_pending:
        print("ERROR: there is no pending Runner operation")
        return 1
    if not paths.OPERATION_REQUEST_PATH.is_file():
        print("ERROR: research/operation_request.json not found")
        return 1
    try:
        request = json.loads(paths.OPERATION_REQUEST_PATH.read_text(encoding="utf-8"))
        accept_operation(request, state)
        return execute_pending_operation()
    except PROPOSAL_ERRORS as error:
        print(f"ERROR: invalid operation: {error}")
        return 1


def run_with_stop_control() -> int:
    with interrupt_on_stop_request():
        return main()


if __name__ == "__main__":
    raise SystemExit(run_with_stop_control())
