"""Transactional Runner for goal-centered scientific operations."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from runner import assessment, console, execution, paths, protocol, repository
from runner.stop_control import interrupt_on_stop_request

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
TIMESTEPS = 120_000


class FrozenOperationMismatch(ValueError):
    """The live request or scientific surface differs from accepted state."""


class _LazyResearchConfig:
    def load_experiment_config(self) -> dict:
        from robot_learning.training import research_config

        return research_config.load_experiment_config()


research_config = _LazyResearchConfig()


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


def _protected_panel_overlap(seed: int, episodes: int) -> bool:
    protocol.require_trusted_assessment_runtime(
        protocol.OFFICIAL_ASSESSMENT_ADAPTER_PATH
    )
    from benchmark.adapters.final_benchmark import (
        research_panel_overlaps_protected,
    )

    return research_panel_overlaps_protected(seed, episodes)


def _task_reference_contract() -> dict:
    return assessment.task_reference_contract()


def _load_experiment_config() -> dict:
    return research_config.load_experiment_config()


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
    if _load_experiment_config() != data["effective_parameters"]:
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
            "effective_parameters": _load_experiment_config(),
            "candidate_dir": None,
            "archived_candidates": None,
            "result": None,
        }
    if kind == "measurement":
        measurement = request["measurement"]
        planned = protocol.planned_measurements(measurement, state)
        protocol.validate_panel_independence(
            measurement,
            protected_overlap=_protected_panel_overlap,
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
                "effective_parameters": _load_experiment_config(),
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
        plan = protocol.plan_checkpoint(request["checkpoint"], state)
        return {
            "plan": plan,
            "code_parent_commit": parent_commit,
            "scientific_manifest": _scientific_manifest(source_changes),
            "scientific_paths": list(changed),
            "effective_parameters": _load_experiment_config(),
            "scientific_commit": None,
            "presentation": _session_completion_presentation(state, session),
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
    plan = protocol.plan_campaign_conclusion(request["campaign_conclusion"], state)
    return {
        "plan": plan,
        "presentation": _session_completion_presentation(state, session),
        "result": None,
    }


def _session_completion_presentation(state: dict, session: dict) -> dict:
    campaign_id = repository.current_campaign_id(state)
    backend_session_id = str(session["backend_session_id"])
    return {
        "campaign_id": campaign_id,
        "session_id": str(session["id"]),
        "session_kind": str(session["kind"]),
        "backend_session_id": backend_session_id,
        "session_usage": console.usage_summary(campaign_id, backend_session_id),
        "campaign_usage": console.usage_summary(campaign_id),
    }


def _validate_new_operation_scientific_delta(state: dict) -> None:
    session = protocol.require_active_session(state)
    parent_commit = str(session["scientific_parent_commit"])
    repository.require_resolvable_commit(parent_commit)
    protocol.validate_research_delta_ownership(
        repository.scientific_delta(parent_commit)
    )


def _training_allocation(request: dict, state: dict) -> int:
    allocation = execution.training_budget(
        TIMESTEPS, request["initialization"], False, 0
    )
    session = protocol.require_active_session(state)
    if session["kind"] == "startup":
        if request["steps"] > allocation:
            raise ValueError(
                f"training allocation is maintainer-owned: startup steps must "
                f"not exceed {allocation:,}; got {request['steps']!r}"
            )
    elif request["steps"] != allocation:
        raise ValueError(
            f"training allocation is maintainer-owned: steps must equal "
            f"{allocation:,}, not {request['steps']!r}"
        )
    return request["steps"]


def _new_pending_operation(
    request: dict,
    state: dict,
    *,
    supersedes: str | None = None,
) -> dict:
    kind = protocol.validate_operation_request(request, state)
    _validate_new_operation_scientific_delta(state)
    if kind == "training":
        _training_allocation(request["training"], state)
    identifier = protocol.allocate_operation_id(kind, state)
    session = protocol.require_active_session(state)
    pending = {
        "id": identifier,
        "kind": kind,
        "session_id": session["id"],
        "inquiry_id": session["inquiry_id"],
        "request": copy.deepcopy(request),
        "request_fingerprint": _canonical_fingerprint(request),
        "progress": "accepted",
        "failure": None,
        "supersedes": supersedes,
        "data": _transaction_data(kind, request, state),
    }
    state["pending_operation"] = pending
    return pending


def _prepare_failed_replacement(request: dict, state: dict) -> tuple[dict, dict]:
    previous = state["pending_operation"]
    if not isinstance(previous, dict):
        raise TypeError("there is no pending Runner operation to replace")
    if not str(previous.get("failure") or "").strip():
        raise ValueError("only a failed Runner operation can be superseded")
    state["pending_operation"] = None
    pending = _new_pending_operation(
        request,
        state,
        supersedes=str(previous["id"]),
    )
    failed_event = _event_for(
        state,
        previous,
        {"status": "failed", "error": previous["failure"]},
        status="failed",
        superseded_by=pending["id"],
    )
    state["operation_events"].append(
        {key: value for key, value in failed_event.items() if key != "campaign_id"}
    )
    repository.validate_research_state(state, allow_missing_artifact=True)
    return pending, failed_event


def replace_failed_operation(
    request: dict,
    state: dict | None = None,
) -> dict:
    original = state or repository.load_state(allow_missing_artifact=True)
    working = copy.deepcopy(original)
    _pending, failed_event = _prepare_failed_replacement(request, working)
    repository.upsert_operation_event(failed_event)
    repository.write_state(working)
    original.clear()
    original.update(copy.deepcopy(working))
    accepted = original["pending_operation"]
    _write_accepted_request_handoff(accepted)
    if not repository.commit_runner_memory(
        f"supersede {accepted['supersedes']} with {accepted['id']}"
    ):
        repository.push_head()
    return accepted


def accept_operation(request: dict, state: dict | None = None) -> dict:
    state = state or repository.load_state(allow_missing_artifact=True)
    existing = state["pending_operation"]
    fingerprint = _canonical_fingerprint(request)
    if isinstance(existing, dict):
        if (
            existing["request_fingerprint"] == fingerprint
            and existing["request"] == request
        ):
            _write_accepted_request_handoff(existing)
            return existing
        if not str(existing.get("failure") or "").strip():
            raise FrozenOperationMismatch(
                "a different Runner operation is already pending"
            )
        return replace_failed_operation(request, state)
    working = copy.deepcopy(state)
    _new_pending_operation(request, working)
    repository.write_state(working)
    state.clear()
    state.update(copy.deepcopy(working))
    accepted = state["pending_operation"]
    _write_accepted_request_handoff(accepted)
    return accepted


def reaccept_pending_operation(state: dict | None = None) -> dict:
    state = state or repository.load_state(allow_missing_artifact=True)
    previous = state["pending_operation"]
    if not isinstance(previous, dict):
        raise TypeError("there is no pending Runner operation to reaccept")
    if not str(previous.get("failure") or "").strip():
        raise ValueError("only a failed Runner operation can be reaccepted")
    return replace_failed_operation(copy.deepcopy(previous["request"]), state)


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
    if pending["kind"] == "measurement":
        _verify_completed_measurement_result(state, pending)
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


def _recover_interrupted_finalization(
    state: dict,
) -> tuple[str, dict | None] | None:
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
        return "retry", None
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
    if pending["kind"] == "measurement":
        _verify_completed_measurement_result(previous, pending)
    repository.push_head()
    if _consume_accepted_request_handoff(operation_id):
        return "published", _completion_presentation(previous, pending)
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
        active = current.get("active_inquiry")
        if (
            checkpoint["inquiry_id"] is None
            and isinstance(active, dict)
            and active.get("opened_in_session") == checkpoint["session_id"]
        ):
            active["handoff_conclusion"] = checkpoint["current_synthesis"]
            active["handoff_question"] = active["question"]
            active["handoff_source_session_id"] = checkpoint["session_id"]
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
    if terminal["status"] != "official_assessment_requested":
        raise ValueError("only an official-assessment request may conclude a campaign")

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
    record["evaluation_artifact_contents"] = repository.measurement_artifact_contents(
        _json_object_artifact(output_path, "measurement artifact")
    )
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


def _python_module_archive_path(
    state: dict,
    pending: dict,
    spec: dict,
    index: int,
) -> Path:
    requested = Path(spec["artifact"])
    label = re.sub(r"[^A-Za-z0-9._-]+", "-", requested.stem).strip("-")
    return paths.campaign_evaluation_dir(repository.current_campaign_id(state)) / (
        f"python-module-{pending['id']}-{index + 1}-{label or 'artifact'}.json"
    )


def _json_object_artifact(path: Path, description: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{description} must contain JSON") from error
    if not isinstance(value, dict):
        raise TypeError(f"{description} must contain a JSON object")
    return value


def _seal_python_module_artifact(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.pending")
    temporary.unlink(missing_ok=True)
    shutil.copyfile(source, temporary)
    if repository.file_fingerprint(temporary) != repository.file_fingerprint(source):
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            "sealed python_module measurement artifact changed while copying"
        )
    temporary.replace(destination)


def _expected_measurement_artifact(
    state: dict,
    pending: dict,
    spec: dict,
    index: int,
    *,
    semantics: str | None,
    task_reference_contract: dict | None,
) -> str:
    if spec["instrument"] == "python_module":
        return repository.repo_relative_path(
            _python_module_archive_path(state, pending, spec, index)
        )
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
    index: int,
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
        index,
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


def _verify_completed_measurement_result(state: dict, pending: dict) -> None:
    data = pending["data"]
    result = data.get("result")
    if not isinstance(result, dict):
        raise FrozenOperationMismatch("completed measurement result is missing")
    measurements = result.get("measurements")
    if not isinstance(measurements, list) or measurements != data["partial_results"]:
        raise FrozenOperationMismatch("completed measurement results changed")
    planned = data["measurements"]
    if len(measurements) != len(planned):
        raise FrozenOperationMismatch("completed measurement count changed")
    for index, (spec, measurement) in enumerate(
        zip(planned, measurements, strict=True)
    ):
        _validate_partial_measurement(
            state,
            pending,
            spec,
            measurement,
            index,
            semantics=data["evaluation_semantics"],
            task_reference_contract=data["task_reference_contract"],
        )


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
            spec["module"].startswith("robot_learning.lab.")
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
            index,
            semantics=semantics,
            task_reference_contract=task_reference_contract,
        )
    try:
        for index, spec in enumerate(planned):
            if index < len(partials):
                continue
            if spec["instrument"] == "python_module":
                archived_path = _python_module_archive_path(state, pending, spec, index)
                if archived_path.is_file():
                    evidence = _json_object_artifact(
                        archived_path,
                        "sealed python_module measurement artifact",
                    )
                else:
                    output_path = repository.resolve_repo_path(spec["artifact"])
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.unlink(missing_ok=True)
                    execution.run_module(spec["module"], *spec["args"])
                    if not output_path.is_file():
                        raise RuntimeError(
                            "python_module measurement produced no declared artifact"
                        )
                    _json_object_artifact(
                        output_path,
                        "python_module measurement artifact",
                    )
                    _seal_python_module_artifact(output_path, archived_path)
                    evidence = _json_object_artifact(
                        archived_path,
                        "sealed python_module measurement artifact",
                    )
                partials.append(
                    {
                        "instrument": "python_module",
                        "module": spec["module"],
                        "args": list(spec["args"]),
                        "label": spec["label"],
                        "metrics": {
                            "evaluation_artifact": repository.repo_relative_path(
                                archived_path
                            ),
                            "evaluation_artifact_fingerprint": (
                                repository.file_fingerprint(archived_path)
                            ),
                            "evaluation_artifact_contents": (
                                repository.measurement_artifact_contents(evidence)
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
                    operation_id=str(pending["id"]),
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
                    operation_id=str(pending["id"]),
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
        pending["failure"] = str(error)
        repository.write_state(state)
        raise

    verified_evidence = []
    for index, (spec, partial) in enumerate(zip(planned, partials, strict=True)):
        verified_evidence.append(
            _validate_partial_measurement(
                state,
                pending,
                spec,
                partial,
                index,
                semantics=semantics,
                task_reference_contract=task_reference_contract,
            )
        )
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


def _ensure_candidate_keys_available(state: dict, candidates: list[dict]) -> None:
    seen: set[str] = set()
    duplicate_ids: set[str] = set()
    for candidate in candidates:
        identifier = candidate["id"]
        if identifier in state["candidates"] or identifier in seen:
            duplicate_ids.add(identifier)
        seen.add(identifier)
    if duplicate_ids:
        raise ValueError(
            "completed training candidate key collision: "
            + ", ".join(sorted(duplicate_ids))
        )


def _saved_component_comparisons(
    state: dict,
    records: list[dict],
    *,
    parent: str | None,
    seed: int,
    requested_steps: int,
) -> dict:
    current_by_steps = {item["training_steps"]: item for item in records}
    saved_cache: dict[str, dict] = {}

    def saved(candidate: dict) -> dict:
        artifact = str(candidate["artifact"])
        if artifact not in saved_cache:
            saved_cache[artifact] = repository.saved_component_fingerprints(
                repository.resolve_repo_path(artifact)
            )
        return saved_cache[artifact]

    events = {
        event["id"]: event
        for event in state["operation_events"]
        if event.get("status") == "completed" and event.get("kind") == "training"
    }
    prior_by_operation: dict[str, list[dict]] = {}
    for candidate in state["candidates"].values():
        prior_by_operation.setdefault(candidate["origin_operation"], []).append(candidate)

    comparisons: list[dict] = []
    for operation_id, prior_candidates in prior_by_operation.items():
        event = events.get(operation_id)
        if event is None:
            continue
        prior_by_steps = {
            candidate["training_steps"]: candidate for candidate in prior_candidates
        }
        corresponding_steps = sorted(set(current_by_steps) & set(prior_by_steps))
        if not corresponding_steps:
            continue
        component_counts = {
            name: {"compared": 0, "equal": 0}
            for name in repository.SAVED_COMPONENT_NAMES
        }
        runtime_counts = {"compared": 0, "equal": 0}
        exact_matches: list[dict] = []
        for training_steps in corresponding_steps:
            current = current_by_steps[training_steps]
            prior = prior_by_steps[training_steps]
            current_saved = saved(current)
            prior_saved = saved(prior)
            checkpoint_exact = True
            for name in repository.SAVED_COMPONENT_NAMES:
                current_component = current_saved["components"][name]
                prior_component = prior_saved["components"][name]
                if (
                    current_component["status"] != "available"
                    or prior_component["status"] != "available"
                ):
                    checkpoint_exact = False
                    continue
                component_counts[name]["compared"] += 1
                if current_component["sha256"] == prior_component["sha256"]:
                    component_counts[name]["equal"] += 1
                else:
                    checkpoint_exact = False
            current_runtime = current_saved["runtime"]
            prior_runtime = prior_saved["runtime"]
            if (
                current_runtime["status"] == "available"
                and prior_runtime["status"] == "available"
            ):
                runtime_counts["compared"] += 1
                if current_runtime["sha256"] == prior_runtime["sha256"]:
                    runtime_counts["equal"] += 1
            if checkpoint_exact:
                exact_matches.append(
                    {
                        "training_steps": training_steps,
                        "candidate": current["id"],
                        "prior_candidate": prior["id"],
                    }
                )
        prior_result = event["result"]
        comparisons.append(
            {
                "operation": operation_id,
                "context": {
                    "parent": prior_result["parent"],
                    "seed": prior_result["seed"],
                    "requested_steps": prior_result["requested_steps"],
                },
                "current_checkpoint_count": len(current_by_steps),
                "prior_checkpoint_count": len(prior_by_steps),
                "corresponding_checkpoint_count": len(corresponding_steps),
                "step_sets_equal": set(current_by_steps) == set(prior_by_steps),
                "components": component_counts,
                "runtime": runtime_counts,
                "exact_component_matches": exact_matches,
            }
        )
    return {
        "schema_version": 1,
        "scope": "exact_serialized_components",
        "current_context": {
            "parent": parent,
            "seed": seed,
            "requested_steps": requested_steps,
        },
        "comparisons": comparisons,
    }


def execute_training(state: dict, pending: dict) -> int:
    data = pending["data"]
    request = pending["request"]["training"]
    timesteps = int(request["steps"])
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
                        timesteps=timesteps,
                        seed=int(request["seed"]),
                        resume=resume,
                        config=config,
                    )
                    completed = True
            if not completed:
                timesteps = _training_allocation(request, state)
                if candidate_dir.exists():
                    execution.remove_candidate_dir(candidate_dir)
                pending["progress"] = "training_dispatched"
                repository.write_state(state)
                attempt = _training_log_attempt(operation_id, campaign_id)
                execution.train_candidate(
                    candidate_dir,
                    timesteps,
                    int(request["seed"]),
                    resume,
                    paths.training_log_path(
                        operation_id, attempt, campaign_id=campaign_id
                    ),
                    operation_id,
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
        pending["failure"] = str(error)
        repository.write_state(state)
        raise

    repository.persist_saved_components_inventory(
        operation_id, archived, campaign_id=campaign_id
    )
    records = _candidate_records(
        operation_id,
        archived,
        config,
        str(data["scientific_commit"]),
    )
    _ensure_candidate_keys_available(state, records)
    completed_steps = max(
        (candidate["training_steps"] for candidate in records), default=0
    )
    result = {
        "status": "completed",
        "initialization": request["initialization"],
        "parent": parent["id"] if isinstance(parent, dict) else None,
        "seed": int(request["seed"]),
        "requested_steps": timesteps,
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
        "saved_component_comparisons": _saved_component_comparisons(
            state,
            records,
            parent=parent["id"] if isinstance(parent, dict) else None,
            seed=int(request["seed"]),
            requested_steps=timesteps,
        ),
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


def _operation_subject(pending: dict) -> str:
    kind = str(pending["kind"])
    plan = pending["data"].get("plan")
    if kind == "inquiry" and isinstance(plan, dict):
        inquiry_id = (
            plan.get("inquiry", {}).get("id")
            if plan.get("action") == "open"
            else plan.get("inquiry_id")
        )
        return f"{inquiry_id} inquiry" if inquiry_id else "inquiry"
    if kind == "checkpoint":
        session_id = plan.get("session_id") if isinstance(plan, dict) else None
        return f"{session_id} session summary" if session_id else "session summary"
    if kind == "campaign_conclusion":
        return "campaign decision"
    if kind == "model_role":
        return "model role"
    if kind == "restore_recipe":
        return "recipe restore"
    return f"{pending['id']} {kind.replace('_', ' ')}"


def _scientific_delta_lines(pending: dict) -> list[str]:
    data = pending.get("data") or {}
    provenance = data.get("module_provenance")
    if not isinstance(provenance, dict):
        provenance = {}
    paths_to_report = data.get("scientific_paths") or provenance.get("scientific_paths")
    if not isinstance(paths_to_report, list) or not paths_to_report:
        return []
    return [
        f"Scientific file changed: {repository.resolve_repo_path(str(relative_value))}"
        for relative_value in paths_to_report
    ]


def _operation_request_detail(pending: dict) -> str:
    request = pending["request"][pending["kind"]]
    kind = pending["kind"]
    if kind == "training":
        return "\n".join(
            (
                *_scientific_delta_lines(pending),
                f"Why: {request['description']}",
                f"Rationale: {request['rationale']}",
                (
                    f"Plan: {int(request['steps']):,} steps | "
                    f"seed {int(request['seed'])} | {request['initialization']}"
                ),
            )
        )
    if kind == "measurement":
        lines = [
            f"Why: {request['description']}",
            f"Rationale: {request['rationale']}",
        ]
        for index, measurement in enumerate(request["measurements"], start=1):
            instrument = str(measurement["instrument"]).replace("_", " ")
            parts = [
                f"Panel {index}: {instrument}",
                str(measurement.get("candidate") or measurement.get("module") or ""),
            ]
            if measurement.get("episodes") is not None:
                parts.append(f"{int(measurement['episodes'])} episodes")
            if measurement.get("seed") is not None:
                parts.append(f"seed {int(measurement['seed'])}")
            if measurement.get("label"):
                parts.append(str(measurement["label"]))
            lines.append(" | ".join(part for part in parts if part))
        for comparison in request.get("paired_comparisons", []):
            lines.append(
                f"Compare: {comparison['candidate']} vs {comparison['reference']}"
            )
        lines = [*_scientific_delta_lines(pending), *lines]
        return "\n".join(lines)
    if kind == "inquiry":
        return str(request["action"])
    if kind == "model_role":
        return f"{request['action']} | {request['candidate']}"
    if kind == "restore_recipe":
        return str(request["candidate"])
    if kind == "campaign_conclusion":
        return str(request["action"])
    if kind == "checkpoint":
        return "\n".join(_scientific_delta_lines(pending))
    return ""


def _operation_completion_detail(pending: dict) -> str:
    result = pending["data"].get("result") or {}
    kind = pending["kind"]
    parts: list[str] = []
    if kind == "measurement":
        for index, measurement in enumerate(result.get("measurements", []), start=1):
            metrics = measurement.get("metrics") or {}
            row = [
                f"Result {index}: {measurement.get('candidate', '')}",
                str(measurement.get("instrument", "")).replace("_", " "),
            ]
            if metrics.get("success_percent") is not None:
                row.append(f"success {float(metrics['success_percent']):.1f}%")
            if metrics.get("episodes") is not None:
                row.append(f"{int(metrics['episodes'])} episodes")
            parts.append(" | ".join(part for part in row if part))
        comparisons = len(result.get("paired_comparisons", []))
        if comparisons:
            parts.append(f"Paired comparisons: {comparisons}")
    elif kind == "training":
        parts.append(f"{int(result.get('completed_steps', 0)):,} steps")
        dynamics = result.get("learning_dynamics") or []
        for item in dynamics:
            parts.append(
                f"{item['candidate']} | steps {int(item['training_steps']):,} | "
                f"reward {item.get('ep_rew_mean')} | "
                f"success {item.get('training_success')}"
            )
    elif kind == "model_role":
        parts.append(f"{result.get('action')} | {result.get('candidate')}")
    elif kind == "restore_recipe":
        parts.append(str(result.get("candidate", "")))
    return "\n".join(part for part in parts if part)


def _completion_presentation(state: dict, pending: dict) -> dict:
    presentation = {
        "campaign_id": repository.current_campaign_id(state),
        "kind": str(pending["kind"]),
        "pending": pending,
        "session_id": str(pending["session_id"]),
    }
    stored = pending["data"].get("presentation")
    if isinstance(stored, dict):
        presentation.update(copy.deepcopy(stored))
    return presentation


def _announce_consequential_completion(presentation: dict) -> None:
    pending = copy.deepcopy(presentation["pending"])
    result = pending["data"].get("result") or {}
    kind = presentation["kind"]
    if kind == "inquiry":
        action = str(result.get("action", "")).upper()
        inquiry_id = str(result.get("inquiry_id", ""))
        detail = (
            str(result.get("outcome") or result.get("reason") or "")
            if action == "CLOSE"
            else ""
        )
        console.boundary("inquiry", action, inquiry_id, detail)
    elif kind == "checkpoint":
        session_id = str(result.get("session_id", ""))
        plan = pending["data"].get("plan") or {}
        console.announce(f"[session] SUMMARY SAVED | {session_id}")
        console.boundary(
            "session",
            "END",
            f"{presentation['session_id']} "
            f"{str(presentation['session_kind']).replace('_', ' ')}",
            "\n".join(
                (
                    f"Outcome: {plan.get('current_synthesis', 'Session summary saved.')}",
                    "Next question: "
                    + str(
                        plan.get(
                            "next_question",
                            "No next inquiry question was recorded.",
                        )
                    ),
                    "Next: "
                    + str(
                        plan.get(
                            "next_direction_or_closure",
                            "Continue from the durable session summary.",
                        )
                    ),
                    f"Usage: {presentation['session_usage']}",
                )
            ),
        )
    elif kind == "campaign_conclusion":
        plan = pending["data"].get("plan") or {}
        next_transition = (
            "Run the protected official assessment."
            if result.get("status") == "official_assessment_requested"
            else "End the campaign."
        )
        console.boundary(
            "session",
            "END",
            f"{presentation['session_id']} "
            f"{str(presentation['session_kind']).replace('_', ' ')}",
            "\n".join(
                (
                    f"Outcome: {plan.get('reason', 'Campaign decision recorded.')}",
                    f"Next: {next_transition}",
                    f"Usage: {presentation['session_usage']}",
                )
            ),
        )
        status = str(result.get("status", "")).replace("_", " ")
        action = "END" if result.get("status") == "no_credible_route" else "DECISION"
        console.boundary(
            "campaign",
            action,
            status,
            presentation["campaign_usage"],
        )


def _announce_completed_operation(presentation: dict) -> None:
    pending = copy.deepcopy(presentation["pending"])
    console.boundary(
        "operation",
        "COMPLETE",
        _operation_subject(pending),
        _operation_completion_detail(pending),
    )
    _announce_consequential_completion(presentation)


def _campaign_resource_summary(state: dict) -> str:
    completed = [
        event for event in state["operation_events"] if event["status"] == "completed"
    ]
    measurements = sum(event["kind"] == "measurement" for event in completed)
    training = sum(event["kind"] == "training" for event in completed)
    return (
        f"inquiries {int(state['counters']['inquiry'])}/"
        f"{int(state['campaign']['max_inquiries'])} | "
        f"sessions {int(state['counters']['session'])} | "
        f"measurements {measurements} | training {training} | "
        f"candidates {len(state['candidates'])}"
    )


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
    if pending["kind"] == "training" and pending["progress"] in {
        "accepted",
        "recipe_published",
        "training_dispatched",
    }:
        _training_allocation(request["training"], state)
    _write_accepted_request_handoff(pending)
    subject = _operation_subject(pending)
    detail = _operation_request_detail(pending)
    presentation = _completion_presentation(state, pending)
    action = "REQUEST" if pending["progress"] == "accepted" else "RESUME"
    console.boundary("operation", action, subject, detail)
    kind = pending["kind"]
    try:
        if pending["progress"] == "completed":
            _finalize_operation(state, pending)
            _announce_completed_operation(presentation)
            return 0
        console.boundary("operation", "START", subject)
        if kind == "measurement":
            exit_code = execute_measurement(state, pending)
        elif kind == "training":
            exit_code = execute_training(state, pending)
        elif kind == "inquiry":
            exit_code = _execute_inquiry(state, pending)
        elif kind == "checkpoint":
            exit_code = _execute_checkpoint(state, pending)
        elif kind == "model_role":
            exit_code = _execute_model_role(state, pending)
        elif kind == "restore_recipe":
            exit_code = _execute_recipe_restore(state, pending)
        elif kind == "campaign_conclusion":
            exit_code = _execute_campaign_conclusion(state, pending)
        else:
            raise RuntimeError(f"unsupported pending operation kind: {kind}")
    except Exception as error:
        publication_failure = pending["progress"] in {"result_ready", "completed"}
        if not publication_failure:
            pending["failure"] = str(error)
            repository.write_state(state)
        console.boundary(
            "error",
            "PUBLICATION FAILED" if publication_failure else "OPERATION FAILED",
            subject,
            str(error),
        )
        raise
    if exit_code == 130:
        console.boundary("warning", "OPERATION PAUSED", subject)
        return exit_code
    _announce_completed_operation(presentation)
    return exit_code


def check_operation() -> int:
    try:
        request = json.loads(paths.OPERATION_REQUEST_PATH.read_text(encoding="utf-8"))
        state = repository.load_state(allow_missing_artifact=True)
        working = copy.deepcopy(state)
        existing = working["pending_operation"]
        if isinstance(existing, dict):
            if (
                existing["request_fingerprint"] == _canonical_fingerprint(request)
                and existing["request"] == request
            ):
                kind = str(existing["kind"])
            elif str(existing.get("failure") or "").strip():
                pending, _failed_event = _prepare_failed_replacement(request, working)
                kind = str(pending["kind"])
            else:
                raise FrozenOperationMismatch(
                    "a different Runner operation is already pending"
                )
        else:
            pending = _new_pending_operation(request, working)
            repository.validate_research_state(working, allow_missing_artifact=True)
            kind = str(pending["kind"])
        if kind == "training":
            _training_allocation(request["training"], working)
    except PROPOSAL_ERRORS as error:
        print(f"OPERATION_INVALID: {error}")
        return 1
    print(f"OPERATION_VALID: {kind}")
    return 0


def check_scientific_model_deliverable(*, quiet: bool = False) -> int:
    try:
        if not paths.SCIENTIFIC_MODEL_PATH.is_file():
            raise FileNotFoundError("pi_workspace/scientific_model.md is missing")
        text = paths.SCIENTIFIC_MODEL_PATH.read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError("pi_workspace/scientific_model.md is empty")
        for heading in (
            "Established facts",
            "Physical consequences",
            "Unknowns",
            "Decision-relevant synthesis",
        ):
            match = re.search(
                rf"(?ms)^## {re.escape(heading)}\s+(.*?)(?=^## |\Z)",
                text,
            )
            if not match or not match.group(1).strip():
                raise ValueError(
                    f"pi_workspace/scientific_model.md requires a substantive "
                    f"## {heading} section"
                )
    except (OSError, UnicodeError, ValueError) as error:
        print(f"SCIENTIFIC_MODEL_DELIVERABLE_INVALID: {error}")
        return 1
    if not quiet:
        print("SCIENTIFIC_MODEL_DELIVERABLE_VALID")
    return 0


def official_assessment_progress(completed: int, total: int) -> None:
    percent = 100 * completed // total if total else 0
    console.progress(f"ASSESS | {completed}/{total} | {percent}%")


def _official_assessment_event(state: dict) -> dict:
    for event in reversed(state["operation_events"]):
        if (
            event["kind"] == "campaign_conclusion"
            and event["request"].get("action") == "request_official_assessment"
        ):
            return event
    raise RuntimeError("the official assessment request event is missing")


def _persist_official_assessment_transition(state: dict) -> None:
    assessment = state["official_assessment"]
    if not isinstance(assessment, dict):
        raise TypeError("the official assessment result is missing")
    terminal = state["terminal_state"]
    terminal["status"] = f"official_assessment_{assessment['status']}"
    event = _official_assessment_event(state)
    event["result"] = {
        "status": terminal["status"],
        "model": assessment["model"],
    }
    event["completed_at"] = assessment["completed_at"]
    state["last_verdict"] = f"official assessment {assessment['summary']}"
    repository.write_state(state)
    repository.upsert_operation_event(
        {
            "campaign_id": repository.current_campaign_id(state),
            **copy.deepcopy(event),
        }
    )


def _validate_official_assessment_artifact(
    candidate: dict, existing: dict | None = None
) -> Path:
    if isinstance(existing, dict):
        if existing["artifact"] != candidate["artifact"]:
            raise ValueError("the assessed artifact identity changed")
        if existing["fingerprint"] != candidate["fingerprint"]:
            raise ValueError("the assessed artifact fingerprint changed")
        expected_fingerprint = existing["fingerprint"]
    else:
        expected_fingerprint = candidate["fingerprint"]
    artifact = repository.resolve_repo_path(candidate["artifact"])
    repository.require_complete_inference_artifact(
        artifact, "official-assessment model"
    )
    if repository.artifact_fingerprint(artifact) != expected_fingerprint:
        raise ValueError("official-assessment model fingerprint changed")
    return artifact


def run_official_assessment() -> int:
    state = repository.load_state(allow_missing_artifact=True)
    terminal = state["terminal_state"]
    if not isinstance(terminal, dict) or not terminal["status"].startswith(
        "official_assessment_"
    ):
        raise ValueError("there is no requested official assessment")
    candidate = state["candidates"].get(terminal["model"])
    if not isinstance(candidate, dict):
        raise TypeError("the requested official-assessment model is unavailable")
    console.boundary("assessment", "START", "official", str(candidate["id"]))
    existing = state["official_assessment"]
    if isinstance(existing, dict):
        if existing["model"] != candidate["id"]:
            raise ValueError("the recorded official assessment names another model")
        _validate_official_assessment_artifact(candidate, existing)
        _persist_official_assessment_transition(state)
        if existing["status"] == "passed" and not paths.GOAL_PATH.is_file():
            paths.GOAL_PATH.write_text(
                f"Goal reached with {candidate['id']}.\n", encoding="utf-8"
            )
        if not repository.commit_runner_memory("record official assessment"):
            repository.push_head()
        console.boundary(
            "assessment",
            "COMPLETE",
            str(existing["status"]).upper(),
            str(existing["summary"]),
        )
        console.boundary(
            "campaign",
            "END",
            f"official assessment {existing['status']}",
            console.usage_summary(repository.current_campaign_id(state)),
        )
        return 0
    artifact = _validate_official_assessment_artifact(candidate)

    metrics = assessment.evaluate_official_model(
        artifact / "model.zip",
        progress_callback=official_assessment_progress,
    )
    _validate_official_assessment_artifact(candidate)
    passed = bool(metrics["goal_reached"])
    facts = ["goal reached" if passed else "goal not reached"]
    if metrics.get("success_percent") is not None:
        facts.append(f"success {float(metrics['success_percent']):.1f}%")
    if metrics.get("episodes") is not None:
        facts.append(f"{int(metrics['episodes'])} episodes")
    summary = "; ".join(facts)
    state["official_assessment"] = {
        "status": "passed" if passed else "failed",
        "model": candidate["id"],
        "artifact": candidate["artifact"],
        "fingerprint": candidate["fingerprint"],
        "summary": summary,
        "completed_at": _now(),
    }
    _persist_official_assessment_transition(state)
    if passed:
        paths.GOAL_PATH.write_text(
            f"Goal reached with {candidate['id']}.\n", encoding="utf-8"
        )
    if not repository.commit_runner_memory("record official assessment"):
        repository.push_head()
    console.boundary(
        "assessment",
        "COMPLETE",
        "PASSED" if passed else "FAILED",
        summary,
    )
    console.boundary(
        "campaign",
        "END",
        f"official assessment {'passed' if passed else 'failed'}",
        console.usage_summary(repository.current_campaign_id(state)),
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timesteps", type=int, default=TIMESTEPS)
    parser.add_argument("--check-operation", action="store_true")
    parser.add_argument("--execute-pending", action="store_true")
    parser.add_argument(
        "--start-session", choices=("startup", "goal_review", "inquiry"), default=None
    )
    parser.add_argument("--session-objective")
    parser.add_argument("--backend-session-id")
    parser.add_argument("--backend-adapter")
    parser.add_argument("--backend-model")
    parser.add_argument("--backend-reasoning")
    parser.add_argument("--validate-session-backend", action="store_true")
    parser.add_argument("--max-inquiries", type=int)
    parser.add_argument("--synchronize-max-inquiries", type=int)
    parser.add_argument("--check-scientific-model-deliverable", action="store_true")
    parser.add_argument("--mark-scientific-model-ready", action="store_true")
    parser.add_argument("--reaccept-pending", action="store_true")
    parser.add_argument("--run-official-assessment", action="store_true")
    args = parser.parse_args()
    if args.timesteps <= 0:
        parser.error("--timesteps must be positive")
    return args


def main() -> int:
    global TIMESTEPS
    args = parse_args()
    TIMESTEPS = args.timesteps
    if args.validate_session_backend:
        if not all(
            (
                args.backend_adapter,
                args.backend_model,
                args.backend_reasoning,
            )
        ):
            raise ValueError(
                "session backend validation requires adapter, model, and reasoning"
            )
        state = repository.load_state(allow_missing_artifact=True)
        repository.require_scientific_session_backend(
            state,
            adapter=args.backend_adapter,
            model=args.backend_model,
            reasoning=args.backend_reasoning,
        )
        return 0
    if args.synchronize_max_inquiries is not None:
        state = repository.load_state(allow_missing_artifact=True)
        changed = repository.synchronize_max_inquiries(
            state, args.synchronize_max_inquiries
        )
        if changed:
            repository.write_state(state)
        return 0
    if args.check_scientific_model_deliverable:
        return check_scientific_model_deliverable()
    if args.mark_scientific_model_ready:
        if check_scientific_model_deliverable(quiet=True) != 0:
            return 1
        state = repository.load_state(allow_missing_artifact=True)
        repository.require_scientific_model_publication_pending(state)
        repository.commit_paths(
            repository.campaign_commit_message("scientific model"),
            ["pi_workspace/scientific_model.md"],
        )
        commit = repository.git("rev-parse", "HEAD").strip()
        repository.require_path_at_commit(commit, "pi_workspace/scientific_model.md")
        repository.mark_scientific_model_ready(state, commit)
        repository.write_state(state)
        if not repository.commit_runner_memory("publish scientific model"):
            repository.push_head()
        console.boundary("validation", "SCIENTIFIC MODEL VALIDATED")
        return 0
    if args.reaccept_pending:
        pending = reaccept_pending_operation()
        console.boundary(
            "operation",
            "REACCEPTED",
            _operation_subject(pending),
            f"supersedes {pending['supersedes']}",
        )
        return 0
    if args.run_official_assessment:
        return run_official_assessment()
    if args.start_session:
        if not args.session_objective:
            print("ERROR: --start-session requires --session-objective")
            return 1
        if not args.backend_session_id:
            print("ERROR: --start-session requires --backend-session-id")
            return 1
        if not all(
            (
                args.backend_adapter,
                args.backend_model,
                args.backend_reasoning,
            )
        ):
            print(
                "ERROR: --start-session requires --backend-adapter, "
                "--backend-model, and --backend-reasoning"
            )
            return 1
        state = repository.load_state(allow_missing_artifact=True)
        if args.max_inquiries is not None:
            repository.synchronize_max_inquiries(state, args.max_inquiries)
        session = repository.start_scientific_session(
            state,
            kind=args.start_session,
            objective=args.session_objective,
            backend_session_id=args.backend_session_id,
            backend_adapter=args.backend_adapter,
            backend_model=args.backend_model,
            backend_reasoning=args.backend_reasoning,
        )
        repository.write_state(state)
        console.boundary(
            "session",
            "START",
            f"{session['id']} {session['kind'].replace('_', ' ')}",
            f"Objective: {session['objective']}",
        )
        if session["kind"] == "goal_review":
            console.boundary(
                "campaign",
                "GOAL REVIEW",
                _campaign_resource_summary(state),
                console.usage_summary(repository.current_campaign_id(state)),
            )
        return 0
    if args.check_operation:
        return check_operation()
    repository.synchronize_operation_log()
    state = repository.load_state(allow_missing_artifact=True)
    finalization = _recover_interrupted_finalization(state)
    if finalization is not None and finalization[0] == "published":
        presentation = finalization[1]
        if not isinstance(presentation, dict):
            raise TypeError("published finalization is missing completion presentation")
        _announce_completed_operation(presentation)
        return 0
    if finalization is not None and finalization[0] == "retry":
        state = repository.load_state(allow_missing_artifact=True)
    if isinstance(state["pending_operation"], dict):
        if state["pending_operation"]["failure"] is not None:
            if not paths.OPERATION_REQUEST_PATH.is_file():
                print(
                    f"ERROR: pending operation {state['pending_operation']['id']} "
                    "failed; repair it with --reaccept-pending or write a valid "
                    "replacement operation request"
                )
                return 1
            try:
                request = json.loads(
                    paths.OPERATION_REQUEST_PATH.read_text(encoding="utf-8")
                )
                if _accepted_request_id(request) == state["pending_operation"]["id"]:
                    print(
                        f"ERROR: pending operation "
                        f"{state['pending_operation']['id']} failed; run "
                        "--reaccept-pending after implementation repair or replace "
                        "pi_workspace/operation_request.json"
                    )
                    return 1
                accept_operation(request, state)
                return execute_pending_operation()
            except PROPOSAL_ERRORS as error:
                print(f"ERROR: invalid replacement operation: {error}")
                return 1
        return execute_pending_operation()
    if args.execute_pending:
        print("ERROR: there is no pending Runner operation")
        return 1
    if not paths.OPERATION_REQUEST_PATH.is_file():
        print("ERROR: pi_workspace/operation_request.json not found")
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
