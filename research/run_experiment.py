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
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


class FrozenOperationMismatch(ValueError):
    """The live request or scientific surface differs from accepted state."""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _canonical_fingerprint(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
            "recovery_candidate": None,
            "archived_candidates": None,
            "result": None,
            "last_error": None,
        }
    if kind == "measurement":
        measurement = request["measurement"]
        protocol.validate_panel_independence(
            measurement,
            protocol.recorded_research_panels(state),
            protected_overlap=_protected_panel_overlap(),
        )
        return {
            "measurements": protocol.planned_measurements(measurement, state),
            "evaluation_semantics": protocol.evaluation_semantics_fingerprint(),
            "tool_provenance": None,
            "partial_results": [],
            "result": None,
            "last_error": None,
        }
    if kind == "inquiry":
        return {"plan": protocol.plan_inquiry_operation(request["inquiry"], state)}
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
        }
    if kind == "model_role":
        return {
            "plan": protocol.plan_model_role(request["model_role"], state),
            "publication": None,
        }
    if kind == "restore_recipe":
        return {"plan": protocol.plan_recipe_restore(request["restore_recipe"], state)}
    return {
        "plan": protocol.plan_campaign_conclusion(request["campaign_conclusion"], state)
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
        "data": _transaction_data(kind, request, state),
    }
    state["pending_operation"] = pending
    repository.write_state(state)
    return pending


def _event_for(state: dict, pending: dict, result: dict) -> dict:
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
    paths.OPERATION_REQUEST_PATH.unlink(missing_ok=True)
    state["pending_operation"] = None
    repository.write_state(state)
    if not repository.commit_runner_memory(f"finalize {pending['id']}"):
        repository.push_head()


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
    if data["scientific_commit"] is None:
        _require_matching_manifest(
            data["scientific_manifest"],
            _current_scientific_manifest(data["code_parent_commit"]),
            "scientific session surface",
        )
        changed_paths = [entry["path"] for entry in data["scientific_manifest"]]
        current_parameters = research_config.load_experiment_config()
        if current_parameters != data["effective_parameters"]:
            raise FrozenOperationMismatch(
                "scientific session parameters changed after checkpoint acceptance"
            )
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
    pending["progress"] = "restoring"
    repository.write_state(state)
    repository.apply_recipe_restore(plan)
    research_config.write_experiment_config(copy.deepcopy(plan["parameters"]))
    restored = research_config.load_experiment_config()
    if restored != plan["parameters"]:
        raise FrozenOperationMismatch(
            "restored training configuration differs from selected candidate"
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


def execute_measurement(state: dict, pending: dict) -> int:
    from robot_learning.scenario.task_reference import task_reference_panel

    data = pending["data"]
    planned = data["measurements"]
    partials = data["partial_results"]
    campaign_id = repository.current_campaign_id(state)
    semantics = str(data["evaluation_semantics"])
    if protocol.evaluation_semantics_fingerprint() != semantics:
        raise FrozenOperationMismatch(
            "measurement semantics changed after the operation was accepted"
        )
    if data["tool_provenance"] is None:
        data["tool_provenance"] = repository.publish_campaign_laboratory(pending["id"])
        repository.write_state(state)
    panel = task_reference_panel()
    try:
        for index, spec in enumerate(planned):
            if index < len(partials):
                continue
            if spec["instrument"] == "python_module":
                output_path = repository.resolve_repo_path(spec["artifact"])
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.unlink(missing_ok=True)
                stdout = execution.run_module(spec["module"], *spec["args"])
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
                partials.append(
                    {
                        "instrument": "python_module",
                        "module": spec["module"],
                        "args": list(spec["args"]),
                        "label": spec["label"],
                        "stdout": stdout,
                        "metrics": {
                            "evaluation_artifact": spec["artifact"],
                            "evaluation_artifact_fingerprint": (
                                repository.file_fingerprint(output_path)
                            ),
                            "data": metrics,
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
                    semantics,
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
                    spec, metrics, output_path, semantics=semantics
                )
            else:
                output_path = output_dir / protocol.task_reference_artifact_name(
                    pending["id"],
                    spec["candidate"],
                    panel["panel"],
                    campaign_id=campaign_id,
                )
                metrics = execution.evaluate_artifact(
                    artifact,
                    int(panel["seed"]),
                    label=spec["label"],
                    episodes=int(panel["episodes"]),
                    output_path=output_path,
                    task_reference=True,
                )
                result = _measurement_result(spec, metrics, output_path, semantics=None)
                result["metrics"]["panel"] = panel["panel"]
                result["metrics"]["panel_version"] = panel["panel_version"]
            partials.append(result)
            pending["progress"] = f"measured_{len(partials)}_of_{len(planned)}"
            repository.write_state(state)
    except KeyboardInterrupt:
        console.announce(
            "[runner] Measurement paused; completed results remain in the transaction."
        )
        return 130
    except Exception as error:
        data["last_error"] = str(error)[:500]
        repository.write_state(state)
        raise

    by_candidate: dict[str, list[dict]] = {}
    for item in partials:
        if item["instrument"] != "research_evaluation":
            continue
        by_candidate.setdefault(item["candidate"], []).append(
            repository.measurement_evidence(item["metrics"])
        )
    comparisons = execution.requested_paired_comparisons(
        pending["request"]["measurement"], by_candidate
    )
    result = {
        "status": "completed",
        "measurements": copy.deepcopy(partials),
        "paired_comparisons": comparisons,
        "tool_provenance": copy.deepcopy(data["tool_provenance"]),
    }

    def apply(current: dict, _result: dict) -> None:
        for item in partials:
            if "candidate_id" not in item:
                continue
            candidate = current["candidates"][item["candidate_id"]]
            artifact = item["metrics"]["evaluation_artifact"]
            if artifact not in candidate["evaluation_artifacts"]:
                candidate["evaluation_artifacts"].append(artifact)

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
    if data["scientific_commit"] is None:
        _require_matching_manifest(
            manifest,
            _current_scientific_manifest(parent_commit),
            "scientific surface",
        )
        changed_paths = [entry["path"] for entry in manifest]
        if changed_paths:
            execution.validate_changed_sources(changed_paths)
        execution.validate_active_configuration()
        selected_tests = protocol.validation_test_paths(changed_paths)
        if selected_tests:
            execution.run_validation_suites(selected_tests)
        current_parameters = research_config.load_experiment_config()
        if current_parameters != data["effective_parameters"]:
            raise FrozenOperationMismatch(
                "training parameters changed after the operation was accepted"
            )
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
        data["last_error"] = str(error)[:500]
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
    request = pending["request"]
    if _canonical_fingerprint(request) != pending["request_fingerprint"]:
        raise FrozenOperationMismatch("accepted operation request changed")
    kind = pending["kind"]
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check_scientific_model_deliverable:
        return check_scientific_model_deliverable()
    if args.mark_scientific_model_ready:
        if check_scientific_model_deliverable() != 0:
            return 1
        state = repository.load_state(allow_missing_artifact=True)
        commit = repository.git("rev-parse", "HEAD").strip()
        repository.mark_scientific_model_ready(state, commit)
        repository.write_state(state)
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
    if isinstance(state["pending_operation"], dict):
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
